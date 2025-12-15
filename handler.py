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
from typing import Dict, Any
from app.services.job_service import process_job_batch
from app.config import get_settings


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
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

    Raises:
        Never - all exceptions are caught and returned as error responses
    """
    job_input = job.get("input", {})

    # Validate input structure
    jobs = job_input.get("jobs", [])
    if not jobs or not isinstance(jobs, list):
        return {
            "ok": False,
            "error": "Invalid or empty jobs list",
            "summary": {"total": 0, "completed": 0, "retry": 0, "archived": 0, "deleted": 0}
        }

    # Load settings with error handling
    try:
        settings = get_settings()
    except Exception as e:
        return {
            "ok": False,
            "error": f"Configuration error: {str(e)}",
            "summary": {"total": len(jobs), "completed": 0, "retry": 0, "archived": 0, "deleted": 0}
        }

    # Process jobs using asyncio.run() for proper event loop management
    try:
        result = asyncio.run(
            process_job_batch(
                payload=job_input,
                max_retries=settings.worker_max_retries,
                model_size=settings.worker_model_size,
                provider=settings.worker_provider
            )
        )
        return result
    except Exception as e:
        # Catch any unhandled exceptions and return structured error
        error_msg = f"Handler processing error: {str(e)}"
        print(f"ERROR: {error_msg}")
        return {
            "ok": False,
            "error": error_msg,
            "summary": {
                "total": len(jobs),
                "completed": 0,
                "retry": 0,
                "archived": 0,
                "deleted": 0,
                "failed": len(jobs)
            },
            "results": []
        }


if __name__ == "__main__":
    # Start RunPod serverless worker
    runpod.serverless.start({"handler": handler})
