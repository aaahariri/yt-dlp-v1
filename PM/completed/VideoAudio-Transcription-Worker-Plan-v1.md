# Video/Audio Transcription — Python Pull Worker Plan (from current state)

## Current state (already done)

* Queue **`video_audio_transcription`** exists.
* Trigger enqueues on `documents` INSERT when `media_format IN ('video','audio')`.
* Supabase RPCs exist for:

  * dequeue (`dequeue_video_audio_transcription`)
  * ack helpers (`pgmq_delete_one`, `pgmq_archive_one`)
* Edge function **`consume-video-audio-transcription`** exists **but is not scheduled**.

---

## Decision: keep or delete the Edge function?

**Keep it.** You don’t need to delete it.

* Since it’s not scheduled, it won’t run or incur cost.
* It’s useful as a **manual fallback** / temporary batch dispatcher later (e.g., when you want to drain queue without running the worker).
* If you want a cleaner project later, you can delete it once your Python worker is stable, but there’s no urgency.

---

## Step 1 — Pick the pull method (recommended)

### Option A (recommended): Python calls the existing RPC `dequeue_video_audio_transcription`

Pros: simplest, keeps PGMQ access behind a controlled function.

### Option B: Python calls `pgmq.read(...)` directly

Pros: one less RPC.
Cons: needs direct SQL and tighter privileges.

**Recommendation:** Option A.

---

## Step 2 — Implement the Python worker loop (no cron)

Run a long-lived process that continuously:

1. Dequeues a small batch
2. Processes each message
3. Acks (delete) on success or archives on too many attempts
4. Sleeps briefly when no messages

### Suggested settings

* `BATCH_SIZE`: 5–25
* `VT_SECONDS`: 1800–3600 (30–60 min; pick > worst-case transcription)
* `MAX_RETRIES`: 5
* `IDLE_SLEEP_SECONDS`: 2–10 with simple backoff

### Worker logic per message

For each job `{ msg_id, read_ct, message.document_id }`:

1. **Idempotency guard**: only process if `documents.processing_status = 'pending'`

   * If not pending → **ack delete** message (it’s stale/duplicate)
2. Set `documents.processing_status = 'processing'`
3. Fetch media pointer (e.g., `canonical_url` or `metadata.media_url`)
4. Call your internal `POST /transcribe` endpoint
5. Upsert into `document_transcriptions` (unique `document_id`)
6. Mark `documents.processing_status = 'completed'`, set `processed_at = now()`
7. **Ack delete** message

On failure:

* If `read_ct >= MAX_RETRIES`:

  * Set document to `error` and write `processing_error`
  * **Ack archive** message
* Else:

  * Set document back to `pending` (optional but recommended)
  * **Do not ack** (message will reappear after VT)

---

## Step 3 — Minimal Python code skeleton (Supabase client)

> This is intentionally minimal; you’ll plug in your actual `/transcribe` call and the exact media URL field.

```python
import os, time, requests
from datetime import datetime, timezone
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
TRANSCRIBE_URL = os.environ["TRANSCRIBE_URL"]

QUEUE_NAME = "video_audio_transcription"
VT_SECONDS = int(os.getenv("VT_SECONDS", "1800"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
IDLE_SLEEP = float(os.getenv("IDLE_SLEEP_SECONDS", "5"))

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

while True:
    # 1) Dequeue
    resp = sb.rpc("dequeue_video_audio_transcription", {
        "vt_seconds": VT_SECONDS,
        "qty": BATCH_SIZE
    }).execute()

    rows = resp.data or []
    if not rows:
        time.sleep(IDLE_SLEEP)
        continue

    for m in rows:
        msg_id = m["msg_id"]
        read_ct = m.get("read_ct", 1)
        document_id = (m.get("message") or {}).get("document_id")

        if not document_id:
            sb.rpc("pgmq_archive_one", {"queue_name": QUEUE_NAME, "msg_id": msg_id}).execute()
            continue

        try:
            # 2) Claim only if pending
            claim = sb.table("documents").update({
                "processing_status": "processing",
                "updated_at": now_iso()
            }).eq("id", document_id).eq("processing_status", "pending").execute()

            if not claim.data:
                # stale/duplicate message
                sb.rpc("pgmq_delete_one", {"queue_name": QUEUE_NAME, "msg_id": msg_id}).execute()
                continue

            doc = sb.table("documents").select("id, canonical_url, metadata, lang").eq("id", document_id).single().execute().data
            media_url = doc.get("canonical_url") or (doc.get("metadata") or {}).get("media_url")
            if not media_url:
                raise RuntimeError("Missing media URL")

            # 3) Transcribe
            tr = requests.post(TRANSCRIBE_URL, json={"url": media_url}, timeout=600)
            tr.raise_for_status()
            tr_json = tr.json()

            segments = tr_json["segments"]  # JSON array
            language = tr_json.get("language")
            confidence = tr_json.get("confidence")
            meta = tr_json.get("metadata", {})

            # 4) Upsert transcription
            sb.table("document_transcriptions").upsert({
                "document_id": document_id,
                "segments": segments,
                "language": language,
                "source": "ai",
                "confidence_score": confidence,
                "metadata": meta,
                "updated_at": now_iso()
            }, on_conflict="document_id").execute()

            # 5) Mark completed
            sb.table("documents").update({
                "processing_status": "completed",
                "processed_at": now_iso(),
                "processing_error": None,
                "updated_at": now_iso()
            }).eq("id", document_id).execute()

            # 6) Ack delete
            sb.rpc("pgmq_delete_one", {"queue_name": QUEUE_NAME, "msg_id": msg_id}).execute()

        except Exception as e:
            err = str(e)
            if read_ct >= MAX_RETRIES:
                sb.table("documents").update({
                    "processing_status": "error",
                    "processing_error": err,
                    "updated_at": now_iso()
                }).eq("id", document_id).execute()
                sb.rpc("pgmq_archive_one", {"queue_name": QUEUE_NAME, "msg_id": msg_id}).execute()
            else:
                sb.table("documents").update({
                    "processing_status": "pending",
                    "processing_error": err,
                    "updated_at": now_iso()
                }).eq("id", document_id).execute()
                # No ack => retry after VT
```

---

## Step 4 — Run it reliably (no cron)

Pick one:

* **Docker**: run the worker container with `restart: unless-stopped`
* **systemd** (Linux): `Restart=on-failure` + logs via journald

Minimum reliability checklist:

* Auto-restart on crash
* Start on boot
* Centralized logs

---

## Step 5 — End-to-end test checklist

1. Insert a test row in `documents` with `media_format='video'` (and a valid `canonical_url` or `metadata.media_url`).
2. Confirm a queue message exists (or just watch the worker logs after dequeue).
3. Watch document transition: `pending → processing → completed`.
4. Confirm `document_transcriptions` row exists and `segments` is real JSON (not a string).
5. Confirm message is deleted from queue (no repeat processing).

---

## Step 6 — Optional hardening (later)

* Add `LISTEN/NOTIFY` wake-up to reduce idle reads (keep PGMQ as truth).
* Add a 3-hour “re-enqueue pending” safety job only if you observe missed work.
* Add structured logging + basic metrics (processed count, errors, avg duration).
