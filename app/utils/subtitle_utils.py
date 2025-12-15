"""Subtitle parsing utilities for VTT and SRT formats."""

import re


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
