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

2026-01-04 | [FEATURE] | [YOUTUBE-AUTH] | Auto-detect login success with polling (no manual Enter needed)
- Rewrote cookie refresh scripts to auto-detect login success via DOM checks
- Polls every 5s for up to 5 minutes: checks avatar button, sign-in button absence, URL
- Supports push notification 2FA: RunPod enters credentials → user approves on phone → auto-continues
- Saved state optimization: checks if already logged in before attempting login
- Validates essential cookies (SID, SSID, HSID, LOGIN_INFO) after extraction
- Loads .env automatically from project root
- Files: `scripts/refresh_youtube_cookies.py`, `scripts/refresh_youtube_cookies_async.py`
- Tags: #feature #youtube-auth #automation #2fa

2026-01-04 | [FEATURE] | [ALERTS] | Added system_alerts table with spam prevention
- New `system_alerts` table for centralized alerting (youtube_auth_failure, startup_failure, etc.)
- Added `send_alert()`, `send_youtube_auth_alert()`, `send_startup_alert()` functions
- Built-in spam prevention: checks for recent similar alerts before inserting (configurable cooldown)
- Alerts triggered on: YouTube auth failures, startup issues, cookie refresh errors
- Added `acknowledge_alert()` and `get_unacknowledged_alerts()` for alert management
- Documented in Supabase-Functions-Usage.md with Python usage and CURL examples
- Files: `app/services/supabase_service.py`, `app/services/ytdlp_service.py`, `scripts/cookie_scheduler.py`, `Supabase-Functions-Usage.md`
- Tags: #feature #alerts #monitoring #supabase

2026-01-04 | [FIX] | [YOUTUBE-AUTH] | Fixed Playwright sync/async conflict in RunPod workers
- Root cause: `sync_playwright()` cannot run inside asyncio event loops (FastAPI/RunPod context)
- Created `refresh_youtube_cookies_async.py` using `async_playwright` for async contexts
- Updated `cookie_scheduler.py` with `trigger_manual_refresh_async()` for async callers
- Added `is_running_in_async_context()` detection to auto-fallback to subprocess execution
- When sync `trigger_manual_refresh()` is called from async context, it now runs in subprocess
- Fixes: "Playwright Sync API inside asyncio loop" errors on RunPod workers
- Files: `scripts/refresh_youtube_cookies_async.py` (new), `scripts/cookie_scheduler.py`
- Tags: #fix #youtube-auth #playwright #async #runpod

2026-01-04 | [REFACTOR] | [TRANSCRIPTION] | Moved document_transcriptions creation to Supabase trigger
- Trigger now creates placeholder transcription record on document INSERT (source='pending')
- RunPod job_service.py now UPDATEs existing record instead of UPSERT
- Ensures transcription record exists even if RunPod processing fails
- Consolidated data creation in Supabase (single source of truth)
- Files: `supabase/migrations/20260114_trigger_creates_transcription.sql`, `app/services/job_service.py`, `docs/supabase-integration.md`
- Tags: #refactor #transcription #trigger #supabase

2026-01-04 | [FIX] | [EDGE-FUNCTION] | Fixed consume-video-audio-transcription Edge Function RPC call
- Edge Function was calling `pgmq_read` which is not exposed via PostgREST (500 errors)
- Changed to `dequeue_video_audio_transcription` wrapper function (works via PostgREST)
- Added better error handling, logging, and RunPod config validation
- Added "Automatic Transcription Pipeline" documentation section with architecture diagram
- Documents trigger → PGMQ queue → Edge Function → RunPod/FastAPI flow
- Files: `supabase/functions/consume-video-audio-transcription/index.ts`, `docs/supabase-integration.md`
- Tags: #fix #edge-function #pgmq #supabase #documentation

2026-01-03 | [FIX] | [TRANSCRIPTION] | VTT multi-line parsing fix + skip_subtitles behavior tests
- Fixed VTT parser to capture multi-line subtitle text (was only capturing first line)
- VTT parsing now accumulates text lines until next timestamp or empty line
- Added 5 new tests: multi-line VTT parsing + skip_subtitles conditional behavior
- Total test count: 25 passing tests for subtitle functionality
- Files: `app/services/job_service.py`, `tests/unit/test_job_service_subtitles.py`
- Tags: #fix #vtt #parsing #tests

2026-01-03 | [FEATURE] | [TRANSCRIPTION] | Subtitle-first approach with retry logic and skip_subtitles flag
- Job service now tries platform subtitles first (YouTube/Vimeo) before falling back to AI transcription
- Added `_retry_with_delay()` helper for network resilience (3 attempts, 3s delay)
- Added `_try_extract_platform_subtitles()` with retry for yt-dlp and subtitle download
- Added `_parse_subtitles_to_segments()` supporting json3, VTT, SRT formats with word-level timing
- Subtitle priority: manual subtitles > auto-captions > AI transcription
- Source tracking: `transcription_source` field now set to "subtitle" or "ai"
- Added optional `skip_subtitles` flag to job payload to force AI transcription when subtitles are inaccurate
- 20 unit tests covering parsing, retry logic, and skip_subtitles behavior
- Files: `app/services/job_service.py`, `app/routers/jobs.py`, `tests/unit/test_job_service_subtitles.py`, `docs/endpoints-index.md`
- Tags: #feature #transcription #subtitles #retry #yt-dlp #robustness

2026-01-02 | [FIX] | [SCREENSHOTS] | Robust timestamp parsing + Supabase bucket fix
- `parse_timestamp_to_seconds()` now handles dict, numeric, and string inputs (fixes RunPod `'dict' object has no attribute 'strip'` error)
- Fixed `resolve_media_placeholders()` SQL function: `public_media` bucket is PRIVATE (requires signed URLs), not public
- Updated documentation to clarify `is_public=false` for `public_media` bucket
- Files: `app/utils/timestamp_utils.py`, `supabase/migrations/20260112_fix_is_public_bucket_check.sql`, `Supabase-Functions-Usage.md`, `Frontend-Changes.md`
- Tags: #fix #screenshots #runpod #supabase #timestamp

2025-12-28 | [FEATURE] | [SCREENSHOTS] | Added segment_id tracking to screenshot extraction pipeline
- RunPod handler now accepts timestamp objects with `segment_id`, `reason`, and `text` fields
- Screenshot metadata now stores `segment_id`, `extraction_reason`, `segment_text`, `timestamp_seconds`
- Updated Supabase functions: `get_screenshots_for_review()`, `get_screenshot_candidates_for_segment()`, `get_approved_screenshots_for_document()` to use `segment_id` only
- Removed `segment_index` backwards compatibility - clean rollout using `segment_id` only
- Updated n8n workflow guide: AI Agent prompt now outputs `segment_id`, RunPod payload sends full timestamp objects
- Files: `app/services/screenshot_job_service.py`, `supabase/migrations/20260103_screenshot_functions_clean.sql`, `Guide-n8n-Workflow-GenerateScreenshots-VideoTranscription.md`, `Supabase-Functions-Usage.md`
- Tags: #feature #screenshots #segment_id #runpod #supabase

2025-12-25 | [FEATURE] | [TRANSCRIPTION] | Added segment_id to transcription segments with word-level timing support
- Added `segment_id` (1-based integer) to all transcription segment outputs for stable targeting
- Subtitles router now prefers YouTube json3 format for word-level timing data
- Added json3 parser that extracts word-level timestamps with `words` array
- WhisperX transcription now includes segment_id on all segments
- OpenAI transcription now requests word timestamps and preserves `words` array
- Job service includes fallback to ensure segment_id exists before Supabase save
- Created Supabase SQL functions: `get_segment_by_transcription_id()`, `get_segment_by_document_id()`
- Added 9 unit tests for segment_id functionality
- Files: `app/routers/subtitles.py`, `app/services/transcription_service.py`, `app/services/job_service.py`, `supabase/migrations/20251225_segment_retrieval_functions.sql`, `tests/unit/test_segment_id.py`
- Tags: #feature #transcription #segments #json3 #word-timing #supabase

2025-12-22 | [REFACTOR] | [HANDLER] | Modularized handler.py into reusable utilities and services
- Extracted logging setup into `app/utils/logging_utils.py` (setup_logger, get_job_logger)
- Extracted async helper into `app/utils/async_utils.py` (run_async for RunPod event loop handling)
- Moved check_video_cache to `app/services/cache_service.py` as check_video_cache_status()
- Reduced handler.py from 396 → 244 lines (-38%), now pure orchestration layer
- Added comprehensive Services & Utilities Index to docs/docs-home.md
- Files: `handler.py`, `app/utils/logging_utils.py`, `app/utils/async_utils.py`, `app/services/cache_service.py`, `docs/docs-home.md`
- Tags: #refactor #handler #modular #utilities #documentation

2025-12-18 | [FEATURE] | [RUNPOD] | Screenshot Jobs System for async batch screenshot extraction
- Added screenshot_job_service.py for processing screenshot extraction via RunPod
- Extended handler.py with queue routing: `screenshot_extraction` queue alongside existing `video_audio_transcription`
- Added `save_screenshot_with_job_metadata()` to supabase_service.py for job tracking
- Screenshots saved to Supabase with job metadata (job_id, storage_status, timestamps, worker)
- Job results can be queried directly from Supabase using `get_screenshots_by_job_id()`
- Added Supabase SQL migration with indexes and functions for job tracking
- Created cleanup-temp-screenshots Edge Function for TTL-based cleanup (48h default)
- Added input validation (max 100 timestamps, quality 1-31), file size validation, error handling
- Files: `app/services/screenshot_job_service.py`, `app/services/supabase_service.py`, `handler.py`, `supabase/migrations/20251218_screenshot_jobs.sql`, `supabase/functions/cleanup-temp-screenshots/index.ts`, `docs/endpoints-index.md`
- Tags: #feature #runpod #screenshots #supabase #jobs #async

2025-12-18 | [DOCS] | [OPS] | Added n8n Operations Guide with CURL examples
- Created Guide-n8n-Operations.md with comprehensive CURL and n8n workflow examples
- Covers screenshot extraction, transcription jobs, and all Supabase RPC functions
- Includes polling strategy, complete workflow diagram, and quick reference table
- Files: `Guide-n8n-Operations.md`
- Tags: #docs #n8n #operations #curl

2025-12-18 | [DEPLOY] | [SUPABASE] | Deployed cleanup-temp-screenshots Edge Function
- Deployed Edge Function to Supabase (v1) for automated temp screenshot cleanup
- SQL migration 20251218_screenshot_jobs.sql confirmed applied (Local & Remote)
- Functions deployed: `get_screenshots_by_job_id`, `confirm_screenshots`, `get_expired_temp_screenshots`
- Tags: #deploy #supabase #edge-function

2025-12-16 | [FIX] | [RUNPOD] | Fixed whisperX transcription Pipeline import error
- Removed pyannote.audio from Dockerfile (caused `from transformers import Pipeline` error)
- pyannote.audio uses old-style import incompatible with transformers>=4.36
- We don't use speaker diarization, so pyannote.audio not needed
- Keep transformers>=4.36.0 for whisperX alignment features
- Files: `Dockerfile`
- Tags: #fix #runpod #whisperx #dependencies

2025-12-16 | [FIX] | [RUNPOD] | Added YouTube cookies for authentication
- Exported authenticated YouTube cookies via Playwright
- Removed cookies.txt from .gitignore and .dockerignore for deployment
- Added startup/runtime logging for cookies file debugging
- Files: `cookies.txt`, `.gitignore`, `.dockerignore`, `handler.py`, `app/services/ytdlp_service.py`
- Tags: #fix #runpod #youtube #cookies #authentication

2025-12-16 | [FIX] | [RUNPOD] | Fixed async handler and yt-dlp binary architecture issues
- Fixed async handler: RunPod doesn't properly await async handlers (GitHub #387)
- Added run_async() helper for safe event loop handling in any context
- Added bin/ to .dockerignore to prevent macOS yt-dlp binary overwriting Linux binary
- Added E2E integration test: tests/integration/test_runpod_e2e.py
- Files: `handler.py`, `.dockerignore`, `tests/integration/test_runpod_e2e.py`
- Tags: #fix #runpod #async #docker #testing

2025-12-16 | [FEATURE] | [RUNPOD] | RunPod serverless handler for async transcription processing
- Added handler.py: Thin orchestration layer (~85 lines) that receives RunPod jobs
- Handler delegates to existing job_service.py process_job_batch() - zero code duplication
- Proper async handling with asyncio.run() and comprehensive error handling
- Updated Dockerfile CMD to run handler.py instead of uvicorn for serverless mode
- Added runpod>=1.6.0 to requirements.txt
- Architecture: Supabase Edge Function → RunPod /run → handler.py → job_service.py → Supabase DB
- Results saved directly to Supabase (no need to poll RunPod for results)
- Edge Function returns immediately (200 OK with runpod_job_id) - no timeout issues
- Files: `handler.py`, `Dockerfile`, `requirements.txt`, `docs/runpod-deployment.md`, `docs/supabase-edge-function-runpod.md`
- Tags: #feature #runpod #serverless #async #transcription

2025-12-15 | [FIX] | [JOBS] | Fixed job_service.py upsert to match document_transcriptions schema
- Removed non-existent columns from upsert: `full_text`, `word_count`, `segment_count`, `model`
- Updated metadata format: `model` → `"WhisperX-{size}"`, `provider` → from `PROVIDER_NAME` env var
- Added `word_count` and `segment_count` to metadata JSONB (not as columns)
- Added `PROVIDER_NAME` config setting (default: "yt-dlp-api") for customizable provider tagging
- Metadata now includes: model, provider, duration, processing_time, word_count, segment_count
- Files: `app/services/job_service.py`, `app/config.py`, `example.env`
- Tags: #fix #jobs #metadata #supabase

2025-12-15 | [FEATURE] | [JOBS] | Endpoint-based transcription job processing from Supabase Edge Functions
- Added POST /jobs/video-audio-transcription endpoint for receiving job batches from Supabase
- Replaces polling worker with push-based approach: Supabase Edge Function → Python endpoint
- New PY_API_TOKEN authentication for secure Edge Function → Python communication
- Job service processes batches: claim → extract audio → transcribe → save → ack
- Supports retry logic with max_retries and visibility timeout handling
- Idempotent processing with atomic pending→processing document claim
- Response includes summary (completed/retry/archived/deleted) and per-job results
- Added verify_job_token dependency for Bearer token authentication
- GET /jobs/status endpoint for health checks
- Legacy polling worker disabled by default (TRANSCRIPTION_WORKER_ENABLED=false)
- Files: `app/routers/jobs.py`, `app/services/job_service.py`, `app/dependencies.py`, `app/config.py`, `example.env`
- Tags: #feature #jobs #transcription #supabase #edge-functions #endpoint

2025-12-15 | [REFACTOR] | [ARCHITECTURE] | Modular architecture refactoring from monolithic main.py
- Refactored monolithic main.py (2,622 lines) into modular FastAPI structure (~100 lines entry point)
- Created app/ package with config, dependencies, models, routers, services, and utils submodules
- 8 router modules: download, subtitles, audio, transcription, playlist, screenshot, cache, admin
- 5 service modules: ytdlp_service, cache_service, supabase_service, transcription_service, screenshot_service
- 5 utility modules: filename_utils, timestamp_utils, subtitle_utils, language_utils, platform_utils
- Type-safe configuration using pydantic-settings with environment variable validation
- Added 79 pytest tests (38 unit, 41 integration) with 46% code coverage, 99% on utilities
- All 17 API endpoints preserved with identical functionality
- Files: `main.py`, `app/**/*.py`, `tests/**/*.py`, `docs/endpoints-index.md`
- Tags: #refactor #architecture #modular #testing #pydantic-settings

2025-12-15 | [FEATURE] | [WORKER] | Background transcription worker with PGMQ queue processing
- Added scripts/transcription_worker.py for automatic transcription of video/audio documents
- Polls Supabase PGMQ queue (video_audio_transcription) for pending jobs on server startup
- Parallel job processing with asyncio, respecting MAX_CONCURRENT_TRANSCRIPTIONS semaphore
- Job flow: dequeue → validate → claim document → extract audio → transcribe → save → ack
- Automatic retry with visibility timeout (VT_SECONDS), max retries before error state
- Progressive idle backoff to reduce database load when queue is empty
- Graceful shutdown with timeout for in-flight jobs
- GET /admin/transcription-worker/status endpoint for monitoring
- Configuration via environment variables: TRANSCRIPTION_WORKER_ENABLED, WORKER_POLL_INTERVAL, etc.
- Requires Supabase queue setup (dequeue_video_audio_transcription, pgmq_delete_one, pgmq_archive_one RPCs)
- Files: `scripts/transcription_worker.py`, `main.py:313-349,2427-2449`, `example.env`
- Tags: #feature #worker #transcription #pgmq #supabase #asyncio

2025-12-14 | [FEATURE] | [YOUTUBE] | Automated cookie refresh with Playwright
- Added scripts/refresh_youtube_cookies.py for automated YouTube login and cookie export
- Interactive mode (--interactive) for 2FA accounts, headless mode for automation
- Exports cookies in Netscape format compatible with yt-dlp
- Supports scheduled cron refresh for production deployments
- Navigates to robots.txt before export to prevent cookie rotation
- Environment: YOUTUBE_EMAIL, YOUTUBE_PASSWORD for credentials
- Requires: pip install playwright && playwright install chromium
- Files: `scripts/refresh_youtube_cookies.py`, `docs/Youtube-Cookies-Export.md`, `example.env`
- Tags: #feature #youtube #playwright #cookies #automation

2025-12-14 | [FIX] | [YOUTUBE] | Standalone yt-dlp binary with Deno for YouTube downloads
- Added standalone yt-dlp binary (2025.12.08) requiring Deno runtime for YouTube
- Automatic rate limiting with random delays (7-25s) to avoid YouTube bans
- Added is_youtube_url() and run_ytdlp_binary() helper functions
- YouTube-specific binary used for /screenshot/video and /extract-audio endpoints
- Non-YouTube platforms continue using Python yt-dlp library
- Cookie authentication support via YTDLP_COOKIES_FILE environment variable
- Environment: YTDLP_BINARY, YTDLP_MIN_SLEEP, YTDLP_MAX_SLEEP, YTDLP_SLEEP_REQUESTS
- Requires Deno 2.0.0+ installed: https://deno.com/
- Files: `main.py`, `example.env`, `bin/yt-dlp`
- Tags: #fix #youtube #deno #rate-limiting

2025-12-14 | [FEATURE] | [CACHE] | Unified cache system and screenshot extraction endpoint
- Added POST /screenshot/video endpoint for extracting frames at specified timestamps
- Added GET /cache and DELETE /cache/cleanup endpoints for cache management
- Unified cache system: ./cache/{videos,audio,transcriptions,screenshots}/ with TTL-based cleanup
- Video caching for reuse across screenshot requests (skip re-download)
- Optional Supabase upload for screenshots to public_media bucket
- Updated /extract-audio to use unified cache path (./cache/audio/)
- Files: `main.py`, `example.env`, `docs/endpoints-index.md`, `docs/endpoints-usage.md`
- Tags: #feature #cache #screenshots #supabase

2025-12-14 | [FEATURE] | [PERF] | GPU detection on server startup with model information
- Added automatic GPU detection at server startup (runs once, not per request)
- Detects NVIDIA CUDA GPUs with model name (e.g., "NVIDIA RTX 4090")
- Detects Apple Silicon (M1/M2/M3) with chip model using system info
- NOTE: Apple Silicon MPS support in whisperX is unstable (crashes with tensor broadcast errors)
- Automatic CPU fallback when MPS fails - confirmed working on M1/M2/M3 Macs
- Falls back to CPU if no GPU available with clear informative messages
- Global variables: WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_GPU_INFO
- Startup messages show detected hardware and compute configuration
- Eliminates per-request device detection overhead
- Files: `main.py:64-114,1453-1490`
- Tags: #feature #performance #gpu #device-detection #whisperx #apple-silicon

2025-11-08 | [FEATURE] | [SUPABASE] | Supabase integration for persistent transcription storage
- Added optional Supabase integration to store transcriptions in `document_transcriptions` table
- POST /transcriptions/save: UPSERT transcription data (requires existing document_id)
- GET /transcriptions/check/{document_id}: Check if transcription exists for a document
- Normalized schema: `documents` table (video metadata) + `document_transcriptions` table (segments, language, source)
- Server-to-server authentication via SUPABASE_SERVICE_KEY (bypasses RLS)
- Auto-updating timestamps via PostgreSQL trigger
- Supports foreign key constraints with CASCADE delete
- New dependencies: supabase-py (2.24.0)
- Environment variables: SUPABASE_URL, SUPABASE_SERVICE_KEY (optional)
- Documentation: docs/supabase-integration.md with complete setup, schema, and workflows
- Files: `main.py:19,60-84,631-645,1776-1892`, `.env`, `example.env`, `CLAUDE.md`, `docs/supabase-integration.md`
- Tags: #feature #supabase #database #storage #transcription

2025-11-08 | [BREAKING] | [API] | Unified transcription response format for database storage
- Standardized JSON response structure for /subtitles and /transcribe endpoints
- Timestamps return as float (seconds): 0.24 instead of "00:00:00,240"
- New fields: source, video_id, url, metadata (created_at, platform, transcription_time)
- video_id extracted via yt-dlp info.get('id') for all platforms, MD5 hash fallback for local files
- Enhanced /extract-audio to return metadata (video_id, url, duration, platform)
- /transcribe accepts optional metadata parameters from /extract-audio
- Utility functions: convert_srt_timestamp_to_seconds(), get_platform_from_url(), create_unified_transcription_response()
- Files: `main.py:255-371,837-897,1070-1110,1120-1389`, `CLAUDE.md`
- Tags: #breaking-change #api #database #transcription

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

2025-11-02 | [REFACTOR] | [API] | Improved transcription workflow and error handling
- Refactored to composable endpoints: /extract-audio and /transcribe
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
- Added POST /extract-audio endpoint to extract audio from video URLs or local files
- Added POST /transcribe endpoint with whisperX (local) and OpenAI providers
- Support for 99 languages with automatic detection using OpenAI Whisper
- Multiple output formats: JSON with timestamps, SRT, VTT, plain text
- Local transcription: $0 cost using whisperX (70x real-time on GPU, 3-5x on CPU)
- Cloud transcription: OpenAI Whisper API ($0.006/min) for managed service option
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