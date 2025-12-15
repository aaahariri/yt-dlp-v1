<!--
===========================================
  IMPLEMENTATION STATUS: COMPLETED
  Completed Date: 2025-12-14

  Summary:
  - All 11 implementation steps completed
  - main.py updated with screenshot extraction
  - Unified cache system implemented
  - Documentation updated
  - Syntax validation passed

  Manual Task Remaining:
  - Run SQL migration in Supabase (see Supabase Migration section)
===========================================
-->

# Video Screenshot Extraction Feature - Implementation Plan

## Overview

Add a `/screenshot/video` endpoint to extract frames from videos at specified timestamps, with a **unified cache system** for all temporary files (videos, audio, transcriptions, screenshots) and optional Supabase storage integration.

---

## User Requirements Summary

1. **New endpoint `/screenshot/video`** - Extract screenshots from video at specified timestamps
2. **Unified cache system** - Single `./cache/` directory for all temporary files
3. **Video reuse** - Cache downloaded videos so subsequent screenshot requests skip re-download
4. **Simple cleanup** - mtime-based expiration with single TTL, triggered on requests + optional cron
5. **Supabase integration** - Optional upload to `public_media` bucket and table

### Design Decisions:
- **Cache key**: `video_id` (no datetime in filename - use mtime for age)
- **Lookup**: Filename pattern matching + mtime check
- **TTL**: Single `CACHE_TTL_HOURS` for all temp files (default: 3 hours)
- **Cleanup trigger**: On each transcription request + optional cron endpoint
- **No registry file**: Filesystem is the database

---

## Unified Cache Architecture

```
./cache/
├── videos/                        # Downloaded videos for processing
│   └── YT-dQw4w9WgXcQ.mp4        # {platform}-{video_id}.{ext}
├── audio/                         # Extracted audio files
│   └── dQw4w9WgXcQ.mp3           # {video_id}.{ext}
├── transcriptions/                # Transcription outputs
│   └── dQw4w9WgXcQ-en.json       # {video_id}-{lang}.json
└── screenshots/                   # Extracted screenshots
    └── dQw4w9WgXcQ-90500.jpg     # {video_id}-{timestamp_ms}.jpg
```

| Subdirectory | Purpose | Filename Format |
|--------------|---------|-----------------|
| `videos/` | Cached videos for screenshot extraction | `{platform}-{video_id}.{ext}` |
| `audio/` | Extracted audio for transcription | `{video_id}.{ext}` |
| `transcriptions/` | Transcription JSON outputs | `{video_id}-{lang}.json` |
| `screenshots/` | Extracted video frames | `{video_id}-{timestamp_ms}.jpg` |

**Key principle**: `video_id` is the cache key. No datetime in filenames. Use `os.path.getmtime()` for age checks.

---

## Environment Variables

```env
# Add to example.env

# Unified cache configuration
CACHE_DIR=./cache
CACHE_TTL_HOURS=3
```

**Migration**: Replace `TRANSCRIPTIONS_DIR=./transcriptions` with unified `CACHE_DIR=./cache`

---

## Files to Modify

1. **main.py** - Add endpoints, cache functions, update existing transcription paths
2. **example.env** - Add cache configuration variables
3. **CLAUDE.md** - Document new endpoints

---

## Implementation

### 1. Directory Initialization (main.py)

```python
# Replace TRANSCRIPTIONS_DIR with unified cache
CACHE_DIR = os.getenv("CACHE_DIR", "./cache")
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "3"))

# Create cache subdirectories
for subdir in ["videos", "audio", "transcriptions", "screenshots"]:
    os.makedirs(os.path.join(CACHE_DIR, subdir), exist_ok=True)
```

### 2. Pydantic Models (main.py)

```python
class ScreenshotRequest(BaseModel):
    video_url: str
    timestamps: List[str]  # SRT format "00:01:30,500" or float seconds "90.5"
    upload_to_supabase: bool = False
    document_id: Optional[str] = None  # For Supabase metadata linking
    quality: int = 2  # FFmpeg JPEG quality 1-31 (lower = better)

class ScreenshotResult(BaseModel):
    timestamp: float
    timestamp_formatted: str
    file_path: str
    width: int
    height: int
    size_bytes: int
    supabase_url: Optional[str] = None

class ScreenshotResponse(BaseModel):
    screenshots: List[ScreenshotResult]
    video_id: str
    video_title: str
    video_duration: Optional[int]
    video_cached: bool  # True if reused existing cached video
    total_extracted: int
    failed_timestamps: List[str] = []
```

### 3. Utility Functions (main.py)

```python
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


def get_cached_video(video_id: str) -> Optional[str]:
    """
    Find cached video by video_id.
    Returns file path if fresh (within TTL), None if expired or missing.
    """
    cache_dir = os.path.join(CACHE_DIR, "videos")
    if not os.path.exists(cache_dir):
        return None

    for filename in os.listdir(cache_dir):
        if f"-{video_id}." in filename:
            filepath = os.path.join(cache_dir, filename)
            age_hours = (time.time() - os.path.getmtime(filepath)) / 3600
            if age_hours < CACHE_TTL_HOURS:
                return filepath  # Fresh, reuse it
    return None


def cleanup_cache() -> dict:
    """
    Delete all cached files older than TTL.
    Returns summary of deleted files.
    """
    cutoff = time.time() - (CACHE_TTL_HOURS * 3600)
    deleted = {"videos": 0, "audio": 0, "transcriptions": 0, "screenshots": 0}
    freed_bytes = 0

    for subdir in deleted.keys():
        dir_path = os.path.join(CACHE_DIR, subdir)
        if os.path.exists(dir_path):
            for filename in os.listdir(dir_path):
                filepath = os.path.join(dir_path, filename)
                if os.path.isfile(filepath) and os.path.getmtime(filepath) < cutoff:
                    freed_bytes += os.path.getsize(filepath)
                    os.remove(filepath)
                    deleted[subdir] += 1

    return {
        "deleted": deleted,
        "total_deleted": sum(deleted.values()),
        "freed_bytes": freed_bytes
    }


def extract_screenshot(video_path: str, timestamp_seconds: float, output_path: str, quality: int = 2) -> dict:
    """
    Extract single frame from video using FFmpeg.
    Returns metadata dict or raises exception.
    """
    import subprocess

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
```

### 4. Supabase Helpers (main.py)

```python
def upload_screenshot_to_supabase(file_path: str, storage_path: str) -> dict:
    """
    Upload screenshot to Supabase storage bucket.
    Reuses existing get_supabase_client().
    """
    supabase = get_supabase_client()

    with open(file_path, 'rb') as f:
        result = supabase.storage.from_("public_media").upload(
            path=storage_path,
            file=f.read(),
            file_options={"content-type": "image/jpeg"}
        )

    # Get public URL
    public_url = supabase.storage.from_("public_media").get_public_url(storage_path)

    return {
        "storage_path": storage_path,
        "public_url": public_url
    }


def save_screenshot_metadata(data: dict) -> dict:
    """Save screenshot metadata to public_media table."""
    supabase = get_supabase_client()
    result = supabase.table("public_media").insert(data).execute()
    return result.data[0] if result.data else None
```

### 5. Main Endpoint: POST /screenshot/video

```python
@app.post("/screenshot/video")
async def screenshot_video(
    request: ScreenshotRequest = Body(...),
    _: bool = Depends(verify_api_key)
) -> ScreenshotResponse:
    """
    Extract screenshots from video at specified timestamps.

    - Caches downloaded videos for reuse (subsequent requests skip download)
    - Supports SRT timestamps ("00:01:30,500") or float seconds (90.5)
    - Optional Supabase upload

    Workflow:
    1. Check cache for existing video (by video_id)
    2. If not cached, download video to ./cache/videos/
    3. Extract screenshots with FFmpeg
    4. Optional: upload to Supabase
    5. Return screenshot paths
    """
    # Trigger cache cleanup at start of request
    cleanup_cache()

    try:
        # Extract video metadata
        meta_opts = {'quiet': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(meta_opts) as ydl:
            info = ydl.extract_info(request.video_url, download=False)
            video_id = info.get('id')
            title = info.get('title', 'Unknown')
            duration = info.get('duration')
            platform = get_platform_prefix(request.video_url)

        # Check cache for existing video
        video_path = get_cached_video(video_id)
        video_cached = video_path is not None

        if not video_path:
            # Download video to cache
            video_filename = f"{platform}-{video_id}.mp4"
            video_path = os.path.join(CACHE_DIR, "videos", video_filename)

            ydl_opts = {
                'format': 'best[height<=1080]',
                'outtmpl': video_path.replace('.mp4', '.%(ext)s'),
                'quiet': True,
                'merge_output_format': 'mp4',
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([request.video_url])

            # Find actual downloaded file (extension may vary)
            cache_videos_dir = os.path.join(CACHE_DIR, "videos")
            for f in os.listdir(cache_videos_dir):
                if f.startswith(f"{platform}-{video_id}"):
                    video_path = os.path.join(cache_videos_dir, f)
                    break

        if not video_path or not os.path.exists(video_path):
            raise HTTPException(status_code=500, detail="Failed to download video")

        # Extract screenshots
        screenshots = []
        failed_timestamps = []
        screenshots_dir = os.path.join(CACHE_DIR, "screenshots")

        for ts in request.timestamps:
            try:
                ts_seconds = parse_timestamp_to_seconds(ts)
                ts_ms = int(ts_seconds * 1000)

                # Output path: {video_id}-{timestamp_ms}.jpg
                output_filename = f"{video_id}-{ts_ms}.jpg"
                output_path = os.path.join(screenshots_dir, output_filename)

                # Extract frame
                result = extract_screenshot(video_path, ts_seconds, output_path, request.quality)

                screenshot_result = ScreenshotResult(
                    timestamp=ts_seconds,
                    timestamp_formatted=format_seconds_to_srt(ts_seconds),
                    file_path=result["file_path"],
                    width=result["width"],
                    height=result["height"],
                    size_bytes=result["size_bytes"],
                    supabase_url=None
                )

                # Optional Supabase upload
                if request.upload_to_supabase:
                    storage_path = f"screenshots/{video_id}/{ts_ms}.jpg"
                    upload_result = upload_screenshot_to_supabase(output_path, storage_path)
                    screenshot_result.supabase_url = upload_result["public_url"]

                    # Save metadata to database
                    save_screenshot_metadata({
                        "type": "screenshot",
                        "storage_path": storage_path,
                        "storage_bucket": "public_media",
                        "content_type": "image/jpeg",
                        "size_bytes": result["size_bytes"],
                        "source_url": request.video_url,
                        "source_url_hash": hashlib.md5(request.video_url.encode()).hexdigest(),
                        "title": f"{title} - {format_seconds_to_srt(ts_seconds)}",
                        "document_id": request.document_id,
                        "metadata": {
                            "video_id": video_id,
                            "timestamp": ts_seconds,
                            "timestamp_formatted": format_seconds_to_srt(ts_seconds),
                            "width": result["width"],
                            "height": result["height"],
                            "platform": platform.lower()
                        }
                    })

                screenshots.append(screenshot_result)

            except Exception as e:
                failed_timestamps.append(f"{ts}: {str(e)}")

        return ScreenshotResponse(
            screenshots=screenshots,
            video_id=video_id,
            video_title=title,
            video_duration=duration,
            video_cached=video_cached,
            total_extracted=len(screenshots),
            failed_timestamps=failed_timestamps
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screenshot extraction failed: {str(e)}")
```

### 6. Cache Management Endpoints

```python
@app.delete("/cache/cleanup")
async def cache_cleanup(_: bool = Depends(verify_api_key)):
    """
    Delete all cached files older than CACHE_TTL_HOURS.

    Use cases:
    - Cron job target: 0 * * * * curl -X DELETE .../cache/cleanup
    - Manual cleanup trigger

    Note: Also triggered automatically on transcription requests.
    """
    result = cleanup_cache()
    return {
        "message": f"Cleanup complete. Deleted {result['total_deleted']} files.",
        "deleted": result["deleted"],
        "freed_bytes": result["freed_bytes"],
        "ttl_hours": CACHE_TTL_HOURS
    }


@app.get("/cache")
async def list_cache(
    type: str = Query(None, description="Filter by type: videos, audio, transcriptions, screenshots"),
    _: bool = Depends(verify_api_key)
):
    """
    List all cached files with metadata.
    Optional filter by type.
    """
    subdirs = [type] if type else ["videos", "audio", "transcriptions", "screenshots"]
    files = []
    total_size = 0

    for subdir in subdirs:
        dir_path = os.path.join(CACHE_DIR, subdir)
        if not os.path.exists(dir_path):
            continue

        for filename in os.listdir(dir_path):
            filepath = os.path.join(dir_path, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                age_hours = (time.time() - stat.st_mtime) / 3600

                files.append({
                    "filename": filename,
                    "type": subdir.rstrip('s'),  # "videos" -> "video"
                    "path": filepath,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "age_hours": round(age_hours, 2),
                    "expires_in_hours": round(max(0, CACHE_TTL_HOURS - age_hours), 2)
                })
                total_size += stat.st_size

    # Sort by age (newest first)
    files.sort(key=lambda x: x["age_hours"])

    return {
        "files": files,
        "summary": {
            "total_files": len(files),
            "total_size_bytes": total_size,
            "ttl_hours": CACHE_TTL_HOURS
        }
    }
```

### 7. Update Existing Transcription Endpoints

**Modify `/extract-audio`** to use unified cache:

```python
# Change audio output path from /tmp/ to ./cache/audio/
audio_path = os.path.join(CACHE_DIR, "audio", f"{video_id}.{output_format}")
```

**Modify `/transcribe`** to trigger cleanup:

```python
@app.post("/transcribe")
async def transcribe_audio(...):
    # Add at start of function:
    cleanup_cache()  # Trigger cleanup on each transcription request

    # Rest of existing code...
```

**Remove old cleanup function**: Replace `cleanup_old_transcriptions()` calls with `cleanup_cache()`.

---

## Implementation Order

1. **Add environment variables** to example.env (`CACHE_DIR`, `CACHE_TTL_HOURS`)
2. **Add directory initialization** for `./cache/{videos,audio,transcriptions,screenshots}/`
3. **Add utility functions**:
   - `parse_timestamp_to_seconds()`
   - `format_seconds_to_srt()`
   - `get_cached_video()`
   - `cleanup_cache()` (replaces `cleanup_old_transcriptions()`)
   - `extract_screenshot()`
4. **Add Supabase helpers**:
   - `upload_screenshot_to_supabase()`
   - `save_screenshot_metadata()`
5. **Add Pydantic models** for screenshot request/response
6. **Add POST /screenshot/video** endpoint
7. **Add cache management endpoints**:
   - `DELETE /cache/cleanup`
   - `GET /cache`
8. **Update existing endpoints**:
   - `/extract-audio` → use `./cache/audio/` path
   - `/transcribe` → add `cleanup_cache()` call at start
   - Remove old `cleanup_old_transcriptions()` function
9. **Run SQL migration** in Supabase (add 'screenshot' type to constraint)
10. **Test all modified endpoints**:
    - `POST /screenshot/video` - test with YouTube URL, multiple timestamps, Supabase upload
    - `DELETE /cache/cleanup` - verify expired files are deleted
    - `GET /cache` - verify listing with type filter
    - `POST /extract-audio` - verify new cache path works
    - `POST /transcribe` - verify cleanup triggers and transcription works
11. **Update documentation** (after testing confirms all endpoints work):
    - `docs/endpoints-index.md` - add new endpoints to index table
    - `docs/endpoints-usage.md` - add detailed usage docs for new endpoints
    - `CLAUDE.md` - update with new cache system and endpoints

---

## Supabase Migration

**SQL** (run in Supabase SQL Editor):
```sql
ALTER TABLE public.public_media
DROP CONSTRAINT IF EXISTS valid_type;

ALTER TABLE public.public_media
ADD CONSTRAINT valid_type CHECK (
  type = ANY (ARRAY['thumbnail', 'avatar', 'resource_file', 'screenshot'])
);
```

---

## Response Format Example

```json
{
  "screenshots": [
    {
      "timestamp": 90.5,
      "timestamp_formatted": "00:01:30,500",
      "file_path": "./cache/screenshots/dQw4w9WgXcQ-90500.jpg",
      "width": 1920,
      "height": 1080,
      "size_bytes": 123456,
      "supabase_url": "https://xxx.supabase.co/storage/v1/object/public/public_media/screenshots/dQw4w9WgXcQ/90500.jpg"
    }
  ],
  "video_id": "dQw4w9WgXcQ",
  "video_title": "Video Title",
  "video_duration": 630,
  "video_cached": true,
  "total_extracted": 1,
  "failed_timestamps": []
}
```

---

## Error Handling

| Condition | Status | Message |
|-----------|--------|---------|
| Missing video_url | 422 | Validation error |
| Empty timestamps | 422 | Validation error |
| Invalid timestamp format | 400 | "Invalid timestamp: {value}" |
| Video download failed | 500 | "Failed to download video" |
| FFmpeg error | 500 | "Screenshot extraction failed: {error}" |
| Supabase not configured | 503 | "Supabase not configured" |

---

## Dependencies

- **System**: FFmpeg, ffprobe (for screenshot extraction)
- **Python**: No new packages
  - `subprocess`, `json`, `time`, `os`, `hashlib` (stdlib)
  - `supabase-py` (already installed)

---

## Summary

| Aspect | Value |
|--------|-------|
| New endpoints | 3 (`POST /screenshot/video`, `DELETE /cache/cleanup`, `GET /cache`) |
| New env vars | 2 (`CACHE_DIR`, `CACHE_TTL_HOURS`) |
| New directories | 1 (`./cache/` with 4 subdirs) |
| Registry file | None (filesystem + mtime) |
| Cleanup trigger | On transcription requests + optional cron |
| Estimated lines | ~250 |
| Implementation steps | 11 (including testing & documentation) |
