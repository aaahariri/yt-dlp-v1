# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based social media video downloader that uses `yt-dlp` to download videos from platforms like YouTube, TikTok, Instagram, Facebook, Twitter, and more. The API streams videos directly to clients without storing them permanently on the server.

## YT-DLP Usage and Options
To learn about yt-dlp and its available suit of tools and options, check the following Github repo: https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#usage-and-options


## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
uv venv
source .venv/bin/activate  # Linux/Mac
# or .venv\Scripts\activate  # Windows

# Install dependencies
uv add fastapi uvicorn yt-dlp python-multipart python-dotenv requests
```

### Running the Application
```bash
# Development server with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production server
python main.py
```

### Environment Configuration
- Copy `example.env` to `.env` and configure `ALLOWED_ORIGIN` for CORS
- Default CORS origin is set to "https://example.com" - update for your frontend domain

## Architecture

### Core Components
- **main.py**: Single-file FastAPI application containing all endpoints and logic
- **Dependencies**: Uses `yt-dlp` for video extraction, FastAPI for web API, and uvicorn for ASGI server

### API Endpoints

#### Video Download
- `GET /`: Root endpoint returning welcome message
- `GET /download`: Main endpoint for video downloading with query parameters:
  - `url` (required): Video URL from supported platforms
  - `format` (optional): Video quality format (default: "best")
  - `keep` (optional): Save video to server (default: false)
  - `custom_title` (optional): Custom filename for download

- `POST /batch-download`: Download multiple videos with automatic rate limiting
  - Supports all major platforms
  - Independent error handling per video
  - Automatic duplicate detection

#### Transcription
- `GET /transcription`: Extract existing subtitles from videos (free, instant)
  - `url` (required): Video URL
  - `lang` (optional): Language code (default: "en")
  - `format` (optional): Output format - text, json, srt, vtt (default: "text")
  - `auto` (optional): Include auto-generated subtitles (default: true)

- `POST /ai-transcribe`: AI-powered transcription with multi-provider support
  - `url` (required): Video URL
  - `format` (optional): Output format - json, srt, vtt, text (default: "json")
  - `language` (optional): Language code for transcription (auto-detect if not specified)
  - `model_size` (optional): Model size - tiny, small, medium, large-v2, large-v3, turbo (default: "medium")
  - `provider` (optional): AI provider - local or openai (default: "local")
  - **Providers**:
    - `local`: whisperX (70x real-time on GPU, 3-5x on CPU, $0 cost, word-level timestamps)
    - `openai`: OpenAI Whisper API ($0.006/min)

- `POST /smart-transcribe`: **Recommended** - Hybrid transcription endpoint
  - First tries subtitle extraction (free, instant)
  - Falls back to AI transcription if no subtitles available
  - `url` (required): Video URL
  - `format` (optional): Output format - json, srt, vtt, text (default: "json")
  - `language` (optional): Preferred language code (default: "en")
  - `force_ai` (optional): Skip subtitles and use AI directly (default: false)
  - `model_size` (optional): AI model size if needed (default: "medium")
  - `provider` (optional): AI provider - local or openai (default: "local")
  - **Best for**: Maximizing cost efficiency while ensuring complete transcription coverage

- `GET /transcription/locales`: Get available subtitle languages for a video
- `GET /playlist/info`: Extract playlist metadata without downloading
- `GET /downloads/list`: List all downloaded files on the server

### Download Process
1. Extract video metadata using yt-dlp without downloading
2. Generate unique temporary filename in `/tmp/` directory
3. Download video with specified format to temporary location
4. Stream file content to client with proper Content-Disposition headers
5. Clean up temporary file after streaming completes

### Supported Formats
Common format strings for quality selection:
- `best[height<=360]`: 360p quality
- `best[height<=720]`: 720p quality  
- `best[height<=1080]`: 1080p quality
- `best`: Highest available quality

### File Handling
- Videos are temporarily stored in `/tmp/` with UUID-based filenames
- Original video titles are sanitized and used for download filenames
- Files are automatically deleted after streaming to prevent storage buildup

### CORS Configuration
- Configured to allow specific origin from environment variable
- Allows all methods and headers for the configured origin
- Credentials are enabled for cross-origin requests

## Dependencies

### Core Dependencies
- **fastapi**: Web framework for building the API
- **uvicorn**: ASGI server for running the FastAPI application
- **yt-dlp**: Core library for video extraction and downloading
- **python-multipart**: For handling multipart form data
- **python-dotenv**: Environment variable loading from .env files
- **requests**: HTTP library for downloading subtitle content

### AI Transcription (Optional)
- **whisperX**: Enhanced Whisper implementation with word-level timestamps for AI transcription
  - **Installation**: `uv add whisperx` or `pip install whisperx`
  - **Requirements**: Works on CPU, NVIDIA GPUs (CUDA), Apple Silicon (MPS - experimental)
  - **Models**: Automatically downloads on first use (39MB to 1.5GB depending on model size)
  - **Performance**: 70x faster than real-time on GPU, 3-5x on CPU
  - **Features**: Word-level timestamps, speaker diarization support, automatic device detection
  - **Note**: Optional dependency - subtitle extraction works without it

## Platform Support

The application supports video downloads from 1000+ platforms through yt-dlp, including major social media and video hosting sites. See [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) for the complete list.

## Transcription Features

### Subtitle Extraction
The application can extract existing subtitles from videos using yt-dlp:
- **Free & Instant**: No processing time or cost
- **Supports**: Manual subtitles and auto-generated captions
- **Formats**: VTT, SRT, plain text, JSON with timestamps
- **Languages**: 100+ languages supported by platforms
- **Best for**: YouTube videos, educational content, any video with existing captions

### AI Transcription (whisperX)
For videos without subtitles, the application offers AI-powered transcription:
- **Local Processing**: Runs on any server (CPU/GPU), no cloud API fees ($0 cost)
- **High Accuracy**: OpenAI Whisper models with 95%+ accuracy for clear audio
- **Multi-language**: Supports 99 languages with automatic language detection
- **Word-level Timestamps**: Provides precise word-level timestamps (not just segments)
- **Multiple Formats**: JSON, SRT, VTT, plain text
- **Platform Agnostic**: Works on Railway (CPU mode), NVIDIA GPUs, Apple Silicon

#### Model Selection
Choose based on your needs:
- **tiny** (39MB): Ultra-fast, lower accuracy - good for quick drafts
- **small** (244MB): Fast, good accuracy - balanced for most use cases
- **medium** (769MB): Very good accuracy - recommended default
- **large-v2/large-v3** (1.5GB): Highest accuracy - best for production
- **turbo** (809MB): **Best choice** - excellent accuracy with fastest speed

#### Performance
- **GPU (NVIDIA/MPS)**: 70x faster than real-time
- **CPU**: 3-5x faster than real-time (int8 quantization)
- **Example**: 10-minute video transcribed in 8-20 seconds (GPU) or 2-3 minutes (CPU)
- **Memory**: 2-12GB RAM depending on model size and device
- **Railway Compatible**: Works in CPU mode on Railway deployment ($0 cost)

### Smart Transcription (Hybrid Approach)
The `/smart-transcribe` endpoint automatically:
1. Checks for existing subtitles (free, instant)
2. Falls back to AI if no subtitles found
3. Returns unified format with `source` field indicating "subtitle" or "ai"

**Benefits**:
- **Cost optimization**: Uses free subtitles when available
- **Complete coverage**: AI fallback ensures all videos can be transcribed
- **Consistent output**: Same format regardless of source

### Output Formats

#### JSON Format (Recommended for APIs)
```json
{
  "title": "Video Title",
  "duration": 630,
  "language": "en",
  "segments": [
    {"start": 0.0, "end": 3.5, "text": "Hello, welcome to the video."},
    {"start": 3.5, "end": 7.2, "text": "Today we'll discuss..."}
  ],
  "full_text": "Hello, welcome to the video. Today we'll discuss...",
  "word_count": 245,
  "source": "ai"
}
```

#### SRT Format (Subtitle Files)
```srt
1
00:00:00,000 --> 00:00:03,500
Hello, welcome to the video.

2
00:00:03,500 --> 00:00:07,200
Today we'll discuss transcription.
```

#### VTT Format (WebVTT for Web Players)
```vtt
WEBVTT

00:00:00.000 --> 00:00:03.500
Hello, welcome to the video.

00:00:03.500 --> 00:00:07.200
Today we'll discuss transcription.
```

#### Text Format (Plain Text)
```json
{
  "transcript": "Hello, welcome to the video. Today we'll discuss transcription...",
  "word_count": 245,
  "title": "Video Title"
}
```

## Key References

- **yt-dlp GitHub Repository**: https://github.com/yt-dlp/yt-dlp
  - Main reference for yt-dlp usage, options, and capabilities
  - Contains comprehensive documentation for format selectors, extraction options, and platform-specific features
  - Essential for understanding advanced yt-dlp configuration and troubleshooting

- **whisperX GitHub Repository**: https://github.com/m-bain/whisperX
  - Enhanced Whisper implementation with word-level timestamps
  - Documentation for model selection and performance optimization
  - Essential for AI transcription features on any platform (CPU/GPU)