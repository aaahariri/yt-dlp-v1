"""
RunPod Serverless Handler - Orchestration Layer

This is a thin wrapper that receives RunPod jobs and delegates
to the existing FastAPI job processing logic. No business logic here.

All processing results are saved directly to Supabase by job_service.py,
so there's no need to return results to the caller - they can check the
database for status updates.
"""
import runpod
import asyncio
from app.services.job_service import process_job_batch
from app.config import get_settings


def handler(job):
    """
    RunPod handler - receives job, delegates to FastAPI services.

    Input format (from Supabase via RunPod):
    {
        "input": {
            "queue": "video_audio_transcription",
            "vt_seconds": 1800,
            "jobs": [{"msg_id": 1, "read_ct": 1, "document_id": "uuid"}]
        }
    }

    Returns:
        Result dict with ok status, summary, and individual job results
    """
    job_input = job.get("input", {})

    # Validate input
    if not job_input.get("jobs"):
        return {"ok": False, "error": "No jobs provided in input"}

    settings = get_settings()

    # Delegate to existing job processing (runs async internally)
    # Create new event loop for this handler invocation
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            process_job_batch(
                payload=job_input,
                max_retries=settings.worker_max_retries,
                model_size=settings.worker_model_size,
                provider=settings.worker_provider
            )
        )
    finally:
        loop.close()

    return result


if __name__ == "__main__":
    # Start RunPod serverless worker
    runpod.serverless.start({"handler": handler})
