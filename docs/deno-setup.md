# Deno Setup for yt-dlp YouTube Support

## Overview

Starting with an upcoming yt-dlp release (post-2025.10.22), **Deno (or another JavaScript runtime) will be required** for YouTube downloads to work properly. This is due to YouTube's increasingly complex JavaScript challenges that exceed the capabilities of yt-dlp's built-in JS interpreter.

## Why Deno?

- **Security**: Deno is sandboxed by default with no filesystem or network access
- **Portability**: Single-file executable, similar to ffmpeg
- **Performance**: Full-strength JavaScript runtime for solving YouTube's JS challenges

## Installation

### Option 1: Download Binary (Recommended)

**macOS/Linux:**
```bash
curl -fsSL https://deno.land/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://deno.land/install.ps1 | iex
```

**Manual Download:**
Visit https://github.com/denoland/deno/releases and download the latest release for your platform.

### Option 2: Package Managers

**macOS (Homebrew):**
```bash
brew install deno
```

**Linux (apt/snap):**
```bash
# Ubuntu/Debian
curl -fsSL https://deno.land/x/install/install.sh | sh

# Or via snap
snap install deno
```

**Windows (Chocolatey):**
```bash
choco install deno
```

## Version Requirements

- **Minimum**: Deno 2.0.0
- **Recommended**: Latest stable version
- Check version: `deno --version`

## Alternative JavaScript Runtimes

Deno is the recommended runtime, but these alternatives are also supported:

| Runtime | Minimum Version |
|---------|----------------|
| Deno    | 2.0.0         |
| Node.js | 20.0.0        |
| Bun     | 1.0.31        |
| QuickJS | (supported)   |

## Verification

After installation, verify Deno is accessible:

```bash
deno --version
# Should output something like:
# deno 2.x.x
# typescript 5.x.x
```

## Impact on This Project

### Current Status (yt-dlp 2025.10.22)
- ✅ YouTube downloads work with temporary workaround
- ⚠️  Some formats may be unavailable
- ⚠️  Cookies may cause issues

### After Next Release
- ⚠️  **Deno will be REQUIRED for YouTube downloads**
- ✅ Other 1000+ sites will continue working without Deno
- ✅ Deno will be auto-detected if in PATH

## Deployment Considerations

### Local Development
- Install Deno on your development machine
- Add to PATH (installer usually does this automatically)

### Docker Deployment
Add Deno installation to Dockerfile:

```dockerfile
# Install Deno
RUN curl -fsSL https://deno.land/install.sh | sh
ENV PATH="/root/.deno/bin:${PATH}"
```

### Railway/Cloud Deployment
Add Deno installation to build script or Nixpacks configuration:

```bash
# In railway.json or build script
curl -fsSL https://deno.land/install.sh | sh
export PATH="$HOME/.deno/bin:$PATH"
```

## Python Library Users (PyPI/pip)

If you installed yt-dlp via pip, you'll need to:

1. Install Deno (see instructions above)
2. Update yt-dlp when the new version releases:
   ```bash
   pip install -U "yt-dlp[default]"
   ```

The `[default]` extra ensures you get all necessary JavaScript components.

## No Action Required... Yet

For now, **no immediate action is required**. The current version (2025.10.22) includes a temporary workaround. However, we recommend:

1. **Install Deno now** to be prepared
2. **Test** that Deno is accessible: `deno --version`
3. **Monitor** yt-dlp release notes for the mandatory update

## Troubleshooting

### "Deno not found" error
- Ensure Deno is installed: `which deno` (Linux/Mac) or `where deno` (Windows)
- Add Deno to PATH if not already there
- Restart terminal/shell after installation

### YouTube downloads still failing
- Update to latest yt-dlp version: `pip install -U yt-dlp`
- Verify Deno version: `deno --version` (must be 2.0.0+)
- Check yt-dlp GitHub issues: https://github.com/yt-dlp/yt-dlp/issues

### Other sites not working
- Deno is only required for YouTube
- Other sites should work without Deno
- If issues persist, check yt-dlp documentation

## References

- [Deno Official Website](https://deno.com/)
- [yt-dlp Deno Announcement](https://github.com/yt-dlp/yt-dlp/issues/14404)
- [yt-dlp GitHub Repository](https://github.com/yt-dlp/yt-dlp)
- [Deno Installation Guide](https://docs.deno.com/runtime/getting_started/installation/)

## Timeline

- **September 23, 2025**: Deno requirement announced
- **October 22, 2025**: Temporary workaround released (current version)
- **Coming soon**: Deno becomes mandatory for YouTube downloads

---

**Last Updated**: November 2025
**Current yt-dlp Version**: 2025.10.22
**Status**: Preparation phase - Deno not yet mandatory
