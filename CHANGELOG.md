# file: CHANGELOG.md | Log of key changes made
# description: Use this file to document key changes made to any features, functions, or code with structured entries for easy parsing by AI agents and developers.

## Template Format:
```
YYYY-MM-DD | [TYPE] | [SCOPE] | WHAT → WHY → IMPACT
- Files: `path/to/file.tsx`, `path/to/other.tsx`
- Tags: #component #refactor #breaking-change
```

### Change Types:
- **[FEATURE]** - New functionality
- **[FIX]** - Bug fixes  
- **[REFACTOR]** - Code restructuring without functional changes
- **[BREAKING]** - Changes that break existing functionality
- **[DOCS]** - Documentation updates
- **[PERF]** - Performance improvements
- **[TEST]** - Test additions/updates

---

## Recent Changes

2025-11-02 | [FEATURE] | [CONCURRENCY] | Transcription concurrency limits to prevent memory overload
- Added MAX_CONCURRENT_TRANSCRIPTIONS environment variable (default: 2) to limit parallel transcriptions (main.py:50-56)
- Implemented asyncio.Semaphore pattern to queue excess requests instead of crashing (main.py:970-1011)
- Prevents out-of-memory crashes when multiple transcription requests arrive simultaneously
- Each whisperX model instance requires 0.5-3.5GB RAM depending on model size (tiny to large-v2)
- M1 Mac (8GB RAM) safe limits: tiny (4-6), medium (2-3), turbo (1-2), large-v2 (1)
- Railway deployment limits auto-calculated based on available memory
- Created docs/concurrency-limits.md with memory calculations and platform-specific recommendations
- Created docs/mps-and-device-selection.md explaining M1 GPU vs CPU usage with whisperX
- Improved MPS device detection with automatic CPU fallback if MPS/CUDA fails (main.py:1020-1070)
- Files: `main.py:9,50-56,970-1011,1020-1070`, `.env`, `docs/concurrency-limits.md`, `docs/mps-and-device-selection.md`
- Tags: #feature #concurrency #memory-management #stability #whisperx

2025-11-02 | [FIX] | [AUDIO] | Local file audio extraction and whisperX CPU mode
- Fixed /extract-audio endpoint to use FFmpeg directly for local files (main.py:836-920)
- Removed yt-dlp file:// URL approach due to security restrictions
- Added subprocess-based FFmpeg audio extraction with timeout protection
- Disabled MPS (Apple Silicon GPU) support in whisperX due to compatibility issues (main.py:1020-1034)
- Force CPU mode for stability (3-5x real-time transcription speed)
- Installed FFmpeg 8.0 as required dependency for local file processing
- Uninstalled mlx-whisper (M1-only), kept whisperX (cross-platform)
- All endpoints tested and working: subtitles, audio extraction, AI transcription
- Files: `main.py:836-920`, `main.py:1020-1034`
- Tags: #fix #audio-extraction #whisperx #cpu-mode #ffmpeg

2025-11-02 | [DOCS] | [WORKFLOWS] | Platform-specific composable workflow guide
- Created docs/composable-workflows.md with platform-specific transcription strategies
- YouTube: Try subtitles first (instant, $0) → fallback to audio extraction + AI
- TikTok/Instagram/Twitter: Direct audio extraction (no subtitle check)
- Podcasts: Audio-only downloads with format conversion support
- Batch processing: Download once, retry transcription without re-downloading
- Model selection guide: tiny (short videos) → turbo (long content) → large-v2 (critical accuracy)
- Cost comparison: Local ($0) vs OpenAI ($0.006/min)
- Error handling strategies: graceful degradation, OOM retry with smaller model
- Platform quick reference table with timing estimates
- Files: `docs/composable-workflows.md`
- Tags: #docs #workflows #platform-specific #best-practices

2025-11-02 | [REFACTOR] | [ARCHITECTURE] | Clean endpoint architecture with single responsibility principle
- Renamed GET /transcription → GET /subtitles (extract existing subtitles only)
- Created POST /extract-audio (extract audio from URL or local video file)
- Created POST /transcribe (transcribe audio file with AI - accepts file path only)
- Each endpoint now has ONE clear responsibility (no overlapping logic)
- Composable workflow: /subtitles → /extract-audio → /transcribe
- Improved error messages with suggested next steps
- /subtitles returns 404 with workflow guidance if no subtitles found
- /extract-audio works with URLs or local files from /download
- /transcribe accepts audio_file path (not URLs)
- Comprehensive error handling: timeouts, connection failures, OOM detection
- Files: `main.py:599-1217`, `docs/endpoint-flows.md`, `docs/clean-api-architecture.md`
- Tags: #refactor #architecture #single-responsibility #clean-code

2025-11-02 | [FEATURE] | [API] | Download and transcribe workflow with comprehensive error handling
- Added POST /download-and-transcribe endpoint for download + transcribe in one workflow
- Download video to server, transcribe with subtitles or AI, optionally keep or delete files
- Enables retry capability without re-downloading (keep_video=true)
- Improved error handling across all transcription endpoints with detailed error messages
- OpenAI errors: Timeout (504), connection failures (503), API errors with HTTP status codes
- Local whisperX errors: Import errors, model loading, audio format issues, OOM detection
- Created docs/endpoint-flows.md with mermaid diagrams and step-by-step logic for all endpoints
- Files: `main.py:1170-1600`, `main.py:730-845` (error handling), `docs/endpoint-flows.md`
- Tags: #feature #api #transcription #error-handling #documentation

2025-11-02 | [REFACTOR] | [AI] | Migrated from mlx-whisper to whisperX for enhanced transcription
- Replaced mlx-whisper with whisperX for broader platform compatibility
- Added support for CPU, NVIDIA GPU (CUDA), and Apple Silicon (MPS) devices
- Improved performance: 70x real-time on GPU, 3-5x on CPU (vs 3-8x on M1 only)
- Added word-level timestamps (not just segment-level)
- Railway deployment now supports local provider in CPU mode ($0 cost)
- Additional models: large-v2, large-v3 for highest accuracy
- Automatic device detection (CUDA > MPS > CPU)
- Files: `main.py`, `requirements.txt`, `pyproject.toml`, `CLAUDE.md`, `docs/transcription-services.md`, `docs/transcription-setup-guide.md`
- Tags: #refactor #ai #transcription #whisperx #performance

2025-11-02 | [FEATURE] | [API] | AI-powered video transcription with local and cloud support
- Added POST /ai-transcribe endpoint with mlx-whisper (M1-optimized) and OpenAI providers
- Added POST /smart-transcribe hybrid endpoint (tries subtitles first, falls back to AI)
- Support for 99 languages with automatic detection using OpenAI Whisper (open source)
- Multiple output formats: JSON with timestamps, SRT, VTT, plain text
- Local transcription: $0 cost on M1/M2/M3 Macs using mlx-whisper (3-8x real-time speed)
- Cloud transcription: OpenAI Whisper API ($0.36/hr) for Railway/non-M1 deployment
- Files: `main.py`, `requirements.txt`, `pyproject.toml`, `CLAUDE.md`, `docs/transcription-services.md`, `docs/transcription-setup-guide.md`
- Tags: #feature #api #ai #transcription #whisper

2025-11-02 | [FIX] | [DEPLOY] | Railway deployment pip command not found error
- Fixed nixpacks.toml to use `python3 -m pip` instead of `pip` for Nixpacks compatibility
- Resolves "pip: command not found" error during Railway build process with nixPkgs python312
- Files: `nixpacks.toml`
- Tags: #fix #deployment #railway #nixpacks

2025-11-01 | [FEATURE] | [API] | Batch download API endpoint with multi-platform support
- Added POST /batch-download endpoint for downloading multiple videos with automatic platform detection
- Pydantic models for type-safe requests, configurable rate limiting, comprehensive error handling
- Files: `main.py`, `docs/batch-download-api.md`, `test_batch_request.json`
- Tags: #feature #api #batch-download #multi-platform

2025-11-01 | [DOCS] | [SCRIPTS] | Local scripts documentation
- Created docs/local-scripts.md with usage guide for batch_download.py
- Files: `docs/local-scripts.md`
- Tags: #docs #scripts

2025-11-01 | [FEATURE] | [TOOLING] | Batch download script with rate limiting
- Created batch_download.py for bulk downloads with 20-30s random pauses
- Files: `batch_download.py`
- Tags: #feature #tooling

2025-11-01 | [FEATURE] | [API] | Custom title parameter for downloads
- Added custom_title parameter to /download endpoint
- Files: `main.py`
- Tags: #feature #api

2025-11-01 | [FEATURE] | [API] | Platform prefix filename formatting
- Added get_platform_prefix(), format_title_for_filename(), create_formatted_filename()
- Consistent naming: {PLATFORM}-{title}.{ext} with 50 char limit
- Files: `main.py`, `batch_download.py`
- Tags: #feature #filenames