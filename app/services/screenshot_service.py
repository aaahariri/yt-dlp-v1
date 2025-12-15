"""
Screenshot extraction service for video frames.

This module handles screenshot extraction from video files using FFmpeg,
including frame capture, quality control, and metadata extraction.
"""

import os
import json
import subprocess
from typing import Dict


def extract_screenshot(video_path: str, timestamp_seconds: float, output_path: str, quality: int = 2) -> dict:
    """
    Extract single frame from video using FFmpeg.
    Returns metadata dict or raises exception.

    Args:
        video_path: Path to the video file
        timestamp_seconds: Timestamp to extract (in seconds)
        output_path: Path where screenshot should be saved
        quality: JPEG quality (1-31, lower=better, default=2)

    Returns:
        Dictionary with file_path, size_bytes, width, height

    Raises:
        Exception: If FFmpeg extraction fails or output file not created
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
