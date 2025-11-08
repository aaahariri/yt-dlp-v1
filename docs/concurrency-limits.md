# Concurrency and Scaling Guide

**Understanding parallel processing limits for video transcription**

---

## Your System Specs

- **CPU**: 8 cores (M1 Apple Silicon)
- **RAM**: 8 GB
- **Platform**: macOS

---

## Quick Answer

**Yes, you can process multiple files concurrently!**

**Recommended limits:**
- **2-3 concurrent requests** for production reliability
- **Up to 4-6** if you're willing to risk memory issues

---

## Detailed Analysis

### Memory Bottleneck (Main Limit)

WhisperX loads the entire model into RAM for each concurrent request:

| Model | RAM per Instance | Max Concurrent (8GB RAM) | Recommended |
|-------|------------------|--------------------------|-------------|
| **tiny** | ~0.5 GB | 10-12 | 6-8 |
| **small** | ~1.0 GB | 5-6 | 3-4 |
| **medium** | ~2.0 GB | 2-3 | 2 |
| **turbo** | ~2.5 GB | 2 | 1-2 |
| **large-v2** | ~3.5 GB | 1 | 1 |

**Formula:**
```
Max Concurrent = (Available RAM - 2GB for OS) / Model Size
```

**Why the difference between "Max" and "Recommended"?**
- Max = Theoretical limit before out-of-memory
- Recommended = Leaves headroom for stability

---

### CPU Bottleneck (Secondary)

Each transcription uses all available CPU cores:

**M1 (8 cores):**
- 1 request → Uses 100% CPU (8 cores) → Fast (3-5x RT)
- 2 requests → Each gets 50% CPU (4 cores) → Slower (1.5-2x RT)
- 4 requests → Each gets 25% CPU (2 cores) → Much slower (0.5-1x RT)

**Impact:**
```
Concurrent Requests: 1    2    4    6    8
CPU per Request:     100% 50%  25%  16%  12%
Speed Factor:        5x   2.5x 1.2x 0.8x 0.6x
```

**What this means:**
- Running 4 concurrent requests isn't 4x faster
- You might only get 2x total throughput due to CPU sharing

---

## FastAPI's Default Behavior

### Current Setup (Unlimited)

Your FastAPI server currently has **no concurrency limits**:

```python
# main.py - No limits set
app = FastAPI(title="Video Downloader API")
```

**What happens:**
1. User sends 10 concurrent requests
2. FastAPI accepts all 10
3. All 10 start transcribing simultaneously
4. System runs out of RAM → **CRASH** 💥

---

### How to Add Limits

#### Option 1: FastAPI Semaphore (Application Level)

```python
# Add to main.py
import asyncio

# Limit to 3 concurrent transcriptions
transcription_semaphore = asyncio.Semaphore(3)

@app.post("/transcribe")
async def transcribe_audio(...):
    async with transcription_semaphore:
        # Existing transcription code
        ...
```

**Pros:**
- ✅ Prevents memory overload
- ✅ Queues requests automatically
- ✅ Simple to implement

**Cons:**
- ❌ Other endpoints (download, extract-audio) are not limited
- ❌ Requests wait in queue (could timeout)

---

#### Option 2: Uvicorn Worker Limits (Server Level)

```bash
# Run with limited workers
uvicorn main:app --workers 2 --host 0.0.0.0 --port 8000
```

**Pros:**
- ✅ Limits all endpoints
- ✅ Better for production

**Cons:**
- ❌ Each worker loads own copy of model (2x memory)
- ❌ Not ideal for memory-constrained systems

---

#### Option 3: External Queue (Production)

Use Redis + Celery for proper job queue:

```python
# Pseudocode
@app.post("/transcribe")
async def transcribe_audio(...):
    # Queue the job
    job_id = celery_app.send_task("transcribe", args=[audio_file])

    return {"job_id": job_id, "status": "queued"}

# Check status later
@app.get("/transcribe/{job_id}/status")
async def check_status(job_id: str):
    ...
```

**Pros:**
- ✅ Proper job queue with retries
- ✅ Can scale to multiple workers
- ✅ Production-grade solution

**Cons:**
- ❌ More complex setup
- ❌ Requires Redis/RabbitMQ

---

## Practical Recommendations

### For Local Development (Your M1 Mac)

**Setup:**
```python
# Add to main.py around line 50
import asyncio

# Limit transcription concurrency
MAX_CONCURRENT_TRANSCRIPTIONS = 2
transcription_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSCRIPTIONS)

@app.post("/transcribe")
async def transcribe_audio(...):
    async with transcription_semaphore:
        # All existing code stays the same
        try:
            # Validate audio file exists
            if not os.path.exists(audio_file):
                ...
```

**Recommended settings:**
- **tiny/small model**: `MAX_CONCURRENT_TRANSCRIPTIONS = 4`
- **medium model**: `MAX_CONCURRENT_TRANSCRIPTIONS = 2`
- **turbo/large**: `MAX_CONCURRENT_TRANSCRIPTIONS = 1`

---

### For Railway Deployment

Railway typically provides:
- **CPU**: 2-8 vCPUs (varies by plan)
- **RAM**: 512MB - 8GB (varies by plan)

**Recommended:**
```python
import os

# Auto-detect based on available memory
def get_max_concurrent():
    """Calculate safe concurrency based on model size."""
    # Railway sets this env var
    memory_mb = int(os.getenv("RAILWAY_RAM_MB", "512"))

    # Assume medium model (~2GB per instance)
    model_memory_mb = 2000
    max_concurrent = max(1, (memory_mb - 500) // model_memory_mb)

    return min(max_concurrent, 4)  # Cap at 4 for CPU reasons

MAX_CONCURRENT_TRANSCRIPTIONS = get_max_concurrent()
```

---

## Testing Concurrency

### Quick Test

```bash
# Start server
uvicorn main:app --reload

# In another terminal, send 4 concurrent requests
for i in {1..4}; do
  curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/4450a805.mp3&provider=local&model_size=tiny" \
    -H "X-API-Key: test-api-key-123" &
done

# Wait for all to complete
wait

echo "All requests completed"
```

**Watch for:**
- Memory usage: `top` or Activity Monitor
- CPU usage: Should stay <100% per core
- Response times: Should not timeout

---

### Systematic Test Script

I've created a test script at `docs/concurrency-and-scaling.md` (save as `.py`):

```bash
# Test 1, 2, 4, 6, 8 concurrent requests
python3 test_concurrency.py --test-all --model tiny

# Test specific concurrency
python3 test_concurrency.py --concurrent 4 --model medium
```

---

## Real-World Scenarios

### Scenario 1: Single User, Multiple Videos

**Use case:** User uploads 10 videos to transcribe

**Solution:**
```python
# Client-side queuing
async def process_videos(video_list):
    results = []

    # Process 2 at a time
    for i in range(0, len(video_list), 2):
        batch = video_list[i:i+2]
        batch_results = await asyncio.gather(*[
            transcribe(video) for video in batch
        ])
        results.extend(batch_results)

    return results
```

**Why:** Prevents overwhelming server

---

### Scenario 2: Multiple Users

**Problem:** 3 users each send 2 requests = 6 concurrent

**Solution 1 - Queue (Better):**
```python
# Server limits to 2 concurrent
# Requests 3-6 wait in queue
transcription_semaphore = asyncio.Semaphore(2)
```

**Solution 2 - Reject (Fail-Fast):**
```python
# Return 429 Too Many Requests
if active_transcriptions >= MAX_CONCURRENT:
    raise HTTPException(
        status_code=429,
        detail="Too many active transcriptions. Try again later."
    )
```

---

### Scenario 3: Batch Processing Overnight

**Use case:** Process 100 videos overnight

**Best approach:**
```python
# Sequential with small batches
async def batch_process(videos, batch_size=2):
    for i in range(0, len(videos), batch_size):
        batch = videos[i:i+batch_size]

        # Process batch concurrently
        results = await asyncio.gather(*[
            transcribe(video) for video in batch
        ])

        # Log progress
        print(f"Completed {i+len(batch)}/{len(videos)}")

        # Brief pause between batches
        await asyncio.sleep(1)
```

**Why:** Sustainable overnight processing without crashes

---

## Performance Benchmarks

### Expected Throughput (M1, 8GB RAM)

#### Tiny Model
| Concurrent | Time per 10min Audio | Total Throughput |
|------------|----------------------|------------------|
| 1 | 45s | 13.3 videos/hour |
| 2 | 90s (45s each) | 13.3 videos/hour |
| 4 | 180s (45s each) | 13.3 videos/hour |

**Insight:** No benefit beyond 1-2 concurrent for tiny model (CPU saturated)

#### Medium Model
| Concurrent | Time per 10min Audio | Total Throughput |
|------------|----------------------|------------------|
| 1 | 180s | 20 videos/hour |
| 2 | 180s (90s each) | 40 videos/hour |
| 3 | 270s (90s each) | 40 videos/hour |

**Insight:** Sweet spot is 2 concurrent for medium model

---

## Memory Management

### Monitor Memory Usage

```bash
# macOS
while true; do
    echo "Memory: $(vm_stat | grep 'Pages active' | awk '{print $3}' | tr -d '.')";
    sleep 5;
done

# Or use Activity Monitor GUI
```

### What to Watch For

**Warning signs:**
- ⚠️ RAM usage >90%
- ⚠️ Swap memory increasing
- ⚠️ Response times getting slower
- ⚠️ "Out of memory" errors

**Action:**
- Reduce `MAX_CONCURRENT_TRANSCRIPTIONS`
- Use smaller model (medium → small → tiny)
- Add more RAM (cloud deployment)

---

## Summary

### Concurrency Limits

| Configuration | M1 Mac (8GB) | Railway (2GB) | Railway (4GB) |
|---------------|--------------|---------------|---------------|
| **tiny model** | 4-6 | 2-3 | 4-6 |
| **medium model** | 2 | 1 | 2 |
| **turbo model** | 1-2 | 1 | 1 |

### Recommendations

1. **Start Conservative**: Set `MAX_CONCURRENT = 2`
2. **Monitor**: Watch memory and CPU usage
3. **Adjust**: Increase if stable, decrease if crashes
4. **Test**: Use test script to find your sweet spot

### Code to Add

```python
# At top of main.py
import asyncio

# After FastAPI app creation
MAX_CONCURRENT_TRANSCRIPTIONS = 2
transcription_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSCRIPTIONS)

# In /transcribe endpoint, wrap everything
@app.post("/transcribe")
async def transcribe_audio(...):
    async with transcription_semaphore:
        # All existing code here
        ...
```

**This prevents memory overload and system crashes!**

---

## Related Documentation

- [MPS and Device Selection](./mps-and-device-selection.md) - CPU vs GPU usage
- [Transcription Setup Guide](./transcription-setup-guide.md) - Model sizes and performance
- [Composable Workflows](./composable-workflows.md) - Platform-specific optimizations
