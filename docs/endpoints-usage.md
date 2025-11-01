# API Endpoints Usage Guide

This document provides detailed information about all available API endpoints, their parameters, and response formats.

## Authentication

All protected endpoints require the `X-Api-Key` header:

```bash
X-Api-Key: your-api-key-here
```

---

## 1. Health Check Endpoint

### `GET /`

**Description**: Returns a welcome message to verify the API is running.

**Authentication**: Not required

**Parameters**: None

**Example Request**:
```bash
curl "http://localhost:8000/"
```

**Example Response**:
```json
{
  "message": "Welcome to the Social Media Video Downloader API. Use /download?url=<video_url>&format=<video_format> to download videos."
}
```

---

## 2. Video Download Endpoint

### `GET /download`

**Description**: Downloads videos from supported platforms (YouTube, TikTok, Instagram, Facebook, Twitter, etc.) and streams them to the client. Optionally saves videos to server storage.

**Authentication**: Required

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | Video URL from any supported platform |
| `format` | string | No | `"best"` | Video quality format selector |
| `keep` | boolean | No | `false` | Save video to server storage if true |

### Format Options

| Format | Description |
|--------|-------------|
| `best` | Highest available quality |
| `worst` | Lowest available quality |
| `best[height<=360]` | 360p or lower |
| `best[height<=720]` | 720p or lower |
| `best[height<=1080]` | 1080p or lower |
| `best[height<=1440]` | 1440p or lower |
| `best[height<=2160]` | 4K or lower |

### Example Requests

**Download 720p video (temporary)**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/download?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format=best[height<=720]"
```

**Download and keep on server**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/download?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format=best[height<=720]&keep=true"
```

### Response

**Headers**:
- `Content-Type`: `application/octet-stream`
- `Content-Disposition`: `attachment; filename="Video Title.mp4"`
- `X-Server-Path`: `/downloads/filename.mp4` (only when `keep=true`)

**Body**: Binary video file stream

### Error Responses

```json
{
  "detail": "Invalid API Key"
}
```

```json
{
  "detail": "Download failed or file not found."
}
```

---

## 3. Video Transcription Endpoint

### `GET /transcription`

**Description**: Extracts and returns video transcriptions/subtitles from supported platforms. Downloads subtitle content directly and parses it into various formats.

**Authentication**: Required

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | Video URL from any supported platform |
| `lang` | string | No | `"en"` | Language code for subtitles |
| `format` | string | No | `"text"` | Output format for transcription |
| `auto` | boolean | No | `true` | Include auto-generated captions |

### Format Options

| Format | Description | Output |
|--------|-------------|--------|
| `text` | Plain text transcript | Clean text with word count |
| `json` | Structured data with metadata | Same as `segments` |
| `segments` | Timestamped segments | Array of timed text segments |
| `srt` | Raw SRT subtitle format | Original SRT content |
| `vtt` | Raw VTT subtitle format | Original VTT content |

### Language Options

Common language codes:
- `en` - English
- `es` - Spanish  
- `fr` - French
- `de` - German
- `ja` - Japanese
- `ko` - Korean
- `zh` - Chinese
- `ar` - Arabic

**Note**: Language codes vary by platform:
- YouTube: Often uses simple codes (`en`, `es`, `fr`)
- TikTok: Uses region-specific codes (`eng-US`, `ara-SA`)
- Use `/transcription/locales` endpoint to get exact codes for a video

*Fallback: If specified language not found, tries `en`, `en-US`, `en-GB`*

### Important Notes on Subtitle Availability

1. **Check availability first**: Use `/transcription/locales` to verify which languages are available before requesting transcriptions
2. **Platform variations**: Different platforms have different subtitle availability patterns
3. **Manual vs Auto**: Manual subtitles are more accurate than auto-generated captions

### Example Requests

**Get plain text transcript**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/transcription?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&lang=en&format=text"
```

**Get timestamped segments**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/transcription?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format=segments"
```

**Get Spanish subtitles in SRT format**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/transcription?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&lang=es&format=srt"
```

### Response Examples

**Text Format Response**:
```json
{
  "transcript": "Hello, welcome to this video. Today we'll discuss the importance of value propositions...",
  "word_count": 1250,
  "title": "Video Title",
  "duration": 300,
  "language": "en",
  "source_format": "vtt"
}
```

**Segments Format Response**:
```json
{
  "title": "Video Title",
  "duration": 300,
  "language": "en",
  "source_format": "srt",
  "segments": [
    {
      "start": "00:00:00,000",
      "end": "00:00:03,000",
      "text": "Hello, welcome to this video."
    },
    {
      "start": "00:00:03,000",
      "end": "00:00:07,500",
      "text": "Today we'll discuss the importance of value propositions."
    }
  ],
  "full_text": "Hello, welcome to this video. Today we'll discuss the importance of value propositions.",
  "word_count": 1250,
  "segment_count": 85
}
```

**SRT Format Response**:
```json
{
  "title": "Video Title",
  "language": "en",
  "format": "srt",
  "content": "1\n00:00:00,000 --> 00:00:03,000\nHello, welcome to this video.\n\n2\n00:00:03,000 --> 00:00:07,500\nToday we'll discuss the importance of value propositions.\n",
  "source_format": "srt"
}
```

### Error Responses

**No subtitles available**:
```json
{
  "error": "No subtitles found for language 'es'",
  "available_languages": ["en", "en-US", "fr"],
  "title": "Video Title",
  "duration": 300
}
```

**Subtitle download failed**:
```json
{
  "detail": "Failed to download subtitle content: HTTP 404 Not Found"
}
```

**Invalid format**:
```json
{
  "detail": "Invalid format. Use: text, json, segments, srt, or vtt"
}
```

---

## 4. Get Available Transcription Locales Endpoint

### `GET /transcription/locales`

**Description**: Retrieves all available subtitle/caption languages for a video without downloading the video or subtitles. Useful for building language selectors and checking availability before requesting transcriptions.

**Authentication**: Required

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | Video URL from any supported platform |

### Example Request

```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/transcription/locales?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Example Response

```json
{
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration": 213,
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "locales": [
    {
      "code": "en",
      "name": "English",
      "type": ["manual"],
      "formats": ["vtt", "srt"]
    },
    {
      "code": "es",
      "name": "Spanish",
      "type": ["manual", "auto"],
      "formats": ["vtt", "srt"]
    },
    {
      "code": "fr",
      "name": "French",
      "type": ["auto"],
      "formats": ["vtt"]
    }
  ],
  "summary": {
    "total": 3,
    "manual_count": 2,
    "auto_count": 2,
    "has_manual": true,
    "has_auto": true
  }
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `title` | Video title |
| `duration` | Video duration in seconds |
| `url` | Original video URL |
| `locales` | Array of available language locales |
| `locales[].code` | Language code (e.g., "en", "en-US", "ara-SA") |
| `locales[].name` | Human-readable language name |
| `locales[].type` | Array indicating subtitle type: ["manual"], ["auto"], or ["manual", "auto"] |
| `locales[].formats` | Available subtitle formats (typically "vtt" or "srt") |
| `summary.total` | Total number of available locales |
| `summary.manual_count` | Number of languages with manual subtitles |
| `summary.auto_count` | Number of languages with auto-generated captions |
| `summary.has_manual` | Boolean indicating if any manual subtitles exist |
| `summary.has_auto` | Boolean indicating if any auto-generated captions exist |

### Subtitle Types

- **Manual**: Human-created subtitles, typically higher quality and more accurate
- **Auto**: Auto-generated captions using speech recognition (mainly on YouTube)

### Usage Notes

1. **Platform Differences**:
   - YouTube often has both manual and auto-generated captions in many languages
   - TikTok, Instagram, and other platforms typically only have manual subtitles
   - Auto-generated captions may have transcription errors

2. **Language Code Formats**:
   - Simple codes: `en`, `es`, `fr`
   - Region-specific: `en-US`, `en-GB`, `pt-BR`
   - Platform-specific: `eng-US`, `ara-SA` (TikTok format)

3. **Platform-Specific Language Codes**:

   **Arabic variations**:
   - TikTok: `ara-SA` (Arabic - Saudi Arabia)
   - YouTube: `ar` (generic Arabic)
   - Other platforms: `ar-SA`, `ar-EG`, etc.

   **English variations**:
   - TikTok: `eng-US` (English - US)
   - YouTube: `en`, `en-US`, `en-GB`
   - Other platforms: various regional formats

   **Important**: Always use the exact code returned by `/transcription/locales` when calling `/transcription`. The same language can have different codes on different platforms.

4. **Best Practices**:
   - Call this endpoint before `/transcription` to verify language availability
   - Prefer manual subtitles over auto-generated when both are available
   - Cache the results as subtitle availability rarely changes

### Integration Examples

**Finding the correct language code across platforms:**

```javascript
// Get available languages first
const localesResponse = await fetch('http://localhost:8000/transcription/locales?url=' + videoUrl, {
  headers: { 'X-Api-Key': apiKey }
});
const locales = await localesResponse.json();

// Example 1: Finding English (varies by platform)
const englishLocale = locales.locales.find(l => 
  l.code === 'en' ||        // YouTube
  l.code === 'en-US' ||     // YouTube regional
  l.code === 'eng-US'       // TikTok
);

// Example 2: Finding Arabic (varies by platform)  
const arabicLocale = locales.locales.find(l =>
  l.code === 'ar' ||        // YouTube
  l.code === 'ara-SA' ||    // TikTok
  l.code === 'ar-SA'        // Other platforms
);

// Use the exact code found
if (englishLocale) {
  const transcriptResponse = await fetch(
    `http://localhost:8000/transcription?url=${videoUrl}&lang=${englishLocale.code}`,
    { headers: { 'X-Api-Key': apiKey } }
  );
}
```

**Platform-aware approach:**

```javascript
// Better approach: Use the language name from the response
const locales = await getLocales(videoUrl);

// Find by language name (more reliable across platforms)
const arabicLocale = locales.locales.find(l => 
  l.name.toLowerCase().includes('arabic')
);

const englishLocale = locales.locales.find(l => 
  l.name.toLowerCase().includes('english')
);

// This works regardless of whether it's 'ar', 'ara-SA', etc.
if (arabicLocale) {
  await getTranscription(videoUrl, arabicLocale.code);
}
```

---

## 5. Get Playlist Information Endpoint

### `GET /playlist/info`

**Description**: Extracts metadata from YouTube playlists or channel videos without downloading. Returns a list of video URLs that can be used with existing `/download` and `/transcription` endpoints. Supports filtering by upload date and selecting specific videos.

**Authentication**: Required

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | YouTube playlist or channel URL |
| `dateafter` | string | No | - | Filter videos uploaded after this date |
| `datebefore` | string | No | - | Filter videos uploaded before this date |
| `max_items` | integer | No | - | Maximum number of videos to return |
| `items` | string | No | - | Select specific videos by index |

### Date Filter Format

Date parameters support two formats:

1. **Absolute dates**: `YYYYMMDD` format
   - Example: `20240101` (January 1, 2024)
   - Example: `20231225` (December 25, 2023)

2. **Relative dates**: Based on current date
   - `today` - Current date
   - `yesterday` - Yesterday's date
   - `today-1week` or `now-7days` - 7 days ago
   - `today-1month` - 1 month ago
   - `today-1year` - 1 year ago
   - Pattern: `[now|today|yesterday][-N[day|week|month|year]]`

### Item Selection Format

The `items` parameter allows precise video selection:
- Range: `1:5` - Videos 1 through 5
- Specific: `1,3,5,7` - Videos at indices 1, 3, 5, and 7
- Mixed: `1:3,7,10:15` - Videos 1-3, 7, and 10-15
- Reverse: `-5:` - Last 5 videos
- Step: `1:10:2` - Every 2nd video from 1 to 10

### Example Requests

**Get all videos from a playlist**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/playlist/info?url=https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
```

**Get videos uploaded in last week**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/playlist/info?url=PLAYLIST_URL&dateafter=today-1week"
```

**Get first 10 videos from 2024**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/playlist/info?url=PLAYLIST_URL&dateafter=20240101&max_items=10"
```

**Get specific videos by index**:
```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/playlist/info?url=PLAYLIST_URL&items=1,5,10"
```

### Example Response

```json
{
  "playlist_title": "Select Lectures",
  "playlist_url": "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
  "channel": "Lex Fridman",
  "channel_id": "@lexfridman",
  "channel_url": "https://www.youtube.com/@lexfridman",
  "video_count": 2,
  "total_count": 25,
  "videos": [
    {
      "url": "https://www.youtube.com/watch?v=0VH1Lim8gL8",
      "title": "Deep Learning State of the Art (2020)",
      "duration": "1:27:41",
      "duration_seconds": 5261,
      "upload_date": "2020-01-15",
      "index": 1,
      "id": "0VH1Lim8gL8",
      "views": 1300000,
      "description": "MIT Deep Learning Lecture on the state of the art in deep learning..."
    },
    {
      "url": "https://www.youtube.com/watch?v=O5xeyoRL95U",
      "title": "Deep Learning Basics: Introduction and Overview",
      "duration": "1:08:06",
      "duration_seconds": 4086,
      "upload_date": "2019-02-04",
      "index": 2,
      "id": "O5xeyoRL95U",
      "views": 2400000
    }
  ],
  "filters_applied": {
    "dateafter": null,
    "datebefore": null,
    "max_items": null,
    "items": null
  }
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `playlist_title` | Name of the playlist or channel |
| `playlist_url` | URL of the playlist |
| `channel` | Channel/uploader name |
| `channel_id` | Channel identifier |
| `channel_url` | URL to the channel |
| `video_count` | Number of videos returned (after filtering) |
| `total_count` | Total videos in playlist (before filtering) |
| `videos` | Array of video information |
| `videos[].url` | Direct URL to the video |
| `videos[].title` | Video title |
| `videos[].duration` | Duration in HH:MM:SS or MM:SS format |
| `videos[].duration_seconds` | Duration in seconds |
| `videos[].upload_date` | Upload date (YYYY-MM-DD format) |
| `videos[].index` | Position in the playlist |
| `videos[].id` | Video ID |
| `videos[].views` | View count (if available) |
| `videos[].description` | Truncated description (first 200 chars) |
| `filters_applied` | Shows which filters were used |

### Single Video Handling

If a single video URL is provided instead of a playlist, the endpoint will return it wrapped as a single-item playlist for consistency:

```json
{
  "playlist_title": "Single Video",
  "playlist_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "channel": "Rick Astley",
  "video_count": 1,
  "videos": [
    {
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "title": "Never Gonna Give You Up",
      "duration": "3:33",
      "index": 1,
      "id": "dQw4w9WgXcQ"
    }
  ]
}
```

### Usage with Other Endpoints

The video URLs returned can be used directly with other endpoints:

**1. Download specific videos from playlist**:
```bash
# First, get playlist info
PLAYLIST_INFO=$(curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/playlist/info?url=PLAYLIST_URL&max_items=5")

# Extract first video URL (using jq)
VIDEO_URL=$(echo $PLAYLIST_INFO | jq -r '.videos[0].url')

# Download the video
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/download?url=$VIDEO_URL&format=best[height<=720]" \
  --output video.mp4
```

**2. Transcribe all recent videos**:
```javascript
// Get recent videos (last week)
const response = await fetch(
  'http://localhost:8000/playlist/info?url=PLAYLIST_URL&dateafter=today-1week',
  { headers: { 'X-Api-Key': apiKey } }
);
const playlist = await response.json();

// Transcribe each video
for (const video of playlist.videos) {
  const transcriptResponse = await fetch(
    `http://localhost:8000/transcription?url=${video.url}&format=text`,
    { headers: { 'X-Api-Key': apiKey } }
  );
  const transcript = await transcriptResponse.json();
  console.log(`${video.title}: ${transcript.word_count} words`);
}
```

### Practical Use Cases

1. **Monitor channels for new content**:
   - Use `dateafter=today-1day` to check for videos uploaded in last 24 hours
   - Automate transcription of new videos

2. **Batch download playlists**:
   - Get playlist info with desired filters
   - Loop through video URLs to download each

3. **Content analysis**:
   - Extract metadata for multiple videos
   - Analyze upload patterns, video lengths, view counts

4. **Selective processing**:
   - Use `items` parameter to process specific videos
   - Filter by date range for historical content

### Best Practices

1. **Use filters to reduce response size**: Large playlists can return hundreds of videos
2. **Cache playlist info**: Video metadata doesn't change frequently
3. **Implement pagination**: Use `items` parameter for large playlists
4. **Check `total_count` vs `video_count`**: Understand how many videos were filtered out
5. **Handle unavailable videos**: Some videos may be private or deleted (returned as null entries)

### Limitations

- Only works with YouTube playlists and channels currently
- Date filtering depends on YouTube providing upload dates
- Some metadata may be unavailable for certain videos
- Private or age-restricted videos may have limited information

### Error Responses

```json
{
  "detail": "Error extracting playlist info: Invalid playlist URL"
}
```

```json
{
  "detail": "Error extracting playlist info: This playlist is private"
}
```

---

## 6. List Downloads Endpoint

### `GET /downloads/list`

**Description**: Lists all videos saved to server storage (when `keep=true` was used in `/download`).

**Authentication**: Required

**Parameters**: None

### Example Request

```bash
curl -H "X-Api-Key: your-key" \
  "http://localhost:8000/downloads/list"
```

### Example Response

```json
{
  "downloads": [
    {
      "filename": "Video_Title_1_20240823_143020.mp4",
      "size": 15728640,
      "created": "2024-08-23T14:30:20.123456",
      "path": "./downloads/Video_Title_1_20240823_143020.mp4"
    },
    {
      "filename": "Another_Video_20240823_143145.mp4", 
      "size": 8945120,
      "created": "2024-08-23T14:31:45.789012",
      "path": "./downloads/Another_Video_20240823_143145.mp4"
    }
  ],
  "count": 2
}
```

### File Size

File sizes are returned in bytes. Common conversions:
- 1 MB = 1,048,576 bytes
- 1 GB = 1,073,741,824 bytes

---

## Supported Platforms

The API supports video downloads and transcriptions from 1000+ platforms including:

- **Video Platforms**: YouTube, Vimeo, DailyMotion
- **Social Media**: TikTok, Instagram, Facebook, Twitter (X)
- **Live Streaming**: Twitch, YouTube Live
- **Educational**: Coursera, edX, Khan Academy
- **News**: CNN, BBC, Reuters
- **And many more**: See [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

---

## Rate Limits and Best Practices

### Recommendations
- Use appropriate video quality formats to avoid large downloads
- Implement client-side timeouts for long video downloads
- Clean up downloaded files regularly if using `keep=true`
- Cache transcriptions on your end to avoid repeated API calls
- Use `format=text` for AI processing, `format=segments` for subtitle display

### Error Handling
- Always check for HTTP error status codes
- Handle cases where videos are private, deleted, or geo-blocked
- Implement retry logic for temporary network failures
- Parse error messages for specific failure reasons

---

## Integration Examples

### n8n Workflow Integration

```javascript
// n8n HTTP Request Node Configuration
{
  "method": "GET",
  "url": "http://video-downloader.railway.internal:8000/transcription",
  "headers": {
    "X-Api-Key": "your-production-key"
  },
  "qs": {
    "url": "{{$json.video_url}}",
    "format": "text",
    "lang": "en"
  }
}
```

### cURL with Environment Variable

```bash
# Set API key once
export API_KEY="your-api-key-here"

# Download video
curl -H "X-Api-Key: $API_KEY" \
  "http://localhost:8000/download?url=VIDEO_URL&keep=true" \
  --output video.mp4

# Get transcript
curl -H "X-Api-Key: $API_KEY" \
  "http://localhost:8000/transcription?url=VIDEO_URL&format=text" \
  | jq -r '.transcript' > transcript.txt
```