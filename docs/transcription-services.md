# Video Transcription Services

Simple guide to video transcription features in the yt-dlp API.

## Overview

The API provides two transcription approaches:
1. **Subtitle Extraction** - Extract existing subtitles (free, instant)
2. **AI Transcription** - Local (M1 Mac) or Cloud (OpenAI)

## Endpoints

### 1. Subtitle Extraction: `GET /transcription`

Extract existing subtitles from videos (no AI processing).

**Parameters:**
- `url` (required) - Video URL
- `lang` (optional, default: "en") - Language code (e.g., "en", "es", "fr")
- `format` (optional, default: "text") - Output format: text, json, srt, vtt
- `auto` (optional, default: true) - Include auto-generated captions
- `cookies_file` (optional) - Path to cookies file for authentication

**Cost:** $0 (free, instant)

**Example:**
```bash
curl "http://localhost:8000/transcription?url=VIDEO_URL&format=json" \
  -H "X-API-Key: YOUR_KEY"
```

---

### 2. AI Transcription: `POST /ai-transcribe`

AI-powered transcription with provider selection.

**Parameters:**
- `url` (required) - Video URL
- `format` (optional, default: "json") - Output format: json, srt, vtt, text
- `language` (optional) - Language code or auto-detect
- `model_size` (optional, default: "medium") - Model size: tiny, small, medium, large-v2, large-v3, turbo
- `provider` (optional, default: "local") - Provider: **local** or **openai**
- `cookies_file` (optional) - Path to cookies file

**Example:**
```bash
# Local AI (M1 Mac)
curl -X POST "http://localhost:8000/ai-transcribe?url=VIDEO_URL&provider=local" \
  -H "X-API-Key: YOUR_KEY"

# OpenAI Cloud API
curl -X POST "http://localhost:8000/ai-transcribe?url=VIDEO_URL&provider=openai" \
  -H "X-API-Key: YOUR_KEY"
```

**Response:**
```json
{
  "title": "Video Title",
  "duration": 630,
  "language": "en",
  "model": "medium",
  "provider": "local",
  "segments": [
    {"start": 0.0, "end": 3.5, "text": "Hello world"}
  ],
  "full_text": "Hello world...",
  "word_count": 245,
  "transcription_time": 45.2,
  "source": "ai"
}
```

---

### 3. Smart Transcription: `POST /smart-transcribe` ⭐ RECOMMENDED

Hybrid endpoint that automatically chooses the best method.

**Logic:**
1. Try subtitle extraction first (if `force_ai=false`)
2. Fall back to AI transcription if no subtitles available

**Parameters:**
- `url` (required) - Video URL
- `format` (optional, default: "json") - Output format: json, srt, vtt, text
- `language` (optional, default: "en") - Preferred language
- `force_ai` (optional, default: false) - Skip subtitles, use AI directly
- `model_size` (optional, default: "medium") - AI model size
- `provider` (optional, default: "local") - AI provider: **local** or **openai**
- `auto` (optional, default: true) - Include auto-generated subtitles
- `cookies_file` (optional) - Path to cookies file

**Example:**
```bash
# Try subtitles first, fall back to local AI
curl -X POST "http://localhost:8000/smart-transcribe?url=VIDEO_URL" \
  -H "X-API-Key: YOUR_KEY"

# Force OpenAI cloud transcription
curl -X POST "http://localhost:8000/smart-transcribe?url=VIDEO_URL&force_ai=true&provider=openai" \
  -H "X-API-Key: YOUR_KEY"
```

---

## AI Transcription Providers

### Local Provider (whisperX)

**Platform:** CPU, CUDA (NVIDIA GPUs), MPS (Apple Silicon - experimental)
**Cost:** $0 (no API fees)
**Setup:** `pip install whisperx`

**Supported Models:**
| Model | Size | Speed | Accuracy | Best For |
|-------|------|-------|----------|----------|
| tiny | 39MB | 70x RT (GPU) | Fair | Quick drafts |
| small | 244MB | 70x RT (GPU) | Good | Balanced performance |
| medium | 769MB | 70x RT (GPU) | Very Good | General use |
| large-v2 | 1.5GB | 70x RT (GPU) | Excellent | High accuracy |
| large-v3 | 1.5GB | 70x RT (GPU) | Excellent | Latest model |
| turbo | 809MB | 70x RT (GPU) | Excellent | **Recommended** |

**Performance:**
- Up to 70x faster than real-time on GPU
- CPU mode: 3-5x real-time (int8 quantization)
- Example: 10-minute video → 8-20 seconds (GPU) or 2-3 minutes (CPU)
- Memory: 2-12GB depending on model and device

**Languages Supported:** 99 languages
- English, Spanish, French, German, Italian, Portuguese, Dutch, Russian
- Chinese (Simplified/Traditional), Japanese, Korean, Arabic, Hindi
- And 80+ more languages with automatic detection

**Key Features:**
- ✅ Word-level timestamps (not just segment-level)
- ✅ Works on any platform (CPU, NVIDIA GPU, Apple Silicon)
- ✅ 70x real-time on GPU, 3-5x on CPU
- ✅ Automatic device detection (CUDA > MPS > CPU)
- ✅ Speaker diarization support

**When to Use:**
- ✅ Want zero API costs
- ✅ Need offline transcription
- ✅ Privacy-sensitive content
- ✅ Need word-level timestamps
- ✅ Works on Railway (CPU mode)

---

### OpenAI Provider (Whisper API)

**Platform:** Cloud API (works anywhere)
**Cost:** $0.006/minute ($0.36/hour)
**Setup:** Set `OPENAI_API_KEY` in environment

**Supported Models:**
- `whisper-1` - Latest Whisper model

**Performance:**
- Processing: ~1-2 minutes typical
- Max file size: 25MB
- Handles long audio automatically

**Languages Supported:** 99 languages (same as local)

**When to Use:**
- ✅ Deploying to Railway/non-Apple Silicon servers
- ✅ Don't want to manage local models
- ✅ Need consistent cloud performance
- ✅ Low transcription volume (<100 hours/month)

---

## Environment Configuration

### Local Provider (whisperX)

No configuration needed! Just install:

```bash
pip install whisperx
```

Works on CPU, NVIDIA GPUs, and Apple Silicon (experimental MPS support).

### OpenAI Provider

Add to your `.env` file:

```env
OPENAI_API_KEY=sk-...
```

---

## Output Formats

### JSON Format (Default)
Best for programmatic access with full metadata and segments.

```json
{
  "title": "Video Title",
  "duration": 630,
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
  "transcription_time": 45.2,
  "source": "ai"
}
```

### SRT Format
Standard subtitle format for video players.

```srt
1
00:00:00,000 --> 00:00:03,500
Hello, welcome to the video.

2
00:00:03,500 --> 00:00:07,200
Today we'll discuss transcription.
```

### VTT Format
WebVTT format for HTML5 video players.

```vtt
WEBVTT

00:00:00.000 --> 00:00:03.500
Hello, welcome to the video.

00:00:03.500 --> 00:00:07.200
Today we'll discuss transcription.
```

### Text Format
Plain text without timestamps.

```json
{
  "transcript": "Hello, welcome to the video. Today we'll discuss transcription...",
  "word_count": 245,
  "title": "Video Title",
  "duration": 630,
  "language": "en",
  "source": "ai"
}
```

---

## Cost Comparison

| Provider | Cost per Hour | 100 Hours | 1,000 Hours | Notes |
|----------|--------------|-----------|-------------|-------|
| **Local (whisperX)** | $0 | $0 | $0 | Works on CPU/GPU |
| **OpenAI** | $0.36 | $36 | $360 | Managed cloud service |

---

## Best Practices

### 1. Provider Selection Strategy

**For Development:**
```bash
# Use local provider - free and fast (GPU or CPU)
curl -X POST "http://localhost:8000/smart-transcribe?url=VIDEO_URL&provider=local"
```

**For Production (Railway/Cloud):**
```bash
# Option 1: Use local provider in CPU mode (free, 3-5x real-time)
curl -X POST "http://localhost:8000/smart-transcribe?url=VIDEO_URL&provider=local"

# Option 2: Use OpenAI provider (managed, simpler deployment)
curl -X POST "http://localhost:8000/smart-transcribe?url=VIDEO_URL&provider=openai"
```

### 2. Smart Transcription Workflow

```python
# Let the API choose the best method automatically
response = requests.post(
    "http://localhost:8000/smart-transcribe",
    params={
        "url": video_url,
        "format": "json",
        "provider": "local"  # or "openai" for cloud
    },
    headers={"X-API-Key": api_key}
)

# Check the source
if response.json()["source"] == "subtitle":
    print("Used free subtitles - $0 cost")
else:
    print(f"Used AI transcription - Provider: {response.json()['provider']}")
```

### 3. Language Detection

Both providers support automatic language detection:

```bash
# Auto-detect language (recommended)
curl -X POST "http://localhost:8000/ai-transcribe?url=VIDEO_URL"

# Specify language for better accuracy
curl -X POST "http://localhost:8000/ai-transcribe?url=VIDEO_URL&language=es"
```

---

## Deployment Considerations

### Local Development
- ✅ Use `provider=local` for free transcription
- ✅ No API keys needed
- ✅ Models download automatically on first use
- ✅ GPU acceleration if CUDA or MPS available

### Railway Deployment
- ✅ Can use `provider=local` (runs in CPU mode with int8)
- ✅ Or use `provider=openai` for simpler deployment
- ✅ CPU mode: 3-5x real-time (still fast enough)
- ✅ Set `OPENAI_API_KEY` if using OpenAI provider

---

## Troubleshooting

### "whisperX not installed"
**Solution:** Install with `pip install whisperx`

### "No subtitles available"
**Solution:** Use `force_ai=true` or `/ai-transcribe` endpoint

### "OPENAI_API_KEY not configured"
**Solution:** Set API key in `.env` file

### Slow transcription
**Solution:**
- GPU: Use `model_size=turbo` for best performance (70x real-time)
- CPU: Already optimized with int8, expect 3-5x real-time

---

## API Reference Summary

| Endpoint | Method | Purpose | Cost |
|----------|--------|---------|------|
| `/transcription` | GET | Extract subtitles | $0 |
| `/ai-transcribe` | POST | AI transcription | $0 (local) or $0.36/hr (openai) |
| `/smart-transcribe` | POST | Hybrid (subtitle → AI) | $0 or varies |
| `/transcription/locales` | GET | List available languages | $0 |

---

## Related Documentation

- [Transcription Setup Guide](./transcription-setup-guide.md)
- [Batch Download API](./batch-download-api.md)
- [Main README](../README.md)
- [CLAUDE.md](../CLAUDE.md)
