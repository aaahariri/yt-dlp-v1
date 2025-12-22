"""
Screenshot job service for processing screenshot extraction jobs.

This module handles screenshot extraction jobs for RunPod processing,
following the same pattern as the transcription job service.

Job Processing Flow:
1. Receive batch of screenshot jobs from RunPod payload
2. For each job:
   - Extract video metadata using yt-dlp
   - Download/cache video file
   - Extract frames at specified timestamps using FFmpeg
   - Upload screenshots to Supabase storage
   - Save metadata with job tracking info
3. Return results with success/failure status per job

Payload Format:
{
    "queue": "screenshot_extraction",
    "jobs": [{
        "video_url": "https://youtube.com/...",
        "timestamps": ["00:00:30,000", "00:01:00,000"],
        "quality": 2,
        "document_id": "optional-uuid"
    }]
}
"""

import os
import uuid
import hashlib
import yt_dlp
from datetime import datetime, timezone
from typing import Dict, Any, List

from app.config import CACHE_DIR, YTDLP_BINARY
from app.services.supabase_service import (
    upload_screenshot_to_supabase,
    save_screenshot_with_job_metadata
)
from app.services.screenshot_service import extract_screenshot
from app.services.ytdlp_service import run_ytdlp_binary, youtube_rate_limit
from app.services.cache_service import get_cached_video
from app.utils.platform_utils import is_youtube_url, get_platform_prefix
from app.utils.timestamp_utils import parse_timestamp_to_seconds, format_seconds_to_srt


# =============================================================================
# Helper Functions
# =============================================================================

def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _get_worker_name() -> str:
    """Get worker name from environment variable or default to 'runpod'."""
    return os.environ.get("WORKER_NAME", "runpod")


# =============================================================================
# Video Metadata Extraction
# =============================================================================

async def _extract_video_metadata(video_url: str) -> Dict[str, Any]:
    """
    Extract video metadata using yt-dlp.

    Args:
        video_url: URL of the video

    Returns:
        Dictionary with video_id, title, duration

    Raises:
        Exception: If metadata extraction fails
    """
    use_binary = is_youtube_url(video_url) and os.path.exists(YTDLP_BINARY)

    # Apply rate limiting for YouTube
    if is_youtube_url(video_url):
        await youtube_rate_limit()

    try:
        if use_binary:
            # Use standalone binary for YouTube
            stdout, stderr, code = run_ytdlp_binary([
                '--skip-download', '--print', '%(id)s\n%(title)s\n%(duration)s',
                video_url
            ])
            if code != 0:
                raise Exception(f"yt-dlp binary failed: {stderr}")

            lines = stdout.strip().split('\n')
            video_id = lines[0] if len(lines) > 0 else None
            title = lines[1] if len(lines) > 1 else 'Unknown'
            duration = int(lines[2]) if len(lines) > 2 and lines[2].isdigit() else None

            if not video_id:
                raise Exception("Failed to extract video_id from metadata")

            return {
                "video_id": video_id,
                "title": title,
                "duration": duration
            }
        else:
            # Use Python library for non-YouTube
            meta_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                video_id = info.get('id')
                title = info.get('title', 'Unknown')
                duration = info.get('duration')

                if not video_id:
                    raise Exception("Failed to extract video_id from metadata")

                return {
                    "video_id": video_id,
                    "title": title,
                    "duration": duration
                }
    except Exception as e:
        raise Exception(f"Metadata extraction failed: {str(e)}")


# =============================================================================
# Video Download/Caching
# =============================================================================

async def _download_or_get_cached_video(
    video_url: str,
    video_id: str
) -> str:
    """
    Download video or return cached path if available.

    Args:
        video_url: URL of the video
        video_id: Video ID for cache lookup

    Returns:
        Path to the video file (cached or newly downloaded)

    Raises:
        Exception: If video download fails
    """
    platform = get_platform_prefix(video_url)

    # Check cache first
    video_path = get_cached_video(video_id)
    if video_path:
        print(f"INFO: Using cached video: {video_path}")
        return video_path

    # Download video to cache
    print(f"INFO: Downloading video {video_id}...")
    video_filename = f"{platform}-{video_id}.mp4"
    video_path = os.path.join(CACHE_DIR, "videos", video_filename)

    use_binary = is_youtube_url(video_url) and os.path.exists(YTDLP_BINARY)

    # Apply rate limiting for YouTube
    if is_youtube_url(video_url):
        await youtube_rate_limit()

    try:
        if use_binary:
            # Use standalone binary for YouTube
            stdout, stderr, code = run_ytdlp_binary([
                '-f', 'best[height<=1080]',
                '-o', video_path.replace('.mp4', '.%(ext)s'),
                '--merge-output-format', 'mp4',
                video_url
            ], timeout=600)
            if code != 0:
                raise Exception(f"yt-dlp binary failed: {stderr}")
        else:
            # Use Python library for non-YouTube
            ydl_opts = {
                'format': 'best[height<=1080]',
                'outtmpl': video_path.replace('.mp4', '.%(ext)s'),
                'quiet': True,
                'merge_output_format': 'mp4',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

        # Find actual downloaded file (extension may vary)
        cache_videos_dir = os.path.join(CACHE_DIR, "videos")
        actual_video_path = None
        for f in os.listdir(cache_videos_dir):
            if f.startswith(f"{platform}-{video_id}"):
                actual_video_path = os.path.join(cache_videos_dir, f)
                break

        if not actual_video_path or not os.path.exists(actual_video_path):
            raise Exception("Video download completed but file not found")

        # Validate file size to catch corrupted/incomplete downloads
        file_size = os.path.getsize(actual_video_path)
        if file_size < 1024:  # Less than 1KB indicates corruption
            raise Exception(f"Downloaded video appears corrupted (size: {file_size} bytes)")

        print(f"INFO: Video downloaded: {actual_video_path} ({file_size} bytes)")
        return actual_video_path

    except Exception as e:
        raise Exception(f"Video download failed: {str(e)}")


# =============================================================================
# Single Job Processing
# =============================================================================

async def _process_single_screenshot_job(
    job: Dict[str, Any],
    worker: str
) -> Dict[str, Any]:
    """
    Process a single screenshot extraction job.

    Args:
        job: Job data containing video_url, timestamps, quality, document_id
        worker: Worker name (e.g., "runpod", "local")

    Returns:
        Result dict with status, job_id, total_extracted, failed_timestamps, error
    """
    # Generate unique job_id for this job
    job_id = str(uuid.uuid4())
    job_received_at = _now_iso()

    # Extract job parameters
    video_url = job.get("video_url")
    timestamps = job.get("timestamps", [])
    quality = job.get("quality", 2)
    document_id = job.get("document_id")

    # Validate quality parameter (FFmpeg JPEG quality range: 1-31, lower=better)
    if not isinstance(quality, int) or not (1 <= quality <= 31):
        quality = 2  # Default to safe value

    print(f"INFO: Processing screenshot job {job_id} for {video_url}")
    print(f"INFO: Timestamps: {len(timestamps)}, Quality: {quality}")

    # Validate job data
    if not video_url:
        return {
            "job_id": job_id,
            "status": "error",
            "video_url": video_url,
            "error": "Missing video_url",
            "total_extracted": 0,
            "failed_timestamps": []
        }

    if not timestamps or len(timestamps) == 0:
        return {
            "job_id": job_id,
            "status": "error",
            "video_url": video_url,
            "error": "No timestamps provided",
            "total_extracted": 0,
            "failed_timestamps": []
        }

    # Limit timestamps to prevent DoS attacks
    if len(timestamps) > 100:
        return {
            "job_id": job_id,
            "status": "error",
            "video_url": video_url,
            "error": f"Too many timestamps ({len(timestamps)}). Maximum 100 allowed.",
            "total_extracted": 0,
            "failed_timestamps": []
        }

    current_step = "initialization"

    try:
        # =================================================================
        # Step 1: Extract video metadata
        # =================================================================
        current_step = "extracting video metadata"
        print(f"INFO: [{job_id}] Extracting metadata...")

        metadata = await _extract_video_metadata(video_url)
        video_id = metadata["video_id"]
        video_title = metadata["title"]
        video_duration = metadata["duration"]

        print(f"INFO: [{job_id}] Video: {video_title} (ID: {video_id}, Duration: {video_duration}s)")

        # =================================================================
        # Step 2: Download or get cached video
        # =================================================================
        current_step = "downloading video"
        print(f"INFO: [{job_id}] Checking cache / downloading video...")

        video_path = await _download_or_get_cached_video(video_url, video_id)

        # =================================================================
        # Step 3: Extract screenshots at each timestamp
        # =================================================================
        current_step = "extracting screenshots"
        print(f"INFO: [{job_id}] Extracting {len(timestamps)} screenshot(s)...")

        screenshots_dir = os.path.join(CACHE_DIR, "screenshots")
        platform = get_platform_prefix(video_url)
        extracted_count = 0
        failed_timestamps = []

        # Common job metadata for all screenshots from this job
        job_metadata_base = {
            "job_id": job_id,
            "storage_status": "temp",  # Default - can be confirmed later by client
            "job_received_at": job_received_at,
            "worker": worker,
            "video_title": video_title,
            "video_duration": video_duration
        }

        for ts in timestamps:
            try:
                # Parse timestamp to seconds
                ts_seconds = parse_timestamp_to_seconds(ts)
                ts_ms = int(ts_seconds * 1000)

                # Output path: {video_id}-{timestamp_ms}.jpg
                output_filename = f"{video_id}-{ts_ms}.jpg"
                output_path = os.path.join(screenshots_dir, output_filename)

                # Extract frame using FFmpeg
                result = extract_screenshot(video_path, ts_seconds, output_path, quality)

                # Upload to Supabase storage
                storage_path = f"screenshots/{video_id}/{ts_ms}.jpg"
                upload_result = upload_screenshot_to_supabase(output_path, storage_path)
                public_url = upload_result["public_url"]

                # Prepare base metadata for this screenshot
                base_data = {
                    "type": "screenshot",
                    "storage_path": storage_path,
                    "storage_bucket": "public_media",
                    "content_type": "image/jpeg",
                    "size_bytes": result["size_bytes"],
                    "source_url": video_url,
                    "source_url_hash": hashlib.md5(video_url.encode()).hexdigest(),
                    "title": f"{video_title} - {format_seconds_to_srt(ts_seconds)}",
                    "document_id": document_id,
                    "metadata": {
                        "video_id": video_id,
                        "timestamp": ts_seconds,
                        "timestamp_formatted": format_seconds_to_srt(ts_seconds),
                        "width": result["width"],
                        "height": result["height"],
                        "platform": platform.lower()
                    }
                }

                # Add job completion timestamp to metadata for this screenshot
                screenshot_job_metadata = job_metadata_base.copy()
                screenshot_job_metadata["job_completed_at"] = _now_iso()

                # Save to database with job metadata
                try:
                    save_screenshot_with_job_metadata(base_data, screenshot_job_metadata)
                except Exception as db_err:
                    # Log but don't fail - screenshot was extracted and uploaded successfully
                    print(f"WARNING: [{job_id}] Failed to save metadata to DB: {str(db_err)}")

                extracted_count += 1
                print(f"INFO: [{job_id}] Extracted screenshot at {format_seconds_to_srt(ts_seconds)}")

            except Exception as e:
                error_msg = f"{ts}: {str(e)}"
                failed_timestamps.append(error_msg)
                print(f"WARNING: [{job_id}] Failed to extract screenshot at {ts}: {str(e)}")

        # =================================================================
        # Job Complete
        # =================================================================
        job_completed_at = _now_iso()

        print(f"INFO: [{job_id}] Complete - {extracted_count}/{len(timestamps)} screenshots extracted")

        return {
            "job_id": job_id,
            "status": "completed",
            "video_url": video_url,
            "total_extracted": extracted_count,
            "failed_timestamps": failed_timestamps
        }

    except Exception as e:
        # Build descriptive error message with step context
        base_error = str(e)
        error_msg = f"[Step: {current_step}] {base_error}"

        # Truncate if too long but preserve key info
        if len(error_msg) > 500:
            error_msg = error_msg[:480] + "... (truncated)"

        print(f"ERROR: [{job_id}] Job failed at '{current_step}': {base_error}")

        return {
            "job_id": job_id,
            "status": "error",
            "video_url": video_url,
            "error": error_msg,
            "total_extracted": 0,
            "failed_timestamps": []
        }


# =============================================================================
# Batch Processing (Main Entry Point)
# =============================================================================

async def process_screenshot_job_batch(
    payload: Dict[str, Any],
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Process a batch of screenshot extraction jobs from RunPod payload.

    This is the main entry point called by handler.py for screenshot jobs.

    Args:
        payload: Full payload from RunPod with queue and jobs array
        max_retries: Maximum retry attempts (currently unused, for future retry logic)

    Returns:
        Dictionary with ok status, summary, and results array

    Example Payload:
        {
            "queue": "screenshot_extraction",
            "jobs": [
                {
                    "video_url": "https://youtube.com/watch?v=xyz",
                    "timestamps": ["00:00:30,000", "00:01:00,000"],
                    "quality": 2,
                    "document_id": "uuid-optional"
                }
            ]
        }

    Example Response:
        {
            "ok": True,
            "summary": {"total": 2, "completed": 1, "failed": 1},
            "results": [
                {
                    "job_id": "abc-123",
                    "status": "completed",
                    "video_url": "https://...",
                    "total_extracted": 2,
                    "failed_timestamps": []
                },
                {
                    "job_id": "def-456",
                    "status": "error",
                    "video_url": "https://...",
                    "error": "Video download failed: ...",
                    "total_extracted": 0,
                    "failed_timestamps": []
                }
            ]
        }
    """
    queue_name = payload.get("queue", "screenshot_extraction")
    jobs = payload.get("jobs", [])
    worker = _get_worker_name()

    print(f"INFO: Processing batch of {len(jobs)} screenshot job(s) from queue '{queue_name}'")
    print(f"INFO: Worker: {worker}")

    results = []

    # Process jobs sequentially to respect rate limiting and resource constraints
    for job in jobs:
        result = await _process_single_screenshot_job(job=job, worker=worker)
        results.append(result)

    # Count results by status
    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "error")

    print(f"INFO: Batch complete - completed:{completed} failed:{failed}")

    return {
        "ok": True,
        "summary": {
            "total": len(jobs),
            "completed": completed,
            "failed": failed
        },
        "results": results
    }
