"""
Supabase service module for cloud storage and database operations.

This module provides utilities for:
- Supabase client initialization and access
- Screenshot uploads to Supabase storage
- Metadata storage in Supabase database
"""

from typing import Optional, Dict
from fastapi import HTTPException
from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_SERVICE_KEY


# Supabase client initialization (optional, only if configured)
supabase_client: Optional[Client] = None

try:
    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print("INFO: Supabase client initialized successfully")
    else:
        print("INFO: Supabase not configured (SUPABASE_URL/SUPABASE_SERVICE_KEY missing) - transcription storage disabled")
except Exception as e:
    print(f"WARNING: Failed to initialize Supabase client: {str(e)}")
    supabase_client = None


def get_supabase_client() -> Client:
    """
    Get Supabase client or raise error if not configured.

    This function should be used in endpoints that require Supabase to ensure
    proper error handling when Supabase is not configured.

    Returns:
        Initialized Supabase client instance

    Raises:
        HTTPException: 503 Service Unavailable if Supabase is not configured

    Example:
        >>> try:
        ...     client = get_supabase_client()
        ...     # Use client for operations
        ... except HTTPException as e:
        ...     print("Supabase not available")
    """
    if supabase_client is None:
        raise HTTPException(
            status_code=503,
            detail="Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables."
        )
    return supabase_client


def upload_screenshot_to_supabase(file_path: str, storage_path: str) -> Dict[str, str]:
    """
    Upload screenshot to Supabase storage bucket.

    Uploads an image file to the 'public_media' storage bucket and returns
    the storage path and public URL for accessing the uploaded file.

    Args:
        file_path: Local filesystem path to the image file
        storage_path: Destination path within the Supabase storage bucket

    Returns:
        Dictionary containing:
        - storage_path: Path in Supabase storage
        - public_url: Public URL for accessing the uploaded file

    Raises:
        HTTPException: If Supabase is not configured
        Exception: If file upload or URL retrieval fails

    Example:
        >>> result = upload_screenshot_to_supabase(
        ...     "/tmp/screenshot.jpg",
        ...     "screenshots/2024/01/video-123.jpg"
        ... )
        >>> print(f"Uploaded to: {result['public_url']}")
    """
    supabase = get_supabase_client()

    with open(file_path, 'rb') as f:
        result = supabase.storage.from_("public_media").upload(
            path=storage_path,
            file=f.read(),
            file_options={"content-type": "image/jpeg"}
        )

    # Get public URL
    public_url = supabase.storage.from_("public_media").get_public_url(storage_path)

    return {
        "storage_path": storage_path,
        "public_url": public_url
    }


def save_screenshot_metadata(data: Dict) -> Optional[Dict]:
    """
    Save screenshot metadata to public_media table.

    Inserts a new row into the public_media table with screenshot metadata
    including URL, timestamp, video information, and quality settings.

    Args:
        data: Dictionary containing screenshot metadata fields:
            - url: Source video URL
            - timestamp: Screenshot timestamp in seconds
            - video_title: Title of the source video
            - video_id: Unique identifier for the video
            - screenshot_url: Public URL of the uploaded screenshot
            - storage_path: Storage path in Supabase
            - quality: Quality setting used for extraction
            - format: Screenshot image format
            - file_size: Size of the screenshot file in bytes
            - resolution: Image resolution (e.g., "1920x1080")

    Returns:
        Inserted row data as dictionary, or None if insertion failed

    Raises:
        HTTPException: If Supabase is not configured
        Exception: If database insertion fails

    Example:
        >>> metadata = {
        ...     "url": "https://youtube.com/watch?v=...",
        ...     "timestamp": 42.5,
        ...     "video_title": "Amazing Video",
        ...     "screenshot_url": "https://...",
        ...     "quality": 2
        ... }
        >>> result = save_screenshot_metadata(metadata)
        >>> print(f"Saved with ID: {result['id']}")
    """
    supabase = get_supabase_client()
    result = supabase.table("public_media").insert(data).execute()
    return result.data[0] if result.data else None
