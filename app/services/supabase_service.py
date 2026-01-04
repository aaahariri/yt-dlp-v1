"""
Supabase service module for cloud storage and database operations.

This module provides utilities for:
- Supabase client initialization and access
- Screenshot uploads to Supabase storage
- Metadata storage in Supabase database
- System alerts with spam prevention
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
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
            file_options={"content-type": "image/jpeg", "upsert": "true"}
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


def save_screenshot_with_job_metadata(
    base_data: Dict,
    job_metadata: Dict
) -> Optional[Dict]:
    """
    Save screenshot to public_media with job tracking in metadata.

    This is used by the screenshot job service to include job tracking fields
    in the metadata JSONB field.

    Args:
        base_data: Base screenshot data dict with type, storage_path, etc.
        job_metadata: Job tracking fields to merge into metadata:
            - job_id: UUID string
            - storage_status: "temp" or "confirmed"
            - job_received_at: ISO timestamp
            - job_completed_at: ISO timestamp
            - worker: "runpod", "local", etc.

    Returns:
        Inserted row data as dictionary, or None if insertion failed

    Example:
        >>> base_data = {
        ...     "type": "screenshot",
        ...     "storage_path": "screenshots/xyz/1000.jpg",
        ...     "metadata": {"video_id": "xyz", "timestamp": 1.0}
        ... }
        >>> job_metadata = {
        ...     "job_id": "abc-123",
        ...     "storage_status": "temp",
        ...     "worker": "runpod"
        ... }
        >>> result = save_screenshot_with_job_metadata(base_data, job_metadata)
    """
    supabase = get_supabase_client()

    # Merge job_metadata into the existing metadata field
    data = base_data.copy()
    existing_metadata = data.get("metadata", {})
    if existing_metadata is None:
        existing_metadata = {}
    existing_metadata.update(job_metadata)
    data["metadata"] = existing_metadata

    result = supabase.table("public_media").insert(data).execute()
    return result.data[0] if result.data else None


# =============================================================================
# System Alerts
# =============================================================================

def send_alert(
    alert_type: str,
    message: str,
    severity: str = "warning",
    context: Optional[Dict[str, Any]] = None,
    cooldown_minutes: int = 60
) -> Optional[Dict]:
    """
    Send a system alert to the system_alerts table with spam prevention.

    Checks for recent similar alerts (same type) within the cooldown period
    before inserting a new alert. This prevents spamming the alerts table
    when the same error occurs repeatedly.

    Args:
        alert_type: Type of alert (e.g., 'youtube_auth_failure', 'job_failed')
        message: Human-readable alert message
        severity: Alert severity - 'info', 'warning', or 'critical'
        context: Optional dict with additional context (stored as JSONB)
        cooldown_minutes: Don't create duplicate alerts within this window (default: 60)

    Returns:
        Inserted alert data dict, or None if:
        - Supabase not configured
        - Recent similar alert exists (spam prevention)
        - Insert failed

    Example:
        >>> send_alert(
        ...     alert_type="youtube_auth_failure",
        ...     message="Cookie refresh failed - 2FA challenge detected",
        ...     severity="critical",
        ...     context={"email": "user@example.com", "error": "2FA required"},
        ...     cooldown_minutes=30
        ... )
    """
    if supabase_client is None:
        print(f"WARNING: Alert not sent (Supabase not configured): [{severity}] {alert_type}: {message}")
        return None

    try:
        # Check for recent similar alerts (spam prevention)
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)

        recent_alerts = supabase_client.table("system_alerts").select("id, created_at").eq(
            "alert_type", alert_type
        ).gte(
            "created_at", cutoff_time.isoformat()
        ).limit(1).execute()

        if recent_alerts.data:
            print(f"INFO: Skipping duplicate alert (cooldown): {alert_type} - last alert at {recent_alerts.data[0]['created_at']}")
            return None

        # Insert new alert
        alert_data = {
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "context": context or {}
        }

        result = supabase_client.table("system_alerts").insert(alert_data).execute()

        if result.data:
            print(f"ALERT: [{severity.upper()}] {alert_type}: {message}")
            return result.data[0]
        return None

    except Exception as e:
        print(f"ERROR: Failed to send alert: {e}")
        return None


def send_youtube_auth_alert(error_message: str, context: Optional[Dict] = None) -> Optional[Dict]:
    """
    Send a YouTube authentication failure alert.

    Convenience wrapper for common YouTube auth failure alerts.
    Uses 60-minute cooldown to prevent spam during repeated failures.

    Args:
        error_message: Description of the auth failure
        context: Optional additional context (email, job_id, etc.)

    Returns:
        Alert data dict or None
    """
    full_context = {
        "error": error_message,
        "requires_manual_action": True,
        "action_steps": [
            "Run locally: python scripts/refresh_youtube_cookies.py --interactive",
            "Complete Google security challenges in browser",
            "Upload cookies.txt and cookies_state.json to server"
        ]
    }
    if context:
        full_context.update(context)

    return send_alert(
        alert_type="youtube_auth_failure",
        message=f"YouTube cookie refresh failed: {error_message[:200]}",
        severity="critical",
        context=full_context,
        cooldown_minutes=60  # Only one alert per hour for same issue
    )


def send_startup_alert(component: str, error_message: str, severity: str = "warning") -> Optional[Dict]:
    """
    Send a server/RunPod startup issue alert.

    Args:
        component: Component that failed (e.g., 'supabase', 'cookie_scheduler', 'whisperx')
        error_message: Description of the startup issue
        severity: 'info', 'warning', or 'critical'

    Returns:
        Alert data dict or None
    """
    return send_alert(
        alert_type="startup_failure",
        message=f"Startup issue in {component}: {error_message[:200]}",
        severity=severity,
        context={
            "component": component,
            "error": error_message
        },
        cooldown_minutes=30  # 30 min cooldown for startup issues
    )


# =============================================================================
# Screenshot Status Updates
# =============================================================================

def mark_transcription_screenshots_extracted(
    transcription_id: str,
    runpod_job_id: str,
    extracted_count: int
) -> bool:
    """
    Mark transcription as having screenshots extracted (ready for review).

    Calls the Supabase RPC function mark_transcription_screenshots_extracted
    which sets screenshots_status = 'extracted' in the transcription metadata.

    Args:
        transcription_id: UUID of the transcription
        runpod_job_id: RunPod job ID for tracking
        extracted_count: Number of screenshots extracted

    Returns:
        True if update succeeded, False otherwise
    """
    if supabase_client is None:
        print("WARNING: Cannot mark screenshots extracted - Supabase not configured")
        return False

    try:
        result = supabase_client.rpc(
            "mark_transcription_screenshots_extracted",
            {
                "p_transcription_id": transcription_id,
                "p_runpod_job_id": runpod_job_id,
                "p_extracted_count": extracted_count
            }
        ).execute()

        success = result.data is True
        if success:
            print(f"INFO: Marked transcription {transcription_id[:8]}... as screenshots_status='extracted' (count: {extracted_count})")
        else:
            print(f"WARNING: mark_transcription_screenshots_extracted returned {result.data} for {transcription_id}")
        return success
    except Exception as e:
        print(f"ERROR: Failed to mark screenshots extracted for {transcription_id}: {e}")
        return False


def acknowledge_alert(alert_id: str) -> bool:
    """
    Mark an alert as acknowledged.

    Args:
        alert_id: UUID of the alert to acknowledge

    Returns:
        True if acknowledged successfully, False otherwise
    """
    if supabase_client is None:
        return False

    try:
        result = supabase_client.table("system_alerts").update({
            "acknowledged_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", alert_id).execute()
        return bool(result.data)
    except Exception as e:
        print(f"ERROR: Failed to acknowledge alert: {e}")
        return False


def get_unacknowledged_alerts(
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50
) -> list:
    """
    Get unacknowledged alerts, optionally filtered by type and severity.

    Args:
        alert_type: Filter by alert type (optional)
        severity: Filter by severity (optional)
        limit: Maximum number of alerts to return (default: 50)

    Returns:
        List of alert dicts, newest first
    """
    if supabase_client is None:
        return []

    try:
        query = supabase_client.table("system_alerts").select("*").is_(
            "acknowledged_at", "null"
        )

        if alert_type:
            query = query.eq("alert_type", alert_type)
        if severity:
            query = query.eq("severity", severity)

        result = query.order("created_at", desc=True).limit(limit).execute()
        return result.data or []

    except Exception as e:
        print(f"ERROR: Failed to get alerts: {e}")
        return []
