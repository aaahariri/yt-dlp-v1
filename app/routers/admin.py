"""
Admin router for administrative endpoints.

This module provides endpoints for:
- Manual cookie refresh triggering
- Cookie scheduler status monitoring
- Transcription worker status monitoring
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.dependencies import verify_api_key
from scripts.cookie_scheduler import trigger_manual_refresh, get_scheduler_status

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/refresh-cookies")
async def admin_refresh_cookies(_: bool = Depends(verify_api_key)):
    """
    Manually trigger YouTube cookie refresh immediately.

    This endpoint allows manual triggering of the cookie refresh process
    that normally runs on a schedule (every YTDLP_COOKIE_REFRESH_DAYS days).

    Use cases:
    - Auth failures detected during video downloads
    - Proactive refresh before scheduled time
    - Testing cookie refresh setup

    Requirements:
    - YOUTUBE_EMAIL and YOUTUBE_PASSWORD environment variables must be set
    - Playwright and Chromium must be installed (playwright install chromium)

    Returns:
    - success: Boolean indicating if refresh succeeded
    - message/error: Status message
    - cookies_file: Path to cookies file (on success)
    - timestamp: ISO timestamp of refresh attempt
    """
    result = trigger_manual_refresh()
    if result["success"]:
        return JSONResponse(content=result, status_code=200)
    else:
        return JSONResponse(content=result, status_code=500)


@router.get("/cookie-scheduler/status")
async def get_cookie_scheduler_status(_: bool = Depends(verify_api_key)):
    """
    Get current status of the cookie refresh scheduler.

    Returns information about:
    - Scheduler running state
    - Refresh interval (days)
    - Next scheduled refresh time
    - Last refresh timestamp and status
    - Credentials configuration status
    - Cookies file path and existence

    Useful for monitoring and debugging the automated cookie refresh system.
    """
    status = get_scheduler_status()
    return JSONResponse(content=status, status_code=200)


@router.get("/transcription-worker/status")
async def get_transcription_worker_status(_: bool = Depends(verify_api_key)):
    """
    Get current status of the transcription worker.

    Returns information about:
    - Worker running state (enabled/disabled)
    - Job statistics (processed, failed, retried)
    - Last poll time and last job time
    - Recent errors (last 5)
    - Worker configuration (poll_interval, batch_size, etc.)

    Useful for monitoring background transcription processing.
    """
    try:
        from scripts.transcription_worker import get_worker_status
        status = get_worker_status()
        return JSONResponse(content=status, status_code=200)
    except ImportError:
        return JSONResponse(
            content={"running": False, "error": "Worker module not available"},
            status_code=200
        )
