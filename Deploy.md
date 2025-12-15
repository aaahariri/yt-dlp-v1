# Deployment Guide

## YouTube Cookie Authentication Setup

### Files Required
Upload these files to your server:
- `cookies.txt` - Netscape format cookies for yt-dlp
- `cookies_state.json` - Playwright browser state for automated refresh

### First Server Deploy

1. **Generate cookies locally first** (on your machine with a browser):
   ```bash
   python scripts/refresh_youtube_cookies.py --interactive
   ```
2. **Upload cookie files** to server root directory:
   - `cookies.txt`
   - `cookies_state.json`
3. **Test on server**:
   ```bash
   ./bin/yt-dlp --cookies ./cookies.txt --print title "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
   ```
4. **If cookies work** - you're good, the scheduler will auto-refresh every 5 days

### If Authentication Fails on Server

Since external servers are headless (no browser), you must refresh cookies **locally** then re-upload:

1. **On your local machine** (with browser):
   ```bash
   cd your-project
   python scripts/refresh_youtube_cookies.py --interactive
   # Complete any Google security challenges in the browser
   # Press Enter when logged in
   ```

2. **Upload refreshed files to server**:
   ```bash
   scp cookies.txt cookies_state.json user@server:/path/to/project/
   # Or use your deployment method (git, Railway CLI, etc.)
   ```

3. **Verify on server**:
   ```bash
   ./bin/yt-dlp --cookies ./cookies.txt --print title "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
   ```

### Environment Variables

```env
# YouTube credentials for automated refresh
YOUTUBE_EMAIL=your-throwaway@gmail.com
YOUTUBE_PASSWORD=your-password

# Cookie refresh interval (days)
YTDLP_COOKIE_REFRESH_DAYS=5

# Cookie file path
YTDLP_COOKIES_FILE=./cookies.txt
```

### Server Requirements

```bash
# Install Playwright and Chromium browser
pip install playwright
playwright install chromium
```

### How Auto-Refresh Works

| Event | Action |
|-------|--------|
| Server starts | Checks if cookies missing/expired, refreshes if needed |
| Every 5 days | Scheduled refresh using saved browser state |
| Auth failure | Console warning displayed, manual intervention required |

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "Security challenge detected" | Run `--interactive` mode once from server |
| Cookies not working | Check file permissions: `chmod 600 cookies.txt` |
| Playwright not found | Run `pip install playwright && playwright install chromium` |
