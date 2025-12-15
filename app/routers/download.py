"""
Download router module.

Provides endpoints for downloading videos from various platforms:
- GET /download: Single video download with streaming response
- POST /batch-download: Batch download multiple videos with automatic rate limiting
"""

import os
import time
import uuid
import random
from typing import List

import yt_dlp
from fastapi import APIRouter, Query, HTTPException, Depends, Body
from fastapi.responses import StreamingResponse

from app.dependencies import verify_api_key
from app.config import DOWNLOADS_DIR, YTDLP_EXTRACTOR_ARGS
from app.models import BatchDownloadRequest, BatchDownloadResponse, VideoDownloadResult
from app.utils.filename_utils import (
    create_formatted_filename,
    encode_content_disposition_filename,
    get_platform_prefix,
)


router = APIRouter(tags=["Download"])


@router.get("/download")
async def download_video(
    url: str = Query(...),
    format: str = Query("best"),
    keep: bool = Query(False),
    custom_title: str = Query(None, description="Optional custom title for the downloaded file"),
    cookies_file: str = Query(None, description="Optional path to cookies file for sites requiring authentication"),
    _: bool = Depends(verify_api_key)
):
    """
    Download a single video and stream it to the client.

    Supports 1000+ platforms through yt-dlp including YouTube, TikTok, Instagram,
    Facebook, Twitter, and more.

    Args:
        url: Video URL to download
        format: Video quality format (default: "best")
        keep: Save video to server storage (default: False)
        custom_title: Optional custom title for the downloaded file
        cookies_file: Optional path to cookies file for authenticated downloads

    Returns:
        StreamingResponse with video file

    Raises:
        HTTPException: If download fails or file not found
    """
    try:
        # Prepare yt-dlp options for metadata extraction
        meta_opts = {'quiet': True, 'skip_download': True, 'extractor_args': YTDLP_EXTRACTOR_ARGS}

        # Add cookies file if provided (for sites like Patreon)
        if cookies_file and os.path.exists(cookies_file):
            meta_opts['cookiefile'] = cookies_file

        # Extract metadata
        with yt_dlp.YoutubeDL(meta_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "video")
            extension = "mp4"  # fallback extension

            # Create formatted filename with platform prefix
            filename = create_formatted_filename(url, title, extension, custom_title)

        # Create output template based on keep parameter
        if keep:
            # Save to downloads directory with formatted filename
            # Extract just the name without extension for template
            base_filename = filename.rsplit('.', 1)[0]
            saved_filename = f"{base_filename}.%(ext)s"
            output_template = os.path.join(DOWNLOADS_DIR, saved_filename)
        else:
            # Use temporary file
            uid = uuid.uuid4().hex[:8]
            output_template = f"/tmp/{uid}.%(ext)s"

        ydl_opts = {
            'format': format,
            'outtmpl': output_template,
            'quiet': True,
            'merge_output_format': 'mp4',
            'extractor_args': YTDLP_EXTRACTOR_ARGS,
        }

        # Add cookies file if provided (for sites like Patreon)
        if cookies_file and os.path.exists(cookies_file):
            ydl_opts['cookiefile'] = cookies_file

        # Download the video using yt-dlp Python API
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.download([url])

        # Find actual downloaded file
        actual_file_path = None
        if keep:
            # Look in downloads directory for the formatted filename
            base_filename = filename.rsplit('.', 1)[0]
            for f in os.listdir(DOWNLOADS_DIR):
                if f.startswith(base_filename):
                    actual_file_path = os.path.join(DOWNLOADS_DIR, f)
                    break
        else:
            # Look in temp directory
            for f in os.listdir("/tmp"):
                if f.startswith(uid):
                    actual_file_path = os.path.join("/tmp", f)
                    break

        if not actual_file_path or not os.path.exists(actual_file_path):
            raise HTTPException(status_code=500, detail="Download failed or file not found.")

        # Stream file
        def iterfile():
            with open(actual_file_path, "rb") as f:
                yield from f
            if not keep:
                os.unlink(actual_file_path)  # only clean up temp files

        # Prepare response headers
        response_headers = {"Content-Disposition": encode_content_disposition_filename(filename)}
        if keep:
            saved_path = os.path.relpath(actual_file_path, start=".")
            response_headers["X-Server-Path"] = saved_path

        return StreamingResponse(
            iterfile(),
            media_type="application/octet-stream",
            headers=response_headers
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during download: {str(e)}")


@router.post("/batch-download")
async def batch_download_videos(
    request: BatchDownloadRequest = Body(...),
    _: bool = Depends(verify_api_key)
) -> BatchDownloadResponse:
    """
    Download multiple videos from various platforms with automatic rate limiting.

    Supports YouTube, TikTok, Instagram, Facebook, Twitter, and 1000+ platforms.
    Independent error handling - one failure doesn't stop the batch.

    Args:
        request: BatchDownloadRequest with URLs, format, keep, delays, and cookies_file

    Returns:
        BatchDownloadResponse with download results and statistics

    Features:
        - Automatic rate limiting with random delays between downloads
        - Skip already downloaded files (when keep=True)
        - Independent error handling per video
        - Detailed per-video results with platform, title, file size
    """
    start_time = time.time()
    results: List[VideoDownloadResult] = []
    successful = 0
    failed = 0
    skipped = 0
    total_size = 0

    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    for idx, url in enumerate(request.urls, 1):
        result = VideoDownloadResult(url=url, success=False)

        try:
            platform_prefix = get_platform_prefix(url)
            result.platform = platform_prefix

            # Extract metadata without downloading
            meta_opts = {'quiet': True, 'skip_download': True, 'extractor_args': YTDLP_EXTRACTOR_ARGS}
            if request.cookies_file and os.path.exists(request.cookies_file):
                meta_opts['cookiefile'] = request.cookies_file

            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "video")
                result.title = title
                extension = "mp4"
                filename = create_formatted_filename(url, title, extension, None)
                result.filename = filename

            # Set up output path
            if request.keep:
                base_filename = filename.rsplit('.', 1)[0]
                saved_filename = f"{base_filename}.%(ext)s"
                output_template = os.path.join(DOWNLOADS_DIR, saved_filename)
                expected_file = os.path.join(DOWNLOADS_DIR, filename)

                # Skip if already exists
                if os.path.exists(expected_file):
                    file_stat = os.stat(expected_file)
                    result.success = True
                    result.file_path = os.path.relpath(expected_file, start=".")
                    result.file_size = file_stat.st_size
                    total_size += file_stat.st_size
                    skipped += 1
                    results.append(result)
                    continue
            else:
                uid = uuid.uuid4().hex[:8]
                output_template = f"/tmp/{uid}.%(ext)s"

            # Download video
            ydl_opts = {
                'format': request.format,
                'outtmpl': output_template,
                'quiet': True,
                'merge_output_format': 'mp4',
                'extractor_args': YTDLP_EXTRACTOR_ARGS,
            }

            if request.cookies_file and os.path.exists(request.cookies_file):
                ydl_opts['cookiefile'] = request.cookies_file

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Verify file exists
            actual_file_path = None
            if request.keep:
                for f in os.listdir(DOWNLOADS_DIR):
                    if f.startswith(base_filename):
                        actual_file_path = os.path.join(DOWNLOADS_DIR, f)
                        break
            else:
                for f in os.listdir("/tmp"):
                    if f.startswith(uid):
                        actual_file_path = os.path.join("/tmp", f)
                        break

            if actual_file_path and os.path.exists(actual_file_path):
                file_stat = os.stat(actual_file_path)
                result.success = True
                result.file_path = os.path.relpath(actual_file_path, start=".") if request.keep else actual_file_path
                result.file_size = file_stat.st_size
                total_size += file_stat.st_size
                successful += 1
            else:
                result.error = "Download completed but file not found"
                failed += 1

        except Exception as e:
            result.error = str(e)
            failed += 1

        results.append(result)

        # Add delay between downloads (prevents rate limiting)
        if idx < len(request.urls):
            delay = random.randint(request.min_delay, request.max_delay)
            time.sleep(delay)

    duration = time.time() - start_time

    return BatchDownloadResponse(
        total=len(request.urls),
        successful=successful,
        failed=failed,
        skipped=skipped,
        downloads=results,
        total_size=total_size,
        duration_seconds=round(duration, 2)
    )
