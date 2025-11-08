# Clean API Architecture

**Simple, composable endpoints with single responsibility.**

## Philosophy

Each endpoint does **ONE thing** well. Combine endpoints for complex workflows.

---

## Endpoints

### 1. `GET /download` - Download Files
**Purpose:** Download video or audio file
**Input:** `url`, `format`, `keep`
**Output:** File (streamed to client or saved to server)

**Example:**
```bash
# Download video and keep on server
curl -X GET "/download?url=VIDEO_URL&keep=true" \
  -H "X-API-Key: YOUR_KEY" \
  -O video.mp4

# Returns header: X-Server-Path: downloads/VIDEO-title.mp4
```

---

### 2. `GET /subtitles` - Extract Subtitles
**Purpose:** Extract existing subtitles (no AI)
**Input:** `url`, `lang`, `format`
**Output:** Subtitles OR 404 with workflow guidance

**Example:**
```bash
# Try to get subtitles
curl -X GET "/subtitles?url=VIDEO_URL&lang=en&format=json" \
  -H "X-API-Key: YOUR_KEY"
```

**Success Response:**
```json
{
  "transcript": "Video transcript text...",
  "word_count": 245,
  "title": "Video Title",
  "language": "en"
}
```

**No Subtitles Found (404):**
```json
{
  "error": "No subtitles available",
  "message": "No subtitles found for language 'en'. Use POST /extract-audio + POST /transcribe to generate AI transcription.",
  "suggested_workflow": [
    "1. POST /extract-audio with url parameter",
    "2. POST /transcribe with returned audio_file path"
  ],
  "available_languages": [],
  "title": "Video Title"
}
```

---

### 3. `POST /extract-audio` - Extract Audio
**Purpose:** Extract audio from video (URL or local file)
**Input:** `url` OR `local_file`, `output_format`, `quality`
**Output:** Audio file path on server

**Example 1: From URL**
```bash
curl -X POST "/extract-audio?url=VIDEO_URL" \
  -H "X-API-Key: YOUR_KEY"
```

**Example 2: From Local File**
```bash
# First download video
curl -X GET "/download?url=VIDEO_URL&keep=true" -H "X-API-Key: YOUR_KEY"
# Returns: X-Server-Path: downloads/VIDEO-title.mp4

# Then extract audio from it
curl -X POST "/extract-audio?local_file=downloads/VIDEO-title.mp4" \
  -H "X-API-Key: YOUR_KEY"
```

**Response:**
```json
{
  "audio_file": "/tmp/a1b2c3d4.mp3",
  "format": "mp3",
  "size": 5242880,
  "title": "Video Title",
  "source_type": "url",
  "message": "Audio extracted successfully. Use this audio_file path with POST /transcribe",
  "expires_in": "1 hour (automatic cleanup)"
}
```

---

### 4. `POST /transcribe` - Transcribe Audio
**Purpose:** Transcribe audio file using AI
**Input:** `audio_file` (path from /extract-audio), `provider`, `model_size`
**Output:** Transcription

**Example:**
```bash
curl -X POST "/transcribe?audio_file=/tmp/a1b2c3d4.mp3&provider=local" \
  -H "X-API-Key: YOUR_KEY"
```

**Response:**
```json
{
  "title": "a1b2c3d4.mp3",
  "language": "en",
  "model": "medium",
  "provider": "local",
  "segments": [
    {"start": 0.0, "end": 3.5, "text": "Hello, welcome to the video."},
    {"start": 3.5, "end": 7.2, "text": "Today we'll discuss..."}
  ],
  "full_text": "Hello, welcome to the video. Today we'll discuss...",
  "word_count": 245,
  "segment_count": 68,
  "transcription_time": 45.2
}
```

---

## Workflows

### Workflow 1: Quick Transcription (Try Subtitles First)

```bash
# Step 1: Try subtitles (free, instant)
curl -X GET "/subtitles?url=VIDEO_URL" -H "X-API-Key: YOUR_KEY"

# If 404, proceed with AI:

# Step 2: Extract audio
curl -X POST "/extract-audio?url=VIDEO_URL" -H "X-API-Key: YOUR_KEY"
# Returns: {"audio_file": "/tmp/abc.mp3"}

# Step 3: Transcribe
curl -X POST "/transcribe?audio_file=/tmp/abc.mp3" -H "X-API-Key: YOUR_KEY"
```

---

### Workflow 2: Download + Transcribe + Keep Video

```bash
# Step 1: Download and keep video
curl -X GET "/download?url=VIDEO_URL&keep=true" -H "X-API-Key: YOUR_KEY"
# Returns header: X-Server-Path: downloads/VIDEO-title.mp4

# Step 2: Extract audio from saved video
curl -X POST "/extract-audio?local_file=downloads/VIDEO-title.mp4" \
  -H "X-API-Key: YOUR_KEY"
# Returns: {"audio_file": "/tmp/abc.mp3"}

# Step 3: Transcribe
curl -X POST "/transcribe?audio_file=/tmp/abc.mp3&provider=local" \
  -H "X-API-Key: YOUR_KEY"

# Now you have: Video saved + Transcription
```

---

### Workflow 3: Download Audio Only + Transcribe

```bash
# Step 1: Download audio file
curl -X GET "/download?url=VIDEO_URL&format=bestaudio&keep=true" \
  -H "X-API-Key: YOUR_KEY"
# Returns header: X-Server-Path: downloads/AUDIO-title.m4a

# Step 2: Transcribe audio file directly
curl -X POST "/extract-audio?local_file=downloads/AUDIO-title.m4a" \
  -H "X-API-Key: YOUR_KEY"
# Returns: {"audio_file": "/tmp/abc.mp3"}

# Step 3: Transcribe
curl -X POST "/transcribe?audio_file=/tmp/abc.mp3" -H "X-API-Key: YOUR_KEY"
```

---

### Workflow 4: Batch Processing with Retry

```bash
# Download once
curl -X GET "/download?url=VIDEO&keep=true" -H "X-API-Key: KEY"

# Extract audio once
curl -X POST "/extract-audio?local_file=downloads/video.mp4" -H "X-API-Key: KEY"
# Returns: {"audio_file": "/tmp/abc.mp3"}

# Retry transcription with different models if needed
curl -X POST "/transcribe?audio_file=/tmp/abc.mp3&model_size=tiny" -H "X-API-Key: KEY"
curl -X POST "/transcribe?audio_file=/tmp/abc.mp3&model_size=medium" -H "X-API-Key: KEY"
curl -X POST "/transcribe?audio_file=/tmp/abc.mp3&provider=openai" -H "X-API-Key: KEY"

# No re-downloading needed!
```

---

## Benefits

### ✅ Single Responsibility
- Each endpoint does ONE thing
- Easy to understand and test
- Clear error messages

### ✅ Composable
- Combine endpoints for different workflows
- Flexible: download + keep, extract + retry, etc.

### ✅ Reusable
- `/extract-audio` works with URLs AND local files
- `/transcribe` works with any audio file path
- No duplicate logic

### ✅ Efficient
- Download once, transcribe multiple times
- Try subtitles before AI
- Retry transcription without re-downloading

### ✅ Practical
- No over-engineering
- Simple HTTP calls
- Clear workflow guidance in error messages

---

## Error Handling

All endpoints return detailed error messages:

**404 - Not Found:**
```json
{
  "detail": {
    "error": "No subtitles available",
    "message": "Use POST /extract-audio + POST /transcribe",
    "suggested_workflow": ["..."]
  }
}
```

**500 - Provider Errors:**
```json
{
  "detail": "Local provider error: Out of memory. Try smaller model (tiny/small) or use provider=openai"
}
```

**503 - Connection Failed:**
```json
{
  "detail": "OpenAI provider error: Connection failed - [Errno 61] Connection refused"
}
```

**504 - Timeout:**
```json
{
  "detail": "OpenAI provider error: Request timeout - API did not respond within 5 minutes"
}
```

---

## Comparison: Old vs New

### Old Architecture (Overlapping Responsibilities)
```
/transcription  →  Get subtitles (one job) ✅
/ai-transcribe  →  Download + Extract + Transcribe (three jobs) ❌
/smart-transcribe → Try subtitles + Download + Extract + Transcribe (four jobs) ❌
```

### New Architecture (Single Responsibility)
```
/subtitles      →  Get subtitles (one job) ✅
/extract-audio  →  Extract audio (one job) ✅
/transcribe     →  Transcribe audio (one job) ✅
/download       →  Download file (one job) ✅
```

**Result:**
- 4 simple endpoints that work together
- No duplicate logic
- Easy to combine for any workflow

---

## Quick Reference

| Endpoint | Method | Input | Output | Use Case |
|----------|--------|-------|--------|----------|
| `/download` | GET | url | File | Download video/audio |
| `/subtitles` | GET | url | Subtitles or 404 | Extract existing subtitles |
| `/extract-audio` | POST | url OR local_file | audio_file path | Get audio from video |
| `/transcribe` | POST | audio_file path | Transcription | AI transcription |

---

## Related Documentation

- [Composable Workflows Guide](./composable-workflows.md) - Platform-specific workflow examples (YouTube, TikTok, podcasts)
- [Endpoint Flow Diagrams](./endpoint-flows.md) - Technical flow diagrams with line references
- [Transcription Services Guide](./transcription-services.md) - Provider comparison and features
- [Transcription Setup Guide](./transcription-setup-guide.md) - Installation and configuration
