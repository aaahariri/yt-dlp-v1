# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based social media video downloader that uses `yt-dlp` to download videos from platforms like YouTube, TikTok, Instagram, Facebook, Twitter, and more. The API streams videos directly to clients without storing them permanently on the server.

## Philosophy
MUST ADHERE to these principles:
- Test-Driven Development: Write tests first, always
- Systematic over ad-hoc: Process over guessing.
- Complexity reduction: Simplicity as primary goal, avoiding over-engineering at all costs.
- Evidence over claims - Verify before declaring success.


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


#### Optional: Supabase Integration
See [docs/supabase-integration.md](docs/supabase-integration.md) for complete setup and usage.

## Architecture

### Core Components
- **main.py**: Single-file FastAPI application containing all endpoints and logic
- **Dependencies**: Uses `yt-dlp` for video extraction, FastAPI for web API, and uvicorn for ASGI server

### API Documentation
**IMPORTANT**: When working with endpoints:
- **Always check [docs/endpoints-index.md](docs/endpoints-index.md)** first for a complete list of all endpoints
- Update the endpoints-index.md file when adding, modifying, or removing endpoints
- Ensure all endpoint changes are documented in both endpoints-index.md and endpoints-usage.md
- Keep implementation line numbers in endpoints-index.md up to date (search by endpoint path if unsure)

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
  - **Requirements**: Works on CPU, NVIDIA GPUs (CUDA), Apple Silicon (MPS - experimental)
  - **Models**: Automatically downloads on first use (39MB to 1.5GB depending on model size)
  - **Performance**: 70x faster than real-time on GPU, 3-5x on CPU
  - **Features**: Word-level timestamps, speaker diarization support, automatic device detection
  - **Note**: Optional dependency - subtitle extraction works without it


## Platform Support

The application supports video downloads from 1000+ platforms through yt-dlp, including major social media and video hosting sites. See [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) for the complete list.

## Key References

- **yt-dlp GitHub Repository**: https://github.com/yt-dlp/yt-dlp
  - Main reference for yt-dlp usage, options, and capabilities
  - Contains comprehensive documentation for format selectors, extraction options, and platform-specific features
  - Essential for understanding advanced yt-dlp configuration and troubleshooting

- **whisperX GitHub Repository**: https://github.com/m-bain/whisperX
  - Enhanced Whisper implementation with word-level timestamps
  - Documentation for model selection and performance optimization
  - Essential for AI transcription features on any platform (CPU/GPU)