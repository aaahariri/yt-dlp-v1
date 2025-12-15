"""
Screenshot router for video frame extraction.

This module handles screenshot extraction from videos at specified timestamps,
with support for caching, Supabase upload, and multiple timestamp formats.
"""

import os
import hashlib
import yt_dlp
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body

from app.dependencies import verify_api_key
from app.config import CACHE_DIR, YTDLP_BINARY
from app.models import ScreenshotRequest, ScreenshotResponse, ScreenshotResult
from app.services.ytdlp_service import run_ytdlp_binary, youtube_rate_limit
from app.services.screenshot_service import extract_screenshot
from app.services.supabase_service import upload_screenshot_to_supabase, save_screenshot_metadata
from app.services.cache_service import get_cached_video, cleanup_cache
from app.utils.platform_utils import is_youtube_url, get_platform_prefix
from app.utils.timestamp_utils import parse_timestamp_to_seconds, format_seconds_to_srt


router = APIRouter(tags=["Screenshot"])


@router.post("/screenshot/video", response_model=ScreenshotResponse)
async def screenshot_video(
    request: ScreenshotRequest = Body(...),
    _: bool = Depends(verify_api_key)
) -> ScreenshotResponse:
    """
    Extract screenshots from video at specified timestamps.

    - Caches downloaded videos for reuse (subsequent requests skip download)
    - Supports SRT timestamps ("00:01:30,500") or float seconds (90.5)
    - Optional Supabase upload

    Workflow:
    1. Check cache for existing video (by video_id)
    2. If not cached, download video to ./cache/videos/
    3. Extract screenshots with FFmpeg
    4. Optional: upload to Supabase
    5. Return screenshot paths
    """
    # Trigger cache cleanup at start of request
    cleanup_cache()

    try:
        use_binary = is_youtube_url(request.video_url) and os.path.exists(YTDLP_BINARY)
        platform = get_platform_prefix(request.video_url)

        # Apply rate limiting for YouTube
        if is_youtube_url(request.video_url):
            await youtube_rate_limit()

        # Extract video metadata
        if use_binary:
            # Use standalone binary for YouTube (requires Deno)
            stdout, stderr, code = run_ytdlp_binary([
                '--skip-download', '--print', '%(id)s\n%(title)s\n%(duration)s',
                request.video_url
            ])
            if code != 0:
                raise HTTPException(status_code=500, detail=f"Failed to extract metadata: {stderr}")
            lines = stdout.strip().split('\n')
            video_id = lines[0] if len(lines) > 0 else None
            title = lines[1] if len(lines) > 1 else 'Unknown'
            duration = int(lines[2]) if len(lines) > 2 and lines[2].isdigit() else None
        else:
            # Use Python library for non-YouTube
            meta_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                info = ydl.extract_info(request.video_url, download=False)
                video_id = info.get('id')
                title = info.get('title', 'Unknown')
                duration = info.get('duration')

        # Check cache for existing video
        video_path = get_cached_video(video_id)
        video_cached = video_path is not None

        if not video_path:
            # Download video to cache
            video_filename = f"{platform}-{video_id}.mp4"
            video_path = os.path.join(CACHE_DIR, "videos", video_filename)

            if use_binary:
                # Use standalone binary for YouTube
                stdout, stderr, code = run_ytdlp_binary([
                    '-f', 'best[height<=1080]',
                    '-o', video_path.replace('.mp4', '.%(ext)s'),
                    '--merge-output-format', 'mp4',
                    request.video_url
                ], timeout=600)
                if code != 0:
                    raise HTTPException(status_code=500, detail=f"Failed to download video: {stderr}")
            else:
                # Use Python library for non-YouTube
                ydl_opts = {
                    'format': 'best[height<=1080]',
                    'outtmpl': video_path.replace('.mp4', '.%(ext)s'),
                    'quiet': True,
                    'merge_output_format': 'mp4',
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([request.video_url])

            # Find actual downloaded file (extension may vary)
            cache_videos_dir = os.path.join(CACHE_DIR, "videos")
            for f in os.listdir(cache_videos_dir):
                if f.startswith(f"{platform}-{video_id}"):
                    video_path = os.path.join(cache_videos_dir, f)
                    break

        if not video_path or not os.path.exists(video_path):
            raise HTTPException(status_code=500, detail="Failed to download video")

        # Extract screenshots
        screenshots = []
        failed_timestamps = []
        screenshots_dir = os.path.join(CACHE_DIR, "screenshots")

        for ts in request.timestamps:
            try:
                ts_seconds = parse_timestamp_to_seconds(ts)
                ts_ms = int(ts_seconds * 1000)

                # Output path: {video_id}-{timestamp_ms}.jpg
                output_filename = f"{video_id}-{ts_ms}.jpg"
                output_path = os.path.join(screenshots_dir, output_filename)

                # Extract frame
                result = extract_screenshot(video_path, ts_seconds, output_path, request.quality)

                screenshot_result = ScreenshotResult(
                    timestamp=ts_seconds,
                    timestamp_formatted=format_seconds_to_srt(ts_seconds),
                    file_path=result["file_path"],
                    width=result["width"],
                    height=result["height"],
                    size_bytes=result["size_bytes"],
                    supabase_url=None
                )

                # Optional Supabase upload
                if request.upload_to_supabase:
                    storage_path = f"screenshots/{video_id}/{ts_ms}.jpg"
                    upload_result = upload_screenshot_to_supabase(output_path, storage_path)
                    screenshot_result.supabase_url = upload_result["public_url"]

                    # Save metadata to database
                    save_screenshot_metadata({
                        "type": "screenshot",
                        "storage_path": storage_path,
                        "storage_bucket": "public_media",
                        "content_type": "image/jpeg",
                        "size_bytes": result["size_bytes"],
                        "source_url": request.video_url,
                        "source_url_hash": hashlib.md5(request.video_url.encode()).hexdigest(),
                        "title": f"{title} - {format_seconds_to_srt(ts_seconds)}",
                        "document_id": request.document_id,
                        "metadata": {
                            "video_id": video_id,
                            "timestamp": ts_seconds,
                            "timestamp_formatted": format_seconds_to_srt(ts_seconds),
                            "width": result["width"],
                            "height": result["height"],
                            "platform": platform.lower()
                        }
                    })

                screenshots.append(screenshot_result)

            except Exception as e:
                failed_timestamps.append(f"{ts}: {str(e)}")

        return ScreenshotResponse(
            screenshots=screenshots,
            video_id=video_id,
            video_title=title,
            video_duration=duration,
            video_cached=video_cached,
            total_extracted=len(screenshots),
            failed_timestamps=failed_timestamps
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screenshot extraction failed: {str(e)}")
