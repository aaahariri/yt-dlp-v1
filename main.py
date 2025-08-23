import os
import re
import time
import uuid
import json
import hashlib
import requests
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

@app.get("/download")
async def download_video(
    url: str = Query(...), 
    format: str = Query("best"), 
    keep: bool = Query(False),
    _: bool = Depends(verify_api_key)
):
    try:
        # Extract metadata
        with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "video").replace("/", "-").replace("\\", "-")
            extension = "mp4"  # fallback extension
            filename = f"{title}.{extension}"

        # Create output template based on keep parameter
        if keep:
            # Save to downloads directory with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title.replace(' ', '_')
            saved_filename = f"{safe_title}_{timestamp}.%(ext)s"
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

        # Download the video using yt-dlp Python API
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.download([url])

        # Find actual downloaded file
        actual_file_path = None
        if keep:
            # Look in downloads directory
            for f in os.listdir(DOWNLOADS_DIR):
                if timestamp in f and safe_title in f:
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
        response_headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
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
    uvicorn.run(app, host="0.0.0.0", port=8000)