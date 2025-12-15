"""
Audio extraction router.

This module provides endpoints for extracting audio from video URLs or local files.
Extracted audio files are stored in cache and automatically cleaned up based on CACHE_TTL_HOURS.
"""

import os
import uuid
import hashlib
import subprocess
import yt_dlp
from fastapi import APIRouter, Query, Depends, HTTPException

from app.dependencies import verify_api_key
from app.config import CACHE_DIR, CACHE_TTL_HOURS, YTDLP_EXTRACTOR_ARGS, YTDLP_BINARY
from app.services.ytdlp_service import run_ytdlp_binary, youtube_rate_limit
from app.services.cache_service import cleanup_cache
from app.utils.platform_utils import get_platform_from_url, get_video_id_from_url, is_youtube_url


router = APIRouter(tags=["Audio"])


@router.post("/extract-audio")
async def extract_audio(
    url: str = Query(None, description="Video URL to extract audio from"),
    local_file: str = Query(None, description="Path to local video file (alternative to url)"),
    output_format: str = Query("mp3", description="Audio format: mp3, m4a, wav, etc."),
    quality: str = Query("192", description="Audio quality/bitrate (e.g., '192', '320')"),
    cookies_file: str = Query(None, description="Optional cookies file for authentication"),
    _: bool = Depends(verify_api_key)
):
    """
    Extract audio from video (URL or local file).

    Returns the path to the extracted audio file on the server.
    Audio files are stored in cache and automatically cleaned up based on CACHE_TTL_HOURS.

    Use cases:
    - Extract audio from URL: provide 'url' parameter
    - Extract audio from downloaded video: provide 'local_file' parameter

    Next step: Use returned audio_file path with POST /transcribe
    """
    try:
        # Validate input
        if not url and not local_file:
            raise HTTPException(
                status_code=400,
                detail="Either 'url' or 'local_file' parameter must be provided"
            )

        if url and local_file:
            raise HTTPException(
                status_code=400,
                detail="Provide either 'url' OR 'local_file', not both"
            )

        # Run cleanup
        cleanup_cache()

        # Generate unique ID for audio file
        audio_uid = uuid.uuid4().hex[:8]
        audio_path = os.path.join(CACHE_DIR, "audio", f"{audio_uid}.{output_format}")

        # Get source info
        if local_file:
            # Validate local file exists
            if not os.path.exists(local_file):
                raise HTTPException(
                    status_code=404,
                    detail=f"Local file not found: {local_file}"
                )

            # For local files, use FFmpeg directly
            source_type = "local_file"
            title = os.path.basename(local_file)

            try:
                # Use FFmpeg to extract audio from local file
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-i', os.path.abspath(local_file),
                    '-vn',  # No video
                    '-acodec', 'libmp3lame' if output_format == 'mp3' else output_format,
                    '-b:a', f'{quality}k',
                    '-y',  # Overwrite output file
                    audio_path
                ]

                result = subprocess.run(
                    ffmpeg_cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if result.returncode != 0:
                    raise Exception(f"FFmpeg error: {result.stderr}")

            except subprocess.TimeoutExpired:
                raise HTTPException(
                    status_code=500,
                    detail="Audio extraction timed out (>5 minutes)"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to extract audio from local file: {str(e)}"
                )
        else:
            # For URLs, use yt-dlp
            source = url
            source_type = "url"
            use_binary = is_youtube_url(url) and os.path.exists(YTDLP_BINARY)

            # Apply rate limiting for YouTube
            if is_youtube_url(url):
                await youtube_rate_limit()

            # Get metadata
            try:
                if use_binary:
                    stdout, stderr, code = run_ytdlp_binary([
                        '--skip-download', '--print', '%(title)s',
                        url
                    ])
                    title = stdout.strip() if code == 0 else "Unknown"
                else:
                    meta_opts = {'quiet': True, 'skip_download': True}
                    if cookies_file and os.path.exists(cookies_file):
                        meta_opts['cookiefile'] = cookies_file
                    with yt_dlp.YoutubeDL(meta_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        title = info.get("title", "Unknown")
            except Exception:
                title = "Unknown"

            # Extract audio using yt-dlp
            try:
                if use_binary:
                    # Use standalone binary for YouTube
                    stdout, stderr, code = run_ytdlp_binary([
                        '-f', 'bestaudio/best',
                        '-x', '--audio-format', output_format,
                        '--audio-quality', quality,
                        '-o', audio_path.replace(f'.{output_format}', '.%(ext)s'),
                        url
                    ], timeout=600)
                    if code != 0:
                        raise Exception(stderr)
                else:
                    # Use Python library for non-YouTube
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': output_format,
                            'preferredquality': quality,
                        }],
                        'outtmpl': audio_path.replace(f'.{output_format}', '.%(ext)s'),
                        'quiet': True,
                    }
                    if cookies_file and os.path.exists(cookies_file):
                        ydl_opts['cookiefile'] = cookies_file
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([source])
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to extract audio: {str(e)}"
                )

        # Find actual audio file
        if local_file:
            # For local files, FFmpeg creates file directly at audio_path
            actual_audio_path = audio_path
        else:
            # For URLs, yt-dlp may change extension, so search for it
            actual_audio_path = None
            audio_cache_dir = os.path.join(CACHE_DIR, "audio")
            for f in os.listdir(audio_cache_dir):
                if f.startswith(audio_uid):
                    actual_audio_path = os.path.join(audio_cache_dir, f)
                    break

        if not actual_audio_path or not os.path.exists(actual_audio_path):
            raise HTTPException(
                status_code=500,
                detail="Audio extraction completed but file not found"
            )

        # Get file info
        file_size = os.path.getsize(actual_audio_path)

        # Extract metadata for unified response
        video_id = None
        video_url = None
        video_duration = None
        platform = None

        if url:
            # For URLs, get metadata from yt-dlp
            video_url = url
            platform = get_platform_from_url(url)
            try:
                meta_opts = {'quiet': True, 'skip_download': True, 'extractor_args': YTDLP_EXTRACTOR_ARGS}
                if cookies_file and os.path.exists(cookies_file):
                    meta_opts['cookiefile'] = cookies_file

                with yt_dlp.YoutubeDL(meta_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    video_id = info.get("id")
                    video_duration = info.get("duration")
            except Exception:
                # If metadata extraction fails, use hash fallback
                video_id = get_video_id_from_url(url)
        else:
            # For local files, generate video_id from filename
            video_id = hashlib.md5(os.path.basename(local_file).encode()).hexdigest()[:12]
            platform = "local"

        return {
            "audio_file": actual_audio_path,
            "format": output_format,
            "size": file_size,
            "title": title,
            "source_type": source_type,
            "message": "Audio extracted successfully. Use this audio_file path with POST /transcribe",
            "expires_in": f"{CACHE_TTL_HOURS} hours (automatic cleanup)",
            # Metadata for transcription
            "video_id": video_id,
            "url": video_url,
            "duration": video_duration,
            "platform": platform
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during audio extraction: {str(e)}"
        )
