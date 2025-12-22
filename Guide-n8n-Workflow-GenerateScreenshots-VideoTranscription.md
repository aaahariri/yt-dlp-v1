# n8n Workflow: AI-Driven Screenshot Generation from Video Transcriptions

This guide documents a two-workflow system that automatically analyzes video transcriptions, identifies visually important moments using AI, and generates screenshots via RunPod.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Webhook Security](#webhook-security)
- [Workflow Architecture](#workflow-architecture)
- [Workflow 1: Scheduler](#workflow-1-scheduler-document-transcriptions-to-extract-screenshots)
  - [Node 1: Schedule Trigger](#node-1-schedule-trigger) ✅
  - [Node 2: Query Unprocessed Transcriptions](#node-2-query-unprocessed-transcriptions) ✅
  - [Node 3: IF - Has Transcriptions?](#node-3-if---has-transcriptions) ✅
  - [Node 4: HTTP Request - Trigger Worker Workflow](#node-4-http-request---trigger-worker-workflow)
- [Workflow 2: Worker](#workflow-2-workflow-extract-relevant-screenshots-from-transcription)
  - [Node 1: Webhook Trigger](#node-1-webhook-trigger)
  - [Node 2: AI Agent - Analyze Transcription](#node-2-ai-agent---analyze-transcription)
  - [Node 3: IF - Screenshots Needed?](#node-3-if---screenshots-needed)
  - [Node 4: POST RunPod - Start Screenshot Job](#node-4-post-runpod---start-screenshot-job)
  - [Node 5: Update Supabase - Mark Processing](#node-5-update-supabase---mark-processing)
  - [Node 6: Initialize Loop Counter](#node-6-initialize-loop-counter)
  - [Node 7: Wait 5 Minutes](#node-7-wait-5-minutes)
  - [Node 8: GET RunPod Status](#node-8-get-runpod-status)
  - [Node 9: Switch - Job Status](#node-9-switch---job-status)
  - [Node 10: Process Completed Results](#node-10-process-completed-results)
  - [Node 11: Update Supabase - Mark Complete](#node-11-update-supabase---mark-complete)
  - [Node 12: Handle Failure](#node-12-handle-failure)
  - [Node 13: Increment Loop Counter](#node-13-increment-loop-counter)
  - [Node 14: IF - Loop Limit Reached?](#node-14-if---loop-limit-reached)
  - [Node 15: Handle Timeout](#node-15-handle-timeout)
- [State Management](#state-management)
- [Limits and Guidelines](#limits-and-guidelines)
- [Supabase Functions](#supabase-functions)
- [Error Handling](#error-handling)
- [Testing](#testing)

---

## Overview

**Purpose:** Automatically generate screenshots from videos at visually important moments identified by AI analysis of transcriptions.

**Architecture:** Two separate n8n workflows connected via webhook:

| Workflow | Name | Purpose |
|----------|------|---------|
| **Scheduler** | `Scheduler-Document Transcriptions to Extract Screenshots` | Finds unprocessed transcriptions, dispatches to worker |
| **Worker** | `Workflow-Extract Relevant Screenshots from Transcription` | Processes single transcription: AI analysis → RunPod → completion |

**Why Two Workflows?**
- **Parallel Processing:** n8n webhooks process items concurrently (vs. sequential loop)
- **Error Isolation:** One failed transcription doesn't affect others
- **Better Monitoring:** Each transcription is a separate execution with its own logs
- **Scalability:** Worker can handle multiple concurrent requests

**Flow Summary:**
1. **Scheduler** triggers every 15-30 minutes
2. **Scheduler** queries `document_transcriptions` for unprocessed records
3. **Scheduler** sends each record to **Worker** via webhook
4. **Worker** AI Agent analyzes transcription to identify visual moments
5. **Worker** submits screenshot job to RunPod
6. **Worker** polls for completion (5 min intervals, max 5 attempts)
7. **Worker** marks transcription as processed with screenshot metadata

**Use Cases for Screenshots:**
- Speaker explaining charts, graphs, or diagrams
- Product demonstrations or physical items
- Step-by-step tutorials with UI/screen content
- Key data points or conclusions with visual aids
- Trading/financial analysis with chart references

---

## Prerequisites

### Environment Variables (n8n Credentials)

| Variable | Description | Example |
|----------|-------------|---------|
| `RUNPOD_API_KEY` | RunPod API key | `rp_xxxxxxxx` |
| `RUNPOD_ENDPOINT_ID` | Your RunPod endpoint ID | `abc123def456` |
| `SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase anon/public key | `eyJhbGc...` |
| `OPENAI_API_KEY` | OpenAI API key (for AI Agent) | `sk-...` |
| `WEBHOOK_SECRET` | Shared secret for internal webhooks | `your-secure-random-string` |

### Required Supabase Setup

1. **Tables:** `documents`, `document_transcriptions`, `public_media`
2. **Function:** `get_unprocessed_transcriptions_for_screenshots()` (see [Supabase Functions](#supabase-functions))
3. **Function:** `get_screenshots_by_job_id()` (already exists)

---

## Webhook Security

When connecting two n8n workflows via webhook, you should secure the connection to prevent unauthorized access.

### Recommended: Header-Based Authentication

**Step 1: Create a shared secret**
```bash
# Generate a secure random string
openssl rand -hex 32
# Example output: a1b2c3d4e5f6...
```

**Step 2: Store in n8n credentials**
1. Go to n8n → Credentials → Add Credential
2. Choose "Header Auth"
3. Name: `Internal Webhook Auth`
4. Header Name: `X-Webhook-Secret`
5. Header Value: `your-generated-secret`

**Step 3: Configure Worker Webhook (receiving end)**

In the Webhook node settings:
- **Authentication:** Header Auth
- **Credential:** Select your "Internal Webhook Auth" credential
- **Header Name:** `X-Webhook-Secret`

**Step 4: Configure Scheduler HTTP Request (sending end)**

In the HTTP Request node:
- **Authentication:** Predefined Credential Type → Header Auth
- **Credential:** Select your "Internal Webhook Auth" credential

### Alternative Options

| Method | Security | Setup Complexity | Notes |
|--------|----------|------------------|-------|
| **Header Auth** (Recommended) | High | Low | Best balance of security and simplicity |
| **Basic Auth** | High | Low | Built-in n8n support, username/password |
| **Path Obfuscation** | Medium | Low | Use UUID in webhook path (e.g., `/webhook/abc123-uuid`) |
| **Execute Workflow Node** | Highest | None | No HTTP, but loses parallel processing benefits |

### Security Checklist

- [ ] Use HTTPS for webhook URLs (n8n cloud does this automatically)
- [ ] Store secrets in n8n credentials (not hardcoded)
- [ ] Use Header Auth or Basic Auth for internal webhooks
- [ ] Consider IP restrictions if self-hosted

---

## Workflow Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  WORKFLOW 1: Scheduler-Document Transcriptions to Extract Screenshots   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│  [1] Schedule   │ Every 15-30 min                                    ✅ DONE
│     Trigger     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  [2] Query      │ get_unprocessed_transcriptions_for_screenshots()   ✅ DONE
│  Supabase       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  [3] IF Has     │───No───► END (nothing to process)                  ✅ DONE
│  Transcriptions │
└────────┬────────┘
         │ Yes (for each item)
         ▼
┌─────────────────┐
│  [4] HTTP POST  │ Send each transcription to Worker webhook         ✅ DONE
│  to Worker      │ (with Header Auth)
└─────────────────┘
         │
         │ HTTP POST (async, fire-and-forget)
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  WORKFLOW 2: Workflow-Extract Relevant Screenshots from Transcription   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│  [1] Webhook    │ Receives single transcription               ✅ DONE
│  Trigger        │ (with Header Auth validation)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  [2] AI Agent   │ Analyze segments, identify visual moments
│  (Claude/GPT)   │ Output: timestamps + reasons
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  [3] IF         │───No───► [3b] Mark Skipped ───► END
│  Screenshots    │
│  Needed?        │
└────────┬────────┘
         │ Yes
         ▼
┌─────────────────┐
│  [4] POST       │ RunPod /run - screenshot_extraction queue
│  RunPod Job     │ Returns: runpod_job_id
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  [5] Update     │ Set metadata.screenshots_status = 'processing'
│  Supabase       │ Store runpod_job_id, screenshots_requested_at
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  [6] Init       │ loop_count = 0
│  Loop Counter   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐◄─────────────────────────────────┐
│  [7] Wait       │                                  │
│  5 minutes      │                                  │
└────────┬────────┘                                  │
         │                                           │
         ▼                                           │
┌─────────────────┐                                  │
│  [8] GET        │ RunPod /status/{job_id}          │
│  RunPod Status  │                                  │
└────────┬────────┘                                  │
         │                                           │
         ▼                                           │
┌─────────────────┐                                  │
│  [9] Switch     │                                  │
│  on status      │                                  │
├─────────────────┤                                  │
│ COMPLETED ──────┼──► [10] Process Results          │
│ FAILED ─────────┼──► [12] Handle Failure           │
│ TIMED_OUT ──────┼──► [12] Handle Failure           │
│ IN_QUEUE ───────┼──► [13] Increment Counter ───────┤
│ IN_PROGRESS ────┼──► [13] Increment Counter ───────┘
└─────────────────┘

┌─────────────────┐     ┌─────────────────┐
│  [10] Process   │────►│  [11] Update    │───► END (success)
│  Results        │     │  Mark Complete  │
└─────────────────┘     └─────────────────┘

┌─────────────────┐
│  [12] Handle    │───► Update metadata with error ───► END (failed)
│  Failure        │
└─────────────────┘

┌─────────────────┐     ┌─────────────────┐
│  [13] Increment │────►│  [14] IF        │
│  loop_count++   │     │  count >= 5?    │
└─────────────────┘     └────────┬────────┘
                                 │
                        ┌────────┴────────┐
                        │ No              │ Yes
                        ▼                 ▼
                   Back to [7]      ┌─────────────────┐
                                    │  [15] Timeout   │───► END (timeout)
                                    │  Error          │
                                    └─────────────────┘
```

---

## Workflow 1: Scheduler-Document Transcriptions to Extract Screenshots

This workflow runs on a schedule, finds unprocessed transcriptions, and dispatches each to the worker workflow.

### Node 1: Schedule Trigger

**Status:** ✅ Completed

**Type:** Schedule Trigger

**Settings:**
- **Trigger Interval:** Every 15 minutes (adjust based on volume)
- **Cron Expression:** `*/15 * * * *`

**Notes:**
- Start with 30 minutes during testing
- Reduce to 15 minutes for production
- Consider time-of-day restrictions if needed

---

### Node 2: Query Unprocessed Transcriptions

**Status:** ✅ Completed

**Type:** HTTP Request

**Method:** `POST`

**URL:**
```
{{ $env.SUPABASE_URL }}/rest/v1/rpc/get_unprocessed_transcriptions_for_screenshots
```

**Headers:**
```json
{
  "Authorization": "Bearer {{ $env.SUPABASE_ANON_KEY }}",
  "apikey": "{{ $env.SUPABASE_ANON_KEY }}",
  "Content-Type": "application/json"
}
```

**Body:**
```json
{
  "p_limit": 5,
  "p_stuck_threshold_minutes": 30
}
```

**Expected Response:**
```json
[
  {
    "transcription_id": "uuid-1",
    "document_id": "uuid-2",
    "canonical_url": "https://youtube.com/watch?v=xxx",
    "title": "Video Title",
    "segments": [{"start": 0, "end": 5, "text": "..."}],
    "language": "en",
    "metadata": {}
  }
]
```

---

### Node 3: IF - Has Transcriptions?

**Status:** ✅ Completed

**Type:** IF

**Condition:**
```javascript
{{ $json.length > 0 }}
```

**True Branch:** Continue to Node 4 (HTTP Request to Worker)
**False Branch:** End workflow (nothing to process)

---

### Node 4: HTTP Request - Trigger Worker Workflow

**Type:** HTTP Request

**Purpose:** Send each transcription to the Worker workflow via webhook. n8n will automatically iterate over all items from Node 2.

**Method:** `POST`

**URL:**
```
{{ $env.N8N_WEBHOOK_URL }}/webhook/extract-screenshots
```

Or if using n8n cloud:
```
https://your-instance.app.n8n.cloud/webhook/extract-screenshots
```

**Authentication:**
- **Type:** Predefined Credential Type → Header Auth
- **Credential:** Select your "Internal Webhook Auth" credential

**Headers:**
```json
{
  "Content-Type": "application/json"
}
```

**Body (JSON):**
```json
{
  "transcription_id": "{{ $json.transcription_id }}",
  "document_id": "{{ $json.document_id }}",
  "canonical_url": "{{ $json.canonical_url }}",
  "title": "{{ $json.title }}",
  "segments": {{ JSON.stringify($json.segments) }},
  "language": "{{ $json.language }}",
  "metadata": {{ JSON.stringify($json.metadata) }},
  "created_at": "{{ $json.created_at }}"
}
```

**Settings:**
- **Batch Size:** Leave default (processes all items)
- **Options → Ignore Response Body:** ✅ (fire-and-forget)
- **Options → Timeout:** 10000 (10 seconds, just for the webhook trigger)

**Notes:**
- n8n automatically iterates over all items from Node 2
- Each item triggers a separate Worker workflow execution
- Worker executions run in parallel (n8n handles concurrency)
- Scheduler doesn't wait for Worker to complete (async/fire-and-forget)

---

## Workflow 2: Workflow-Extract Relevant Screenshots from Transcription

This workflow receives a single transcription via webhook and processes it end-to-end.

### Node 1: Webhook Trigger

**Type:** Webhook

**Settings:**
- **HTTP Method:** POST
- **Path:** `extract-screenshots`
- **Authentication:** Header Auth
- **Credential:** Select your "Internal Webhook Auth" credential

**Full Webhook URL:**
```
https://your-n8n-instance/webhook/extract-screenshots
```

**Responds With:**
- **Response Mode:** Immediately (don't wait for workflow to finish)
- **Response Code:** 200

**Output Data:**
The incoming JSON body is available as `{{ $json }}`:
```json
{
  "transcription_id": "uuid-1",
  "document_id": "uuid-2",
  "canonical_url": "https://youtube.com/watch?v=xxx",
  "title": "Video Title",
  "segments": [{"start": 0, "end": 5, "text": "..."}],
  "language": "en",
  "metadata": {},
  "created_at": "2025-12-21T10:00:00Z"
}
```

---

### Node 2: AI Agent - Analyze Transcription

**Type:** HTTP Request (to OpenAI) or OpenAI Node

**Method:** `POST`

**URL:** `https://api.openai.com/v1/chat/completions`

**Headers:**
```json
{
  "Authorization": "Bearer {{ $env.OPENAI_API_KEY }}",
  "Content-Type": "application/json"
}
```

**Body:**
```json
{
  "model": "gpt-4o-mini",
  "response_format": { "type": "json_object" },
  "messages": [
    {
      "role": "system",
      "content": "You are a video content analyst. Your task is to identify moments in a video transcription where a visual screenshot would be valuable for understanding.\n\n## When to Request Screenshots\n\nRequest screenshots when the speaker is:\n1. **Explaining visual content**: Charts, graphs, diagrams, slides, screens\n2. **Demonstrating something physical**: Products, tools, equipment, gestures\n3. **Showing a process**: Step-by-step tutorials, workflows, UI walkthroughs\n4. **Referencing on-screen elements**: \"As you can see here...\", \"Look at this...\", \"On the left side...\"\n5. **Key moments**: Title cards, important data points, conclusions with visuals\n\n## When NOT to Request Screenshots\n\nDo NOT request screenshots for:\n- Pure audio/talking head content with no visual reference\n- Generic transitions or filler content\n- Moments where speaker is just talking without visual aids\n- Redundant moments (don't capture same visual multiple times)\n\n## Output Format\n\nReturn a JSON object:\n```json\n{\n  \"screenshots_needed\": true,\n  \"count\": 3,\n  \"requests\": [\n    {\n      \"timestamp\": \"00:02:15,000\",\n      \"reason\": \"Speaker showing trading chart with support/resistance levels\",\n      \"context\": \"Explaining entry point strategy\"\n    }\n  ]\n}\n```\n\nIf no screenshots are needed:\n```json\n{\n  \"screenshots_needed\": false,\n  \"count\": 0,\n  \"reason\": \"Talking head content with no visual demonstrations\"\n}\n```\n\n## Limits\n- Maximum 10 screenshots per video\n- Minimum 30 seconds apart (avoid redundant captures)\n- Focus on the MOST valuable moments if many candidates exist"
    },
    {
      "role": "user",
      "content": "Analyze this video transcription and identify moments where screenshots would be valuable.\n\n**Video Title:** {{ $json.title }}\n**Video URL:** {{ $json.canonical_url }}\n\n**Transcription Segments:**\n{{ JSON.stringify($json.segments) }}\n\nReturn your analysis as JSON."
    }
  ],
  "temperature": 0.3,
  "max_tokens": 2000
}
```

**Parse Response:**
```javascript
// In a Code node or expression
{{ JSON.parse($json.choices[0].message.content) }}
```

---

### Node 3: IF - Screenshots Needed?

**Type:** IF

**Condition:**
```javascript
{{ $json.screenshots_needed === true && $json.count > 0 }}
```

**True Branch:** Continue to Node 4 (Submit RunPod Job)
**False Branch:** Go to Node 3b (Mark as Skipped), then END

> **Important:** When AI determines no screenshots are needed, you MUST mark the transcription as "skipped" in Supabase (Node 3b). Otherwise, it will be re-processed on the next scheduler run.

---

### Node 3b: Handle Skipped (AI says no screenshots needed)

If AI Agent returns `screenshots_needed: false`, mark as skipped:

**Option 1: Code node**
```javascript
const metadata = $('Webhook Trigger').item.json.metadata || {};
const aiResponse = $('AI Agent Parse').item.json;

const newMetadata = {
  ...metadata,
  screenshots_status: "skipped",
  screenshots_skipped_reason: aiResponse.reason || "No visual content identified",
  screenshots_skipped_at: new Date().toISOString()
};

return { json: { metadata: newMetadata, transcription_id: $('Webhook Trigger').item.json.transcription_id } };
```

**Option 2: Supabase Function (Recommended)**

**Type:** HTTP Request

**Method:** `POST`

**URL:**
```
{{ $env.SUPABASE_URL }}/rest/v1/rpc/skip_transcription_screenshots
```

**Body:**
```json
{
  "p_transcription_id": "{{ $('Webhook Trigger').item.json.transcription_id }}",
  "p_reason": "{{ $json.reason || 'No visual content identified' }}"
}
```

Then workflow ENDs (success - marked as skipped).

---

### Node 4: POST RunPod - Start Screenshot Job

**Type:** HTTP Request

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

**Body:**
```json
{
  "input": {
    "queue": "screenshot_extraction",
    "jobs": [{
      "video_url": "{{ $('Webhook Trigger').item.json.canonical_url }}",
      "timestamps": {{ $json.requests.map(r => r.timestamp) }},
      "quality": 2,
      "document_id": "{{ $('Webhook Trigger').item.json.document_id }}"
    }]
  }
}
```

**Expected Response:**
```json
{
  "id": "runpod-job-id-abc123",
  "status": "IN_QUEUE"
}
```

**Store for later:**
- `runpod_job_id`: `{{ $json.id }}`

---

### Node 5: Update Supabase - Mark Processing

**Type:** HTTP Request

**Method:** `PATCH`

**URL:**
```
{{ $env.SUPABASE_URL }}/rest/v1/document_transcriptions?id=eq.{{ $('Webhook Trigger').item.json.transcription_id }}
```

**Headers:**
```json
{
  "Authorization": "Bearer {{ $env.SUPABASE_ANON_KEY }}",
  "apikey": "{{ $env.SUPABASE_ANON_KEY }}",
  "Content-Type": "application/json",
  "Prefer": "return=representation"
}
```

**Body:**
```json
{
  "metadata": {
    "screenshots_status": "processing",
    "screenshots_runpod_job_id": "{{ $('POST RunPod Job').item.json.id }}",
    "screenshots_requested_at": "{{ $now.toISO() }}",
    "screenshots_requested_count": {{ $('AI Agent Parse').item.json.count }},
    "screenshots_requests": {{ $('AI Agent Parse').item.json.requests }}
  }
}
```

**Note:** You may need to merge with existing metadata. Use a Code node if needed:
```javascript
const existingMetadata = $('Webhook Trigger').item.json.metadata || {};
const newMetadata = {
  ...existingMetadata,
  screenshots_status: "processing",
  screenshots_runpod_job_id: $('POST RunPod Job').item.json.id,
  screenshots_requested_at: new Date().toISOString(),
  screenshots_requested_count: $('AI Agent Parse').item.json.count,
  screenshots_requests: $('AI Agent Parse').item.json.requests
};
return { metadata: newMetadata };
```

---

### Node 6: Initialize Loop Counter

**Type:** Set

**Values:**
```json
{
  "loop_count": 0,
  "runpod_job_id": "{{ $('POST RunPod Job').item.json.id }}",
  "transcription_id": "{{ $('Webhook Trigger').item.json.transcription_id }}",
  "document_id": "{{ $('Webhook Trigger').item.json.document_id }}"
}
```

---

### Node 7: Wait 5 Minutes

**Type:** Wait

**Settings:**
- **Wait Time:** 5 minutes
- **Unit:** Minutes

**Notes:**
- First poll at 5 minutes gives job time to start
- Typical screenshot jobs take 2-10 minutes depending on video length

---

### Node 8: GET RunPod Status

**Type:** HTTP Request

**Method:** `GET`

**URL:**
```
https://api.runpod.ai/v2/{{ $env.RUNPOD_ENDPOINT_ID }}/status/{{ $json.runpod_job_id }}
```

**Headers:**
```json
{
  "Authorization": "Bearer {{ $env.RUNPOD_API_KEY }}"
}
```

**Expected Response (when completed):**
```json
{
  "id": "runpod-job-id-abc123",
  "status": "COMPLETED",
  "output": {
    "ok": true,
    "summary": {"total": 1, "completed": 1, "failed": 0},
    "results": [{
      "job_id": "internal-uuid-550e8400",
      "status": "completed",
      "video_url": "https://youtube.com/...",
      "total_extracted": 5,
      "failed_timestamps": []
    }]
  }
}
```

---

### Node 9: Switch - Job Status

**Type:** Switch

**Field to Match:** `{{ $json.status }}`

**Cases:**

| Case | Value | Route To |
|------|-------|----------|
| COMPLETED | `COMPLETED` | Node 10 (Process Results) |
| FAILED | `FAILED` | Node 12 (Handle Failure) |
| TIMED_OUT | `TIMED_OUT` | Node 12 (Handle Failure) |
| CANCELLED | `CANCELLED` | Node 12 (Handle Failure) |
| Default | (IN_QUEUE, IN_PROGRESS) | Node 13 (Increment Counter) |

---

### Node 10: Process Completed Results

**Type:** Code (JavaScript)

**Code:**
```javascript
const statusResponse = $input.all()[0].json;
const loopData = $('Initialize Loop Counter').item.json;

// Extract results from RunPod output
const output = statusResponse.output;
const results = output.results[0];

return {
  status: "completed",
  runpod_job_id: statusResponse.id,
  internal_job_id: results.job_id,
  total_extracted: results.total_extracted,
  failed_timestamps: results.failed_timestamps,
  transcription_id: loopData.transcription_id,
  document_id: loopData.document_id
};
```

**Optional: Query Supabase for full screenshot details**

If you need the full screenshot metadata (URLs, dimensions, etc.), add an HTTP Request:

**Method:** `POST`

**URL:**
```
{{ $env.SUPABASE_URL }}/rest/v1/rpc/get_screenshots_by_job_id
```

**Body:**
```json
{
  "p_job_id": "{{ $json.internal_job_id }}"
}
```

---

### Node 11: Update Supabase - Mark Complete

**Type:** HTTP Request

**Method:** `PATCH`

**URL:**
```
{{ $env.SUPABASE_URL }}/rest/v1/document_transcriptions?id=eq.{{ $json.transcription_id }}
```

**Headers:**
```json
{
  "Authorization": "Bearer {{ $env.SUPABASE_ANON_KEY }}",
  "apikey": "{{ $env.SUPABASE_ANON_KEY }}",
  "Content-Type": "application/json"
}
```

**Body (use Code node to merge metadata):**
```javascript
const existing = $('Webhook Trigger').item.json.metadata || {};
const processedData = $('Process Completed Results').item.json;

// Build new job entry
const newJob = {
  runpod_job_id: processedData.runpod_job_id,
  internal_job_id: processedData.internal_job_id,
  count: processedData.total_extracted,
  completed_at: new Date().toISOString(),
  failed_timestamps: processedData.failed_timestamps || []
};

// Append to existing jobs array (supports multiple screenshot jobs per transcription)
const existingJobs = existing.screenshots_jobs || [];
const allJobs = [...existingJobs, newJob];

// Calculate total count across all jobs
const totalCount = allJobs.reduce((sum, job) => sum + (job.count || 0), 0);

const newMetadata = {
  ...existing,
  screenshots_status: "completed",  // Only status, no screenshots_generated boolean
  screenshots_total_count: totalCount,
  screenshots_jobs: allJobs,
  screenshots_completed_at: new Date().toISOString()
};

return { json: { metadata: newMetadata } };
```

**Alternative: Use Supabase Function**
```bash
POST /rest/v1/rpc/complete_transcription_screenshots
{
  "p_transcription_id": "uuid",
  "p_runpod_job_id": "runpod-abc123",
  "p_internal_job_id": "internal-uuid",
  "p_count": 5,
  "p_failed_timestamps": []
}
```

**Note:** This structure supports running multiple screenshot jobs for the same transcription (e.g., if you need to request additional screenshots later). Each job is appended to the `screenshots_jobs` array.

Then workflow ENDs (success - screenshots completed).

---

### Node 12: Handle Failure

**Type:** Code (JavaScript)

**Code:**
```javascript
const statusResponse = $input.all()[0].json;
const loopData = $('Initialize Loop Counter').item.json;

const errorMessage = statusResponse.output?.error ||
                     `Job ${statusResponse.status}: ${JSON.stringify(statusResponse.output)}`;

return {
  status: "failed",
  error: errorMessage,
  runpod_status: statusResponse.status,
  transcription_id: loopData.transcription_id,
  document_id: loopData.document_id
};
```

**Then update Supabase:**

**Method:** `PATCH`

**URL:**
```
{{ $env.SUPABASE_URL }}/rest/v1/document_transcriptions?id=eq.{{ $json.transcription_id }}
```

**Body:**
```json
{
  "metadata": {
    "screenshots_status": "failed",
    "screenshots_error": "{{ $json.error }}",
    "screenshots_failed_at": "{{ $now.toISO() }}"
  }
}
```

**Alternative: Use Supabase Function**
```bash
POST /rest/v1/rpc/fail_transcription_screenshots
{
  "p_transcription_id": "{{ $json.transcription_id }}",
  "p_error": "{{ $json.error }}",
  "p_status": "failed"
}
```

Then workflow ENDs (failed).

---

### Node 13: Increment Loop Counter

**Type:** Code (JavaScript)

**Code:**
```javascript
const current = $('Initialize Loop Counter').item.json;
// Or from previous iteration:
// const current = $input.all()[0].json;

return {
  loop_count: (current.loop_count || 0) + 1,
  runpod_job_id: current.runpod_job_id,
  transcription_id: current.transcription_id,
  document_id: current.document_id
};
```

---

### Node 14: IF - Loop Limit Reached?

**Type:** IF

**Condition:**
```javascript
{{ $json.loop_count >= 5 }}
```

**True Branch:** Node 15 (Handle Timeout)
**False Branch:** Back to Node 7 (Wait 5 Minutes)

---

### Node 15: Handle Timeout

**Type:** Code + HTTP Request

**Code:**
```javascript
const loopData = $input.all()[0].json;

return {
  status: "timeout",
  error: `Job timed out after ${loopData.loop_count} attempts (${loopData.loop_count * 5} minutes)`,
  transcription_id: loopData.transcription_id,
  document_id: loopData.document_id,
  runpod_job_id: loopData.runpod_job_id
};
```

**Then update Supabase:**

**Method:** `PATCH`

**Body:**
```json
{
  "metadata": {
    "screenshots_status": "timeout",
    "screenshots_error": "{{ $json.error }}",
    "screenshots_failed_at": "{{ $now.toISO() }}"
  }
}
```

**Alternative: Use Supabase Function**
```bash
POST /rest/v1/rpc/fail_transcription_screenshots
{
  "p_transcription_id": "{{ $json.transcription_id }}",
  "p_error": "{{ $json.error }}",
  "p_status": "timeout"
}
```

Then workflow ENDs (timeout).

---

## State Management

### Metadata Schema in `document_transcriptions`

The workflow uses the `metadata` JSONB column to track screenshot generation state:

```json
// State: Not processed (initial)
{
  // No screenshot-related keys, or screenshots_status is NULL
}

// State: Processing
{
  "screenshots_status": "processing",
  "screenshots_runpod_job_id": "runpod-abc123",
  "screenshots_requested_at": "2025-12-21T10:00:00Z",
  "screenshots_requested_count": 5,
  "screenshots_requests": [
    {"timestamp": "00:02:15,000", "reason": "...", "context": "..."}
  ]
}

// State: Completed (single job)
{
  "screenshots_status": "completed",
  "screenshots_total_count": 5,
  "screenshots_jobs": [
    {
      "runpod_job_id": "runpod-abc123",
      "internal_job_id": "550e8400-uuid",
      "count": 5,
      "completed_at": "2025-12-21T10:05:00Z",
      "failed_timestamps": []
    }
  ],
  "screenshots_completed_at": "2025-12-21T10:05:00Z"
}

// State: Completed (multiple jobs - e.g., requested more screenshots later)
{
  "screenshots_status": "completed",
  "screenshots_total_count": 12,
  "screenshots_jobs": [
    {
      "runpod_job_id": "runpod-abc123",
      "internal_job_id": "550e8400-uuid-1",
      "count": 5,
      "completed_at": "2025-12-21T10:05:00Z",
      "failed_timestamps": []
    },
    {
      "runpod_job_id": "runpod-def456",
      "internal_job_id": "550e8400-uuid-2",
      "count": 7,
      "completed_at": "2025-12-21T14:30:00Z",
      "failed_timestamps": ["00:15:30,000"]
    }
  ],
  "screenshots_completed_at": "2025-12-21T14:30:00Z"
}

// State: Skipped (AI determined no screenshots needed)
{
  "screenshots_status": "skipped",
  "screenshots_skipped_reason": "Talking head content with no visual demonstrations",
  "screenshots_skipped_at": "2025-12-21T10:02:00Z"
}

// State: Failed
{
  "screenshots_status": "failed",
  "screenshots_error": "Job FAILED: Video download error",
  "screenshots_failed_at": "2025-12-21T10:05:00Z"
}

// State: Timeout
{
  "screenshots_status": "timeout",
  "screenshots_error": "Job timed out after 5 attempts (25 minutes)",
  "screenshots_failed_at": "2025-12-21T10:25:00Z"
}
```

### Query Logic

To find unprocessed transcriptions (simplified - uses only `screenshots_status`):
```sql
WHERE
  -- Has a canonical_url (needed for screenshots)
  d.canonical_url IS NOT NULL
  AND d.canonical_url != ''
  -- Either: not yet processed OR stuck in processing
  AND (
    -- Never processed (status is NULL or not set)
    (
      dt.metadata IS NULL
      OR dt.metadata->>'screenshots_status' IS NULL
      OR dt.metadata->>'screenshots_status' = ''
    )
    -- OR stuck in processing for too long
    OR (
      dt.metadata->>'screenshots_status' = 'processing'
      AND (dt.metadata->>'screenshots_requested_at')::timestamptz < NOW() - INTERVAL '30 minutes'
    )
  )
```

> **Note:** The outer `AND` ensures both conditions (has URL + needs processing) must be true. The inner `OR` handles both "never processed" and "stuck" cases.

### State Machine

```
NULL ──► processing ──► completed (screenshots generated)
                    └──► skipped   (AI says no screenshots needed)
                    └──► failed    (job error)
                    └──► timeout   (poll limit reached)

failed/timeout ──► (manual reset) ──► NULL
```

---

## Limits and Guidelines

### Recommended Settings

| Parameter | Value | Reason |
|-----------|-------|--------|
| **Scheduler Interval** | 15-30 min | Balance between responsiveness and load |
| **Batch Size** | 5 transcriptions | Avoid overwhelming RunPod |
| **Max Screenshots/Video** | 10 | Storage costs, relevance |
| **Min Time Between Screenshots** | 30 seconds | Avoid redundant frames |
| **Poll Interval** | 5 minutes | Typical job: 2-10 min |
| **Max Poll Attempts** | 5 (25 min total) | Timeout protection |
| **Stuck Threshold** | 30 minutes | Re-process stuck jobs |

### AI Agent Guidelines

**Good candidates for screenshots:**
- "As you can see on the chart..."
- "Let me show you this diagram..."
- "Here's the product we're reviewing..."
- "On my screen, you'll notice..."
- "This is what the interface looks like..."

**Poor candidates (skip):**
- "Welcome to my channel..."
- "Don't forget to subscribe..."
- "Let me tell you about..."
- Generic talking without visual reference

---

## Supabase Functions

**Migration Files:**
1. `supabase/migrations/20251221_screenshot_workflow_functions.sql` (v1 - base functions)
2. `supabase/migrations/20251221_screenshot_workflow_functions_v2.sql` (v2 - updates)

> **Important:** Run BOTH migrations in order. v1 creates all functions, v2 updates them to use simplified state management (only `screenshots_status`, removed redundant `screenshots_generated` boolean).

### Summary of Available Functions

| Function | Purpose | Used In |
|----------|---------|---------|
| `get_unprocessed_transcriptions_for_screenshots` | Get transcriptions needing screenshots | Node 2 |
| `get_all_screenshots_for_document` | Get existing screenshots for a document | Optional: show AI existing shots |
| `mark_transcription_screenshots_processing` | Atomically claim a transcription | Node 8 (alternative) |
| `complete_transcription_screenshots` | Mark job complete, append to jobs array | Node 14 (alternative) |
| `skip_transcription_screenshots` | Mark as skipped (AI says no screenshots needed) | Node 14b |
| `fail_transcription_screenshots` | Mark job as failed/timeout | Node 15/18 (alternative) |
| `reset_transcription_screenshots` | Reset status for retry | Manual retry |

---

### Function 1: get_unprocessed_transcriptions_for_screenshots

**Purpose:** Returns transcriptions that need screenshot processing.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `p_limit` | INTEGER | 5 | Max transcriptions to return |
| `p_stuck_threshold_minutes` | INTEGER | 30 | Minutes after which "processing" is considered stuck |

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_unprocessed_transcriptions_for_screenshots" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_limit": 5,
    "p_stuck_threshold_minutes": 30
  }'
```

**Response:**
```json
[
  {
    "transcription_id": "uuid-1",
    "document_id": "uuid-2",
    "canonical_url": "https://youtube.com/watch?v=xxx",
    "title": "Video Title",
    "segments": [{"start": 0, "end": 5, "text": "..."}],
    "language": "en",
    "metadata": {},
    "created_at": "2025-12-21T10:00:00Z"
  }
]
```

---

### Function 2: get_all_screenshots_for_document

**Purpose:** Returns all screenshots for a document (useful to show AI existing screenshots).

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_all_screenshots_for_document" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_document_id": "uuid-of-document"
  }'
```

**Response:**
```json
[
  {
    "id": "screenshot-uuid",
    "storage_path": "screenshots/abc123/30000.jpg",
    "storage_bucket": "public_media",
    "timestamp_seconds": 30.0,
    "timestamp_formatted": "00:00:30,000",
    "width": 1920,
    "height": 1080,
    "job_id": "internal-job-uuid",
    "public_url": "/storage/v1/object/public/public_media/screenshots/abc123/30000.jpg"
  }
]
```

**Build full URL:** `${SUPABASE_URL}${public_url}`

---

### Function 3: mark_transcription_screenshots_processing

**Purpose:** Atomically claim a transcription for processing (prevents race conditions).

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/mark_transcription_screenshots_processing" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "uuid-of-transcription",
    "p_runpod_job_id": "runpod-abc123",
    "p_requested_count": 5,
    "p_requests": [{"timestamp": "00:02:15,000", "reason": "Chart explanation"}]
  }'
```

**Response:** `true` (claimed successfully) or `false` (already processing)

---

### Function 4: complete_transcription_screenshots

**Purpose:** Mark job complete and append to jobs array.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/complete_transcription_screenshots" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "uuid-of-transcription",
    "p_runpod_job_id": "runpod-abc123",
    "p_internal_job_id": "550e8400-internal-uuid",
    "p_count": 5,
    "p_failed_timestamps": []
  }'
```

**Response:** `true` (success)

---

### Function 5: skip_transcription_screenshots

**Purpose:** Mark transcription as skipped (AI determined no screenshots needed).

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/skip_transcription_screenshots" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "uuid-of-transcription",
    "p_reason": "Talking head content with no visual demonstrations"
  }'
```

**Response:** `true` (success)

**Use Case:** When the AI Agent analyzes a transcription and determines there are no visual moments worth capturing (e.g., podcast, audio-only content, talking head).

---

### Function 6: fail_transcription_screenshots

**Purpose:** Mark job as failed or timed out.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/fail_transcription_screenshots" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "uuid-of-transcription",
    "p_error": "Job FAILED: Video download error",
    "p_status": "failed"
  }'
```

**Response:** `true` (success)

---

### Function 7: reset_transcription_screenshots

**Purpose:** Reset screenshot status to allow reprocessing.

**CURL Example:**
```bash
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/reset_transcription_screenshots" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "p_transcription_id": "uuid-of-transcription"
  }'
```

**Response:** `true` (success)

**Note:** This does NOT delete existing screenshots from `public_media`. Use this to:
- Retry failed jobs
- Request additional screenshots for a video

---

## Error Handling

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `No transcriptions found` | All processed or none exist | Normal - workflow ends |
| `RunPod job FAILED` | Video download or processing error | Check video URL validity, retry later |
| `RunPod job TIMED_OUT` | Worker took too long | Increase timeout or check video length |
| `AI returned no screenshots` | Content is audio-only | Normal - mark as no screenshots needed |
| `Stuck in processing` | Previous run interrupted | Automatic recovery after 30 min |

### Retry Logic

Failed jobs are NOT automatically retried to avoid infinite loops. To retry:

1. **Manual retry:** Use the reset function
```bash
# Using Supabase function (recommended)
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/reset_transcription_screenshots" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"p_transcription_id": "transcription-uuid"}'
```

Or via SQL:
```sql
-- Single transcription
SELECT reset_transcription_screenshots('transcription-uuid');
```

2. **Batch retry failed jobs (older than 24 hours):**
```sql
-- Reset all failed/timeout jobs older than 24 hours
UPDATE document_transcriptions
SET metadata = metadata
  - 'screenshots_status'
  - 'screenshots_error'
  - 'screenshots_failed_at'
  - 'screenshots_runpod_job_id'
  - 'screenshots_requested_at'
  - 'screenshots_requested_count'
  - 'screenshots_requests',
  updated_at = NOW()
WHERE metadata->>'screenshots_status' IN ('failed', 'timeout')
  AND (metadata->>'screenshots_failed_at')::timestamptz < NOW() - INTERVAL '24 hours';
```

---

## Testing

### Step 1: Test Supabase Function

```bash
# Should return unprocessed transcriptions
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/get_unprocessed_transcriptions_for_screenshots" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"p_limit": 1}'
```

### Step 2: Test AI Agent Prompt

Use the OpenAI playground or a simple script to test the prompt with sample transcription data.

### Step 3: Test RunPod Job Manually

```bash
# Start job
curl -X POST "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/run" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "queue": "screenshot_extraction",
      "jobs": [{
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "timestamps": ["00:00:30,000", "00:01:00,000"],
        "quality": 2
      }]
    }
  }'

# Poll status
curl "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/status/JOB_ID" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

### Step 4: Test Full Workflow

1. Trigger workflow manually in n8n
2. Watch execution logs
3. Verify Supabase metadata updates
4. Check screenshots in `public_media` table

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-12-21 | 2.0 | **Architecture change:** Split into two workflows (Scheduler + Worker) connected via webhook for parallel processing. Added webhook security section. Renumbered all nodes. |
| 2025-12-21 | 1.1 | Simplified state management: use only `screenshots_status`, removed redundant `screenshots_generated` boolean. Added `skip_transcription_screenshots` function for "skipped" state. |
| 2025-12-21 | 1.0 | Initial workflow design |

