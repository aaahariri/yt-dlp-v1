"""
Jobs router for receiving transcription jobs from Supabase Edge Functions.

This module provides the endpoint that receives job batches from Supabase's
PGMQ queue via Edge Functions, replacing the polling worker approach.

Endpoint: POST /jobs/video-audio-transcription

Expected payload:
{
    "queue": "video_audio_transcription",
    "vt_seconds": 1800,
    "jobs": [
        {
            "msg_id": 1,
            "read_ct": 1,
            "enqueued_at": "2025-12-15T16:42:03.680992+00:00",
            "document_id": "b5e4b7d1-bab4-49e3-b8bc-66a320bdb4ca",
            "message": {"document_id": "b5e4b7d1-bab4-49e3-b8bc-66a320bdb4ca"}
        }
    ]
}

Authentication: Bearer token via Authorization header (PY_API_TOKEN)
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Body

from app.dependencies import verify_job_token
from app.config import get_settings
from app.services.job_service import process_job_batch


# =============================================================================
# Pydantic Models
# =============================================================================

class JobMessage(BaseModel):
    """Inner message payload in a job."""
    document_id: str


class Job(BaseModel):
    """Single job from the queue."""
    msg_id: int
    read_ct: int = 1
    enqueued_at: Optional[str] = None
    document_id: Optional[str] = None
    message: Optional[JobMessage] = None


class JobBatchPayload(BaseModel):
    """Payload from Supabase Edge Function with batch of jobs."""
    queue: str = Field(default="video_audio_transcription", description="Queue name")
    vt_seconds: int = Field(default=1800, description="Visibility timeout in seconds")
    jobs: List[Job] = Field(..., description="List of jobs to process")


class JobResult(BaseModel):
    """Result for a single processed job."""
    msg_id: int
    status: str  # completed, retry, archived, deleted
    document_id: Optional[str] = None
    reason: Optional[str] = None
    error: Optional[str] = None
    read_ct: Optional[int] = None
    word_count: Optional[int] = None
    segment_count: Optional[int] = None


class JobBatchResponse(BaseModel):
    """Response after processing job batch."""
    ok: bool
    summary: Dict[str, int]
    results: List[JobResult]


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/video-audio-transcription", response_model=JobBatchResponse)
async def handle_video_audio_transcription_jobs(
    payload: JobBatchPayload = Body(...),
    _: bool = Depends(verify_job_token)
) -> JobBatchResponse:
    """
    Process batch of video/audio transcription jobs from Supabase queue.

    This endpoint is called by the Supabase Edge Function when there are
    pending transcription jobs in the PGMQ queue.

    Authentication: Requires Bearer token in Authorization header.

    Job Processing Flow (per job):
    1. Claim document (atomic: pending -> processing)
    2. Fetch document metadata and media URL
    3. Extract audio from canonical_url
    4. Transcribe audio with whisperX or OpenAI
    5. Upsert transcription to document_transcriptions
    6. Mark document as completed
    7. Delete queue message (ack)

    On failure:
    - If read_ct < MAX_RETRIES: return to pending, message retries after VT
    - If read_ct >= MAX_RETRIES: mark as error, archive message

    Returns:
        Summary of processed jobs and individual results
    """
    settings = get_settings()

    # Convert Pydantic model to dict for processing
    payload_dict = {
        "queue": payload.queue,
        "vt_seconds": payload.vt_seconds,
        "jobs": []
    }

    # Flatten job data - document_id can be at top level or in message
    for job in payload.jobs:
        job_dict = {
            "msg_id": job.msg_id,
            "read_ct": job.read_ct,
            "document_id": job.document_id or (job.message.document_id if job.message else None)
        }
        if job.message:
            job_dict["message"] = {"document_id": job.message.document_id}
        payload_dict["jobs"].append(job_dict)

    # Process the batch
    result = await process_job_batch(
        payload=payload_dict,
        max_retries=settings.worker_max_retries,
        model_size=settings.worker_model_size,
        provider=settings.worker_provider
    )

    return JobBatchResponse(**result)


@router.get("/status")
async def get_jobs_endpoint_status(_: bool = Depends(verify_job_token)):
    """
    Health check endpoint for the jobs handler.

    Returns configuration and status information.
    """
    settings = get_settings()

    return {
        "status": "ready",
        "config": {
            "max_retries": settings.worker_max_retries,
            "model_size": settings.worker_model_size,
            "provider": settings.worker_provider,
            "max_concurrent_transcriptions": settings.max_concurrent_transcriptions
        }
    }
