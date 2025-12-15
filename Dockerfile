# ==============================================================================
# RunPod Deployment Dockerfile for YT-DLP Video Downloader API
# ==============================================================================
# Base: NVIDIA CUDA for GPU-accelerated whisperX transcription
# Features: yt-dlp, whisperX, FastAPI, ffmpeg, Deno
# ==============================================================================

# Use NVIDIA CUDA base image with Python support
# RunPod recommends CUDA images for GPU workloads
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# ==============================================================================
# Install system dependencies
# ==============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python 3.12
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    # FFmpeg for audio/video processing (required by yt-dlp and whisperX)
    ffmpeg \
    # Git (for pip packages from git repos)
    git \
    # Build tools (for some Python packages)
    build-essential \
    # Networking tools
    curl \
    wget \
    ca-certificates \
    # For Playwright (optional - YouTube cookie refresh)
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ==============================================================================
# Install Deno (required by yt-dlp for some extractors)
# ==============================================================================
RUN curl -fsSL https://deno.land/install.sh | sh
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

# ==============================================================================
# Set Python 3.12 as default
# ==============================================================================
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# ==============================================================================
# Create virtual environment and install Python dependencies
# ==============================================================================
RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Install PyTorch with CUDA support first (for GPU acceleration)
# Using PyTorch 2.1+ for CUDA 12.1 compatibility
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install additional dependencies for RunPod
RUN pip install \
    pydantic-settings \
    apscheduler \
    playwright

# Install Playwright browsers (for YouTube cookie refresh)
RUN playwright install chromium || true

# ==============================================================================
# Create directory structure
# ==============================================================================
RUN mkdir -p /app/bin \
    /app/cache/videos \
    /app/cache/audio \
    /app/cache/transcriptions \
    /app/cache/screenshots \
    /app/downloads \
    /app/transcriptions

# ==============================================================================
# Download latest yt-dlp standalone binary
# ==============================================================================
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /app/bin/yt-dlp \
    && chmod +x /app/bin/yt-dlp

# Verify yt-dlp installation
RUN /app/bin/yt-dlp --version

# ==============================================================================
# Copy application code
# ==============================================================================
COPY . .

# ==============================================================================
# Environment variable defaults (override at runtime)
# ==============================================================================
# Server configuration
ENV PORT=8000
ENV HOST=0.0.0.0

# yt-dlp configuration
ENV YTDLP_BINARY=/app/bin/yt-dlp
ENV YTDLP_COOKIES_FILE=/app/cookies.txt
ENV YTDLP_MIN_SLEEP=7
ENV YTDLP_MAX_SLEEP=25

# Cache configuration
ENV CACHE_DIR=/app/cache
ENV CACHE_TTL_HOURS=3
ENV DOWNLOADS_DIR=/app/downloads

# Worker configuration (whisperX)
ENV WORKER_MODEL_SIZE=medium
ENV WORKER_PROVIDER=local
ENV MAX_CONCURRENT_TRANSCRIPTIONS=2

# CORS (override this in production!)
ENV ALLOWED_ORIGIN=*

# ==============================================================================
# Health check
# ==============================================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

# ==============================================================================
# Expose port
# ==============================================================================
EXPOSE 8000

# ==============================================================================
# Start command
# ==============================================================================
# Use uvicorn with proper settings for production
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
