import os
import re
import time
import uuid
import json
import hashlib
import requests
import unicodedata
from urllib.parse import quote
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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
    """Extract platform prefix from URL."""
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

def format_title_for_filename(title: str, max_length: int = 60) -> str:
    """Format title for filename: truncate, replace spaces with hyphens, remove special chars."""
    # First sanitize to remove problematic characters
    title = sanitize_filename(title)

    # Replace multiple spaces with single space
    title = re.sub(r'\s+', ' ', title)

    # Replace spaces with hyphens
    title = title.replace(' ', '-')

    # Replace multiple consecutive hyphens with single hyphen
    title = re.sub(r'-+', '-', title)

    # Remove leading/trailing hyphens
    title = title.strip('-')

    # Truncate to max_length
    if len(title) > max_length:
        # Try to truncate at last hyphen before max_length
        truncated = title[:max_length]
        last_hyphen = truncated.rfind('-')
        if last_hyphen > max_length // 2:  # Only use hyphen if it's past halfway point
            title = truncated[:last_hyphen]
        else:
            title = truncated

    return title or 'video'

def create_formatted_filename(url: str, title: str, extension: str = 'mp4', custom_title: str = None) -> str:
    """Create formatted filename with platform prefix and formatted title."""
    if custom_title:
        # Use custom title if provided
        formatted_title = format_title_for_filename(custom_title)
        platform_prefix = get_platform_prefix(url)
        return f"{platform_prefix}-{formatted_title}.{extension}"
    else:
        # Use extracted title with platform prefix
        formatted_title = format_title_for_filename(title)
        platform_prefix = get_platform_prefix(url)
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

@app.get("/transcription")
async def get_transcription(
    url: str = Query(...),
    lang: str = Query("en"),
    format: str = Query("text"),  # text, json, srt, vtt, segments
    auto: bool = Query(True),
    cookies_file: str = Query(None, description="Optional path to cookies file for sites requiring authentication"),
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
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": f"No subtitles found for language '{lang}'", 
                        "available_languages": all_available_langs,
                        "title": title,
                        "duration": duration
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
        raise HTTPException(status_code=500, detail=f"Error extracting transcription: {str(e)}")

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