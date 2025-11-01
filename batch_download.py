#!/usr/bin/env python3
"""
Batch YouTube Video Downloader with Random Pauses
Downloads multiple YouTube videos with random delays to avoid rate limiting.
"""

import os
import sys
import time
import random
import re
import yt_dlp
from datetime import datetime

# Set PATH to include Deno
os.environ['PATH'] = os.path.expanduser('~/.deno/bin') + ':' + os.environ.get('PATH', '')

# YouTube URLs to download
YOUTUBE_URLS = [
    "https://youtu.be/htyknOTK-xs?si=0LO67FbhZW60Ydrl",
    "https://youtu.be/C33zPmKWQqY?si=4ejCsyuSVeNXR-3K",
    "https://youtu.be/8r7k4GyHjgU?si=6VdCWXn2Ensl7p91",
    "https://youtu.be/aJL__4IDzC4?si=GqBapb3HjuDmVins",
    "https://youtu.be/MObFIEX6hXs?si=qB4Twz94-oZvIbr3",
    "https://youtu.be/Q-jQGto-nic?si=ZZDFGzhLwgdX9s52",
    "https://youtu.be/FUC0iWyCI08?si=q_MYdLoyHEHlgcQL",
    "https://youtu.be/7teuvsTglnQ?si=b_mztNG68tUXLJlY",
    "https://youtu.be/nwWn85GuiR8?si=rPMK_R8HJ1kKXiMs",
    "https://youtu.be/76Oh3eBJ9Tg?si=N2QKmnry_FLO2bvB",
    "https://youtu.be/WmFD6lkGMVU?si=Ds1srg2Rpp5twv5u",
    "https://youtu.be/tTAu-2703uo?si=CKUqBtAyRAnyEZWj",
    "https://youtu.be/jGAS_1bOevA?si=hmSRA74qSHTsC9vk",
    "https://youtu.be/-mX823uc5-s?si=bNGMh5A5ByiI40YG",
    "https://youtu.be/GnQvLr6A558?si=lSc-Rvqy6oxHj4ib",
    "https://youtu.be/d_rkvsi47qo?si=IU6JkJQ9kyAm_yCW",
    "https://youtu.be/MmakHkCJdYA?si=FTZJS2U97LyA6PSz",
    "https://www.youtube.com/watch?v=666K9xmmK0c&list=PLfTWH4DecAh0piINIs_IrwSSftPvm-8lo&index=26",
    "https://youtu.be/baiBs8uy6RI?si=CHepu3mKoHR_V8_a",
    "https://youtu.be/JO2GBUNF3f8?si=-o1_uwMM5-szlMo5",
    "https://youtu.be/33ZJCHwd9KI?si=NEaslsJ9rE0VO7fi",
    "https://youtu.be/po3MlSGt5CY?si=AOIGRh2UrRFdV8hu",
    "https://youtu.be/e_FV0Q14k8E?si=6jkeD3a8qUlp1bQq",
]

DOWNLOADS_DIR = "./downloads"
MIN_PAUSE = 20  # seconds
MAX_PAUSE = 30  # seconds


def format_title_for_filename(title: str, max_length: int = 50) -> str:
    """Format title for filename: truncate, replace spaces with hyphens, remove special chars."""
    # Remove channel name suffix (everything after | or -)
    # Common patterns: "Video Title | Channel Name" or "Video Title - Channel Name"
    if '|' in title:
        title = title.split('|')[0].strip()
    elif ' - ' in title and len(title.split(' - ')[-1]) < 30:
        # Only split on " - " if the last part looks like a channel name (short)
        parts = title.split(' - ')
        if len(parts) > 1:
            # Check if last part might be a channel name (no common title words)
            last_part = parts[-1].lower()
            if not any(word in last_part for word in ['ep', 'part', 'tutorial', 'guide', 'how']):
                title = ' - '.join(parts[:-1]).strip()

    # Sanitize
    title = title.replace('/', '-').replace('\\', '-')
    title = title.replace(':', '-').replace('*', '-')
    title = title.replace('?', '-').replace('"', '-')
    title = title.replace('<', '-').replace('>', '-')
    title = title.replace('|', '-').replace('\0', '-')
    title = title.strip('. ')

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
        if last_hyphen > max_length // 2:
            title = truncated[:last_hyphen]
        else:
            title = truncated

    return title or 'video'


def download_video(url: str, index: int, total: int) -> bool:
    """Download a single YouTube video with formatted filename."""
    print(f"\n{'='*80}")
    print(f"[{index}/{total}] Processing: {url}")
    print(f"{'='*80}")

    try:
        # Create downloads directory if it doesn't exist
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)

        # First, extract video info
        meta_opts = {
            'quiet': True,
            'skip_download': True,
            'no_warnings': False,
        }

        print("📋 Extracting video metadata...")
        with yt_dlp.YoutubeDL(meta_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "video")
            duration = info.get("duration", 0)

        print(f"📺 Title: {title}")
        print(f"⏱️  Duration: {duration}s ({duration//60}m {duration%60}s)")

        # Format filename
        formatted_title = format_title_for_filename(title)
        filename = f"YT-{formatted_title}.%(ext)s"
        output_path = os.path.join(DOWNLOADS_DIR, filename)

        print(f"💾 Filename: YT-{formatted_title}.mp4")

        # Check if file already exists
        expected_file = os.path.join(DOWNLOADS_DIR, f"YT-{formatted_title}.mp4")
        if os.path.exists(expected_file):
            print(f"⏭️  File already exists, skipping download")
            return True

        # Download the video
        ydl_opts = {
            'format': 'best[height<=720]',  # 720p or lower
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'merge_output_format': 'mp4',
        }

        print("⬇️  Downloading...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        print(f"✅ Successfully downloaded!")
        return True

    except Exception as e:
        print(f"❌ Error downloading video: {e}")
        return False


def main():
    """Main function to download all videos with random pauses."""
    print(f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                  YouTube Batch Downloader with Random Pauses               ║
╚════════════════════════════════════════════════════════════════════════════╝

📁 Download directory: {DOWNLOADS_DIR}
🎬 Total videos: {len(YOUTUBE_URLS)}
⏸️  Pause between downloads: {MIN_PAUSE}-{MAX_PAUSE} seconds
🚀 Starting download process...
""")

    start_time = time.time()
    successful = 0
    failed = 0
    skipped = 0

    for i, url in enumerate(YOUTUBE_URLS, 1):
        result = download_video(url, i, len(YOUTUBE_URLS))

        if result:
            successful += 1
        else:
            failed += 1

        # Add random pause between downloads (except after last video)
        if i < len(YOUTUBE_URLS):
            pause_duration = random.randint(MIN_PAUSE, MAX_PAUSE)
            print(f"\n⏸️  Pausing for {pause_duration} seconds to avoid rate limiting...")

            # Show countdown
            for remaining in range(pause_duration, 0, -1):
                print(f"   ⏳ {remaining}s remaining...", end='\r')
                time.sleep(1)
            print(" " * 50, end='\r')  # Clear countdown line

    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)

    print(f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                           Download Complete!                                ║
╚════════════════════════════════════════════════════════════════════════════╝

📊 Summary:
   ✅ Successful: {successful}
   ❌ Failed: {failed}
   ⏭️  Skipped: {skipped}
   ⏱️  Total time: {minutes}m {seconds}s

📁 Files saved to: {os.path.abspath(DOWNLOADS_DIR)}
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user. Exiting...")
        sys.exit(1)
