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
import logging
from typing import Dict, Any
from app.services.job_service import process_job_batch
from app.config import get_settings


# =============================================================================
# Logging Setup
# =============================================================================
def setup_logger(log_level=logging.INFO):
    """
    Configure logger for RunPod serverless environment.

    RunPod captures stdout/stderr and displays in the console.
    Using Python's logging module provides better formatting and control.
    """
    log_format = logging.Formatter(
        '%(asctime)s | %(levelname)s | [%(request_id)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger("runpod_handler")
    logger.setLevel(log_level)

    # Console handler (captured by RunPod)
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)

    return logger


# Initialize logger at module level
base_logger = setup_logger()


def get_job_logger(job_id: str):
    """Create a logger adapter with the job/request ID for tracing."""
    return logging.LoggerAdapter(base_logger, {"request_id": job_id})


# =============================================================================
# RunPod Handler
# =============================================================================
async def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod async handler - receives job, delegates to FastAPI services.

    Input format (from Supabase via RunPod):
    {
        "id": "runpod-job-id",
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

    Note:
        This is an async handler because process_job_batch is async and
        RunPod natively supports async handlers.
    """
    # Get RunPod job ID for logging
    runpod_job_id = job.get("id", "unknown")
    logger = get_job_logger(runpod_job_id)

    logger.info("=" * 60)
    logger.info("JOB RECEIVED")
    logger.info("=" * 60)

    job_input = job.get("input", {})

    # Validate input structure
    jobs = job_input.get("jobs", [])
    if not jobs or not isinstance(jobs, list):
        logger.warning("Invalid or empty jobs list received")
        return {
            "ok": False,
            "error": "Invalid or empty jobs list",
            "summary": {"total": 0, "completed": 0, "retry": 0, "archived": 0, "deleted": 0}
        }

    # Log job details
    document_ids = [j.get("document_id", "?")[:8] for j in jobs]
    logger.info(f"Jobs to process: {len(jobs)}")
    logger.info(f"Document IDs: {document_ids}")
    logger.info(f"Queue: {job_input.get('queue', 'default')}")

    # Load settings with error handling
    try:
        settings = get_settings()
        logger.info(f"Model: {settings.worker_model_size}, Provider: {settings.worker_provider}")
    except Exception as e:
        logger.error(f"Configuration error: {str(e)}")
        return {
            "ok": False,
            "error": f"Configuration error: {str(e)}",
            "summary": {"total": len(jobs), "completed": 0, "retry": 0, "archived": 0, "deleted": 0}
        }

    # Process jobs (already in async context since handler is async)
    logger.info("-" * 40)
    logger.info("STARTING JOB PROCESSING")
    logger.info("-" * 40)

    try:
        result = await process_job_batch(
            payload=job_input,
            max_retries=settings.worker_max_retries,
            model_size=settings.worker_model_size,
            provider=settings.worker_provider
        )

        # Log summary
        summary = result.get("summary", {})
        logger.info("-" * 40)
        logger.info("JOB PROCESSING COMPLETE")
        logger.info("-" * 40)
        logger.info(f"Total: {summary.get('total', 0)}")
        logger.info(f"Completed: {summary.get('completed', 0)}")
        logger.info(f"Retry: {summary.get('retry', 0)}")
        logger.info(f"Archived: {summary.get('archived', 0)}")
        logger.info(f"Deleted: {summary.get('deleted', 0)}")
        logger.info("=" * 60)

        return result

    except Exception as e:
        # Catch any unhandled exceptions and return structured error
        error_msg = f"Handler processing error: {str(e)}"
        logger.error(error_msg)
        logger.exception("Full traceback:")
        logger.info("=" * 60)

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
    # Log startup
    startup_logger = logging.LoggerAdapter(base_logger, {"request_id": "STARTUP"})
    startup_logger.info("=" * 60)
    startup_logger.info("RunPod Handler Starting")
    startup_logger.info("=" * 60)

    try:
        settings = get_settings()
        startup_logger.info(f"Model Size: {settings.worker_model_size}")
        startup_logger.info(f"Provider: {settings.worker_provider}")
        startup_logger.info(f"Max Retries: {settings.worker_max_retries}")
    except Exception as e:
        startup_logger.warning(f"Could not load settings at startup: {e}")

    startup_logger.info("Handler ready, waiting for jobs...")
    startup_logger.info("=" * 60)

    # Start RunPod serverless worker
    runpod.serverless.start({"handler": handler})
