"""
Routers package for API endpoints.

This package contains all API route handlers organized by functionality.
"""

from .download import router as download_router

__all__ = [
    "download_router",
]
