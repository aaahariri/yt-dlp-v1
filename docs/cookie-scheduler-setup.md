# YouTube Cookie Scheduler Setup Guide

This guide explains the automated YouTube cookie refresh system that prevents authentication failures and improves YouTube download reliability.

## Overview

The FastAPI application now includes an automated cookie refresh scheduler that:

1. **Automatically refreshes cookies** every 5 days (configurable)
2. **Detects authentication failures** in YouTube downloads and triggers immediate refresh
3. **Provides admin endpoints** for manual control and monitoring
4. **Logs all operations** for troubleshooting

## Architecture

### Components

1. **scripts/cookie_scheduler.py**: Background scheduler module using APScheduler
2. **main.py**: Integration with FastAPI lifecycle (startup/shutdown hooks)
3. **Admin Endpoints**: Manual trigger and status monitoring
4. **Auto-Retry Logic**: Automatic cookie refresh on auth failures

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                  Application Startup                        │
│  - Loads environment variables                              │
│  - Starts APScheduler background thread                     │
│  - Schedules refresh every N days                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Scheduled Cookie Refresh (Every 5 days)        │
│  1. Check YOUTUBE_EMAIL and YOUTUBE_PASSWORD                │
│  2. Launch headless browser (Playwright)                    │
│  3. Automate YouTube login                                  │
│  4. Extract cookies in Netscape format                      │
│  5. Save to YTDLP_COOKIES_FILE                              │
│  6. Log success/failure                                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           On YouTube Download Request                       │
│  1. run_ytdlp_binary() executes yt-dlp                      │
│  2. If auth failure detected in stderr:                     │
│     - Log warning with error details                        │
│     - Trigger immediate cookie refresh                      │
│     - Retry download once with fresh cookies                │
│  3. Return result to client                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Manual Admin Operations (Optional)             │
│  POST /admin/refresh-cookies - Force immediate refresh      │
│  GET /admin/cookie-scheduler/status - Check scheduler state │
└─────────────────────────────────────────────────────────────┘
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Install APScheduler (already added to requirements.txt)
pip install apscheduler>=3.10.4

# Install Playwright for browser automation
pip install playwright
playwright install chromium
```

### 2. Configure Environment Variables

Add to your `.env` file:

```env
# YouTube account for cookie refresh (use throwaway account!)
YOUTUBE_EMAIL=your-throwaway-account@gmail.com
YOUTUBE_PASSWORD=your-password-here

# Cookie refresh interval (default: 5 days)
YTDLP_COOKIE_REFRESH_DAYS=5

# Path to cookies file (must match your yt-dlp config)
YTDLP_COOKIES_FILE=./cookies.txt
```

**Important Security Notes**:
- Use a throwaway Google account (ban risk exists)
- Never commit `.env` or `cookies.txt` to git
- Disable 2FA on the throwaway account (or use interactive mode manually)

### 3. Verify Setup

Start the FastAPI application:

```bash
uvicorn main:app --reload
```

Check logs for scheduler startup messages:

```
INFO: Starting application...
============================================================
YouTube Cookie Refresh Scheduler Starting
============================================================
Refresh interval: Every 5 days
Email configured: True
Password configured: True
Cookies file: ./cookies.txt
✓ Credentials configured - scheduled refreshes enabled
✓ Scheduler started successfully
Next scheduled refresh: 2025-12-20 10:30:00 UTC
============================================================
```

### 4. Test Manual Refresh

```bash
# Trigger manual cookie refresh
curl -X POST http://localhost:8000/admin/refresh-cookies \
  -H "X-Api-Key: your-api-key"

# Check scheduler status
curl -X GET http://localhost:8000/admin/cookie-scheduler/status \
  -H "X-Api-Key: your-api-key"
```

## Configuration Options

### Refresh Interval

Control how often cookies are refreshed (default: 5 days):

```env
YTDLP_COOKIE_REFRESH_DAYS=5    # Recommended: 3-7 days
```

**Guidelines**:
- Too frequent (< 3 days): Higher risk of Google detecting automation
- Too infrequent (> 7 days): Higher risk of cookies expiring
- Recommended: 5 days balances refresh frequency and detection risk

### Headless vs Interactive Mode

**Scheduled refreshes** always run in headless mode (no browser window).

For **manual testing** or **2FA-enabled accounts**, run the script interactively:

```bash
# Interactive mode (shows browser, allows manual 2FA)
python scripts/refresh_youtube_cookies.py --interactive
```

## Monitoring & Troubleshooting

### Check Scheduler Status

```bash
curl http://localhost:8000/admin/cookie-scheduler/status \
  -H "X-Api-Key: your-api-key"
```

Response:
```json
{
  "running": true,
  "refresh_interval_days": 5,
  "next_run_time": "2025-12-20T10:30:00",
  "last_refresh_time": "2025-12-15T10:30:00",
  "last_refresh_status": "success",
  "credentials_configured": true,
  "cookies_file": "./cookies.txt",
  "cookies_file_exists": true
}
```

### Common Issues

#### 1. Scheduler Not Starting

**Symptoms**: No scheduler logs on startup

**Causes**:
- APScheduler not installed
- Import error in scripts/cookie_scheduler.py

**Solution**:
```bash
pip install apscheduler
python3 -m py_compile scripts/cookie_scheduler.py  # Check syntax
```

#### 2. Cookie Refresh Fails

**Symptoms**: `last_refresh_status: "failed_refresh_error"`

**Causes**:
- 2FA enabled on account
- Incorrect credentials
- Playwright/Chromium not installed
- Google security challenge

**Solutions**:
```bash
# Verify Playwright installation
playwright install chromium

# Test manually with interactive mode
python scripts/refresh_youtube_cookies.py --interactive

# Check credentials in .env
echo $YOUTUBE_EMAIL
echo $YOUTUBE_PASSWORD
```

#### 3. Auth Failures Not Triggering Refresh

**Symptoms**: Downloads fail but no cookie refresh attempted

**Causes**:
- Auth failure pattern not detected
- retry_on_auth_failure=False in code

**Solution**:
Check main.py logs for pattern detection. The function detects:
- "Sign in to confirm you're not a bot"
- "This video requires authentication"
- "HTTP Error 403"
- "Video unavailable"
- "Private video"
- "age.restricted"
- "members.only"

Add custom patterns if needed in `run_ytdlp_binary()`.

### Log Files

All refresh operations are logged to stdout/stderr:

```
# View recent logs
tail -f logs/app.log  # If using file logging

# Or check systemd/docker logs
journalctl -u fastapi-app -f
docker logs -f container-name
```

## Manual Operations

### Trigger Immediate Refresh

Useful when:
- Testing setup
- Proactive refresh before scheduled time
- Recovering from auth failures

```bash
POST /admin/refresh-cookies
X-Api-Key: your-api-key
```

Response on success:
```json
{
  "success": true,
  "message": "Cookies refreshed successfully",
  "cookies_file": "./cookies.txt",
  "timestamp": "2025-12-15T15:30:00"
}
```

Response on failure:
```json
{
  "success": false,
  "error": "Cookie refresh failed. Check server logs for details.",
  "timestamp": "2025-12-15T15:30:00"
}
```

### Check Status

```bash
GET /admin/cookie-scheduler/status
X-Api-Key: your-api-key
```

## Security Considerations

### Account Safety

- **Use throwaway account**: Never use your personal Google account
- **Expect bans**: Google may ban the account for automation
- **Disable 2FA**: Required for headless automation (or use interactive mode)
- **App Passwords**: May not work (Google deprecated for most apps)

### Credential Storage

- **Never commit** `.env` or `cookies.txt` to git
- Add to `.gitignore`:
  ```gitignore
  .env
  cookies.txt
  cookies_state.json
  ```
- **Restrict permissions**:
  ```bash
  chmod 600 .env cookies.txt
  ```

### API Key Protection

Admin endpoints require API key authentication:

```env
API_KEY=your-secure-random-key-here
```

Generate secure key:
```bash
openssl rand -hex 32
```

## Production Deployment

### Railway / Cloud Platforms

1. **Set environment variables** in platform dashboard:
   - `YOUTUBE_EMAIL`
   - `YOUTUBE_PASSWORD`
   - `YTDLP_COOKIE_REFRESH_DAYS`
   - `YTDLP_COOKIES_FILE`

2. **Install Playwright** in Dockerfile:
   ```dockerfile
   RUN pip install playwright
   RUN playwright install chromium --with-deps
   ```

3. **Verify scheduler** in application logs after deployment

### Systemd Service

For self-hosted deployments, ensure scheduler persists:

```ini
[Unit]
Description=FastAPI Video Downloader
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/video-downloader
Environment="PATH=/opt/video-downloader/.venv/bin"
ExecStart=/opt/video-downloader/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Scheduler will auto-start with the application and persist across restarts.

## Advanced Configuration

### Custom Refresh Logic

To customize the refresh behavior, edit `scripts/cookie_scheduler.py`:

```python
# Change refresh interval dynamically
def scheduled_cookie_refresh():
    # Check if last refresh was successful
    # If failures increase, reduce interval
    if failure_count > 3:
        _refresh_interval_days = 2  # More frequent
```

### Alternative Cookie Sources

If automated refresh fails, manually export cookies:

1. Install browser extension: "Get cookies.txt LOCALLY"
2. Navigate to youtube.com while logged in
3. Export cookies to `cookies.txt`
4. Place in project root (or path from `YTDLP_COOKIES_FILE`)

## Testing

### End-to-End Test

1. **Start application** with valid credentials
2. **Wait for scheduler** to initialize
3. **Trigger manual refresh**:
   ```bash
   curl -X POST http://localhost:8000/admin/refresh-cookies \
     -H "X-Api-Key: your-api-key"
   ```
4. **Verify cookies.txt** was created/updated
5. **Test YouTube download** with fresh cookies

### Simulate Auth Failure

1. **Delete cookies.txt**
2. **Attempt YouTube download** (will fail)
3. **Check logs** for auto-refresh trigger
4. **Verify retry** with fresh cookies

## Migration from Manual Cookie Export

If currently using manual cookie export:

1. **Keep existing workflow** as backup
2. **Set up scheduler** with throwaway account
3. **Monitor logs** for first few cycles
4. **Transition fully** once reliable

## Related Documentation

- [refresh_youtube_cookies.py](../scripts/refresh_youtube_cookies.py): Standalone cookie refresh script
- [endpoints-index.md](endpoints-index.md): API endpoint reference
- [CLAUDE.md](../CLAUDE.md): Project overview

## Support

For issues:
1. Check logs for detailed error messages
2. Test manual refresh with `--interactive` flag
3. Verify Playwright installation: `playwright install chromium`
4. Review Google account security settings (disable 2FA)
5. Consider using manual cookie export as fallback

---

**Last Updated**: 2025-12-15
**Version**: 1.0.0
