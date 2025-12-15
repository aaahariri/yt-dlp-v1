"""
Job service for processing transcription jobs from Supabase queue.

This module handles the core job processing logic for video/audio transcription
jobs that are pushed from Supabase Edge Functions via the /jobs endpoint.

Job Processing Flow:
1. Claim document (atomic pending -> processing update)
2. Extract audio from canonical_url
3. Transcribe audio
4. Save transcription to document_transcriptions
5. Mark document completed
6. Ack (delete) queue message

On failure:
- If read_ct < MAX_RETRIES: return to pending, don't ack (will retry after VT)
- If read_ct >= MAX_RETRIES: mark as error, archive message
"""

import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import yt_dlp

from app.config import (
    CACHE_DIR,
    CACHE_TTL_HOURS,
    YTDLP_BINARY,
    get_settings
)
from app.services.supabase_service import get_supabase_client
from app.services.ytdlp_service import run_ytdlp_binary, youtube_rate_limit
from app.services.transcription_service import _transcribe_audio_internal
from app.utils.platform_utils import get_platform_from_url, is_youtube_url
from app.routers.transcription import transcription_semaphore


# =============================================================================
# Helper Functions
# =============================================================================

def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _ack_delete(supabase, queue_name: str, msg_id: int) -> bool:
    """
    Delete message from queue (success acknowledgment).
    Returns True if successful.
    """
    try:
        supabase.rpc("pgmq_delete_one", {
            "queue_name": queue_name,
            "msg_id": msg_id
        }).execute()
        return True
    except Exception as e:
        print(f"WARNING: Failed to ack delete msg_id={msg_id}: {str(e)}")
        return False


def _ack_archive(supabase, queue_name: str, msg_id: int) -> bool:
    """
    Archive message (failed after max retries).
    Returns True if successful.
    """
    try:
        supabase.rpc("pgmq_archive_one", {
            "queue_name": queue_name,
            "msg_id": msg_id
        }).execute()
        return True
    except Exception as e:
        print(f"WARNING: Failed to ack archive msg_id={msg_id}: {str(e)}")
        return False


# =============================================================================
# Audio Extraction (Internal)
# =============================================================================

async def _extract_audio_from_url(url: str) -> Dict[str, Any]:
    """
    Extract audio from URL using yt-dlp.

    This is a simplified version that only handles URLs (not local files)
    for the job processing flow.

    Returns:
        Dict with audio_file path and metadata (video_id, url, duration, platform)
    """
    # Apply rate limiting for YouTube
    if is_youtube_url(url):
        await youtube_rate_limit()

    # Generate unique ID for audio file
    audio_uid = uuid.uuid4().hex[:8]
    output_format = "mp3"
    audio_path = os.path.join(CACHE_DIR, "audio", f"{audio_uid}.{output_format}")

    use_binary = is_youtube_url(url) and os.path.exists(YTDLP_BINARY)

    # Get metadata
    title = "Unknown"
    try:
        if use_binary:
            stdout, stderr, code = run_ytdlp_binary([
                '--skip-download', '--print', '%(title)s',
                url
            ])
            title = stdout.strip() if code == 0 else "Unknown"
        else:
            meta_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown")
    except Exception:
        pass

    # Extract audio using yt-dlp
    if use_binary:
        stdout, stderr, code = run_ytdlp_binary([
            '-f', 'bestaudio/best',
            '-x', '--audio-format', output_format,
            '--audio-quality', '192',
            '-o', audio_path.replace(f'.{output_format}', '.%(ext)s'),
            url
        ], timeout=600)
        if code != 0:
            raise Exception(f"yt-dlp failed: {stderr}")
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': output_format,
                'preferredquality': '192',
            }],
            'outtmpl': audio_path.replace(f'.{output_format}', '.%(ext)s'),
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    # Find actual audio file (yt-dlp may change extension)
    actual_audio_path = None
    audio_cache_dir = os.path.join(CACHE_DIR, "audio")
    for f in os.listdir(audio_cache_dir):
        if f.startswith(audio_uid):
            actual_audio_path = os.path.join(audio_cache_dir, f)
            break

    if not actual_audio_path or not os.path.exists(actual_audio_path):
        raise Exception("Audio extraction completed but file not found")

    # Get additional metadata
    video_id = None
    video_duration = None
    platform = get_platform_from_url(url)

    try:
        if use_binary:
            import json
            stdout, _, code = run_ytdlp_binary([
                '--skip-download', '-j', url
            ])
            if code == 0:
                info = json.loads(stdout)
                video_id = info.get("id")
                video_duration = info.get("duration")
        else:
            meta_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_id = info.get("id")
                video_duration = info.get("duration")
    except Exception:
        pass

    return {
        "audio_file": actual_audio_path,
        "format": output_format,
        "title": title,
        "video_id": video_id,
        "url": url,
        "duration": video_duration,
        "platform": platform
    }


# =============================================================================
# Job Processing
# =============================================================================

async def process_single_job(
    job: Dict[str, Any],
    queue_name: str,
    max_retries: int = 5,
    model_size: str = "medium",
    provider: str = "local"
) -> Dict[str, Any]:
    """
    Process a single transcription job.

    Args:
        job: Job data from queue with msg_id, read_ct, document_id
        queue_name: PGMQ queue name for ack operations
        max_retries: Maximum retry attempts before marking as error
        model_size: Whisper model size (tiny, small, medium, large-v2, etc.)
        provider: Transcription provider (local or openai)

    Returns:
        Result dict with status, msg_id, document_id, and any error info
    """
    msg_id = job.get("msg_id")
    read_ct = int(job.get("read_ct", 1))
    document_id = job.get("document_id")

    # Also check message.document_id if document_id is at top level
    if not document_id and isinstance(job.get("message"), dict):
        document_id = job["message"].get("document_id")

    print(f"INFO: Processing job msg_id={msg_id} document_id={document_id} read_ct={read_ct}")

    # Get Supabase client
    supabase = get_supabase_client()

    # Validate job data
    if not document_id:
        print(f"WARNING: Job {msg_id} missing document_id - archiving")
        _ack_archive(supabase, queue_name, msg_id)
        return {
            "msg_id": msg_id,
            "status": "archived",
            "reason": "missing document_id"
        }

    # Track which step failed for better error messages
    current_step = "initialization"

    try:
        # =================================================================
        # Step 1: Idempotency guard + claim document atomically
        # =================================================================
        current_step = "claiming document"

        claim_result = supabase.table("documents").update({
            "processing_status": "processing",
            "updated_at": _now_iso()
        }).eq("id", document_id).eq("processing_status", "pending").execute()

        if not claim_result.data or len(claim_result.data) == 0:
            # Document not pending - already processed or being processed
            print(f"INFO: Document {document_id} not pending - ack delete stale message")
            _ack_delete(supabase, queue_name, msg_id)
            return {
                "msg_id": msg_id,
                "status": "deleted",
                "reason": "not pending",
                "document_id": document_id
            }

        # =================================================================
        # Step 2: Fetch document details
        # =================================================================
        current_step = "fetching document details"

        doc_result = supabase.table("documents").select(
            "id, canonical_url, metadata, media_format, lang, title"
        ).eq("id", document_id).single().execute()

        if not doc_result.data:
            raise ValueError(f"Document {document_id} not found after claiming")

        doc = doc_result.data

        # =================================================================
        # Step 3: Validate document data
        # =================================================================
        current_step = "validating document data"

        # Get media URL (canonical_url or fallback to metadata)
        media_url = doc.get("canonical_url")
        if not media_url and doc.get("metadata"):
            media_url = doc["metadata"].get("media_url") or doc["metadata"].get("url")

        if not media_url:
            raise ValueError("No media URL found in document (canonical_url or metadata.media_url/url)")

        # Verify media format
        media_format = doc.get("media_format")
        if media_format not in ["video", "audio"]:
            raise ValueError(f"Invalid media_format '{media_format}' (expected 'video' or 'audio')")

        print(f"INFO: Document {document_id}: {media_format} from {media_url[:60]}...")

        # =================================================================
        # Step 4: Extract audio
        # =================================================================
        current_step = f"extracting audio from {media_url[:60]}"

        print(f"INFO: Extracting audio from URL...")
        try:
            audio_result = await _extract_audio_from_url(media_url)
            audio_file = audio_result["audio_file"]
            print(f"INFO: Audio extracted: {audio_file}")
        except Exception as audio_err:
            raise Exception(f"Audio extraction failed: {str(audio_err)}")

        # =================================================================
        # Step 5: Transcribe audio (with semaphore for concurrency)
        # =================================================================
        current_step = f"transcribing audio with {provider}/{model_size}"

        print(f"INFO: Transcribing with provider={provider} model={model_size}...")
        try:
            async with transcription_semaphore:
                transcription = await _transcribe_audio_internal(
                    audio_file=audio_file,
                    language=doc.get("lang"),
                    model_size=model_size,
                    provider=provider,
                    output_format="json",
                    video_id=audio_result.get("video_id"),
                    url=media_url,
                    duration=audio_result.get("duration"),
                    platform=audio_result.get("platform")
                )
        except Exception as transcribe_err:
            raise Exception(f"Transcription failed: {str(transcribe_err)}")

        segments = transcription.get("segments", [])
        print(f"INFO: Transcription complete: {len(segments)} segments")

        # =================================================================
        # Step 6: Upsert to document_transcriptions
        # =================================================================
        current_step = "saving transcription to database"

        print(f"INFO: Saving transcription to document_transcriptions...")

        # Calculate stats for logging (not stored in DB)
        segment_count = len(segments)
        word_count = sum(len(s.get('text', '').split()) for s in segments)

        # Build concise metadata
        settings = get_settings()
        trans_metadata = transcription.get("metadata", {})
        metadata = {
            "model": f"WhisperX-{model_size}",
            "provider": settings.provider_name,
            "duration": audio_result.get("duration"),
            "processing_time": trans_metadata.get("transcription_time"),
            "word_count": word_count,
            "segment_count": segment_count
        }

        upsert_data = {
            "document_id": document_id,
            "segments": segments,
            "language": transcription.get("language", "unknown"),
            "source": "ai",
            "confidence_score": None,
            "metadata": metadata,
            "updated_at": _now_iso()
        }

        try:
            supabase.table("document_transcriptions").upsert(
                upsert_data,
                on_conflict="document_id"
            ).execute()
        except Exception as db_err:
            raise Exception(f"Database save failed: {str(db_err)}")

        print(f"INFO: Transcription saved: {word_count} words, {segment_count} segments")

        # =================================================================
        # Step 7: Mark document completed
        # =================================================================
        current_step = "marking document as completed"

        try:
            supabase.table("documents").update({
                "processing_status": "completed",
                "processed_at": _now_iso(),
                "processing_error": None,
                "updated_at": _now_iso()
            }).eq("id", document_id).execute()
        except Exception as update_err:
            raise Exception(f"Failed to mark document completed: {str(update_err)}")

        # =================================================================
        # Step 8: Ack delete message
        # =================================================================
        _ack_delete(supabase, queue_name, msg_id)

        print(f"INFO: Job completed for document {document_id}")

        return {
            "msg_id": msg_id,
            "status": "completed",
            "document_id": document_id,
            "word_count": word_count,
            "segment_count": segment_count
        }

    except Exception as e:
        # Build descriptive error message with step context
        base_error = str(e)
        error_msg = f"[Step: {current_step}] {base_error}"

        # Truncate if too long but preserve key info
        if len(error_msg) > 500:
            error_msg = error_msg[:480] + "... (truncated)"

        print(f"ERROR: Job processing failed at '{current_step}': {base_error}")

        # Handle retry logic with comprehensive error tracking
        if read_ct >= max_retries:
            # Max retries reached - mark as permanent error
            print(f"ERROR: Max retries reached ({read_ct}/{max_retries}) - marking as error")

            final_error_msg = f"Failed after {read_ct} attempts. Last error: {error_msg}"

            try:
                supabase.table("documents").update({
                    "processing_status": "error",
                    "processing_error": final_error_msg,
                    "updated_at": _now_iso()
                }).eq("id", document_id).execute()
                print(f"INFO: Document {document_id} marked as error")
            except Exception as update_err:
                print(f"WARNING: Failed to update document error status: {update_err}")

            _ack_archive(supabase, queue_name, msg_id)

            return {
                "msg_id": msg_id,
                "status": "archived",
                "error": error_msg,
                "read_ct": read_ct,
                "document_id": document_id
            }
        else:
            # Will retry - mark as pending with retry info
            print(f"WARNING: Retry {read_ct}/{max_retries} - returning to pending")

            retry_error_msg = f"Retry {read_ct}/{max_retries}: {error_msg}"

            try:
                supabase.table("documents").update({
                    "processing_status": "pending",
                    "processing_error": retry_error_msg,
                    "updated_at": _now_iso()
                }).eq("id", document_id).execute()
                print(f"INFO: Document {document_id} returned to pending with retry info")
            except Exception as update_err:
                print(f"WARNING: Failed to update document retry status: {update_err}")

            # Don't ack - message will reappear after VT
            return {
                "msg_id": msg_id,
                "status": "retry",
                "error": error_msg,
                "read_ct": read_ct,
                "document_id": document_id
            }


async def process_job_batch(
    payload: Dict[str, Any],
    max_retries: int = 5,
    model_size: str = "medium",
    provider: str = "local"
) -> Dict[str, Any]:
    """
    Process a batch of transcription jobs from the queue payload.

    Args:
        payload: Full payload from Supabase Edge Function with queue, vt_seconds, jobs
        max_retries: Maximum retry attempts per job
        model_size: Whisper model size
        provider: Transcription provider

    Returns:
        Dict with ok status and results for each job
    """
    queue_name = payload.get("queue", "video_audio_transcription")
    jobs = payload.get("jobs", [])

    print(f"INFO: Processing batch of {len(jobs)} job(s) from queue '{queue_name}'")

    results = []

    # Process jobs sequentially to respect rate limiting and resource constraints
    # Note: The semaphore inside process_single_job handles transcription concurrency
    for job in jobs:
        result = await process_single_job(
            job=job,
            queue_name=queue_name,
            max_retries=max_retries,
            model_size=model_size,
            provider=provider
        )
        results.append(result)

    # Count results by status
    completed = sum(1 for r in results if r.get("status") == "completed")
    retried = sum(1 for r in results if r.get("status") == "retry")
    archived = sum(1 for r in results if r.get("status") == "archived")
    deleted = sum(1 for r in results if r.get("status") == "deleted")

    print(f"INFO: Batch complete - completed:{completed} retry:{retried} archived:{archived} deleted:{deleted}")

    return {
        "ok": True,
        "summary": {
            "total": len(jobs),
            "completed": completed,
            "retry": retried,
            "archived": archived,
            "deleted": deleted
        },
        "results": results
    }
