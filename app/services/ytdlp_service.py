"""
YT-DLP service module.

Handles yt-dlp binary execution with rate limiting, authentication,
and automatic cookie refresh on auth failures.
"""

import os
import re
import time
import random
import asyncio
import subprocess
from typing import Tuple

from app.config import (
    YTDLP_BINARY,
    YTDLP_COOKIES_FILE,
    YTDLP_MIN_SLEEP,
    YTDLP_MAX_SLEEP,
    YTDLP_SLEEP_REQUESTS,
    YTDLP_EXTRACTOR_ARGS,
    CACHE_DIR,
)
from scripts.cookie_scheduler import trigger_manual_refresh
from app.services.supabase_service import send_youtube_auth_alert


# Track last YouTube request time for rate limiting
_last_youtube_request = 0
_youtube_request_lock = asyncio.Lock()


async def youtube_rate_limit():
    """Apply rate limiting for YouTube requests with random delay."""
    global _last_youtube_request
    async with _youtube_request_lock:
        now = time.time()
        elapsed = now - _last_youtube_request
        if elapsed < YTDLP_MIN_SLEEP:
            delay = random.uniform(YTDLP_MIN_SLEEP, YTDLP_MAX_SLEEP)
            print(f"INFO: Rate limiting - sleeping {delay:.1f}s before YouTube request")
            await asyncio.sleep(delay)
        _last_youtube_request = time.time()


def run_ytdlp_binary(args: list, timeout: int = 300, retry_on_auth_failure: bool = True) -> tuple:
    """
    Run yt-dlp standalone binary with given arguments.
    Returns (stdout, stderr, return_code).
    Uses Deno for JavaScript challenges (required for YouTube 2025.11+).

    Auto-detects authentication failures and triggers cookie refresh on first retry.

    Args:
        args: List of yt-dlp command arguments
        timeout: Command timeout in seconds
        retry_on_auth_failure: If True, attempt cookie refresh and retry once on auth errors

    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    cmd = [YTDLP_BINARY] + args

    # Add rate limiting options
    cmd.extend([
        '--sleep-requests', str(YTDLP_SLEEP_REQUESTS),
        '--sleep-interval', str(YTDLP_MIN_SLEEP),
        '--max-sleep-interval', str(YTDLP_MAX_SLEEP),
    ])

    # Add cookies if configured
    if YTDLP_COOKIES_FILE and os.path.exists(YTDLP_COOKIES_FILE):
        cmd.extend(['--cookies', YTDLP_COOKIES_FILE])
        print(f"INFO: Using cookies file: {YTDLP_COOKIES_FILE}")
    else:
        print(f"WARNING: Cookies file not found: {YTDLP_COOKIES_FILE} (exists={os.path.exists(YTDLP_COOKIES_FILE) if YTDLP_COOKIES_FILE else 'N/A'})")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        stdout, stderr, returncode = result.stdout, result.stderr, result.returncode

        # Detect authentication failures in stderr
        auth_failure_patterns = [
            r'Sign in to confirm you\'?re not a bot',
            r'This video requires authentication',
            r'requires? authentication',
            r'HTTP Error 403',
            r'This video is not available',
            r'Video unavailable',
            r'Private video',
            r'This video is private',
            r'age.restricted',
            r'members.?only',
        ]

        is_auth_failure = any(
            re.search(pattern, stderr, re.IGNORECASE) or re.search(pattern, stdout, re.IGNORECASE)
            for pattern in auth_failure_patterns
        )

        # If auth failure detected and retry enabled, attempt cookie refresh and retry once
        if is_auth_failure and retry_on_auth_failure and returncode != 0:
            print("WARNING: Authentication failure detected in yt-dlp output")
            print(f"WARNING: Error message: {stderr[:200]}")
            print("INFO: Attempting automatic cookie refresh...")

            # Trigger cookie refresh
            refresh_result = trigger_manual_refresh()

            if refresh_result.get("success"):
                print("INFO: Cookie refresh successful, retrying download...")
                # Retry once with fresh cookies (disable retry to prevent infinite loop)
                return run_ytdlp_binary(args, timeout, retry_on_auth_failure=False)
            else:
                print("=" * 60)
                print("WARNING: YOUTUBE AUTHENTICATION FAILED")
                print("=" * 60)
                print(f"Cookie refresh error: {refresh_result.get('error')}")
                print("")
                print("MANUAL ACTION REQUIRED:")
                print("  1. Run locally: python scripts/refresh_youtube_cookies.py --interactive")
                print("  2. Complete any Google security challenges in the browser")
                print("  3. Upload cookies.txt and cookies_state.json to server")
                print("")
                print("See Deploy.md for details.")
                print("=" * 60)

                # Send alert to system_alerts table (with 60-min cooldown)
                send_youtube_auth_alert(
                    error_message=refresh_result.get('error', 'Unknown error'),
                    context={"stderr_preview": stderr[:500] if stderr else None}
                )

        return stdout, stderr, returncode

    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except Exception as e:
        return "", str(e), 1
