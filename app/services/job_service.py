"""
Job service for processing transcription jobs from Supabase queue.

This module handles the core job processing logic for video/audio transcription
jobs that are pushed from Supabase Edge Functions via the /jobs endpoint.

Job Processing Flow:
1. Claim document (atomic pending -> processing update)
2. Try to extract platform subtitles (YouTube, Vimeo, etc.) - faster & free
3. If no subtitles: extract audio and transcribe with WhisperX/OpenAI
4. Save transcription to document_transcriptions
5. Mark document completed
6. Ack (delete) queue message

On failure:
- If read_ct < MAX_RETRIES: return to pending, don't ack (will retry after VT)
- If read_ct >= MAX_RETRIES: mark as error, archive message
"""

import os
import re
import json
import uuid
import asyncio
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import yt_dlp

from app.config import (
    CACHE_DIR,
    CACHE_TTL_HOURS,
    YTDLP_BINARY,
    YTDLP_EXTRACTOR_ARGS,
    get_settings
)
from app.services.supabase_service import get_supabase_client
from app.services.ytdlp_service import run_ytdlp_binary, youtube_rate_limit
from app.services.transcription_service import _transcribe_audio_internal
from app.utils.platform_utils import get_platform_from_url, is_youtube_url
from app.utils.timestamp_utils import convert_srt_timestamp_to_seconds
from app.routers.transcription import transcription_semaphore


# =============================================================================
# Helper Functions
# =============================================================================

def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


async def _retry_with_delay(
    func,
    max_attempts: int = 3,
    delay_seconds: float = 3.0,
    operation_name: str = "operation"
):
    """
    Retry a synchronous function with fixed delay between attempts.

    Args:
        func: Callable to execute (no arguments)
        max_attempts: Maximum number of attempts (default 3)
        delay_seconds: Delay between retries in seconds (default 3.0)
        operation_name: Name for logging purposes

    Returns:
        Result of the function call

    Raises:
        Last exception if all attempts fail
    """
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                print(f"WARNING: {operation_name} failed (attempt {attempt}/{max_attempts}): {str(e)}")
                print(f"INFO: Retrying in {delay_seconds}s...")
                await asyncio.sleep(delay_seconds)
            else:
                print(f"ERROR: {operation_name} failed after {max_attempts} attempts: {str(e)}")
    raise last_error


def _ack_delete(supabase, queue_name: str, msg_id: int) -> bool:
    """
    Delete message from queue (success acknowledgment).
    Returns True if successful.
    """
    try:
        supabase.rpc("pgmq_delete_one", {
            "queue_name": queue_name,
            "msg_id": msg_id
        }).execute()
        return True
    except Exception as e:
        print(f"WARNING: Failed to ack delete msg_id={msg_id}: {str(e)}")
        return False


def _ack_archive(supabase, queue_name: str, msg_id: int) -> bool:
    """
    Archive message (failed after max retries).
    Returns True if successful.
    """
    try:
        supabase.rpc("pgmq_archive_one", {
            "queue_name": queue_name,
            "msg_id": msg_id
        }).execute()
        return True
    except Exception as e:
        print(f"WARNING: Failed to ack archive msg_id={msg_id}: {str(e)}")
        return False


# =============================================================================
# Platform Subtitle Extraction (Try First - Faster & Free)
# =============================================================================

def _parse_subtitles_to_segments(
    subtitle_content: str,
    subtitle_format: str
) -> List[Dict[str, Any]]:
    """
    Parse subtitle content (json3, vtt, srt) into standardized segments.

    Returns:
        List of segments with segment_id, start, end, text (and optionally words)
    """
    segments = []

    if subtitle_format == 'json3':
        # Parse YouTube json3 format with word-level timing
        data = json.loads(subtitle_content)
        segment_id = 0

        for event in data.get('events', []):
            # Skip window/positioning events and append events
            if 'segs' not in event or event.get('aAppend'):
                continue

            segs = event.get('segs', [])
            # Skip newline-only segments
            if len(segs) == 1 and segs[0].get('utf8', '').strip() in ('', '\n'):
                continue

            segment_id += 1
            start_ms = event.get('tStartMs', 0)
            duration_ms = event.get('dDurationMs', 0)

            # Build words with timing
            words = []
            text_parts = []
            for seg in segs:
                word_text = seg.get('utf8', '').strip()
                if not word_text or word_text == '\n':
                    continue
                text_parts.append(word_text)
                offset_ms = seg.get('tOffsetMs', 0)
                words.append({
                    'word': word_text,
                    'start': round((start_ms + offset_ms) / 1000.0, 3),
                    'end': None  # Calculated below
                })

            # Calculate word end times
            for i, word in enumerate(words):
                if i + 1 < len(words):
                    word['end'] = words[i + 1]['start']
                else:
                    word['end'] = round((start_ms + duration_ms) / 1000.0, 3)

            if text_parts:
                segment = {
                    'segment_id': segment_id,
                    'start': round(start_ms / 1000.0, 3),
                    'end': round((start_ms + duration_ms) / 1000.0, 3),
                    'text': ' '.join(text_parts)
                }
                if words:
                    segment['words'] = words
                segments.append(segment)

    elif subtitle_format == 'vtt':
        # Parse VTT format
        segment_id = 0
        lines = subtitle_content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            if '-->' in line:
                time_match = re.match(r'(\d+:\d+:\d+\.\d+)\s+-->\s+(\d+:\d+:\d+\.\d+)', line)
                if time_match:
                    # Collect all text lines after timestamp until next timestamp or empty line
                    text_lines = []
                    j = i + 1
                    while j < len(lines):
                        text_line = lines[j].strip()
                        # Stop at empty line or next timestamp
                        if not text_line or '-->' in text_line:
                            break
                        text_lines.append(text_line)
                        j += 1

                    # Join all text lines and strip HTML tags
                    combined_text = ' '.join(text_lines)
                    cleaned_text = re.sub(r'<[^>]+>', '', combined_text).strip()

                    if cleaned_text:
                        segment_id += 1
                        segments.append({
                            "segment_id": segment_id,
                            "start": convert_srt_timestamp_to_seconds(time_match.group(1)),
                            "end": convert_srt_timestamp_to_seconds(time_match.group(2)),
                            "text": cleaned_text
                        })

                    # Move past the text lines we just processed
                    i = j
                    continue
            i += 1

    elif subtitle_format == 'srt':
        # Parse SRT format
        segment_id = 0
        srt_blocks = subtitle_content.strip().split('\n\n')
        for block in srt_blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                timestamp_line = lines[1]
                time_match = re.match(r'(\d+:\d+:\d+,\d+)\s+-->\s+(\d+:\d+:\d+,\d+)', timestamp_line)
                if time_match:
                    segment_id += 1
                    text = ' '.join(lines[2:]).strip()
                    text = re.sub(r'<[^>]+>', '', text)
                    if text:
                        segments.append({
                            "segment_id": segment_id,
                            "start": convert_srt_timestamp_to_seconds(time_match.group(1)),
                            "end": convert_srt_timestamp_to_seconds(time_match.group(2)),
                            "text": text
                        })

    return segments


async def _try_extract_platform_subtitles(
    url: str,
    lang: str = None,
    include_auto_captions: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Try to extract subtitles from the video platform (YouTube, Vimeo, etc.).

    This is faster and free compared to AI transcription. Prioritizes manual
    subtitles over auto-generated ones when available.

    Args:
        url: Video URL
        lang: Preferred language code (e.g., 'en', 'es'). Defaults to English.
        include_auto_captions: Whether to use auto-generated captions if no manual subs

    Returns:
        Dict with segments, language, source info if successful, None if no subtitles
    """
    target_lang = lang or 'en'

    # Apply rate limiting for YouTube
    if is_youtube_url(url):
        await youtube_rate_limit()

    try:
        # Configure yt-dlp for subtitle extraction only
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': include_auto_captions,
            'skip_download': True,
            'quiet': True,
            'subtitleslangs': [target_lang],
            'extractor_args': YTDLP_EXTRACTOR_ARGS,
        }

        # Retry yt-dlp extraction (3 attempts, 3s delay)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await _retry_with_delay(
                    func=lambda: ydl.extract_info(url, download=False),
                    max_attempts=3,
                    delay_seconds=3.0,
                    operation_name="yt-dlp subtitle extraction"
                )
        except Exception as e:
            print(f"WARNING: Platform subtitle extraction failed after retries: {str(e)}")
            return None

        # Get video metadata
        title = info.get("title", "Unknown")
        duration = info.get("duration", 0)
        video_id = info.get("id")
        platform = get_platform_from_url(url)

        # Extract subtitles - prioritize manual over auto-generated
        manual_subs = info.get('subtitles', {})
        auto_captions = info.get('automatic_captions', {})

        # Try to find subtitles in this order:
        # 1. Manual subtitles in target language
        # 2. Manual subtitles in English variants
        # 3. Auto-captions in target language (if enabled)
        # 4. Auto-captions in English variants (if enabled)

        available_subs = None
        actual_lang = target_lang
        is_auto_generated = False

        # Try manual subtitles first (higher quality)
        if manual_subs.get(target_lang):
            available_subs = manual_subs[target_lang]
            actual_lang = target_lang
        else:
            # Try English fallback for manual
            for fallback in ['en', 'en-US', 'en-GB']:
                if manual_subs.get(fallback):
                    available_subs = manual_subs[fallback]
                    actual_lang = fallback
                    break

        # If no manual subs found and auto-captions enabled, try auto
        if not available_subs and include_auto_captions:
            if auto_captions.get(target_lang):
                available_subs = auto_captions[target_lang]
                actual_lang = target_lang
                is_auto_generated = True
            else:
                for fallback in ['en', 'en-US', 'en-GB']:
                    if auto_captions.get(fallback):
                        available_subs = auto_captions[fallback]
                        actual_lang = fallback
                        is_auto_generated = True
                        break

        if not available_subs:
            print(f"INFO: No subtitles available for {url[:50]}...")
            return None

        # Get the best subtitle format (prefer json3 for word-level timing)
        subtitle_info = None
        for sub in available_subs:
            if sub.get('ext') == 'json3':
                subtitle_info = sub
                break
        if not subtitle_info:
            for sub in available_subs:
                if sub.get('ext') in ['vtt', 'srt']:
                    subtitle_info = sub
                    break
        if not subtitle_info:
            subtitle_info = available_subs[0]

        subtitle_url = subtitle_info.get('url')
        subtitle_format = subtitle_info.get('ext', 'unknown')

        # Download subtitle content with retry (3 attempts, 3s delay)
        try:
            response = await _retry_with_delay(
                func=lambda: requests.get(subtitle_url, timeout=30),
                max_attempts=3,
                delay_seconds=3.0,
                operation_name="subtitle content download"
            )
            response.raise_for_status()
            subtitle_content = response.text
        except Exception as e:
            print(f"WARNING: Failed to download subtitles after retries: {str(e)}")
            return None

        # Parse subtitles into segments
        segments = _parse_subtitles_to_segments(subtitle_content, subtitle_format)

        if not segments:
            print(f"WARNING: Subtitle parsing returned no segments")
            return None

        sub_type = "auto-generated" if is_auto_generated else "manual"
        print(f"INFO: Extracted {len(segments)} segments from {sub_type} {subtitle_format} subtitles ({actual_lang})")

        return {
            "segments": segments,
            "language": actual_lang,
            "title": title,
            "duration": duration,
            "video_id": video_id,
            "platform": platform,
            "source_format": subtitle_format,
            "is_auto_generated": is_auto_generated
        }

    except Exception as e:
        print(f"WARNING: Platform subtitle extraction failed: {str(e)}")
        return None


# =============================================================================
# Audio Extraction (Internal)
# =============================================================================

async def _extract_audio_from_url(url: str) -> Dict[str, Any]:
    """
    Extract audio from URL using yt-dlp.

    This is a simplified version that only handles URLs (not local files)
    for the job processing flow.

    Returns:
        Dict with audio_file path and metadata (video_id, url, duration, platform)
    """
    # Apply rate limiting for YouTube
    if is_youtube_url(url):
        await youtube_rate_limit()

    # Generate unique ID for audio file
    audio_uid = uuid.uuid4().hex[:8]
    output_format = "mp3"
    audio_path = os.path.join(CACHE_DIR, "audio", f"{audio_uid}.{output_format}")

    use_binary = is_youtube_url(url) and os.path.exists(YTDLP_BINARY)

    # Get metadata
    title = "Unknown"
    try:
        if use_binary:
            stdout, stderr, code = run_ytdlp_binary([
                '--skip-download', '--print', '%(title)s',
                url
            ])
            title = stdout.strip() if code == 0 else "Unknown"
        else:
            meta_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown")
    except Exception:
        pass

    # Extract audio using yt-dlp
    if use_binary:
        stdout, stderr, code = run_ytdlp_binary([
            '-f', 'bestaudio/best',
            '-x', '--audio-format', output_format,
            '--audio-quality', '192',
            '-o', audio_path.replace(f'.{output_format}', '.%(ext)s'),
            url
        ], timeout=600)
        if code != 0:
            raise Exception(f"yt-dlp failed: {stderr}")
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': output_format,
                'preferredquality': '192',
            }],
            'outtmpl': audio_path.replace(f'.{output_format}', '.%(ext)s'),
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    # Find actual audio file (yt-dlp may change extension)
    actual_audio_path = None
    audio_cache_dir = os.path.join(CACHE_DIR, "audio")
    for f in os.listdir(audio_cache_dir):
        if f.startswith(audio_uid):
            actual_audio_path = os.path.join(audio_cache_dir, f)
            break

    if not actual_audio_path or not os.path.exists(actual_audio_path):
        raise Exception("Audio extraction completed but file not found")

    # Get additional metadata
    video_id = None
    video_duration = None
    platform = get_platform_from_url(url)

    try:
        if use_binary:
            import json
            stdout, _, code = run_ytdlp_binary([
                '--skip-download', '-j', url
            ])
            if code == 0:
                info = json.loads(stdout)
                video_id = info.get("id")
                video_duration = info.get("duration")
        else:
            meta_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_id = info.get("id")
                video_duration = info.get("duration")
    except Exception:
        pass

    return {
        "audio_file": actual_audio_path,
        "format": output_format,
        "title": title,
        "video_id": video_id,
        "url": url,
        "duration": video_duration,
        "platform": platform
    }


# =============================================================================
# Job Processing
# =============================================================================

async def process_single_job(
    job: Dict[str, Any],
    queue_name: str,
    max_retries: int = 5,
    model_size: str = "medium",
    provider: str = "local"
) -> Dict[str, Any]:
    """
    Process a single transcription job.

    Args:
        job: Job data from queue with msg_id, read_ct, document_id
        queue_name: PGMQ queue name for ack operations
        max_retries: Maximum retry attempts before marking as error
        model_size: Whisper model size (tiny, small, medium, large-v2, etc.)
        provider: Transcription provider (local or openai)

    Returns:
        Result dict with status, msg_id, document_id, and any error info
    """
    msg_id = job.get("msg_id")
    read_ct = int(job.get("read_ct", 1))
    document_id = job.get("document_id")

    # Also check message.document_id if document_id is at top level
    if not document_id and isinstance(job.get("message"), dict):
        document_id = job["message"].get("document_id")

    print(f"INFO: Processing job msg_id={msg_id} document_id={document_id} read_ct={read_ct}")

    # Get Supabase client
    supabase = get_supabase_client()

    # Validate job data
    if not document_id:
        print(f"WARNING: Job {msg_id} missing document_id - archiving")
        _ack_archive(supabase, queue_name, msg_id)
        return {
            "msg_id": msg_id,
            "status": "archived",
            "reason": "missing document_id"
        }

    # Track which step failed for better error messages
    current_step = "initialization"

    try:
        # =================================================================
        # Step 1: Idempotency guard + claim document atomically
        # =================================================================
        current_step = "claiming document"

        claim_result = supabase.table("documents").update({
            "processing_status": "processing",
            "updated_at": _now_iso()
        }).eq("id", document_id).eq("processing_status", "pending").execute()

        if not claim_result.data or len(claim_result.data) == 0:
            # Document not pending - already processed or being processed
            print(f"INFO: Document {document_id} not pending - ack delete stale message")
            _ack_delete(supabase, queue_name, msg_id)
            return {
                "msg_id": msg_id,
                "status": "deleted",
                "reason": "not pending",
                "document_id": document_id
            }

        # =================================================================
        # Step 2: Fetch document details
        # =================================================================
        current_step = "fetching document details"

        doc_result = supabase.table("documents").select(
            "id, canonical_url, metadata, media_format, lang, title"
        ).eq("id", document_id).single().execute()

        if not doc_result.data:
            raise ValueError(f"Document {document_id} not found after claiming")

        doc = doc_result.data

        # =================================================================
        # Step 3: Validate document data
        # =================================================================
        current_step = "validating document data"

        # Get media URL (canonical_url or fallback to metadata)
        media_url = doc.get("canonical_url")
        if not media_url and doc.get("metadata"):
            media_url = doc["metadata"].get("media_url") or doc["metadata"].get("url")

        if not media_url:
            raise ValueError("No media URL found in document (canonical_url or metadata.media_url/url)")

        # Verify media format
        media_format = doc.get("media_format")
        if media_format not in ["video", "audio"]:
            raise ValueError(f"Invalid media_format '{media_format}' (expected 'video' or 'audio')")

        print(f"INFO: Document {document_id}: {media_format} from {media_url[:60]}...")

        # =================================================================
        # Step 4: Try platform subtitles first (faster & free)
        # =================================================================
        current_step = "extracting platform subtitles"

        subtitle_result = None
        transcription_source = None  # Will be "subtitle" or "ai"

        # Check if skip_subtitles flag is set (optional, defaults to False)
        skip_subtitles = job.get("skip_subtitles", False)

        # Only try subtitles for video format (audio-only won't have platform subs)
        # and if skip_subtitles flag is not set
        if media_format == "video" and not skip_subtitles:
            print(f"INFO: Trying to extract platform subtitles...")
            subtitle_result = await _try_extract_platform_subtitles(
                url=media_url,
                lang=doc.get("lang"),
                include_auto_captions=True
            )
        elif skip_subtitles:
            print(f"INFO: Skipping platform subtitles (skip_subtitles=True), using AI transcription")

        if subtitle_result:
            # Success! Use platform subtitles
            transcription_source = "subtitle"
            segments = subtitle_result["segments"]
            detected_language = subtitle_result["language"]
            video_duration = subtitle_result.get("duration")
            video_id = subtitle_result.get("video_id")
            platform = subtitle_result.get("platform")

            sub_type = "auto-generated" if subtitle_result.get("is_auto_generated") else "manual"
            print(f"INFO: Using {sub_type} platform subtitles ({len(segments)} segments)")

            # Build metadata for subtitle source
            settings = get_settings()
            segment_count = len(segments)
            word_count = sum(len(s.get('text', '').split()) for s in segments)

            metadata = {
                "source_format": subtitle_result.get("source_format"),
                "is_auto_generated": subtitle_result.get("is_auto_generated", False),
                "provider": settings.provider_name,
                "platform": platform,
                "duration": video_duration,
                "word_count": word_count,
                "segment_count": segment_count
            }

        else:
            # =================================================================
            # Step 5: Extract audio (fallback when no subtitles)
            # =================================================================
            current_step = f"extracting audio from {media_url[:60]}"

            print(f"INFO: No platform subtitles available, extracting audio...")
            try:
                audio_result = await _extract_audio_from_url(media_url)
                audio_file = audio_result["audio_file"]
                print(f"INFO: Audio extracted: {audio_file}")
            except Exception as audio_err:
                raise Exception(f"Audio extraction failed: {str(audio_err)}")

            # =================================================================
            # Step 6: Transcribe audio with WhisperX/OpenAI
            # =================================================================
            current_step = f"transcribing audio with {provider}/{model_size}"

            print(f"INFO: Transcribing with provider={provider} model={model_size}...")
            try:
                async with transcription_semaphore:
                    transcription = await _transcribe_audio_internal(
                        audio_file=audio_file,
                        language=doc.get("lang"),
                        model_size=model_size,
                        provider=provider,
                        output_format="json",
                        video_id=audio_result.get("video_id"),
                        url=media_url,
                        duration=audio_result.get("duration"),
                        platform=audio_result.get("platform")
                    )
            except Exception as transcribe_err:
                raise Exception(f"Transcription failed: {str(transcribe_err)}")

            transcription_source = "ai"
            segments = transcription.get("segments", [])
            detected_language = transcription.get("language", "unknown")
            video_duration = audio_result.get("duration")

            # Ensure all segments have segment_id
            for idx, seg in enumerate(segments, start=1):
                if 'segment_id' not in seg:
                    seg['segment_id'] = idx

            print(f"INFO: AI transcription complete: {len(segments)} segments")

            # Build metadata for AI transcription
            settings = get_settings()
            trans_metadata = transcription.get("metadata", {})
            segment_count = len(segments)
            word_count = sum(len(s.get('text', '').split()) for s in segments)

            metadata = {
                "model": f"WhisperX-{model_size}" if provider == "local" else "whisper-1",
                "provider": settings.provider_name,
                "duration": video_duration,
                "processing_time": trans_metadata.get("transcription_time"),
                "word_count": word_count,
                "segment_count": segment_count
            }

        # =================================================================
        # Step 7: Upsert to document_transcriptions
        # =================================================================
        current_step = "saving transcription to database"

        print(f"INFO: Saving {transcription_source} transcription to document_transcriptions...")

        # Calculate stats (may already be set, but ensure consistency)
        segment_count = len(segments)
        word_count = sum(len(s.get('text', '').split()) for s in segments)

        upsert_data = {
            "document_id": document_id,
            "segments": segments,
            "language": detected_language,
            "source": transcription_source,  # "subtitle" or "ai"
            "confidence_score": None,
            "metadata": metadata,
            "updated_at": _now_iso()
        }

        try:
            supabase.table("document_transcriptions").upsert(
                upsert_data,
                on_conflict="document_id"
            ).execute()
        except Exception as db_err:
            raise Exception(f"Database save failed: {str(db_err)}")

        print(f"INFO: Transcription saved ({transcription_source}): {word_count} words, {segment_count} segments")

        # =================================================================
        # Step 8: Mark document completed
        # =================================================================
        current_step = "marking document as completed"

        try:
            supabase.table("documents").update({
                "processing_status": "completed",
                "processed_at": _now_iso(),
                "processing_error": None,
                "updated_at": _now_iso()
            }).eq("id", document_id).execute()
        except Exception as update_err:
            raise Exception(f"Failed to mark document completed: {str(update_err)}")

        # =================================================================
        # Step 9: Ack delete message
        # =================================================================
        _ack_delete(supabase, queue_name, msg_id)

        print(f"INFO: Job completed for document {document_id} (source: {transcription_source})")

        return {
            "msg_id": msg_id,
            "status": "completed",
            "document_id": document_id,
            "source": transcription_source,  # "subtitle" or "ai"
            "word_count": word_count,
            "segment_count": segment_count
        }

    except Exception as e:
        # Build descriptive error message with step context
        base_error = str(e)
        error_msg = f"[Step: {current_step}] {base_error}"

        # Truncate if too long but preserve key info
        if len(error_msg) > 500:
            error_msg = error_msg[:480] + "... (truncated)"

        print(f"ERROR: Job processing failed at '{current_step}': {base_error}")

        # Handle retry logic with comprehensive error tracking
        if read_ct >= max_retries:
            # Max retries reached - mark as permanent error
            print(f"ERROR: Max retries reached ({read_ct}/{max_retries}) - marking as error")

            final_error_msg = f"Failed after {read_ct} attempts. Last error: {error_msg}"

            try:
                supabase.table("documents").update({
                    "processing_status": "error",
                    "processing_error": final_error_msg,
                    "updated_at": _now_iso()
                }).eq("id", document_id).execute()
                print(f"INFO: Document {document_id} marked as error")
            except Exception as update_err:
                print(f"WARNING: Failed to update document error status: {update_err}")

            _ack_archive(supabase, queue_name, msg_id)

            return {
                "msg_id": msg_id,
                "status": "archived",
                "error": error_msg,
                "read_ct": read_ct,
                "document_id": document_id
            }
        else:
            # Will retry - mark as pending with retry info
            print(f"WARNING: Retry {read_ct}/{max_retries} - returning to pending")

            retry_error_msg = f"Retry {read_ct}/{max_retries}: {error_msg}"

            try:
                supabase.table("documents").update({
                    "processing_status": "pending",
                    "processing_error": retry_error_msg,
                    "updated_at": _now_iso()
                }).eq("id", document_id).execute()
                print(f"INFO: Document {document_id} returned to pending with retry info")
            except Exception as update_err:
                print(f"WARNING: Failed to update document retry status: {update_err}")

            # Don't ack - message will reappear after VT
            return {
                "msg_id": msg_id,
                "status": "retry",
                "error": error_msg,
                "read_ct": read_ct,
                "document_id": document_id
            }


async def process_job_batch(
    payload: Dict[str, Any],
    max_retries: int = 5,
    model_size: str = "medium",
    provider: str = "local"
) -> Dict[str, Any]:
    """
    Process a batch of transcription jobs from the queue payload.

    Args:
        payload: Full payload from Supabase Edge Function with queue, vt_seconds, jobs
        max_retries: Maximum retry attempts per job
        model_size: Whisper model size
        provider: Transcription provider

    Returns:
        Dict with ok status and results for each job
    """
    queue_name = payload.get("queue", "video_audio_transcription")
    jobs = payload.get("jobs", [])

    print(f"INFO: Processing batch of {len(jobs)} job(s) from queue '{queue_name}'")

    results = []

    # Process jobs sequentially to respect rate limiting and resource constraints
    # Note: The semaphore inside process_single_job handles transcription concurrency
    for job in jobs:
        result = await process_single_job(
            job=job,
            queue_name=queue_name,
            max_retries=max_retries,
            model_size=model_size,
            provider=provider
        )
        results.append(result)

    # Count results by status
    completed = sum(1 for r in results if r.get("status") == "completed")
    retried = sum(1 for r in results if r.get("status") == "retry")
    archived = sum(1 for r in results if r.get("status") == "archived")
    deleted = sum(1 for r in results if r.get("status") == "deleted")

    print(f"INFO: Batch complete - completed:{completed} retry:{retried} archived:{archived} deleted:{deleted}")

    return {
        "ok": True,
        "summary": {
            "total": len(jobs),
            "completed": completed,
            "retry": retried,
            "archived": archived,
            "deleted": deleted
        },
        "results": results
    }
