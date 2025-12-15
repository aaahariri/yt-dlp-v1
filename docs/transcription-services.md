# Video Transcription Services

Simple guide to video transcription features in the yt-dlp API.

## Overview

The API provides two transcription approaches:
1. **Subtitle Extraction** (`/subtitles`) - Extract existing subtitles (free, instant)
2. **AI Transcription** (`/extract-audio` + `/transcribe`) - Local (whisperX) or Cloud (OpenAI)

## Endpoints

### 1. Subtitle Extraction: `GET /subtitles`

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
curl "http://localhost:8000/subtitles?url=VIDEO_URL&format=json" \
  -H "X-API-Key: YOUR_KEY"
```

**Response:**
```json
{
  "title": "Video Title",
  "language": "en",
  "format": "json",
  "segments": [
    {"start": "00:00:00,000", "end": "00:00:03,500", "text": "Hello, welcome."},
    {"start": "00:00:03,500", "end": "00:00:07,200", "text": "Today we'll discuss..."}
  ],
  "source_format": "srt"
}
```

---

### 2. Audio Extraction: `POST /extract-audio`

Extract audio from video URL or local file.

**Parameters:**
- `url` (optional) - Video URL to extract audio from
- `local_file` (optional) - Path to local video file (alternative to url)
- `output_format` (optional, default: "mp3") - Audio format: mp3, m4a, wav
- `quality` (optional, default: "192") - Audio quality/bitrate
- `cookies_file` (optional) - Path to cookies file

**Cost:** $0 (uses bestaudio stream, no full video download)

**Example:**
```bash
curl -X POST "http://localhost:8000/extract-audio?url=VIDEO_URL" \
  -H "X-API-Key: YOUR_KEY"
```

**Response:**
```json
{
  "audio_file": "/tmp/32527060.mp3",
  "format": "mp3",
  "size": 1929236,
  "title": "Video Title",
  "source_type": "url",
  "message": "Audio extracted successfully. Use this audio_file path with POST /transcribe",
  "expires_in": "1 hour (automatic cleanup)"
}
```

---

### 3. AI Transcription: `POST /transcribe`

AI-powered transcription with provider selection.

**Parameters:**
- `audio_file` (required) - Path to audio file on server (from `/extract-audio`)
- `language` (optional) - Language code or auto-detect
- `model_size` (optional, default: "medium") - Model size: tiny, small, medium, large-v2, large-v3, turbo
- `provider` (optional, default: "local") - Provider: **local** or **openai**
- `output_format` (optional, default: "json") - Output format: json, srt, vtt, text

**Example:**
```bash
# Step 1: Extract audio
AUDIO_FILE=$(curl -X POST "http://localhost:8000/extract-audio?url=VIDEO_URL" \
  -H "X-API-Key: YOUR_KEY" | jq -r '.audio_file')

# Step 2: Transcribe with local AI
curl -X POST "http://localhost:8000/transcribe?audio_file=$AUDIO_FILE&provider=local" \
  -H "X-API-Key: YOUR_KEY"

# Or use OpenAI Cloud API
curl -X POST "http://localhost:8000/transcribe?audio_file=$AUDIO_FILE&provider=openai" \
  -H "X-API-Key: YOUR_KEY"
```

**Response:**
```json
{
  "title": "32527060.mp3",
  "language": "en",
  "model": "medium",
  "provider": "local",
  "segments": [
    {"start": 0.031, "end": 16.028, "text": "I'm going to show you guys..."},
    {"start": 16.028, "end": 39.029, "text": "The very first thing..."}
  ],
  "full_text": "I'm going to show you guys...",
  "word_count": 253,
  "segment_count": 4,
  "transcription_time": 97.95
}
```

---

## AI Transcription Providers

### Local Provider (whisperX)

**Platform:** CPU, CUDA (NVIDIA GPUs), MPS (Apple Silicon - experimental)
**Cost:** $0 (no API fees)
**Setup:** `pip install whisperx`

**Supported Models:**
| Model | Size | Speed (GPU) | Speed (CPU) | Accuracy | Best For |
|-------|------|-------------|-------------|----------|----------|
| tiny | 39MB | 70x RT | 10x RT | Fair | Quick drafts |
| small | 244MB | 70x RT | 5x RT | Good | Balanced performance |
| medium | 769MB | 70x RT | 3-5x RT | Very Good | General use |
| large-v2 | 1.5GB | 70x RT | 2x RT | Excellent | High accuracy |
| large-v3 | 1.5GB | 70x RT | 2x RT | Excellent | Latest model |
| turbo | 809MB | 70x RT | 4x RT | Excellent | **Recommended** |

**Performance:**
- GPU: Up to 70x faster than real-time
- CPU: 3-5x faster than real-time (int8 quantization)
- Example: 10-minute video → 8-20 seconds (GPU) or 2-3 minutes (CPU)
- Memory: 2-12GB depending on model and device

**Languages Supported:** 99 languages with automatic detection
- English, Spanish, French, German, Italian, Portuguese, Dutch, Russian
- Chinese (Simplified/Traditional), Japanese, Korean, Arabic, Hindi
- And 80+ more languages

**Key Features:**
- ✅ Word-level timestamps (not just segment-level)
- ✅ Works on any platform (CPU, NVIDIA GPU, Apple Silicon)
- ✅ Automatic device detection (CUDA > MPS > CPU)
- ✅ Speaker diarization support
- ✅ Zero API costs

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
- ✅ Deploying to cloud servers without GPU
- ✅ Don't want to manage local models
- ✅ Need consistent cloud performance
- ✅ Low transcription volume (<100 hours/month)

---

## Recommended Workflow

### Option 1: Try Subtitles First (Cost-Optimized)

```bash
# Step 1: Try subtitle extraction (free, instant)
curl "http://localhost:8000/subtitles?url=VIDEO_URL&format=json" \
  -H "X-API-Key: YOUR_KEY"

# If no subtitles, proceed to Step 2 & 3
```

### Option 2: Direct AI Transcription

```bash
# Step 1: Extract audio
AUDIO_FILE=$(curl -X POST "http://localhost:8000/extract-audio?url=VIDEO_URL" \
  -H "X-API-Key: YOUR_KEY" | jq -r '.audio_file')

# Step 2: Transcribe
curl -X POST "http://localhost:8000/transcribe?audio_file=$AUDIO_FILE&provider=local" \
  -H "X-API-Key: YOUR_KEY"
```

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

All endpoints support multiple output formats:

### JSON Format (Default)
Full metadata with segments and timestamps.

### SRT Format
Standard subtitle format for video players.

### VTT Format
WebVTT format for HTML5 video players.

### Text Format
Plain text without timestamps.

See `CLAUDE.md` for detailed format examples.

---

## Cost Comparison

| Method | Cost per Hour | 100 Hours | 1,000 Hours | Notes |
|--------|--------------|-----------|-------------|-------|
| **Subtitles** | $0 | $0 | $0 | Instant, if available |
| **Local (whisperX)** | $0 | $0 | $0 | Works on CPU/GPU |
| **OpenAI** | $0.36 | $36 | $360 | Managed cloud service |

---

## Best Practices

### 1. Cost Optimization
Always try `/subtitles` first before using AI transcription.

### 2. Provider Selection

**For Development:**
Use local provider - free and fast (GPU or CPU).

**For Production (Railway/Cloud):**
- Option 1: Use local provider in CPU mode (free, 3-5x real-time)
- Option 2: Use OpenAI provider (managed, simpler deployment)

### 3. Language Detection

Both providers support automatic language detection. Only specify language for better accuracy with specific content.

---

## Troubleshooting

### "whisperX not installed"
**Solution:** Install with `pip install whisperx`

### "No subtitles available"
**Solution:** Use AI transcription workflow (`/extract-audio` → `/transcribe`)

### "OPENAI_API_KEY not configured"
**Solution:** Set API key in `.env` file

### Slow transcription on CPU
**Solution:** This is expected. CPU mode runs at 3-5x real-time (still faster than manual transcription). For faster processing, use GPU or OpenAI provider.

---

## API Reference Summary

| Endpoint | Method | Purpose | Cost |
|----------|--------|---------|------|
| `/subtitles` | GET | Extract existing subtitles | $0 |
| `/extract-audio` | POST | Extract audio from video | $0 |
| `/transcribe` | POST | AI transcription | $0 (local) or $0.006/min (openai) |
| `/transcription/locales` | GET | List available subtitle languages | $0 |

---

## Related Documentation

- [Transcription Setup Guide](./transcription-setup-guide.md)
- [Endpoint Flow Diagrams](./endpoint-flows.md)
- [Main Documentation](../CLAUDE.md)
