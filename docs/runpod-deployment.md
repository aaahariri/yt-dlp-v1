# RunPod Deployment Guide

Deploy the YT-DLP Video Downloader API to RunPod with GPU-accelerated transcription.

## Quick Start

### 1. Build and Push Docker Image

```bash
# Build the image
docker build -t your-registry/yt-dlp-api:latest .

# Push to Docker Hub or your registry
docker push your-registry/yt-dlp-api:latest
```

### 2. Create RunPod Pod

1. Go to [RunPod Console](https://www.runpod.io/console/pods)
2. Click **Deploy** → **Custom Template**
3. Configure:
   - **Container Image**: `your-registry/yt-dlp-api:latest`
   - **GPU Type**: RTX 3090 / RTX 4090 / A100 (any CUDA-capable GPU)
   - **Volume Size**: 20GB+ (for model cache)
   - **Expose HTTP Ports**: `8000`

### 3. Set Environment Variables

In RunPod pod settings, add these environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `ALLOWED_ORIGIN` | Yes | CORS origin (e.g., `https://yourapp.com`) |
| `API_KEY` | Yes | API authentication key |
| `PY_API_TOKEN` | No | Supabase Edge Function auth token |
| `SUPABASE_URL` | No | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | No | Supabase service role key |
| `WORKER_MODEL_SIZE` | No | WhisperX model: `tiny`/`small`/`medium`/`large-v2`/`large-v3` (default: `medium`) |
| `OPENAI_API_KEY` | No | For OpenAI Whisper API transcription |

## Dockerfile Overview

The Dockerfile is optimized for RunPod GPU pods:

```
Base Image: nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04
├── Python 3.12
├── PyTorch + CUDA 12.1
├── whisperX (GPU-accelerated transcription)
├── yt-dlp (standalone binary + Deno)
├── FFmpeg
└── Playwright (optional: YouTube cookie refresh)
```

### GPU Performance

| Model | VRAM Usage | Speed (vs realtime) | Quality |
|-------|------------|---------------------|---------|
| tiny | ~1GB | 200x | Basic |
| small | ~2GB | 100x | Good |
| medium | ~5GB | 70x | Very Good |
| large-v2 | ~10GB | 40x | Excellent |
| large-v3 | ~10GB | 40x | Best |

**Recommendation**: Use `medium` for most cases. Use `large-v3` on A100/A6000 for best quality.

## Volume Mounts

For persistent storage, mount a RunPod volume to `/app/cache`:

```
/app
├── cache/              # Mount point for persistent cache
│   ├── videos/
│   ├── audio/
│   ├── transcriptions/
│   └── screenshots/
├── downloads/          # Permanent downloads
└── cookies.txt         # YouTube auth (optional)
```

## YouTube Cookie Authentication

To enable authenticated YouTube downloads:

1. **Generate cookies locally**:
   ```bash
   python scripts/refresh_youtube_cookies.py --interactive
   ```

2. **Upload to RunPod** via:
   - Pod terminal: `nano /app/cookies.txt` and paste contents
   - Or mount as a volume from your registry

3. **Set environment variable**:
   ```
   YTDLP_COOKIES_FILE=/app/cookies.txt
   ```

## API Endpoints

Once deployed, access:
- **API Root**: `https://your-pod-id.runpod.io/`
- **API Docs**: `https://your-pod-id.runpod.io/docs`
- **Health Check**: `https://your-pod-id.runpod.io/` (returns status)

### Example Request

```bash
curl -X POST "https://your-pod-id.runpod.io/transcribe-audio" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=...", "language": "en"}'
```

## Troubleshooting

### GPU Not Detected

Check GPU status in the container:
```bash
python -c "import torch; print(torch.cuda.is_available())"
```

If `False`, ensure:
1. Pod has GPU allocated
2. NVIDIA drivers are installed on the pod
3. Image was built with CUDA support

### Out of Memory (OOM)

Reduce model size:
```
WORKER_MODEL_SIZE=small  # or tiny
```

Or increase GPU VRAM (use larger GPU tier).

### yt-dlp Errors

1. Check yt-dlp version: `/app/bin/yt-dlp --version`
2. Update yt-dlp: `pip install -U yt-dlp`
3. Check Deno is installed: `deno --version`

### Slow Downloads

YouTube rate-limits aggressive downloaders. Configure:
```
YTDLP_MIN_SLEEP=10
YTDLP_MAX_SLEEP=30
```

## Cost Optimization

### Serverless vs Pod

| Deployment | Best For | Cost Model |
|------------|----------|------------|
| **Pod** | Persistent API, steady traffic | Hourly rate |
| **Serverless** | Burst traffic, infrequent use | Per-second billing |

### GPU Selection

| GPU | Cost/hr | Best For |
|-----|---------|----------|
| RTX 3090 | ~$0.44 | Development, small-medium workloads |
| RTX 4090 | ~$0.69 | Production, medium workloads |
| A100 40GB | ~$1.89 | Large models, high throughput |

## Building for Different Architectures

### CPU-Only (No GPU)

Modify Dockerfile base image:
```dockerfile
FROM python:3.12-slim
# Remove torch CUDA installation
# Use: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### ARM64 (Apple Silicon locally)

```bash
docker buildx build --platform linux/amd64 -t yt-dlp-api .
```

## Security Notes

1. **Never commit** `cookies.txt` or `.env` files
2. **Use secrets** for `API_KEY`, `SUPABASE_SERVICE_KEY`
3. **Restrict CORS** - don't use `ALLOWED_ORIGIN=*` in production
4. **Network policies** - use RunPod's built-in firewall
