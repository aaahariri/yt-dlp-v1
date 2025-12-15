import os
import re
import time
import uuid
import json
import hashlib
import requests
import unicodedata
import asyncio
import subprocess
from urllib.parse import quote
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException, Depends, Header, Body
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import yt_dlp
from dotenv import load_dotenv
from supabase import create_client, Client
from scripts.cookie_scheduler import start_scheduler, stop_scheduler, trigger_manual_refresh, get_scheduler_status

app = FastAPI()

# Load environment variables from .env file
load_dotenv()

# CORS configuration
app.add_middleware(CORSMiddleware,
    allow_origins=[os.getenv("ALLOWED_ORIGIN")],  # Adjust this to your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key authentication
def verify_api_key(x_api_key: str = Header(None)):
    expected_key = os.getenv("API_KEY")
    if not expected_key:
        raise HTTPException(status_code=500, detail="API key not configured")
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True

# Ensure downloads directory exists
DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", "./downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Unified cache configuration
CACHE_DIR = os.getenv("CACHE_DIR", "./cache")
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "3"))

# Create cache subdirectories
for subdir in ["videos", "audio", "transcriptions", "screenshots"]:
    os.makedirs(os.path.join(CACHE_DIR, subdir), exist_ok=True)

# yt-dlp Configuration
# Use standalone binary (with Deno support) for YouTube downloads
# See: https://github.com/yt-dlp/yt-dlp/issues/15012
YTDLP_BINARY = os.getenv("YTDLP_BINARY", "./bin/yt-dlp")
YTDLP_COOKIES_FILE = os.getenv("YTDLP_COOKIES_FILE", None)  # Path to cookies.txt for authenticated downloads

# Rate limiting to avoid YouTube bans
# See: https://github.com/yt-dlp/yt-dlp/wiki/Extractors
YTDLP_MIN_SLEEP = int(os.getenv("YTDLP_MIN_SLEEP", "7"))  # Minimum seconds between requests
YTDLP_MAX_SLEEP = int(os.getenv("YTDLP_MAX_SLEEP", "25"))  # Maximum seconds between requests
YTDLP_SLEEP_REQUESTS = float(os.getenv("YTDLP_SLEEP_REQUESTS", "1.0"))  # Seconds between API requests

# Track last YouTube request time for rate limiting
_last_youtube_request = 0
_youtube_request_lock = asyncio.Lock()

import random

async def youtube_rate_limit():
    """Apply rate limiting for YouTube requests with random delay."""
    global _last_youtube_request
    async with _youtube_request_lock:
        now = time.time()
        elapsed = now - _last_youtube_request
        if elapsed < YTDLP_MIN_SLEEP:
            delay = random.uniform(YTDLP_MIN_SLEEP, YTDLP_MAX_SLEEP)
            print(f"INFO: Rate limiting - sleeping {delay:.1f}s before YouTube request")
            await asyncio.sleep(delay)
        _last_youtube_request = time.time()

def run_ytdlp_binary(args: list, timeout: int = 300, retry_on_auth_failure: bool = True) -> tuple:
    """
    Run yt-dlp standalone binary with given arguments.
    Returns (stdout, stderr, return_code).
    Uses Deno for JavaScript challenges (required for YouTube 2025.11+).

    Auto-detects authentication failures and triggers cookie refresh on first retry.

    Args:
        args: List of yt-dlp command arguments
        timeout: Command timeout in seconds
        retry_on_auth_failure: If True, attempt cookie refresh and retry once on auth errors

    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    cmd = [YTDLP_BINARY] + args

    # Add rate limiting options
    cmd.extend([
        '--sleep-requests', str(YTDLP_SLEEP_REQUESTS),
        '--sleep-interval', str(YTDLP_MIN_SLEEP),
        '--max-sleep-interval', str(YTDLP_MAX_SLEEP),
    ])

    # Add cookies if configured
    if YTDLP_COOKIES_FILE and os.path.exists(YTDLP_COOKIES_FILE):
        cmd.extend(['--cookies', YTDLP_COOKIES_FILE])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        stdout, stderr, returncode = result.stdout, result.stderr, result.returncode

        # Detect authentication failures in stderr
        auth_failure_patterns = [
            r'Sign in to confirm you\'?re not a bot',
            r'This video requires authentication',
            r'requires? authentication',
            r'HTTP Error 403',
            r'This video is not available',
            r'Video unavailable',
            r'Private video',
            r'This video is private',
            r'age.restricted',
            r'members.?only',
        ]

        is_auth_failure = any(
            re.search(pattern, stderr, re.IGNORECASE) or re.search(pattern, stdout, re.IGNORECASE)
            for pattern in auth_failure_patterns
        )

        # If auth failure detected and retry enabled, attempt cookie refresh and retry once
        if is_auth_failure and retry_on_auth_failure and returncode != 0:
            print("WARNING: Authentication failure detected in yt-dlp output")
            print(f"WARNING: Error message: {stderr[:200]}")
            print("INFO: Attempting automatic cookie refresh...")

            # Trigger cookie refresh
            refresh_result = trigger_manual_refresh()

            if refresh_result.get("success"):
                print("INFO: Cookie refresh successful, retrying download...")
                # Retry once with fresh cookies (disable retry to prevent infinite loop)
                return run_ytdlp_binary(args, timeout, retry_on_auth_failure=False)
            else:
                print("=" * 60)
                print("WARNING: YOUTUBE AUTHENTICATION FAILED")
                print("=" * 60)
                print(f"Cookie refresh error: {refresh_result.get('error')}")
                print("")
                print("MANUAL ACTION REQUIRED:")
                print("  1. Run locally: python scripts/refresh_youtube_cookies.py --interactive")
                print("  2. Complete any Google security challenges in the browser")
                print("  3. Upload cookies.txt and cookies_state.json to server")
                print("")
                print("See Deploy.md for details.")
                print("=" * 60)

        return stdout, stderr, returncode

    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except Exception as e:
        return "", str(e), 1

def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube URL."""
    youtube_patterns = [
        r'youtube\.com',
        r'youtu\.be',
        r'youtube-nocookie\.com',
    ]
    return any(re.search(pattern, url, re.IGNORECASE) for pattern in youtube_patterns)

# Log yt-dlp binary status
if os.path.exists(YTDLP_BINARY):
    stdout, _, _ = run_ytdlp_binary(['--version'])
    print(f"INFO: yt-dlp standalone binary version: {stdout.strip()}")
    print(f"INFO: Rate limiting: {YTDLP_MIN_SLEEP}-{YTDLP_MAX_SLEEP}s between downloads")
else:
    print(f"WARNING: yt-dlp binary not found at {YTDLP_BINARY}")
    print("WARNING: YouTube downloads may fail. Download from: https://github.com/yt-dlp/yt-dlp/releases")

# Concurrency control for transcription endpoints
# This prevents memory overload when multiple transcription requests arrive
# Set via environment variable or use default based on common model sizes
MAX_CONCURRENT_TRANSCRIPTIONS = int(os.getenv("MAX_CONCURRENT_TRANSCRIPTIONS", "2"))
transcription_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSCRIPTIONS)

print(f"INFO: Max concurrent transcriptions set to: {MAX_CONCURRENT_TRANSCRIPTIONS}")

# Device detection for AI transcription (whisperX)
# Detect optimal device on server startup to avoid repeated detection per request
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_GPU_INFO = None

try:
    import torch

    if torch.cuda.is_available():
        WHISPER_DEVICE = "cuda"
        WHISPER_COMPUTE_TYPE = "float16"

        # Try to get GPU model name
        try:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_count = torch.cuda.device_count()
            WHISPER_GPU_INFO = f"{gpu_name} (x{gpu_count})" if gpu_count > 1 else gpu_name
            print(f"INFO: NVIDIA GPU detected - whisperX will use CUDA with float16 compute type")
            print(f"INFO: GPU Model: {WHISPER_GPU_INFO}")
        except Exception:
            WHISPER_GPU_INFO = "CUDA GPU (model unknown)"
            print(f"INFO: NVIDIA GPU (CUDA) detected - whisperX will use CUDA with float16 compute type")

    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        WHISPER_DEVICE = "mps"
        WHISPER_COMPUTE_TYPE = "float16"

        # For Apple Silicon, we can infer from system info
        try:
            import platform
            import subprocess
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                  capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                cpu_info = result.stdout.strip()
                WHISPER_GPU_INFO = f"Apple Silicon ({cpu_info})"
            else:
                WHISPER_GPU_INFO = "Apple Silicon GPU"
        except Exception:
            WHISPER_GPU_INFO = "Apple Silicon GPU"

        print(f"INFO: Apple Silicon GPU detected - whisperX will use MPS with float16 compute type")
        if WHISPER_GPU_INFO:
            print(f"INFO: GPU Model: {WHISPER_GPU_INFO}")
    else:
        print(f"INFO: No GPU detected - whisperX will use CPU with int8 compute type (slower)")
except ImportError:
    print(f"INFO: PyTorch not installed - whisperX device detection skipped (will fallback to CPU if used)")
except Exception as e:
    print(f"WARNING: Device detection failed ({str(e)}) - whisperX will default to CPU")

# Supabase client initialization (optional, only if configured)
supabase_client: Optional[Client] = None
try:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print("INFO: Supabase client initialized successfully")
    else:
        print("INFO: Supabase not configured (SUPABASE_URL/SUPABASE_SERVICE_KEY missing) - transcription storage disabled")
except Exception as e:
    print(f"WARNING: Failed to initialize Supabase client: {str(e)}")
    supabase_client = None

def get_supabase_client() -> Client:
    """
    Get Supabase client or raise error if not configured.
    Use this in endpoints that require Supabase.
    """
    if supabase_client is None:
        raise HTTPException(
            status_code=503,
            detail="Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables."
        )
    return supabase_client

def upload_screenshot_to_supabase(file_path: str, storage_path: str) -> dict:
    """
    Upload screenshot to Supabase storage bucket.
    Reuses existing get_supabase_client().
    """
    supabase = get_supabase_client()

    with open(file_path, 'rb') as f:
        result = supabase.storage.from_("public_media").upload(
            path=storage_path,
            file=f.read(),
            file_options={"content-type": "image/jpeg"}
        )

    # Get public URL
    public_url = supabase.storage.from_("public_media").get_public_url(storage_path)

    return {
        "storage_path": storage_path,
        "public_url": public_url
    }

def save_screenshot_metadata(data: dict) -> dict:
    """Save screenshot metadata to public_media table."""
    supabase = get_supabase_client()
    result = supabase.table("public_media").insert(data).execute()
    return result.data[0] if result.data else None

# Application lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    print("INFO: Starting application...")

    # Start cookie refresh scheduler
    try:
        start_scheduler()
    except Exception as e:
        print(f"WARNING: Failed to start cookie scheduler: {str(e)}")
        print("WARNING: Scheduled cookie refresh disabled")

    # Start transcription worker
    try:
        from scripts.transcription_worker import start_worker
        await start_worker()
    except Exception as e:
        print(f"WARNING: Failed to start transcription worker: {str(e)}")
        print("WARNING: Background transcription processing disabled")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    print("INFO: Shutting down application...")

    # Stop transcription worker first (may have in-flight jobs)
    try:
        from scripts.transcription_worker import stop_worker
        await stop_worker()
    except Exception as e:
        print(f"WARNING: Error stopping transcription worker: {str(e)}")

    # Stop cookie refresh scheduler
    try:
        stop_scheduler()
    except Exception as e:
        print(f"WARNING: Error stopping cookie scheduler: {str(e)}")

# Utility functions for subtitle parsing and cleanup
def parse_vtt_to_text(vtt_content: str) -> str:
    """Parse VTT content and extract plain text."""
    lines = vtt_content.split('\n')
    text_parts = []
    
    for line in lines:
        line = line.strip()
        # Skip empty lines, WEBVTT header, and timestamp lines
        if not line or line.startswith('WEBVTT') or '-->' in line or line.isdigit():
            continue
        # Skip lines that look like positioning/styling
        if line.startswith('<') or line.startswith('NOTE') or 'align:' in line:
            continue
        
        # Clean up any remaining HTML tags
        line = re.sub(r'<[^>]+>', '', line)
        text_parts.append(line)
    
    return ' '.join(text_parts)

def parse_srt_to_text(srt_content: str) -> str:
    """Parse SRT content and extract plain text."""
    lines = srt_content.split('\n')
    text_parts = []
    
    for line in lines:
        line = line.strip()
        # Skip empty lines, sequence numbers, and timestamp lines
        if not line or line.isdigit() or '-->' in line:
            continue
        
        # Clean up any HTML tags
        line = re.sub(r'<[^>]+>', '', line)
        text_parts.append(line)
    
    return ' '.join(text_parts)

def cleanup_old_transcriptions(max_age_hours: int = 1):
    """Remove transcription files older than specified hours."""
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

def parse_timestamp_to_seconds(timestamp: str) -> float:
    """
    Auto-detect and parse timestamp to seconds.
    Supports: SRT "00:01:30,500" or float "90.5"
    """
    timestamp = timestamp.strip()

    # Try SRT/VTT format: HH:MM:SS,mmm or HH:MM:SS.mmm
    if ':' in timestamp:
        timestamp = timestamp.replace(',', '.')
        parts = timestamp.split(':')
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds

    # Try float seconds
    return float(timestamp)

def format_seconds_to_srt(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def get_cached_video(video_id: str) -> Optional[str]:
    """
    Find cached video by video_id.
    Returns file path if fresh (within TTL), None if expired or missing.
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

def extract_screenshot(video_path: str, timestamp_seconds: float, output_path: str, quality: int = 2) -> dict:
    """
    Extract single frame from video using FFmpeg.
    Returns metadata dict or raises exception.
    """
    cmd = [
        'ffmpeg',
        '-ss', str(timestamp_seconds),  # Seek position
        '-i', video_path,                # Input file
        '-vframes', '1',                 # Extract 1 frame
        '-q:v', str(quality),            # JPEG quality (1-31, lower=better)
        '-y',                            # Overwrite output
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0 or not os.path.exists(output_path):
        raise Exception(f"FFmpeg failed: {result.stderr}")

    # Get image dimensions using ffprobe
    probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                 '-show_entries', 'stream=width,height', '-of', 'json', output_path]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)

    width, height = 0, 0
    if probe_result.returncode == 0:
        probe_data = json.loads(probe_result.stdout)
        if probe_data.get('streams'):
            width = probe_data['streams'][0].get('width', 0)
            height = probe_data['streams'][0].get('height', 0)

    return {
        "file_path": output_path,
        "size_bytes": os.path.getsize(output_path),
        "width": width,
        "height": height
    }

def get_video_id_from_url(url: str) -> str:
    """Extract a consistent ID from video URL for caching."""
    # Create a hash of the URL for consistent file naming
    return hashlib.md5(url.encode()).hexdigest()[:12]

# Language code to name mapping for common languages
LANGUAGE_NAMES = {
    'en': 'English',
    'en-US': 'English (US)',
    'en-GB': 'English (UK)',
    'eng-US': 'English (US)',
    'es': 'Spanish',
    'es-419': 'Spanish (Latin America)',
    'es-ES': 'Spanish (Spain)',
    'fr': 'French',
    'fr-FR': 'French (France)',
    'de': 'German',
    'de-DE': 'German (Germany)',
    'it': 'Italian',
    'pt': 'Portuguese',
    'pt-BR': 'Portuguese (Brazil)',
    'pt-PT': 'Portuguese (Portugal)',
    'ru': 'Russian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh': 'Chinese',
    'zh-CN': 'Chinese (Simplified)',
    'zh-TW': 'Chinese (Traditional)',
    'ar': 'Arabic',
    'ara-SA': 'Arabic (Saudi Arabia)',
    'hi': 'Hindi',
    'id': 'Indonesian',
    'tr': 'Turkish',
    'nl': 'Dutch',
    'pl': 'Polish',
    'sv': 'Swedish',
    'no': 'Norwegian',
    'da': 'Danish',
    'fi': 'Finnish',
    'he': 'Hebrew',
    'th': 'Thai',
    'vi': 'Vietnamese',
    'uk': 'Ukrainian',
    'cs': 'Czech',
    'hu': 'Hungarian',
    'ro': 'Romanian',
    'bg': 'Bulgarian',
    'sr': 'Serbian',
    'hr': 'Croatian',
    'sk': 'Slovak',
    'sl': 'Slovenian',
    'et': 'Estonian',
    'lv': 'Latvian',
    'lt': 'Lithuanian',
    'ms': 'Malay',
    'fa': 'Persian',
    'ur': 'Urdu',
    'bn': 'Bengali',
    'ta': 'Tamil',
    'te': 'Telugu',
    'ml': 'Malayalam',
    'kn': 'Kannada',
    'mr': 'Marathi',
    'gu': 'Gujarati',
    'pa': 'Punjabi',
    'ne': 'Nepali',
    'si': 'Sinhala',
    'my': 'Burmese',
    'km': 'Khmer',
    'lo': 'Lao',
    'ka': 'Georgian',
    'am': 'Amharic',
    'sw': 'Swahili',
    'zu': 'Zulu',
    'xh': 'Xhosa',
    'af': 'Afrikaans',
    'sq': 'Albanian',
    'eu': 'Basque',
    'be': 'Belarusian',
    'bs': 'Bosnian',
    'ca': 'Catalan',
    'co': 'Corsican',
    'cy': 'Welsh',
    'eo': 'Esperanto',
    'et': 'Estonian',
    'fil': 'Filipino',
    'fy': 'Frisian',
    'ga': 'Irish',
    'gd': 'Scottish Gaelic',
    'gl': 'Galician',
    'ha': 'Hausa',
    'haw': 'Hawaiian',
    'hmn': 'Hmong',
    'ht': 'Haitian Creole',
    'ig': 'Igbo',
    'is': 'Icelandic',
    'jv': 'Javanese',
    'kk': 'Kazakh',
    'ku': 'Kurdish',
    'ky': 'Kyrgyz',
    'la': 'Latin',
    'lb': 'Luxembourgish',
    'mg': 'Malagasy',
    'mi': 'Maori',
    'mk': 'Macedonian',
    'mn': 'Mongolian',
    'mt': 'Maltese',
    'ny': 'Chichewa',
    'or': 'Odia',
    'ps': 'Pashto',
    'sd': 'Sindhi',
    'sm': 'Samoan',
    'sn': 'Shona',
    'so': 'Somali',
    'st': 'Southern Sotho',
    'su': 'Sundanese',
    'tg': 'Tajik',
    'tk': 'Turkmen',
    'tl': 'Tagalog',
    'tt': 'Tatar',
    'ug': 'Uyghur',
    'uz': 'Uzbek',
    'yi': 'Yiddish',
    'yo': 'Yoruba'
}

def get_language_name(code: str) -> str:
    """Get human-readable language name from code."""
    # First try exact match
    if code in LANGUAGE_NAMES:
        return LANGUAGE_NAMES[code]

    # Try base language code (e.g., 'en' from 'en-US')
    base_code = code.split('-')[0].lower()
    if base_code in LANGUAGE_NAMES:
        return f"{LANGUAGE_NAMES[base_code]} ({code})"

    # Return original code if no match found
    return code

def convert_srt_timestamp_to_seconds(timestamp: str) -> float:
    """
    Convert SRT/VTT timestamp string to seconds (float).

    Examples:
        "00:00:00,240" -> 0.24
        "00:01:23,456" -> 83.456
        "01:30:45.123" -> 5445.123
    """
    # Replace comma with dot for milliseconds (SRT uses comma, VTT uses dot)
    timestamp = timestamp.replace(',', '.')

    # Parse HH:MM:SS.mmm format
    parts = timestamp.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    else:
        # Fallback: try to parse as float
        return float(timestamp)

def get_platform_from_url(url: str) -> str:
    """
    Detect platform from URL and return lowercase platform name.
    Returns: youtube, tiktok, instagram, facebook, twitter, vimeo, dailymotion, twitch, or unknown.
    """
    url_lower = url.lower()

    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    elif 'tiktok.com' in url_lower:
        return 'tiktok'
    elif 'instagram.com' in url_lower:
        return 'instagram'
    elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
        return 'facebook'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'twitter'
    elif 'vimeo.com' in url_lower:
        return 'vimeo'
    elif 'dailymotion.com' in url_lower:
        return 'dailymotion'
    elif 'twitch.tv' in url_lower:
        return 'twitch'
    else:
        return 'unknown'

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
    from datetime import datetime

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

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be safe for filesystem while preserving Unicode."""
    # Normalize Unicode characters
    filename = unicodedata.normalize('NFC', filename)
    # Replace path separators and other problematic characters
    filename = filename.replace('/', '-').replace('\\', '-')
    filename = filename.replace(':', '-').replace('*', '-')
    filename = filename.replace('?', '-').replace('"', '-')
    filename = filename.replace('<', '-').replace('>', '-')
    filename = filename.replace('|', '-').replace('\0', '-')
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    # Limit length to prevent filesystem issues
    if len(filename) > 200:
        filename = filename[:200]
    return filename or 'video'

def get_platform_prefix(url: str) -> str:
    """
    Detect platform from URL and return prefix code.
    Returns: YT, TT, IG, FB, X, VM, DM, TW, or VIDEO (unknown).
    """
    url_lower = url.lower()

    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'YT'
    elif 'tiktok.com' in url_lower:
        return 'TT'
    elif 'instagram.com' in url_lower:
        return 'IG'
    elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
        return 'FB'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'X'
    elif 'vimeo.com' in url_lower:
        return 'VM'
    elif 'dailymotion.com' in url_lower:
        return 'DM'
    elif 'twitch.tv' in url_lower:
        return 'TW'
    else:
        return 'VIDEO'

def format_title_for_filename(title: str, max_length: int = 50) -> str:
    """
    Format title for filename: remove channel names, sanitize chars, replace spaces with hyphens.
    Truncates at word boundaries (max 50 chars) to prevent "Inter-Equity" vs "Inter-Equity-Trading".
    """
    # Remove channel name suffix (e.g., "Video Title | Channel Name" → "Video Title")
    if '|' in title:
        title = title.split('|')[0].strip()
    elif ' - ' in title and len(title.split(' - ')[-1]) < 30:
        parts = title.split(' - ')
        if len(parts) > 1:
            last_part = parts[-1].lower()
            # Keep if it looks like episode/part number
            if not any(word in last_part for word in ['ep', 'part', 'tutorial', 'guide', 'how']):
                title = ' - '.join(parts[:-1]).strip()

    title = sanitize_filename(title)
    title = re.sub(r'\s+', ' ', title)  # Normalize whitespace
    title = title.replace(' ', '-')     # Spaces to hyphens
    title = re.sub(r'-+', '-', title)   # Remove duplicate hyphens
    title = title.strip('-')            # Remove leading/trailing hyphens

    # Truncate at word boundary if too long
    if len(title) > max_length:
        truncated = title[:max_length]
        last_hyphen = truncated.rfind('-')
        if last_hyphen > max_length // 2:
            title = truncated[:last_hyphen]
        else:
            title = truncated

    return title or 'video'

def create_formatted_filename(url: str, title: str, extension: str = 'mp4', custom_title: str = None) -> str:
    """
    Create filename with platform prefix: {PLATFORM}-{formatted-title}.{ext}
    Example: "YT-My-Video.mp4"
    """
    platform_prefix = get_platform_prefix(url)
    formatted_title = format_title_for_filename(custom_title if custom_title else title)
    return f"{platform_prefix}-{formatted_title}.{extension}"

def encode_content_disposition_filename(filename: str) -> str:
    """Encode filename for Content-Disposition header following RFC 5987."""
    # For ASCII filenames, use simple format
    try:
        filename.encode('ascii')
        # Escape quotes for the simple format
        safe_filename = filename.replace('"', '\\"')
        return f'attachment; filename="{safe_filename}"'
    except UnicodeEncodeError:
        # For Unicode filenames, use RFC 5987 encoding
        encoded_filename = quote(filename, safe='')
        # Also provide ASCII fallback
        ascii_filename = unicodedata.normalize('NFD', filename)
        ascii_filename = ascii_filename.encode('ascii', 'ignore').decode('ascii')
        ascii_filename = ascii_filename.replace('"', '\\"') or 'video'
        return f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'

@app.get("/download")
async def download_video(
    url: str = Query(...),
    format: str = Query("best"),
    keep: bool = Query(False),
    custom_title: str = Query(None, description="Optional custom title for the downloaded file"),
    cookies_file: str = Query(None, description="Optional path to cookies file for sites requiring authentication"),
    _: bool = Depends(verify_api_key)
):
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

# ============================================================================
# PYDANTIC DATA MODELS (for request/response validation, NOT AI models)
# ============================================================================

class BatchDownloadRequest(BaseModel):
    """Request model for batch downloads: validates URLs, format, delays, etc."""
    urls: List[str] = Field(..., description="List of video URLs to download", min_items=1)
    format: str = Field("best[height<=720]", description="Video quality format")
    keep: bool = Field(True, description="Save videos to server storage")
    min_delay: int = Field(5, description="Minimum delay between downloads (seconds)", ge=0, le=300)
    max_delay: int = Field(10, description="Maximum delay between downloads (seconds)", ge=0, le=300)
    cookies_file: Optional[str] = Field(None, description="Path to cookies file")

class VideoDownloadResult(BaseModel):
    """Result for individual video: url, success, filename, size, platform, error."""
    url: str
    success: bool
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    platform: Optional[str] = None
    title: Optional[str] = None
    error: Optional[str] = None

class BatchDownloadResponse(BaseModel):
    """Response with stats and per-video results: total, successful, failed, skipped, downloads[]."""
    total: int
    successful: int
    failed: int
    skipped: int
    downloads: List[VideoDownloadResult]
    total_size: int
    duration_seconds: float

class TranscriptionSaveRequest(BaseModel):
    """Request model for saving transcriptions to Supabase document_transcriptions table."""
    document_id: str = Field(..., description="UUID of the document (foreign key to documents table)")
    segments: List[Dict[str, Any]] = Field(..., description="Transcription segments with start, end, text")
    language: str = Field(..., description="Language code (e.g., 'en', max 5 chars)")
    source: str = Field(..., description="Source: 'subtitle' or 'ai' (max 50 chars)")
    confidence_score: Optional[float] = Field(None, description="Confidence score (0.0-1.0)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (JSONB)")

class TranscriptionSaveResponse(BaseModel):
    """Response after saving transcription."""
    id: str = Field(..., description="Transcription record ID (UUID)")
    document_id: str
    created_at: str
    message: str

class ScreenshotRequest(BaseModel):
    """Request model for screenshot extraction from video at timestamps."""
    video_url: str
    timestamps: List[str]  # SRT format "00:01:30,500" or float seconds "90.5"
    upload_to_supabase: bool = False
    document_id: Optional[str] = None
    quality: int = 2  # FFmpeg JPEG quality 1-31 (lower = better)

class ScreenshotResult(BaseModel):
    """Result for individual screenshot: timestamp, path, dimensions, size."""
    timestamp: float
    timestamp_formatted: str
    file_path: str
    width: int
    height: int
    size_bytes: int
    supabase_url: Optional[str] = None

class ScreenshotResponse(BaseModel):
    """Response with extracted screenshots and metadata."""
    screenshots: List[ScreenshotResult]
    video_id: str
    video_title: str
    video_duration: Optional[int]
    video_cached: bool
    total_extracted: int
    failed_timestamps: List[str] = []

@app.post("/batch-download")
async def batch_download_videos(
    request: BatchDownloadRequest = Body(...),
    _: bool = Depends(verify_api_key)
) -> BatchDownloadResponse:
    """
    Download multiple videos from various platforms with automatic rate limiting.
    Supports YouTube, TikTok, Instagram, Facebook, Twitter, and 1000+ platforms.
    Independent error handling - one failure doesn't stop the batch.
    """
    import random

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

@app.get("/subtitles")
async def get_subtitles(
    url: str = Query(..., description="Video URL to extract subtitles from"),
    lang: str = Query("en", description="Language code (e.g., 'en', 'es', 'fr')"),
    format: str = Query("text", description="Output format: text, json, srt, vtt"),
    auto: bool = Query(True, description="Include auto-generated captions"),
    cookies_file: str = Query(None, description="Optional path to cookies file for authentication"),
    _: bool = Depends(verify_api_key)
):
    try:
        # Run cleanup at start of each request
        cleanup_cache()

        # Configure yt-dlp for subtitle extraction
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': auto,
            'skip_download': True,
            'quiet': True,
            'subtitleslangs': [lang],
            'extractor_args': YTDLP_EXTRACTOR_ARGS,
        }

        # Add cookies file if provided (for sites like Patreon)
        if cookies_file and os.path.exists(cookies_file):
            ydl_opts['cookiefile'] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Get video metadata
            title = info.get("title", "Unknown")
            duration = info.get("duration", 0)
            video_id = get_video_id_from_url(url)
            
            # Extract subtitles
            subtitles = info.get('subtitles', {})
            auto_captions = info.get('automatic_captions', {})
            all_available_langs = list(set(list(subtitles.keys()) + list(auto_captions.keys())))
            
            # Determine which subtitles to use
            available_subs = subtitles.get(lang) or auto_captions.get(lang)
            
            if not available_subs:
                # Try fallback languages
                fallback_langs = ['en', 'en-US', 'en-GB']
                for fallback_lang in fallback_langs:
                    available_subs = subtitles.get(fallback_lang) or auto_captions.get(fallback_lang)
                    if available_subs:
                        lang = fallback_lang
                        break
            
            if not available_subs:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "No subtitles available",
                        "message": f"No subtitles found for language '{lang}'. Use POST /extract-audio + POST /transcribe to generate AI transcription.",
                        "available_languages": all_available_langs,
                        "title": title,
                        "duration": duration,
                        "suggested_workflow": [
                            "1. POST /extract-audio with url parameter",
                            "2. POST /transcribe with returned audio_file path"
                        ]
                    }
                )
            
            # Get the best subtitle format (prefer vtt or srt)
            subtitle_info = None
            for sub in available_subs:
                if sub.get('ext') in ['vtt', 'srt']:
                    subtitle_info = sub
                    break
            
            if not subtitle_info:
                subtitle_info = available_subs[0]  # fallback to first available
            
            subtitle_url = subtitle_info.get('url')
            subtitle_format = subtitle_info.get('ext', 'unknown')
            
            # Download subtitle content
            try:
                response = requests.get(subtitle_url, timeout=30)
                response.raise_for_status()
                subtitle_content = response.text
            except requests.RequestException as e:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to download subtitle content: {str(e)}"
                )
            
            # Return based on requested format
            if format == "text":
                # Parse to plain text
                if subtitle_format == 'vtt':
                    transcript_text = parse_vtt_to_text(subtitle_content)
                elif subtitle_format == 'srt':
                    transcript_text = parse_srt_to_text(subtitle_content)
                else:
                    # Try both parsers
                    transcript_text = parse_vtt_to_text(subtitle_content) or parse_srt_to_text(subtitle_content)
                
                return {
                    "transcript": transcript_text,
                    "word_count": len(transcript_text.split()),
                    "title": title,
                    "duration": duration,
                    "language": lang,
                    "source_format": subtitle_format
                }
            
            elif format == "json" or format == "segments":
                # Return structured data with segments
                segments = []
                if subtitle_format == 'vtt':
                    # Parse VTT with timestamps
                    lines = subtitle_content.split('\n')
                    for i, line in enumerate(lines):
                        if '-->' in line:
                            # Parse timestamp line
                            time_match = re.match(r'(\d+:\d+:\d+\.\d+)\s+-->\s+(\d+:\d+:\d+\.\d+)', line)
                            if time_match and i + 1 < len(lines):
                                start_time_str = time_match.group(1)
                                end_time_str = time_match.group(2)
                                text_line = lines[i + 1].strip()
                                if text_line and not text_line.startswith('<'):
                                    segments.append({
                                        "start": convert_srt_timestamp_to_seconds(start_time_str),
                                        "end": convert_srt_timestamp_to_seconds(end_time_str),
                                        "text": re.sub(r'<[^>]+>', '', text_line)
                                    })

                elif subtitle_format == 'srt':
                    # Parse SRT with timestamps
                    srt_blocks = subtitle_content.strip().split('\n\n')
                    for block in srt_blocks:
                        lines = block.strip().split('\n')
                        if len(lines) >= 3:
                            # lines[0] is sequence number, lines[1] is timestamp, lines[2+] is text
                            timestamp_line = lines[1]
                            time_match = re.match(r'(\d+:\d+:\d+,\d+)\s+-->\s+(\d+:\d+:\d+,\d+)', timestamp_line)
                            if time_match:
                                start_time_str = time_match.group(1)
                                end_time_str = time_match.group(2)
                                text = ' '.join(lines[2:]).strip()
                                text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
                                if text:
                                    segments.append({
                                        "start": convert_srt_timestamp_to_seconds(start_time_str),
                                        "end": convert_srt_timestamp_to_seconds(end_time_str),
                                        "text": text
                                    })

                # Get video_id and platform from yt-dlp info (available from earlier extraction)
                video_id = info.get('id')
                platform = get_platform_from_url(url)

                # Use unified response structure
                return create_unified_transcription_response(
                    title=title,
                    language=lang,
                    segments=segments,
                    source="subtitle",
                    video_id=video_id,
                    url=url,
                    duration=duration,
                    provider=platform,
                    model=None,
                    source_format=subtitle_format,
                    transcription_time=None,
                    platform=platform
                )
            
            elif format == "srt":
                # Return raw SRT content (or convert VTT to SRT-like format)
                return {
                    "title": title,
                    "language": lang,
                    "format": "srt",
                    "content": subtitle_content if subtitle_format == 'srt' else subtitle_content,
                    "source_format": subtitle_format
                }
            
            elif format == "vtt":
                # Return raw VTT content
                return {
                    "title": title,
                    "language": lang,
                    "format": "vtt", 
                    "content": subtitle_content,
                    "source_format": subtitle_format
                }
            
            else:
                raise HTTPException(status_code=400, detail="Invalid format. Use: text, json, segments, srt, or vtt")
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting subtitles: {str(e)}")

@app.post("/extract-audio")
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
            import subprocess
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

@app.post("/transcribe")
async def transcribe_audio(
    audio_file: str = Query(..., description="Path to audio file on server (from /extract-audio)"),
    language: str = Query(None, description="Language code (auto-detect if not specified)"),
    model_size: str = Query("medium", description="Model size: tiny, small, medium, large-v2, large-v3, turbo"),
    provider: str = Query("local", description="Provider: local (whisperX) or openai"),
    output_format: str = Query("json", description="Output format: json, srt, vtt, text"),
    video_id: str = Query(None, description="Video ID from /extract-audio (for unified response)"),
    url: str = Query(None, description="Video URL from /extract-audio (for unified response)"),
    duration: int = Query(None, description="Video duration from /extract-audio (for unified response)"),
    platform: str = Query(None, description="Platform name from /extract-audio (for unified response)"),
    _: bool = Depends(verify_api_key)
):
    """
    Transcribe audio file using AI.

    Providers:
    - local: whisperX (70x real-time on GPU, 3-5x on CPU, $0 cost, word-level timestamps)
    - openai: OpenAI Whisper API ($0.006/min, managed service)

    Input: audio_file path (from /extract-audio endpoint)
    Output: Transcription in unified format

    Workflow:
    1. POST /extract-audio → get audio_file path and metadata
    2. POST /transcribe → get transcription

    Note: This endpoint is limited to MAX_CONCURRENT_TRANSCRIPTIONS concurrent requests
    to prevent memory overload. Additional requests will wait in queue.
    """
    # Acquire semaphore to limit concurrent transcriptions
    async with transcription_semaphore:
        return await _transcribe_audio_internal(
            audio_file, language, model_size, provider, output_format,
            video_id, url, duration, platform
        )


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

@app.get("/transcription/locales")
async def get_transcription_locales(
    url: str = Query(...),
    cookies_file: str = Query(None, description="Optional path to cookies file for sites requiring authentication"),
    _: bool = Depends(verify_api_key)
):
    """Get available subtitle/caption locales for a video without downloading."""
    try:
        # Configure yt-dlp to extract subtitle information
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'skip_download': True,
            'quiet': True,
            'subtitleslangs': ['all'],  # Request all available languages
            'extractor_args': YTDLP_EXTRACTOR_ARGS,
        }

        # Add cookies file if provided (for sites like Patreon)
        if cookies_file and os.path.exists(cookies_file):
            ydl_opts['cookiefile'] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Get video metadata
            title = info.get("title", "Unknown")
            duration = info.get("duration", 0)
            
            # Extract subtitle information
            manual_subs = info.get('subtitles', {})
            auto_subs = info.get('automatic_captions', {})
            
            # Build locales list
            locales = []
            all_langs = set()
            
            # Process manual subtitles
            for lang_code, formats in manual_subs.items():
                all_langs.add(lang_code)
                # Get available formats for this language
                available_formats = list(set([f.get('ext') for f in formats if f.get('ext')]))
                
                locale = {
                    'code': lang_code,
                    'name': get_language_name(lang_code),
                    'type': ['manual'],
                    'formats': available_formats
                }
                locales.append(locale)
            
            # Process auto-generated subtitles
            for lang_code, formats in auto_subs.items():
                available_formats = list(set([f.get('ext') for f in formats if f.get('ext')]))
                
                if lang_code in all_langs:
                    # Language already exists with manual subs, add auto type
                    for locale in locales:
                        if locale['code'] == lang_code:
                            if 'auto' not in locale['type']:
                                locale['type'].append('auto')
                            # Merge formats
                            locale['formats'] = list(set(locale['formats'] + available_formats))
                            break
                else:
                    # New language with only auto subs
                    locale = {
                        'code': lang_code,
                        'name': get_language_name(lang_code),
                        'type': ['auto'],
                        'formats': available_formats
                    }
                    locales.append(locale)
                    all_langs.add(lang_code)
            
            # Sort locales by code for consistency
            locales.sort(key=lambda x: x['code'])
            
            # Calculate summary statistics
            manual_count = len([l for l in locales if 'manual' in l['type']])
            auto_count = len([l for l in locales if 'auto' in l['type']])
            
            return {
                'title': title,
                'duration': duration,
                'url': url,
                'locales': locales,
                'summary': {
                    'total': len(locales),
                    'manual_count': manual_count,
                    'auto_count': auto_count,
                    'has_manual': manual_count > 0,
                    'has_auto': auto_count > 0
                }
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting locales: {str(e)}")

@app.get("/playlist/info")
async def get_playlist_info(
    url: str = Query(...),
    dateafter: str = Query(None, description="Filter videos uploaded after this date (YYYYMMDD or relative like 'today-1week')"),
    datebefore: str = Query(None, description="Filter videos uploaded before this date"),
    max_items: int = Query(None, description="Maximum number of videos to return"),
    items: str = Query(None, description="Select specific videos by index (e.g., '1:5' for videos 1-5, '1,3,5' for specific videos)"),
    _: bool = Depends(verify_api_key)
):
    """Extract playlist metadata without downloading videos."""
    try:
        # Configure yt-dlp for playlist extraction
        ydl_opts = {
            'extract_flat': 'in_playlist',  # Extract playlist metadata without individual video details
            'quiet': True,
            'no_warnings': True,
            'extractor_args': YTDLP_EXTRACTOR_ARGS,
        }

        # Add date filters if provided
        if dateafter:
            ydl_opts['dateafter'] = dateafter
        if datebefore:
            ydl_opts['datebefore'] = datebefore
        
        # Add playlist item selection if provided
        if items:
            ydl_opts['playlist_items'] = items
        elif max_items:
            ydl_opts['playlist_items'] = f'1:{max_items}'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Check if it's actually a playlist
            if info.get('_type') != 'playlist':
                # Single video, wrap it as a playlist
                video_url = info.get('webpage_url') or url
                return {
                    'playlist_title': info.get('title', 'Single Video'),
                    'playlist_url': url,
                    'channel': info.get('uploader', 'Unknown'),
                    'channel_id': info.get('uploader_id'),
                    'channel_url': info.get('uploader_url'),
                    'video_count': 1,
                    'videos': [{
                        'url': video_url,
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration'),
                        'upload_date': info.get('upload_date'),
                        'index': 1,
                        'id': info.get('id')
                    }]
                }
            
            # Extract playlist metadata
            playlist_title = info.get('title', 'Unknown Playlist')
            playlist_url = info.get('webpage_url', url)
            channel = info.get('uploader', 'Unknown')
            channel_id = info.get('uploader_id')
            channel_url = info.get('uploader_url')
            
            # Process video entries
            entries = info.get('entries', [])
            videos = []
            
            for idx, entry in enumerate(entries, 1):
                if entry is None:  # Skip unavailable videos
                    continue
                    
                # Build video URL
                video_id = entry.get('id')
                video_url = entry.get('url') or entry.get('webpage_url')
                
                # If we only have ID, construct YouTube URL
                if not video_url and video_id:
                    video_url = f'https://www.youtube.com/watch?v={video_id}'
                
                # Format duration from seconds to MM:SS or HH:MM:SS
                duration_seconds = entry.get('duration')
                duration_str = None
                if duration_seconds:
                    hours = duration_seconds // 3600
                    minutes = (duration_seconds % 3600) // 60
                    seconds = duration_seconds % 60
                    if hours > 0:
                        duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
                    else:
                        duration_str = f"{minutes}:{seconds:02d}"
                
                # Format upload date
                upload_date = entry.get('upload_date')
                if upload_date and len(upload_date) == 8:
                    # Convert YYYYMMDD to YYYY-MM-DD
                    upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                
                video_info = {
                    'url': video_url,
                    'title': entry.get('title', 'Unknown'),
                    'duration': duration_str,
                    'duration_seconds': duration_seconds,
                    'upload_date': upload_date,
                    'index': idx,
                    'id': video_id
                }
                
                # Add additional metadata if available
                if entry.get('view_count'):
                    video_info['views'] = entry.get('view_count')
                if entry.get('description'):
                    video_info['description'] = entry.get('description')[:200] + '...' if len(entry.get('description', '')) > 200 else entry.get('description')
                
                videos.append(video_info)
            
            # Calculate total playlist count (might be different from filtered count)
            total_count = info.get('playlist_count') or len(entries)
            
            return {
                'playlist_title': playlist_title,
                'playlist_url': playlist_url,
                'channel': channel,
                'channel_id': channel_id,
                'channel_url': channel_url,
                'video_count': len(videos),
                'total_count': total_count,
                'videos': videos,
                'filters_applied': {
                    'dateafter': dateafter,
                    'datebefore': datebefore,
                    'max_items': max_items,
                    'items': items
                }
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting playlist info: {str(e)}")

@app.get("/downloads/list")
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

@app.post("/transcriptions/save")
async def save_transcription(
    request: TranscriptionSaveRequest = Body(...),
    _: bool = Depends(verify_api_key)
) -> TranscriptionSaveResponse:
    """
    Save transcription data to Supabase document_transcriptions table.

    This endpoint stores transcription data linked to an existing document.
    The document must already exist in the `documents` table.

    Required: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.

    Behavior:
    - Uses UPSERT: If transcription exists for document_id, it updates; otherwise inserts
    - Unique constraint: One transcription per document
    - Auto-updates `updated_at` timestamp on updates

    Example workflow:
    1. Create document record (done elsewhere in your system)
    2. GET /subtitles or POST /transcribe → get transcription data
    3. POST /transcriptions/save → store in document_transcriptions table
    """
    try:
        supabase = get_supabase_client()

        # Prepare data for upsert
        transcription_data = {
            "document_id": request.document_id,
            "segments": request.segments,  # JSONB field
            "language": request.language,
            "source": request.source,
            "confidence_score": request.confidence_score,
            "metadata": request.metadata or {}  # JSONB field, default to empty dict
        }

        # Upsert into document_transcriptions table
        # on_conflict uses the unique constraint on document_id
        result = supabase.table("document_transcriptions").upsert(
            transcription_data,
            on_conflict="document_id"
        ).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to save transcription to Supabase - no data returned"
            )

        saved_record = result.data[0]
        record_id = saved_record.get("id")
        created_at = saved_record.get("created_at")
        document_id = saved_record.get("document_id")

        return TranscriptionSaveResponse(
            id=record_id,
            document_id=document_id,
            created_at=created_at,
            message=f"Transcription saved successfully to Supabase with ID: {record_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error saving transcription to Supabase: {str(e)}"
        )

@app.get("/transcriptions/check/{document_id}")
async def check_transcription_exists(
    document_id: str,
    _: bool = Depends(verify_api_key)
):
    """
    Check if a transcription exists for a given document ID.

    Returns transcription status and basic metadata if it exists.

    Required: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.
    """
    try:
        supabase = get_supabase_client()

        # Query by document_id (which has unique constraint)
        result = supabase.table("document_transcriptions").select(
            "id, document_id, language, source, confidence_score, created_at, updated_at"
        ).eq("document_id", document_id).execute()

        if not result.data or len(result.data) == 0:
            return {
                "exists": False,
                "document_id": document_id,
                "transcription": None
            }

        transcription = result.data[0]
        return {
            "exists": True,
            "document_id": document_id,
            "transcription": {
                "id": transcription.get("id"),
                "language": transcription.get("language"),
                "source": transcription.get("source"),
                "confidence_score": transcription.get("confidence_score"),
                "created_at": transcription.get("created_at"),
                "updated_at": transcription.get("updated_at")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking transcription in Supabase: {str(e)}"
        )

@app.delete("/cache/cleanup")
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

@app.get("/cache")
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

@app.post("/admin/refresh-cookies")
async def admin_refresh_cookies(_: bool = Depends(verify_api_key)):
    """
    Manually trigger YouTube cookie refresh immediately.

    This endpoint allows manual triggering of the cookie refresh process
    that normally runs on a schedule (every YTDLP_COOKIE_REFRESH_DAYS days).

    Use cases:
    - Auth failures detected during video downloads
    - Proactive refresh before scheduled time
    - Testing cookie refresh setup

    Requirements:
    - YOUTUBE_EMAIL and YOUTUBE_PASSWORD environment variables must be set
    - Playwright and Chromium must be installed (playwright install chromium)

    Returns:
    - success: Boolean indicating if refresh succeeded
    - message/error: Status message
    - cookies_file: Path to cookies file (on success)
    - timestamp: ISO timestamp of refresh attempt
    """
    result = trigger_manual_refresh()
    if result["success"]:
        return JSONResponse(content=result, status_code=200)
    else:
        return JSONResponse(content=result, status_code=500)

@app.get("/admin/cookie-scheduler/status")
async def get_cookie_scheduler_status(_: bool = Depends(verify_api_key)):
    """
    Get current status of the cookie refresh scheduler.

    Returns information about:
    - Scheduler running state
    - Refresh interval (days)
    - Next scheduled refresh time
    - Last refresh timestamp and status
    - Credentials configuration status
    - Cookies file path and existence

    Useful for monitoring and debugging the automated cookie refresh system.
    """
    status = get_scheduler_status()
    return JSONResponse(content=status, status_code=200)

@app.get("/admin/transcription-worker/status")
async def get_transcription_worker_status(_: bool = Depends(verify_api_key)):
    """
    Get current status of the transcription worker.

    Returns information about:
    - Worker running state (enabled/disabled)
    - Job statistics (processed, failed, retried)
    - Last poll time and last job time
    - Recent errors (last 5)
    - Worker configuration (poll_interval, batch_size, etc.)

    Useful for monitoring background transcription processing.
    """
    try:
        from scripts.transcription_worker import get_worker_status
        status = get_worker_status()
        return JSONResponse(content=status, status_code=200)
    except ImportError:
        return JSONResponse(
            content={"running": False, "error": "Worker module not available"},
            status_code=200
        )

@app.post("/screenshot/video")
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

@app.get("/")
async def root():
    return {"message": "Welcome to the Social Media Video Downloader API. Use /download?url=<video_url>&format=<video_format> to download videos."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="::", port=8000)