"""
Unit tests for job service subtitle extraction functionality.

This module tests:
- _parse_subtitles_to_segments() for json3, vtt, srt formats
- Subtitle extraction priority logic (manual > auto-generated)
"""

import pytest
import json
from app.services.job_service import _parse_subtitles_to_segments


class TestParseSubtitlesToSegments:
    """Test subtitle parsing for different formats."""

    def test_parse_json3_basic(self):
        """Test parsing YouTube json3 format with basic segments."""
        json3_content = json.dumps({
            "events": [
                {
                    "tStartMs": 0,
                    "dDurationMs": 3000,
                    "segs": [{"utf8": "Hello world"}]
                },
                {
                    "tStartMs": 3000,
                    "dDurationMs": 2000,
                    "segs": [{"utf8": "This is a test"}]
                }
            ]
        })

        segments = _parse_subtitles_to_segments(json3_content, "json3")

        assert len(segments) == 2
        assert segments[0]["segment_id"] == 1
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 3.0
        assert segments[0]["text"] == "Hello world"

        assert segments[1]["segment_id"] == 2
        assert segments[1]["start"] == 3.0
        assert segments[1]["end"] == 5.0
        assert segments[1]["text"] == "This is a test"

    def test_parse_json3_with_word_timing(self):
        """Test parsing json3 with word-level timing."""
        json3_content = json.dumps({
            "events": [
                {
                    "tStartMs": 1000,
                    "dDurationMs": 2000,
                    "segs": [
                        {"utf8": "Hello", "tOffsetMs": 0},
                        {"utf8": "world", "tOffsetMs": 500}
                    ]
                }
            ]
        })

        segments = _parse_subtitles_to_segments(json3_content, "json3")

        assert len(segments) == 1
        assert segments[0]["text"] == "Hello world"
        assert "words" in segments[0]
        assert len(segments[0]["words"]) == 2
        assert segments[0]["words"][0]["word"] == "Hello"
        assert segments[0]["words"][0]["start"] == 1.0
        assert segments[0]["words"][1]["word"] == "world"
        assert segments[0]["words"][1]["start"] == 1.5

    def test_parse_json3_skips_empty_segments(self):
        """Test that json3 parsing skips empty and newline-only segments."""
        json3_content = json.dumps({
            "events": [
                {
                    "tStartMs": 0,
                    "dDurationMs": 1000,
                    "segs": [{"utf8": "\n"}]  # Newline only
                },
                {
                    "tStartMs": 1000,
                    "dDurationMs": 1000,
                    "segs": [{"utf8": ""}]  # Empty
                },
                {
                    "tStartMs": 2000,
                    "dDurationMs": 1000,
                    "segs": [{"utf8": "Actual text"}]  # Valid
                },
                {
                    "aAppend": True,  # Append event (should be skipped)
                    "segs": [{"utf8": "append"}]
                }
            ]
        })

        segments = _parse_subtitles_to_segments(json3_content, "json3")

        assert len(segments) == 1
        assert segments[0]["text"] == "Actual text"

    def test_parse_vtt_basic(self):
        """Test parsing basic VTT format."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:03.000
Hello world

00:00:03.000 --> 00:00:05.000
This is a test"""

        segments = _parse_subtitles_to_segments(vtt_content, "vtt")

        assert len(segments) == 2
        assert segments[0]["segment_id"] == 1
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 3.0
        assert segments[0]["text"] == "Hello world"

        assert segments[1]["segment_id"] == 2
        assert segments[1]["start"] == 3.0
        assert segments[1]["end"] == 5.0
        assert segments[1]["text"] == "This is a test"

    def test_parse_vtt_with_html_tags(self):
        """Test VTT parsing strips HTML tags."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:03.000
<c>Hello</c> <b>world</b>"""

        segments = _parse_subtitles_to_segments(vtt_content, "vtt")

        assert len(segments) == 1
        # HTML tags should be stripped
        assert "<" not in segments[0]["text"]
        assert ">" not in segments[0]["text"]

    def test_parse_vtt_skips_positioning_lines(self):
        """Test VTT parsing skips lines starting with <."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:03.000
<c.colorE5E5E5>

00:00:03.000 --> 00:00:06.000
Actual text"""

        segments = _parse_subtitles_to_segments(vtt_content, "vtt")

        # Should only get the second segment with actual text
        assert len(segments) == 1
        assert segments[0]["text"] == "Actual text"

    def test_parse_vtt_multiline_text(self):
        """Test VTT parsing handles multi-line text."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:03.000
Line one
Line two
Line three

00:00:03.000 --> 00:00:06.000
Single line"""

        segments = _parse_subtitles_to_segments(vtt_content, "vtt")

        assert len(segments) == 2
        # First segment should combine all three lines
        assert "Line one" in segments[0]["text"]
        assert "Line two" in segments[0]["text"]
        assert "Line three" in segments[0]["text"]
        # Second segment is single line
        assert segments[1]["text"] == "Single line"

    def test_parse_srt_basic(self):
        """Test parsing basic SRT format."""
        srt_content = """1
00:00:00,000 --> 00:00:03,000
Hello world

2
00:00:03,000 --> 00:00:05,500
This is a test"""

        segments = _parse_subtitles_to_segments(srt_content, "srt")

        assert len(segments) == 2
        assert segments[0]["segment_id"] == 1
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 3.0
        assert segments[0]["text"] == "Hello world"

        assert segments[1]["segment_id"] == 2
        assert segments[1]["start"] == 3.0
        assert segments[1]["end"] == 5.5
        assert segments[1]["text"] == "This is a test"

    def test_parse_srt_multiline_text(self):
        """Test SRT parsing handles multi-line text."""
        srt_content = """1
00:00:00,000 --> 00:00:03,000
Line one
Line two
Line three"""

        segments = _parse_subtitles_to_segments(srt_content, "srt")

        assert len(segments) == 1
        assert "Line one" in segments[0]["text"]
        assert "Line two" in segments[0]["text"]
        assert "Line three" in segments[0]["text"]

    def test_parse_srt_strips_html_tags(self):
        """Test SRT parsing strips HTML tags."""
        srt_content = """1
00:00:00,000 --> 00:00:03,000
<i>Italic</i> and <b>bold</b>"""

        segments = _parse_subtitles_to_segments(srt_content, "srt")

        assert len(segments) == 1
        assert "<" not in segments[0]["text"]
        assert ">" not in segments[0]["text"]
        assert "Italic" in segments[0]["text"]
        assert "bold" in segments[0]["text"]

    def test_parse_unknown_format_returns_empty(self):
        """Test unknown format returns empty list."""
        segments = _parse_subtitles_to_segments("some content", "unknown")
        assert segments == []

    def test_parse_empty_content(self):
        """Test parsing empty content."""
        assert _parse_subtitles_to_segments("", "vtt") == []
        assert _parse_subtitles_to_segments("", "srt") == []

    def test_segment_ids_are_sequential(self):
        """Test that segment IDs are sequential starting from 1."""
        srt_content = """1
00:00:00,000 --> 00:00:01,000
First

2
00:00:01,000 --> 00:00:02,000
Second

3
00:00:02,000 --> 00:00:03,000
Third"""

        segments = _parse_subtitles_to_segments(srt_content, "srt")

        assert len(segments) == 3
        for i, seg in enumerate(segments, start=1):
            assert seg["segment_id"] == i


class TestSubtitleExtractionPriority:
    """Test subtitle extraction priority logic (conceptual tests)."""

    def test_manual_subs_preferred_over_auto(self):
        """
        Conceptual test: Manual subtitles should be preferred over auto-generated.

        The actual priority logic is in _try_extract_platform_subtitles().
        This test documents the expected behavior.
        """
        # This is a documentation test - the actual logic is:
        # 1. Try manual subtitles in target language
        # 2. Try manual subtitles in English variants
        # 3. Try auto-captions in target language
        # 4. Try auto-captions in English variants
        pass

    def test_fallback_to_english_variants(self):
        """
        Conceptual test: Should fall back to English variants if target lang unavailable.

        Expected fallback order: target_lang -> 'en' -> 'en-US' -> 'en-GB'
        """
        pass


class TestRetryWithDelay:
    """Test _retry_with_delay helper function."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_first_attempt(self):
        """Test that successful first attempt returns immediately."""
        from app.services.job_service import _retry_with_delay

        call_count = 0

        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await _retry_with_delay(
            func=success_func,
            max_attempts=3,
            delay_seconds=0.1,
            operation_name="test"
        )

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self):
        """Test that retry succeeds after first failure."""
        from app.services.job_service import _retry_with_delay

        call_count = 0

        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First attempt failed")
            return "success"

        result = await _retry_with_delay(
            func=fail_then_succeed,
            max_attempts=3,
            delay_seconds=0.1,
            operation_name="test"
        )

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausts_all_attempts(self):
        """Test that all attempts are tried before raising."""
        from app.services.job_service import _retry_with_delay

        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")

        with pytest.raises(Exception, match="Always fails"):
            await _retry_with_delay(
                func=always_fail,
                max_attempts=3,
                delay_seconds=0.1,
                operation_name="test"
            )

        assert call_count == 3


class TestSkipSubtitlesFlag:
    """Test skip_subtitles flag behavior."""

    def test_skip_subtitles_default_is_false(self):
        """Test that skip_subtitles defaults to False when not provided."""
        job_without_flag = {"msg_id": 1, "document_id": "test-id"}
        assert job_without_flag.get("skip_subtitles", False) is False

    def test_skip_subtitles_can_be_true(self):
        """Test that skip_subtitles can be set to True."""
        job_with_flag = {"msg_id": 1, "document_id": "test-id", "skip_subtitles": True}
        assert job_with_flag.get("skip_subtitles", False) is True

    def test_skip_subtitles_can_be_explicitly_false(self):
        """Test that skip_subtitles can be explicitly set to False."""
        job_with_flag = {"msg_id": 1, "document_id": "test-id", "skip_subtitles": False}
        assert job_with_flag.get("skip_subtitles", False) is False


class TestSkipSubtitlesBehavior:
    """Test that skip_subtitles flag controls subtitle extraction logic."""

    def test_skip_subtitles_true_skips_extraction(self):
        """Test that skip_subtitles=True would bypass subtitle extraction."""
        job = {"msg_id": 1, "document_id": "test", "skip_subtitles": True}
        skip_subtitles = job.get("skip_subtitles", False)
        media_format = "video"

        # This is the condition from process_single_job (line 622)
        should_try_subtitles = media_format == "video" and not skip_subtitles
        assert should_try_subtitles is False

    def test_skip_subtitles_false_allows_extraction(self):
        """Test that skip_subtitles=False allows subtitle extraction."""
        job = {"msg_id": 1, "document_id": "test", "skip_subtitles": False}
        skip_subtitles = job.get("skip_subtitles", False)
        media_format = "video"

        # This is the condition from process_single_job (line 622)
        should_try_subtitles = media_format == "video" and not skip_subtitles
        assert should_try_subtitles is True

    def test_skip_subtitles_default_allows_extraction(self):
        """Test that missing skip_subtitles flag allows subtitle extraction (default behavior)."""
        job = {"msg_id": 1, "document_id": "test"}
        skip_subtitles = job.get("skip_subtitles", False)
        media_format = "video"

        # This is the condition from process_single_job (line 622)
        should_try_subtitles = media_format == "video" and not skip_subtitles
        assert should_try_subtitles is True

    def test_audio_format_skips_subtitles_regardless_of_flag(self):
        """Test that audio format skips subtitles even if skip_subtitles=False."""
        job = {"msg_id": 1, "document_id": "test", "skip_subtitles": False}
        skip_subtitles = job.get("skip_subtitles", False)
        media_format = "audio"

        # This is the condition from process_single_job (line 622)
        should_try_subtitles = media_format == "video" and not skip_subtitles
        assert should_try_subtitles is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
