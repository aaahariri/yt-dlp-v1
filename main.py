import os
import re
import time
import uuid
import json
import hashlib
import requests
import unicodedata
import asyncio
from urllib.parse import quote
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException, Depends, Header, Body
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import yt_dlp
from dotenv import load_dotenv

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

# Ensure transcriptions directory exists
TRANSCRIPTIONS_DIR = os.getenv("TRANSCRIPTIONS_DIR", "./transcriptions")
os.makedirs(TRANSCRIPTIONS_DIR, exist_ok=True)

# Concurrency control for transcription endpoints
# This prevents memory overload when multiple transcription requests arrive
# Set via environment variable or use default based on common model sizes
MAX_CONCURRENT_TRANSCRIPTIONS = int(os.getenv("MAX_CONCURRENT_TRANSCRIPTIONS", "2"))
transcription_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSCRIPTIONS)

print(f"INFO: Max concurrent transcriptions set to: {MAX_CONCURRENT_TRANSCRIPTIONS}")

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
        meta_opts = {'quiet': True, 'skip_download': True}

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
            meta_opts = {'quiet': True, 'skip_download': True}
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
        cleanup_old_transcriptions()
        
        # Configure yt-dlp for subtitle extraction
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': auto,
            'skip_download': True,
            'quiet': True,
            'subtitleslangs': [lang],
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
                                start_time = time_match.group(1)
                                end_time = time_match.group(2)
                                text_line = lines[i + 1].strip()
                                if text_line and not text_line.startswith('<'):
                                    segments.append({
                                        "start": start_time,
                                        "end": end_time,
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
                                start_time = time_match.group(1)
                                end_time = time_match.group(2)
                                text = ' '.join(lines[2:]).strip()
                                text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
                                if text:
                                    segments.append({
                                        "start": start_time,
                                        "end": end_time,
                                        "text": text
                                    })
                
                full_text = ' '.join([seg['text'] for seg in segments])
                
                return {
                    "title": title,
                    "duration": duration,
                    "language": lang,
                    "source_format": subtitle_format,
                    "segments": segments,
                    "full_text": full_text,
                    "word_count": len(full_text.split()),
                    "segment_count": len(segments)
                }
            
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
    Audio files are stored in /tmp/ and automatically cleaned up after 1 hour.

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
        cleanup_old_transcriptions()

        # Generate unique ID for audio file
        audio_uid = uuid.uuid4().hex[:8]
        audio_path = f"/tmp/{audio_uid}.{output_format}"

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

            # Get metadata
            try:
                meta_opts = {'quiet': True, 'skip_download': True}
                if cookies_file and os.path.exists(cookies_file):
                    meta_opts['cookiefile'] = cookies_file

                with yt_dlp.YoutubeDL(meta_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get("title", "Unknown")
            except Exception:
                title = "Unknown"

            # Extract audio using yt-dlp
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

            try:
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
            for f in os.listdir("/tmp"):
                if f.startswith(audio_uid):
                    actual_audio_path = os.path.join("/tmp", f)
                    break

        if not actual_audio_path or not os.path.exists(actual_audio_path):
            raise HTTPException(
                status_code=500,
                detail="Audio extraction completed but file not found"
            )

        # Get file info
        file_size = os.path.getsize(actual_audio_path)

        return {
            "audio_file": actual_audio_path,
            "format": output_format,
            "size": file_size,
            "title": title,
            "source_type": source_type,
            "message": "Audio extracted successfully. Use this audio_file path with POST /transcribe",
            "expires_in": "1 hour (automatic cleanup)"
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
    _: bool = Depends(verify_api_key)
):
    """
    Transcribe audio file using AI.

    Providers:
    - local: whisperX (70x real-time on GPU, 3-5x on CPU, $0 cost, word-level timestamps)
    - openai: OpenAI Whisper API ($0.006/min, managed service)

    Input: audio_file path (from /extract-audio endpoint)
    Output: Transcription in specified format

    Workflow:
    1. POST /extract-audio → get audio_file path
    2. POST /transcribe → get transcription

    Note: This endpoint is limited to MAX_CONCURRENT_TRANSCRIPTIONS concurrent requests
    to prevent memory overload. Additional requests will wait in queue.
    """
    # Acquire semaphore to limit concurrent transcriptions
    async with transcription_semaphore:
        return await _transcribe_audio_internal(
            audio_file, language, model_size, provider, output_format
        )


async def _transcribe_audio_internal(
    audio_file: str,
    language: str,
    model_size: str,
    provider: str,
    output_format: str
):
    """Internal transcription logic (separated for semaphore control)."""
    try:
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
        duration = 0  # We don't have duration without re-processing

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

            # Determine device and compute type with fallback strategy
            device = "cpu"
            compute_type = "int8"
            attempted_device = "cpu"

            try:
                if torch.cuda.is_available():
                    device = "cuda"
                    compute_type = "float16"
                    attempted_device = "cuda"
                elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    device = "mps"
                    compute_type = "float16"
                    attempted_device = "mps"
            except Exception:
                pass

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
                        print(f"Warning: {attempted_device.upper()} failed ({model_load_error}), fell back to CPU")
                    except Exception as cpu_error:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Local provider error: Failed to load model '{model_size}' on {attempted_device.upper()} ({model_load_error}) and CPU ({str(cpu_error)})"
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
            full_text = ' '.join([s['text'].strip() for s in segments])
            return {
                "title": title,
                "language": detected_language,
                "model": model_size if provider == "local" else "whisper-1",
                "provider": provider,
                "segments": segments,
                "full_text": full_text,
                "word_count": len(full_text.split()),
                "segment_count": len(segments),
                "transcription_time": round(transcribe_duration, 2)
            }

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

@app.get("/")
async def root():
    return {"message": "Welcome to the Social Media Video Downloader API. Use /download?url=<video_url>&format=<video_format> to download videos."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="::", port=8000)