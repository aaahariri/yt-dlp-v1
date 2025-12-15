#!/usr/bin/env python3
"""Wrapper to test YouTube cookie refresh with .env credentials"""
from dotenv import load_dotenv
import subprocess
import sys

# Load .env file
load_dotenv()

# Run the actual script with all args passed through
result = subprocess.run([
    sys.executable,
    'scripts/refresh_youtube_cookies.py',
    '--interactive',
    '--output',
    './cookies.txt'
])

sys.exit(result.returncode)
