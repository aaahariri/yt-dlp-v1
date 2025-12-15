"""
Subtitles router module.

This module provides endpoints for:
- Extracting subtitles/captions from videos
- Listing available subtitle languages for videos
"""

import os
import re
import yt_dlp
import requests
from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Dict, Any

from app.dependencies import verify_api_key
from app.config import YTDLP_EXTRACTOR_ARGS
from app.services.cache_service import cleanup_cache
from app.services.transcription_service import create_unified_transcription_response
from app.utils.platform_utils import get_platform_from_url, get_video_id_from_url
from app.utils.language_utils import get_language_name
from app.utils.subtitle_utils import parse_vtt_to_text, parse_srt_to_text
from app.utils.timestamp_utils import convert_srt_timestamp_to_seconds


router = APIRouter(tags=["Subtitles"])


@router.get("/subtitles")
async def get_subtitles(
    url: str = Query(..., description="Video URL to extract subtitles from"),
    lang: str = Query("en", description="Language code (e.g., 'en', 'es', 'fr')"),
    format: str = Query("text", description="Output format: text, json, srt, vtt"),
    auto: bool = Query(True, description="Include auto-generated captions"),
    cookies_file: str = Query(None, description="Optional path to cookies file for authentication"),
    _: bool = Depends(verify_api_key)
) -> Dict[str, Any]:
    """
    Extract subtitles/captions from a video URL.

    Args:
        url: Video URL to extract subtitles from
        lang: Language code (e.g., 'en', 'es', 'fr')
        format: Output format (text, json, srt, vtt)
        auto: Include auto-generated captions
        cookies_file: Optional path to cookies file for authentication

    Returns:
        Subtitle content in requested format with metadata

    Raises:
        HTTPException: 404 if no subtitles available, 500 on extraction error
    """
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


@router.get("/transcription/locales")
async def get_transcription_locales(
    url: str = Query(...),
    cookies_file: str = Query(None, description="Optional path to cookies file for sites requiring authentication"),
    _: bool = Depends(verify_api_key)
) -> Dict[str, Any]:
    """
    Get available subtitle/caption locales for a video without downloading.

    Args:
        url: Video URL to check for available subtitles
        cookies_file: Optional path to cookies file for authentication

    Returns:
        Dictionary containing:
        - title: Video title
        - duration: Video duration in seconds
        - url: Original URL
        - locales: List of available locales with codes, names, types, and formats
        - summary: Statistics about manual and auto-generated subtitles

    Raises:
        HTTPException: 500 on extraction error
    """
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
