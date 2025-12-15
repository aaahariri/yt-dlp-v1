"""
Transcription service for AI and subtitle-based transcriptions.

This module handles all transcription logic including:
- WhisperX local transcription
- OpenAI Whisper API transcription
- Unified response formatting for both subtitle and AI sources
"""

import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from fastapi import HTTPException

from app.config import (
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_GPU_INFO,
    CACHE_DIR,
    MAX_CONCURRENT_TRANSCRIPTIONS,
    CACHE_TTL_HOURS
)


def cleanup_cache() -> dict:
    """
    Delete all cached files older than TTL.
    Returns summary of deleted files.
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


def create_unified_transcription_response(
    title: str,
    language: str,
    segments: List[Dict[str, Any]],
    source: str,
    video_id: Optional[str] = None,
    url: Optional[str] = None,
    duration: Optional[int] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    source_format: Optional[str] = None,
    transcription_time: Optional[float] = None,
    platform: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create unified transcription response structure.

    Args:
        title: Video/audio title
        language: Language code (e.g., 'en', 'es')
        segments: List of segments with start (float), end (float), text (str)
        source: "subtitle" or "ai"
        video_id: Platform video ID or filename hash
        url: Original video URL (None for local files)
        duration: Video duration in seconds
        provider: Service provider (youtube, local, openai, etc.)
        model: AI model name (if source="ai")
        source_format: Original format (srt, vtt, etc. if source="subtitle")
        transcription_time: Processing time in seconds (if source="ai")
        platform: Platform name (youtube, tiktok, etc.)

    Returns:
        Unified transcription response dict
    """
    # Calculate full_text and counts
    full_text = ' '.join([s['text'].strip() for s in segments])
    word_count = len(full_text.split())
    segment_count = len(segments)

    # Build metadata object
    metadata = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "platform": platform
    }
    if transcription_time is not None:
        metadata["transcription_time"] = round(transcription_time, 2)

    # Build unified response
    response = {
        "video_id": video_id,
        "url": url,
        "title": title,
        "duration": duration,
        "language": language,
        "source": source,
        "provider": provider,
        "model": model,
        "source_format": source_format,
        "segments": segments,
        "full_text": full_text,
        "word_count": word_count,
        "segment_count": segment_count,
        "metadata": metadata
    }

    return response


async def _transcribe_audio_internal(
    audio_file: str,
    language: str,
    model_size: str,
    provider: str,
    output_format: str,
    video_id: Optional[str] = None,
    url: Optional[str] = None,
    duration: Optional[int] = None,
    platform: Optional[str] = None
):
    """Internal transcription logic (separated for semaphore control)."""
    try:
        # Run cleanup at start of transcription
        cleanup_cache()

        # Validate audio file exists
        if not os.path.exists(audio_file):
            raise HTTPException(
                status_code=404,
                detail=f"Audio file not found: {audio_file}. Did you run /extract-audio first?"
            )

        # Validate provider
        valid_providers = ["local", "openai"]
        if provider not in valid_providers:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider '{provider}'. Must be one of: {', '.join(valid_providers)}"
            )

        # Get basic file info
        title = os.path.basename(audio_file)

        # Transcribe based on provider
        transcribe_start = time.time()
        segments = []
        detected_language = language or 'unknown'

        if provider == "local":
            # Local whisperX transcription
            try:
                import whisperx
                import torch
            except ImportError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Local provider error: whisperX not installed - {str(e)}. Run: pip install whisperx OR use provider=openai"
                )

            # Use global device configuration detected at server startup
            device = WHISPER_DEVICE
            compute_type = WHISPER_COMPUTE_TYPE

            # Load model with automatic fallback to CPU if GPU fails
            model_load_error = None
            try:
                model = whisperx.load_model(
                    model_size,
                    device,
                    compute_type=compute_type,
                    language=language
                )
            except Exception as e:
                model_load_error = str(e)
                # If GPU (CUDA or MPS) failed, try CPU fallback
                if device in ["cuda", "mps"]:
                    try:
                        device = "cpu"
                        compute_type = "int8"
                        model = whisperx.load_model(
                            model_size,
                            device,
                            compute_type=compute_type,
                            language=language
                        )
                        # Successfully loaded on CPU after GPU failure
                        print(f"WARNING: {WHISPER_DEVICE.upper()} failed ({model_load_error}), fell back to CPU")
                    except Exception as cpu_error:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Local provider error: Failed to load model '{model_size}' on {WHISPER_DEVICE.upper()} ({model_load_error}) and CPU ({str(cpu_error)})"
                        )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Local provider error: Failed to load model '{model_size}' on {device.upper()} - {str(e)}"
                    )

            # Load and transcribe audio
            try:
                audio = whisperx.load_audio(audio_file)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Local provider error: Failed to load audio - {str(e)}. Audio format may not be supported."
                )

            try:
                result = model.transcribe(audio, batch_size=16)
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    raise HTTPException(
                        status_code=500,
                        detail=f"Local provider error: Out of memory. Try smaller model (tiny/small) or use provider=openai"
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Local provider error: Transcription failed - {str(e)}"
                    )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Local provider error: {str(e)}"
                )

            if not result or 'segments' not in result:
                raise HTTPException(
                    status_code=500,
                    detail="Local provider error: Transcription returned no segments - audio may be silent or corrupted"
                )

            for segment in result.get('segments', []):
                segments.append({
                    'start': segment['start'],
                    'end': segment['end'],
                    'text': segment['text']
                })
            detected_language = result.get('language', language or 'unknown')

        elif provider == "openai":
            # OpenAI Whisper API
            openai_key = os.getenv("OPENAI_API_KEY")
            if not openai_key:
                raise HTTPException(
                    status_code=500,
                    detail="OpenAI provider error: OPENAI_API_KEY not configured in environment"
                )

            try:
                with open(audio_file, 'rb') as f:
                    response = requests.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {openai_key}"},
                        files={"file": f},
                        data={
                            "model": "whisper-1",
                            "response_format": "verbose_json",
                            "language": language if language else None
                        },
                        timeout=300
                    )
            except requests.exceptions.Timeout:
                raise HTTPException(
                    status_code=504,
                    detail="OpenAI provider error: Request timeout - API did not respond within 5 minutes"
                )
            except requests.exceptions.ConnectionError as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"OpenAI provider error: Connection failed - {str(e)}"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"OpenAI provider error: Request failed - {str(e)}"
                )

            if response.status_code != 200:
                try:
                    error_json = response.json()
                    error_message = error_json.get('error', {}).get('message', response.text)
                except:
                    error_message = response.text

                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"OpenAI API error (HTTP {response.status_code}): {error_message}"
                )

            try:
                result = response.json()
            except ValueError:
                raise HTTPException(
                    status_code=500,
                    detail="OpenAI provider error: Invalid JSON response"
                )

            if 'segments' not in result:
                raise HTTPException(
                    status_code=500,
                    detail="OpenAI provider error: Response missing segments - transcription incomplete"
                )

            for segment in result.get('segments', []):
                segments.append({
                    'start': segment['start'],
                    'end': segment['end'],
                    'text': segment['text']
                })
            detected_language = result.get('language', language or 'unknown')

        transcribe_duration = time.time() - transcribe_start

        # Format output
        if output_format == "json":
            # Use unified response structure
            return create_unified_transcription_response(
                title=title,
                language=detected_language,
                segments=segments,
                source="ai",
                video_id=video_id,
                url=url,
                duration=duration,
                provider=provider,
                model=model_size if provider == "local" else "whisper-1",
                source_format=None,
                transcription_time=transcribe_duration,
                platform=platform
            )

        elif output_format == "srt":
            # Convert to SRT format
            srt_lines = []
            for idx, segment in enumerate(segments, 1):
                start = segment['start']
                end = segment['end']
                text = segment['text'].strip()

                # Convert to SRT timestamp format
                start_h = int(start // 3600)
                start_m = int((start % 3600) // 60)
                start_s = int(start % 60)
                start_ms = int((start % 1) * 1000)

                end_h = int(end // 3600)
                end_m = int((end % 3600) // 60)
                end_s = int(end % 60)
                end_ms = int((end % 1) * 1000)

                srt_lines.append(f"{idx}")
                srt_lines.append(f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> {end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}")
                srt_lines.append(text)
                srt_lines.append("")

            return {
                "title": title,
                "language": detected_language,
                "format": "srt",
                "content": '\n'.join(srt_lines),
                "provider": provider
            }

        elif output_format == "vtt":
            # Convert to VTT format
            vtt_lines = ["WEBVTT", ""]
            for segment in segments:
                start = segment['start']
                end = segment['end']
                text = segment['text'].strip()

                start_h = int(start // 3600)
                start_m = int((start % 3600) // 60)
                start_s = int(start % 60)
                start_ms = int((start % 1) * 1000)

                end_h = int(end // 3600)
                end_m = int((end % 3600) // 60)
                end_s = int(end % 60)
                end_ms = int((end % 1) * 1000)

                vtt_lines.append(f"{start_h:02d}:{start_m:02d}:{start_s:02d}.{start_ms:03d} --> {end_h:02d}:{end_m:02d}:{end_s:02d}.{end_ms:03d}")
                vtt_lines.append(text)
                vtt_lines.append("")

            return {
                "title": title,
                "language": detected_language,
                "format": "vtt",
                "content": '\n'.join(vtt_lines),
                "provider": provider
            }

        else:  # text
            full_text = ' '.join([s['text'].strip() for s in segments])
            return {
                "transcript": full_text,
                "word_count": len(full_text.split()),
                "title": title,
                "language": detected_language,
                "provider": provider
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during transcription: {str(e)}"
        )
