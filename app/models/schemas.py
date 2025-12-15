"""
Pydantic models for request/response validation.

This module contains all Pydantic BaseModel schemas used for API request
and response validation. These are data validation models, not AI models.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class BatchDownloadRequest(BaseModel):
    """Request model for batch downloads: validates URLs, format, delays, etc."""
    urls: List[str] = Field(..., description="List of video URLs to download", min_items=1)
    format: str = Field("best[height<=720]", description="Video quality format")
    keep: bool = Field(True, description="Save videos to server storage")
    min_delay: int = Field(5, description="Minimum delay between downloads (seconds)", ge=0, le=300)
    max_delay: int = Field(10, description="Maximum delay between downloads (seconds)", ge=0, le=300)
    cookies_file: Optional[str] = Field(None, description="Path to cookies file")


class VideoDownloadResult(BaseModel):
    """Result for individual video: url, success, filename, size, platform, error."""
    url: str
    success: bool
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    platform: Optional[str] = None
    title: Optional[str] = None
    error: Optional[str] = None


class BatchDownloadResponse(BaseModel):
    """Response with stats and per-video results: total, successful, failed, skipped, downloads[]."""
    total: int
    successful: int
    failed: int
    skipped: int
    downloads: List[VideoDownloadResult]
    total_size: int
    duration_seconds: float


class TranscriptionSaveRequest(BaseModel):
    """Request model for saving transcriptions to Supabase document_transcriptions table."""
    document_id: str = Field(..., description="UUID of the document (foreign key to documents table)")
    segments: List[Dict[str, Any]] = Field(..., description="Transcription segments with start, end, text")
    language: str = Field(..., description="Language code (e.g., 'en', max 5 chars)")
    source: str = Field(..., description="Source: 'subtitle' or 'ai' (max 50 chars)")
    confidence_score: Optional[float] = Field(None, description="Confidence score (0.0-1.0)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (JSONB)")


class TranscriptionSaveResponse(BaseModel):
    """Response after saving transcription."""
    id: str = Field(..., description="Transcription record ID (UUID)")
    document_id: str
    created_at: str
    message: str


class ScreenshotRequest(BaseModel):
    """Request model for screenshot extraction from video at timestamps."""
    video_url: str
    timestamps: List[str]  # SRT format "00:01:30,500" or float seconds "90.5"
    upload_to_supabase: bool = False
    document_id: Optional[str] = None
    quality: int = 2  # FFmpeg JPEG quality 1-31 (lower = better)


class ScreenshotResult(BaseModel):
    """Result for individual screenshot: timestamp, path, dimensions, size."""
    timestamp: float
    timestamp_formatted: str
    file_path: str
    width: int
    height: int
    size_bytes: int
    supabase_url: Optional[str] = None


class ScreenshotResponse(BaseModel):
    """Response with extracted screenshots and metadata."""
    screenshots: List[ScreenshotResult]
    video_id: str
    video_title: str
    video_duration: Optional[int]
    video_cached: bool
    total_extracted: int
    failed_timestamps: List[str] = []
