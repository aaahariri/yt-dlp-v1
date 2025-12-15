"""
Transcription router for AI-powered audio transcription and storage.

Handles audio transcription using whisperX or OpenAI Whisper API,
and manages transcription data storage in Supabase.
"""

import asyncio
from fastapi import APIRouter, Query, Depends, HTTPException, Body

from app.dependencies import verify_api_key
from app.config import MAX_CONCURRENT_TRANSCRIPTIONS
from app.models import TranscriptionSaveRequest, TranscriptionSaveResponse
from app.services.transcription_service import _transcribe_audio_internal
from app.services.supabase_service import get_supabase_client


router = APIRouter(tags=["Transcription"])

# Semaphore for concurrency control
transcription_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSCRIPTIONS)


@router.post("/transcribe")
async def transcribe_audio(
    audio_file: str = Query(..., description="Path to audio file on server (from /extract-audio)"),
    language: str = Query(None, description="Language code (auto-detect if not specified)"),
    model_size: str = Query("medium", description="Model size: tiny, small, medium, large-v2, large-v3, turbo"),
    provider: str = Query("local", description="Provider: local (whisperX) or openai"),
    output_format: str = Query("json", description="Output format: json, srt, vtt, text"),
    video_id: str = Query(None, description="Video ID from /extract-audio (for unified response)"),
    url: str = Query(None, description="Video URL from /extract-audio (for unified response)"),
    duration: int = Query(None, description="Video duration from /extract-audio (for unified response)"),
    platform: str = Query(None, description="Platform name from /extract-audio (for unified response)"),
    _: bool = Depends(verify_api_key)
):
    """
    Transcribe audio file using AI.

    Providers:
    - local: whisperX (70x real-time on GPU, 3-5x on CPU, $0 cost, word-level timestamps)
    - openai: OpenAI Whisper API ($0.006/min, managed service)

    Input: audio_file path (from /extract-audio endpoint)
    Output: Transcription in unified format

    Workflow:
    1. POST /extract-audio → get audio_file path and metadata
    2. POST /transcribe → get transcription

    Note: This endpoint is limited to MAX_CONCURRENT_TRANSCRIPTIONS concurrent requests
    to prevent memory overload. Additional requests will wait in queue.
    """
    # Acquire semaphore to limit concurrent transcriptions
    async with transcription_semaphore:
        return await _transcribe_audio_internal(
            audio_file, language, model_size, provider, output_format,
            video_id, url, duration, platform
        )


@router.post("/transcriptions/save")
async def save_transcription(
    request: TranscriptionSaveRequest = Body(...),
    _: bool = Depends(verify_api_key)
) -> TranscriptionSaveResponse:
    """
    Save transcription data to Supabase document_transcriptions table.

    This endpoint stores transcription data linked to an existing document.
    The document must already exist in the `documents` table.

    Required: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.

    Behavior:
    - Uses UPSERT: If transcription exists for document_id, it updates; otherwise inserts
    - Unique constraint: One transcription per document
    - Auto-updates `updated_at` timestamp on updates

    Example workflow:
    1. Create document record (done elsewhere in your system)
    2. GET /subtitles or POST /transcribe → get transcription data
    3. POST /transcriptions/save → store in document_transcriptions table
    """
    try:
        supabase = get_supabase_client()

        # Prepare data for upsert
        transcription_data = {
            "document_id": request.document_id,
            "segments": request.segments,  # JSONB field
            "language": request.language,
            "source": request.source,
            "confidence_score": request.confidence_score,
            "metadata": request.metadata or {}  # JSONB field, default to empty dict
        }

        # Upsert into document_transcriptions table
        # on_conflict uses the unique constraint on document_id
        result = supabase.table("document_transcriptions").upsert(
            transcription_data,
            on_conflict="document_id"
        ).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to save transcription to Supabase - no data returned"
            )

        saved_record = result.data[0]
        record_id = saved_record.get("id")
        created_at = saved_record.get("created_at")
        document_id = saved_record.get("document_id")

        return TranscriptionSaveResponse(
            id=record_id,
            document_id=document_id,
            created_at=created_at,
            message=f"Transcription saved successfully to Supabase with ID: {record_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error saving transcription to Supabase: {str(e)}"
        )


@router.get("/transcriptions/check/{document_id}")
async def check_transcription_exists(
    document_id: str,
    _: bool = Depends(verify_api_key)
):
    """
    Check if a transcription exists for a given document ID.

    Returns transcription status and basic metadata if it exists.

    Required: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.
    """
    try:
        supabase = get_supabase_client()

        # Query by document_id (which has unique constraint)
        result = supabase.table("document_transcriptions").select(
            "id, document_id, language, source, confidence_score, created_at, updated_at"
        ).eq("document_id", document_id).execute()

        if not result.data or len(result.data) == 0:
            return {
                "exists": False,
                "document_id": document_id,
                "transcription": None
            }

        transcription = result.data[0]
        return {
            "exists": True,
            "document_id": document_id,
            "transcription": {
                "id": transcription.get("id"),
                "language": transcription.get("language"),
                "source": transcription.get("source"),
                "confidence_score": transcription.get("confidence_score"),
                "created_at": transcription.get("created_at"),
                "updated_at": transcription.get("updated_at")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking transcription in Supabase: {str(e)}"
        )
