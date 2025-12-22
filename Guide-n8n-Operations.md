# n8n Operations Guide - RunPod Jobs

This guide shows how to use the screenshot and transcription job systems from n8n workflows and via CURL.

## Table of Contents
- [Prerequisites](#prerequisites)
- [CURL Examples](#curl-examples)
  - [Screenshot Extraction](#screenshot-extraction-curl)
  - [Transcription Jobs](#transcription-jobs-curl)
  - [Supabase Functions](#supabase-functions-curl)
- [n8n Workflow Examples](#n8n-workflow-examples)

## Prerequisites

Set these environment variables:
- `RUNPOD_API_KEY` - Your RunPod API key
- `RUNPOD_ENDPOINT_ID` - Your RunPod endpoint ID (e.g., `abc123def`)
- `SUPABASE_URL` - Your Supabase project URL (e.g., `https://xxx.supabase.co`)
- `SUPABASE_ANON_KEY` - Your Supabase anon/public key

---

# CURL Examples

## Screenshot Extraction (CURL)

### 1. Start Screenshot Job on RunPod

Extract screenshots from a video at specified timestamps.

```bash
curl -X POST "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/run" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "queue": "screenshot_extraction",
      "jobs": [
        {
          "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
          "timestamps": ["00:00:30,000", "00:01:00,000", "00:01:30,000"],
          "quality": 2,
          "document_id": null
        }
      ]
    }
  }'
```

**Response:**
```json
{
  "id": "abc123-runpod-job-id",
  "status": "IN_QUEUE"
}
```

### 2. Poll Job Status

Check if a RunPod job has completed. Poll until `status` is `COMPLETED` or `FAILED`.

```bash
curl -X GET "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/status/abc123-runpod-job-id" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

**RunPod Job Status Values:**

| Status | Description | `output` Available |
|--------|-------------|-------------------|
| `IN_QUEUE` | Waiting for worker | No |
| `IN_PROGRESS` | Being processed | No |
| `COMPLETED` | Finished successfully | **Yes** |
| `FAILED` | Error occurred | Yes (error details) |
| `CANCELLED` | Manually cancelled | No |
| `TIMED_OUT` | Exceeded timeout | Yes (error details) |

**Response (completed):**
```json
{
  "id": "abc123-runpod-job-id",
  "status": "COMPLETED",
  "output": {
    "ok": true,
    "summary": {"total": 1, "completed": 1, "failed": 0},
    "results": [
      {
        "job_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "completed",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "total_extracted": 3,
        "failed_timestamps": []
      }
    ]
  }
}
```

### Two Approaches for Getting Results

After a job completes, you have two options:

| Approach | When to Use | Method |
|----------|-------------|--------|
| **A) Poll RunPod Status** | Simple integrations, immediate results | Poll `/status/{id}` → read `output` field |
| **B) Query Supabase** | Persistent data, complex queries, richer metadata | Query `public_media` table or use `get_screenshots_by_job_id()` |

**Approach A - Use RunPod `output`:**
- When `status` is `COMPLETED`, the `output` field contains all job results
- Quick and simple - no additional API calls needed
- Data expires after 30 minutes

**Approach B - Query Supabase directly:**
- Screenshots are persisted in `public_media` table with full metadata
- Use the internal `job_id` (from `output.results[].job_id`) to query
- Data persists until cleanup (temp screenshots expire after 48 hours unless confirmed)

### 3. Multiple Videos in One Job

Process multiple videos in a single RunPod job. Each video is processed sequentially.

```bash
curl -X POST "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/run" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "queue": "screenshot_extraction",
      "jobs": [
        {
          "video_url": "https://www.youtube.com/watch?v=video1",
          "timestamps": ["00:00:10,000", "00:00:20,000"],
          "quality": 2
        },
        {
          "video_url": "https://www.youtube.com/watch?v=video2",
          "timestamps": ["00:01:00,000"],
          "quality": 5
        }
      ]
    }
  }'
```

---

## Transcription Jobs (CURL)

### 1. Start Transcription Job on RunPod

Transcribe video/audio using whisperX. Uses PGMQ queue from Supabase.

```bash
curl -X POST "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/run" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "queue": "video_audio_transcription",
      "vt_seconds": 1800,
      "jobs": [
        {
          "msg_id": 1,
          "read_ct": 1,
          "document_id": "your-document-uuid-here"
        }
      ]
    }
  }'
```

**Note:** Transcription jobs typically come from Supabase PGMQ queue via Edge Function. The `msg_id` and `read_ct` are from the queue.

### 2. Poll Transcription Job Status

Same polling endpoint as screenshots. Results are saved to `documents` table in Supabase.

```bash
curl -X GET "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/status/abc123-runpod-job-id" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

**Response (completed):**
```json
{
  "id": "abc123-runpod-job-id",
  "status": "COMPLETED",
  "output": {
    "ok": true,
    "summary": {
      "total": 1,
      "completed": 1,
      "retry": 0,
      "archived": 0,
      "deleted": 0
    },
    "results": [
      {
        "msg_id": 1,
        "status": "completed",
        "document_id": "your-document-uuid-here",
        "word_count": 1234,
        "segment_count": 45
      }
    ]
  }
}
```

---

## Supabase Functions (CURL)

### Get Screenshots by Job ID

Query all screenshots from a completed screenshot job.

```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_screenshots_by_job_id" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_job_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response:**
```json
[
  {
    "id": "screenshot-uuid-1",
    "storage_path": "screenshots/dQw4w9WgXcQ/30000.jpg",
    "storage_bucket": "public_media",
    "timestamp_seconds": 30.0,
    "timestamp_formatted": "00:00:30,000",
    "width": 1920,
    "height": 1080,
    "platform": "youtube",
    "video_title": "Rick Astley - Never Gonna Give You Up",
    "storage_status": "temp"
  }
]
```

**Public URL format:**
```
${SUPABASE_URL}/storage/v1/object/public/public_media/screenshots/dQw4w9WgXcQ/30000.jpg
```

### Confirm Screenshots (temp → confirmed)

Mark screenshots as confirmed so they won't be auto-deleted.

**Confirm multiple screenshots:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/confirm_screenshots" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_ids": ["screenshot-uuid-1", "screenshot-uuid-2", "screenshot-uuid-3"]
  }'
```

**Confirm single screenshot:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/confirm_screenshots" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_ids": ["screenshot-uuid-1"]
  }'
```

**Response:** `3` (count of confirmed screenshots)

### Get Expired Temp Screenshots (Preview)

Preview which screenshots would be deleted before running cleanup.

```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_expired_temp_screenshots" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "hours_old": 48
  }'
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

### Cleanup Expired Temp Screenshots (Edge Function)

Delete expired temp screenshots from storage AND database.

```bash
curl -X POST "${SUPABASE_URL}/functions/v1/cleanup-temp-screenshots" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "hours_old": 48
  }'
```

**Response:**
```json
{
  "deleted_count": 15,
  "storage_paths_removed": [
    "screenshots/abc123/30000.jpg",
    "screenshots/def456/60000.jpg"
  ],
  "message": "Deleted 15 expired temp screenshots",
  "hours_checked": 48,
  "cutoff_date": "2025-12-16T10:00:00Z"
}
```

---

## Queue Routing Summary

| Queue Name | Purpose | Job Format |
|------------|---------|------------|
| `screenshot_extraction` | Extract video frames | `{"video_url": "...", "timestamps": [...]}` |
| `video_audio_transcription` | Transcribe audio | `{"msg_id": N, "document_id": "uuid"}` |

**Default:** If `queue` is omitted, defaults to `video_audio_transcription` for backward compatibility.

---

# n8n Workflow Examples

## 1. Initiate Screenshot Job on RunPod

Start a screenshot extraction job. Returns immediately with `job_id` for tracking.

### HTTP Request Node

**Method:** `POST`

**URL:**
```
https://api.runpod.ai/v2/{{ $env.RUNPOD_ENDPOINT_ID }}/run
```

**Headers:**
```json
{
  "Authorization": "Bearer {{ $env.RUNPOD_API_KEY }}",
  "Content-Type": "application/json"
}
```

**Body (JSON):**
```json
{
  "input": {
    "queue": "screenshot_extraction",
    "jobs": [
      {
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "timestamps": ["00:00:30,000", "00:01:00,000", "00:01:30,000"],
        "quality": 2,
        "document_id": "optional-uuid-to-link-to-documents-table"
      }
    ]
  }
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `video_url` | string | Yes | Video URL (YouTube, Vimeo, TikTok, etc.) |
| `timestamps` | array | Yes | Array of timestamps in SRT format (`"00:01:30,500"`) or seconds (`"90.5"`) |
| `quality` | int | No | JPEG quality 1-31, lower = better (default: 2) |
| `document_id` | UUID | No | Optional FK to `documents` table |

### Response

```json
{
  "id": "runpod-job-id-abc123",
  "status": "IN_QUEUE"
}
```

Save `id` for polling status.

---

## 2. Poll RunPod Job Status

Wait for job completion and get the internal `job_id` for Supabase queries.

### HTTP Request Node

**Method:** `GET`

**URL:**
```
https://api.runpod.ai/v2/{{ $env.RUNPOD_ENDPOINT_ID }}/status/{{ $json.id }}
```

**Headers:**
```json
{
  "Authorization": "Bearer {{ $env.RUNPOD_API_KEY }}"
}
```

### Response (when completed)

```json
{
  "id": "runpod-job-id-abc123",
  "status": "COMPLETED",
  "output": {
    "ok": true,
    "summary": {
      "total": 1,
      "completed": 1,
      "failed": 0
    },
    "results": [
      {
        "job_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "completed",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "total_extracted": 3,
        "failed_timestamps": []
      }
    ]
  }
}
```

### Polling Strategy

Use n8n's **Wait** node between polls:
1. Initial wait: 30 seconds
2. Poll status
3. If `status` is `IN_QUEUE` or `IN_PROGRESS`, wait 15 seconds and poll again
4. If `status` is `COMPLETED`, continue to next step
5. If `status` is `FAILED` or `TIMED_OUT`, handle error

### Two Options After Job Completes

When `status` is `COMPLETED`, you have two options:

**Option A: Use the `output` directly from status response**
- The `output` field contains all job results immediately
- No additional API call needed
- Extract: `{{ $json.output.results[0] }}`

**Option B: Query Supabase for richer data**
- Use `output.results[0].job_id` to query `public_media` table
- Gets full metadata: timestamps, dimensions, storage paths, public URLs
- Data persists beyond RunPod's 30-minute expiration

**Choose based on your needs:**
| Need | Use |
|------|-----|
| Quick status check | Option A (output field) |
| Full screenshot metadata | Option B (Supabase query) |
| Build public URLs | Option B (has `storage_path`) |
| Persist beyond 30 min | Option B (saved to DB) |

---

## 3. Get Screenshots by Job ID (Option B)

Query Supabase for all screenshots from a completed job. Use the internal `job_id` from `output.results[0].job_id`.

### HTTP Request Node

**Method:** `POST`

**URL:**
```
{{ $env.SUPABASE_URL }}/rest/v1/rpc/get_screenshots_by_job_id
```

**Headers:**
```json
{
  "Authorization": "Bearer {{ $env.SUPABASE_ANON_KEY }}",
  "apikey": "{{ $env.SUPABASE_ANON_KEY }}",
  "Content-Type": "application/json"
}
```

**Body (JSON):**
```json
{
  "p_job_id": "{{ $json.output.results[0].job_id }}"
}
```

### Response

```json
[
  {
    "id": "screenshot-uuid-1",
    "storage_path": "screenshots/dQw4w9WgXcQ/30000.jpg",
    "storage_bucket": "public_media",
    "content_type": "image/jpeg",
    "size_bytes": 125000,
    "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up - 00:00:30,000",
    "document_id": "uuid-or-null",
    "metadata": { ... },
    "created_at": "2025-12-17T10:01:30Z",
    "timestamp_seconds": 30.0,
    "timestamp_formatted": "00:00:30,000",
    "width": 1920,
    "height": 1080,
    "platform": "youtube",
    "video_title": "Rick Astley - Never Gonna Give You Up",
    "storage_status": "temp"
  },
  {
    "id": "screenshot-uuid-2",
    ...
  }
]
```

### Construct Public URL

For each screenshot, build the public URL:
```
{{ $env.SUPABASE_URL }}/storage/v1/object/public/{{ $json.storage_bucket }}/{{ $json.storage_path }}
```

Example:
```
https://xxx.supabase.co/storage/v1/object/public/public_media/screenshots/dQw4w9WgXcQ/30000.jpg
```

---

## 4. Confirm Screenshots (Keep Permanently)

Mark specific screenshots as "confirmed" so they won't be auto-deleted.

Accepts an array of `public_media` record IDs (can be single or multiple).

### HTTP Request Node

**Method:** `POST`

**URL:**
```
{{ $env.SUPABASE_URL }}/rest/v1/rpc/confirm_screenshots
```

**Headers:**
```json
{
  "Authorization": "Bearer {{ $env.SUPABASE_ANON_KEY }}",
  "apikey": "{{ $env.SUPABASE_ANON_KEY }}",
  "Content-Type": "application/json"
}
```

**Body - Confirm ALL screenshots from a job:**
```json
{
  "p_ids": {{ $json.map(item => item.id) }}
}
```

**Body - Confirm specific screenshots:**
```json
{
  "p_ids": ["screenshot-uuid-1", "screenshot-uuid-3"]
}
```

**Body - Confirm single screenshot:**
```json
{
  "p_ids": ["screenshot-uuid-1"]
}
```

### Response

```json
3
```
*(Returns count of confirmed screenshots)*

---

## 5. Cleanup Expired Temp Screenshots (Cron Job)

Delete temp screenshots older than 48 hours. Run this on a schedule (e.g., every 6 hours).

### HTTP Request Node

**Method:** `POST`

**URL:**
```
{{ $env.SUPABASE_URL }}/functions/v1/cleanup-temp-screenshots
```

**Headers:**
```json
{
  "Authorization": "Bearer {{ $env.SUPABASE_ANON_KEY }}",
  "Content-Type": "application/json"
}
```

**Body (JSON):**
```json
{
  "hours_old": 48
}
```

### Response

```json
{
  "deleted_count": 15,
  "storage_paths_removed": [
    "screenshots/abc123/30000.jpg",
    "screenshots/def456/60000.jpg"
  ],
  "message": "Deleted 15 expired temp screenshots"
}
```

### n8n Cron Schedule

Set up a **Schedule Trigger** node:
- **Trigger Interval:** Every 6 hours
- Or use cron expression: `0 */6 * * *`

---

## Complete Workflow Example

```
┌─────────────────┐
│ Schedule/Manual │
│    Trigger      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Start RunPod   │
│  Screenshot Job │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Wait 30s      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────┐
│  Poll RunPod    │────▶│  Wait 15s   │──┐
│    Status       │     └─────────────┘  │
└────────┬────────┘                      │
         │ COMPLETED                     │
         ▼                               │
┌─────────────────┐◀─────────────────────┘
│ Get Screenshots │     (if still IN_PROGRESS)
│   from Supabase │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Process/Filter  │
│  Screenshots    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Confirm      │
│  (if keeping)   │
└─────────────────┘
```

---

## Quick Reference

| Operation | Description | Endpoint | Body |
|-----------|-------------|----------|------|
| Start Screenshot Job | Extract frames from video at timestamps | `POST runpod.ai/.../run` | `{"input": {"queue": "screenshot_extraction", "jobs": [...]}}` |
| Start Transcription Job | Transcribe video/audio with whisperX | `POST runpod.ai/.../run` | `{"input": {"queue": "video_audio_transcription", "jobs": [...]}}` |
| Poll Status | Check job status; returns `output` when `COMPLETED` | `GET runpod.ai/.../status/{id}` | - |
| Cancel Job | Cancel a queued or in-progress job | `POST runpod.ai/.../cancel/{id}` | - |
| Get Screenshots | Retrieve all screenshots from a job (Option B) | `POST supabase/.../rpc/get_screenshots_by_job_id` | `{"p_job_id": "uuid"}` |
| Confirm Screenshots | Mark screenshots as permanent (won't auto-delete) | `POST supabase/.../rpc/confirm_screenshots` | `{"p_ids": ["uuid1", "uuid2"]}` |
| Preview Expired | List temp screenshots that would be deleted | `POST supabase/.../rpc/get_expired_temp_screenshots` | `{"hours_old": 48}` |
| Cleanup Temp | Delete expired temp screenshots from storage + DB | `POST supabase/.../functions/v1/cleanup-temp-screenshots` | `{"hours_old": 48}` |

### RunPod Status Values

| Status | Meaning | Has `output` |
|--------|---------|--------------|
| `IN_QUEUE` | Waiting for worker | No |
| `IN_PROGRESS` | Being processed | No |
| `COMPLETED` | Success | **Yes** |
| `FAILED` | Error | Yes |
| `CANCELLED` | Cancelled | No |
| `TIMED_OUT` | Timeout | Yes |
