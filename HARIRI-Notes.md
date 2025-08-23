# Social Media Video Downloader - Development Notes

## Server Commands

### Start Development Server
```bash
# Activate virtual environment
source .venv/bin/activate

# Run development server with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Alternative Run Method
```bash
# Direct Python execution
source .venv/bin/activate
python main.py
```

### API Endpoints (All require X-Api-Key header)
- **Root**: http://localhost:8000/ (no auth required)
- **Download**: http://localhost:8000/download?url=VIDEO_URL&format=FORMAT&keep=BOOLEAN
- **Transcription**: http://localhost:8000/transcription?url=VIDEO_URL&lang=LANG&format=FORMAT
- **List Downloads**: http://localhost:8000/downloads/list

### Example Usage
```bash
# Set API key for all requests
API_KEY="test-api-key-12345"

# Download 720p video (temporary)
curl -H "X-Api-Key: $API_KEY" "http://localhost:8000/download?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format=best[height<=720]"

# Download and keep video on server
curl -H "X-Api-Key: $API_KEY" "http://localhost:8000/download?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format=best[height<=720]&keep=true"

# Get video transcription
curl -H "X-Api-Key: $API_KEY" "http://localhost:8000/transcription?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&lang=en&format=json"

# List saved videos
curl -H "X-Api-Key: $API_KEY" "http://localhost:8000/downloads/list"
```

### Environment Setup
```bash
# Copy environment template
cp example.env .env

# Edit .env to set required variables:
# - ALLOWED_ORIGIN for CORS
# - API_KEY for authentication (required)
# - DOWNLOADS_DIR for saved videos folder
```

### Railway Deployment
```bash
# For n8n on Railway, use internal URL:
# http://video-downloader.railway.internal:8000/endpoint
# Include X-Api-Key header in all n8n HTTP requests
```