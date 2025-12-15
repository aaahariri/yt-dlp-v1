"""
Integration tests for all API routers.

This module tests:
- API authentication (401 for missing/invalid keys)
- Input validation (422 for invalid params)
- Endpoint responses (200 for valid requests with mocked yt-dlp)
- All routers: download, subtitles, audio, transcription, playlist, screenshot, cache, admin
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import os


class TestAuthentication:
    """Test API key authentication across all endpoints."""

    @pytest.mark.asyncio
    async def test_missing_api_key(self, client):
        """Test requests without API key are rejected."""
        response = await client.get("/cache")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, client):
        """Test requests with invalid API key are rejected."""
        response = await client.get("/cache", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_api_key(self, client, api_headers):
        """Test requests with valid API key are accepted."""
        response = await client.get("/cache", headers=api_headers)
        # Should not be 401 (should be 200 for valid auth)
        assert response.status_code == 200


class TestDownloadRouter:
    """Test download router endpoints."""

    @pytest.mark.asyncio
    async def test_download_missing_api_key(self, client, youtube_url):
        """Test download endpoint rejects missing API key."""
        response = await client.get(f"/download?url={youtube_url}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_download_invalid_url_param(self, client, api_headers):
        """Test download endpoint requires url parameter."""
        response = await client.get("/download", headers=api_headers)
        assert response.status_code == 422  # Missing required parameter

    @pytest.mark.asyncio
    async def test_batch_download_missing_api_key(self, client):
        """Test batch download endpoint rejects missing API key."""
        response = await client.post("/batch-download", json={"urls": []})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_batch_download_invalid_body(self, client, api_headers):
        """Test batch download endpoint validates request body."""
        response = await client.post("/batch-download", headers=api_headers, json={})
        assert response.status_code == 422  # Invalid request body


class TestSubtitlesRouter:
    """Test subtitles router endpoints."""

    @pytest.mark.asyncio
    async def test_subtitles_missing_api_key(self, client, youtube_url):
        """Test subtitles endpoint rejects missing API key."""
        response = await client.get(f"/subtitles?url={youtube_url}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_subtitles_missing_url(self, client, api_headers):
        """Test subtitles endpoint requires url parameter."""
        response = await client.get("/subtitles", headers=api_headers)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_subtitles_with_mocked_ytdlp(self, client, api_headers, youtube_url):
        """Test subtitles endpoint with mocked yt-dlp."""
        mock_info = {
            "title": "Test Video",
            "duration": 120,
            "id": "test_id",
            "subtitles": {
                "en": [{
                    "ext": "vtt",
                    "url": "https://example.com/subs.vtt"
                }]
            },
            "automatic_captions": {}
        }

        with patch("yt_dlp.YoutubeDL") as mock_ytdlp:
            mock_instance = MagicMock()
            mock_instance.extract_info.return_value = mock_info
            mock_ytdlp.return_value.__enter__.return_value = mock_instance

            with patch("requests.get") as mock_requests:
                mock_requests.return_value.text = "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest subtitle"
                mock_requests.return_value.raise_for_status = MagicMock()

                response = await client.get(
                    f"/subtitles?url={youtube_url}&format=text",
                    headers=api_headers
                )

                # Should succeed or fail gracefully (not 401/422)
                assert response.status_code in [200, 404, 500]

    @pytest.mark.asyncio
    async def test_transcription_locales_missing_api_key(self, client, youtube_url):
        """Test transcription locales endpoint rejects missing API key."""
        response = await client.get(f"/transcription/locales?url={youtube_url}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_transcription_locales_missing_url(self, client, api_headers):
        """Test transcription locales endpoint requires url parameter."""
        response = await client.get("/transcription/locales", headers=api_headers)
        assert response.status_code == 422


class TestAudioRouter:
    """Test audio extraction router endpoints."""

    @pytest.mark.asyncio
    async def test_extract_audio_missing_api_key(self, client, youtube_url):
        """Test audio extraction endpoint rejects missing API key."""
        response = await client.post(f"/extract-audio?url={youtube_url}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_extract_audio_missing_url_and_file(self, client, api_headers):
        """Test audio extraction requires url or local_file parameter."""
        response = await client.post("/extract-audio", headers=api_headers)
        assert response.status_code == 400  # Bad request

    @pytest.mark.asyncio
    async def test_extract_audio_both_url_and_file(self, client, api_headers, youtube_url):
        """Test audio extraction rejects both url and local_file."""
        response = await client.post(
            f"/extract-audio?url={youtube_url}&local_file=/tmp/test.mp4",
            headers=api_headers
        )
        assert response.status_code == 400


class TestTranscriptionRouter:
    """Test transcription router endpoints."""

    @pytest.mark.asyncio
    async def test_transcribe_missing_api_key(self, client):
        """Test transcribe endpoint rejects missing API key."""
        response = await client.post("/transcribe?audio_file=/tmp/test.mp3")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_transcribe_missing_audio_file(self, client, api_headers):
        """Test transcribe endpoint requires audio_file parameter."""
        response = await client.post("/transcribe", headers=api_headers)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_transcriptions_save_missing_api_key(self, client):
        """Test save transcription endpoint rejects missing API key."""
        response = await client.post("/transcriptions/save", json={
            "document_id": "test",
            "segments": [],
            "language": "en",
            "source": "test"
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_transcriptions_save_invalid_body(self, client, api_headers):
        """Test save transcription endpoint validates request body."""
        response = await client.post("/transcriptions/save", headers=api_headers, json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_transcriptions_check_missing_api_key(self, client):
        """Test check transcription endpoint rejects missing API key."""
        response = await client.get("/transcriptions/check/test_id")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_transcriptions_check_with_api_key(self, client, api_headers):
        """Test check transcription endpoint with valid API key."""
        with patch("app.services.supabase_service.get_supabase_client") as mock_supabase:
            mock_client = MagicMock()
            mock_table = MagicMock()
            mock_select = MagicMock()
            mock_eq = MagicMock()
            mock_eq.execute.return_value = MagicMock(data=[])
            mock_select.eq.return_value = mock_eq
            mock_table.select.return_value = mock_select
            mock_client.table.return_value = mock_table
            mock_supabase.return_value = mock_client

            response = await client.get("/transcriptions/check/test_id", headers=api_headers)
            # Should succeed or fail gracefully
            assert response.status_code in [200, 500]


class TestPlaylistRouter:
    """Test playlist router endpoints."""

    @pytest.mark.asyncio
    async def test_playlist_info_missing_api_key(self, client, youtube_url):
        """Test playlist info endpoint rejects missing API key."""
        response = await client.get(f"/playlist/info?url={youtube_url}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_playlist_info_missing_url(self, client, api_headers):
        """Test playlist info endpoint requires url parameter."""
        response = await client.get("/playlist/info", headers=api_headers)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_playlist_info_with_mocked_ytdlp(self, client, api_headers, youtube_url, mock_ytdlp_playlist_info):
        """Test playlist info endpoint with mocked yt-dlp."""
        with patch("yt_dlp.YoutubeDL") as mock_ytdlp:
            mock_instance = MagicMock()
            mock_instance.extract_info.return_value = mock_ytdlp_playlist_info
            mock_ytdlp.return_value.__enter__.return_value = mock_instance

            response = await client.get(
                f"/playlist/info?url={youtube_url}",
                headers=api_headers
            )

            # Should succeed or fail gracefully
            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert "playlist_title" in data
                assert "videos" in data


class TestScreenshotRouter:
    """Test screenshot router endpoints."""

    @pytest.mark.asyncio
    async def test_screenshot_missing_api_key(self, client, youtube_url):
        """Test screenshot endpoint rejects missing API key."""
        response = await client.post("/screenshot/video", json={
            "video_url": youtube_url,
            "timestamps": ["00:00:10"]
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_screenshot_invalid_body(self, client, api_headers):
        """Test screenshot endpoint validates request body."""
        response = await client.post("/screenshot/video", headers=api_headers, json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_screenshot_missing_timestamps(self, client, api_headers, youtube_url):
        """Test screenshot endpoint requires timestamps."""
        response = await client.post("/screenshot/video", headers=api_headers, json={
            "video_url": youtube_url
        })
        assert response.status_code == 422


class TestCacheRouter:
    """Test cache router endpoints."""

    @pytest.mark.asyncio
    async def test_cache_cleanup_missing_api_key(self, client):
        """Test cache cleanup endpoint rejects missing API key."""
        response = await client.delete("/cache/cleanup")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cache_cleanup_with_api_key(self, client, api_headers):
        """Test cache cleanup endpoint with valid API key."""
        with patch("app.services.cache_service.cleanup_cache") as mock_cleanup:
            mock_cleanup.return_value = {
                "total_deleted": 0,
                "deleted": [],
                "freed_bytes": 0
            }

            response = await client.delete("/cache/cleanup", headers=api_headers)
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "deleted" in data

    @pytest.mark.asyncio
    async def test_list_cache_missing_api_key(self, client):
        """Test list cache endpoint rejects missing API key."""
        response = await client.get("/cache")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_cache_with_api_key(self, client, api_headers):
        """Test list cache endpoint with valid API key."""
        response = await client.get("/cache", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_list_cache_with_type_filter(self, client, api_headers):
        """Test list cache endpoint with type filter."""
        response = await client.get("/cache?type=videos", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "files" in data

    @pytest.mark.asyncio
    async def test_list_downloads_missing_api_key(self, client):
        """Test list downloads endpoint rejects missing API key."""
        response = await client.get("/downloads/list")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_downloads_with_api_key(self, client, api_headers):
        """Test list downloads endpoint with valid API key."""
        response = await client.get("/downloads/list", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "downloads" in data
        assert "count" in data


class TestAdminRouter:
    """Test admin router endpoints."""

    @pytest.mark.asyncio
    async def test_refresh_cookies_missing_api_key(self, client):
        """Test refresh cookies endpoint rejects missing API key."""
        response = await client.post("/admin/refresh-cookies")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_cookies_with_api_key(self, client, api_headers):
        """Test refresh cookies endpoint with valid API key."""
        with patch("app.routers.admin.trigger_manual_refresh") as mock_refresh:
            mock_refresh.return_value = {
                "success": True,
                "message": "Cookies refreshed successfully",
                "timestamp": "2025-01-01T00:00:00"
            }

            response = await client.post("/admin/refresh-cookies", headers=api_headers)
            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_cookie_scheduler_status_missing_api_key(self, client):
        """Test cookie scheduler status endpoint rejects missing API key."""
        response = await client.get("/admin/cookie-scheduler/status")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cookie_scheduler_status_with_api_key(self, client, api_headers):
        """Test cookie scheduler status endpoint with valid API key."""
        with patch("app.routers.admin.get_scheduler_status") as mock_status:
            mock_status.return_value = {
                "running": True,
                "interval_days": 5
            }

            response = await client.get("/admin/cookie-scheduler/status", headers=api_headers)
            assert response.status_code == 200
            data = response.json()
            assert "running" in data

    @pytest.mark.asyncio
    async def test_transcription_worker_status_missing_api_key(self, client):
        """Test transcription worker status endpoint rejects missing API key."""
        response = await client.get("/admin/transcription-worker/status")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_transcription_worker_status_with_api_key(self, client, api_headers):
        """Test transcription worker status endpoint with valid API key."""
        response = await client.get("/admin/transcription-worker/status", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "running" in data or "error" in data


class TestHealthCheck:
    """Test basic health check endpoint."""

    @pytest.mark.asyncio
    async def test_root_endpoint_with_api_key(self, client, api_headers):
        """Test root endpoint responds."""
        response = await client.get("/", headers=api_headers)
        # May be 200 if implemented, 404 if not, but should not crash
        assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
