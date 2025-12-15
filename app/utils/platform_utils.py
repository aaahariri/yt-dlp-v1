"""
Platform utility functions for detecting and parsing video URLs.

This module provides utilities for:
- Detecting platform from URL
- Extracting video IDs from URLs
- Checking if URLs are from specific platforms
"""

import re
import hashlib


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube URL."""
    youtube_patterns = [
        r'youtube\.com',
        r'youtu\.be',
        r'youtube-nocookie\.com',
    ]
    return any(re.search(pattern, url, re.IGNORECASE) for pattern in youtube_patterns)


def get_video_id_from_url(url: str) -> str:
    """Extract a consistent ID from video URL for caching."""
    # Create a hash of the URL for consistent file naming
    return hashlib.md5(url.encode()).hexdigest()[:12]


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
