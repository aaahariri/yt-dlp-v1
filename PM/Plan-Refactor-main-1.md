# Plan: Refactor main.py into Modular Structure

## Overview
Refactor the monolithic `main.py` (2,622 lines, 26+ functions, 17+ endpoints) into a clean modular FastAPI structure.

**Execution Strategy:** 4-wave parallel execution using up to **10 agents** simultaneously.

**Estimated Time:**
- Sequential (1 agent): ~8-10 hours
- Parallel (10 agents): ~1.75 hours
- **Speedup: ~5x faster**

---

## Phase 1: Pre-Refactor Commit & Backup

### Task 1.1: Create Git Commit of Current State
```bash
git add -A
git commit -m "PRE: REFACTOR of main.py"
```

### Task 1.2: Create Backup
```bash
cp main.py main.py.backup
```

---

## Parallel Execution Strategy (4 Waves, 10 Agents)

### Dependency Graph
```
Wave 1: Foundation (MUST complete first)
├── config.py          → Required by: ALL modules
└── models/schemas.py  → Required by: routers, services

Wave 2: Core Infrastructure (depends on Wave 1)
├── dependencies.py    → Required by: routers
├── utils/*           → Required by: services, routers
└── services/*        → Required by: routers

Wave 3: API Layer (depends on Wave 2)
└── routers/*         → Required by: main.py

Wave 4: Integration (depends on Wave 3)
├── main.py refactor  → Wires everything together
└── Full test suite   → Validates everything works
```

### Wave 1: Foundation (2 Agents, ~20 min)
**MUST complete before any other work begins**

| Agent | Type | Files | Responsibilities |
|-------|------|-------|------------------|
| **Agent-1** | general-purpose | `app/__init__.py`, `app/config.py` | Extract all config, env vars, pydantic-settings |
| **Agent-2** | general-purpose | `app/models/__init__.py`, `app/models/schemas.py` | Extract all 8 Pydantic models |

**Deliverables:** Config centralized, all request/response models defined

---

### Wave 2: Core Infrastructure (7 Agents, ~30 min)
**Starts ONLY after Wave 1 commits**

| Agent | Type | Files | Dependencies |
|-------|------|-------|--------------|
| **Agent-3** | general-purpose | `app/dependencies.py` | config.py |
| **Agent-4** | general-purpose | `app/utils/filename_utils.py`, `app/utils/timestamp_utils.py` | config.py |
| **Agent-5** | general-purpose | `app/utils/subtitle_utils.py`, `app/utils/language_utils.py` | - |
| **Agent-6** | general-purpose | `app/utils/platform_utils.py` | - |
| **Agent-7** | **python-fastapi-architect** | `app/services/ytdlp_service.py` | config.py, utils/* |
| **Agent-8** | **python-fastapi-architect** | `app/services/cache_service.py`, `app/services/supabase_service.py` | config.py |
| **Agent-9** | **python-fastapi-architect** | `app/services/transcription_service.py`, `app/services/screenshot_service.py` | config.py, schemas |

**Deliverables:** All utils and services with proper patterns

---

### Wave 3: API Routers (8 Agents, ~35 min)
**Starts ONLY after Wave 2 commits**

| Agent | Type | Router File | Endpoints |
|-------|------|-------------|-----------|
| **Agent-1** | **python-fastapi-architect** | `app/routers/download.py` | `/download`, `/batch-download` |
| **Agent-2** | **python-fastapi-architect** | `app/routers/subtitles.py` | `/subtitles`, `/transcription/locales` |
| **Agent-3** | **python-fastapi-architect** | `app/routers/audio.py` | `/extract-audio` |
| **Agent-4** | **python-fastapi-architect** | `app/routers/transcription.py` | `/transcribe`, `/transcriptions/*` |
| **Agent-5** | **python-fastapi-architect** | `app/routers/playlist.py` | `/playlist/info` |
| **Agent-6** | **python-fastapi-architect** | `app/routers/screenshot.py` | `/screenshot/video` |
| **Agent-7** | **python-fastapi-architect** | `app/routers/cache.py` | `/cache/*`, `/downloads/list` |
| **Agent-8** | **python-fastapi-architect** | `app/routers/admin.py` | `/admin/*` |

**Deliverables:** All 17 endpoints migrated with proper typing and OpenAPI docs

---

### Wave 4: Integration (2 Agents, ~20 min)
**Starts ONLY after Wave 3 commits**

| Agent | Type | Responsibilities |
|-------|------|------------------|
| **Agent-1** | **python-fastapi-architect** | Rewrite `main.py`, update `scripts/transcription_worker.py` imports |
| **Agent-2** | general-purpose | Run full pytest suite, validate all endpoints, create test report |

**Deliverables:** Clean main.py, all tests passing, documentation updated

---

### Agent Type Usage Summary

| Agent Type | Count | Used In |
|------------|-------|---------|
| `general-purpose` | 8 | Foundation, utils, dependencies, testing |
| `python-fastapi-architect` | 12 | Services, routers, main.py integration |

---

## Phase 2: Create Directory Structure

### Task 2.1: Create New Directories
```
app/
├── __init__.py
├── config.py              # All configuration & env vars
├── dependencies.py        # Auth, shared FastAPI dependencies
├── models/
│   ├── __init__.py
│   └── schemas.py         # All Pydantic models
├── routers/
│   ├── __init__.py
│   ├── download.py        # /download, /batch-download
│   ├── subtitles.py       # /subtitles, /transcription/locales
│   ├── transcription.py   # /transcribe, /transcriptions/*
│   ├── playlist.py        # /playlist/info
│   ├── audio.py           # /extract-audio
│   ├── screenshot.py      # /screenshot/video
│   ├── cache.py           # /cache/*, /downloads/list
│   └── admin.py           # /admin/*
├── services/
│   ├── __init__.py
│   ├── ytdlp_service.py   # yt-dlp wrapper, binary runner, rate limiting
│   ├── supabase_service.py # Supabase client & operations
│   ├── cache_service.py   # Cache management
│   ├── transcription_service.py # WhisperX/OpenAI transcription
│   └── screenshot_service.py # FFmpeg screenshot extraction
└── utils/
    ├── __init__.py
    ├── filename_utils.py  # Filename sanitization, formatting
    ├── timestamp_utils.py # Timestamp parsing, conversion
    ├── subtitle_utils.py  # VTT/SRT parsing
    └── language_utils.py  # Language code mapping
```

---

## Phase 3: Extract Configuration (app/config.py)

### Task 3.1: Create config.py with all environment variables

**Extract from main.py:**
- Lines 24-70: All `os.getenv()` calls
- Lines 45-54: Directory setup (DOWNLOADS_DIR, CACHE_DIR)
- Lines 59-66: YTDLP configuration
- Lines 200-254: Whisper device detection

**Define missing constants:**
- `YTDLP_EXTRACTOR_ARGS = {}` (currently undefined but used 8 times)
- `TRANSCRIPTIONS_DIR` (currently undefined but referenced)

**Pattern:**
```python
# app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # CORS & Security
    allowed_origin: str = "http://localhost:3000"
    api_key: str

    # Storage
    downloads_dir: str = "./downloads"
    cache_dir: str = "./cache"
    cache_ttl_hours: int = 3

    # yt-dlp
    ytdlp_binary: str = "./bin/yt-dlp"
    ytdlp_cookies_file: str | None = None
    ytdlp_min_sleep: int = 7
    ytdlp_max_sleep: int = 25
    ytdlp_sleep_requests: float = 1.0
    ytdlp_extractor_args: dict = {}

    # Transcription
    max_concurrent_transcriptions: int = 2

    # Supabase (optional)
    supabase_url: str | None = None
    supabase_service_key: str | None = None

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

---

## Phase 4: Extract Pydantic Models (app/models/schemas.py)

### Task 4.1: Move all Pydantic classes

**Extract from main.py (lines 976-1048):**
| Class | Line | Purpose |
|-------|------|---------|
| `BatchDownloadRequest` | 976 | Batch download input |
| `VideoDownloadResult` | 985 | Single video result |
| `BatchDownloadResponse` | 996 | Batch response |
| `TranscriptionSaveRequest` | 1006 | Save transcription input |
| `TranscriptionSaveResponse` | 1015 | Save response |
| `ScreenshotRequest` | 1022 | Screenshot input |
| `ScreenshotResult` | 1030 | Single screenshot result |
| `ScreenshotResponse` | 1040 | Screenshot response |

---

## Phase 5: Extract Dependencies (app/dependencies.py)

### Task 5.1: Move authentication dependency

**Extract from main.py:**
- Lines 36-43: `verify_api_key()` function

```python
# app/dependencies.py
from fastapi import Header, HTTPException
from app.config import get_settings

def verify_api_key(x_api_key: str = Header(None)) -> bool:
    settings = get_settings()
    if not settings.api_key:
        raise HTTPException(status_code=500, detail="API key not configured")
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True
```

---

## Phase 6: Extract Services

### Task 6.1: Create ytdlp_service.py
**Extract from main.py:**
- Lines 69-70: `_last_youtube_request`, `_youtube_request_lock`
- Lines 75-85: `youtube_rate_limit()`
- Lines 87-177: `run_ytdlp_binary()`
- Lines 179-270: `is_youtube_url()`

### Task 6.2: Create supabase_service.py
**Extract from main.py:**
- Lines 257-269: `supabase_client` initialization
- Lines 272-282: `get_supabase_client()`
- Lines 284-304: `upload_screenshot_to_supabase()`
- Lines 306-311: `save_screenshot_metadata()`

### Task 6.3: Create cache_service.py
**Extract from main.py:**
- Lines 436-451: `get_cached_video()`
- Lines 453-476: `cleanup_cache()`
- Lines 389-406: `cleanup_old_transcriptions()`

### Task 6.4: Create transcription_service.py
**Extract from main.py:**
- Lines 200-254: Device detection (WHISPER_DEVICE, WHISPER_COMPUTE_TYPE)
- Lines 1637-1938: `_transcribe_audio_internal()`
- Lines 706-773: `create_unified_transcription_response()`

### Task 6.5: Create screenshot_service.py
**Extract from main.py:**
- Lines 478-515: `extract_screenshot()`

---

## Phase 7: Extract Utilities

### Task 7.1: Create filename_utils.py
**Extract from main.py:**
- Lines 775-790: `sanitize_filename()`
- Lines 792-816: `get_platform_prefix()`
- Lines 818-849: `format_title_for_filename()`
- Lines 851-858: `create_formatted_filename()`
- Lines 860-875: `encode_content_disposition_filename()`

### Task 7.2: Create timestamp_utils.py
**Extract from main.py:**
- Lines 408-426: `parse_timestamp_to_seconds()`
- Lines 428-434: `format_seconds_to_srt()`
- Lines 657-678: `convert_srt_timestamp_to_seconds()`

### Task 7.3: Create subtitle_utils.py
**Extract from main.py:**
- Lines 352-370: `parse_vtt_to_text()`
- Lines 372-387: `parse_srt_to_text()`

### Task 7.4: Create language_utils.py
**Extract from main.py:**
- Lines 523-641: `LANGUAGE_NAMES` dict
- Lines 643-655: `get_language_name()`

### Task 7.5: Create platform_utils.py
**Extract from main.py:**
- Lines 680-704: `get_platform_from_url()`
- Lines 517-521: `get_video_id_from_url()`

---

## Phase 8: Extract Routers

### Task 8.1: Create download.py router
**Endpoints:**
- `GET /download` (lines 877-970)
- `POST /batch-download` (lines 1050-1173)

### Task 8.2: Create subtitles.py router
**Endpoints:**
- `GET /subtitles` (lines 1174-1375)
- `GET /transcription/locales` (lines 1940-2038)

### Task 8.3: Create audio.py router
**Endpoints:**
- `POST /extract-audio` (lines 1376-1596)

### Task 8.4: Create transcription.py router
**Endpoints:**
- `POST /transcribe` (lines 1599-1634)
- `POST /transcriptions/save` (lines 2196-2263)
- `GET /transcriptions/check/{document_id}` (lines 2265-2312)

### Task 8.5: Create playlist.py router
**Endpoints:**
- `GET /playlist/info` (lines 2039-2175)

### Task 8.6: Create screenshot.py router
**Endpoints:**
- `POST /screenshot/video` (lines 2451-2615)

### Task 8.7: Create cache.py router
**Endpoints:**
- `DELETE /cache/cleanup` (lines 2314-2331)
- `GET /cache` (lines 2333-2378)
- `GET /downloads/list` (lines 2176-2194)

### Task 8.8: Create admin.py router
**Endpoints:**
- `POST /admin/refresh-cookies` (lines 2380-2408)
- `GET /admin/cookie-scheduler/status` (lines 2409-2426)
- `GET /admin/transcription-worker/status` (lines 2427-2450)

---

## Phase 9: Update main.py (Minimal App Entry Point)

### Task 9.1: Rewrite main.py as minimal entry point

```python
# main.py (NEW - ~50 lines)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.routers import (
    download, subtitles, audio, transcription,
    playlist, screenshot, cache, admin
)
from scripts.cookie_scheduler import start_scheduler, stop_scheduler
from scripts.transcription_worker import start_worker, stop_worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    await start_worker()
    yield
    # Shutdown
    await stop_worker()
    stop_scheduler()

app = FastAPI(lifespan=lifespan)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(download.router)
app.include_router(subtitles.router)
app.include_router(audio.router)
app.include_router(transcription.router)
app.include_router(playlist.router)
app.include_router(screenshot.router)
app.include_router(cache.router)
app.include_router(admin.router)

@app.get("/")
async def root():
    return {"message": "yt-dlp API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Phase 10: Update scripts/transcription_worker.py

### Task 10.1: Update imports to use new modules
The worker currently imports directly from `main.py`. Update to import from new modules:

**Current imports (to change):**
```python
from main import (
    _transcribe_audio_internal, run_ytdlp_binary, is_youtube_url,
    youtube_rate_limit, get_platform_from_url, CACHE_DIR, YTDLP_BINARY
)
```

**New imports:**
```python
from app.services.transcription_service import transcribe_audio_internal
from app.services.ytdlp_service import run_ytdlp_binary, is_youtube_url, youtube_rate_limit
from app.utils.platform_utils import get_platform_from_url
from app.config import get_settings
```

---

## Phase 11: Verification

### Task 11.1: Create verification checklist
Create a checklist mapping every function from original main.py to its new location.

### Task 11.2: Run static analysis
```bash
# Check for import errors
python -c "from app.config import get_settings; from app.routers import download"

# Check for syntax errors in all new files
python -m py_compile app/**/*.py
```

### Task 11.3: Verify no functions are missing
Compare function counts:
- Original main.py: 26 helper functions + 17 endpoints + 8 models
- New structure: Sum of all extracted functions

---

## Phase 12: Create Automated Pytest Suite

### Task 12.1: Add pytest dependencies
```bash
uv add pytest pytest-asyncio httpx pytest-cov pydantic-settings
```

### Task 12.2: Create test structure
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures (test client, API key, mock data)
├── unit/
│   ├── __init__.py
│   ├── test_config.py       # Test configuration loading
│   ├── test_filename_utils.py
│   ├── test_timestamp_utils.py
│   ├── test_language_utils.py
│   └── test_platform_utils.py
└── integration/
    ├── __init__.py
    ├── test_health.py       # Test / endpoint
    ├── test_download.py     # Test /download, /batch-download
    ├── test_subtitles.py    # Test /subtitles, /transcription/locales
    ├── test_audio.py        # Test /extract-audio
    ├── test_transcription.py # Test /transcribe, /transcriptions/*
    ├── test_playlist.py     # Test /playlist/info
    ├── test_screenshot.py   # Test /screenshot/video
    ├── test_cache.py        # Test /cache/*, /downloads/list
    └── test_admin.py        # Test /admin/*
```

### Task 12.3: Create conftest.py with fixtures
```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
import os

@pytest.fixture
def api_key():
    return os.getenv("API_KEY", "test-api-key")

@pytest.fixture
def client():
    from main import app
    return TestClient(app)

@pytest.fixture
async def async_client():
    from main import app
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def auth_headers(api_key):
    return {"X-API-Key": api_key}

@pytest.fixture
def sample_youtube_url():
    return "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Short, reliable test video
```

### Task 12.4: Write tests for ALL 17 endpoints

| # | Endpoint | Test File | Test Cases |
|---|----------|-----------|------------|
| 1 | `GET /` | test_health.py | Response 200, correct message |
| 2 | `GET /download` | test_download.py | Valid URL returns stream, invalid URL returns 400, missing API key returns 401 |
| 3 | `POST /batch-download` | test_download.py | Multiple URLs, rate limiting works, error handling |
| 4 | `GET /subtitles` | test_subtitles.py | Returns subtitles, format options (json/srt/vtt/text) |
| 5 | `POST /extract-audio` | test_audio.py | Returns audio path, caches correctly |
| 6 | `POST /transcribe` | test_transcription.py | Accepts audio file, returns segments |
| 7 | `GET /transcription/locales` | test_subtitles.py | Returns available languages |
| 8 | `GET /playlist/info` | test_playlist.py | Returns playlist metadata |
| 9 | `GET /downloads/list` | test_cache.py | Lists saved downloads |
| 10 | `POST /transcriptions/save` | test_transcription.py | Saves to Supabase (mock if not configured) |
| 11 | `GET /transcriptions/check/{id}` | test_transcription.py | Returns existence status |
| 12 | `DELETE /cache/cleanup` | test_cache.py | Cleans expired files |
| 13 | `GET /cache` | test_cache.py | Lists cached files by type |
| 14 | `POST /admin/refresh-cookies` | test_admin.py | Triggers refresh (mock actual refresh) |
| 15 | `GET /admin/cookie-scheduler/status` | test_admin.py | Returns scheduler status |
| 16 | `GET /admin/transcription-worker/status` | test_admin.py | Returns worker status |
| 17 | `POST /screenshot/video` | test_screenshot.py | Extracts frames at timestamps |

### Task 12.5: Run full test suite
```bash
# Run all tests with verbose output
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run only integration tests
pytest tests/integration/ -v

# Run only unit tests
pytest tests/unit/ -v
```

### Task 12.6: Document test results
Create test report with:
- Total tests: X passed, Y failed
- Coverage percentage per module
- Any failures with error details
- Performance metrics (response times)

---

## Files to Create (Summary)

### App Module Files
| File | Purpose | Lines (est.) |
|------|---------|--------------|
| `app/__init__.py` | Package init | 1 |
| `app/config.py` | Configuration (pydantic-settings) | 80 |
| `app/dependencies.py` | Auth deps | 20 |
| `app/models/__init__.py` | Package init | 1 |
| `app/models/schemas.py` | Pydantic models | 100 |
| `app/routers/__init__.py` | Package init | 1 |
| `app/routers/download.py` | Download endpoints | 200 |
| `app/routers/subtitles.py` | Subtitle endpoints | 250 |
| `app/routers/audio.py` | Audio endpoint | 150 |
| `app/routers/transcription.py` | Transcription endpoints | 150 |
| `app/routers/playlist.py` | Playlist endpoint | 150 |
| `app/routers/screenshot.py` | Screenshot endpoint | 200 |
| `app/routers/cache.py` | Cache endpoints | 100 |
| `app/routers/admin.py` | Admin endpoints | 80 |
| `app/services/__init__.py` | Package init | 1 |
| `app/services/ytdlp_service.py` | yt-dlp wrapper | 200 |
| `app/services/supabase_service.py` | Supabase client | 80 |
| `app/services/cache_service.py` | Cache manager | 100 |
| `app/services/transcription_service.py` | Transcription | 350 |
| `app/services/screenshot_service.py` | Screenshot | 60 |
| `app/utils/__init__.py` | Package init | 1 |
| `app/utils/filename_utils.py` | Filename helpers | 120 |
| `app/utils/timestamp_utils.py` | Timestamp helpers | 60 |
| `app/utils/subtitle_utils.py` | Subtitle parsers (keep unused for future) | 50 |
| `app/utils/language_utils.py` | Language mapping | 150 |
| `app/utils/platform_utils.py` | Platform detection (keep is_youtube_url for future) | 80 |
| `main.py` (rewritten) | App entry point | 50 |

### Test Files
| File | Purpose | Lines (est.) |
|------|---------|--------------|
| `tests/__init__.py` | Package init | 1 |
| `tests/conftest.py` | Shared fixtures | 50 |
| `tests/unit/__init__.py` | Package init | 1 |
| `tests/unit/test_config.py` | Config tests | 30 |
| `tests/unit/test_filename_utils.py` | Filename tests | 50 |
| `tests/unit/test_timestamp_utils.py` | Timestamp tests | 40 |
| `tests/unit/test_language_utils.py` | Language tests | 30 |
| `tests/unit/test_platform_utils.py` | Platform tests | 40 |
| `tests/integration/__init__.py` | Package init | 1 |
| `tests/integration/test_health.py` | Health endpoint | 20 |
| `tests/integration/test_download.py` | Download endpoints | 80 |
| `tests/integration/test_subtitles.py` | Subtitle endpoints | 60 |
| `tests/integration/test_audio.py` | Audio endpoint | 50 |
| `tests/integration/test_transcription.py` | Transcription endpoints | 80 |
| `tests/integration/test_playlist.py` | Playlist endpoint | 50 |
| `tests/integration/test_screenshot.py` | Screenshot endpoint | 60 |
| `tests/integration/test_cache.py` | Cache endpoints | 60 |
| `tests/integration/test_admin.py` | Admin endpoints | 50 |

### Dependencies to Add
```bash
uv add pydantic-settings pytest pytest-asyncio httpx pytest-cov
```

**Total: 45 files**
- App module: 27 files (~2,800 lines)
- Test suite: 18 files (~750 lines)
- Original: 1 file (2,622 lines)

---

## Critical Bug Fixes During Refactor

1. **Define `YTDLP_EXTRACTOR_ARGS`** - Currently undefined, used 8 times
2. **Define `TRANSCRIPTIONS_DIR`** - Currently undefined, used 3 times
3. **Keep unused functions for future use** (user decision):
   - `parse_vtt_to_text()` → `app/utils/subtitle_utils.py`
   - `parse_srt_to_text()` → `app/utils/subtitle_utils.py`
   - `cleanup_old_transcriptions()` → `app/services/cache_service.py`
   - `is_youtube_url()` → `app/utils/platform_utils.py`

---

## Success Criteria

1. **All 17 endpoints respond correctly** via pytest integration tests
2. **No import errors** - `python -c "from app.config import get_settings"` works
3. **No undefined variable errors** - `YTDLP_EXTRACTOR_ARGS` and `TRANSCRIPTIONS_DIR` defined
4. **`scripts/transcription_worker.py` works** with new module imports
5. **Cookie scheduler starts/stops correctly** - verified via admin endpoints
6. **Transcription worker starts/stops correctly** - verified via admin endpoints
7. **All functions accounted for** - verification checklist completed
8. **Pytest suite passes** - `pytest -v` shows all tests green
9. **Coverage report** - `pytest --cov=app` shows reasonable coverage

---

## Execution Order (Parallel Wave Summary)

### Pre-Flight
| Step | Command | Description |
|------|---------|-------------|
| 0.1 | `git add -A && git commit -m "PRE: REFACTOR of main.py"` | Commit current state |
| 0.2 | `cp main.py main.py.backup` | Create backup |
| 0.3 | `mkdir -p app/{models,routers,services,utils}` | Create directory structure |
| 0.4 | `uv add pydantic-settings pytest pytest-asyncio httpx pytest-cov` | Add dependencies |

### Wave Execution Timeline (~105 minutes total)

| Wave | Agents | Duration | Files Created | Agent Types |
|------|--------|----------|---------------|-------------|
| **Wave 1** | 2 | ~20 min | `config.py`, `schemas.py` | general-purpose |
| **Wave 2** | 7 | ~30 min | `dependencies.py`, 5 utils, 5 services | general-purpose + python-fastapi-architect |
| **Wave 3** | 8 | ~35 min | 8 routers | python-fastapi-architect |
| **Wave 4** | 2 | ~20 min | `main.py` rewrite, full test suite | python-fastapi-architect + general-purpose |

### Parallelization Metrics

| Metric | Value |
|--------|-------|
| Total Agents Used | 10 (max per wave) |
| Total Files Created | 45 |
| Sequential Estimate | 8-10 hours |
| Parallel Estimate | ~1.75 hours |
| **Speedup Factor** | **~5x** |

### Wave Completion Checklist (Run After Each Wave)
```bash
# After each wave, verify:
python -c "from app.config import get_settings"  # Wave 1+
python -m py_compile app/**/*.py                  # All waves
pytest tests/ -v                                   # Wave 4
```
