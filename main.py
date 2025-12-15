"""
YT-DLP Video Downloader API - Main Entry Point

This is the main entry point for the FastAPI application.
All business logic is organized in app/routers modules.
Configuration is managed in app/config.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.routers import (
    download,
    subtitles,
    audio,
    transcription,
    playlist,
    screenshot,
    cache,
    admin
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown tasks.

    Startup:
        - Directories are already created by app.config module
        - Cookie scheduler is started by admin router
        - Transcription worker is started by transcription router

    Shutdown:
        - Cleanup tasks handled by individual routers
    """
    # Startup
    print("INFO: Application startup complete")
    yield
    # Shutdown
    print("INFO: Application shutdown complete")


# Initialize settings
settings = get_settings()

# Create FastAPI application
app = FastAPI(
    title="YT-DLP Video Downloader API",
    description="Social media video downloader powered by yt-dlp. Supports 1000+ platforms including YouTube, TikTok, Instagram, Facebook, and more.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - allow requests from configured origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
# Note: Routers define their own path prefixes
app.include_router(download.router)
app.include_router(subtitles.router)
app.include_router(audio.router)
app.include_router(transcription.router)
app.include_router(playlist.router)
app.include_router(screenshot.router)
app.include_router(cache.router)
app.include_router(admin.router)


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API information.

    Returns:
        API name, version, and status
    """
    return {
        "message": "YT-DLP Video Downloader API",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs"
    }


# Entry point for direct execution
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
