# Supabase Functions Reference

Complete reference for all Supabase RPC functions used in this project.

## Quick Reference

| Function | Category | Description |
|----------|----------|-------------|
| `get_segment_by_transcription_id` | Segments | Get segment by transcription ID + segment_id |
| `get_segment_by_document_id` | Segments | Get segment by document ID + segment_id |
| `get_screenshots_by_job_id` | Screenshots | Get all screenshots for a job |
| `get_all_screenshots_for_document` | Screenshots | Get all screenshots for a document |
| `confirm_screenshots` | Screenshots | Confirm temp screenshots (temp → confirmed) |
| `get_expired_temp_screenshots` | Screenshots | List temp screenshots older than X hours |
| `get_unprocessed_transcriptions_for_screenshots` | Workflow | Get transcriptions needing screenshots |
| `complete_transcription_screenshots` | Workflow | Mark screenshot job as complete |
| `skip_transcription_screenshots` | Workflow | Mark as skipped (no screenshots needed) |
| `fail_transcription_screenshots` | Workflow | Mark screenshot job as failed |
| `reset_transcription_screenshots` | Workflow | Reset for reprocessing |
| `approve_screenshot` | AI Review | Mark screenshot as approved ✨ NEW |
| `reject_screenshot` | AI Review | Mark screenshot as rejected ✨ NEW |
| `get_screenshots_for_review` | AI Review | Get screenshots pending review ✨ NEW |
| `get_screenshot_candidates_for_segment` | AI Review | Get all candidates for a segment ✨ NEW |
| `cleanup_unapproved_screenshots` | AI Review | Delete rejected screenshots ✨ NEW |
| `complete_transcription_with_segment_screenshots` | AI Review | Complete with segment mapping ✨ NEW |
| `get_approved_screenshots_for_document` | AI Review | Get approved screenshots for frontend ✨ NEW |
| `mark_transcription_screenshots_reviewing` | AI Review | Transition to reviewing state |
| `mark_transcription_screenshots_processing` | RunPod | RunPod sets processing state on job receive |
| `mark_transcription_screenshots_extracted` | RunPod | RunPod sets extracted state after storing |
| `get_transcriptions_for_screenshot_review` | AI Review | Get transcriptions ready for review (status=extracted) |
| `get_stale_screenshot_transcriptions` | Monitoring | Find transcriptions stuck in any status |
| `reset_stale_screenshot_transcription` | Monitoring | Reset stuck transcription to retryable state |
| `push_screenshot_status` | Helper | Internal helper for status history array |
| `resolve_media_placeholders` | Frontend | Batch resolve media for inline placeholders |
| `pgmq_read` | Queue | Read messages from PGMQ queue |
| `pgmq_delete_one` | Queue | Delete (ack) a queue message |
| `pgmq_archive_one` | Queue | Archive a failed queue message |
| `dequeue_video_audio_transcription` | Queue | Dequeue transcription jobs (wrapper) |

---

## Environment Setup

All CURL examples assume these environment variables:

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-service-role-key"
```

---

## 1. Segment Retrieval Functions

### get_segment_by_transcription_id

Retrieves a specific segment from a transcription by its `segment_id`.

**Signature:**
```sql
get_segment_by_transcription_id(p_transcription_id UUID, p_segment_id INTEGER) → JSONB
```

**Parameters:**
- `p_transcription_id` - UUID of the transcription record
- `p_segment_id` - 1-based segment index

**Returns:** JSONB object with segment data, or NULL if not found.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_segment_by_transcription_id" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "550e8400-e29b-41d4-a716-446655440000",
    "p_segment_id": 1
  }'
```

**Response Example:**
```json
{
  "segment_id": 1,
  "start": 0.0,
  "end": 3.5,
  "text": "Hello world",
  "words": [
    {"word": "Hello", "start": 0.0, "end": 0.8},
    {"word": "world", "start": 0.9, "end": 3.5}
  ]
}
```

---

### get_segment_by_document_id

Retrieves a specific segment using the document ID instead of transcription ID.

**Signature:**
```sql
get_segment_by_document_id(p_document_id UUID, p_segment_id INTEGER) → JSONB
```

**Parameters:**
- `p_document_id` - UUID of the document record
- `p_segment_id` - 1-based segment index

**Returns:** JSONB object with segment data, or NULL if not found.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_segment_by_document_id" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_document_id": "660e8400-e29b-41d4-a716-446655440000",
    "p_segment_id": 5
  }'
```

---

## 2. Screenshot Job Functions

### get_screenshots_by_job_id

Retrieves all screenshots for a specific job with extracted metadata fields.

**Signature:**
```sql
get_screenshots_by_job_id(p_job_id TEXT) → TABLE(...)
```

**Parameters:**
- `p_job_id` - Job ID string (typically a UUID)

**Returns:** Table with columns: `id`, `storage_path`, `storage_bucket`, `content_type`, `size_bytes`, `source_url`, `title`, `document_id`, `metadata`, `created_at`, `timestamp_seconds`, `timestamp_formatted`, `width`, `height`, `platform`, `video_title`, `storage_status`

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_screenshots_by_job_id" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_job_id": "job-550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response Example:**
```json
[
  {
    "id": "770e8400-e29b-41d4-a716-446655440000",
    "storage_path": "screenshots/abc123.jpg",
    "storage_bucket": "public_media",
    "timestamp_seconds": 30.5,
    "timestamp_formatted": "00:00:30",
    "width": 1920,
    "height": 1080,
    "storage_status": "temp"
  }
]
```

---

### get_all_screenshots_for_document

Returns all screenshots associated with a document, ordered by timestamp. Used to show existing screenshots to AI agent before requesting new ones.

**Signature:**
```sql
get_all_screenshots_for_document(p_document_id UUID) → TABLE(...)
```

**Parameters:**
- `p_document_id` - UUID of the document

**Returns:** Table with columns: `id`, `storage_path`, `storage_bucket`, `content_type`, `size_bytes`, `title`, `created_at`, `timestamp_seconds`, `timestamp_formatted`, `width`, `height`, `platform`, `job_id`, `storage_status`, `public_url`

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_all_screenshots_for_document" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_document_id": "660e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response Example:**
```json
[
  {
    "id": "770e8400-e29b-41d4-a716-446655440000",
    "storage_path": "screenshots/abc123/30000.jpg",
    "storage_bucket": "public_media",
    "timestamp_seconds": 30.0,
    "timestamp_formatted": "00:00:30",
    "width": 1920,
    "height": 1080,
    "storage_status": "temp",
    "public_url": "/storage/v1/object/public/public_media/screenshots/abc123/30000.jpg"
  }
]
```

---

### confirm_screenshots

Confirms temporary screenshots by updating their storage_status from "temp" to "confirmed".

**Signature:**
```sql
confirm_screenshots(p_ids UUID[]) → INTEGER
```

**Parameters:**
- `p_ids` - Array of public_media UUIDs to confirm

**Returns:** Number of rows updated.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/confirm_screenshots" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_ids": [
      "770e8400-e29b-41d4-a716-446655440000",
      "880e8400-e29b-41d4-a716-446655440001"
    ]
  }'
```

**Response:** `2` (number confirmed)

---

### get_expired_temp_screenshots

Lists temporary screenshots older than a specified number of hours for cleanup.

**Signature:**
```sql
get_expired_temp_screenshots(hours_old INTEGER DEFAULT 48) → TABLE(...)
```

**Parameters:**
- `hours_old` - Age threshold in hours (default: 48)

**Returns:** Table with: `id`, `storage_path`, `storage_bucket`, `job_id`, `created_at`, `age_hours`

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_expired_temp_screenshots" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"hours_old": 24}'
```

---

## 3. Screenshot Workflow Functions

### get_unprocessed_transcriptions_for_screenshots

Retrieves transcriptions that need screenshot processing (status NULL, empty, or stuck in processing).

**Signature:**
```sql
get_unprocessed_transcriptions_for_screenshots(
  p_limit INTEGER DEFAULT 5,
  p_stuck_threshold_minutes INTEGER DEFAULT 30
) → TABLE(...)
```

**Parameters:**
- `p_limit` - Maximum number of results (default: 5)
- `p_stuck_threshold_minutes` - Minutes before "processing" is considered stuck (default: 30)

**Returns:** Table with: `transcription_id`, `document_id`, `canonical_url`, `title`, `segments`, `language`, `metadata`, `created_at`

**Note:** Uses `screenshots_status_history[0].at` for stuck detection.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_unprocessed_transcriptions_for_screenshots" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_limit": 10,
    "p_stuck_threshold_minutes": 60
  }'
```

---

### complete_transcription_screenshots

Marks a screenshot job as complete and updates metadata with job details.

**Signature:**
```sql
complete_transcription_screenshots(
  p_transcription_id UUID,
  p_runpod_job_id TEXT,
  p_internal_job_id TEXT,
  p_count INTEGER,
  p_failed_timestamps JSONB DEFAULT '[]'
) → BOOLEAN
```

**Parameters:**
- `p_transcription_id` - Transcription UUID
- `p_runpod_job_id` - RunPod job ID
- `p_internal_job_id` - Internal job tracking ID
- `p_count` - Number of screenshots generated
- `p_failed_timestamps` - Array of timestamps that failed (optional)

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/complete_transcription_screenshots" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "550e8400-e29b-41d4-a716-446655440000",
    "p_runpod_job_id": "runpod-abc123",
    "p_internal_job_id": "job-xyz789",
    "p_count": 15,
    "p_failed_timestamps": []
  }'
```

---

### skip_transcription_screenshots

Marks a transcription as skipped (AI determined no screenshots are needed).

**Signature:**
```sql
skip_transcription_screenshots(
  p_transcription_id UUID,
  p_reason TEXT DEFAULT 'No visual content identified'
) → BOOLEAN
```

**Parameters:**
- `p_transcription_id` - Transcription UUID
- `p_reason` - Reason for skipping (optional)

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/skip_transcription_screenshots" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "550e8400-e29b-41d4-a716-446655440000",
    "p_reason": "Audio-only podcast, no visual content"
  }'
```

---

### fail_transcription_screenshots

Marks a screenshot job as failed or timed out.

**Signature:**
```sql
fail_transcription_screenshots(
  p_transcription_id UUID,
  p_error TEXT,
  p_status TEXT DEFAULT 'failed'
) → BOOLEAN
```

**Parameters:**
- `p_transcription_id` - Transcription UUID
- `p_error` - Error message
- `p_status` - Either "failed" or "timeout" (default: "failed")

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/fail_transcription_screenshots" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "550e8400-e29b-41d4-a716-446655440000",
    "p_error": "RunPod worker timeout after 300s",
    "p_status": "timeout"
  }'
```

---

### reset_transcription_screenshots

Resets screenshot processing status to allow reprocessing. Does NOT delete existing screenshots.

**Signature:**
```sql
reset_transcription_screenshots(p_transcription_id UUID) → BOOLEAN
```

**Parameters:**
- `p_transcription_id` - Transcription UUID to reset

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/reset_transcription_screenshots" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

---

## 4. AI Screenshot Review Functions

These functions support the AI-powered screenshot review workflow introduced in v4.0.

### approve_screenshot

Marks a screenshot as approved and links it to a segment index.

**Signature:**
```sql
approve_screenshot(p_screenshot_id UUID, p_segment_id INTEGER, p_review_explanation TEXT DEFAULT NULL) → BOOLEAN
```

**Parameters:**
- `p_screenshot_id` - UUID of the screenshot in `public_media`
- `p_segment_id` - Segment ID this screenshot belongs to (1-based)
- `p_review_explanation` - Optional AI explanation for approval

**Returns:** `true` if updated successfully.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/approve_screenshot" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_screenshot_id": "770e8400-e29b-41d4-a716-446655440000",
    "p_segment_id": 3,
    "p_review_explanation": "Screenshot shows clear product interface matching segment description"
  }'
```

**Response:** `true`

---

### reject_screenshot

Marks a screenshot as rejected during AI review.

**Signature:**
```sql
reject_screenshot(p_screenshot_id UUID, p_rejection_reason TEXT DEFAULT 'Screenshot does not match segment content') → BOOLEAN
```

**Parameters:**
- `p_screenshot_id` - UUID of the screenshot in `public_media`
- `p_rejection_reason` - Reason for rejection

**Returns:** `true` if updated successfully.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/reject_screenshot" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_screenshot_id": "770e8400-e29b-41d4-a716-446655440000",
    "p_rejection_reason": "Shows only talking head, no visual content"
  }'
```

**Response:** `true`

---

### get_screenshots_for_review

Returns screenshots for a document that have not been reviewed yet.

**Signature:**
```sql
get_screenshots_for_review(p_document_id UUID) → TABLE(...)
```

**Parameters:**
- `p_document_id` - UUID of the document

**Returns:** Table with columns: `id`, `storage_path`, `storage_bucket`, `timestamp_seconds`, `segment_id`, `segment_text`, `extraction_reason`, `offset_seconds`, `job_id`, `public_url`, `created_at`

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_screenshots_for_review" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_document_id": "660e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response Example:**
```json
[
  {
    "id": "770e8400-e29b-41d4-a716-446655440000",
    "storage_path": "screenshots/abc123/30000.jpg",
    "timestamp_seconds": 30.5,
    "segment_id": 1,
    "segment_text": "As you can see in this chart, our Q3 results show significant growth",
    "extraction_reason": "Chart showing Q3 results",
    "public_url": "/storage/v1/object/public/public_media/screenshots/abc123/30000.jpg"
  }
]
```

---

### get_screenshot_candidates_for_segment

Returns all screenshot candidates for a specific segment (used for multi-offset retry review).

**Signature:**
```sql
get_screenshot_candidates_for_segment(p_document_id UUID, p_segment_id INTEGER) → TABLE(...)
```

**Parameters:**
- `p_document_id` - UUID of the document
- `p_segment_id` - Segment ID (1-based)

**Returns:** Table with columns: `id`, `storage_path`, `timestamp_seconds`, `offset_seconds`, `public_url`, `approved`, `review_status`

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_screenshot_candidates_for_segment" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_document_id": "660e8400-e29b-41d4-a716-446655440000",
    "p_segment_id": 3
  }'
```

**Response Example:**
```json
[
  {"id": "uuid-1", "offset_seconds": -3, "approved": null},
  {"id": "uuid-2", "offset_seconds": -1, "approved": null},
  {"id": "uuid-3", "offset_seconds": 1, "approved": null},
  {"id": "uuid-4", "offset_seconds": 3, "approved": null}
]
```

---

### cleanup_unapproved_screenshots

Deletes all non-approved screenshots for a document. Returns storage paths for cleanup.

**Signature:**
```sql
cleanup_unapproved_screenshots(p_document_id UUID) → TABLE(deleted_id UUID, storage_path TEXT, storage_bucket TEXT)
```

**Parameters:**
- `p_document_id` - UUID of the document

**Returns:** Table with deleted screenshot info for Supabase Storage cleanup.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/cleanup_unapproved_screenshots" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_document_id": "660e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response Example:**
```json
[
  {"deleted_id": "uuid-1", "storage_path": "screenshots/abc/30000.jpg", "storage_bucket": "public_media"},
  {"deleted_id": "uuid-2", "storage_path": "screenshots/abc/31000.jpg", "storage_bucket": "public_media"}
]
```

**Note:** Use the returned paths to delete files from Supabase Storage.

---

### complete_transcription_with_segment_screenshots

Marks transcription complete with segment-to-screenshot mappings.

**Signature:**
```sql
complete_transcription_with_segment_screenshots(
  p_transcription_id UUID,
  p_runpod_job_id TEXT,
  p_segment_screenshots JSONB,
  p_approved_count INTEGER,
  p_rejected_count INTEGER DEFAULT 0
) → BOOLEAN
```

**Parameters:**
- `p_transcription_id` - UUID of the transcription
- `p_runpod_job_id` - RunPod job ID
- `p_segment_screenshots` - JSONB array: `[{segment_id, screenshot_id, timestamp_seconds, reason}, ...]`
- `p_approved_count` - Number of approved screenshots
- `p_rejected_count` - Number of rejected screenshots

**Returns:** `true` if updated successfully.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/complete_transcription_with_segment_screenshots" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "550e8400-e29b-41d4-a716-446655440000",
    "p_runpod_job_id": "runpod-abc123",
    "p_segment_screenshots": [
      {"segment_id": 1, "screenshot_id": "uuid-1", "timestamp_seconds": 30.5, "reason": "Chart"},
      {"segment_id": 3, "screenshot_id": "uuid-2", "timestamp_seconds": 135.4, "reason": "Demo"}
    ],
    "p_approved_count": 5,
    "p_rejected_count": 2
  }'
```

**Response:** `true`

---

### get_approved_screenshots_for_document

Returns all approved screenshots for a document (for frontend display).

**Signature:**
```sql
get_approved_screenshots_for_document(p_document_id UUID) → TABLE(...)
```

**Parameters:**
- `p_document_id` - UUID of the document

**Returns:** Table with columns: `id`, `storage_path`, `storage_bucket`, `timestamp_seconds`, `segment_id`, `extraction_reason`, `public_url`, `width`, `height`

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_approved_screenshots_for_document" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_document_id": "660e8400-e29b-41d4-a716-446655440000"
  }'
```

---

### mark_transcription_screenshots_reviewing

Transitions a transcription from "extracted" to "reviewing" state. Sets `screenshots_review_started_at` timestamp.

**Signature:**
```sql
mark_transcription_screenshots_reviewing(p_transcription_id UUID) → BOOLEAN
```

**Parameters:**
- `p_transcription_id` - UUID of the transcription

**Returns:** `true` if updated successfully.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/mark_transcription_screenshots_reviewing" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response:** `true`

---

### get_transcriptions_for_screenshot_review

Returns transcriptions ready for AI screenshot review (status=extracted or stuck in reviewing).

**Signature:**
```sql
get_transcriptions_for_screenshot_review(
  p_limit INTEGER DEFAULT 10,
  p_stuck_threshold_minutes INTEGER DEFAULT 60
) → TABLE(...)
```

**Parameters:**
- `p_limit` - Maximum records to return (default: 10)
- `p_stuck_threshold_minutes` - How long in "reviewing" before considered stuck (default: 60)

**Returns:** Table with: `transcription_id`, `document_id`, `canonical_url`, `title`, `segments`, `language`, `metadata`, `screenshots_extracted_count`, `status_changed_at`, `created_at`

**Note:** Uses `screenshots_status_history[0].at` for all timestamp checks.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_transcriptions_for_screenshot_review" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_limit": 10,
    "p_stuck_threshold_minutes": 30
  }'
```

**Response Example:**
```json
[
  {
    "transcription_id": "550e8400-e29b-41d4-a716-446655440000",
    "document_id": "660e8400-e29b-41d4-a716-446655440000",
    "canonical_url": "https://youtube.com/watch?v=abc123",
    "title": "Video Title",
    "screenshots_extracted_count": 5,
    "status_changed_at": "2025-12-29T02:34:05Z"
  }
]
```

---

### get_stale_screenshot_transcriptions

Finds transcriptions stuck in a specified screenshot workflow status for too long. Works with any status.

**Signature:**
```sql
get_stale_screenshot_transcriptions(
  p_status TEXT,                                -- Required: status to check
  p_stale_threshold_minutes INTEGER DEFAULT 30,
  p_limit INTEGER DEFAULT 50
) → TABLE(...)
```

**Parameters:**
- `p_status` - **Required.** Status to check: `"processing"`, `"reviewing"`, `"extracted"`, `"completed"`, etc.
- `p_stale_threshold_minutes` - How long in state before considered stuck (default: 30)
- `p_limit` - Max records to return (default: 50)

**Returns:** Table with columns: `transcription_id`, `document_id`, `canonical_url`, `title`, `screenshots_status`, `runpod_job_id`, `status_started_at`, `stuck_duration_minutes`, `status_history`, `metadata`

**Note:** Uses `screenshots_status_history[0].at` for timing - works uniformly for any status.

**CURL Examples:**
```bash
# Get records stuck in "reviewing" for > 30 min (default)
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_stale_screenshot_transcriptions" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_status": "reviewing"
  }'

# Get records stuck in "processing" for > 10 min
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_stale_screenshot_transcriptions" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_status": "processing",
    "p_stale_threshold_minutes": 10
  }'

# Get records stuck in "extracted" (waiting for review) for > 60 min
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_stale_screenshot_transcriptions" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_status": "extracted",
    "p_stale_threshold_minutes": 60
  }'
```

**Response Example:**
```json
[
  {
    "transcription_id": "550e8400-e29b-41d4-a716-446655440000",
    "document_id": "660e8400-e29b-41d4-a716-446655440000",
    "canonical_url": "https://youtube.com/watch?v=abc123",
    "title": "Video Title",
    "screenshots_status": "reviewing",
    "runpod_job_id": "runpod-abc123",
    "status_started_at": "2025-12-28T10:00:00Z",
    "stuck_duration_minutes": 713
  }
]
```

---

### reset_stale_screenshot_transcription

Resets a stuck transcription back to a retryable state.

**Signature:**
```sql
reset_stale_screenshot_transcription(
  p_transcription_id UUID,
  p_reset_to_status TEXT DEFAULT 'extracted',
  p_reason TEXT DEFAULT 'Reset due to stale state'
) → BOOLEAN
```

**Parameters:**
- `p_transcription_id` - UUID of the transcription to reset
- `p_reset_to_status` - Target status (default: `"extracted"` to re-enter review queue)
- `p_reason` - Reason for reset (stored in metadata for debugging)

**Returns:** `true` if reset successfully.

**Notes:**
- Only works on transcriptions in `"processing"` or `"reviewing"` status
- Pushes to `screenshots_status_history` array with `reset_from` and `reason` for audit trail

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/reset_stale_screenshot_transcription" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "550e8400-e29b-41d4-a716-446655440000",
    "p_reset_to_status": "extracted",
    "p_reason": "WF3 crashed during review"
  }'
```

**Response:** `true`

---

## 5. Frontend Media Functions

These functions support frontend rendering of content with embedded media.

### resolve_media_placeholders

Batch resolve media placeholders from various source tables. Used by frontend to fetch all media referenced in `documents.content` inline placeholders.

**Signature:**
```sql
resolve_media_placeholders(p_placeholders JSONB) → TABLE(
  source TEXT,
  identifier TEXT,
  storage_path TEXT,
  storage_bucket TEXT,
  is_public BOOLEAN,
  alt_text TEXT,
  width INTEGER,
  height INTEGER
)
```

**Parameters:**
- `p_placeholders` - JSONB array of `{source, id}` objects

**Returns:** Table with storage info for URL construction:
- `source` - The source table name (e.g., "public_media")
- `identifier` - The original ID (UUID)
- `storage_path` - Path within the storage bucket
- `storage_bucket` - Supabase storage bucket name
- `is_public` - If TRUE, use public URL; if FALSE, use signed URL
- `alt_text` - Alt text for accessibility
- `width`, `height` - Image dimensions if available

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/resolve_media_placeholders" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_placeholders": [
      {"source": "public_media", "id": "550e8400-e29b-41d4-a716-446655440000"},
      {"source": "public_media", "id": "660e8400-e29b-41d4-a716-446655440001"}
    ]
  }'
```

**Response Example:**
```json
[
  {
    "source": "public_media",
    "identifier": "550e8400-e29b-41d4-a716-446655440000",
    "storage_path": "screenshots/abc123/30500.jpg",
    "storage_bucket": "public_media",
    "is_public": false,
    "alt_text": "Chart showing growth metrics",
    "width": 1920,
    "height": 1080
  },
  {
    "source": "public_media",
    "identifier": "660e8400-e29b-41d4-a716-446655440001",
    "storage_path": "screenshots/abc123/65200.jpg",
    "storage_bucket": "public_media",
    "is_public": false,
    "alt_text": "Product demo interface",
    "width": 1920,
    "height": 1080
  }
]
```

> **Note:** The `public_media` bucket is PRIVATE despite its name. `is_public: false` means the frontend must use signed URLs. Only `thumbnails` and `screenshots` buckets return `is_public: true`.

**Frontend Usage:**

This function is used to resolve `${{source:id}}$` placeholders in `documents.content`:

```typescript
// Extract placeholders from content
const placeholders = content.matchAll(/\$\{\{(\w+):([^}]+)\}\}\$/g);

// Build RPC input
const rpcInput = [...placeholders].map(m => ({ source: m[1], id: m[2] }));

// Call RPC
const { data } = await supabase.rpc('resolve_media_placeholders', {
  p_placeholders: rpcInput
});

// Build URLs based on is_public flag
for (const row of data) {
  if (row.is_public) {
    url = `${SUPABASE_URL}/storage/v1/object/public/${row.storage_bucket}/${row.storage_path}`;
  } else {
    // Use signed URL for private buckets
    const { data } = await supabase.storage.from(row.storage_bucket).createSignedUrl(row.storage_path, 3600);
    url = data.signedUrl;
  }
}
```

**Extensibility:**

To add a new source table:
1. Add ID extraction for the new source in the function
2. Add a `UNION ALL` query for the new source table
3. Update the `is_public` CASE statement for new buckets

See migration file `20260110_resolve_media_placeholders.sql` for implementation details.

---

## 6. PGMQ Queue Functions

These functions are part of the [PGMQ extension](https://github.com/tembo-io/pgmq) for PostgreSQL message queues.

### pgmq_read

Reads messages from a PGMQ queue without deleting them.

**Signature:**
```sql
pgmq_read(queue_name TEXT, vt INTEGER, qty INTEGER) → TABLE(...)
```

**Parameters:**
- `queue_name` - Name of the queue
- `vt` - Visibility timeout in seconds (message hidden from other readers)
- `qty` - Number of messages to read

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/pgmq_read" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "queue_name": "video_audio_transcription",
    "vt": 1800,
    "qty": 10
  }'
```

---

### pgmq_delete_one

Deletes (acknowledges) a single message from the queue after successful processing.

**Signature:**
```sql
pgmq_delete_one(queue_name TEXT, msg_id BIGINT) → BOOLEAN
```

**Parameters:**
- `queue_name` - Name of the queue
- `msg_id` - Message ID to delete

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/pgmq_delete_one" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "queue_name": "video_audio_transcription",
    "msg_id": 12345
  }'
```

---

### pgmq_archive_one

Archives a message (moves to archive table) after max retries exceeded.

**Signature:**
```sql
pgmq_archive_one(queue_name TEXT, msg_id BIGINT) → BOOLEAN
```

**Parameters:**
- `queue_name` - Name of the queue
- `msg_id` - Message ID to archive

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/pgmq_archive_one" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "queue_name": "video_audio_transcription",
    "msg_id": 12345
  }'
```

---

### dequeue_video_audio_transcription

Custom wrapper function for dequeuing transcription jobs with visibility timeout. Wraps `pgmq.read()` for the `video_audio_transcription` queue.

> **Note:** This function was created directly in Supabase (not in tracked migrations).

**Signature:**
```sql
dequeue_video_audio_transcription(vt_seconds INTEGER DEFAULT 1800, qty INTEGER DEFAULT 25) → TABLE(...)
```

**Parameters:**
- `vt_seconds` - Visibility timeout in seconds (default: 1800)
- `qty` - Number of jobs to dequeue (default: 25)

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/dequeue_video_audio_transcription" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "vt_seconds": 1800,
    "qty": 5
  }'
```

**Response Example:**
```json
[
  {
    "msg_id": 12345,
    "read_ct": 1,
    "enqueued_at": "2025-12-15T10:30:00Z",
    "message": {
      "document_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
]
```

---

## 7. Status Values Reference

### Screenshot Status (`metadata.screenshots_status`)

| Status | Who Sets It | Description |
|--------|-------------|-------------|
| `NULL` / empty | - | Not yet processed |
| `processing` | **RunPod** | RunPod received job, extraction starting |
| `extracted` | **RunPod** | Screenshots stored in `public_media`, ready for review |
| `reviewing` | WF3 | AI review in progress |
| `completed` | WF3 | Successfully completed |
| `skipped` | WF2 | AI determined no screenshots needed |
| `failed` | RunPod/WF3 | Processing failed |
| `timeout` | RunPod/WF3 | Processing timed out |

### Status History Array (`metadata.screenshots_status_history`)

All status changes are tracked in a JSONB array for full audit trail. Newest entries are prepended (index 0 = most recent).

**Structure:**
```json
{
  "screenshots_status": "completed",
  "screenshots_status_history": [
    {"status": "completed", "at": "2025-12-29T02:34:22Z", "approved_count": 3, "rejected_count": 2},
    {"status": "reviewing", "at": "2025-12-29T02:34:12Z"},
    {"status": "extracted", "at": "2025-12-29T02:34:05Z", "count": 5, "job_id": "runpod-abc123"},
    {"status": "processing", "at": "2025-12-29T02:33:41Z", "job_id": "runpod-abc123"}
  ]
}
```

**Extra fields per status:**
| Status | Extra Fields |
|--------|--------------|
| `processing` | `job_id` |
| `extracted` | `job_id`, `count` |
| `reviewing` | (none) |
| `completed` | `job_id`, `approved_count`, `rejected_count` |
| `skipped` | `reason` |
| `failed`/`timeout` | `error` |
| (reset) | `reason`, `reset_from` |
| (migrated) | `migrated: true` |

### Screenshot Review Status (`public_media.metadata.review_status`)

| Status | Description |
|--------|-------------|
| `NULL` | Not yet reviewed |
| `approved` | Screenshot approved by AI reviewer |
| `rejected` | Screenshot rejected by AI reviewer |

### Storage Status (`metadata.storage_status`)

| Status | Description |
|--------|-------------|
| `temp` | Temporary, subject to cleanup |
| `confirmed` | Confirmed for permanent storage |

---

## Migration Files

All functions are defined in these migration files:

| File | Functions |
|------|-----------|
| `20251218_screenshot_jobs.sql` | `get_screenshots_by_job_id`, `confirm_screenshots`, `get_expired_temp_screenshots` |
| `20251221_screenshot_workflow_functions.sql` | `get_all_screenshots_for_document` |
| `20251222_screenshot_workflow_functions_v2.sql` | `get_unprocessed_transcriptions_for_screenshots`, `complete_transcription_screenshots`, `skip_transcription_screenshots`, `fail_transcription_screenshots`, `reset_transcription_screenshots` |
| `20251225_segment_retrieval_functions.sql` | `get_segment_by_transcription_id`, `get_segment_by_document_id` |
| `20251226_screenshot_review_functions.sql` | `approve_screenshot`, `reject_screenshot`, `get_screenshots_for_review`, `get_screenshot_candidates_for_segment`, `cleanup_unapproved_screenshots`, `complete_transcription_with_segment_screenshots`, `get_approved_screenshots_for_document`, `mark_transcription_screenshots_reviewing` |
| `20251228_rename_segment_index_to_segment_id.sql` | Updated functions to use `segment_id` instead of `segment_index` |
| `20251229_segment_id_only.sql` | Removed `segment_index` backwards compatibility |
| `20260103_screenshot_functions_clean.sql` | Clean functions using `segment_id` and `timestamp_seconds` |
| `20251230_get_transcriptions_for_review.sql` | `get_transcriptions_for_screenshot_review` |
| `20251231_runpod_screenshot_status_functions.sql` | `mark_transcription_screenshots_processing`, `mark_transcription_screenshots_extracted`, updated `get_transcriptions_for_screenshot_review` |
| `20260104_get_stale_screenshot_transcriptions.sql` | `get_stale_screenshot_transcriptions`, `reset_stale_screenshot_transcription` |
| `20260105_generic_stale_detection.sql` | Updated `get_stale_screenshot_transcriptions` with generic status input and minutes threshold |
| `20260106_complete_stale_detection.sql` | Added missing status mappings (skipped, failed, timeout) |
| `20260107_add_segment_text_to_review.sql` | Added `segment_text` to `get_screenshots_for_review` |
| `20260108_status_history_array.sql` | **Major refactor:** Added `screenshots_status_history` array for audit trail, `push_screenshot_status` helper, updated all status-setting functions |
| `20260109_update_functions_to_use_status_history.sql` | Updated `get_unprocessed_transcriptions_for_screenshots` and `get_transcriptions_for_screenshot_review` to use status history array |
| `20260110_resolve_media_placeholders.sql` | `resolve_media_placeholders` for frontend inline placeholder resolution |

### Functions Created Directly in Supabase

These functions exist in the remote database but are not tracked in migration files:

| Function | Description |
|----------|-------------|
| `dequeue_video_audio_transcription` | PGMQ wrapper for video/audio transcription queue |
| `pgmq_read`, `pgmq_delete_one`, `pgmq_archive_one` | PGMQ extension functions |

---

## System Alerts

The `system_alerts` table provides a centralized alerting mechanism for server/RunPod issues.

### Table Schema

```sql
CREATE TABLE system_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type TEXT NOT NULL,           -- 'youtube_auth_failure', 'startup_failure', etc.
    severity TEXT NOT NULL DEFAULT 'warning',  -- 'info', 'warning', 'critical'
    message TEXT NOT NULL,              -- Human-readable message
    context JSONB DEFAULT '{}',         -- Flexible metadata
    acknowledged_at TIMESTAMPTZ,        -- NULL = unacknowledged
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Alert Types

| Type | Severity | When Triggered |
|------|----------|----------------|
| `youtube_auth_failure` | critical | YouTube cookie refresh fails (2FA, security challenge) |
| `startup_failure` | warning/critical | Server/RunPod startup component fails |
| `job_failed` | warning | Job processing fails (for future use) |

### Python Usage

```python
from app.services.supabase_service import (
    send_alert,
    send_youtube_auth_alert,
    send_startup_alert,
    acknowledge_alert,
    get_unacknowledged_alerts
)

# Generic alert (with 60-min spam prevention cooldown)
send_alert(
    alert_type="custom_alert",
    message="Something went wrong",
    severity="warning",
    context={"details": "..."},
    cooldown_minutes=60  # Don't repeat same alert within 60 mins
)

# YouTube auth failure (uses 60-min cooldown)
send_youtube_auth_alert(
    error_message="2FA challenge detected",
    context={"email": "user@example.com"}
)

# Startup issue (uses 30-min cooldown)
send_startup_alert(
    component="whisperx",
    error_message="Failed to load model",
    severity="warning"
)

# Get unacknowledged alerts
alerts = get_unacknowledged_alerts(severity="critical")

# Acknowledge an alert
acknowledge_alert(alert_id="uuid-here")
```

### CURL Examples

```bash
# Get unacknowledged critical alerts
curl -X GET "$SUPABASE_URL/rest/v1/system_alerts?acknowledged_at=is.null&severity=eq.critical&order=created_at.desc" \
  -H "apikey: $SUPABASE_KEY" \
  -H "Authorization: Bearer $SUPABASE_KEY"

# Acknowledge an alert
curl -X PATCH "$SUPABASE_URL/rest/v1/system_alerts?id=eq.YOUR_ALERT_ID" \
  -H "apikey: $SUPABASE_KEY" \
  -H "Authorization: Bearer $SUPABASE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"acknowledged_at": "2026-01-04T12:00:00Z"}'

# Get alerts from last 24 hours
curl -X GET "$SUPABASE_URL/rest/v1/system_alerts?created_at=gte.$(date -u -v-1d +%Y-%m-%dT%H:%M:%SZ)&order=created_at.desc" \
  -H "apikey: $SUPABASE_KEY" \
  -H "Authorization: Bearer $SUPABASE_KEY"
```

### n8n Workflow Integration

To get notified of critical alerts:

1. **Trigger**: Schedule trigger (every 5-15 minutes)
2. **Supabase Node**: Query `system_alerts` where `acknowledged_at IS NULL AND severity = 'critical'`
3. **Filter**: Only proceed if alerts exist
4. **Slack/Email Node**: Send notification with alert details
5. **Supabase Node**: Acknowledge the alerts after notification
