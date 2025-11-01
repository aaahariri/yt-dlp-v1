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