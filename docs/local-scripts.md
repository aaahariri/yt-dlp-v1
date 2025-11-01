# Local Scripts Documentation

This document describes local utility scripts available in the repository for downloading and managing media files.

---

## Table of Contents

1. [Batch Download Script](#batch-download-script)
2. [Supported Platforms](#supported-platforms)
3. [File Format Handling](#file-format-handling)
4. [Usage Examples](#usage-examples)
5. [Customization](#customization)
6. [Troubleshooting](#troubleshooting)

---

## Batch Download Script

### Overview

**File:** `batch_download.py`

**Purpose:** Download multiple videos from supported platforms with automatic rate-limiting delays to prevent blocks/bans.

**Current Configuration:**
- **Platform**: YouTube (default configuration)
- **Can be adapted for**: TikTok, Instagram, Facebook, Twitter, Vimeo, and 1000+ other platforms supported by yt-dlp

### Key Features

✅ **Batch downloading** - Process multiple videos in one run
✅ **Rate limiting protection** - Random 20-30 second pauses between downloads
✅ **Auto-skip duplicates** - Skips already downloaded files
✅ **Progress tracking** - Real-time download progress with ETA
✅ **Error handling** - Continues on errors, reports failures at end
✅ **Formatted filenames** - Consistent naming with platform prefixes
✅ **Smart truncation** - Removes channel names, limits to 50 chars

---

## Supported Platforms

### Current Implementation

**Default Platform:** YouTube only (hardcoded)

The script is currently configured with:
- Platform prefix: `YT-`
- YouTube-specific URL list
- Optimized for YouTube rate limits

### Can Be Adapted For

Since the script uses `yt-dlp` under the hood, it supports **1000+ platforms** including:

| Platform | Status | Prefix | Notes |
|----------|--------|--------|-------|
| **YouTube** | ✅ Default | `YT` | Current implementation |
| **TikTok** | ⚙️ Adaptable | `TT` | Requires URL list change |
| **Instagram** | ⚙️ Adaptable | `IG` | Requires URL list change |
| **Facebook** | ⚙️ Adaptable | `FB` | Requires URL list change |
| **Twitter/X** | ⚙️ Adaptable | `X` | Requires URL list change |
| **Vimeo** | ⚙️ Adaptable | `VM` | Requires URL list change |
| **DailyMotion** | ⚙️ Adaptable | `DM` | Requires URL list change |
| **Twitch** | ⚙️ Adaptable | `TW` | Requires URL list change |

> **Note:** To use with other platforms, you must modify the script (see [Adapting for Other Platforms](#adapting-for-other-platforms))

**Full platform list:** [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

---

## File Format Handling

### Output Format

**Default:** MP4 (720p or best available)

The script uses:
```python
'format': 'best[height<=720]',  # 720p or lower
'merge_output_format': 'mp4',   # Force MP4 output
```

### Why MP4?

- ✅ Universal compatibility (all devices/browsers)
- ✅ Good compression ratio
- ✅ Supported by all video players
- ✅ Ideal for archiving and sharing

### File Naming Convention

**Pattern:** `{PLATFORM}-{formatted-title}.{ext}`

**Examples:**
```
YT-Liquidity-Inducement-Masterclass-Ep.-1.mp4
TT-Viral-Dance-Trend-2024.mp4
IG-Behind-The-Scenes-Photoshoot.mp4
```

**Rules:**
- Platform prefix (2-6 chars) + hyphen
- Title max 50 characters
- Spaces replaced with hyphens
- Channel names removed (text after `|` or `-`)
- Extension automatically determined by yt-dlp

### Other Supported Formats

While the script defaults to MP4, yt-dlp supports many formats. You can modify the script to download:

| Format | Extension | Use Case |
|--------|-----------|----------|
| MP4 | `.mp4` | **Default** - Universal video |
| WebM | `.webm` | Web-optimized video |
| MKV | `.mkv` | High-quality archiving |
| M4A | `.m4a` | Audio only |
| MP3 | `.mp3` | Audio only (requires ffmpeg) |
| WAV | `.wav` | Uncompressed audio |

To change format, modify line 139-143 in `batch_download.py`:

```python
# For audio only (podcast/music)
'format': 'bestaudio',
'merge_output_format': 'm4a',

# For highest quality video
'format': 'bestvideo+bestaudio',
'merge_output_format': 'mkv',
```

---

## Usage Examples

### Basic Usage (YouTube)

#### 1. **Edit the URL List**

Open `batch_download.py` and modify the `YOUTUBE_URLS` list (lines 19-43):

```python
# YouTube URLs to download
YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=VIDEO_ID_1",
    "https://youtu.be/VIDEO_ID_2",
    "https://www.youtube.com/watch?v=VIDEO_ID_3",
    # Add more URLs here...
]
```

#### 2. **Run the Script**

```bash
# Make executable (first time only)
chmod +x batch_download.py

# Run
python3 batch_download.py
```

#### 3. **Monitor Progress**

The script will show:
- Current video being processed (X/Y)
- Download progress with ETA
- Pause countdown between downloads
- Success/failure status for each video

#### 4. **Check Downloaded Files**

```bash
# List all downloaded videos
ls -lh YT-*.mp4

# Count total downloads
ls -1 YT-*.mp4 | wc -l

# See file sizes
du -sh YT-*.mp4
```

### Advanced Usage

#### Custom Download Directory

Modify line 45 in `batch_download.py`:

```python
DOWNLOADS_DIR = "./my-custom-folder"  # Change to your preferred path
```

#### Adjust Pause Times

Modify lines 46-47 to change rate-limiting delays:

```python
MIN_PAUSE = 10  # Minimum seconds between downloads
MAX_PAUSE = 20  # Maximum seconds between downloads
```

> ⚠️ **Warning:** Shorter pauses increase risk of being rate-limited or banned by the platform.

#### Higher Quality Downloads

Change line 139 for better quality:

```python
# 1080p or best available
'format': 'best[height<=1080]',

# Highest quality (any resolution)
'format': 'best',

# 4K if available
'format': 'best[height<=2160]',
```

#### Audio-Only Downloads

For podcasts or music:

```python
ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': output_path,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}
```

---

## Customization

### Adapting for Other Platforms

To use with TikTok, Instagram, or other platforms:

#### 1. **Change URL List Variable Name** (Line 18-19)

```python
# Before:
YOUTUBE_URLS = [...]

# After:
TIKTOK_URLS = [
    "https://www.tiktok.com/@user/video/123456789",
    "https://www.tiktok.com/@user/video/987654321",
]
```

#### 2. **Update Platform Prefix** (Line 126)

```python
# Before:
filename = f"YT-{formatted_title}.%(ext)s"

# After (for TikTok):
filename = f"TT-{formatted_title}.%(ext)s"

# Or detect automatically:
prefix = "TT" if "tiktok.com" in url else "YT"
filename = f"{prefix}-{formatted_title}.%(ext)s"
```

#### 3. **Adjust Rate Limiting** (Lines 46-47)

Different platforms have different rate limits:

```python
# YouTube (default)
MIN_PAUSE = 20
MAX_PAUSE = 30

# TikTok (more aggressive)
MIN_PAUSE = 30
MAX_PAUSE = 60

# Instagram (very aggressive)
MIN_PAUSE = 60
MAX_PAUSE = 120
```

#### 4. **Update Main Loop** (Line 159)

```python
# Before:
for i, url in enumerate(YOUTUBE_URLS, 1):

# After:
for i, url in enumerate(TIKTOK_URLS, 1):
```

### Multi-Platform Script

For downloading from multiple platforms in one script:

```python
# Define URLs by platform
URLS = {
    'youtube': [
        "https://www.youtube.com/watch?v=...",
        "https://youtu.be/...",
    ],
    'tiktok': [
        "https://www.tiktok.com/@user/video/...",
    ],
    'instagram': [
        "https://www.instagram.com/p/...",
    ]
}

# Detect platform and set prefix
def get_platform(url):
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'YT'
    elif 'tiktok.com' in url:
        return 'TT'
    elif 'instagram.com' in url:
        return 'IG'
    return 'VIDEO'

# Use in download function
prefix = get_platform(url)
filename = f"{prefix}-{formatted_title}.%(ext)s"
```

---

## Troubleshooting

### Common Issues

#### 1. **"yt-dlp not found" Error**

**Solution:**
```bash
pip3 install --upgrade yt-dlp
```

#### 2. **"Deno not found" Warning (YouTube)**

For YouTube videos, Deno may be required:

```bash
# macOS/Linux
curl -fsSL https://deno.land/install.sh | sh

# Verify
deno --version
```

See: [Deno Setup Guide](./deno-setup.md)

#### 3. **"429 Too Many Requests" Error**

**Cause:** Rate limiting by the platform

**Solution:**
- Increase `MIN_PAUSE` and `MAX_PAUSE` values
- Wait 10-15 minutes before retrying
- Use cookies from logged-in browser session

#### 4. **Downloaded File Names Show "YT-" for Non-YouTube Videos**

**Cause:** Platform prefix is hardcoded to "YT"

**Solution:** Modify line 126 to detect platform dynamically (see [Adapting for Other Platforms](#adapting-for-other-platforms))

#### 5. **Files Download in WebM Instead of MP4**

**Cause:** Platform doesn't have MP4 format available

**Solution:**
- yt-dlp will automatically merge to MP4 if `ffmpeg` is installed
- Install ffmpeg: `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Linux)

#### 6. **"File already exists, skipping" But File Not Found**

**Cause:** File check looks for MP4 but actual file might have different extension

**Solution:** Check actual file extension:
```bash
ls -1 | grep "filename-prefix"
```

Then update the check on line 132 to match actual extension.

---

## URL List Management

### Where to Add URLs

**Location:** Lines 19-43 in `batch_download.py`

```python
YOUTUBE_URLS = [
    "URL_1_HERE",
    "URL_2_HERE",
    "URL_3_HERE",
    # Add more URLs below...
    "YOUR_NEW_URL_HERE",
]
```

### URL Formats Supported

All URL formats supported by yt-dlp work:

**YouTube:**
```python
"https://www.youtube.com/watch?v=VIDEO_ID"
"https://youtu.be/VIDEO_ID"
"https://www.youtube.com/watch?v=VIDEO_ID&list=PLAYLIST_ID&index=1"
"https://m.youtube.com/watch?v=VIDEO_ID"
```

**TikTok:**
```python
"https://www.tiktok.com/@username/video/1234567890"
"https://vm.tiktok.com/SHORT_CODE/"
```

**Instagram:**
```python
"https://www.instagram.com/p/POST_ID/"
"https://www.instagram.com/reel/REEL_ID/"
"https://www.instagram.com/tv/TV_ID/"
```

**Twitter/X:**
```python
"https://twitter.com/user/status/1234567890"
"https://x.com/user/status/1234567890"
```

### Loading URLs from File

For very large lists, load from external file:

```python
# Read URLs from text file (one per line)
with open('urls.txt', 'r') as f:
    YOUTUBE_URLS = [line.strip() for line in f if line.strip()]
```

Create `urls.txt`:
```
https://www.youtube.com/watch?v=VIDEO_1
https://www.youtube.com/watch?v=VIDEO_2
https://www.youtube.com/watch?v=VIDEO_3
```

---

## Best Practices

### 1. **Test with Small Batches First**

Start with 2-3 URLs to ensure everything works:
```python
YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=test1",
    "https://www.youtube.com/watch?v=test2",
]
```

### 2. **Monitor First Few Downloads**

Watch the output for the first 2-3 videos to catch any errors early.

### 3. **Backup URL Lists**

Keep your URL list in a separate file:
```bash
cp batch_download.py batch_download_backup.py
```

### 4. **Use Appropriate Pauses**

| Platform | Recommended Min | Recommended Max |
|----------|----------------|-----------------|
| YouTube | 20s | 30s |
| TikTok | 30s | 60s |
| Instagram | 60s | 120s |
| Twitter/X | 15s | 25s |

### 5. **Check Disk Space**

Videos can be large. Check available space:
```bash
df -h .
```

### 6. **Run in Screen/Tmux for Long Sessions**

For 50+ videos, use screen/tmux to prevent interruption:
```bash
screen -S download
python3 batch_download.py
# Ctrl+A, D to detach
# screen -r download to reattach
```

---

## Performance Tips

### Faster Downloads

1. **Use wired connection** instead of WiFi
2. **Close bandwidth-heavy apps** during download
3. **Lower quality** if speed is more important than quality:
   ```python
   'format': 'best[height<=480]',  # 480p for faster downloads
   ```

### Reduce Bandwidth Usage

```python
# Download audio only (much smaller)
'format': 'bestaudio',
'merge_output_format': 'm4a',
```

---

## Limitations

### Current Limitations

1. **Single platform per run** - Script must be modified for mixed platforms
2. **Hardcoded YouTube prefix** - Shows "YT-" for all videos
3. **No playlist support** - Must extract individual URLs manually
4. **No resume capability** - Failed downloads must be restarted
5. **Sequential only** - Cannot download multiple videos in parallel

### Future Enhancements

Possible improvements:
- [ ] Auto-detect platform from URL
- [ ] Support for playlist URLs (download all videos in playlist)
- [ ] Resume failed downloads
- [ ] Parallel downloads (with rate limiting)
- [ ] Interactive mode (choose URLs from menu)
- [ ] Download metadata (thumbnails, descriptions, subtitles)

---

## Related Documentation

- [API Endpoints Usage](./endpoints-usage.md)
- [Deno Setup Guide](./deno-setup.md)
- [Unicode Handling](./unicode-handling.md)
- [Main README](../README.md)

---

## Support

For issues or questions:
1. Check [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp)
2. Review [troubleshooting section](#troubleshooting) above
3. Check GitHub issues: [yt-dlp/yt-dlp/issues](https://github.com/yt-dlp/yt-dlp/issues)

---

**Last Updated:** 2025-11-01
**Script Version:** 1.0.0
**Compatible with:** yt-dlp 2025.10.14+
