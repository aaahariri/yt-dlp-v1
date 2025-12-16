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
# Async Helper
# =============================================================================
def run_async(coro):
    """
    Run an async coroutine safely, handling existing event loops.

    RunPod's async handler support has known issues (GitHub #387), so we use
    a sync handler and manage the event loop ourselves.
    """
    try:
        # Try to get existing loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context - create new loop in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            # No running loop - use it directly
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop exists - create one
        return asyncio.run(coro)


# =============================================================================
# RunPod Handler
# =============================================================================
def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod sync handler - receives job, delegates to FastAPI services.

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
        Uses sync handler with manual event loop management because RunPod's
        async handler support has known issues (coroutines not awaited).
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

    # Process jobs using run_async helper for safe event loop handling
    logger.info("-" * 40)
    logger.info("STARTING JOB PROCESSING")
    logger.info("-" * 40)

    try:
        result = run_async(
            process_job_batch(
                payload=job_input,
                max_retries=settings.worker_max_retries,
                model_size=settings.worker_model_size,
                provider=settings.worker_provider
            )
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
    import os

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

    # Check yt-dlp binary
    ytdlp_binary = os.environ.get("YTDLP_BINARY", "./bin/yt-dlp")
    if os.path.exists(ytdlp_binary):
        startup_logger.info(f"yt-dlp binary: {ytdlp_binary} (EXISTS)")
    else:
        startup_logger.warning(f"yt-dlp binary: {ytdlp_binary} (NOT FOUND)")

    # Check cookies file
    cookies_file = os.environ.get("YTDLP_COOKIES_FILE", "./cookies.txt")
    startup_logger.info(f"Cookies path: {cookies_file}")
    if os.path.exists(cookies_file):
        file_size = os.path.getsize(cookies_file)
        startup_logger.info(f"Cookies file: EXISTS ({file_size} bytes)")
    else:
        startup_logger.warning(f"Cookies file: NOT FOUND at {cookies_file}")
        # List directory to help debug
        cookies_dir = os.path.dirname(cookies_file) or "."
        if os.path.exists(cookies_dir):
            files = os.listdir(cookies_dir)
            startup_logger.info(f"Files in {cookies_dir}: {files[:20]}")  # First 20 files

    startup_logger.info("Handler ready, waiting for jobs...")
    startup_logger.info("=" * 60)

    # Start RunPod serverless worker
    runpod.serverless.start({"handler": handler})
