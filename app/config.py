"""
Configuration module for yt-dlp video downloader API.

This module centralizes all environment variables, constants, and runtime configuration
using pydantic-settings for type-safe configuration management.
"""

import os
import subprocess
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # CORS Configuration
    allowed_origin: str = Field(
        default="https://example.com",
        validation_alias="ALLOWED_ORIGIN",
        description="Allowed CORS origin for API requests"
    )

    # API Authentication
    api_key: str = Field(
        default="",
        validation_alias="API_KEY",
        description="API key for endpoint authentication"
    )

    # Job Worker Token (for Supabase Edge Function → Python communication)
    py_api_token: Optional[str] = Field(
        default=None,
        validation_alias="PY_API_TOKEN",
        description="Token for authenticating job requests from Supabase Edge Functions"
    )

    # Directory Configuration
    downloads_dir: str = Field(
        default="./downloads",
        validation_alias="DOWNLOADS_DIR",
        description="Directory for saved videos (when keep=true)"
    )

    cache_dir: str = Field(
        default="./cache",
        validation_alias="CACHE_DIR",
        description="Unified cache directory for temporary files"
    )

    cache_ttl_hours: int = Field(
        default=3,
        validation_alias="CACHE_TTL_HOURS",
        description="Time-to-live for cached files in hours"
    )

    # Deprecated - kept for backward compatibility
    transcriptions_dir: Optional[str] = Field(
        default=None,
        validation_alias="TRANSCRIPTIONS_DIR",
        description="Legacy transcriptions directory (deprecated, use cache_dir/transcriptions)"
    )

    # yt-dlp Configuration
    ytdlp_binary: str = Field(
        default="./bin/yt-dlp",
        validation_alias="YTDLP_BINARY",
        description="Path to standalone yt-dlp binary"
    )

    ytdlp_cookies_file: Optional[str] = Field(
        default=None,
        validation_alias="YTDLP_COOKIES_FILE",
        description="Path to cookies.txt for authenticated downloads"
    )

    ytdlp_min_sleep: int = Field(
        default=7,
        validation_alias="YTDLP_MIN_SLEEP",
        description="Minimum seconds between YouTube requests"
    )

    ytdlp_max_sleep: int = Field(
        default=25,
        validation_alias="YTDLP_MAX_SLEEP",
        description="Maximum seconds between YouTube requests"
    )

    ytdlp_sleep_requests: float = Field(
        default=1.0,
        validation_alias="YTDLP_SLEEP_REQUESTS",
        description="Seconds between API requests"
    )

    # YouTube Cookie Refresh
    youtube_email: Optional[str] = Field(
        default=None,
        validation_alias="YOUTUBE_EMAIL",
        description="YouTube account email for cookie refresh"
    )

    youtube_password: Optional[str] = Field(
        default=None,
        validation_alias="YOUTUBE_PASSWORD",
        description="YouTube account password for cookie refresh"
    )

    ytdlp_cookie_refresh_days: int = Field(
        default=5,
        validation_alias="YTDLP_COOKIE_REFRESH_DAYS",
        description="Automated cookie refresh interval in days"
    )

    # Concurrency Control
    max_concurrent_transcriptions: int = Field(
        default=2,
        validation_alias="MAX_CONCURRENT_TRANSCRIPTIONS",
        description="Maximum concurrent transcription requests"
    )

    # Supabase Configuration
    supabase_url: Optional[str] = Field(
        default=None,
        validation_alias="SUPABASE_URL",
        description="Supabase project URL"
    )

    supabase_service_key: Optional[str] = Field(
        default=None,
        validation_alias="SUPABASE_SERVICE_KEY",
        description="Supabase service role key"
    )

    # Transcription Worker Configuration
    transcription_worker_enabled: bool = Field(
        default=True,
        validation_alias="TRANSCRIPTION_WORKER_ENABLED",
        description="Enable/disable background transcription worker"
    )

    worker_poll_interval: int = Field(
        default=5,
        validation_alias="WORKER_POLL_INTERVAL",
        description="Seconds between queue polls when idle"
    )

    worker_batch_size: int = Field(
        default=10,
        validation_alias="WORKER_BATCH_SIZE",
        description="Maximum jobs to dequeue per poll"
    )

    worker_vt_seconds: int = Field(
        default=1800,
        validation_alias="WORKER_VT_SECONDS",
        description="Visibility timeout in seconds (30 minutes)"
    )

    worker_max_retries: int = Field(
        default=5,
        validation_alias="WORKER_MAX_RETRIES",
        description="Maximum retry attempts before marking job as failed"
    )

    worker_startup_delay: int = Field(
        default=5,
        validation_alias="WORKER_STARTUP_DELAY",
        description="Seconds to wait before first poll after startup"
    )

    worker_model_size: str = Field(
        default="medium",
        validation_alias="WORKER_MODEL_SIZE",
        description="WhisperX model size for AI transcription"
    )

    worker_provider: str = Field(
        default="local",
        validation_alias="WORKER_PROVIDER",
        description="Transcription provider (local or openai)"
    )

    provider_name: str = Field(
        default="yt-dlp-api",
        validation_alias="PROVIDER_NAME",
        description="Provider name for metadata tagging in transcriptions"
    )

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
        description="OpenAI API key for transcription"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()


# Initialize settings
settings = get_settings()

# Export commonly used directory paths
DOWNLOADS_DIR = settings.downloads_dir
CACHE_DIR = settings.cache_dir
CACHE_TTL_HOURS = settings.cache_ttl_hours

# Create directories on startup
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Create cache subdirectories
for subdir in ["videos", "audio", "transcriptions", "screenshots"]:
    os.makedirs(os.path.join(CACHE_DIR, subdir), exist_ok=True)

# TRANSCRIPTIONS_DIR - derived from cache directory structure
TRANSCRIPTIONS_DIR = os.path.join(CACHE_DIR, "transcriptions")

# yt-dlp Configuration
YTDLP_BINARY = settings.ytdlp_binary
YTDLP_COOKIES_FILE = settings.ytdlp_cookies_file
YTDLP_MIN_SLEEP = settings.ytdlp_min_sleep
YTDLP_MAX_SLEEP = settings.ytdlp_max_sleep
YTDLP_SLEEP_REQUESTS = settings.ytdlp_sleep_requests

# yt-dlp extractor args (currently empty but used throughout main.py)
YTDLP_EXTRACTOR_ARGS = {}

# Concurrency control
MAX_CONCURRENT_TRANSCRIPTIONS = settings.max_concurrent_transcriptions

# Supabase Configuration
SUPABASE_URL = settings.supabase_url
SUPABASE_SERVICE_KEY = settings.supabase_service_key

# Whisper device detection for AI transcription
# Detect optimal device on startup to avoid repeated detection per request
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_GPU_INFO = None

try:
    import torch

    if torch.cuda.is_available():
        WHISPER_DEVICE = "cuda"
        WHISPER_COMPUTE_TYPE = "float16"

        # Try to get GPU model name
        try:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_count = torch.cuda.device_count()
            WHISPER_GPU_INFO = f"{gpu_name} (x{gpu_count})" if gpu_count > 1 else gpu_name
            print(f"INFO: NVIDIA GPU detected - whisperX will use CUDA with float16 compute type")
            print(f"INFO: GPU Model: {WHISPER_GPU_INFO}")
        except Exception:
            WHISPER_GPU_INFO = "CUDA GPU (model unknown)"
            print(f"INFO: NVIDIA GPU (CUDA) detected - whisperX will use CUDA with float16 compute type")

    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        WHISPER_DEVICE = "mps"
        WHISPER_COMPUTE_TYPE = "float16"

        # For Apple Silicon, we can infer from system info
        try:
            import platform
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                  capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                cpu_info = result.stdout.strip()
                WHISPER_GPU_INFO = f"Apple Silicon ({cpu_info})"
            else:
                WHISPER_GPU_INFO = "Apple Silicon GPU"
        except Exception:
            WHISPER_GPU_INFO = "Apple Silicon GPU"

        print(f"INFO: Apple Silicon GPU detected - whisperX will use MPS with float16 compute type")
        if WHISPER_GPU_INFO:
            print(f"INFO: GPU Model: {WHISPER_GPU_INFO}")
    else:
        print(f"INFO: No GPU detected - whisperX will use CPU with int8 compute type (slower)")
except ImportError:
    print(f"INFO: PyTorch not installed - whisperX device detection skipped (will fallback to CPU if used)")
except Exception as e:
    print(f"WARNING: Device detection failed ({str(e)}) - whisperX will default to CPU")


# Log yt-dlp binary status on module import
def _log_ytdlp_status():
    """Log yt-dlp binary version and configuration on startup."""
    if os.path.exists(YTDLP_BINARY):
        try:
            result = subprocess.run(
                [YTDLP_BINARY, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"INFO: yt-dlp standalone binary version: {result.stdout.strip()}")
                print(f"INFO: Rate limiting: {YTDLP_MIN_SLEEP}-{YTDLP_MAX_SLEEP}s between downloads")
        except Exception as e:
            print(f"WARNING: Could not get yt-dlp version: {e}")
    else:
        print(f"WARNING: yt-dlp binary not found at {YTDLP_BINARY}")
        print("WARNING: YouTube downloads may fail. Download from: https://github.com/yt-dlp/yt-dlp/releases")


_log_ytdlp_status()

# Log concurrency settings
print(f"INFO: Max concurrent transcriptions set to: {MAX_CONCURRENT_TRANSCRIPTIONS}")

# Log Supabase status
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    print("INFO: Supabase configuration detected")
else:
    print("INFO: Supabase not configured (SUPABASE_URL/SUPABASE_SERVICE_KEY missing) - transcription storage disabled")
