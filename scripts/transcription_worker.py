#!/usr/bin/env python3
# =============================================================================
# DEPRECATED - NOT IN USE
# =============================================================================
# This polling worker has been replaced by endpoint-based job processing.
# Jobs are now pushed to POST /jobs/video-audio-transcription by Supabase
# Edge Functions instead of being polled by this worker.
#
# See: app/routers/jobs.py and app/services/job_service.py
# Config: TRANSCRIPTION_WORKER_ENABLED=false (default)
# =============================================================================
"""
Video/Audio Transcription Queue Worker

Automatically processes pending transcription jobs from Supabase PGMQ queue.
Integrates with FastAPI application lifecycle.

Features:
- Polls PGMQ queue for pending transcription jobs
- Parallel job processing with semaphore control
- Automatic retry with visibility timeout
- Graceful startup and shutdown
- Comprehensive logging with timestamps
- Status endpoint for monitoring

Job Processing Flow:
1. Dequeue batch from video_audio_transcription queue
2. For each job (parallel, respecting MAX_CONCURRENT_TRANSCRIPTIONS):
   - Validate document has processing_status='pending' and media_format in ('video', 'audio')
   - Update document processing_status to 'processing'
   - Extract audio from canonical_url
   - Transcribe audio with whisperX/OpenAI
   - Upsert transcription to document_transcriptions
   - Update document to 'completed' with processed_at timestamp
   - Delete queue message (ack)
3. On failure: retry up to MAX_RETRIES, then archive and mark as 'error'

Usage:
    from scripts.transcription_worker import start_worker, stop_worker, get_worker_status

    # Start on app startup (non-blocking)
    await start_worker()

    # Stop on app shutdown
    await stop_worker()

    # Get status for monitoring
    status = get_worker_status()
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("transcription_worker")

# Add parent directory to path for imports
scripts_dir = Path(__file__).parent
project_root = scripts_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# =============================================================================
# Configuration
# =============================================================================

def get_worker_config() -> Dict[str, Any]:
    """Load worker configuration from environment variables."""
    return {
        'enabled': os.getenv('TRANSCRIPTION_WORKER_ENABLED', 'true').lower() in ('true', '1', 'yes'),
        'poll_interval': int(os.getenv('WORKER_POLL_INTERVAL', '5')),  # seconds
        'batch_size': int(os.getenv('WORKER_BATCH_SIZE', '10')),  # jobs per poll
        'vt_seconds': int(os.getenv('WORKER_VT_SECONDS', '1800')),  # 30 min visibility timeout
        'max_retries': int(os.getenv('WORKER_MAX_RETRIES', '5')),
        'startup_delay': int(os.getenv('WORKER_STARTUP_DELAY', '5')),  # seconds before first poll
        'idle_backoff': [5, 10, 20, 30, 60],  # Progressive backoff when queue empty
        'model_size': os.getenv('WORKER_MODEL_SIZE', 'medium'),  # whisperX model
        'provider': os.getenv('WORKER_PROVIDER', 'local'),  # local or openai
    }


QUEUE_NAME = "video_audio_transcription"


# =============================================================================
# Global State
# =============================================================================

_worker_task: Optional[asyncio.Task] = None
_worker_shutdown_event: Optional[asyncio.Event] = None
_worker_supabase_client = None
_worker_stats = {
    "jobs_processed": 0,
    "jobs_failed": 0,
    "jobs_retried": 0,
    "last_poll_time": None,
    "last_job_time": None,
    "errors": []
}


# =============================================================================
# Internal Functions (imported from main.py)
# =============================================================================

def _get_main_module():
    """Lazy import main module to avoid circular imports."""
    import main
    return main


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Queue Operations
# =============================================================================

def _ack_delete(msg_id: int):
    """Delete message from queue (success acknowledgment)."""
    global _worker_supabase_client
    try:
        _worker_supabase_client.rpc("pgmq_delete_one", {
            "queue_name": QUEUE_NAME,
            "msg_id": msg_id
        }).execute()
        logger.debug(f"Acked (delete) msg_id={msg_id}")
    except Exception as e:
        logger.error(f"Failed to ack delete msg_id={msg_id}: {str(e)}")


def _ack_archive(msg_id: int):
    """Archive message (failed after max retries)."""
    global _worker_supabase_client
    try:
        _worker_supabase_client.rpc("pgmq_archive_one", {
            "queue_name": QUEUE_NAME,
            "msg_id": msg_id
        }).execute()
        logger.debug(f"Acked (archive) msg_id={msg_id}")
    except Exception as e:
        logger.error(f"Failed to ack archive msg_id={msg_id}: {str(e)}")


# =============================================================================
# Job Processing
# =============================================================================

async def _process_job(job: dict, config: dict):
    """
    Process a single transcription job.

    Flow:
    1. Validate job data
    2. Claim document (atomic update: pending -> processing)
    3. Fetch document metadata
    4. Extract audio from URL
    5. Transcribe audio
    6. Save transcription to document_transcriptions
    7. Mark document completed
    8. Ack delete message
    """
    global _worker_supabase_client, _worker_stats

    msg_id = job.get("msg_id")
    read_ct = job.get("read_ct", 1)
    message = job.get("message") or {}
    document_id = message.get("document_id")

    logger.info(f"Processing job msg_id={msg_id} document_id={document_id} read_ct={read_ct}")

    # Validate job data
    if not document_id:
        logger.warning(f"Job {msg_id} missing document_id - archiving")
        _ack_archive(msg_id)
        return

    try:
        # =================================================================
        # Step 1: Idempotency guard + claim document atomically
        # =================================================================
        # Only process if status is 'pending' - prevents duplicate processing
        claim_result = _worker_supabase_client.table("documents").update({
            "processing_status": "processing",
            "updated_at": _now_iso()
        }).eq("id", document_id).eq("processing_status", "pending").execute()

        if not claim_result.data or len(claim_result.data) == 0:
            # Document not pending - already processed or being processed
            logger.info(f"Document {document_id} not pending (already processed/processing) - ack delete")
            _ack_delete(msg_id)
            return

        # =================================================================
        # Step 2: Fetch document details
        # =================================================================
        doc_result = _worker_supabase_client.table("documents").select(
            "id, canonical_url, metadata, media_format, lang, title"
        ).eq("id", document_id).single().execute()

        if not doc_result.data:
            raise ValueError(f"Document {document_id} not found after claiming")

        doc = doc_result.data

        # Get media URL (canonical_url or fallback to metadata)
        media_url = doc.get("canonical_url")
        if not media_url and doc.get("metadata"):
            media_url = doc["metadata"].get("media_url") or doc["metadata"].get("url")

        if not media_url:
            raise ValueError("No media URL found (canonical_url or metadata.media_url)")

        # Verify media format
        media_format = doc.get("media_format")
        if media_format not in ["video", "audio"]:
            raise ValueError(f"Invalid media_format: {media_format} (expected video or audio)")

        logger.info(f"Document {document_id}: {media_format} from {media_url[:60]}...")

        # =================================================================
        # Step 3: Extract audio using internal function
        # =================================================================
        logger.info(f"Extracting audio from URL...")

        main = _get_main_module()

        # Call the extract_audio endpoint logic directly (bypass HTTP)
        # We need to extract the core logic - for now call via internal path
        audio_result = await _extract_audio_internal(media_url, main)
        audio_file = audio_result["audio_file"]

        logger.info(f"Audio extracted: {audio_file}")

        # =================================================================
        # Step 4: Transcribe audio
        # =================================================================
        logger.info(f"Transcribing audio with provider={config['provider']} model={config['model_size']}...")

        # Use the existing semaphore from main.py for concurrency control
        async with main.transcription_semaphore:
            transcription = await main._transcribe_audio_internal(
                audio_file=audio_file,
                language=doc.get("lang"),
                model_size=config['model_size'],
                provider=config['provider'],
                output_format="json",
                video_id=audio_result.get("video_id"),
                url=media_url,
                duration=audio_result.get("duration"),
                platform=audio_result.get("platform")
            )

        logger.info(f"Transcription complete: {len(transcription.get('segments', []))} segments")

        # =================================================================
        # Step 5: Upsert to document_transcriptions
        # =================================================================
        logger.info(f"Saving transcription to document_transcriptions...")

        # Build full_text and counts from segments
        segments = transcription.get("segments", [])
        full_text = ' '.join([s.get('text', '').strip() for s in segments])
        word_count = len(full_text.split())
        segment_count = len(segments)

        upsert_data = {
            "document_id": document_id,
            "segments": segments,
            "language": transcription.get("language", "unknown"),
            "source": "ai",
            "model": transcription.get("model"),
            "full_text": full_text,
            "word_count": word_count,
            "segment_count": segment_count,
            "confidence_score": None,
            "metadata": transcription.get("metadata", {}),
            "updated_at": _now_iso()
        }

        _worker_supabase_client.table("document_transcriptions").upsert(
            upsert_data,
            on_conflict="document_id"
        ).execute()

        logger.info(f"Transcription saved: {word_count} words, {segment_count} segments")

        # =================================================================
        # Step 6: Mark document completed
        # =================================================================
        _worker_supabase_client.table("documents").update({
            "processing_status": "completed",
            "processed_at": _now_iso(),
            "processing_error": None,
            "updated_at": _now_iso()
        }).eq("id", document_id).execute()

        # =================================================================
        # Step 7: Ack delete message
        # =================================================================
        _ack_delete(msg_id)

        _worker_stats["jobs_processed"] += 1
        _worker_stats["last_job_time"] = datetime.now().isoformat()

        logger.info(f"✓ Job completed for document {document_id}")

    except Exception as e:
        error_msg = str(e)[:500]  # Truncate long errors
        logger.error(f"Job processing failed: {error_msg}")
        logger.exception("Full traceback:")

        # Track error
        _worker_stats["errors"].append({
            "document_id": document_id,
            "msg_id": msg_id,
            "error": error_msg,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only last 10 errors
        _worker_stats["errors"] = _worker_stats["errors"][-10:]

        # Retry logic
        if read_ct >= config['max_retries']:
            logger.error(f"Max retries reached ({read_ct}/{config['max_retries']}) - marking as error")
            try:
                _worker_supabase_client.table("documents").update({
                    "processing_status": "error",
                    "processing_error": f"Failed after {read_ct} attempts: {error_msg}",
                    "updated_at": _now_iso()
                }).eq("id", document_id).execute()
            except Exception as update_err:
                logger.error(f"Failed to update document error status: {update_err}")

            _ack_archive(msg_id)
            _worker_stats["jobs_failed"] += 1
        else:
            logger.warning(f"Retry {read_ct}/{config['max_retries']} - returning to pending")
            try:
                _worker_supabase_client.table("documents").update({
                    "processing_status": "pending",
                    "processing_error": f"Retry {read_ct}: {error_msg}",
                    "updated_at": _now_iso()
                }).eq("id", document_id).execute()
            except Exception as update_err:
                logger.error(f"Failed to update document retry status: {update_err}")

            # Don't ack - message will reappear after VT
            _worker_stats["jobs_retried"] += 1


async def _extract_audio_internal(url: str, main) -> dict:
    """
    Extract audio from URL using the existing extract_audio logic.

    This function reuses the core logic from the /extract-audio endpoint
    without the HTTP layer.
    """
    import uuid

    # Apply rate limiting for YouTube
    if main.is_youtube_url(url):
        await main.youtube_rate_limit()

    # Generate unique ID for audio file
    audio_uid = uuid.uuid4().hex[:8]
    output_format = "mp3"
    audio_path = os.path.join(main.CACHE_DIR, "audio", f"{audio_uid}.{output_format}")

    use_binary = main.is_youtube_url(url) and os.path.exists(main.YTDLP_BINARY)

    # Get metadata
    title = "Unknown"
    try:
        if use_binary:
            stdout, stderr, code = main.run_ytdlp_binary([
                '--skip-download', '--print', '%(title)s',
                url
            ])
            title = stdout.strip() if code == 0 else "Unknown"
        else:
            import yt_dlp
            meta_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown")
    except Exception:
        pass

    # Extract audio using yt-dlp
    if use_binary:
        # Use standalone binary for YouTube
        stdout, stderr, code = main.run_ytdlp_binary([
            '-f', 'bestaudio/best',
            '-x', '--audio-format', output_format,
            '--audio-quality', '192',
            '-o', audio_path.replace(f'.{output_format}', '.%(ext)s'),
            url
        ], timeout=600)
        if code != 0:
            raise Exception(f"yt-dlp binary failed: {stderr}")
    else:
        import yt_dlp
        # Use Python library for non-YouTube
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
    audio_cache_dir = os.path.join(main.CACHE_DIR, "audio")
    for f in os.listdir(audio_cache_dir):
        if f.startswith(audio_uid):
            actual_audio_path = os.path.join(audio_cache_dir, f)
            break

    if not actual_audio_path or not os.path.exists(actual_audio_path):
        raise Exception("Audio extraction completed but file not found")

    # Get metadata for response
    video_id = None
    video_duration = None
    platform = main.get_platform_from_url(url) if hasattr(main, 'get_platform_from_url') else None

    try:
        if use_binary:
            stdout, _, code = main.run_ytdlp_binary([
                '--skip-download', '-j', url
            ])
            if code == 0:
                import json
                info = json.loads(stdout)
                video_id = info.get("id")
                video_duration = info.get("duration")
        else:
            import yt_dlp
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
# Main Worker Loop
# =============================================================================

async def _worker_loop():
    """
    Main worker loop - continuously polls queue and processes jobs.

    Uses progressive backoff when queue is empty to reduce load.
    """
    global _worker_stats, _worker_shutdown_event, _worker_supabase_client

    config = get_worker_config()
    idle_index = 0  # For progressive backoff

    # Initial delay before first poll
    logger.info(f"Starting worker loop in {config['startup_delay']}s...")
    await asyncio.sleep(config['startup_delay'])

    logger.info("Worker loop started - polling for jobs")

    while not _worker_shutdown_event.is_set():
        try:
            _worker_stats["last_poll_time"] = datetime.now().isoformat()

            # Dequeue batch from PGMQ
            result = _worker_supabase_client.rpc(
                "dequeue_video_audio_transcription",
                {
                    "vt_seconds": config['vt_seconds'],
                    "qty": config['batch_size']
                }
            ).execute()

            jobs = result.data or []

            if not jobs:
                # Progressive backoff when idle
                sleep_time = config['idle_backoff'][min(idle_index, len(config['idle_backoff']) - 1)]
                idle_index += 1
                logger.debug(f"No jobs found, sleeping {sleep_time}s (backoff level {idle_index})")

                # Check shutdown during sleep
                try:
                    await asyncio.wait_for(
                        _worker_shutdown_event.wait(),
                        timeout=sleep_time
                    )
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    continue  # Continue polling

            # Reset backoff when jobs found
            idle_index = 0
            logger.info(f"Dequeued {len(jobs)} job(s)")

            # Process jobs in parallel (respecting semaphore in each job)
            tasks = [_process_job(job, config) for job in jobs]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Brief pause between batches
            await asyncio.sleep(config['poll_interval'])

        except Exception as e:
            logger.error(f"Worker loop error: {str(e)}")
            logger.exception("Full traceback:")
            # Brief pause on error before retrying
            await asyncio.sleep(10)

    logger.info("Worker loop shutting down...")


# =============================================================================
# Public API
# =============================================================================

async def start_worker():
    """
    Start the background transcription worker.

    Called from FastAPI startup event. Non-blocking.
    Worker runs as an asyncio background task.
    """
    global _worker_task, _worker_shutdown_event, _worker_supabase_client

    config = get_worker_config()

    if not config['enabled']:
        logger.info("Transcription worker disabled (TRANSCRIPTION_WORKER_ENABLED=false)")
        return

    if _worker_task is not None and not _worker_task.done():
        logger.warning("Transcription worker already running, skipping start")
        return

    # Check Supabase configuration
    try:
        main = _get_main_module()
        if not main.supabase_client:
            logger.warning("Transcription worker disabled - Supabase not configured")
            logger.warning("Set SUPABASE_URL and SUPABASE_SERVICE_KEY to enable")
            return
        _worker_supabase_client = main.supabase_client
    except Exception as e:
        logger.warning(f"Transcription worker disabled - {str(e)}")
        return

    logger.info("=" * 60)
    logger.info("Starting Transcription Worker")
    logger.info("=" * 60)
    logger.info(f"Poll interval: {config['poll_interval']}s")
    logger.info(f"Batch size: {config['batch_size']}")
    logger.info(f"VT seconds: {config['vt_seconds']} ({config['vt_seconds']//60} minutes)")
    logger.info(f"Max retries: {config['max_retries']}")
    logger.info(f"Model: {config['model_size']} (provider: {config['provider']})")
    logger.info(f"Max concurrent: {main.MAX_CONCURRENT_TRANSCRIPTIONS}")
    logger.info("=" * 60)

    # Create shutdown event and start background task
    _worker_shutdown_event = asyncio.Event()
    _worker_task = asyncio.create_task(_worker_loop())

    logger.info("✓ Transcription worker started successfully")


async def stop_worker():
    """
    Gracefully stop the transcription worker.

    Called from FastAPI shutdown event.
    Waits for in-flight jobs to complete (with timeout).
    """
    global _worker_task, _worker_shutdown_event

    if _worker_task is None:
        return

    logger.info("Stopping transcription worker...")

    # Signal shutdown
    _worker_shutdown_event.set()

    # Wait for worker to finish (with timeout)
    try:
        await asyncio.wait_for(_worker_task, timeout=120)
        logger.info("✓ Transcription worker stopped gracefully")
    except asyncio.TimeoutError:
        logger.warning("Worker shutdown timeout - cancelling")
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Worker cancelled")
    except asyncio.CancelledError:
        logger.info("Worker was cancelled")

    _worker_task = None
    _worker_shutdown_event = None


def get_worker_status() -> dict:
    """
    Get current worker status for monitoring.

    Returns:
        Dict with running state, configuration, and statistics.
    """
    global _worker_task, _worker_stats

    config = get_worker_config()

    is_running = _worker_task is not None and not _worker_task.done()

    return {
        "running": is_running,
        "enabled": config['enabled'],
        "stats": {
            "jobs_processed": _worker_stats["jobs_processed"],
            "jobs_failed": _worker_stats["jobs_failed"],
            "jobs_retried": _worker_stats["jobs_retried"],
            "last_poll_time": _worker_stats["last_poll_time"],
            "last_job_time": _worker_stats["last_job_time"],
            "recent_errors": _worker_stats["errors"][-5:] if _worker_stats["errors"] else []
        },
        "config": {
            "poll_interval": config['poll_interval'],
            "batch_size": config['batch_size'],
            "vt_seconds": config['vt_seconds'],
            "max_retries": config['max_retries'],
            "model_size": config['model_size'],
            "provider": config['provider']
        }
    }


# Exports
__all__ = [
    'start_worker',
    'stop_worker',
    'get_worker_status',
]
