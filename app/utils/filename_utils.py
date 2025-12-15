"""
Filename utility functions for sanitizing and formatting filenames.

This module provides utilities for:
- Sanitizing filenames to be filesystem-safe
- Detecting platform from URL and generating prefixes
- Formatting titles for filenames
- Creating formatted filenames with platform prefixes
- Encoding filenames for Content-Disposition headers
"""

import re
import unicodedata
from urllib.parse import quote


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
