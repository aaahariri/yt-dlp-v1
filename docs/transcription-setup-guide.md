# Transcription Setup Guide

Simple setup guide for video transcription features.

## Quick Start

### Local AI Transcription (Any Platform)

**Step 1: Install whisperX**
```bash
pip install whisperx
```

**Step 2: Use it**
```bash
curl -X POST "http://localhost:8000/ai-transcribe?url=YOUR_VIDEO&provider=local" \
  -H "X-API-Key: YOUR_KEY"
```

**That's it!** Models download automatically on first use (39MB to 1.5GB depending on model).

**Cost:** $0
**Works on:** CPU, NVIDIA GPUs, Apple Silicon (MPS)

---

### Cloud AI Transcription (OpenAI)

**Step 1: Get API key**
- Sign up at https://platform.openai.com
- Create API key

**Step 2: Add to environment**
```bash
# .env file
OPENAI_API_KEY=sk-...
```

**Step 3: Use it**
```bash
curl -X POST "http://localhost:8000/ai-transcribe?url=YOUR_VIDEO&provider=openai" \
  -H "X-API-Key: YOUR_KEY"
```

**Cost:** $0.006/minute ($0.36/hour)

---

## Understanding the Models

### What is Whisper?

**OpenAI Whisper** is an open-source speech recognition model:
- Released by OpenAI
- Free to use
- 99 languages supported
- Industry standard accuracy

### Local vs Cloud - Same Core Models!

Both providers use **Whisper models**:

| Provider | Models | Implementation | Cost |
|----------|--------|----------------|------|
| **Local** | Whisper (open source) | whisperX (enhanced) | $0 |
| **OpenAI** | Whisper API | OpenAI's servers | $0.36/hour |

**Key differences:**
- Local: Runs on your server (free, private, word-level timestamps)
- OpenAI: Runs on their servers (paid, convenient, managed)

---

## Model Selection

### Available Models (Local)

| Model | Size | Download Once | Speed (GPU) | Speed (CPU) | Accuracy |
|-------|------|---------------|-------------|-------------|----------|
| tiny | 39MB | First use | 70x RT | 5x RT | Fair |
| small | 244MB | First use | 70x RT | 4x RT | Good |
| **medium** | 769MB | First use | 70x RT | 3x RT | Very Good |
| large-v2 | 1.5GB | First use | 70x RT | 2x RT | Excellent |
| large-v3 | 1.5GB | First use | 70x RT | 2x RT | Excellent |
| **turbo** | 809MB | First use | 70x RT | 3.5x RT | Excellent |

**Recommendation:** Use `turbo` for best balance of speed and accuracy.

**Example:**
```bash
curl -X POST "http://localhost:8000/ai-transcribe?url=VIDEO&model_size=turbo&provider=local"
```

RT = Real-Time

---

## Deployment Scenarios

### Scenario 1: Local Development

**Setup:**
```bash
# Install whisperX
pip install whisperx

# No .env configuration needed
```

**Use:**
```bash
# Free, fast local transcription (GPU or CPU)
curl -X POST "http://localhost:8000/smart-transcribe?url=VIDEO&provider=local"
```

**Cost:** $0
**Performance:** 70x real-time (GPU) or 3-5x real-time (CPU)

---

### Scenario 2: Railway Deployment

**Option A: Use whisperX in CPU mode (free)**
```bash
# whisperX works on Railway in CPU mode!
# No environment variables needed
# Keep whisperx in requirements.txt
```

**Use:**
```bash
# Free local transcription in CPU mode (3-5x real-time)
curl -X POST "https://your-api.railway.app/smart-transcribe?url=VIDEO&provider=local"
```

**Cost:** $0 (CPU processing on Railway servers)

**Option B: Use OpenAI (simpler deployment)**
```bash
# Railway environment variables
OPENAI_API_KEY=sk-...
```

**Use:**
```bash
# Cloud transcription
curl -X POST "https://your-api.railway.app/smart-transcribe?url=VIDEO&provider=openai"
```

**Cost:** $0.36/hour

---

### Scenario 3: Automatic Provider Selection

**Local development and production both can use local:**
```python
provider = "local"  # Free everywhere (GPU or CPU)
```

**Fallback to OpenAI if needed:**
```python
import os

def get_provider():
    """Auto-select best provider."""
    # Check if whisperX is available
    try:
        import whisperx
        return "local"  # Free on CPU/GPU!
    except ImportError:
        pass

    # Check if OpenAI key is configured
    if os.getenv("OPENAI_API_KEY"):
        return "openai"  # Cloud fallback

    raise Exception("No transcription provider available")

# Use in API calls
provider = get_provider()
response = requests.post(
    f"{API_URL}/smart-transcribe",
    params={"url": video_url, "provider": provider}
)
```

---

## Language Support

### 99 Languages Supported

Both providers support the same languages:

**Major Languages:**
- English, Spanish, French, German, Italian, Portuguese, Russian
- Chinese, Japanese, Korean, Arabic, Hindi, Bengali
- Dutch, Polish, Swedish, Norwegian, Danish, Finnish, Turkish

**Plus 70+ more:** Thai, Vietnamese, Indonesian, Hebrew, Persian, Tamil, and many more.

### Automatic Detection

```bash
# Auto-detect language (recommended)
curl -X POST "http://localhost:8000/ai-transcribe?url=VIDEO"

# Specify language
curl -X POST "http://localhost:8000/ai-transcribe?url=VIDEO&language=es"
```

---

## Cost Analysis

### 100 Hours of Video

| Provider | Cost | Setup | Speed | Works On |
|----------|------|-------|-------|----------|
| **Local (whisperX)** | **$0** | One command | 70x RT (GPU), 3-5x RT (CPU) | Any server |
| **OpenAI** | **$36** | API key | Fast | Any server |

### When to Use Which

**Use Local (whisperX):**
- ✅ Want $0 cost
- ✅ High transcription volume
- ✅ Privacy-sensitive content
- ✅ Offline transcription needed
- ✅ Need word-level timestamps
- ✅ Works on Railway (CPU mode)
- ✅ Have NVIDIA GPU for maximum speed

**Use OpenAI (Cloud):**
- ✅ Low transcription volume
- ✅ Don't want to manage models
- ✅ Prefer managed cloud service
- ✅ Simpler deployment (no dependencies)

---

## Best Practices

### 1. Smart Transcription First

Always use `/smart-transcribe` - it tries free subtitles first:

```bash
curl -X POST "http://localhost:8000/smart-transcribe?url=VIDEO"
```

- If video has subtitles → $0 cost (instant)
- If no subtitles → Falls back to AI

### 2. Environment-Based Provider

```python
# Development
provider = "local" if is_m1_mac() else "openai"

# Production
provider = os.getenv("TRANSCRIPTION_PROVIDER", "openai")
```

### 3. Error Handling

```python
def transcribe_with_fallback(url: str):
    """Try local, fall back to OpenAI."""
    try:
        # Try local first
        return transcribe(url, provider="local")
    except ImportError:
        # Fall back to cloud
        return transcribe(url, provider="openai")
```

---

## Troubleshooting

### "whisperX not installed"

**Problem:** Trying to use `provider=local` without whisperX

**Solution:**
```bash
pip install whisperx
```

Or switch to OpenAI:
```bash
curl -X POST "http://localhost:8000/ai-transcribe?url=VIDEO&provider=openai"
```

---

### "OPENAI_API_KEY not configured"

**Problem:** Using `provider=openai` without API key

**Solution:**
```bash
# Add to .env file
echo "OPENAI_API_KEY=sk-..." >> .env
```

---

### Slow transcription

**Problem:** Transcription is slower than expected

**Solution:**

**On GPU:**
- Use `turbo` model for best performance (70x real-time)
```bash
curl -X POST "http://localhost:8000/ai-transcribe?url=VIDEO&model_size=turbo&provider=local"
```

**On CPU (Railway):**
- Already optimized with int8, expect 3-5x real-time
- This is normal for CPU processing
- Still faster than OpenAI for short videos
- Use smaller models (tiny/small) for faster processing

---

## FAQ

### Q: Do I need ffmpeg installed?

**A:** No, yt-dlp handles audio extraction automatically.

### Q: Where are models stored?

**A:** `~/.cache/huggingface/hub/` (automatic, no management needed)

### Q: Can I delete models?

**A:** Yes, delete `~/.cache/huggingface/` to free space. Models re-download on next use.

### Q: Does local provider need internet?

**A:** Only for first-time model download. After that, works offline.

### Q: Is OpenAI Whisper really free (local)?

**A:** Yes! Whisper is open source. whisperX is an enhanced implementation with word-level timestamps and better performance.

### Q: Which is more accurate - local or OpenAI?

**A:** Same accuracy - they use the same Whisper models.

### Q: Can I use local provider on Intel Mac?

**A:** Yes! whisperX works on any CPU. Performance will be 3-5x real-time using int8 quantization.

---

## Summary

### For Any Development Environment:
```bash
# Step 1: Install
pip install whisperx

# Step 2: Use
curl -X POST "http://localhost:8000/smart-transcribe?url=VIDEO&provider=local"

# Cost: $0
# Speed: 70x real-time (GPU) or 3-5x (CPU)
```

### For Railway Production:
```bash
# Option 1: Use whisperX in CPU mode (free)
curl -X POST "https://your-api.railway.app/smart-transcribe?url=VIDEO&provider=local"
# Cost: $0
# Speed: 3-5x real-time

# Option 2: Use OpenAI (managed service)
OPENAI_API_KEY=sk-...
curl -X POST "https://your-api.railway.app/smart-transcribe?url=VIDEO&provider=openai"
# Cost: $0.36/hour
```

### Key Takeaways:
- ✅ whisperX based on OpenAI Whisper (open source)
- ✅ Local = free on any platform (CPU/GPU)
- ✅ Works on Railway in CPU mode ($0 cost)
- ✅ Word-level timestamps (not just segments)
- ✅ 70x real-time on GPU, 3-5x on CPU
- ✅ Smart-transcribe tries subtitles first (free)

**You're all set!**

---

## Next Steps

Now that you have transcription set up, check out the platform-specific workflow guides:

- [Composable Workflows Guide](./composable-workflows.md) - Best practices for YouTube, TikTok, Instagram, podcasts
- [Clean API Architecture](./clean-api-architecture.md) - Endpoint design and philosophy
- [Endpoint Flow Diagrams](./endpoint-flows.md) - Technical flow diagrams
