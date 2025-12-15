"""
Unit tests for utility modules.

This module tests:
- app/utils/filename_utils.py
- app/utils/timestamp_utils.py
- app/utils/platform_utils.py
"""

import pytest
from app.utils.filename_utils import (
    sanitize_filename,
    get_platform_prefix,
    format_title_for_filename,
    create_formatted_filename,
    encode_content_disposition_filename,
)
from app.utils.timestamp_utils import (
    parse_timestamp_to_seconds,
    format_seconds_to_srt,
    convert_srt_timestamp_to_seconds,
)
from app.utils.platform_utils import (
    is_youtube_url,
    get_video_id_from_url,
    get_platform_from_url,
    get_platform_prefix as platform_get_prefix,
)


class TestFilenameUtils:
    """Test filename utility functions."""

    def test_sanitize_filename_basic(self):
        """Test basic filename sanitization."""
        assert sanitize_filename("hello world") == "hello world"
        assert sanitize_filename("test/file") == "test-file"
        assert sanitize_filename("test\\file") == "test-file"

    def test_sanitize_filename_special_chars(self):
        """Test sanitization of special characters."""
        assert sanitize_filename("file:name") == "file-name"
        assert sanitize_filename("file*name") == "file-name"
        assert sanitize_filename("file?name") == "file-name"
        assert sanitize_filename('file"name') == "file-name"
        assert sanitize_filename("file<name>") == "file-name-"
        assert sanitize_filename("file|name") == "file-name"

    def test_sanitize_filename_unicode(self):
        """Test Unicode filename handling."""
        assert sanitize_filename("日本語") == "日本語"
        assert sanitize_filename("café") == "café"
        assert sanitize_filename("тест") == "тест"

    def test_sanitize_filename_length_limit(self):
        """Test filename length limiting."""
        long_name = "a" * 250
        result = sanitize_filename(long_name)
        assert len(result) == 200

    def test_sanitize_filename_empty_fallback(self):
        """Test empty filename fallback."""
        assert sanitize_filename("") == "video"
        assert sanitize_filename("   ") == "video"
        assert sanitize_filename("...") == "video"

    def test_get_platform_prefix_youtube(self):
        """Test YouTube platform detection."""
        assert get_platform_prefix("https://www.youtube.com/watch?v=123") == "YT"
        assert get_platform_prefix("https://youtu.be/123") == "YT"
        assert get_platform_prefix("https://www.YouTube.com/watch?v=123") == "YT"

    def test_get_platform_prefix_social_media(self):
        """Test social media platform detection."""
        assert get_platform_prefix("https://www.tiktok.com/@user/video/123") == "TT"
        assert get_platform_prefix("https://www.instagram.com/p/ABC/") == "IG"
        assert get_platform_prefix("https://www.facebook.com/video/123") == "FB"
        assert get_platform_prefix("https://fb.watch/abc") == "FB"
        assert get_platform_prefix("https://twitter.com/user/status/123") == "X"
        assert get_platform_prefix("https://x.com/user/status/123") == "X"

    def test_get_platform_prefix_video_platforms(self):
        """Test video platform detection."""
        assert get_platform_prefix("https://vimeo.com/123456") == "VM"
        assert get_platform_prefix("https://www.dailymotion.com/video/abc") == "DM"
        assert get_platform_prefix("https://www.twitch.tv/username") == "TW"

    def test_get_platform_prefix_unknown(self):
        """Test unknown platform fallback."""
        assert get_platform_prefix("https://unknown-site.com/video") == "VIDEO"

    def test_format_title_for_filename_basic(self):
        """Test basic title formatting."""
        assert format_title_for_filename("Hello World") == "Hello-World"
        assert format_title_for_filename("Test  Multiple   Spaces") == "Test-Multiple-Spaces"

    def test_format_title_for_filename_channel_removal(self):
        """Test channel name removal."""
        assert format_title_for_filename("Video Title | Channel Name") == "Video-Title"
        assert format_title_for_filename("Video - Channel") == "Video"

    def test_format_title_for_filename_episode_kept(self):
        """Test episode/part numbers are kept."""
        title = format_title_for_filename("Tutorial - Part 2")
        assert "Part" in title or "part" in title

    def test_format_title_for_filename_length_limit(self):
        """Test title length limiting."""
        long_title = "Very Long Title " * 10
        result = format_title_for_filename(long_title, max_length=50)
        assert len(result) <= 50

    def test_format_title_for_filename_special_chars(self):
        """Test special character handling in titles."""
        assert format_title_for_filename("Test/Title") == "Test-Title"
        assert format_title_for_filename("Test:Title") == "Test-Title"

    def test_create_formatted_filename(self):
        """Test complete filename creation."""
        url = "https://www.youtube.com/watch?v=123"
        title = "My Video Title"
        result = create_formatted_filename(url, title, "mp4")
        assert result.startswith("YT-")
        assert result.endswith(".mp4")
        assert "My-Video-Title" in result

    def test_create_formatted_filename_custom_title(self):
        """Test filename creation with custom title."""
        url = "https://www.youtube.com/watch?v=123"
        title = "Original Title"
        custom = "Custom Title"
        result = create_formatted_filename(url, title, "mp4", custom)
        assert "Custom-Title" in result
        assert "Original" not in result

    def test_encode_content_disposition_ascii(self):
        """Test Content-Disposition encoding for ASCII filenames."""
        result = encode_content_disposition_filename("test-video.mp4")
        assert 'attachment; filename="test-video.mp4"' == result

    def test_encode_content_disposition_unicode(self):
        """Test Content-Disposition encoding for Unicode filenames."""
        result = encode_content_disposition_filename("日本語ビデオ.mp4")
        assert "attachment; filename=" in result
        assert "filename*=UTF-8''" in result

    def test_encode_content_disposition_quotes(self):
        """Test handling of quotes in filenames."""
        result = encode_content_disposition_filename('test"video.mp4')
        assert '\\"' in result or "filename*=" in result


class TestTimestampUtils:
    """Test timestamp utility functions."""

    def test_parse_timestamp_srt_format(self):
        """Test parsing SRT timestamp format."""
        assert parse_timestamp_to_seconds("00:01:30,500") == 90.5
        assert parse_timestamp_to_seconds("00:00:10,000") == 10.0
        assert parse_timestamp_to_seconds("01:00:00,000") == 3600.0

    def test_parse_timestamp_vtt_format(self):
        """Test parsing VTT timestamp format (dot instead of comma)."""
        assert parse_timestamp_to_seconds("00:01:30.500") == 90.5
        assert parse_timestamp_to_seconds("00:00:10.000") == 10.0

    def test_parse_timestamp_float_seconds(self):
        """Test parsing float seconds."""
        assert parse_timestamp_to_seconds("90.5") == 90.5
        assert parse_timestamp_to_seconds("10") == 10.0
        assert parse_timestamp_to_seconds("3600.0") == 3600.0

    def test_format_seconds_to_srt(self):
        """Test formatting seconds to SRT timestamp."""
        assert format_seconds_to_srt(90.5) == "00:01:30,500"
        assert format_seconds_to_srt(10.0) == "00:00:10,000"
        assert format_seconds_to_srt(3600.0) == "01:00:00,000"
        assert format_seconds_to_srt(0.0) == "00:00:00,000"

    def test_format_seconds_to_srt_fractional(self):
        """Test formatting fractional seconds."""
        assert format_seconds_to_srt(1.234) == "00:00:01,234"
        assert format_seconds_to_srt(60.999) == "00:01:00,999"

    def test_convert_srt_timestamp_to_seconds(self):
        """Test SRT timestamp conversion."""
        assert convert_srt_timestamp_to_seconds("00:00:00,240") == 0.24
        assert convert_srt_timestamp_to_seconds("00:01:23,456") == 83.456
        assert convert_srt_timestamp_to_seconds("01:30:45,123") == 5445.123

    def test_convert_srt_timestamp_vtt_format(self):
        """Test VTT timestamp conversion (dot separator)."""
        assert convert_srt_timestamp_to_seconds("00:00:00.240") == 0.24
        assert convert_srt_timestamp_to_seconds("00:01:23.456") == 83.456

    def test_timestamp_roundtrip(self):
        """Test roundtrip conversion (seconds -> SRT -> seconds)."""
        original = 123.456
        srt = format_seconds_to_srt(original)
        converted = convert_srt_timestamp_to_seconds(srt)
        assert abs(converted - original) < 0.001  # Allow small floating point error


class TestPlatformUtils:
    """Test platform utility functions."""

    def test_is_youtube_url_standard(self):
        """Test YouTube URL detection - standard format."""
        assert is_youtube_url("https://www.youtube.com/watch?v=123") is True
        assert is_youtube_url("https://youtube.com/watch?v=123") is True
        assert is_youtube_url("http://www.youtube.com/watch?v=123") is True

    def test_is_youtube_url_short(self):
        """Test YouTube URL detection - short format."""
        assert is_youtube_url("https://youtu.be/123") is True
        assert is_youtube_url("http://youtu.be/123") is True

    def test_is_youtube_url_nocookie(self):
        """Test YouTube URL detection - nocookie domain."""
        assert is_youtube_url("https://www.youtube-nocookie.com/embed/123") is True

    def test_is_youtube_url_case_insensitive(self):
        """Test YouTube URL detection is case insensitive."""
        assert is_youtube_url("https://WWW.YOUTUBE.COM/watch?v=123") is True
        assert is_youtube_url("https://YOUTU.BE/123") is True

    def test_is_youtube_url_negative(self):
        """Test non-YouTube URLs."""
        assert is_youtube_url("https://vimeo.com/123") is False
        assert is_youtube_url("https://tiktok.com/@user/video/123") is False
        assert is_youtube_url("https://facebook.com/video") is False

    def test_get_video_id_from_url(self):
        """Test video ID extraction from URL."""
        url1 = "https://www.youtube.com/watch?v=123"
        url2 = "https://www.youtube.com/watch?v=456"
        id1 = get_video_id_from_url(url1)
        id2 = get_video_id_from_url(url2)

        # IDs should be consistent for same URL
        assert id1 == get_video_id_from_url(url1)
        # IDs should be different for different URLs
        assert id1 != id2
        # ID should be 12 characters
        assert len(id1) == 12

    def test_get_platform_from_url_youtube(self):
        """Test platform detection for YouTube."""
        assert get_platform_from_url("https://www.youtube.com/watch?v=123") == "youtube"
        assert get_platform_from_url("https://youtu.be/123") == "youtube"

    def test_get_platform_from_url_social_media(self):
        """Test platform detection for social media."""
        assert get_platform_from_url("https://www.tiktok.com/@user/video/123") == "tiktok"
        assert get_platform_from_url("https://www.instagram.com/p/ABC/") == "instagram"
        assert get_platform_from_url("https://www.facebook.com/video/123") == "facebook"
        assert get_platform_from_url("https://fb.watch/abc") == "facebook"
        assert get_platform_from_url("https://twitter.com/user/status/123") == "twitter"
        assert get_platform_from_url("https://x.com/user/status/123") == "twitter"

    def test_get_platform_from_url_video_platforms(self):
        """Test platform detection for video platforms."""
        assert get_platform_from_url("https://vimeo.com/123456") == "vimeo"
        assert get_platform_from_url("https://www.dailymotion.com/video/abc") == "dailymotion"
        assert get_platform_from_url("https://www.twitch.tv/username") == "twitch"

    def test_get_platform_from_url_unknown(self):
        """Test unknown platform detection."""
        assert get_platform_from_url("https://unknown-site.com/video") == "unknown"

    def test_get_platform_prefix_matches_get_platform_from_url(self):
        """Test that platform prefix matches platform detection."""
        test_urls = [
            ("https://www.youtube.com/watch?v=123", "YT", "youtube"),
            ("https://www.tiktok.com/@user/video/123", "TT", "tiktok"),
            ("https://www.instagram.com/p/ABC/", "IG", "instagram"),
            ("https://www.facebook.com/video/123", "FB", "facebook"),
            ("https://twitter.com/user/status/123", "X", "twitter"),
            ("https://vimeo.com/123456", "VM", "vimeo"),
            ("https://www.dailymotion.com/video/abc", "DM", "dailymotion"),
            ("https://www.twitch.tv/username", "TW", "twitch"),
        ]

        for url, expected_prefix, expected_platform in test_urls:
            assert platform_get_prefix(url) == expected_prefix
            assert get_platform_from_url(url) == expected_platform


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
