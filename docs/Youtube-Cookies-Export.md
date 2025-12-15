# YouTube Cookies Export Guide

This guide explains how to export YouTube cookies for use with yt-dlp on external servers where you can't use `--cookies-from-browser`.

## Why Cookies Are Needed

- YouTube increasingly requires authentication for downloads
- OAuth no longer works with yt-dlp (blocked by YouTube)
- Cookies are the only reliable authentication method
- Required for: age-restricted content, some regions, higher rate limits

## Quick Start (Server Deployment)

1. **Export cookies** from your desktop browser (incognito window)
2. **Transfer** `cookies.txt` to your server
3. **Set** `YTDLP_COOKIES_FILE=/path/to/cookies.txt` in `.env`
4. **Refresh** cookies periodically (expire ~weekly)
5. **Consider** using a throwaway account (ban risk)

---

## Step-by-Step Export Instructions

### Step 1: Install Browser Extension

Install **"Get cookies.txt LOCALLY"** extension:
- [Chrome/Edge](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
- [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

> **Important**: Use "Get cookies.txt LOCALLY" - it exports cookies without sending them to external servers.

### Step 2: Open Incognito/Private Window

1. Open a **new private/incognito window** in your browser
2. This prevents cookie rotation that happens on regular tabs

### Step 3: Log Into YouTube

1. Go to [youtube.com](https://www.youtube.com)
2. Sign in with your account (or throwaway account)
3. Accept any consent dialogs

### Step 4: Navigate to robots.txt

**Critical step** - this prevents YouTube from rotating your cookies:

1. In the same tab, go to: `https://www.youtube.com/robots.txt`
2. You should see a plain text file with crawling rules

### Step 5: Export Cookies

1. Click the cookie extension icon
2. Select "Export" or "Get cookies.txt"
3. Save the file as `cookies.txt`
4. **Close the incognito window immediately** (don't browse further)

### Step 6: Transfer to Server

```bash
# Using SCP
scp cookies.txt user@server:/path/to/yt-dlp-v1/cookies.txt

# Using rsync
rsync -av cookies.txt user@server:/path/to/yt-dlp-v1/
```

### Step 7: Configure Environment

Add to your `.env` file:

```env
YTDLP_COOKIES_FILE=./cookies.txt
```

Or set absolute path:

```env
YTDLP_COOKIES_FILE=/path/to/yt-dlp-v1/cookies.txt
```

---

## Cookie Expiration & Refresh

### How Long Do Cookies Last?

- **Guest cookies**: ~24 hours
- **Logged-in cookies**: ~1-2 weeks
- **After heavy use**: May expire faster due to rate limiting

### When to Refresh

Refresh cookies when you see errors like:
- "Sign in to confirm you're not a bot"
- "This video requires authentication"
- "HTTP Error 403: Forbidden" (after working previously)

### Automated Refresh (Advanced)

For production deployments, consider:

1. **Scheduled refresh**: Export new cookies weekly via cron job on a desktop machine
2. **Health check endpoint**: Monitor for auth errors and alert when refresh needed
3. **Multiple accounts**: Rotate between accounts to reduce ban risk

---

## Automated Cookie Refresh with Playwright

This project includes a Playwright-based script that can automatically log into YouTube and export cookies. This eliminates the need for manual browser extension exports.

### Prerequisites

1. **Install Playwright**:
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **Create throwaway Google account**:
   - Use a fresh Gmail account (not your personal one)
   - **Disable 2FA** for fully automated mode, OR use interactive mode for 2FA

3. **Set credentials** in `.env`:
   ```env
   YOUTUBE_EMAIL=throwaway@gmail.com
   YOUTUBE_PASSWORD=your-password
   YTDLP_COOKIES_FILE=./cookies.txt
   ```

### Usage

#### Interactive Mode (Recommended First Time)

Shows the browser window so you can handle 2FA, captchas, or security prompts:

```bash
python scripts/refresh_youtube_cookies.py --interactive
```

The script will:
1. Open a Chromium browser window
2. Navigate to YouTube login
3. Enter your credentials
4. **Pause** for you to complete 2FA if needed
5. Export cookies after you press Enter

#### Headless Mode (For Automation)

Runs without GUI - requires account with 2FA disabled:

```bash
python scripts/refresh_youtube_cookies.py
```

Or with explicit credentials:

```bash
python scripts/refresh_youtube_cookies.py \
    --email throwaway@gmail.com \
    --password your-password \
    --output ./cookies.txt
```

### Automated Scheduled Refresh (Cron)

Set up a weekly cron job to keep cookies fresh:

```bash
# Edit crontab
crontab -e

# Add this line (runs every Sunday at 3 AM)
0 3 * * 0 cd /path/to/yt-dlp-v1 && /path/to/python scripts/refresh_youtube_cookies.py >> /var/log/youtube-cookies.log 2>&1
```

**Important for cron**:
- Account must have 2FA disabled
- Use absolute paths
- Ensure `YOUTUBE_EMAIL` and `YOUTUBE_PASSWORD` are set in environment

### Script Options

| Option | Short | Description |
|--------|-------|-------------|
| `--interactive` | `-i` | Show browser window (required for 2FA) |
| `--email` | `-e` | Google account email |
| `--password` | `-p` | Google account password |
| `--output` | `-o` | Output path for cookies.txt |
| `--timeout` | `-t` | Login timeout in seconds (default: 300) |

### How It Works

1. **Launches Chromium** with anti-detection settings
2. **Navigates to YouTube** and initiates login flow
3. **Enters credentials** automatically
4. **Waits for login** (manual intervention in interactive mode)
5. **Visits robots.txt** to stabilize cookies (prevents rotation)
6. **Exports cookies** in Netscape format for yt-dlp
7. **Saves browser state** for potential session reuse

### Handling 2FA Accounts

If your throwaway account has 2FA enabled:

1. **Option A**: Use `--interactive` mode
   ```bash
   python scripts/refresh_youtube_cookies.py --interactive
   # Complete 2FA in the browser, then press Enter
   ```

2. **Option B**: Disable 2FA on throwaway account
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Turn off 2-Step Verification
   - This allows fully automated headless operation

3. **Option C**: Use App Password (if 2FA required)
   - Generate App Password in Google Account settings
   - Use the 16-character app password instead of regular password

### Troubleshooting Playwright

#### "Playwright not installed"

```bash
pip install playwright
playwright install chromium
```

#### "Browser executable not found"

```bash
playwright install chromium --with-deps
```

#### "Login failed" in headless mode

- Account may have triggered security check
- Run with `--interactive` to see what's happening
- Try from same IP where account was created

#### Cookies export but don't work

- Ensure you're logged in fully before script exports
- Check that robots.txt page loaded successfully
- Verify cookies.txt contains YouTube domain cookies

### Server Deployment Architecture

For production servers without desktop access:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Desktop/CI     │     │   File Storage  │     │  API Server     │
│  Machine        │────▶│   (S3/GCS/etc)  │────▶│  (yt-dlp-v1)    │
│                 │     │                 │     │                 │
│  Runs Playwright│     │  cookies.txt    │     │  Reads cookies  │
│  weekly cron    │     │                 │     │  for YouTube    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. **Desktop/CI machine** runs Playwright script weekly
2. **Uploads cookies.txt** to shared storage or directly to server
3. **API server** reads fresh cookies for authenticated requests

---

## Security & Ban Risks

### Account Ban Risks

> **Warning**: Using your account with yt-dlp risks temporary or permanent bans.

**Risk factors**:
- High download volume (>300 videos/hour guest, >2000/hour authenticated)
- Rapid consecutive requests (no delays)
- Downloading restricted content
- Using datacenter IP addresses

### Mitigation Strategies

1. **Use throwaway account** - Don't use your main Google account
2. **Enable rate limiting** - Configure delays in `.env`:
   ```env
   YTDLP_MIN_SLEEP=7
   YTDLP_MAX_SLEEP=25
   ```
3. **Use residential proxies** - Datacenter IPs are often blocked
4. **Monitor for warnings** - Stop if you see captchas or warnings

### Cookie File Security

- **Never commit** `cookies.txt` to git (add to `.gitignore`)
- **Restrict permissions**: `chmod 600 cookies.txt`
- **Don't share** cookie files - they contain your session

---

## Troubleshooting

### "Sign in to confirm you're not a bot"

1. Cookies may be expired - export fresh ones
2. Too many requests - increase sleep intervals
3. IP may be flagged - try different network/proxy

### "Cookies from browser could not be loaded"

1. Close all browser windows before exporting
2. Use the extension method, not `--cookies-from-browser`
3. Ensure cookies.txt format is Netscape format

### Cookies Work Locally But Not On Server

1. Check file permissions: `ls -la cookies.txt`
2. Verify file was transferred correctly: `head cookies.txt`
3. Server IP may be blocked - try residential proxy

### "HTTP Error 403" Despite Valid Cookies

1. YouTube may have rotated signature algorithm
2. Update yt-dlp binary: Download latest from [releases](https://github.com/yt-dlp/yt-dlp/releases)
3. Ensure Deno is installed and in PATH

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `YTDLP_COOKIES_FILE` | (none) | Path to cookies.txt file |
| `YTDLP_BINARY` | `./bin/yt-dlp` | Path to yt-dlp binary |
| `YTDLP_MIN_SLEEP` | `7` | Minimum seconds between requests |
| `YTDLP_MAX_SLEEP` | `25` | Maximum seconds between requests |
| `YTDLP_SLEEP_REQUESTS` | `1.0` | Seconds between API requests |

---

## References

- [yt-dlp FAQ: How to pass cookies](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [yt-dlp Wiki: Exporting YouTube cookies](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)
- [yt-dlp Deno requirement](https://github.com/yt-dlp/yt-dlp/issues/15012)
