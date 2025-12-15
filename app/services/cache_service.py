"""
Cache service module for managing temporary files.

This module provides utilities for:
- Finding cached videos by video_id
- Cleaning up expired cache files
- Managing transcription file cleanup
"""

import os
import time
from typing import Optional, Dict
from app.config import (
    CACHE_DIR,
    CACHE_TTL_HOURS,
    TRANSCRIPTIONS_DIR
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
