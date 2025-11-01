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

2025-11-01 | [FEATURE] | [API] | Enhanced filename formatting with platform prefixes and consistent naming
→ Added intelligent title formatting that removes channel names, applies platform prefixes (YT, TT, IG, etc.), and ensures consistent truncation at 50 characters for clean, predictable filenames
→ **WHAT**:
  - New utility functions: `get_platform_prefix()`, `format_title_for_filename()`, `create_formatted_filename()`
  - Automatic removal of channel name suffixes (text after | or -)
  - Platform-specific prefixes: YouTube→YT, TikTok→TT, Instagram→IG, Facebook→FB, Twitter→X, Vimeo→VM
  - Title truncation at 50 chars with intelligent word boundary detection
  - Spaces replaced with hyphens for filesystem compatibility
→ **WHY**:
  - Eliminate filename inconsistencies (e.g., "Inter-Equity" vs "Inter-Equity-Trading")
  - Improve file organization and searchability
  - Ensure cross-platform compatibility
  - Make filenames predictable and readable
→ **IMPACT**:
  - Filename format: `{PLATFORM}-{formatted-title}.{ext}` (e.g., `YT-Liquidity-Inducement-Masterclass-Ep.-1.mp4`)
  - All existing files renamed for consistency
  - Batch download script updated with same formatting logic
  - API endpoint accepts optional `custom_title` parameter for user-defined names
- Files: `main.py`, `batch_download.py`
- Tags: #feature #api #filenames #formatting #consistency

2025-11-01 | [FEATURE] | [API] | Added custom_title parameter to /download endpoint
→ Allows users to specify custom filenames while maintaining platform prefix and formatting rules
→ **WHAT**: New optional query parameter `custom_title` in `/download` endpoint
→ **WHY**: Give users control over downloaded filenames when original titles are too long or unclear
→ **IMPACT**: `GET /download?url=<url>&custom_title=My Custom Name` → saves as `YT-My-Custom-Name.mp4`
- Files: `main.py`
- Tags: #feature #api #customization

2025-11-01 | [FEATURE] | [TOOLING] | Created batch download script with anti-rate-limiting
→ Python script to download multiple YouTube videos with random 20-30 second pauses between downloads to avoid YouTube rate limiting
→ **WHAT**:
  - `batch_download.py` - Batch downloader with progress tracking
  - Random pauses (20-30s) between downloads
  - Skip already downloaded files
  - Beautiful console output with progress indicators
  - Error handling and retry logic
→ **WHY**: Enable efficient bulk downloading while respecting YouTube's rate limits
→ **IMPACT**: Can safely download 20+ videos in one session without triggering blocks
- Files: `batch_download.py`
- Tags: #feature #tooling #automation #rate-limiting

2025-11-01 | [DOCS] | [SCRIPTS] | Comprehensive local scripts documentation
→ Created detailed documentation for batch_download.py and local utility scripts
→ **WHAT**:
  - New docs/local-scripts.md file with complete usage guide
  - Platform support clarification (YouTube default, adaptable for 1000+ platforms)
  - File format handling explanation (MP4 default, supports many formats via yt-dlp)
  - URL list management instructions
  - Customization examples for TikTok, Instagram, Twitter, etc.
  - Troubleshooting section
  - Best practices and performance tips
→ **WHY**:
  - Users unclear about platform support (YouTube-only vs multi-platform)
  - File format handling needed explanation
  - URL list location not obvious (hardcoded in script)
  - Adaptation for other platforms required documentation
→ **IMPACT**:
  - Clear understanding of script capabilities and limitations
  - Easy customization for other platforms
  - Reduced support questions
  - Better user experience for batch downloading
- Files: `docs/local-scripts.md`
- Tags: #docs #scripts #batch-download #multi-platform