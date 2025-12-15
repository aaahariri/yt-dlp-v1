"""
FastAPI dependency injection functions.

This module provides reusable dependencies for:
- API key authentication and verification
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
