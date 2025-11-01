# Batch Download API Documentation

## Overview

The Batch Download API endpoint allows you to download multiple videos from various platforms in a single API request. This endpoint automatically detects platforms, applies appropriate formatting, and handles rate limiting to prevent blocks.

---

## Endpoint

### `POST /batch-download`

Download multiple videos from YouTube, TikTok, Instagram, Facebook, Twitter, and 1000+ other platforms in batch.

**Authentication:** Required (`X-Api-Key` header)

---

## Request Format

### Request Body (JSON)

```json
{
  "urls": [
    "https://www.youtube.com/watch?v=VIDEO_1",
    "https://www.tiktok.com/@user/video/123",
    "https://www.instagram.com/p/POST_ID/"
  ],
  "format": "best[height<=720]",
  "keep": true,
  "min_delay": 5,
  "max_delay": 10,
  "cookies_file": null
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `urls` | array[string] | **Yes** | - | List of video URLs to download (min: 1) |
| `format` | string | No | `"best[height<=720]"` | Video quality format selector |
| `keep` | boolean | No | `true` | Save videos to server storage |
| `min_delay` | integer | No | `5` | Minimum delay between downloads (0-300 seconds) |
| `max_delay` | integer | No | `10` | Maximum delay between downloads (0-300 seconds) |
| `cookies_file` | string | No | `null` | Path to cookies file for authentication |

---

## Response Format

### Success Response

**Status Code:** `200 OK`

```json
{
  "total": 3,
  "successful": 2,
  "failed": 1,
  "skipped": 0,
  "downloads": [
    {
      "url": "https://www.youtube.com/watch?v=VIDEO_1",
      "success": true,
      "filename": "YT-Video-Title-Here.mp4",
      "file_path": "./downloads/YT-Video-Title-Here.mp4",
      "file_size": 15728640,
      "platform": "YT",
      "title": "Original Video Title Here",
      "error": null
    },
    {
      "url": "https://www.tiktok.com/@user/video/123",
      "success": true,
      "filename": "TT-Viral-Dance-Trend.mp4",
      "file_path": "./downloads/TT-Viral-Dance-Trend.mp4",
      "file_size": 8945120,
      "platform": "TT",
      "title": "Viral Dance Trend",
      "error": null
    },
    {
      "url": "https://www.instagram.com/p/POST_ID/",
      "success": false,
      "filename": null,
      "file_path": null,
      "file_size": null,
      "platform": "IG",
      "title": null,
      "error": "Private video"
    }
  ],
  "total_size": 24673760,
  "duration_seconds": 45.23
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `total` | integer | Total number of videos requested |
| `successful` | integer | Number of successfully downloaded videos |
| `failed` | integer | Number of failed downloads |
| `skipped` | integer | Number of skipped videos (already downloaded) |
| `downloads` | array | Detailed results for each video |
| `total_size` | integer | Total size of all downloads in bytes |
| `duration_seconds` | float | Total time taken for batch download |

### Video Download Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Original video URL |
| `success` | boolean | Whether download succeeded |
| `filename` | string | Generated filename (with platform prefix) |
| `file_path` | string | Relative path to downloaded file |
| `file_size` | integer | File size in bytes |
| `platform` | string | Detected platform (YT, TT, IG, FB, X, etc.) |
| `title` | string | Extracted video title |
| `error` | string | Error message if failed (null if successful) |

---

## Platform Support

### Automatic Platform Detection

The endpoint automatically detects the platform from the URL and applies the appropriate prefix to filenames:

| Platform | Prefix | Example URL |
|----------|--------|-------------|
| YouTube | `YT` | `https://youtube.com/watch?v=...` |
| TikTok | `TT` | `https://tiktok.com/@user/video/...` |
| Instagram | `IG` | `https://instagram.com/p/...` |
| Facebook | `FB` | `https://facebook.com/watch/...` |
| Twitter/X | `X` | `https://twitter.com/user/status/...` |
| Vimeo | `VM` | `https://vimeo.com/...` |
| DailyMotion | `DM` | `https://dailymotion.com/video/...` |
| Twitch | `TW` | `https://twitch.tv/videos/...` |
| Other | `VIDEO` | Any other supported platform |

### Mixed Platform Batches

You can mix URLs from different platforms in a single request:

```json
{
  "urls": [
    "https://www.youtube.com/watch?v=ABC123",
    "https://www.tiktok.com/@user/video/789",
    "https://www.instagram.com/reel/XYZ/",
    "https://twitter.com/user/status/456"
  ],
  "format": "best[height<=720]",
  "keep": true
}
```

**Result:**
- YouTube video → `YT-video-title.mp4`
- TikTok video → `TT-video-title.mp4`
- Instagram reel → `IG-video-title.mp4`
- Twitter video → `X-video-title.mp4`

---

## Usage Examples

### Example 1: Basic YouTube Batch

**Request:**
```bash
curl -X POST "http://localhost:8000/batch-download" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-api-key" \
  -d '{
    "urls": [
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    ]
  }'
```

**Response:**
```json
{
  "total": 2,
  "successful": 2,
  "failed": 0,
  "skipped": 0,
  "downloads": [
    {
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "success": true,
      "filename": "YT-Rick-Astley-Never-Gonna-Give-You-Up.mp4",
      "file_path": "./downloads/YT-Rick-Astley-Never-Gonna-Give-You-Up.mp4",
      "file_size": 4567890,
      "platform": "YT",
      "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
      "error": null
    },
    ...
  ],
  "total_size": 8945120,
  "duration_seconds": 25.5
}
```

### Example 2: Multi-Platform Batch

**Request:**
```json
{
  "urls": [
    "https://www.youtube.com/watch?v=ABC123",
    "https://www.tiktok.com/@user/video/123456",
    "https://www.instagram.com/p/POST123/",
    "https://twitter.com/user/status/789012"
  ],
  "format": "best[height<=1080]",
  "keep": true,
  "min_delay": 10,
  "max_delay": 20
}
```

### Example 3: High Quality with Longer Delays

```json
{
  "urls": [
    "https://www.youtube.com/watch?v=VIDEO1",
    "https://www.youtube.com/watch?v=VIDEO2",
    "https://www.youtube.com/watch?v=VIDEO3"
  ],
  "format": "best",
  "keep": true,
  "min_delay": 20,
  "max_delay": 30
}
```

### Example 4: Temporary Downloads (No Storage)

```json
{
  "urls": [
    "https://www.youtube.com/watch?v=VIDEO1"
  ],
  "format": "best[height<=480]",
  "keep": false,
  "min_delay": 0,
  "max_delay": 0
}
```

### Example 5: With Authentication Cookies

```json
{
  "urls": [
    "https://www.patreon.com/posts/video-123"
  ],
  "keep": true,
  "cookies_file": "/path/to/cookies.txt"
}
```

---

## Format Options

Same as single download endpoint:

| Format | Description |
|--------|-------------|
| `best` | Highest available quality |
| `worst` | Lowest available quality |
| `best[height<=360]` | 360p or lower |
| `best[height<=720]` | 720p or lower (default) |
| `best[height<=1080]` | 1080p or lower |
| `best[height<=2160]` | 4K or lower |
| `bestaudio` | Audio only (best quality) |

---

## Rate Limiting

### Why Delays Are Important

Platforms like YouTube, TikTok, and Instagram have rate limits. Downloading too many videos too quickly can result in:
- Temporary IP bans
- 429 "Too Many Requests" errors
- Failed downloads

### Recommended Delays

| Platform | Min Delay | Max Delay | Reason |
|----------|-----------|-----------|--------|
| YouTube | 10s | 20s | Moderate rate limiting |
| TikTok | 15s | 30s | Strict rate limiting |
| Instagram | 30s | 60s | Very strict rate limiting |
| Twitter/X | 5s | 15s | Lenient rate limiting |
| Vimeo | 5s | 10s | Lenient rate limiting |

### How Delays Work

- Random delay between `min_delay` and `max_delay` is added after each download
- No delay after the last video
- Formula: `time.sleep(random.randint(min_delay, max_delay))`

---

## Error Handling

### Common Errors and Solutions

#### 1. Video Not Available

**Error:**
```json
{
  "success": false,
  "error": "Video unavailable"
}
```

**Causes:**
- Video is private
- Video is geo-blocked
- Video has been deleted
- Age-restricted content

**Solution:**
- Use cookies file for authentication
- Use VPN if geo-blocked
- Skip unavailable videos

#### 2. Rate Limited

**Error:**
```json
{
  "success": false,
  "error": "HTTP Error 429: Too Many Requests"
}
```

**Solution:**
- Increase `min_delay` and `max_delay`
- Reduce batch size (fewer URLs per request)
- Wait 10-15 minutes before retrying

#### 3. Format Not Available

**Error:**
```json
{
  "success": false,
  "error": "Requested format not available"
}
```

**Solution:**
- Use `"best"` instead of specific height
- Lower quality setting (e.g., `best[height<=480]`)

#### 4. Authentication Required

**Error:**
```json
{
  "success": false,
  "error": "This video requires authentication"
}
```

**Solution:**
- Provide `cookies_file` parameter
- Extract cookies from logged-in browser session

---

## Best Practices

### 1. **Batch Size**

Don't download too many videos at once:
- **Small batches:** 5-10 videos (recommended)
- **Medium batches:** 10-20 videos
- **Large batches:** 20+ videos (use longer delays)

### 2. **Platform Grouping**

Group URLs by platform when possible:
```json
{
  "urls": [
    "https://www.youtube.com/watch?v=1",
    "https://www.youtube.com/watch?v=2",
    "https://www.youtube.com/watch?v=3"
  ]
}
```

Instead of mixing:
```json
{
  "urls": [
    "https://www.youtube.com/watch?v=1",
    "https://www.tiktok.com/@user/video/2",
    "https://www.youtube.com/watch?v=3"
  ]
}
```

### 3. **Quality Selection**

Balance quality vs speed:
- **Fast:** `best[height<=480]` (480p)
- **Balanced:** `best[height<=720]` (720p) - **Default**
- **High:** `best[height<=1080]` (1080p)
- **Max:** `best` (highest available)

### 4. **Storage Management**

- Use `"keep": false` for temporary analysis
- Use `"keep": true` for archiving
- Regularly clean up downloads directory
- Monitor disk space

### 5. **Error Recovery**

Check response for failed downloads:
```javascript
const response = await fetch('/batch-download', {...});
const data = await response.json();

// Retry failed downloads
const failedUrls = data.downloads
  .filter(d => !d.success)
  .map(d => d.url);

if (failedUrls.length > 0) {
  // Retry with longer delays
  await fetch('/batch-download', {
    body: JSON.stringify({
      urls: failedUrls,
      min_delay: 30,
      max_delay: 60
    })
  });
}
```

---

## Limitations

### Current Limitations

1. **Synchronous Processing** - Request waits until all downloads complete
2. **No Progress Updates** - No real-time progress during download
3. **No Partial Results** - If one video fails, others still continue
4. **No Resume** - Failed batches must be retried manually
5. **Sequential Only** - Videos downloaded one at a time

### Timeout Considerations

- Large batches may timeout (especially with delays)
- Recommended maximum: 20 videos per batch
- For more videos: split into multiple requests

### File Size Limits

- No file size limit enforced
- Large videos (>500MB) may take several minutes
- Monitor disk space when downloading many videos

---

## Comparison with Single Download

| Feature | Single Download | Batch Download |
|---------|----------------|----------------|
| **Endpoint** | `GET /download` | `POST /batch-download` |
| **Method** | GET | POST |
| **URLs** | 1 | Multiple (1+) |
| **Platform Detection** | Manual | Automatic |
| **Rate Limiting** | Manual | Built-in |
| **Response** | File stream | JSON summary |
| **Use Case** | Single video | Multiple videos |

---

## Integration Examples

### JavaScript/Node.js

```javascript
async function batchDownload(urls) {
  const response = await fetch('http://localhost:8000/batch-download', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Api-Key': 'your-api-key'
    },
    body: JSON.stringify({
      urls: urls,
      format: 'best[height<=720]',
      keep: true,
      min_delay: 10,
      max_delay: 20
    })
  });

  const result = await response.json();
  console.log(`Downloaded ${result.successful}/${result.total} videos`);
  console.log(`Total size: ${(result.total_size / 1024 / 1024).toFixed(2)} MB`);

  return result;
}

// Usage
const urls = [
  'https://www.youtube.com/watch?v=VIDEO1',
  'https://www.youtube.com/watch?v=VIDEO2'
];

batchDownload(urls);
```

### Python

```python
import requests

def batch_download(urls, api_key):
    response = requests.post(
        'http://localhost:8000/batch-download',
        headers={'X-Api-Key': api_key},
        json={
            'urls': urls,
            'format': 'best[height<=720]',
            'keep': True,
            'min_delay': 10,
            'max_delay': 20
        }
    )

    result = response.json()
    print(f"Downloaded {result['successful']}/{result['total']} videos")
    print(f"Total size: {result['total_size'] / 1024 / 1024:.2f} MB")

    return result

# Usage
urls = [
    'https://www.youtube.com/watch?v=VIDEO1',
    'https://www.youtube.com/watch?v=VIDEO2'
]

batch_download(urls, 'your-api-key')
```

### cURL

```bash
curl -X POST "http://localhost:8000/batch-download" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-api-key" \
  -d @batch_request.json
```

**batch_request.json:**
```json
{
  "urls": [
    "https://www.youtube.com/watch?v=VIDEO1",
    "https://www.youtube.com/watch?v=VIDEO2"
  ],
  "format": "best[height<=720]",
  "keep": true,
  "min_delay": 10,
  "max_delay": 20
}
```

---

## Related Documentation

- [API Endpoints Usage](./endpoints-usage.md)
- [Local Scripts Documentation](./local-scripts.md)
- [Deno Setup Guide](./deno-setup.md)

---

**Last Updated:** 2025-11-01
**API Version:** 1.0.0
**Compatible with:** yt-dlp 2025.10.14+
