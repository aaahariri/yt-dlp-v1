"""
FastAPI dependency injection functions.

This module provides reusable dependencies for:
- API key authentication and verification
- Job worker token verification (for Supabase Edge Function calls)
"""

from fastapi import Header, HTTPException
from app.config import get_settings


def verify_api_key(x_api_key: str = Header(None)) -> bool:
    """
    Dependency to verify API key from request header.
    Raises HTTPException 401 if invalid, 500 if not configured.
    """
    settings = get_settings()
    if not settings.api_key:
        raise HTTPException(status_code=500, detail="API key not configured")
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True


def verify_job_token(authorization: str = Header(None)) -> bool:
    """
    Dependency to verify job worker token from Authorization header.

    Expected format: "Bearer <token>"

    This is used by the Supabase Edge Function to authenticate
    when pushing transcription jobs to our endpoint.

    Raises:
        HTTPException 401 if token is invalid
        HTTPException 500 if PY_API_TOKEN not configured
    """
    settings = get_settings()
    if not settings.py_api_token:
        raise HTTPException(status_code=500, detail="PY_API_TOKEN not configured")

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Parse "Bearer <token>" format
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected: Bearer <token>")

    token = parts[1]
    if token != settings.py_api_token:
        raise HTTPException(status_code=401, detail="Invalid job worker token")

    return True
