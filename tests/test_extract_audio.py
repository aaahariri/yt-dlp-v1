#!/usr/bin/env python3
"""Test the /extract-audio endpoint"""
import requests
import json
import sys

# API configuration
BASE_URL = "http://localhost:8000"
API_KEY = "a23633cf237fea25b5ca0297e3219ae6b987d678d56b047cf36385c8a50e8b66"

# Test URL - a very short YouTube video
VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

headers = {
    "X-Api-Key": API_KEY
}

params = {
    "url": VIDEO_URL,
    "output_format": "mp3"
}

print(f"Testing POST {BASE_URL}/extract-audio")
print(f"URL: {VIDEO_URL}")
print("Waiting for response (this may take a minute)...")
print()

try:
    response = requests.post(
        f"{BASE_URL}/extract-audio",
        params=params,
        headers=headers,
        timeout=180  # 3 minute timeout
    )

    print(f"Status Code: {response.status_code}")
    print()

    if response.status_code == 200:
        data = response.json()
        print("SUCCESS!")
        print()
        print("Response JSON:")
        print(json.dumps(data, indent=2))
        print()

        # Check cache path
        audio_file = data.get("audio_file", "")
        if "./cache/audio/" in audio_file or "cache/audio" in audio_file:
            print("✓ Audio file is in correct cache location: ./cache/audio/")
        else:
            print(f"✗ Audio file is NOT in cache location: {audio_file}")

        print()
        print(f"File size: {data.get('size', 0):,} bytes")

    else:
        print(f"ERROR: {response.status_code}")
        print(response.text)

except requests.exceptions.Timeout:
    print("ERROR: Request timed out after 3 minutes")
    sys.exit(1)
except requests.exceptions.ConnectionError:
    print("ERROR: Could not connect to server. Is it running?")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {str(e)}")
    sys.exit(1)
