# RunPod Serverless Deployment Guide

Deploy the YT-DLP Transcription API to RunPod Serverless with GPU-accelerated whisperX.

## Architecture

```
Supabase Edge Function
        │
        ▼ POST /run (immediate response)
RunPod Serverless
        │
        ▼ handler.py (thin orchestration layer)
        │
        ▼ job_service.py (existing processing logic)
        │
        ▼ Supabase DB (results saved directly)
```

**Key Benefits:**
- Edge Function returns immediately (no timeout issues)
- GPU acceleration: whisperX runs 70x faster
- Pay only when processing jobs
- Zero code duplication: handler.py reuses existing logic

## Quick Start

### 1. Deploy to RunPod

1. Go to [RunPod Console](https://www.runpod.io/console/serverless)
2. Click **New Endpoint**
3. Select **Custom Template**
4. Configure:
   - **GitHub Repo**: `https://github.com/your-username/yt-dlp-v1`
   - **Branch**: `main`
   - **Build Context**: `.` (root)
   - **Dockerfile Path**: `Dockerfile`

### 2. Set Environment Variables

In RunPod endpoint settings:

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `WORKER_MODEL_SIZE` | No | WhisperX model: `tiny`/`small`/`medium`/`large-v2`/`large-v3` (default: `medium`) |
| `WORKER_PROVIDER` | No | `local` (whisperX) or `openai` (default: `local`) |
| `WORKER_MAX_RETRIES` | No | Max retry attempts (default: `5`) |
| `MAX_CONCURRENT_TRANSCRIPTIONS` | No | Parallel transcriptions (default: `2`) |
| `OPENAI_API_KEY` | No | Required if `WORKER_PROVIDER=openai` |

### 3. Update Supabase Edge Function

Add secrets to Supabase:
```bash
supabase secrets set RUNPOD_ENDPOINT_ID=your-endpoint-id
supabase secrets set RUNPOD_API_KEY=your-runpod-api-key
```

Update Edge Function to call RunPod (see [supabase-edge-function-runpod.md](supabase-edge-function-runpod.md)).

## Implementation Details

### handler.py

The handler is a thin orchestration layer (~85 lines) that:
1. Receives RunPod job format: `{"input": {...}}`
2. Validates input structure
3. Delegates to existing `job_service.py` via `process_job_batch()`
4. Returns structured response

**Zero code duplication** - all business logic stays in `job_service.py`.

```python
# handler.py - simplified view
def handler(job):
    job_input = job.get("input", {})
    result = asyncio.run(process_job_batch(payload=job_input, ...))
    return result

runpod.serverless.start({"handler": handler})
```

### Dockerfile

The Dockerfile starts `handler.py` instead of uvicorn:

```dockerfile
# CUDA base image for GPU support
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# ... dependencies ...

# Start RunPod handler (not uvicorn)
CMD ["python", "-u", "handler.py"]
```

## GPU Performance

| Model | VRAM | Speed vs Realtime | Quality |
|-------|------|-------------------|---------|
| tiny | ~1GB | 200x | Basic |
| small | ~2GB | 100x | Good |
| medium | ~5GB | 70x | Very Good |
| large-v2 | ~10GB | 40x | Excellent |
| large-v3 | ~10GB | 40x | Best |

**Recommendation**: Use `medium` for most cases. Use `large-v3` on A100 for best quality.

## Request/Response Format

### Submit Async Job

```bash
curl -X POST "https://api.runpod.ai/v2/${ENDPOINT_ID}/run" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "queue": "video_audio_transcription",
      "jobs": [
        {"msg_id": 1, "read_ct": 1, "document_id": "uuid-here"}
      ]
    }
  }'
```

**Response (immediate):**
```json
{
  "id": "job-abc123",
  "status": "IN_QUEUE"
}
```

### Check Job Status

```bash
curl "https://api.runpod.ai/v2/${ENDPOINT_ID}/status/${JOB_ID}" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

### Synchronous Execution (Testing)

```bash
curl -X POST "https://api.runpod.ai/v2/${ENDPOINT_ID}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"input": {...}}'
```

## Testing Locally

```bash
# Install dependencies
pip install runpod

# Start local server
python handler.py --rp_serve_api --rp_api_host 0.0.0.0

# Test request
curl -X POST http://localhost:8000/runsync \
  -H "Content-Type: application/json" \
  -d '{"input": {"jobs": [{"msg_id": 1, "document_id": "test-uuid"}]}}'
```

## Troubleshooting

### GPU Not Detected

```bash
# Check in container
python -c "import torch; print(torch.cuda.is_available())"
```

If `False`:
1. Ensure endpoint has GPU allocated
2. Check CUDA drivers are installed
3. Verify base image is CUDA-enabled

### Out of Memory (OOM)

Reduce model size:
```
WORKER_MODEL_SIZE=small  # or tiny
```

### Build Failures

1. Check build logs in RunPod console
2. Verify Dockerfile syntax
3. Ensure all dependencies are in requirements.txt

### Slow Processing

- Check network to Supabase (use same region)
- Increase GPU tier for faster transcription
- Reduce `MAX_CONCURRENT_TRANSCRIPTIONS` if memory issues

## Cost Optimization

### GPU Selection

| GPU | Cost/hr | Best For |
|-----|---------|----------|
| RTX 3090 | ~$0.44 | Development |
| RTX 4090 | ~$0.69 | Production |
| A100 40GB | ~$1.89 | High throughput |

### Scaling Settings

- **Min Workers**: 0 (scale to zero when idle)
- **Max Workers**: Based on expected load
- **Idle Timeout**: 5-10 seconds

## Security

1. **Never commit** API keys or secrets
2. **Use environment variables** for all sensitive data
3. **Restrict Supabase RLS** - service key bypasses RLS, ensure table policies are correct
4. **Monitor usage** - set alerts for unexpected activity

## Related Documentation

- [endpoints-usage.md](endpoints-usage.md#13-runpod-serverless-endpoint) - API reference
- [supabase-edge-function-runpod.md](supabase-edge-function-runpod.md) - Edge Function code
- [RunPod Serverless Docs](https://docs.runpod.io/serverless/overview)
