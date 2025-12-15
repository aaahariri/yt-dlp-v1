"""
Cache router module for managing cached files and downloads.

This module provides endpoints for:
- Cleaning up expired cache files
- Listing cached files by type
- Listing saved downloads
"""

import os
import time
from datetime import datetime
from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Dict, List, Any

from app.dependencies import verify_api_key
from app.config import CACHE_DIR, DOWNLOADS_DIR, CACHE_TTL_HOURS
from app.services.cache_service import cleanup_cache


router = APIRouter(tags=["Cache"])


@router.delete("/cache/cleanup")
async def cache_cleanup(_: bool = Depends(verify_api_key)):
    """
    Delete all cached files older than CACHE_TTL_HOURS.

    Use cases:
    - Cron job target: 0 * * * * curl -X DELETE .../cache/cleanup
    - Manual cleanup trigger

    Note: Also triggered automatically on transcription requests.
    """
    result = cleanup_cache()
    return {
        "message": f"Cleanup complete. Deleted {result['total_deleted']} files.",
        "deleted": result["deleted"],
        "freed_bytes": result["freed_bytes"],
        "ttl_hours": CACHE_TTL_HOURS
    }


@router.get("/cache")
async def list_cache(
    type: str = Query(None, description="Filter by type: videos, audio, transcriptions, screenshots"),
    _: bool = Depends(verify_api_key)
):
    """
    List all cached files with metadata.
    Optional filter by type.
    """
    subdirs = [type] if type else ["videos", "audio", "transcriptions", "screenshots"]
    files = []
    total_size = 0

    for subdir in subdirs:
        dir_path = os.path.join(CACHE_DIR, subdir)
        if not os.path.exists(dir_path):
            continue

        for filename in os.listdir(dir_path):
            filepath = os.path.join(dir_path, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                age_hours = (time.time() - stat.st_mtime) / 3600

                files.append({
                    "filename": filename,
                    "type": subdir.rstrip('s'),  # "videos" -> "video"
                    "path": filepath,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "age_hours": round(age_hours, 2),
                    "expires_in_hours": round(max(0, CACHE_TTL_HOURS - age_hours), 2)
                })
                total_size += stat.st_size

    # Sort by age (newest first)
    files.sort(key=lambda x: x["age_hours"])

    return {
        "files": files,
        "summary": {
            "total_files": len(files),
            "total_size_bytes": total_size,
            "ttl_hours": CACHE_TTL_HOURS
        }
    }


@router.get("/downloads/list")
async def list_downloads(_: bool = Depends(verify_api_key)):
    try:
        files = []
        if os.path.exists(DOWNLOADS_DIR):
            for filename in os.listdir(DOWNLOADS_DIR):
                filepath = os.path.join(DOWNLOADS_DIR, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    files.append({
                        "filename": filename,
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "path": os.path.relpath(filepath, start=".")
                    })

        return {"downloads": files, "count": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing downloads: {str(e)}")
