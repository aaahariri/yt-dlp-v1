#!/usr/bin/env python3
"""
YouTube Cookie Refresh Scheduler

Automatically refreshes YouTube cookies on a schedule using APScheduler.
Integrates with FastAPI application lifecycle.

Features:
- Scheduled refresh every N days (configurable via YTDLP_COOKIE_REFRESH_DAYS)
- Auto-refresh on startup if cookies missing or expired
- Manual trigger via API endpoint
- Comprehensive logging with timestamps
- Graceful error handling
- Non-blocking background execution

Usage:
    from scripts.cookie_scheduler import start_scheduler, stop_scheduler, trigger_manual_refresh

    # Start on app startup
    start_scheduler()

    # Stop on app shutdown
    stop_scheduler()

    # Manual trigger
    result = trigger_manual_refresh()
"""

import os
import sys
import logging
import threading
import time as time_module
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

# Import the refresh_cookies function from the existing script
# Add scripts directory to path if needed
scripts_dir = Path(__file__).parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

try:
    from refresh_youtube_cookies import refresh_cookies
except ImportError:
    # Fallback if import fails
    refresh_cookies = None
    logging.warning("Could not import refresh_youtube_cookies module")


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[BackgroundScheduler] = None
_refresh_interval_days: int = 5
_last_refresh_time: Optional[datetime] = None
_last_refresh_status: str = "never_run"


def get_config_from_env() -> dict:
    """Load configuration from environment variables."""
    return {
        'refresh_days': int(os.getenv('YTDLP_COOKIE_REFRESH_DAYS', '5')),
        'youtube_email': os.getenv('YOUTUBE_EMAIL'),
        'youtube_password': os.getenv('YOUTUBE_PASSWORD'),
        'cookies_file': os.getenv('YTDLP_COOKIES_FILE', './cookies.txt'),
        'startup_delay': int(os.getenv('YTDLP_STARTUP_REFRESH_DELAY', '30')),  # Seconds to wait before initial refresh
    }


def cookies_need_refresh() -> tuple:
    """
    Check if cookies need to be refreshed.

    Returns:
        (needs_refresh: bool, reason: str)
    """
    config = get_config_from_env()
    cookies_file = config['cookies_file']
    refresh_days = config['refresh_days']

    # Check if file exists
    if not cookies_file or not os.path.exists(cookies_file):
        return True, "cookies_file_missing"

    # Check file size (empty file)
    if os.path.getsize(cookies_file) < 100:  # Minimum reasonable size for cookies
        return True, "cookies_file_empty"

    # Check file modification time (age)
    try:
        mtime = os.path.getmtime(cookies_file)
        file_age_days = (time_module.time() - mtime) / (24 * 3600)

        if file_age_days >= refresh_days:
            return True, f"cookies_expired_age_{file_age_days:.1f}_days"

        # Also check if cookies are about to expire (within 1 day)
        if file_age_days >= (refresh_days - 1):
            return True, f"cookies_expiring_soon_{file_age_days:.1f}_days"

    except Exception as e:
        logger.warning(f"Could not check cookie file age: {e}")
        return True, "cookies_age_check_failed"

    # Check actual cookie expiry by parsing the file
    try:
        with open(cookies_file, 'r') as f:
            content = f.read()

        # Look for YouTube cookies
        has_youtube_cookies = '.youtube.com' in content or 'youtube.com' in content
        if not has_youtube_cookies:
            return True, "no_youtube_cookies_in_file"

        # Parse expiry timestamps from Netscape format
        # Format: domain\tsubdomains\tpath\tsecure\texpiry\tname\tvalue
        lines = content.strip().split('\n')
        now = time_module.time()
        expired_count = 0
        valid_count = 0

        for line in lines:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) >= 6:
                try:
                    expiry = int(parts[4])
                    if expiry > 0:  # 0 means session cookie
                        if expiry < now:
                            expired_count += 1
                        else:
                            valid_count += 1
                except (ValueError, IndexError):
                    continue

        # If more than half of cookies are expired, refresh
        if expired_count > 0 and valid_count == 0:
            return True, "all_cookies_expired"
        if expired_count > valid_count:
            return True, f"most_cookies_expired_{expired_count}_of_{expired_count + valid_count}"

    except Exception as e:
        logger.warning(f"Could not parse cookie file: {e}")
        # Don't fail if we can't parse, rely on file age instead

    return False, "cookies_valid"


def startup_cookie_check():
    """
    Check if cookies need refresh on startup and trigger if needed.
    Runs in a separate thread with a delay to let server fully start.
    """
    config = get_config_from_env()
    delay = config['startup_delay']

    logger.info(f"Startup cookie check scheduled in {delay} seconds...")

    # Wait for server to fully start
    time_module.sleep(delay)

    logger.info("=" * 60)
    logger.info("Running startup cookie check")
    logger.info("=" * 60)

    # Check if credentials are configured
    if not config['youtube_email'] or not config['youtube_password']:
        logger.warning("⚠ Skipping startup cookie check - credentials not configured")
        logger.warning("⚠ Set YOUTUBE_EMAIL and YOUTUBE_PASSWORD in .env")
        return

    # Check if cookies need refresh
    needs_refresh, reason = cookies_need_refresh()

    if needs_refresh:
        logger.info(f"Cookies need refresh: {reason}")
        logger.info("Triggering automatic cookie refresh...")

        # Run the refresh
        result = trigger_manual_refresh()

        if result.get('success'):
            logger.info("✓ Startup cookie refresh completed successfully")
        else:
            logger.error("=" * 60)
            logger.error("WARNING: YOUTUBE AUTHENTICATION FAILED")
            logger.error("=" * 60)
            logger.error(f"Error: {result.get('error')}")
            logger.error("")
            logger.error("MANUAL ACTION REQUIRED:")
            logger.error("  1. Run locally: python scripts/refresh_youtube_cookies.py --interactive")
            logger.error("  2. Complete any Google security challenges in the browser")
            logger.error("  3. Upload cookies.txt and cookies_state.json to server")
            logger.error("")
            logger.error("See Deploy.md for details.")
            logger.error("=" * 60)
    else:
        logger.info(f"✓ Cookies are valid ({reason})")
        logger.info(f"File: {config['cookies_file']}")

        # Log when cookies were last modified
        try:
            mtime = os.path.getmtime(config['cookies_file'])
            age_hours = (time_module.time() - mtime) / 3600
            logger.info(f"Cookie file age: {age_hours:.1f} hours")
        except Exception:
            pass

    logger.info("=" * 60)


def scheduled_cookie_refresh():
    """
    Scheduled job that runs every N days to refresh cookies.
    Logs all attempts and outcomes.
    """
    global _last_refresh_time, _last_refresh_status

    logger.info("=" * 60)
    logger.info("Starting scheduled YouTube cookie refresh")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    config = get_config_from_env()

    # Validate configuration
    if not config['youtube_email'] or not config['youtube_password']:
        logger.error("Cookie refresh skipped: YOUTUBE_EMAIL or YOUTUBE_PASSWORD not configured")
        logger.error("Set these environment variables to enable automated cookie refresh")
        _last_refresh_status = "failed_no_credentials"
        return

    if not refresh_cookies:
        logger.error("Cookie refresh skipped: refresh_youtube_cookies module not available")
        _last_refresh_status = "failed_module_unavailable"
        return

    try:
        # Call the refresh function (non-interactive, headless mode)
        logger.info(f"Refreshing cookies for: {config['youtube_email']}")
        logger.info(f"Output file: {config['cookies_file']}")

        success = refresh_cookies(
            email=config['youtube_email'],
            password=config['youtube_password'],
            output_path=config['cookies_file'],
            interactive=False,  # Always headless for scheduled runs
            timeout=300  # 5 minute timeout
        )

        _last_refresh_time = datetime.now()

        if success:
            logger.info("✓ Cookie refresh completed successfully")
            logger.info(f"Cookies saved to: {config['cookies_file']}")
            logger.info(f"Next refresh scheduled in {config['refresh_days']} days")
            _last_refresh_status = "success"
        else:
            logger.error("=" * 60)
            logger.error("WARNING: YOUTUBE AUTHENTICATION FAILED")
            logger.error("=" * 60)
            logger.error("Possible issues:")
            logger.error("  - Google security challenge (new IP/device)")
            logger.error("  - 2FA enabled on account")
            logger.error("  - Incorrect credentials")
            logger.error("  - Playwright/Chromium not installed")
            logger.error("")
            logger.error("MANUAL ACTION REQUIRED:")
            logger.error("  1. Run locally: python scripts/refresh_youtube_cookies.py --interactive")
            logger.error("  2. Complete any Google security challenges in the browser")
            logger.error("  3. Upload cookies.txt and cookies_state.json to server")
            logger.error("")
            logger.error("See Deploy.md for details.")
            logger.error("=" * 60)
            _last_refresh_status = "failed_refresh_error"

    except Exception as e:
        logger.error(f"✗ Cookie refresh failed with exception: {str(e)}")
        logger.exception("Full traceback:")
        _last_refresh_status = f"failed_exception: {str(e)}"
        _last_refresh_time = datetime.now()

    logger.info("=" * 60)


def trigger_manual_refresh() -> dict:
    """
    Manually trigger a cookie refresh immediately.
    Returns status dict with success/failure info.
    """
    global _last_refresh_time, _last_refresh_status

    logger.info("Manual cookie refresh triggered")

    config = get_config_from_env()

    # Validate configuration
    if not config['youtube_email'] or not config['youtube_password']:
        return {
            "success": False,
            "error": "YOUTUBE_EMAIL or YOUTUBE_PASSWORD not configured",
            "timestamp": datetime.now().isoformat()
        }

    if not refresh_cookies:
        return {
            "success": False,
            "error": "refresh_youtube_cookies module not available",
            "timestamp": datetime.now().isoformat()
        }

    try:
        logger.info(f"Refreshing cookies for: {config['youtube_email']}")

        success = refresh_cookies(
            email=config['youtube_email'],
            password=config['youtube_password'],
            output_path=config['cookies_file'],
            interactive=False,
            timeout=300
        )

        _last_refresh_time = datetime.now()

        if success:
            logger.info("✓ Manual cookie refresh completed successfully")
            _last_refresh_status = "success_manual"
            return {
                "success": True,
                "message": "Cookies refreshed successfully",
                "cookies_file": config['cookies_file'],
                "timestamp": _last_refresh_time.isoformat()
            }
        else:
            logger.error("✗ Manual cookie refresh failed")
            _last_refresh_status = "failed_manual"
            return {
                "success": False,
                "error": "Cookie refresh failed. Check server logs for details.",
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.error(f"✗ Manual cookie refresh failed: {str(e)}")
        logger.exception("Full traceback:")
        _last_refresh_status = f"failed_manual_exception: {str(e)}"
        _last_refresh_time = datetime.now()
        return {
            "success": False,
            "error": str(e),
            "timestamp": _last_refresh_time.isoformat()
        }


def start_scheduler():
    """
    Initialize and start the background scheduler.
    Called on FastAPI app startup.

    Also starts a background thread to check cookies on startup
    and refresh if missing or expired.
    """
    global _scheduler, _refresh_interval_days

    if _scheduler is not None:
        logger.warning("Scheduler already running, skipping start")
        return

    config = get_config_from_env()
    _refresh_interval_days = config['refresh_days']

    logger.info("=" * 60)
    logger.info("YouTube Cookie Refresh Scheduler Starting")
    logger.info("=" * 60)
    logger.info(f"Refresh interval: Every {_refresh_interval_days} days")
    logger.info(f"Startup check delay: {config['startup_delay']} seconds")
    logger.info(f"Email configured: {config['youtube_email'] is not None}")
    logger.info(f"Password configured: {config['youtube_password'] is not None}")
    logger.info(f"Cookies file: {config['cookies_file']}")

    # Check current cookie status
    needs_refresh, reason = cookies_need_refresh()
    logger.info(f"Current cookie status: {reason}")

    if not config['youtube_email'] or not config['youtube_password']:
        logger.warning("⚠ Cookie refresh scheduler started but credentials not configured")
        logger.warning("⚠ Scheduled refreshes will be skipped until YOUTUBE_EMAIL and YOUTUBE_PASSWORD are set")
    else:
        logger.info("✓ Credentials configured - scheduled refreshes enabled")

    # Create scheduler
    _scheduler = BackgroundScheduler(
        job_defaults={
            'coalesce': True,  # Combine multiple missed runs into one
            'max_instances': 1,  # Only one refresh job at a time
        }
    )

    # Schedule the periodic refresh job
    _scheduler.add_job(
        func=scheduled_cookie_refresh,
        trigger=IntervalTrigger(days=_refresh_interval_days),
        id='youtube_cookie_refresh',
        name='YouTube Cookie Refresh',
        replace_existing=True,
    )

    # Start the scheduler
    _scheduler.start()

    # Get next run time
    next_run = _scheduler.get_job('youtube_cookie_refresh').next_run_time
    logger.info(f"✓ Scheduler started successfully")
    logger.info(f"Next scheduled refresh: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Start background thread for startup cookie check
    # This runs after a delay to let the server fully start
    if config['youtube_email'] and config['youtube_password']:
        startup_thread = threading.Thread(
            target=startup_cookie_check,
            name="StartupCookieCheck",
            daemon=True
        )
        startup_thread.start()
        logger.info(f"✓ Startup cookie check thread started (will run in {config['startup_delay']}s)")
    else:
        logger.warning("⚠ Startup cookie check skipped - credentials not configured")

    logger.info("=" * 60)


def stop_scheduler():
    """
    Gracefully stop the scheduler.
    Called on FastAPI app shutdown.
    """
    global _scheduler

    if _scheduler is None:
        logger.warning("Scheduler not running, skipping stop")
        return

    logger.info("Stopping YouTube cookie refresh scheduler...")
    _scheduler.shutdown(wait=True)
    _scheduler = None
    logger.info("✓ Scheduler stopped successfully")


def get_scheduler_status() -> dict:
    """
    Get current scheduler status for monitoring/debugging.
    Returns dict with scheduler state, next run time, last refresh info.
    """
    global _scheduler, _last_refresh_time, _last_refresh_status, _refresh_interval_days

    if _scheduler is None:
        return {
            "running": False,
            "message": "Scheduler not started"
        }

    job = _scheduler.get_job('youtube_cookie_refresh')
    config = get_config_from_env()

    return {
        "running": True,
        "refresh_interval_days": _refresh_interval_days,
        "next_run_time": job.next_run_time.isoformat() if job and job.next_run_time else None,
        "last_refresh_time": _last_refresh_time.isoformat() if _last_refresh_time else None,
        "last_refresh_status": _last_refresh_status,
        "credentials_configured": bool(config['youtube_email'] and config['youtube_password']),
        "cookies_file": config['cookies_file'],
        "cookies_file_exists": os.path.exists(config['cookies_file']) if config['cookies_file'] else False,
    }


# Provide both named and default exports for flexibility
__all__ = [
    'start_scheduler',
    'stop_scheduler',
    'trigger_manual_refresh',
    'get_scheduler_status',
    'cookies_need_refresh',
]
