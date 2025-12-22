"""
Cache service module for managing temporary files.

This module provides utilities for:
- Finding cached videos by video_id
- Checking video cache status with expiration details
- Cleaning up expired cache files
- Managing transcription file cleanup
"""

import os
import time
import subprocess
from typing import Optional, Dict, Any
from app.config import (
    CACHE_DIR,
    CACHE_TTL_HOURS,
    TRANSCRIPTIONS_DIR,
    YTDLP_BINARY
)


def get_cached_video(video_id: str) -> Optional[str]:
    """
    Find cached video by video_id.

    Searches the cache directory for a video file matching the given video_id
    and returns its path if it's still fresh (within TTL).

    Args:
        video_id: The unique identifier for the video

    Returns:
        File path if fresh (within TTL), None if expired or missing

    Example:
        >>> cached_path = get_cached_video("dQw4w9WgXcQ")
        >>> if cached_path:
        ...     print(f"Using cached video: {cached_path}")
    """
    cache_dir = os.path.join(CACHE_DIR, "videos")
    if not os.path.exists(cache_dir):
        return None

    for filename in os.listdir(cache_dir):
        if f"-{video_id}." in filename:
            filepath = os.path.join(cache_dir, filename)
            age_hours = (time.time() - os.path.getmtime(filepath)) / 3600
            if age_hours < CACHE_TTL_HOURS:
                return filepath  # Fresh, reuse it
    return None


def check_video_cache_status(video_url: str, logger) -> Dict[str, Any]:
    """
    Check if a video is cached and provide detailed cache status.

    Extracts the video ID from the URL using yt-dlp, checks if the video
    is in the cache, and calculates cache age and expiration time.

    Args:
        video_url: URL of the video to check
        logger: Logger instance for tracking

    Returns:
        Dictionary with cache status containing:
        - cached: bool - whether video is in cache
        - cache_path: str|None - path to cached file if cached
        - cache_age_seconds: int|None - age of cache file in seconds
        - expires_in_seconds: int|None - seconds until cache expires
        - video_id: str|None - extracted video ID
        - error: str|None - error message if extraction failed
    """
    try:
        logger.info(f"Extracting video ID from URL: {video_url}")

        result = subprocess.run(
            [YTDLP_BINARY, '--get-id', video_url],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"Failed to extract video ID: {result.stderr}")
            return {
                "cached": False,
                "cache_path": None,
                "cache_age_seconds": None,
                "expires_in_seconds": None,
                "video_id": None,
                "error": f"Failed to extract video ID: {result.stderr.strip()}"
            }

        video_id = result.stdout.strip()
        logger.info(f"Video ID extracted: {video_id}")

        cached_path = get_cached_video(video_id)

        if cached_path:
            cache_mtime = os.path.getmtime(cached_path)
            cache_age_seconds = int(time.time() - cache_mtime)
            cache_ttl_seconds = CACHE_TTL_HOURS * 3600
            expires_in_seconds = cache_ttl_seconds - cache_age_seconds

            logger.info(f"Video CACHED at {cached_path}")
            logger.info(f"Cache age: {cache_age_seconds}s, expires in: {expires_in_seconds}s")

            return {
                "cached": True,
                "cache_path": cached_path,
                "cache_age_seconds": cache_age_seconds,
                "expires_in_seconds": expires_in_seconds,
                "video_id": video_id,
                "error": None
            }
        else:
            logger.info(f"Video NOT cached (video_id: {video_id})")
            return {
                "cached": False,
                "cache_path": None,
                "cache_age_seconds": None,
                "expires_in_seconds": None,
                "video_id": video_id,
                "error": None
            }

    except subprocess.TimeoutExpired:
        logger.error("Video ID extraction timed out")
        return {
            "cached": False,
            "cache_path": None,
            "cache_age_seconds": None,
            "expires_in_seconds": None,
            "video_id": None,
            "error": "Video ID extraction timed out"
        }
    except Exception as e:
        logger.error(f"Cache check error: {str(e)}")
        return {
            "cached": False,
            "cache_path": None,
            "cache_age_seconds": None,
            "expires_in_seconds": None,
            "video_id": None,
            "error": str(e)
        }


def cleanup_cache() -> Dict[str, int]:
    """
    Delete all cached files older than TTL.

    Iterates through all cache subdirectories (videos, audio, transcriptions, screenshots)
    and removes files that have exceeded the configured TTL.

    Returns:
        Dictionary containing:
        - deleted: Count of files deleted per category
        - total_deleted: Total number of files deleted
        - freed_bytes: Total disk space freed in bytes

    Example:
        >>> result = cleanup_cache()
        >>> print(f"Deleted {result['total_deleted']} files, freed {result['freed_bytes']} bytes")
    """
    cutoff = time.time() - (CACHE_TTL_HOURS * 3600)
    deleted = {"videos": 0, "audio": 0, "transcriptions": 0, "screenshots": 0}
    freed_bytes = 0

    for subdir in deleted.keys():
        dir_path = os.path.join(CACHE_DIR, subdir)
        if os.path.exists(dir_path):
            for filename in os.listdir(dir_path):
                filepath = os.path.join(dir_path, filename)
                if os.path.isfile(filepath) and os.path.getmtime(filepath) < cutoff:
                    freed_bytes += os.path.getsize(filepath)
                    os.remove(filepath)
                    deleted[subdir] += 1

    return {
        "deleted": deleted,
        "total_deleted": sum(deleted.values()),
        "freed_bytes": freed_bytes
    }


def cleanup_old_transcriptions(max_age_hours: int = 1) -> None:
    """
    Remove transcription files older than specified hours.

    This is a specialized cleanup function for transcription files that may need
    more frequent cleanup than the general cache (default 1 hour vs 3 hours for cache).

    Args:
        max_age_hours: Maximum age in hours before file is deleted (default: 1)

    Note:
        Silently handles cleanup errors to not interrupt main functionality.
        Transcription files are typically larger and should be cleaned more aggressively.

    Example:
        >>> cleanup_old_transcriptions(max_age_hours=2)  # Clean files older than 2 hours
    """
    try:
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)

        if not os.path.exists(TRANSCRIPTIONS_DIR):
            return

        for filename in os.listdir(TRANSCRIPTIONS_DIR):
            filepath = os.path.join(TRANSCRIPTIONS_DIR, filename)
            if os.path.isfile(filepath):
                file_mtime = os.path.getmtime(filepath)
                if file_mtime < cutoff_time:
                    os.remove(filepath)
    except Exception as e:
        # Silently handle cleanup errors to not interrupt main functionality
        pass
