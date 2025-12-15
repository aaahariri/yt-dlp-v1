"""
Pytest configuration and shared fixtures for test suite.

This module provides:
- Test client fixtures for FastAPI
- Mock API key fixtures
- Mock environment variables
- Shared test utilities
"""

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock


@pytest.fixture(scope="session")
def mock_env_vars():
    """Mock environment variables for testing."""
    with patch.dict(os.environ, {
        "API_KEY": "test-api-key",
        "ALLOWED_ORIGIN": "*",
        "DOWNLOADS_DIR": "./test_downloads",
        "CACHE_DIR": "./test_cache",
        "CACHE_TTL_HOURS": "3",
        "YTDLP_BINARY": "./bin/yt-dlp",
        "YTDLP_MIN_SLEEP": "1",
        "YTDLP_MAX_SLEEP": "3",
        "MAX_CONCURRENT_TRANSCRIPTIONS": "2",
    }):
        yield


@pytest.fixture
def api_key():
    """Return test API key."""
    return "test-api-key"


@pytest.fixture
def api_headers(api_key):
    """Return headers with API key."""
    return {"X-API-Key": api_key}


@pytest_asyncio.fixture
async def client(mock_env_vars):
    """
    Create async test client for FastAPI app.

    Uses httpx AsyncClient with ASGITransport to test the FastAPI app
    without needing to run a server.
    """
    # Import app after env vars are mocked
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_ytdlp_info():
    """Mock yt-dlp video info response."""
    return {
        "id": "test_video_id",
        "title": "Test Video Title",
        "duration": 120,
        "uploader": "Test Channel",
        "uploader_id": "test_channel_id",
        "uploader_url": "https://youtube.com/@testchannel",
        "upload_date": "20240101",
        "view_count": 1000,
        "description": "Test video description",
        "subtitles": {},
        "automatic_captions": {},
    }


@pytest.fixture
def mock_ytdlp_playlist_info():
    """Mock yt-dlp playlist info response."""
    return {
        "_type": "playlist",
        "title": "Test Playlist",
        "webpage_url": "https://youtube.com/playlist?list=test",
        "uploader": "Test Channel",
        "uploader_id": "test_channel_id",
        "uploader_url": "https://youtube.com/@testchannel",
        "playlist_count": 2,
        "entries": [
            {
                "id": "video1",
                "title": "Video 1",
                "url": "https://youtube.com/watch?v=video1",
                "duration": 100,
                "upload_date": "20240101",
            },
            {
                "id": "video2",
                "title": "Video 2",
                "url": "https://youtube.com/watch?v=video2",
                "duration": 200,
                "upload_date": "20240102",
            },
        ],
    }


@pytest.fixture
def youtube_url():
    """Sample YouTube URL for testing."""
    return "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def tiktok_url():
    """Sample TikTok URL for testing."""
    return "https://www.tiktok.com/@user/video/1234567890"


@pytest.fixture
def instagram_url():
    """Sample Instagram URL for testing."""
    return "https://www.instagram.com/p/ABC123/"


# Mark all tests as asyncio
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an async test"
    )
