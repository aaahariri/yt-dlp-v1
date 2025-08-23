# Unicode Handling Utilities

## Overview

This document describes the Unicode handling utilities implemented to properly support international characters, emojis, and special symbols in video titles when downloading through the API.

## Problem Statement

The original implementation had issues with:
- Unicode characters being stripped from filenames
- Incorrect Content-Disposition headers for non-ASCII filenames
- Loss of international characters (Chinese, Japanese, Arabic, etc.) in saved files

## Implemented Solutions

### Functions

#### `sanitize_filename(filename: str) -> str`

**Location:** `main.py:244-260`

**Purpose:** Sanitizes filenames for filesystem safety while preserving Unicode characters.

**Features:**
- Normalizes Unicode characters using NFC (Canonical Composition)
- Removes only filesystem-unsafe characters (/, \, :, *, ?, ", <, >, |)
- Preserves international characters, emojis, and special symbols
- Trims leading/trailing spaces and dots
- Limits filename length to 200 characters to prevent filesystem issues

**Usage Example:**
```python
title = "🎥 Video/Title: Special*Characters | مع عربي"
safe_title = sanitize_filename(title)
# Result: "🎥 Video-Title- Special-Characters - مع عربي"
```

#### `encode_content_disposition_filename(filename: str) -> str`

**Location:** `main.py:262-277`

**Purpose:** Encodes filenames for HTTP Content-Disposition headers following RFC 5987.

**Features:**
- Handles ASCII filenames with simple format
- Applies RFC 5987 encoding for Unicode filenames
- Provides ASCII fallback for compatibility with older clients
- Properly escapes special characters

**Usage Example:**
```python
filename = "فيديو عربي.mp4"
header = encode_content_disposition_filename(filename)
# Result: 'attachment; filename=".mp4"; filename*=UTF-8''%D9%81%D9%8A%D8%AF%D9%8A%D9%88%20%D8%B9%D8%B1%D8%A8%D9%8A.mp4'
```

## Integration Points

### `/download` Endpoint

The Unicode handling utilities are integrated at multiple points in the download flow:

1. **Metadata extraction** (main.py:283-288):
   - Video title is sanitized using `sanitize_filename()`
   - Preserves original Unicode characters

2. **File saving** (main.py:291-295):
   - When `keep=True`, files are saved with Unicode-preserved names
   - Timestamp is appended for uniqueness

3. **HTTP response** (main.py:337):
   - Content-Disposition header uses `encode_content_disposition_filename()`
   - Ensures proper download naming in browsers

## Supported Character Sets

The implementation has been tested with:
- **Arabic:** العربية
- **Chinese:** 中文
- **Japanese:** 日本語
- **Korean:** 한국어
- **Russian:** Русский
- **Hebrew:** עברית
- **Emojis:** 🎥🎬📱💡🚀
- **Accented Latin:** àéîõü

## RFC 5987 Compliance

The Content-Disposition header encoding follows RFC 5987 specifications:

- **ASCII filenames:** Use simple quoted format
  ```
  Content-Disposition: attachment; filename="video.mp4"
  ```

- **Unicode filenames:** Use extended format with UTF-8 encoding
  ```
  Content-Disposition: attachment; filename="fallback.mp4"; filename*=UTF-8''encoded%20name.mp4
  ```

## Testing

The implementation has been verified with:
- TikTok videos with Arabic titles and emojis
- YouTube videos with various international titles
- Edge cases including special characters and long filenames

## Benefits

1. **International Support:** Full support for global content creators
2. **User Experience:** Downloaded files retain meaningful names in user's language
3. **Compatibility:** Works with modern browsers while providing ASCII fallback
4. **Safety:** Prevents filesystem errors while maximizing character preservation

## Dependencies

The implementation uses Python standard library modules:
- `unicodedata`: For Unicode normalization
- `urllib.parse.quote`: For URL encoding in RFC 5987 format

No external dependencies are required beyond what's already in the project.