# Composable Workflows Guide

**Platform-specific transcription workflows optimized for cost and efficiency.**

---

## Philosophy

Each platform has different capabilities:
- **YouTube**: Usually has subtitles, supports direct audio streaming
- **TikTok/Instagram/Twitter**: Rarely has subtitles, requires full download
- **Podcasts/Audio**: Already in audio format, no extraction needed

Choose the right workflow based on your platform and requirements.

---

## YouTube Videos

### Workflow 1: Quick Transcription (Recommended for YouTube)

**Use when:** You want the fastest, cheapest transcription

```bash
# Step 1: Try subtitles first (instant, $0)
curl -X GET "http://localhost:8000/subtitles?url=YOUTUBE_URL&lang=en" \
  -H "X-API-Key: YOUR_KEY"

# ✅ If subtitles exist → Done! ($0 cost, <1 second)
# ❌ If 404 → Continue to Step 2
```

**If no subtitles found:**

```bash
# Step 2: Extract audio (YouTube provides audio stream, no full download needed)
curl -X POST "http://localhost:8000/extract-audio?url=YOUTUBE_URL" \
  -H "X-API-Key: YOUR_KEY"

# Response: {"audio_file": "/tmp/a1b2c3d4.mp3", ...}

# Step 3: Transcribe with AI
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a1b2c3d4.mp3&provider=local" \
  -H "X-API-Key: YOUR_KEY"
```

**Cost:** $0 (if subtitles exist) or $0 (local AI)
**Time:** <1s (subtitles) or 30-120s (AI transcription)
**Network:** Minimal (audio stream only, ~5-15MB for 10min video)

---

### Workflow 2: Archive + Transcribe (YouTube)

**Use when:** You want to keep the video file for later use

```bash
# Step 1: Download and keep video (best quality ≤720p)
curl -X GET "http://localhost:8000/download?url=YOUTUBE_URL&format=best[height<=720]&keep=true" \
  -H "X-API-Key: YOUR_KEY" \
  -O video.mp4

# Returns header: X-Server-Path: downloads/YOUTUBE-video-title.mp4

# Step 2: Extract audio from saved video
curl -X POST "http://localhost:8000/extract-audio?local_file=downloads/YOUTUBE-video-title.mp4" \
  -H "X-API-Key: YOUR_KEY"

# Response: {"audio_file": "/tmp/a1b2c3d4.mp3", ...}

# Step 3: Transcribe
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a1b2c3d4.mp3&provider=local&model_size=turbo" \
  -H "X-API-Key: YOUR_KEY"
```

**Cost:** $0
**Time:** 2-5 minutes (download) + 30-120s (transcription)
**Network:** Full video download (~100-300MB for 10min 720p video)
**Benefit:** Video saved for future use, can retry transcription without re-downloading

---

### Workflow 3: Audio-Only Archive (YouTube Podcasts/Interviews)

**Use when:** You only need audio, not video (podcasts, interviews, music)

```bash
# Step 1: Download audio only (saves bandwidth and storage)
curl -X GET "http://localhost:8000/download?url=YOUTUBE_URL&format=bestaudio&keep=true" \
  -H "X-API-Key: YOUR_KEY" \
  -O audio.m4a

# Returns header: X-Server-Path: downloads/YOUTUBE-podcast-title.m4a

# Step 2: Extract/convert audio to MP3 if needed
curl -X POST "http://localhost:8000/extract-audio?local_file=downloads/YOUTUBE-podcast-title.m4a&output_format=mp3" \
  -H "X-API-Key: YOUR_KEY"

# Response: {"audio_file": "/tmp/a1b2c3d4.mp3", ...}

# Step 3: Transcribe
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a1b2c3d4.mp3&provider=local&model_size=turbo" \
  -H "X-API-Key: YOUR_KEY"
```

**Cost:** $0
**Time:** 30-90s (audio download) + 30-120s (transcription)
**Network:** Audio only (~10-30MB for 10min podcast)
**Benefit:** 5-10x smaller download than video

---

## TikTok Videos

### Workflow 1: Quick Transcription (TikTok)

**Use when:** Short videos (<3 minutes), don't need to keep file

```bash
# Step 1: Skip subtitle check (TikTok rarely has subtitles)
# Go directly to audio extraction

# Step 2: Extract audio from URL
curl -X POST "http://localhost:8000/extract-audio?url=TIKTOK_URL" \
  -H "X-API-Key: YOUR_KEY"

# Response: {"audio_file": "/tmp/a1b2c3d4.mp3", ...}

# Step 3: Transcribe (use tiny model for short videos)
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a1b2c3d4.mp3&provider=local&model_size=tiny" \
  -H "X-API-Key: YOUR_KEY"
```

**Cost:** $0
**Time:** 10-30s (extraction) + 5-15s (transcription)
**Network:** Full download (~5-15MB for 1min video)
**Note:** TikTok requires full download, then audio extraction

---

### Workflow 2: Archive + Transcribe (TikTok)

**Use when:** You want to keep the video file

```bash
# Step 1: Download and keep video
curl -X GET "http://localhost:8000/download?url=TIKTOK_URL&keep=true" \
  -H "X-API-Key: YOUR_KEY" \
  -O tiktok-video.mp4

# Returns header: X-Server-Path: downloads/TIKTOK-video-title.mp4

# Step 2: Extract audio from saved video
curl -X POST "http://localhost:8000/extract-audio?local_file=downloads/TIKTOK-video-title.mp4" \
  -H "X-API-Key: YOUR_KEY"

# Step 3: Transcribe
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a1b2c3d4.mp3&provider=local&model_size=tiny" \
  -H "X-API-Key: YOUR_KEY"
```

**Cost:** $0
**Time:** 10-30s (download) + 5-15s (transcription)
**Benefit:** Can retry transcription or re-process video later

---

## Instagram Videos/Reels

### Workflow 1: Quick Transcription (Instagram)

**Use when:** Short reels/videos, one-time transcription

```bash
# Step 1: Extract audio directly
curl -X POST "http://localhost:8000/extract-audio?url=INSTAGRAM_URL" \
  -H "X-API-Key: YOUR_KEY"

# Response: {"audio_file": "/tmp/a1b2c3d4.mp3", ...}

# Step 2: Transcribe
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a1b2c3d4.mp3&provider=local&model_size=small" \
  -H "X-API-Key: YOUR_KEY"
```

**Cost:** $0
**Time:** 15-40s (extraction) + 10-30s (transcription)
**Network:** ~10-40MB depending on video length

---

### Workflow 2: Archive + Transcribe (Instagram)

**Use when:** You want to keep the video

```bash
# Step 1: Download and keep
curl -X GET "http://localhost:8000/download?url=INSTAGRAM_URL&keep=true" \
  -H "X-API-Key: YOUR_KEY" \
  -O instagram-video.mp4

# Step 2: Extract audio
curl -X POST "http://localhost:8000/extract-audio?local_file=downloads/INSTAGRAM-video-title.mp4" \
  -H "X-API-Key: YOUR_KEY"

# Step 3: Transcribe
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a1b2c3d4.mp3&provider=local" \
  -H "X-API-Key: YOUR_KEY"
```

---

## Twitter/X Videos

### Workflow 1: Quick Transcription (Twitter)

```bash
# Step 1: Extract audio
curl -X POST "http://localhost:8000/extract-audio?url=TWITTER_URL" \
  -H "X-API-Key: YOUR_KEY"

# Step 2: Transcribe
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a1b2c3d4.mp3&provider=local&model_size=small" \
  -H "X-API-Key: YOUR_KEY"
```

**Cost:** $0
**Time:** 10-30s (extraction) + 10-30s (transcription)

---

## Podcasts (Audio Files)

### Workflow 1: Direct URL Transcription

**Use when:** Podcast is available via direct URL (RSS feed, Spotify, Apple Podcasts)

```bash
# Step 1: Extract audio (if already MP3, this is fast)
curl -X POST "http://localhost:8000/extract-audio?url=PODCAST_MP3_URL" \
  -H "X-API-Key: YOUR_KEY"

# Response: {"audio_file": "/tmp/a1b2c3d4.mp3", ...}

# Step 2: Transcribe (use medium/large for better accuracy on long podcasts)
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a1b2c3d4.mp3&provider=local&model_size=medium" \
  -H "X-API-Key: YOUR_KEY"
```

**Cost:** $0
**Time:** 10-30s (download) + 2-10 minutes (transcription for 1hr podcast)
**Note:** For podcasts >1hr, consider using `model_size=turbo` for faster processing

---

### Workflow 2: Local Podcast File

**Use when:** You already have podcast file on disk

```bash
# Step 1: Extract/convert to MP3 (if needed)
curl -X POST "http://localhost:8000/extract-audio?local_file=/path/to/podcast.m4a&output_format=mp3" \
  -H "X-API-Key: YOUR_KEY"

# Response: {"audio_file": "/tmp/a1b2c3d4.mp3", ...}

# Step 2: Transcribe
curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/a1b2c3d4.mp3&provider=local&model_size=turbo" \
  -H "X-API-Key: YOUR_KEY"
```

**Cost:** $0
**Time:** 5-15s (conversion) + 2-10 minutes (transcription)

---

## Batch Processing Multiple Videos

### Workflow: Process Multiple Videos Efficiently

**Use when:** Processing multiple videos from same platform

```bash
# For each video in your list:

# Step 1: Download all videos first (keep them)
for url in "${urls[@]}"; do
  curl -X GET "http://localhost:8000/download?url=$url&keep=true" \
    -H "X-API-Key: YOUR_KEY" \
    -O video_$i.mp4
done

# Step 2: Extract audio from all downloaded videos
for file in downloads/*.mp4; do
  curl -X POST "http://localhost:8000/extract-audio?local_file=$file" \
    -H "X-API-Key: YOUR_KEY" \
    >> audio_files.json
done

# Step 3: Transcribe all audio files (can retry with different models if needed)
for audio_file in $(jq -r '.audio_file' audio_files.json); do
  curl -X POST "http://localhost:8000/transcribe?audio_file=$audio_file&provider=local&model_size=turbo" \
    -H "X-API-Key: YOUR_KEY" \
    >> transcriptions.json
done

# Benefit: Download once, can retry transcription with different models/providers without re-downloading
```

---

## Platform-Specific Quick Reference

| Platform | Has Subtitles? | Best Workflow | Recommended Model | Avg Time (10min video) |
|----------|----------------|---------------|-------------------|------------------------|
| **YouTube** | Often ✅ | Try subtitles first → Audio extraction | medium/turbo | <1s or 30-120s |
| **YouTube (no subs)** | No ❌ | Direct audio extraction | turbo | 30-120s |
| **TikTok** | Rarely ❌ | Direct audio extraction | tiny/small | 10-30s |
| **Instagram** | No ❌ | Direct audio extraction | small/medium | 15-40s |
| **Twitter/X** | No ❌ | Direct audio extraction | small | 10-30s |
| **Podcasts (URL)** | No ❌ | Direct audio extraction | medium/turbo | 2-10 minutes |
| **Podcasts (local)** | No ❌ | Local file extraction | turbo | 2-10 minutes |

---

## Model Selection Guide

| Model | Best For | Speed (GPU) | Speed (CPU) | Accuracy |
|-------|----------|-------------|-------------|----------|
| **tiny** | TikTok, Twitter (<2min videos) | 70x RT | 5x RT | Fair |
| **small** | Instagram, short YouTube videos | 70x RT | 4x RT | Good |
| **medium** | General purpose, podcasts | 70x RT | 3x RT | Very Good |
| **turbo** | Long content, podcasts, interviews | 70x RT | 3.5x RT | Excellent |
| **large-v2** | Critical accuracy needs | 70x RT | 2x RT | Best |

RT = Real-Time (e.g., 70x RT means a 10-minute video takes ~8.5 seconds to transcribe)

---

## Cost Comparison

### Local Provider (whisperX)
- **Cost:** $0
- **Setup:** `pip install whisperx`
- **Best for:** Any volume, privacy-sensitive content, offline use

### OpenAI Provider
- **Cost:** $0.006/minute ($0.36/hour)
- **Setup:** OPENAI_API_KEY in environment
- **Best for:** Low volume, managed service preference

### Example Costs (100 videos, 10min each)

| Provider | Total Cost | Setup Time |
|----------|------------|------------|
| **Local (whisperX)** | $0 | 1 command |
| **OpenAI** | $6 | Add API key |

---

## Error Handling Strategies

### Strategy 1: Graceful Degradation

```bash
# Try subtitles first
response=$(curl -s -X GET "http://localhost:8000/subtitles?url=$url")

if echo "$response" | jq -e '.error' > /dev/null; then
  # No subtitles, use AI
  audio=$(curl -X POST "http://localhost:8000/extract-audio?url=$url")
  audio_file=$(echo "$audio" | jq -r '.audio_file')

  # Try local first
  result=$(curl -X POST "http://localhost:8000/transcribe?audio_file=$audio_file&provider=local")

  if echo "$result" | jq -e '.detail' > /dev/null; then
    # Local failed, try OpenAI
    result=$(curl -X POST "http://localhost:8000/transcribe?audio_file=$audio_file&provider=openai")
  fi
fi
```

---

### Strategy 2: Retry with Smaller Model (OOM errors)

```bash
# Try medium model first
result=$(curl -X POST "http://localhost:8000/transcribe?audio_file=$audio_file&model_size=medium&provider=local")

if echo "$result" | jq -r '.detail' | grep -q "out of memory"; then
  # Retry with smaller model
  result=$(curl -X POST "http://localhost:8000/transcribe?audio_file=$audio_file&model_size=tiny&provider=local")
fi
```

---

## Best Practices

### ✅ Do

1. **Try subtitles first for YouTube** - Instant, free, high quality
2. **Use audio-only downloads for podcasts** - 5-10x smaller than video
3. **Keep files when batch processing** - Enables retries without re-downloading
4. **Use appropriate model size** - Tiny for short videos, turbo for long content
5. **Start with local provider** - $0 cost, works offline

### ❌ Don't

1. **Don't check subtitles for TikTok/Instagram** - Waste of API call, they rarely exist
2. **Don't download full video if you only need audio** - Use `format=bestaudio`
3. **Don't use large models for <2min videos** - Tiny/small is sufficient
4. **Don't re-download for retry** - Use `keep=true` and saved file path

---

## Related Documentation

- [Clean API Architecture](./clean-api-architecture.md) - Endpoint details and philosophy
- [Endpoint Flow Diagrams](./endpoint-flows.md) - Technical flow diagrams
- [Transcription Setup Guide](./transcription-setup-guide.md) - Installation and configuration
- [Transcription Services Guide](./transcription-services.md) - Provider comparison
