"""
Timestamp utility functions for parsing and formatting timestamps.

This module provides utilities for:
- Parsing various timestamp formats to seconds
- Converting seconds to SRT timestamp format
- Converting SRT/VTT timestamps to seconds
"""


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
