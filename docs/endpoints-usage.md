# API Endpoints Usage Guide

This document provides detailed information about all available API endpoints, their parameters, and response formats.

## Authentication

All protected endpoints require the `X-Api-Key` header:

```bash
X-Api-Key: your-api-key-here
```

---

## Overview: Transcription Features

The API offers two methods for extracting transcriptions from videos, each with distinct advantages:

### Method 1: Subtitle Extraction (GET /subtitles)

Extract existing subtitles/captions directly from video platforms:

**Key Features:**
- ✅ **Free & Instant**: No processing time or cost (< 1 second)
- ✅ **Manual & Auto Captions**: Supports both human-created and auto-generated subtitles
- ✅ **Multiple Formats**: Returns VTT, SRT, plain text, or JSON with timestamps
- ✅ **100+ Languages**: Supports all languages available on the platform
- ✅ **High Availability**: Most YouTube videos, educational content, and popular social media have subtitles

**Best For:**
- YouTube videos with existing captions
- TikTok videos with subtitles
- Educational content (Coursera, Khan Academy, etc.)
- Any video that already has subtitles

**Limitations:**
- Only works if video has existing subtitles
- Returns 404 if no subtitles available

---

### Method 2: AI Transcription (POST /transcribe)

Generate transcriptions using AI for videos without existing subtitles:

**Key Features:**
- ✅ **Local Processing**: Runs on your server (CPU/GPU), no cloud API fees ($0 cost)
- ✅ **High Accuracy**: OpenAI Whisper models with 95%+ accuracy for clear audio
- ✅ **Multi-language**: Supports 99 languages with automatic language detection
- ✅ **Word-level Timestamps**: Provides precise timestamps (not just segments)
- ✅ **Multiple Formats**: JSON, SRT, VTT, plain text
- ✅ **Platform Agnostic**: Works on Railway (CPU mode), NVIDIA GPUs, Apple Silicon
- ✅ **Two Providers**:
  - **whisperX (local)**: $0 cost, 70x real-time on GPU, 3-5x on CPU
  - **OpenAI API**: $0.006/min, managed service

**Best For:**
- Videos without subtitles
- Podcasts and audio content
- Local video files
- When you need custom language support
- When platform subtitles are low quality

**Performance:**
- **GPU (NVIDIA/MPS)**: 10-min video in ~8 seconds
- **CPU**: 10-min video in 2-3 minutes
- **Railway Compatible**: Works in CPU mode on cloud deployments

---

### Choosing the Right Method

**Recommended Workflow (Smart Transcription):**
1. **Try `/subtitles` first** (free, instant)
2. **If 404 response**, use `/extract-audio` + `/transcribe` (AI transcription)
3. Result: Always get transcription, optimize cost and speed

**Quick Comparison:**

| Feature | Subtitle Extraction | AI Transcription |
|---------|-------------------|------------------|
| **Cost** | $0 | $0 (local) or $0.006/min (OpenAI) |
| **Speed** | < 1s | 2-180s depending on length |
| **Accuracy** | Platform-dependent | 95%+ for clear audio |
| **Availability** | Requires existing subtitles | Works on any video |
| **Languages** | Platform-specific (100+) | 99 languages |
| **Timestamps** | Segment-level | Word-level (whisperX) |
| **Setup** | None | Requires whisperX or OpenAI API |

**See [Common Workflows & Examples](#common-workflows--examples) section below for implementation details.**

---

## 1. Health Check Endpoint

### `GET /`

**Description**: Returns a welcome message to verify the API is running.

**Authentication**: Not required

**Parameters**: None

**Example Request**:
```bash
curl "http://localhost:8000/"
```

**Example Response**:
```json
{
  "message": "Welcome to the Social Media Video Downloader API. Use /download?url=<video_url>&format=<video_format> to download videos."
}
```

---

## 2. Video Download Endpoint

### `GET /download`

**Description**: Downloads videos from supported platforms (YouTube, TikTok, Instagram, Facebook, Twitter, etc.) and streams them to the client. Optionally saves videos to server storage.

**Authentication**: Required

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | Video URL from any supported platform |
| `format` | string | No | `"best"` | Video quality format selector |
| `keep` | boolean | No | `false` | Save video to server storage if true |

### Format Options

| Format | Description |
|--------|-------------|
| `best` | Highest available quality |
| `worst` | Lowest available quality |
| `best[height<=360]` | 360p or lower |
| `best[height<=720]` | 720p or lower |
| `best[height<=1080]` | 1080p or lower |
| `best[height<=1440]` | 1440p or lower |
| `best[height<=2160]` | 4K or lower |

### Example Requests

**Download 720p video (temporary)**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/download?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format=best[height<=720]"
```

**Download and keep on server**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/download?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format=best[height<=720]&keep=true"
```

### Response

**Headers**:
- `Content-Type`: `application/octet-stream`
- `Content-Disposition`: `attachment; filename="Video Title.mp4"`
- `X-Server-Path`: `/downloads/filename.mp4` (only when `keep=true`)

**Body**: Binary video file stream

### Error Responses

```json
{
  "detail": "Invalid API Key"
}
```

```json
{
  "detail": "Download failed or file not found."
}
```

---

## 2B. Batch Video Download Endpoint

### `POST /batch-download`

**Description**: Download multiple videos from supported platforms with automatic rate limiting and independent error handling. One failure doesn't stop the batch. Supports duplicate detection.

**Authentication**: Required

### Request Body (JSON)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `urls` | array[string] | Yes | - | Array of video URLs to download |
| `format` | string | No | `"best"` | Video quality format (same as /download) |
| `keep` | boolean | No | `false` | Save videos to server storage |
| `cookies_file` | string | No | `null` | Path to cookies file for authentication |

### Example Request

```bash
curl -X POST "http://localhost:8000/batch-download" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-key" \
  -d '{
    "urls": [
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "https://www.youtube.com/watch?v=jNQXAC9IVRw",
      "https://www.youtube.com/watch?v=9bZkp7q19f0"
    ],
    "format": "best[height<=720]",
    "keep": true
  }'
```

### Response Example

```json
{
  "total": 3,
  "successful": 2,
  "failed": 1,
  "skipped": 0,
  "results": [
    {
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "success": true,
      "title": "Never Gonna Give You Up",
      "filename": "Never_Gonna_Give_You_Up_20241214_120530.mp4",
      "file_path": "./downloads/Never_Gonna_Give_You_Up_20241214_120530.mp4",
      "file_size": 15728640,
      "platform": "youtube"
    },
    {
      "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
      "success": true,
      "title": "Me at the zoo",
      "filename": "Me_at_the_zoo_20241214_120545.mp4",
      "file_path": "./downloads/Me_at_the_zoo_20241214_120545.mp4",
      "file_size": 3145728,
      "platform": "youtube"
    },
    {
      "url": "https://invalid-url.com/video",
      "success": false,
      "error": "Unsupported URL: No suitable extractor found",
      "platform": "unknown"
    }
  ],
  "total_size": 18874368,
  "processing_time": 45.23
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `total` | Total number of URLs processed |
| `successful` | Number of successful downloads |
| `failed` | Number of failed downloads |
| `skipped` | Number of skipped (already downloaded) videos |
| `results` | Array of download results for each URL |
| `results[].success` | Boolean indicating if download succeeded |
| `results[].error` | Error message if download failed |
| `results[].file_path` | Server path to downloaded file (if keep=true) |
| `results[].file_size` | File size in bytes |
| `total_size` | Total size of all downloaded files in bytes |
| `processing_time` | Total time taken in seconds |

### Features

- **Independent Error Handling**: One video failure doesn't stop the batch
- **Duplicate Detection**: Skips already downloaded files (when keep=true)
- **Platform Detection**: Automatically identifies source platform
- **Automatic Rate Limiting**: Built-in delays between downloads
- **Cookie Support**: Use cookies for authenticated/private content

### Best Practices

1. **Limit batch size**: Recommend 10-50 URLs per request
2. **Use keep=true for archives**: Prevent re-downloading same videos
3. **Handle partial failures**: Check individual results for errors
4. **Monitor disk space**: Large batches can consume significant storage

---

## 3. Subtitle Extraction Endpoint

### `GET /subtitles`

**Description**: Extracts and returns existing video subtitles/captions from supported platforms. Downloads subtitle content directly and parses it into various formats. This is a FREE and INSTANT method - no AI processing required.

**Authentication**: Required

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | Video URL from any supported platform |
| `lang` | string | No | `"en"` | Language code for subtitles |
| `format` | string | No | `"text"` | Output format for transcription |
| `auto` | boolean | No | `true` | Include auto-generated captions |

### Format Options

| Format | Description | Output |
|--------|-------------|--------|
| `text` | Plain text transcript | Clean text with word count |
| `json` | Structured data with metadata | Same as `segments` |
| `segments` | Timestamped segments | Array of timed text segments |
| `srt` | Raw SRT subtitle format | Original SRT content |
| `vtt` | Raw VTT subtitle format | Original VTT content |

### Language Options

Common language codes:
- `en` - English
- `es` - Spanish  
- `fr` - French
- `de` - German
- `ja` - Japanese
- `ko` - Korean
- `zh` - Chinese
- `ar` - Arabic

**Note**: Language codes vary by platform:
- YouTube: Often uses simple codes (`en`, `es`, `fr`)
- TikTok: Uses region-specific codes (`eng-US`, `ara-SA`)
- Use `/transcription/locales` endpoint to get exact codes for a video

*Fallback: If specified language not found, tries `en`, `en-US`, `en-GB`*

### Important Notes on Subtitle Availability

1. **Check availability first**: Use `/transcription/locales` to verify which languages are available before requesting transcriptions
2. **Platform variations**: Different platforms have different subtitle availability patterns
3. **Manual vs Auto**: Manual subtitles are more accurate than auto-generated captions

### Example Requests

**Get plain text transcript**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/subtitles?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&lang=en&format=text"
```

**Get timestamped segments in JSON**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/subtitles?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format=json"
```

**Get Spanish subtitles in SRT format**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/subtitles?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&lang=es&format=srt"
```

### Response Examples

**Text Format Response**:
```json
{
  "transcript": "Hello, welcome to this video. Today we'll discuss the importance of value propositions...",
  "word_count": 1250,
  "title": "Video Title",
  "duration": 300,
  "language": "en",
  "source_format": "vtt"
}
```

**Segments Format Response**:
```json
{
  "title": "Video Title",
  "duration": 300,
  "language": "en",
  "source_format": "srt",
  "segments": [
    {
      "start": "00:00:00,000",
      "end": "00:00:03,000",
      "text": "Hello, welcome to this video."
    },
    {
      "start": "00:00:03,000",
      "end": "00:00:07,500",
      "text": "Today we'll discuss the importance of value propositions."
    }
  ],
  "full_text": "Hello, welcome to this video. Today we'll discuss the importance of value propositions.",
  "word_count": 1250,
  "segment_count": 85
}
```

**SRT Format Response**:
```json
{
  "title": "Video Title",
  "language": "en",
  "format": "srt",
  "content": "1\n00:00:00,000 --> 00:00:03,000\nHello, welcome to this video.\n\n2\n00:00:03,000 --> 00:00:07,500\nToday we'll discuss the importance of value propositions.\n",
  "source_format": "srt"
}
```

### Error Responses

**No subtitles available**:
```json
{
  "error": "No subtitles found for language 'es'",
  "available_languages": ["en", "en-US", "fr"],
  "title": "Video Title",
  "duration": 300
}
```

**Subtitle download failed**:
```json
{
  "detail": "Failed to download subtitle content: HTTP 404 Not Found"
}
```

**Invalid format**:
```json
{
  "detail": "Invalid format. Use: text, json, segments, srt, or vtt"
}
```

---

## 4. Audio Extraction Endpoint

### `POST /extract-audio`

**Description**: Extracts audio from video URL or local file. Returns audio file path on server for use with `/transcribe` endpoint. Audio files are stored in `/tmp/` and automatically cleaned up after 1 hour.

**Authentication**: Required

### Parameters (Query String)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | No* | - | Video URL to extract audio from |
| `local_file` | string | No* | - | Path to local video file (alternative to url) |
| `output_format` | string | No | `"mp3"` | Audio format: mp3, m4a, wav |
| `quality` | string | No | `"192"` | Audio quality/bitrate (e.g., "192", "320") |
| `cookies_file` | string | No | `null` | Path to cookies file for authentication |

*Either `url` OR `local_file` must be provided (not both)

### Example Requests

**Extract audio from YouTube video**:
```bash
curl -X POST "http://localhost:8000/extract-audio?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&output_format=mp3&quality=192" \
  -H "X-Api-Key: your-key"
```

**Extract audio from local file**:
```bash
curl -X POST "http://localhost:8000/extract-audio?local_file=/path/to/video.mp4&output_format=wav" \
  -H "X-Api-Key: your-key"
```

### Response Example

```json
{
  "audio_file": "/tmp/a3b2c1d4.mp3",
  "format": "mp3",
  "size": 4567890,
  "title": "Rick Astley - Never Gonna Give You Up",
  "source_type": "url",
  "video_id": "dQw4w9WgXcQ",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "duration": 212,
  "platform": "youtube",
  "message": "Audio extracted successfully. Use this audio_file path with POST /transcribe",
  "expires_in": "1 hour (automatic cleanup)"
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `audio_file` | Server path to extracted audio file (use with /transcribe) |
| `format` | Audio format (mp3, m4a, wav) |
| `size` | File size in bytes |
| `title` | Video/file title |
| `source_type` | Either "url" or "local_file" |
| `video_id` | Platform video ID (or MD5 hash for local files) |
| `url` | Original video URL (null for local files) |
| `duration` | Video duration in seconds (null if unavailable) |
| `platform` | Platform name (youtube, tiktok, local, etc.) |
| `message` | Next step instructions |
| `expires_in` | Cleanup time for temp files |

### Usage Notes

1. **For URLs**: Uses yt-dlp to download ONLY audio (not full video) with `bestaudio/best` format
2. **For local files**: Uses FFmpeg to extract audio directly from file
3. **Temporary Storage**: Audio files stored in `/tmp/` with automatic cleanup after 1 hour
4. **Next Step**: Pass `audio_file` path to `POST /transcribe` for AI transcription
5. **Metadata Passthrough**: Copy `video_id`, `url`, `duration`, `platform` to `/transcribe` for unified response format

### Error Responses

```json
{
  "detail": "Either 'url' or 'local_file' parameter must be provided"
}
```

```json
{
  "detail": "Local file not found: /path/to/video.mp4"
}
```

---

## 5. AI Transcription Endpoint

### `POST /transcribe`

**Description**: AI-powered transcription using whisperX (local) or OpenAI Whisper API. Returns transcription in multiple formats with word-level timestamps. Requires audio file from `/extract-audio` endpoint.

**Authentication**: Required

### Parameters (Query String)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio_file` | string | Yes | - | Path to audio file on server (from /extract-audio) |
| `language` | string | No | auto-detect | Language code (e.g., "en", "es", "fr") |
| `model_size` | string | No | `"medium"` | Model: tiny, small, medium, large-v2, large-v3, turbo |
| `provider` | string | No | `"local"` | Provider: local (whisperX) or openai |
| `output_format` | string | No | `"json"` | Format: json, srt, vtt, text |
| `video_id` | string | No | - | Video ID from /extract-audio (for unified response) |
| `url` | string | No | - | Video URL from /extract-audio (for unified response) |
| `duration` | int | No | - | Video duration from /extract-audio (for unified response) |
| `platform` | string | No | - | Platform name from /extract-audio (for unified response) |

### Provider Options

| Provider | Cost | Speed | Features |
|----------|------|-------|----------|
| `local` (whisperX) | $0 | 70x real-time (GPU), 3-5x (CPU) | Word-level timestamps, runs on any hardware |
| `openai` | $0.006/min | 5-30s per video | Managed service, no setup required |

### Model Size Options

| Model | Size | Speed | Accuracy | Best For |
|-------|------|-------|----------|----------|
| `tiny` | 39MB | Fastest | Lower | Quick drafts, testing |
| `small` | 244MB | Very fast | Good | Balanced performance |
| `medium` | 769MB | Fast | Very good | Default recommended |
| `large-v2` | 1.5GB | Slower | Highest | Production quality |
| `large-v3` | 1.5GB | Slower | Highest | Latest production |
| `turbo` | 809MB | **Best balance** | Excellent | **Recommended** |

### Example Requests

**Complete workflow with unified response**:
```bash
# Step 1: Extract audio and get metadata
RESPONSE=$(curl -X POST "http://localhost:8000/extract-audio?url=https://youtube.com/watch?v=dQw4w9WgXcQ" \
  -H "X-Api-Key: your-key")

AUDIO_FILE=$(echo $RESPONSE | jq -r '.audio_file')
VIDEO_ID=$(echo $RESPONSE | jq -r '.video_id')
URL=$(echo $RESPONSE | jq -r '.url')
DURATION=$(echo $RESPONSE | jq -r '.duration')
PLATFORM=$(echo $RESPONSE | jq -r '.platform')

# Step 2: Transcribe with metadata for unified response
curl -X POST "http://localhost:8000/transcribe?audio_file=$AUDIO_FILE&video_id=$VIDEO_ID&url=$URL&duration=$DURATION&platform=$PLATFORM&model_size=turbo&output_format=json" \
  -H "X-Api-Key: your-key"
```

**Simple transcription (minimal)**:
```bash
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a3b2c1d4.mp3&output_format=json" \
  -H "X-Api-Key: your-key"
```

**With specific language and model**:
```bash
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a3b2c1d4.mp3&language=en&model_size=turbo&provider=local&output_format=srt" \
  -H "X-Api-Key: your-key"
```

### Response Examples

**JSON Format (Unified Response)**:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "a3b2c1d4.mp3",
  "duration": 212,
  "language": "en",
  "source": "ai",
  "provider": "local",
  "model": "turbo",
  "source_format": null,
  "segments": [
    {"start": 0.031, "end": 16.028, "text": "We're no strangers to love"},
    {"start": 16.028, "end": 39.029, "text": "You know the rules and so do I"}
  ],
  "full_text": "We're no strangers to love You know the rules and so do I...",
  "word_count": 253,
  "segment_count": 12,
  "metadata": {
    "created_at": "2025-12-14T12:30:00Z",
    "platform": "youtube",
    "transcription_time": 15.42
  }
}
```

**SRT Format**:
```
1
00:00:00,031 --> 00:00:16,028
We're no strangers to love

2
00:00:16,028 --> 00:00:39,029
You know the rules and so do I
```

**Text Format**:
```json
{
  "transcript": "We're no strangers to love You know the rules and so do I...",
  "word_count": 253
}
```

### Response Fields (JSON Format)

| Field | Description |
|-------|-------------|
| `video_id` | Video ID from /extract-audio or MD5 hash for local files |
| `url` | Original video URL (null for local files) |
| `title` | Audio filename or video title |
| `duration` | Video duration in seconds |
| `language` | Detected or specified language code |
| `source` | Always "ai" for this endpoint |
| `provider` | "local" (whisperX) or "openai" |
| `model` | Model size used (e.g., "turbo", "medium") |
| `segments` | Array of timestamped text segments |
| `segments[].start` | Start time in float seconds (e.g., 0.031) |
| `segments[].end` | End time in float seconds |
| `full_text` | Complete transcription text |
| `word_count` | Total word count |
| `segment_count` | Number of segments |
| `metadata.transcription_time` | Processing time in seconds |

### Performance Notes

- **GPU (NVIDIA/MPS)**: 70x faster than real-time (10-min video in ~8s)
- **CPU**: 3-5x faster than real-time (10-min video in 2-3 min)
- **Railway Compatible**: Works in CPU mode on Railway deployment
- **Memory**: 2-12GB RAM depending on model size
- **Concurrency**: Limited to prevent memory overload (queued if busy)

### Error Responses

```json
{
  "detail": "Audio file not found: /tmp/xyz.mp3. Did you run /extract-audio first?"
}
```

```json
{
  "detail": "Invalid provider 'invalid'. Must be one of: local, openai"
}
```

```json
{
  "detail": "Local provider error: whisperX not installed. Run: pip install whisperx OR use provider=openai"
}
```

### Unified Response Format

**Important**: Both `/subtitles` (format=json) and `/transcribe` (output_format=json) return the same unified structure for easy database storage. The key differences:

| Field | /subtitles | /transcribe |
|-------|-----------|-------------|
| `source` | "subtitle" | "ai" |
| `provider` | Platform name (youtube, tiktok) | "local" or "openai" |
| `model` | null | Model name (turbo, medium, etc.) |
| `source_format` | Original format (srt, vtt) | null |
| `metadata.transcription_time` | null | Processing time in seconds |

---

## 6. Get Available Transcription Locales Endpoint

### `GET /transcription/locales`

**Description**: Retrieves all available subtitle/caption languages for a video without downloading the video or subtitles. Useful for building language selectors and checking availability before requesting transcriptions.

**Authentication**: Required

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | Video URL from any supported platform |

### Example Request

```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/transcription/locales?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Example Response

```json
{
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration": 213,
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "locales": [
    {
      "code": "en",
      "name": "English",
      "type": ["manual"],
      "formats": ["vtt", "srt"]
    },
    {
      "code": "es",
      "name": "Spanish",
      "type": ["manual", "auto"],
      "formats": ["vtt", "srt"]
    },
    {
      "code": "fr",
      "name": "French",
      "type": ["auto"],
      "formats": ["vtt"]
    }
  ],
  "summary": {
    "total": 3,
    "manual_count": 2,
    "auto_count": 2,
    "has_manual": true,
    "has_auto": true
  }
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `title` | Video title |
| `duration` | Video duration in seconds |
| `url` | Original video URL |
| `locales` | Array of available language locales |
| `locales[].code` | Language code (e.g., "en", "en-US", "ara-SA") |
| `locales[].name` | Human-readable language name |
| `locales[].type` | Array indicating subtitle type: ["manual"], ["auto"], or ["manual", "auto"] |
| `locales[].formats` | Available subtitle formats (typically "vtt" or "srt") |
| `summary.total` | Total number of available locales |
| `summary.manual_count` | Number of languages with manual subtitles |
| `summary.auto_count` | Number of languages with auto-generated captions |
| `summary.has_manual` | Boolean indicating if any manual subtitles exist |
| `summary.has_auto` | Boolean indicating if any auto-generated captions exist |

### Subtitle Types

- **Manual**: Human-created subtitles, typically higher quality and more accurate
- **Auto**: Auto-generated captions using speech recognition (mainly on YouTube)

### Usage Notes

1. **Platform Differences**:
   - YouTube often has both manual and auto-generated captions in many languages
   - TikTok, Instagram, and other platforms typically only have manual subtitles
   - Auto-generated captions may have transcription errors

2. **Language Code Formats**:
   - Simple codes: `en`, `es`, `fr`
   - Region-specific: `en-US`, `en-GB`, `pt-BR`
   - Platform-specific: `eng-US`, `ara-SA` (TikTok format)

3. **Platform-Specific Language Codes**:

   **Arabic variations**:
   - TikTok: `ara-SA` (Arabic - Saudi Arabia)
   - YouTube: `ar` (generic Arabic)
   - Other platforms: `ar-SA`, `ar-EG`, etc.

   **English variations**:
   - TikTok: `eng-US` (English - US)
   - YouTube: `en`, `en-US`, `en-GB`
   - Other platforms: various regional formats

   **Important**: Always use the exact code returned by `/transcription/locales` when calling `/transcription`. The same language can have different codes on different platforms.

4. **Best Practices**:
   - Call this endpoint before `/transcription` to verify language availability
   - Prefer manual subtitles over auto-generated when both are available
   - Cache the results as subtitle availability rarely changes

### Integration Examples

**Finding the correct language code across platforms:**

```javascript
// Get available languages first
const localesResponse = await fetch('http://localhost:8000/transcription/locales?url=' + videoUrl, {
  headers: { 'X-Api-Key': apiKey }
});
const locales = await localesResponse.json();

// Example 1: Finding English (varies by platform)
const englishLocale = locales.locales.find(l => 
  l.code === 'en' ||        // YouTube
  l.code === 'en-US' ||     // YouTube regional
  l.code === 'eng-US'       // TikTok
);

// Example 2: Finding Arabic (varies by platform)  
const arabicLocale = locales.locales.find(l =>
  l.code === 'ar' ||        // YouTube
  l.code === 'ara-SA' ||    // TikTok
  l.code === 'ar-SA'        // Other platforms
);

// Use the exact code found
if (englishLocale) {
  const transcriptResponse = await fetch(
    `http://localhost:8000/transcription?url=${videoUrl}&lang=${englishLocale.code}`,
    { headers: { 'X-Api-Key': apiKey } }
  );
}
```

**Platform-aware approach:**

```javascript
// Better approach: Use the language name from the response
const locales = await getLocales(videoUrl);

// Find by language name (more reliable across platforms)
const arabicLocale = locales.locales.find(l => 
  l.name.toLowerCase().includes('arabic')
);

const englishLocale = locales.locales.find(l => 
  l.name.toLowerCase().includes('english')
);

// This works regardless of whether it's 'ar', 'ara-SA', etc.
if (arabicLocale) {
  await getTranscription(videoUrl, arabicLocale.code);
}
```

---

## 7. Get Playlist Information Endpoint

### `GET /playlist/info`

**Description**: Extracts metadata from YouTube playlists or channel videos without downloading. Returns a list of video URLs that can be used with existing `/download` and `/transcription` endpoints. Supports filtering by upload date and selecting specific videos.

**Authentication**: Required

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | YouTube playlist or channel URL |
| `dateafter` | string | No | - | Filter videos uploaded after this date |
| `datebefore` | string | No | - | Filter videos uploaded before this date |
| `max_items` | integer | No | - | Maximum number of videos to return |
| `items` | string | No | - | Select specific videos by index |

### Date Filter Format

Date parameters support two formats:

1. **Absolute dates**: `YYYYMMDD` format
   - Example: `20240101` (January 1, 2024)
   - Example: `20231225` (December 25, 2023)

2. **Relative dates**: Based on current date
   - `today` - Current date
   - `yesterday` - Yesterday's date
   - `today-1week` or `now-7days` - 7 days ago
   - `today-1month` - 1 month ago
   - `today-1year` - 1 year ago
   - Pattern: `[now|today|yesterday][-N[day|week|month|year]]`

### Item Selection Format

The `items` parameter allows precise video selection:
- Range: `1:5` - Videos 1 through 5
- Specific: `1,3,5,7` - Videos at indices 1, 3, 5, and 7
- Mixed: `1:3,7,10:15` - Videos 1-3, 7, and 10-15
- Reverse: `-5:` - Last 5 videos
- Step: `1:10:2` - Every 2nd video from 1 to 10

### Example Requests

**Get all videos from a playlist**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/playlist/info?url=https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
```

**Get videos uploaded in last week**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/playlist/info?url=PLAYLIST_URL&dateafter=today-1week"
```

**Get first 10 videos from 2024**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/playlist/info?url=PLAYLIST_URL&dateafter=20240101&max_items=10"
```

**Get specific videos by index**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/playlist/info?url=PLAYLIST_URL&items=1,5,10"
```

### Example Response

```json
{
  "playlist_title": "Select Lectures",
  "playlist_url": "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
  "channel": "Lex Fridman",
  "channel_id": "@lexfridman",
  "channel_url": "https://www.youtube.com/@lexfridman",
  "video_count": 2,
  "total_count": 25,
  "videos": [
    {
      "url": "https://www.youtube.com/watch?v=0VH1Lim8gL8",
      "title": "Deep Learning State of the Art (2020)",
      "duration": "1:27:41",
      "duration_seconds": 5261,
      "upload_date": "2020-01-15",
      "index": 1,
      "id": "0VH1Lim8gL8",
      "views": 1300000,
      "description": "MIT Deep Learning Lecture on the state of the art in deep learning..."
    },
    {
      "url": "https://www.youtube.com/watch?v=O5xeyoRL95U",
      "title": "Deep Learning Basics: Introduction and Overview",
      "duration": "1:08:06",
      "duration_seconds": 4086,
      "upload_date": "2019-02-04",
      "index": 2,
      "id": "O5xeyoRL95U",
      "views": 2400000
    }
  ],
  "filters_applied": {
    "dateafter": null,
    "datebefore": null,
    "max_items": null,
    "items": null
  }
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `playlist_title` | Name of the playlist or channel |
| `playlist_url` | URL of the playlist |
| `channel` | Channel/uploader name |
| `channel_id` | Channel identifier |
| `channel_url` | URL to the channel |
| `video_count` | Number of videos returned (after filtering) |
| `total_count` | Total videos in playlist (before filtering) |
| `videos` | Array of video information |
| `videos[].url` | Direct URL to the video |
| `videos[].title` | Video title |
| `videos[].duration` | Duration in HH:MM:SS or MM:SS format |
| `videos[].duration_seconds` | Duration in seconds |
| `videos[].upload_date` | Upload date (YYYY-MM-DD format) |
| `videos[].index` | Position in the playlist |
| `videos[].id` | Video ID |
| `videos[].views` | View count (if available) |
| `videos[].description` | Truncated description (first 200 chars) |
| `filters_applied` | Shows which filters were used |

### Single Video Handling

If a single video URL is provided instead of a playlist, the endpoint will return it wrapped as a single-item playlist for consistency:

```json
{
  "playlist_title": "Single Video",
  "playlist_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "channel": "Rick Astley",
  "video_count": 1,
  "videos": [
    {
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "title": "Never Gonna Give You Up",
      "duration": "3:33",
      "index": 1,
      "id": "dQw4w9WgXcQ"
    }
  ]
}
```

### Usage with Other Endpoints

The video URLs returned can be used directly with other endpoints:

**1. Download specific videos from playlist**:
```bash
# First, get playlist info
PLAYLIST_INFO=$(curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/playlist/info?url=PLAYLIST_URL&max_items=5")

# Extract first video URL (using jq)
VIDEO_URL=$(echo $PLAYLIST_INFO | jq -r '.videos[0].url')

# Download the video
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/download?url=$VIDEO_URL&format=best[height<=720]" \
  --output video.mp4
```

**2. Transcribe all recent videos**:
```javascript
// Get recent videos (last week)
const response = await fetch(
  'http://localhost:8000/playlist/info?url=PLAYLIST_URL&dateafter=today-1week',
  { headers: { 'X-Api-Key': apiKey } }
);
const playlist = await response.json();

// Transcribe each video
for (const video of playlist.videos) {
  const transcriptResponse = await fetch(
    `http://localhost:8000/transcription?url=${video.url}&format=text`,
    { headers: { 'X-Api-Key': apiKey } }
  );
  const transcript = await transcriptResponse.json();
  console.log(`${video.title}: ${transcript.word_count} words`);
}
```

### Practical Use Cases

1. **Monitor channels for new content**:
   - Use `dateafter=today-1day` to check for videos uploaded in last 24 hours
   - Automate transcription of new videos

2. **Batch download playlists**:
   - Get playlist info with desired filters
   - Loop through video URLs to download each

3. **Content analysis**:
   - Extract metadata for multiple videos
   - Analyze upload patterns, video lengths, view counts

4. **Selective processing**:
   - Use `items` parameter to process specific videos
   - Filter by date range for historical content

### Best Practices

1. **Use filters to reduce response size**: Large playlists can return hundreds of videos
2. **Cache playlist info**: Video metadata doesn't change frequently
3. **Implement pagination**: Use `items` parameter for large playlists
4. **Check `total_count` vs `video_count`**: Understand how many videos were filtered out
5. **Handle unavailable videos**: Some videos may be private or deleted (returned as null entries)

### Limitations

- Only works with YouTube playlists and channels currently
- Date filtering depends on YouTube providing upload dates
- Some metadata may be unavailable for certain videos
- Private or age-restricted videos may have limited information

### Error Responses

```json
{
  "detail": "Error extracting playlist info: Invalid playlist URL"
}
```

```json
{
  "detail": "Error extracting playlist info: This playlist is private"
}
```

---

## 8. List Downloads Endpoint

### `GET /downloads/list`

**Description**: Lists all videos saved to server storage (when `keep=true` was used in `/download`).

**Authentication**: Required

**Parameters**: None

### Example Request

```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/downloads/list"
```

### Example Response

```json
{
  "downloads": [
    {
      "filename": "Video_Title_1_20240823_143020.mp4",
      "size": 15728640,
      "created": "2024-08-23T14:30:20.123456",
      "path": "./downloads/Video_Title_1_20240823_143020.mp4"
    },
    {
      "filename": "Another_Video_20240823_143145.mp4", 
      "size": 8945120,
      "created": "2024-08-23T14:31:45.789012",
      "path": "./downloads/Another_Video_20240823_143145.mp4"
    }
  ],
  "count": 2
}
```

### File Size

File sizes are returned in bytes. Common conversions:
- 1 MB = 1,048,576 bytes
- 1 GB = 1,073,741,824 bytes

---

## 9. Supabase Transcription Storage (Optional)

### `POST /transcriptions/save`

**Description**: Saves transcription data to Supabase `document_transcriptions` table for persistent storage. Uses UPSERT behavior - updates existing transcription if found, otherwise inserts new record.

**Authentication**: Required

**Requirements**:
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` environment variables must be configured
- Document record must already exist in `documents` table with matching `document_id`

### Parameters

Request body (JSON):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `document_id` | string (UUID) | Yes | Foreign key to existing document record |
| `segments` | array | Yes | Transcription segments with start, end, text |
| `language` | string | Yes | Language code (max 5 chars, e.g., "en") |
| `source` | string | Yes | Source type: "subtitle" or "ai" (max 50 chars) |
| `confidence_score` | float | No | Confidence score 0.0-1.0 (null for subtitles) |
| `metadata` | object | No | Additional metadata as JSONB |

### Example Request

```bash
curl -X POST "http://localhost:8000/transcriptions/save" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-key" \
  -d '{
    "document_id": "4801fa8c-da28-4b7b-b039-cd696bc8a8bb",
    "segments": [
      {"start": 0.031, "end": 16.028, "text": "Hello world"},
      {"start": 16.028, "end": 39.029, "text": "Welcome to the video"}
    ],
    "language": "en",
    "source": "ai",
    "confidence_score": 0.95,
    "metadata": {
      "model": "whisper-turbo",
      "provider": "local",
      "transcription_time": 97.95
    }
  }'
```

### Example Response

```json
{
  "id": "1d18f01d-1151-4fe7-a697-26adbb79adf3",
  "document_id": "4801fa8c-da28-4b7b-b039-cd696bc8a8bb",
  "created_at": "2025-11-08T12:00:58.043902+00:00",
  "message": "Transcription saved successfully to Supabase with ID: 1d18f01d-1151-4fe7-a697-26adbb79adf3"
}
```

### Storage Behavior

- **Database Storage Only**: Transcription data stored in PostgreSQL JSONB column, no files created
- **UPSERT Logic**: If transcription exists for `document_id`, it updates; otherwise inserts
- **Auto Timestamps**: `updated_at` automatically updated via PostgreSQL trigger
- **Foreign Key Constraint**: Validates `document_id` exists in `documents` table
- **Unique Constraint**: Only one transcription per document allowed

### `GET /transcriptions/check/{document_id}`

**Description**: Checks if a transcription exists for a given document without retrieving full segments data.

**Authentication**: Required

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `document_id` | string (UUID) | Yes | Document UUID to check (path parameter) |

### Example Request

```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/transcriptions/check/4801fa8c-da28-4b7b-b039-cd696bc8a8bb"
```

### Example Response (Exists)

```json
{
  "exists": true,
  "document_id": "4801fa8c-da28-4b7b-b039-cd696bc8a8bb",
  "transcription": {
    "id": "1d18f01d-1151-4fe7-a697-26adbb79adf3",
    "language": "en",
    "source": "ai",
    "confidence_score": 0.95,
    "created_at": "2025-11-08T12:00:58.043902+00:00",
    "updated_at": "2025-11-08T12:01:13.558306+00:00"
  }
}
```

### Example Response (Not Exists)

```json
{
  "exists": false,
  "document_id": "4801fa8c-da28-4b7b-b039-cd696bc8a8bb",
  "transcription": null
}
```

### Common Workflow

```bash
# 1. Check if transcription already exists
curl -H "X-Api-Key: $API_KEY" \
  "http://localhost:8000/transcriptions/check/$DOCUMENT_ID"

# 2. If not exists, get transcription from video
curl -H "X-Api-Key: $API_KEY" \
  "http://localhost:8000/subtitles?url=$VIDEO_URL&format=json" > transcription.json

# 3. Save to Supabase (add document_id to JSON)
curl -X POST "http://localhost:8000/transcriptions/save" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $API_KEY" \
  -d @transcription_with_document_id.json
```

### Error Responses

**Supabase not configured**:
```json
{
  "detail": "Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables."
}
```

**Foreign key constraint violation**:
```json
{
  "detail": "Error saving transcription to Supabase: {'message': 'insert or update on table \"document_transcriptions\" violates foreign key constraint \"document_transcriptions_document_id_fkey\"', ...}"
}
```

### Setup Requirements

See [docs/supabase-integration.md](supabase-integration.md) for complete setup instructions including:
- Database schema SQL
- Environment variable configuration
- Advanced querying examples

---

## Supported Platforms

The API supports video downloads and transcriptions from 1000+ platforms including:

- **Video Platforms**: YouTube, Vimeo, DailyMotion
- **Social Media**: TikTok, Instagram, Facebook, Twitter (X)
- **Live Streaming**: Twitch, YouTube Live
- **Educational**: Coursera, edX, Khan Academy
- **News**: CNN, BBC, Reuters
- **And many more**: See [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

---

## Rate Limits and Best Practices

### Recommendations
- Use appropriate video quality formats to avoid large downloads
- Implement client-side timeouts for long video downloads
- Clean up downloaded files regularly if using `keep=true`
- Cache transcriptions on your end to avoid repeated API calls
- Use `format=text` for AI processing, `format=segments` for subtitle display

### Error Handling
- Always check for HTTP error status codes
- Handle cases where videos are private, deleted, or geo-blocked
- Implement retry logic for temporary network failures
- Parse error messages for specific failure reasons

---

## Common Workflows & Examples

This section shows real-world usage patterns for common tasks.

### Workflow 1: Extract Subtitles from YouTube Video

**Scenario:** Get transcription from a video that has existing subtitles (free & instant).

```bash
GET /subtitles?url=https://youtube.com/watch?v=dQw4w9WgXcQ&format=json&lang=en
```

**Response:** Returns unified format with:
- `source="subtitle"`
- `provider="youtube"`
- `video_id="dQw4w9WgXcQ"`
- Full transcription segments with timestamps

**Use When:** Video has existing subtitles (YouTube, TikTok, educational content)

---

### Workflow 2: AI Transcription with Complete Metadata

**Scenario:** Transcribe video without subtitles and maintain full metadata for database storage.

**Step 1:** Extract audio and get metadata
```bash
POST /extract-audio?url=https://youtube.com/watch?v=dQw4w9WgXcQ
```

**Returns:**
```json
{
  "audio_file": "/tmp/abc123.mp3",
  "video_id": "dQw4w9WgXcQ",
  "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "duration": 212,
  "platform": "youtube"
}
```

**Step 2:** Transcribe with metadata
```bash
POST /transcribe?audio_file=/tmp/abc123.mp3&video_id=dQw4w9WgXcQ&url=https://youtube.com/watch?v=dQw4w9WgXcQ&duration=212&platform=youtube&output_format=json
```

**Returns:** Unified format with:
- `source="ai"`
- `provider="local"` (or "openai")
- All metadata included
- Complete transcription segments

**Use When:** Video has no subtitles, need complete metadata for database storage

---

### Workflow 3: Local File Transcription

**Scenario:** Transcribe a local video file that you already have downloaded.

**Step 1:** Extract audio from local file
```bash
POST /extract-audio?local_file=/path/to/video.mp4
```

**Returns:**
```json
{
  "audio_file": "/tmp/xyz789.mp3",
  "video_id": "a3f2c8d91b4e",
  "url": null,
  "duration": null,
  "platform": "local"
}
```

**Step 2:** Transcribe
```bash
POST /transcribe?audio_file=/tmp/xyz789.mp3&video_id=a3f2c8d91b4e&platform=local&output_format=json
```

**Returns:** Unified format with:
- `url=null` (no URL for local files)
- `video_id` is MD5 hash of filename
- `platform="local"`

**Use When:** Processing local video files, offline transcription

---

### Workflow 4: Smart Transcription (Subtitles First, AI Fallback)

**Scenario:** Optimize cost and speed by trying subtitles first, falling back to AI if unavailable.

**Step 1:** Try subtitles first
```bash
GET /subtitles?url=VIDEO_URL&format=json&lang=en
```

**Step 2:** Check response status
- If `200 OK`: Use subtitle transcription (instant, free)
- If `404 Not Found`: Continue to AI transcription

**Step 3:** AI Fallback (if needed)
```bash
POST /extract-audio?url=VIDEO_URL
POST /transcribe?audio_file=AUDIO_PATH&output_format=json
```

**Result:** Get transcription in unified JSON format regardless of source

**Use When:** Always - this is the optimal workflow for any video

---

### Workflow 5: Transcribe and Save to Supabase

**Scenario:** Get transcription and store in Supabase database for persistent storage.

**Step 1:** Get transcription (try subtitles first)
```bash
GET /subtitles?url=VIDEO_URL&format=json
# OR
POST /extract-audio?url=VIDEO_URL
POST /transcribe?audio_file=AUDIO_PATH&output_format=json
```

**Step 2:** Prepare transcription data
```json
{
  "document_id": "4801fa8c-da28-4b7b-b039-cd696bc8a8bb",
  "segments": [...],
  "language": "en",
  "source": "ai",
  "confidence_score": 0.95,
  "metadata": {
    "model": "turbo",
    "provider": "local"
  }
}
```

**Step 3:** Save to Supabase
```bash
POST /transcriptions/save
```

**Result:** Transcription saved with UPSERT (updates if exists, inserts if new)

**Use When:** Need persistent storage, building a content library, LLM processing

---

### Workflow 6: Extract Screenshots from Video

**Scenario:** Get screenshots from specific timestamps in a video.

```bash
POST /screenshot/video
{
  "video_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "timestamps": ["00:01:30,500", "90.5", "00:02:00,000"],
  "quality": 2
}
```

**Result:** Screenshots saved to `./cache/screenshots/` with metadata

**Use When:** Creating video thumbnails, visual analysis, content moderation

---

### Workflow 7: Process YouTube Playlist

**Scenario:** Batch process all videos in a YouTube playlist.

**Step 1:** Get playlist info
```bash
GET /playlist/info?url=PLAYLIST_URL&dateafter=today-1week&max_items=10
```

**Step 2:** Loop through videos
```javascript
// Example in JavaScript
const playlist = await getPlaylistInfo(playlistUrl);

for (const video of playlist.videos) {
  // Download
  await downloadVideo(video.url);

  // Or transcribe
  const audio = await extractAudio(video.url);
  const transcription = await transcribe(audio.audio_file);
}
```

**Use When:** Batch downloading, channel monitoring, playlist archiving

---

### Response Format Examples

All transcription endpoints (`/subtitles` and `/transcribe`) return data in these formats:

#### JSON Format (Unified Response)
```json
{
  "video_id": "dQw4w9WgXcQ",
  "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "Video Title",
  "duration": 630,
  "language": "en",
  "source": "subtitle",
  "provider": "youtube",
  "model": null,
  "source_format": "srt",
  "segments": [
    {"start": 0.24, "end": 3.5, "text": "Hello, welcome to the video."},
    {"start": 3.5, "end": 7.2, "text": "Today we'll discuss..."}
  ],
  "full_text": "Hello, welcome to the video. Today we'll discuss...",
  "word_count": 245,
  "segment_count": 35,
  "metadata": {
    "created_at": "2025-11-08T10:30:00Z",
    "platform": "youtube"
  }
}
```

#### SRT Format (Subtitle Files)
```srt
1
00:00:00,000 --> 00:00:03,500
Hello, welcome to the video.

2
00:00:03,500 --> 00:00:07,200
Today we'll discuss transcription.
```

#### VTT Format (WebVTT for Web Players)
```vtt
WEBVTT

00:00:00.000 --> 00:00:03.500
Hello, welcome to the video.

00:00:03.500 --> 00:00:07.200
Today we'll discuss transcription.
```

#### Text Format (Plain Text)
```json
{
  "transcript": "Hello, welcome to the video. Today we'll discuss transcription...",
  "word_count": 245,
  "title": "Video Title"
}
```

---

### Video Quality Format Options

Common format strings for quality selection in `/download` and `/batch-download`:

| Format String | Quality | Description |
|---------------|---------|-------------|
| `best` | Highest available | Downloads best quality (can be very large) |
| `best[height<=360]` | 360p or lower | SD quality, smaller files |
| `best[height<=720]` | 720p or lower | HD ready, good balance |
| `best[height<=1080]` | 1080p or lower | Full HD, larger files |
| `best[height<=1440]` | 1440p or lower | 2K quality |
| `best[height<=2160]` | 2160p or lower | 4K quality, very large files |
| `worst` | Lowest available | Smallest file size |

**Examples:**
```bash
# Download 720p video
GET /download?url=VIDEO_URL&format=best[height<=720]

# Batch download in 360p
POST /batch-download
{
  "urls": ["URL1", "URL2"],
  "format": "best[height<=360]"
}
```

---

## Integration Examples

### n8n Workflow Integration

```javascript
// n8n HTTP Request Node Configuration
{
  "method": "GET",
  "url": "http://video-downloader.railway.internal:8000/transcription",
  "headers": {
    "X-Api-Key": "your-production-key"
  },
  "qs": {
    "url": "{{$json.video_url}}",
    "format": "text",
    "lang": "en"
  }
}
```

### cURL with Environment Variable

```bash
# Set API key once
export API_KEY="your-api-key-here"

# Download video
curl -H "X-Api-Key: $API_KEY" \
  "http://localhost:8000/download?url=VIDEO_URL&keep=true" \
  --output video.mp4

# Get transcript
curl -H "X-Api-Key: $API_KEY" \
  "http://localhost:8000/transcription?url=VIDEO_URL&format=text" \
  | jq -r '.transcript' > transcript.txt
```

---

## 10. Screenshot Extraction Endpoint

### `POST /screenshot/video`

**Description**: Extracts screenshots from videos at specified timestamps. Caches downloaded videos for reuse across requests. Supports optional Supabase upload for persistent storage.

**Authentication**: Required

### Request Body (JSON)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `video_url` | string | Yes | - | Video URL from any supported platform |
| `timestamps` | array[string] | Yes | - | Array of timestamps (SRT format "00:01:30,500" or float seconds "90.5") |
| `upload_to_supabase` | boolean | No | `false` | Upload screenshots to Supabase storage |
| `document_id` | string | No | `null` | Document ID for Supabase metadata linking |
| `quality` | integer | No | `2` | FFmpeg JPEG quality 1-31 (lower = better quality) |

### Timestamp Formats

| Format | Example | Description |
|--------|---------|-------------|
| SRT/VTT | `"00:01:30,500"` | Hours:Minutes:Seconds,Milliseconds |
| Float seconds | `"90.5"` | Decimal seconds from start |

### Example Request

```bash
curl -X POST "http://localhost:8000/screenshot/video" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-key" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "timestamps": ["00:00:30,000", "00:01:00,000", "90.5"],
    "quality": 2
  }'
```

### Example Response

```json
{
  "screenshots": [
    {
      "timestamp": 30.0,
      "timestamp_formatted": "00:00:30,000",
      "file_path": "./cache/screenshots/dQw4w9WgXcQ-30000.jpg",
      "width": 1920,
      "height": 1080,
      "size_bytes": 123456,
      "supabase_url": null
    },
    {
      "timestamp": 60.0,
      "timestamp_formatted": "00:01:00,000",
      "file_path": "./cache/screenshots/dQw4w9WgXcQ-60000.jpg",
      "width": 1920,
      "height": 1080,
      "size_bytes": 134567,
      "supabase_url": null
    },
    {
      "timestamp": 90.5,
      "timestamp_formatted": "00:01:30,500",
      "file_path": "./cache/screenshots/dQw4w9WgXcQ-90500.jpg",
      "width": 1920,
      "height": 1080,
      "size_bytes": 145678,
      "supabase_url": null
    }
  ],
  "video_id": "dQw4w9WgXcQ",
  "video_title": "Rick Astley - Never Gonna Give You Up",
  "video_duration": 212,
  "video_cached": false,
  "total_extracted": 3,
  "failed_timestamps": []
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `screenshots` | Array of extracted screenshot results |
| `screenshots[].timestamp` | Timestamp in float seconds |
| `screenshots[].timestamp_formatted` | Timestamp in SRT format |
| `screenshots[].file_path` | Server path to screenshot file |
| `screenshots[].width` | Image width in pixels |
| `screenshots[].height` | Image height in pixels |
| `screenshots[].size_bytes` | File size in bytes |
| `screenshots[].supabase_url` | Public URL if uploaded to Supabase |
| `video_id` | Platform-specific video ID |
| `video_title` | Video title |
| `video_duration` | Video duration in seconds |
| `video_cached` | True if video was reused from cache |
| `total_extracted` | Number of successfully extracted screenshots |
| `failed_timestamps` | Array of timestamps that failed with error messages |

### With Supabase Upload

```bash
curl -X POST "http://localhost:8000/screenshot/video" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-key" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "timestamps": ["00:01:30,500"],
    "upload_to_supabase": true,
    "document_id": "4801fa8c-da28-4b7b-b039-cd696bc8a8bb"
  }'
```

Response with Supabase URL:
```json
{
  "screenshots": [
    {
      "timestamp": 90.5,
      "timestamp_formatted": "00:01:30,500",
      "file_path": "./cache/screenshots/dQw4w9WgXcQ-90500.jpg",
      "width": 1920,
      "height": 1080,
      "size_bytes": 145678,
      "supabase_url": "https://xxx.supabase.co/storage/v1/object/public/public_media/screenshots/dQw4w9WgXcQ/90500.jpg"
    }
  ],
  "video_id": "dQw4w9WgXcQ",
  "video_cached": true,
  "total_extracted": 1,
  "failed_timestamps": []
}
```

### Caching Behavior

- **Video Cache**: Downloaded videos are stored in `./cache/videos/` with format `{platform}-{video_id}.mp4`
- **Screenshot Cache**: Screenshots stored in `./cache/screenshots/` with format `{video_id}-{timestamp_ms}.jpg`
- **Cache TTL**: Files automatically cleaned up after `CACHE_TTL_HOURS` (default: 3 hours)
- **Reuse**: Subsequent requests for same video skip re-download (see `video_cached` field)

### Error Handling

| Condition | Status | Response |
|-----------|--------|----------|
| Missing video_url | 422 | Validation error |
| Empty timestamps | 422 | Validation error |
| Invalid timestamp format | Partial | Timestamp added to `failed_timestamps` |
| Video download failed | 500 | `"Failed to download video"` |
| FFmpeg error | Partial | Error added to `failed_timestamps` |
| Timestamp beyond video duration | Partial | Error added to `failed_timestamps` |

### Dependencies

- **FFmpeg**: Required for screenshot extraction
- **ffprobe**: Required for image dimension detection
- **Supabase**: Optional for persistent storage

---

## 11. Cache Management Endpoints

### `GET /cache`

**Description**: Lists all cached files with metadata including age, size, and expiration time. Useful for monitoring cache usage and debugging.

**Authentication**: Required

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | No | - | Filter by type: videos, audio, transcriptions, screenshots |

### Example Requests

**List all cached files**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/cache"
```

**List only cached videos**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/cache?type=videos"
```

### Example Response

```json
{
  "files": [
    {
      "filename": "YT-dQw4w9WgXcQ.mp4",
      "type": "video",
      "path": "./cache/videos/YT-dQw4w9WgXcQ.mp4",
      "size_bytes": 15728640,
      "created_at": "2025-12-14T10:30:00",
      "age_hours": 1.5,
      "expires_in_hours": 1.5
    },
    {
      "filename": "dQw4w9WgXcQ-90500.jpg",
      "type": "screenshot",
      "path": "./cache/screenshots/dQw4w9WgXcQ-90500.jpg",
      "size_bytes": 145678,
      "created_at": "2025-12-14T11:00:00",
      "age_hours": 1.0,
      "expires_in_hours": 2.0
    }
  ],
  "summary": {
    "total_files": 2,
    "total_size_bytes": 15874318,
    "ttl_hours": 3
  }
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `files` | Array of cached file information |
| `files[].filename` | Name of the cached file |
| `files[].type` | File type (video, audio, transcription, screenshot) |
| `files[].path` | Full path to the file |
| `files[].size_bytes` | File size in bytes |
| `files[].created_at` | ISO timestamp when file was created |
| `files[].age_hours` | How old the file is in hours |
| `files[].expires_in_hours` | Hours until automatic cleanup |
| `summary.total_files` | Total number of cached files |
| `summary.total_size_bytes` | Total size of all cached files |
| `summary.ttl_hours` | Configured cache TTL |

---

### `DELETE /cache/cleanup`

**Description**: Manually triggers cache cleanup, deleting all files older than the configured TTL. Can be used with cron jobs for scheduled cleanup.

**Authentication**: Required

### Example Request

```bash
curl -X DELETE -H "X-Api-Key: your-key" \
  "http://localhost:8000/cache/cleanup"
```

### Example Response

```json
{
  "message": "Cleanup complete. Deleted 5 files.",
  "deleted": {
    "videos": 2,
    "audio": 1,
    "transcriptions": 1,
    "screenshots": 1
  },
  "freed_bytes": 52428800,
  "ttl_hours": 3
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `message` | Summary message |
| `deleted` | Breakdown of deleted files by type |
| `deleted.videos` | Number of deleted video files |
| `deleted.audio` | Number of deleted audio files |
| `deleted.transcriptions` | Number of deleted transcription files |
| `deleted.screenshots` | Number of deleted screenshot files |
| `freed_bytes` | Total bytes freed |
| `ttl_hours` | Configured cache TTL |

### Automatic Cleanup

Cache cleanup is also triggered automatically:
- On each `/transcribe` request
- On each `/screenshot/video` request

### Cron Job Setup

For production deployments, set up a cron job:

```bash
# Run cleanup every hour
0 * * * * curl -X DELETE -H "X-Api-Key: your-key" "http://localhost:8000/cache/cleanup"
```

### Cache Directory Structure

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

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_DIR` | `./cache` | Base directory for all cached files |
| `CACHE_TTL_HOURS` | `3` | Hours before files are eligible for cleanup |

---

## 12. Job Queue Processing Endpoint

### `POST /jobs/video-audio-transcription`

**Description**: Process batch of video/audio transcription jobs from Supabase PGMQ queue. This endpoint is called by Supabase Edge Functions when there are pending transcription jobs in the queue.

**Authentication**: Bearer token via `Authorization` header (uses `PY_API_TOKEN` environment variable, NOT `X-Api-Key`)

### Request Body (JSON)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `queue` | string | No | `"video_audio_transcription"` | PGMQ queue name |
| `vt_seconds` | integer | No | `1800` | Visibility timeout in seconds |
| `jobs` | array[Job] | Yes | - | Array of jobs to process |

**Job Object Structure:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `msg_id` | integer | Yes | PGMQ message ID |
| `read_ct` | integer | No | Read count (retry number), defaults to 1 |
| `enqueued_at` | string | No | ISO timestamp when job was enqueued |
| `document_id` | string | Yes* | Document UUID from Supabase `documents` table |
| `message` | object | No | Nested message with `document_id` (alternative location) |

*`document_id` can be at the top level or inside `message.document_id`

### Example Request

```bash
curl -X POST "http://your-api/jobs/video-audio-transcription" \
  -H "Authorization: Bearer <PY_API_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "queue": "video_audio_transcription",
    "vt_seconds": 1800,
    "jobs": [
      {
        "msg_id": 1,
        "read_ct": 1,
        "document_id": "b5e4b7d1-bab4-49e3-b8bc-66a320bdb4ca"
      }
    ]
  }'
```

### Example Response

```json
{
  "ok": true,
  "summary": {
    "total": 1,
    "completed": 1,
    "retry": 0,
    "archived": 0,
    "deleted": 0
  },
  "results": [
    {
      "msg_id": 1,
      "status": "completed",
      "document_id": "b5e4b7d1-bab4-49e3-b8bc-66a320bdb4ca",
      "word_count": 1234,
      "segment_count": 45
    }
  ]
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `ok` | Boolean indicating overall success |
| `summary.total` | Total number of jobs processed |
| `summary.completed` | Jobs successfully completed |
| `summary.retry` | Jobs returned to queue for retry |
| `summary.archived` | Jobs archived after max retries |
| `summary.deleted` | Stale jobs deleted (already processed) |
| `results` | Array of individual job results |

### Job Result Status Values

| Status | Description |
|--------|-------------|
| `completed` | Job processed successfully, transcription saved |
| `retry` | Job failed but will retry (read_ct < max_retries) |
| `archived` | Job failed after max retries, archived for investigation |
| `deleted` | Job was stale (document already processed), deleted from queue |

### Job Processing Flow

```
Supabase Edge Function
        │
        ▼ POST /jobs/video-audio-transcription (Bearer PY_API_TOKEN)
        │
┌───────┴───────┐
│  For each job │
└───────┬───────┘
        │
        ▼
1. Claim document (pending → processing)
        │
        ▼
2. Extract audio from canonical_url
        │
        ▼
3. Transcribe with whisperX/OpenAI
        │
        ▼
4. Upsert to document_transcriptions
        │
        ▼
5. Update document (completed + processed_at)
        │
        ▼
6. pgmq_delete_one (ack message)
```

### Failure Handling

On job failure, the behavior depends on retry count:

**If `read_ct < WORKER_MAX_RETRIES`:**
- Document status returns to `pending`
- Error message stored in `processing_error` with retry context
- Queue message NOT acknowledged (will reappear after visibility timeout)
- Result status: `retry`

**If `read_ct >= WORKER_MAX_RETRIES`:**
- Document status set to `error`
- Final error message stored in `processing_error`
- Queue message archived via `pgmq_archive_one`
- Result status: `archived`

### Error Response Examples

**Document not in pending state (already processed):**
```json
{
  "ok": true,
  "summary": {"total": 1, "completed": 0, "retry": 0, "archived": 0, "deleted": 1},
  "results": [
    {
      "msg_id": 1,
      "status": "deleted",
      "reason": "not pending",
      "document_id": "b5e4b7d1-bab4-49e3-b8bc-66a320bdb4ca"
    }
  ]
}
```

**Job missing document_id:**
```json
{
  "ok": true,
  "summary": {"total": 1, "completed": 0, "retry": 0, "archived": 1, "deleted": 0},
  "results": [
    {
      "msg_id": 1,
      "status": "archived",
      "reason": "missing document_id"
    }
  ]
}
```

**Transcription failed (will retry):**
```json
{
  "ok": true,
  "summary": {"total": 1, "completed": 0, "retry": 1, "archived": 0, "deleted": 0},
  "results": [
    {
      "msg_id": 1,
      "status": "retry",
      "error": "[Step: transcribing audio with local/medium] Transcription failed: whisperX model load error",
      "read_ct": 2,
      "document_id": "b5e4b7d1-bab4-49e3-b8bc-66a320bdb4ca"
    }
  ]
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PY_API_TOKEN` | - | Bearer token for job endpoint authentication |
| `WORKER_MAX_RETRIES` | `5` | Maximum retry attempts before archiving |
| `WORKER_MODEL_SIZE` | `"medium"` | Whisper model size (tiny, small, medium, large-v2, turbo) |
| `WORKER_PROVIDER` | `"local"` | Transcription provider (local or openai) |
| `PROVIDER_NAME` | `"yt-dlp-api"` | Provider name for metadata tagging |
| `MAX_CONCURRENT_TRANSCRIPTIONS` | `2` | Maximum parallel transcriptions |

### Transcription Data Format

On successful transcription, data is upserted to `document_transcriptions`:

```json
{
  "document_id": "b5e4b7d1-bab4-49e3-b8bc-66a320bdb4ca",
  "segments": [
    {"start": 0.031, "end": 16.028, "text": "First segment text..."},
    {"start": 16.028, "end": 32.056, "text": "Second segment..."}
  ],
  "language": "en",
  "source": "ai",
  "confidence_score": null,
  "metadata": {
    "model": "WhisperX-medium",
    "provider": "yt-dlp-api",
    "duration": 80,
    "processing_time": 66.81,
    "word_count": 253,
    "segment_count": 4
  }
}
```

### Database Updates

The job processor updates the Supabase `documents` table throughout processing:

**On claim (start):**
```sql
UPDATE documents
SET processing_status = 'processing', updated_at = NOW()
WHERE id = ? AND processing_status = 'pending'
```

**On success:**
```sql
UPDATE documents
SET processing_status = 'completed', processed_at = NOW(),
    processing_error = NULL, updated_at = NOW()
WHERE id = ?
```

**On retry failure:**
```sql
UPDATE documents
SET processing_status = 'pending',
    processing_error = 'Retry 2/5: [Step: extracting audio] Audio extraction failed: ...',
    updated_at = NOW()
WHERE id = ?
```

**On max retries:**
```sql
UPDATE documents
SET processing_status = 'error',
    processing_error = 'Failed after 5 attempts. Last error: ...',
    updated_at = NOW()
WHERE id = ?
```

### Requirements

- Supabase project with `documents` and `document_transcriptions` tables
- PGMQ extension enabled with queue `video_audio_transcription`
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` environment variables
- `PY_API_TOKEN` for endpoint authentication
- Optional: whisperX for local transcription or OpenAI API key

### Related Endpoints

- [POST /transcriptions/save](#9-supabase-transcription-storage-optional) - Direct transcription save (alternative to job queue)
- [GET /transcriptions/check/{document_id}](#get-transcriptionscheckdocument_id) - Check if transcription exists

---

### `GET /jobs/status`

**Description**: Health check endpoint for the jobs handler. Returns configuration and status information.

**Authentication**: Bearer token via `Authorization` header

### Example Request

```bash
curl -H "Authorization: Bearer <PY_API_TOKEN>" \
  "http://your-api/jobs/status"
```

### Example Response

```json
{
  "status": "ready",
  "config": {
    "max_retries": 5,
    "model_size": "medium",
    "provider": "local",
    "max_concurrent_transcriptions": 2
  }
}