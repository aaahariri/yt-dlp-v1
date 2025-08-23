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
- `GET /`: Root endpoint returning welcome message
- `GET /download`: Main endpoint for video downloading with query parameters:
  - `url` (required): Video URL from supported platforms  
  - `format` (optional): Video quality format (default: "best")

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

- **fastapi**: Web framework for building the API
- **uvicorn**: ASGI server for running the FastAPI application
- **yt-dlp**: Core library for video extraction and downloading
- **python-multipart**: For handling multipart form data
- **python-dotenv**: Environment variable loading from .env files
- **requests**: HTTP library for downloading subtitle content

## Platform Support

The application supports video downloads from 1000+ platforms through yt-dlp, including major social media and video hosting sites. See [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) for the complete list.

## Key References

- **yt-dlp GitHub Repository**: https://github.com/yt-dlp/yt-dlp
  - Main reference for yt-dlp usage, options, and capabilities
  - Contains comprehensive documentation for format selectors, extraction options, and platform-specific features
  - Essential for understanding advanced yt-dlp configuration and troubleshooting