# Screenshot Jobs System - Implementation Plan

## Problem Statement

Expose screenshot extraction as an async job on RunPod (and other workers) that:
1. Returns a `job_id` immediately so callers can check status later
2. Processes synchronously (RunPod handles async) and stores screenshots to Supabase
3. Uses the existing `/screenshot/video` workflow (no code duplication)
4. Stores job metadata in `public_media.metadata` field (no new tables)
5. Status is queried directly from Supabase (not via our API)

---

## Key Insights

1. **RunPod uses `handler.py`**, not FastAPI with uvicorn. BackgroundTasks won't work.
2. **Follow the transcription pattern**: `handler.py` → service function → Supabase
3. **`document_id` already supported** in `ScreenshotRequest` (line 68, schemas.py)
4. **Status queries go directly to Supabase** from n8n - no GET endpoint needed in our API
5. **Confirm/cleanup endpoints** can be Supabase functions (not in our API)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         n8n / Client                                │
└─────────────────────────────────────────────────────────────────────┘
         │                                          │
         │ POST RunPod /run                         │ Query Supabase directly
         │ {queue: "screenshot_extraction",         │ SELECT * FROM public_media
         │  jobs: [{video_url, timestamps, ...}]}   │ WHERE metadata->>'job_id' = X
         ▼                                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    RunPod Serverless                                │
│                                                                     │
│  handler.py (thin orchestration):                                  │
│  1. Route by queue name                                            │
│  2. Call screenshot_job_service.process_screenshot_job_batch()     │
│  3. Return summary                                                 │
│                                                                     │
│  screenshot_job_service.py:                                        │
│  1. Generate job_id (UUID)                                         │
│  2. Call existing screenshot extraction logic                      │
│  3. Upload to Supabase storage with job_id in metadata             │
│  4. Save to public_media table with job tracking fields            │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Supabase                                    │
│                                                                     │
│  public_media table (existing):                                    │
│  - id, type, storage_path, storage_bucket, content_type, ...      │
│  - source_url, source_url_hash, title, document_id                │
│  - metadata: {                                                     │
│      job_id: "uuid",           ← NEW: job tracking                │
│      storage_status: "temp",   ← NEW: temp/confirmed lifecycle    │
│      job_received_at: "...",   ← NEW                              │
│      job_completed_at: "...",  ← NEW                              │
│      worker: "runpod",         ← NEW                              │
│      video_id, video_title, platform, timestamp, ...  (existing)  │
│    }                                                               │
│  - created_at (use for TTL cleanup)                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Tasks

### Task 1: Create Screenshot Job Service

**File:** `app/services/screenshot_job_service.py` (NEW)

```python
"""
Screenshot job service for processing screenshot extraction jobs.

Follows the same pattern as job_service.py for transcription jobs.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.services.supabase_service import (
    get_supabase_client,
    upload_screenshot_to_supabase,
    save_screenshot_metadata
)
from app.services.screenshot_service import extract_screenshot
from app.services.ytdlp_service import run_ytdlp_binary, youtube_rate_limit
from app.services.cache_service import get_cached_video, cleanup_cache
from app.utils.platform_utils import is_youtube_url, get_platform_prefix
from app.utils.timestamp_utils import parse_timestamp_to_seconds, format_seconds_to_srt
from app.config import CACHE_DIR, YTDLP_BINARY


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


async def process_screenshot_job_batch(
    payload: Dict[str, Any],
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Process a batch of screenshot jobs.

    Payload format:
    {
        "queue": "screenshot_extraction",
        "jobs": [
            {
                "video_url": "https://youtube.com/...",
                "timestamps": ["00:00:30,000", "00:01:00,000"],
                "quality": 2,
                "document_id": "optional-uuid"
            }
        ]
    }

    Returns summary and results like transcription job batch.
    """
    jobs = payload.get("jobs", [])
    worker = os.environ.get("WORKER_NAME", "runpod")

    summary = {
        "total": len(jobs),
        "completed": 0,
        "failed": 0
    }
    results = []

    for job in jobs:
        job_result = await _process_single_screenshot_job(job, worker)
        results.append(job_result)

        if job_result.get("status") == "completed":
            summary["completed"] += 1
        else:
            summary["failed"] += 1

    return {
        "ok": summary["failed"] == 0,
        "summary": summary,
        "results": results
    }


async def _process_single_screenshot_job(
    job: Dict[str, Any],
    worker: str
) -> Dict[str, Any]:
    """
    Process a single screenshot job.

    1. Generate job_id
    2. Extract video metadata
    3. Download video (cached)
    4. Extract screenshots at each timestamp
    5. Upload to Supabase with job_id in metadata
    """
    job_id = str(uuid.uuid4())
    job_received_at = _now_iso()

    video_url = job.get("video_url")
    timestamps = job.get("timestamps", [])
    quality = job.get("quality", 2)
    document_id = job.get("document_id")

    try:
        # ... (extract metadata, download video, process screenshots)
        # ... (reuse logic from screenshot.py)
        # ... (save to Supabase with job_id in metadata)

        return {
            "job_id": job_id,
            "status": "completed",
            "video_url": video_url,
            "total_extracted": len(screenshots),
            "failed_timestamps": failed
        }

    except Exception as e:
        return {
            "job_id": job_id,
            "status": "error",
            "video_url": video_url,
            "error": str(e)
        }
```

**Key difference from plan's BackgroundTasks approach:**
- Process synchronously (RunPod handles the async)
- Return job_id in the response
- Client queries Supabase directly for results

---

### Task 2: Extend handler.py with Queue Routing

**File:** `handler.py` (MODIFY)

Add routing for screenshot jobs:

```python
# After line 133, add queue routing:

from app.services.job_service import process_job_batch
from app.services.screenshot_job_service import process_screenshot_job_batch

# In handler() function:
queue = job_input.get("queue", "video_audio_transcription")

if queue == "screenshot_extraction":
    result = run_async(
        process_screenshot_job_batch(
            payload=job_input,
            max_retries=settings.worker_max_retries
        )
    )
elif queue == "video_audio_transcription":
    result = run_async(
        process_job_batch(
            payload=job_input,
            max_retries=settings.worker_max_retries,
            model_size=settings.worker_model_size,
            provider=settings.worker_provider
        )
    )
else:
    return {
        "ok": False,
        "error": f"Unknown queue: {queue}",
        "summary": {"total": 0}
    }
```

---

### Task 3: Extend Supabase Service

**File:** `app/services/supabase_service.py` (MODIFY)

Add function to save screenshot with job metadata:

```python
def save_screenshot_with_job_metadata(
    base_data: Dict,
    job_metadata: Dict
) -> Optional[Dict]:
    """
    Save screenshot to public_media with job tracking in metadata.

    job_metadata contains:
    - job_id: UUID string
    - storage_status: "temp" or "confirmed"
    - job_received_at: ISO timestamp
    - job_completed_at: ISO timestamp
    - worker: "runpod", "local", etc.
    """
    supabase = get_supabase_client()

    # Merge job_metadata into the existing metadata field
    data = base_data.copy()
    existing_metadata = data.get("metadata", {})
    existing_metadata.update(job_metadata)
    data["metadata"] = existing_metadata

    result = supabase.table("public_media").insert(data).execute()
    return result.data[0] if result.data else None
```

---

### Task 4: Supabase Functions (Optional - for n8n)

Create Supabase database functions for n8n to call:

```sql
-- Get screenshots by job_id
CREATE OR REPLACE FUNCTION get_screenshots_by_job_id(p_job_id TEXT)
RETURNS SETOF public_media AS $$
BEGIN
  RETURN QUERY
  SELECT * FROM public.public_media
  WHERE metadata->>'job_id' = p_job_id
  ORDER BY (metadata->>'timestamp')::float;
END;
$$ LANGUAGE plpgsql;

-- Confirm screenshots (temp -> confirmed)
CREATE OR REPLACE FUNCTION confirm_screenshots(p_job_id TEXT)
RETURNS INTEGER AS $$
DECLARE
  updated_count INTEGER;
BEGIN
  UPDATE public.public_media
  SET metadata = jsonb_set(metadata, '{storage_status}', '"confirmed"')
  WHERE metadata->>'job_id' = p_job_id
    AND metadata->>'storage_status' = 'temp';

  GET DIAGNOSTICS updated_count = ROW_COUNT;
  RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

-- Cleanup expired temp screenshots (call via cron/scheduled function)
CREATE OR REPLACE FUNCTION cleanup_temp_screenshots(hours_old INTEGER DEFAULT 24)
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
  paths_to_delete TEXT[];
BEGIN
  -- Get storage paths to delete
  SELECT array_agg(storage_path) INTO paths_to_delete
  FROM public.public_media
  WHERE metadata->>'storage_status' = 'temp'
    AND created_at < NOW() - (hours_old || ' hours')::INTERVAL;

  -- Delete from database
  DELETE FROM public.public_media
  WHERE metadata->>'storage_status' = 'temp'
    AND created_at < NOW() - (hours_old || ' hours')::INTERVAL;

  GET DIAGNOSTICS deleted_count = ROW_COUNT;

  -- Note: Storage bucket cleanup requires Edge Function or external trigger
  -- The paths_to_delete array can be used by a separate process

  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
```

**Index for faster job_id queries:**
```sql
CREATE INDEX IF NOT EXISTS idx_public_media_job_id
ON public.public_media ((metadata->>'job_id'));

CREATE INDEX IF NOT EXISTS idx_public_media_storage_status
ON public.public_media ((metadata->>'storage_status'));
```

---

## Files Summary

| File | Action | Description |
|------|--------|-------------|
| `app/services/screenshot_job_service.py` | CREATE | Job processing (reuses screenshot logic) |
| `app/services/supabase_service.py` | MODIFY | Add `save_screenshot_with_job_metadata()` |
| `handler.py` | MODIFY | Add queue routing for screenshot_extraction |

**NOT needed in our API:**
- No GET `/jobs/screenshot/{job_id}` endpoint (query Supabase directly)
- No POST `/jobs/screenshot/{job_id}/confirm` endpoint (use Supabase function)
- No DELETE cleanup endpoint (use Supabase scheduled function)

---

## Implementation Order

1. **SQL** - Add index on `metadata->>'job_id'` and Supabase functions
2. **supabase_service.py** - Add `save_screenshot_with_job_metadata()`
3. **screenshot_job_service.py** - Create new service (reuse screenshot.py logic)
4. **handler.py** - Add queue routing
5. **Test** - Submit job via RunPod, query Supabase for results

---

## Usage Flow (n8n)

```
1. POST to RunPod /run
   Headers: Authorization: Bearer {RUNPOD_API_KEY}
   Body: {
     "input": {
       "queue": "screenshot_extraction",
       "jobs": [{
         "video_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
         "timestamps": ["00:00:30,000", "00:01:00,000"],
         "quality": 2,
         "document_id": "optional-uuid-if-linking-to-documents-table"
       }]
     }
   }

   Response: {"id": "runpod-job-id", "status": "IN_QUEUE"}

2. Wait or poll RunPod /status/{runpod-job-id} for completion
   Response when done: {
     "status": "COMPLETED",
     "output": {
       "ok": true,
       "summary": {"total": 1, "completed": 1, "failed": 0},
       "results": [{
         "job_id": "abc-123-uuid",  ← Use this to query Supabase
         "status": "completed",
         "total_extracted": 2
       }]
     }
   }

3. Query Supabase directly for screenshots:
   SELECT * FROM public_media
   WHERE metadata->>'job_id' = 'abc-123-uuid'

   Or use RPC: SELECT * FROM get_screenshots_by_job_id('abc-123-uuid')

4. To keep screenshots permanently:
   SELECT confirm_screenshots('abc-123-uuid')

5. Temp screenshots auto-deleted after 24h via scheduled cleanup
```

---

## Schema Modifications Required

### 1. Add `document_id` column (better for performance)

```sql
-- Add document_id column as optional FK
ALTER TABLE public.public_media
ADD COLUMN IF NOT EXISTS document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL;

-- Index for document_id lookups
CREATE INDEX IF NOT EXISTS idx_public_media_document_id
ON public.public_media (document_id)
WHERE document_id IS NOT NULL;
```

**Rationale:** Better query performance than JSONB extraction. Enables multiple media items per document (screenshots, thumbnails, etc.).

### 2. Modify UNIQUE constraint on `source_url_hash`

```sql
-- Drop existing constraint
ALTER TABLE public.public_media
DROP CONSTRAINT IF EXISTS unique_source_url_hash;

-- Re-add as partial unique constraint (only for thumbnails)
CREATE UNIQUE INDEX IF NOT EXISTS unique_source_url_hash_thumbnails
ON public.public_media (source_url_hash)
WHERE type = 'thumbnail' AND source_url_hash IS NOT NULL;
```

**Rationale:** Thumbnails are 1-per-video, but screenshots can be many per video.

### 3. Verify storage bucket name

The code uses `public_media` (underscore) for both:
- Storage bucket: `supabase.storage.from_("public_media")`
- Database table: `supabase.table("public_media")`

Ensure the storage bucket exists with name `public_media`.

---

## Data Structure in public_media

Each screenshot row will have:

### Top-level columns:
```
id              UUID (auto)
type            "screenshot"
storage_path    "screenshots/{video_id}/{timestamp_ms}.jpg"
storage_bucket  "public_media"
content_type    "image/jpeg"
size_bytes      123456
source_url      "https://youtube.com/watch?v=dQw4w9WgXcQ"
source_url_hash NULL (or md5 hash - not enforced unique for screenshots)
title           "Video Title - 00:00:30,000"
description     NULL
document_id     UUID (optional FK to documents table) ← NEW COLUMN
created_at      auto
updated_at      auto via trigger
```

### metadata JSONB field:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "timestamp": 30.0,
  "timestamp_formatted": "00:00:30,000",
  "width": 1920,
  "height": 1080,
  "platform": "youtube",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "storage_status": "temp",
  "job_received_at": "2025-12-17T10:00:00Z",
  "job_completed_at": "2025-12-17T10:01:30Z",
  "worker": "runpod",
  "video_title": "Video Title",
  "video_duration": 212
}
```

**Existing fields** (from current screenshot.py):
- `video_id`, `timestamp`, `timestamp_formatted`, `width`, `height`, `platform`

**New job tracking fields in metadata**:
- `job_id` - UUID to group screenshots from same job
- `storage_status` - "temp" (default) or "confirmed"
- `job_received_at` - When job was received
- `job_completed_at` - When screenshot was saved
- `worker` - "runpod", "local", etc.
- `video_title` - Full video title
- `video_duration` - Video duration in seconds (if available)

**Top-level column (not in metadata)**:
- `document_id` - Optional FK to documents table (proper column for performance)

---

## Supabase SQL Setup

### Indexes (run once)

```sql
-- Index for fast job_id lookups
CREATE INDEX IF NOT EXISTS idx_public_media_metadata_job_id
ON public.public_media ((metadata->>'job_id'));

-- Index for storage_status filtering (cleanup queries)
CREATE INDEX IF NOT EXISTS idx_public_media_metadata_storage_status
ON public.public_media ((metadata->>'storage_status'));

-- Composite index for temp cleanup queries (status + created_at)
CREATE INDEX IF NOT EXISTS idx_public_media_temp_cleanup
ON public.public_media (created_at)
WHERE (metadata->>'storage_status') = 'temp';
```

### Function: Get Screenshots by Job ID

```sql
-- Get all screenshots for a specific job_id
-- Usage: SELECT * FROM get_screenshots_by_job_id('550e8400-e29b-41d4-a716-446655440000');
CREATE OR REPLACE FUNCTION get_screenshots_by_job_id(p_job_id TEXT)
RETURNS TABLE (
  id UUID,
  storage_path TEXT,
  storage_bucket TEXT,
  content_type TEXT,
  size_bytes BIGINT,
  source_url TEXT,
  title TEXT,
  document_id UUID,
  metadata JSONB,
  created_at TIMESTAMPTZ,
  -- Extracted fields for convenience
  timestamp_seconds FLOAT,
  timestamp_formatted TEXT,
  width INT,
  height INT,
  platform TEXT,
  video_title TEXT,
  storage_status TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    pm.id,
    pm.storage_path,
    pm.storage_bucket,
    pm.content_type,
    pm.size_bytes,
    pm.source_url,
    pm.title,
    pm.document_id,  -- Now a proper column
    pm.metadata,
    pm.created_at,
    -- Extract commonly needed fields from metadata
    (pm.metadata->>'timestamp')::FLOAT AS timestamp_seconds,
    pm.metadata->>'timestamp_formatted' AS timestamp_formatted,
    (pm.metadata->>'width')::INT AS width,
    (pm.metadata->>'height')::INT AS height,
    pm.metadata->>'platform' AS platform,
    pm.metadata->>'video_title' AS video_title,
    pm.metadata->>'storage_status' AS storage_status
  FROM public.public_media pm
  WHERE pm.metadata->>'job_id' = p_job_id
  ORDER BY (pm.metadata->>'timestamp')::FLOAT ASC;
END;
$$ LANGUAGE plpgsql STABLE;
```

**Note:** Public URL can be constructed client-side as:
`{SUPABASE_URL}/storage/v1/object/public/{storage_bucket}/{storage_path}`

### Function: Get Expired Temp Screenshots (for deletion job)

```sql
-- Get temp screenshots older than specified hours (default 48)
-- Usage: SELECT * FROM get_expired_temp_screenshots(48);
-- Returns storage_path for bucket cleanup + id for database deletion
CREATE OR REPLACE FUNCTION get_expired_temp_screenshots(hours_old INTEGER DEFAULT 48)
RETURNS TABLE (
  id UUID,
  storage_path TEXT,
  storage_bucket TEXT,
  job_id TEXT,
  created_at TIMESTAMPTZ,
  age_hours FLOAT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    pm.id,
    pm.storage_path,
    pm.storage_bucket,
    pm.metadata->>'job_id' AS job_id,
    pm.created_at,
    EXTRACT(EPOCH FROM (NOW() - pm.created_at)) / 3600 AS age_hours
  FROM public.public_media pm
  WHERE pm.metadata->>'storage_status' = 'temp'
    AND pm.created_at < NOW() - (hours_old || ' hours')::INTERVAL
  ORDER BY pm.created_at ASC;
END;
$$ LANGUAGE plpgsql STABLE;
```

### Edge Function: Delete Expired Temp Screenshots (storage + database)

Database functions cannot call the Storage API, so we need an Edge Function to:
1. Query expired temp screenshots
2. Delete files from storage bucket
3. Delete records from database

```typescript
// supabase/functions/cleanup-temp-screenshots/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

serve(async (req) => {
  try {
    // Parse hours_old from request (default 48)
    const { hours_old = 48 } = await req.json().catch(() => ({}));

    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

    // 1. Get expired temp screenshots
    const { data: expiredItems, error: queryError } = await supabase
      .from("public_media")
      .select("id, storage_path, storage_bucket")
      .eq("metadata->>storage_status", "temp")
      .lt("created_at", new Date(Date.now() - hours_old * 60 * 60 * 1000).toISOString());

    if (queryError) {
      throw new Error(`Query failed: ${queryError.message}`);
    }

    if (!expiredItems || expiredItems.length === 0) {
      return new Response(
        JSON.stringify({ deleted_count: 0, message: "No expired temp screenshots found" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    // 2. Delete files from storage bucket
    const storagePaths = expiredItems.map((item) => item.storage_path);
    const { error: storageError } = await supabase.storage
      .from("public_media")
      .remove(storagePaths);

    if (storageError) {
      console.error("Storage deletion error (continuing):", storageError.message);
      // Continue anyway - some files might not exist
    }

    // 3. Delete records from database
    const idsToDelete = expiredItems.map((item) => item.id);
    const { error: deleteError } = await supabase
      .from("public_media")
      .delete()
      .in("id", idsToDelete);

    if (deleteError) {
      throw new Error(`Database deletion failed: ${deleteError.message}`);
    }

    return new Response(
      JSON.stringify({
        deleted_count: expiredItems.length,
        storage_paths_removed: storagePaths,
        message: `Deleted ${expiredItems.length} expired temp screenshots`
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );

  } catch (error) {
    console.error("Cleanup error:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
});
```

**Usage from n8n:**
```bash
curl -X POST "https://<project>.supabase.co/functions/v1/cleanup-temp-screenshots" \
  -H "Authorization: Bearer <SUPABASE_ANON_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"hours_old": 48}'
```

**Schedule via Supabase cron (pg_cron):**
```sql
-- Run cleanup every 6 hours
SELECT cron.schedule(
  'cleanup-temp-screenshots',
  '0 */6 * * *',
  $$
  SELECT net.http_post(
    url := 'https://<project>.supabase.co/functions/v1/cleanup-temp-screenshots',
    headers := '{"Authorization": "Bearer <SERVICE_ROLE_KEY>", "Content-Type": "application/json"}'::jsonb,
    body := '{"hours_old": 48}'::jsonb
  );
  $$
);
```

### Function: Confirm Screenshots (temp → confirmed)

```sql
-- Confirm screenshots by array of public_media IDs
-- Usage: SELECT confirm_screenshots(ARRAY['uuid1', 'uuid2']::UUID[]);
-- Usage (single): SELECT confirm_screenshots(ARRAY['uuid1']::UUID[]);
CREATE OR REPLACE FUNCTION confirm_screenshots(p_ids UUID[])
RETURNS INTEGER AS $$
DECLARE
  updated_count INTEGER;
BEGIN
  UPDATE public.public_media
  SET metadata = jsonb_set(metadata, '{storage_status}', '"confirmed"')
  WHERE id = ANY(p_ids)
    AND metadata->>'storage_status' = 'temp';

  GET DIAGNOSTICS updated_count = ROW_COUNT;
  RETURN updated_count;
END;
$$ LANGUAGE plpgsql;
```

---

## n8n Usage Examples

### Query screenshots by job_id:
```sql
-- Direct query
SELECT * FROM public_media WHERE metadata->>'job_id' = 'abc-123';

-- Or use function (returns flattened fields)
SELECT * FROM get_screenshots_by_job_id('abc-123');
```

### Check for expired temp screenshots:
```sql
SELECT * FROM get_expired_temp_screenshots(48);
```

### Delete expired (returns paths for storage cleanup):
```sql
SELECT * FROM delete_expired_temp_screenshots(48);
-- Then use returned storage_paths array to delete from bucket via Edge Function
```

---

## n8n / API Usage Examples

All Supabase functions can be called via the REST API using the `rpc` endpoint.

### Base URL
```
https://<PROJECT_ID>.supabase.co/rest/v1/rpc/<function_name>
```

### Headers (for all requests)
```
Authorization: Bearer <SUPABASE_ANON_KEY or SERVICE_ROLE_KEY>
apikey: <SUPABASE_ANON_KEY>
Content-Type: application/json
```

---

### 1. Get Screenshots by Job ID

**HTTP Request:**
```bash
curl -X POST "https://<PROJECT>.supabase.co/rest/v1/rpc/get_screenshots_by_job_id" \
  -H "Authorization: Bearer <SUPABASE_ANON_KEY>" \
  -H "apikey: <SUPABASE_ANON_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"p_job_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

**n8n HTTP Request Node:**
```json
{
  "method": "POST",
  "url": "https://<PROJECT>.supabase.co/rest/v1/rpc/get_screenshots_by_job_id",
  "headers": {
    "Authorization": "Bearer {{ $env.SUPABASE_ANON_KEY }}",
    "apikey": "{{ $env.SUPABASE_ANON_KEY }}",
    "Content-Type": "application/json"
  },
  "body": {
    "p_job_id": "{{ $json.job_id }}"
  }
}
```

**Response:**
```json
[
  {
    "id": "uuid",
    "storage_path": "screenshots/dQw4w9WgXcQ/30000.jpg",
    "storage_bucket": "public_media",
    "document_id": "uuid-or-null",
    "timestamp_seconds": 30.0,
    "timestamp_formatted": "00:00:30,000",
    "width": 1920,
    "height": 1080,
    "platform": "youtube",
    "video_title": "Video Title",
    "storage_status": "temp",
    ...
  }
]
```

---

### 2. Confirm Screenshots (temp → confirmed)

Accepts array of `public_media` record IDs (single or multiple).

**HTTP Request (multiple):**
```bash
curl -X POST "https://<PROJECT>.supabase.co/rest/v1/rpc/confirm_screenshots" \
  -H "Authorization: Bearer <SUPABASE_ANON_KEY>" \
  -H "apikey: <SUPABASE_ANON_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"p_ids": ["uuid-1", "uuid-2", "uuid-3"]}'
```

**HTTP Request (single):**
```bash
curl -X POST "https://<PROJECT>.supabase.co/rest/v1/rpc/confirm_screenshots" \
  -H "Authorization: Bearer <SUPABASE_ANON_KEY>" \
  -H "apikey: <SUPABASE_ANON_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"p_ids": ["uuid-1"]}'
```

**Response:**
```json
2
```
*(Returns count of confirmed screenshots)*

---

### 3. Get Expired Temp Screenshots (preview before delete)

**HTTP Request:**
```bash
curl -X POST "https://<PROJECT>.supabase.co/rest/v1/rpc/get_expired_temp_screenshots" \
  -H "Authorization: Bearer <SUPABASE_ANON_KEY>" \
  -H "apikey: <SUPABASE_ANON_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"hours_old": 48}'
```

**n8n HTTP Request Node:**
```json
{
  "method": "POST",
  "url": "https://<PROJECT>.supabase.co/rest/v1/rpc/get_expired_temp_screenshots",
  "headers": {
    "Authorization": "Bearer {{ $env.SUPABASE_ANON_KEY }}",
    "apikey": "{{ $env.SUPABASE_ANON_KEY }}",
    "Content-Type": "application/json"
  },
  "body": {
    "hours_old": 48
  }
}
```

**Response:**
```json
[
  {
    "id": "uuid",
    "storage_path": "screenshots/abc123/30000.jpg",
    "storage_bucket": "public_media",
    "job_id": "job-uuid",
    "created_at": "2025-12-15T10:00:00Z",
    "age_hours": 52.5
  }
]
```

---

### 4. Delete Expired Temp Screenshots (Edge Function)

**HTTP Request:**
```bash
curl -X POST "https://<PROJECT>.supabase.co/functions/v1/cleanup-temp-screenshots" \
  -H "Authorization: Bearer <SUPABASE_ANON_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"hours_old": 48}'
```

**n8n HTTP Request Node:**
```json
{
  "method": "POST",
  "url": "https://<PROJECT>.supabase.co/functions/v1/cleanup-temp-screenshots",
  "headers": {
    "Authorization": "Bearer {{ $env.SUPABASE_ANON_KEY }}",
    "Content-Type": "application/json"
  },
  "body": {
    "hours_old": 48
  }
}
```

**Response:**
```json
{
  "deleted_count": 15,
  "storage_paths_removed": ["screenshots/abc/1.jpg", "screenshots/def/2.jpg", ...],
  "message": "Deleted 15 expired temp screenshots"
}
```

---

### Quick Reference Table

| Action | Endpoint | Method | Body |
|--------|----------|--------|------|
| Get screenshots by job | `/rest/v1/rpc/get_screenshots_by_job_id` | POST | `{"p_job_id": "uuid"}` |
| Confirm screenshots | `/rest/v1/rpc/confirm_screenshots` | POST | `{"p_ids": ["uuid1", "uuid2"]}` |
| Preview expired | `/rest/v1/rpc/get_expired_temp_screenshots` | POST | `{"hours_old": 48}` |
| Delete expired | `/functions/v1/cleanup-temp-screenshots` | POST | `{"hours_old": 48}` |

**See also:** [Guide-n8n-Operations.md](Guide-n8n-Operations.md) for complete n8n workflow examples.

---

## Notes

- **document_id** - Proper column (after schema migration). Optional FK to documents table.
- **Worker-agnostic**: `WORKER_NAME` env var identifies the worker (runpod, local, etc.)
- **No FastAPI endpoints needed** for status/confirm/cleanup - all via Supabase
- **Storage + database cleanup** via Edge Function (deletes files then records)
- **48-hour default** for temp screenshot expiry (configurable)
- **source_url_hash** - UNIQUE constraint only applies to thumbnails after schema migration

---

## Summary of Schema Migrations

### Option A: Run via Supabase CLI

Supabase CLI is installed. Link to your project first, then run SQL:

```bash
# Link to project (one-time setup)
supabase link --project-ref <PROJECT_REF>

# Run SQL file
supabase db push --db-url <DATABASE_URL>
# Or execute directly:
supabase db query --db-url <DATABASE_URL> -f migrations/screenshot_jobs.sql
```

### Option B: Run in Supabase SQL Editor

Copy and paste the SQL below into the Supabase Dashboard → SQL Editor:

```sql
-- 1. Add document_id column
ALTER TABLE public.public_media
ADD COLUMN IF NOT EXISTS document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_public_media_document_id
ON public.public_media (document_id)
WHERE document_id IS NOT NULL;

-- 2. Fix UNIQUE constraint (only for thumbnails)
ALTER TABLE public.public_media
DROP CONSTRAINT IF EXISTS unique_source_url_hash;

CREATE UNIQUE INDEX IF NOT EXISTS unique_source_url_hash_thumbnails
ON public.public_media (source_url_hash)
WHERE type = 'thumbnail' AND source_url_hash IS NOT NULL;

-- 3. Add indexes for job queries
CREATE INDEX IF NOT EXISTS idx_public_media_metadata_job_id
ON public.public_media ((metadata->>'job_id'));

CREATE INDEX IF NOT EXISTS idx_public_media_metadata_storage_status
ON public.public_media ((metadata->>'storage_status'));

CREATE INDEX IF NOT EXISTS idx_public_media_temp_cleanup
ON public.public_media (created_at)
WHERE (metadata->>'storage_status') = 'temp';
```

---

## Code Compatibility Note

**File:** `app/routers/screenshot.py` (lines 154-172)

The existing code saves `document_id` as a top-level field. After adding the column, this will work correctly. No code changes needed for the existing screenshot endpoint - it already passes `document_id` correctly.
