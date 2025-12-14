# Video Screenshot Extraction Feature - Implementation Plan

## Overview

Add a `/screenshot/video` endpoint to extract frames from videos at specified timestamps, with a **unified caching system** for videos and transcriptions, plus Supabase storage integration.

---

## User Requirements Summary

1. **New endpoint `/screenshot/video`** - Extract screenshots from video at specified timestamps
2. **Video caching with registry** - Track locally downloaded videos with expiration
3. **Unified cache system** - Single registry for both videos and transcriptions
4. **Supabase integration** - Store screenshots to `public_media` bucket and table
5. **Utility endpoints** - Inspect and manage cached files with filtering

### User Decisions Made:
- **Media type**: Add 'screenshot' to public_media table constraint
- **Registry storage**: JSON file (`./cache/registry.json`)
- **Video TTL**: 3 hours (configurable via `VIDEO_CACHE_TTL_HOURS`)
- **Timestamp format**: Auto-detect both SRT ("00:01:30,500") and float seconds (90.5)
- **Supabase records**: One record per screenshot

---

## Unified Cache Architecture

```
./cache/
├── registry.json              # Single registry for ALL cached resources
├── videos/                    # Cached video files
│   └── YT-video-title-abc123.mp4
└── transcriptions/            # Processed transcription files
    └── abc123_subtitles.json
```

| Location | Purpose | Default TTL | Cleanup |
|----------|---------|-------------|---------|
| `/tmp/` | Temporary screenshots | Manual | Per-request or explicit |
| `./cache/videos/` | Cached videos for processing | 3 hours | Auto via registry |
| `./cache/transcriptions/` | Processed transcriptions | 1 hour | Auto via registry |
| `./downloads/` | Persistent downloads (keep=true) | None | Manual only |

### Unified Registry Schema (registry.json)

```json
{
  "abc123_video": {
    "type": "video",
    "file_path": "./cache/videos/YT-video-title-abc123.mp4",
    "source_url": "https://youtube.com/watch?v=abc123",
    "video_id": "abc123",
    "title": "Video Title",
    "duration": 630,
    "platform": "youtube",
    "size_bytes": 52428800,
    "created_at": "2025-01-08T10:30:00Z",
    "expires_at": "2025-01-08T13:30:00Z",
    "metadata": {}
  },
  "abc123_transcription": {
    "type": "transcription",
    "file_path": "./cache/transcriptions/abc123_subtitles.json",
    "source_url": "https://youtube.com/watch?v=abc123",
    "video_id": "abc123",
    "title": "Video Title",
    "language": "en",
    "source": "subtitle",
    "provider": "youtube",
    "size_bytes": 12345,
    "created_at": "2025-01-08T10:30:00Z",
    "expires_at": "2025-01-08T11:30:00Z",
    "metadata": {"segment_count": 245, "word_count": 3500}
  }
}
```

---

## Files to Modify

1. **main.py** - Add endpoints, models, unified cache system
2. **example.env** - Add cache configuration variables
3. **CLAUDE.md** - Document new endpoints

---

## Environment Variables (example.env)

```env
# Unified cache configuration
CACHE_DIR=./cache
CACHE_REGISTRY_FILE=./cache/registry.json
VIDEO_CACHE_TTL_HOURS=3
TRANSCRIPTION_CACHE_TTL_HOURS=1
```

---

## Implementation

### 1. Pydantic Models (main.py)

```python
class ScreenshotRequest(BaseModel):
    video_url: Optional[str] = None
    video_file_path: Optional[str] = None
    timestamps: List[str]  # SRT format or float seconds
    upload_to_supabase: bool = False
    document_id: Optional[str] = None
    quality: int = 2  # JPEG quality 1-31

class ScreenshotResult(BaseModel):
    timestamp: float
    timestamp_formatted: str
    file_path: str
    width: int
    height: int
    size_bytes: int
    supabase_path: Optional[str] = None

class ScreenshotResponse(BaseModel):
    screenshots: List[ScreenshotResult]
    video_metadata: dict
    total_extracted: int
    failed_timestamps: List[str] = []

class CacheEntry(BaseModel):
    id: str
    type: str  # "video" or "transcription"
    video_id: str
    file_path: str
    source_url: Optional[str]
    title: str
    platform: str
    size_bytes: int
    created_at: str
    expires_at: str
    is_expired: bool
    time_remaining_seconds: int
    metadata: dict = {}
```

### 2. Utility Functions (main.py)

```python
# Timestamp parsing (auto-detect SRT vs float)
def parse_timestamp_to_seconds(timestamp: str) -> float
def format_seconds_to_srt(seconds: float) -> str

# Unified cache registry management
def load_cache_registry() -> Dict[str, Any]
def save_cache_registry(registry: Dict[str, Any]) -> None
def cleanup_expired_cache(entry_type: Optional[str] = None) -> int
def get_cached_entry(entry_id: str) -> Optional[Dict]
def get_cached_video(video_id: str) -> Optional[Dict]
def get_cached_transcription(video_id: str, language: str = None) -> Optional[Dict]
def register_cache_entry(
    entry_type: str,  # "video" or "transcription"
    file_path: str,
    video_id: str,
    source_url: Optional[str],
    title: str,
    ttl_hours: int,
    **metadata
) -> Dict[str, Any]
def delete_cache_entry(entry_id: str) -> bool
def list_cache_entries(
    entry_type: Optional[str] = None,
    video_id: Optional[str] = None,
    expired_only: bool = False
) -> List[Dict]

# FFmpeg screenshot extraction
def extract_screenshot(video_path, timestamp_seconds, output_path, quality) -> Dict

# Supabase helpers (reuse existing get_supabase_client())
def upload_screenshot_to_supabase(file_path: str, storage_path: str) -> Dict
def save_screenshot_metadata(data: Dict) -> Dict
```

### 3. Main Endpoint

**POST /screenshot/video**
- Input: `video_url` OR `video_file_path` + `timestamps[]`
- Auto-detect timestamp format (SRT "00:01:30,500" or float 90.5)
- Check video cache before downloading
- Extract screenshots to `/tmp/` with UUID naming
- Optional Supabase upload
- Return screenshot paths + metadata

### 4. Unified Cache Endpoints

**GET /cache**
List all cached resources with optional filtering.

Query params:
- `type`: Filter by type (`video`, `transcription`, or omit for all)
- `video_id`: Filter by video_id
- `expired`: Show only expired (`true`) or non-expired (`false`)
- `platform`: Filter by platform (youtube, tiktok, etc.)

```json
{
  "entries": [
    {
      "id": "abc123_video",
      "type": "video",
      "video_id": "abc123",
      "title": "Video Title",
      "file_path": "./cache/videos/YT-video.mp4",
      "size_bytes": 52428800,
      "platform": "youtube",
      "created_at": "2025-01-08T10:30:00Z",
      "expires_at": "2025-01-08T13:30:00Z",
      "is_expired": false,
      "time_remaining_seconds": 7200
    },
    {
      "id": "abc123_transcription",
      "type": "transcription",
      "video_id": "abc123",
      "title": "Video Title",
      "file_path": "./cache/transcriptions/abc123_subtitles.json",
      "size_bytes": 12345,
      "language": "en",
      "source": "subtitle",
      "created_at": "2025-01-08T10:30:00Z",
      "expires_at": "2025-01-08T11:30:00Z",
      "is_expired": true,
      "time_remaining_seconds": 0
    }
  ],
  "summary": {
    "total_count": 10,
    "video_count": 5,
    "transcription_count": 5,
    "total_size_bytes": 262156345,
    "expired_count": 2
  }
}
```

**GET /cache/{entry_id}**
Get specific cache entry details.

**DELETE /cache/{entry_id}**
Delete specific cache entry and its file.

**DELETE /cache**
Cleanup cache entries.

Query params:
- `type`: Only cleanup specific type (`video`, `transcription`)
- `force`: Delete ALL entries of type, not just expired (`true`/`false`)
- `video_id`: Delete all entries for specific video_id

**GET /cache/temp-screenshots**
List temporary screenshot files in `/tmp/` (not in registry, scanned from filesystem).
```json
{
  "screenshots": [
    {
      "file_path": "/tmp/abc123_screenshot_001.jpg",
      "size_bytes": 54321,
      "modified_at": "2025-01-08T11:00:00Z",
      "age_minutes": 15
    }
  ],
  "total_count": 10,
  "total_size_bytes": 543210
}
```

**DELETE /cache/temp-screenshots**
Clean up temporary screenshot files from `/tmp/`.

### 5. Supabase Integration

**Reuse Existing Client**: The existing `supabase-py` client in main.py (lines 59-84) supports both database and storage operations. No new dependencies needed.

```python
# Existing client pattern (main.py lines 74-84)
def get_supabase_client() -> Client:
    """Returns client or raises 503 HTTPException if not configured"""
    if supabase_client is None:
        raise HTTPException(status_code=503, detail="Supabase not configured...")
    return supabase_client

# NEW: Storage upload helper
def upload_screenshot_to_supabase(file_path: str, storage_path: str) -> dict:
    """Upload screenshot to Supabase storage bucket."""
    supabase = get_supabase_client()

    with open(file_path, 'rb') as f:
        result = supabase.storage.from_("public_media").upload(
            path=storage_path,
            file=f.read(),
            file_options={"content-type": "image/jpeg"}
        )

    # Get signed URL (authenticated access)
    url_response = supabase.storage.from_("public_media").create_signed_url(
        path=storage_path,
        expires_in=3600  # 1 hour
    )

    return {
        "storage_path": storage_path,
        "signed_url": url_response.get("signedURL")
    }

# NEW: Database insert helper (same pattern as existing transcription save)
def save_screenshot_metadata(data: dict) -> dict:
    """Save screenshot metadata to public_media table."""
    supabase = get_supabase_client()
    result = supabase.table("public_media").insert(data).execute()
    return result.data[0] if result.data else None
```

**SQL Migration** (run in Supabase SQL Editor):
```sql
ALTER TABLE public.public_media
DROP CONSTRAINT IF EXISTS valid_type;

ALTER TABLE public.public_media
ADD CONSTRAINT valid_type CHECK (
  type = ANY (ARRAY['thumbnail', 'avatar', 'resource_file', 'screenshot'])
);
```

**Storage**: Upload to `public_media` bucket with path:
`screenshots/{video_id}/{timestamp_ms}.jpg`

**Database**: One record per screenshot in `public_media` table:
```json
{
  "type": "screenshot",
  "storage_path": "screenshots/dQw4w9WgXcQ/90500.jpg",
  "storage_bucket": "public_media",
  "content_type": "image/jpeg",
  "size_bytes": 123456,
  "source_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "source_url_hash": "abc123...",
  "title": "Video Title - 00:01:30",
  "metadata": {
    "video_id": "dQw4w9WgXcQ",
    "timestamp": 90.5,
    "timestamp_formatted": "00:01:30,500",
    "width": 1920,
    "height": 1080,
    "platform": "youtube"
  }
}
```

### 6. FFmpeg Command

```bash
ffmpeg -ss <seconds> -i <video> -vframes 1 -q:v 2 -y /tmp/<uuid>_screenshot_<idx>.jpg
```

---

## Implementation Order

1. **Add environment variables** to example.env
2. **Add directory initialization** for `./cache/videos/` and `./cache/transcriptions/`
3. **Add Pydantic models** for cache entries and screenshot requests
4. **Implement unified cache system**:
   - `load_cache_registry()` / `save_cache_registry()`
   - `register_cache_entry()` / `delete_cache_entry()`
   - `get_cached_video()` / `get_cached_transcription()`
   - `list_cache_entries()` with filtering
   - `cleanup_expired_cache()`
5. **Add timestamp utilities**:
   - `parse_timestamp_to_seconds()` (auto-detect format)
   - `format_seconds_to_srt()`
6. **Add FFmpeg screenshot extraction** function
7. **Add Supabase storage helpers** (reuse existing client):
   - `upload_screenshot_to_supabase()` - storage upload
   - `save_screenshot_metadata()` - database insert
8. **Add POST /screenshot/video** endpoint
9. **Add cache management endpoints**:
   - GET /cache (with filters)
   - GET /cache/{entry_id}
   - DELETE /cache/{entry_id}
   - DELETE /cache (cleanup)
   - GET /cache/temp-screenshots
   - DELETE /cache/temp-screenshots
10. **Update existing transcription endpoints** to use unified cache:
    - Modify `/subtitles` to save transcriptions to `./cache/transcriptions/`
    - Modify `/transcribe` to save transcriptions to `./cache/transcriptions/`
    - Remove old `cleanup_old_transcriptions()` in favor of unified cleanup
11. **Run SQL migration** in Supabase (add 'screenshot' type)
12. **Update CLAUDE.md** documentation

---

## Response Format Example

```json
{
  "screenshots": [
    {
      "timestamp": 90.5,
      "timestamp_formatted": "00:01:30,500",
      "file_path": "/tmp/a1b2c3d4_screenshot_000.jpg",
      "width": 1920,
      "height": 1080,
      "size_bytes": 123456,
      "supabase_path": "screenshots/doc123/vid456_90500.jpg"
    }
  ],
  "video_metadata": {
    "video_id": "dQw4w9WgXcQ",
    "title": "Video Title",
    "duration": 630,
    "platform": "youtube"
  },
  "total_extracted": 1,
  "failed_timestamps": []
}
```

---

## Error Handling

| Condition | Status | Message |
|-----------|--------|---------|
| No video_url or video_file_path | 400 | "Either video_url or video_file_path required" |
| Both provided | 400 | "Provide video_url OR video_file_path, not both" |
| Invalid timestamp | 400 | "Invalid timestamp: {value}" |
| File not found | 404 | "Video file not found" |
| FFmpeg error | 500 | "Screenshot extraction failed: {error}" |
| Supabase not configured | 503 | "Supabase not configured" |

---

## Dependencies

- **System**: FFmpeg (ffmpeg, ffprobe commands)
- **Python**: No new packages needed
  - `subprocess`, `json`, `datetime`, `os`, `hashlib`, `uuid` (stdlib)
  - `supabase-py` (already installed - reuse existing client for storage + database)
