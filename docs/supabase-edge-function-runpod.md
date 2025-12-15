# Supabase Edge Function → RunPod Integration

This document provides the Edge Function code for calling RunPod's serverless endpoint instead of the FastAPI server directly.

## Why RunPod?

| Problem | Solution |
|---------|----------|
| Edge Functions have timeout limits | RunPod `/run` returns immediately |
| Long transcriptions may timeout | Processing happens async in RunPod worker |
| Results needed in response | Results saved directly to Supabase DB |

## Edge Function Code

Replace your existing Edge Function that calls the Python API with this version:

```typescript
// supabase/functions/process-transcription-queue/index.ts

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const RUNPOD_ENDPOINT_ID = Deno.env.get("RUNPOD_ENDPOINT_ID")!;
const RUNPOD_API_KEY = Deno.env.get("RUNPOD_API_KEY")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

serve(async (req) => {
  try {
    // Initialize Supabase client
    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

    // Read jobs from PGMQ queue
    const { data: jobs, error: queueError } = await supabase.rpc("pgmq_read", {
      queue_name: "video_audio_transcription",
      vt: 1800, // 30 min visibility timeout
      qty: 10,  // batch size
    });

    if (queueError) {
      console.error("Queue read error:", queueError);
      return new Response(JSON.stringify({ error: queueError.message }), {
        status: 500,
      });
    }

    if (!jobs || jobs.length === 0) {
      return new Response(JSON.stringify({ ok: true, message: "No jobs in queue" }), {
        status: 200,
      });
    }

    // Format jobs for RunPod handler
    const jobsToProcess = jobs.map((job: any) => ({
      msg_id: job.msg_id,
      read_ct: job.read_ct,
      enqueued_at: job.enqueued_at,
      document_id: job.message?.document_id || job.document_id,
      message: job.message,
    }));

    // Call RunPod async endpoint (returns immediately)
    const runpodResponse = await fetch(
      `https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/run`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${RUNPOD_API_KEY}`,
        },
        body: JSON.stringify({
          input: {
            queue: "video_audio_transcription",
            vt_seconds: 1800,
            jobs: jobsToProcess,
          },
        }),
      }
    );

    if (!runpodResponse.ok) {
      const errorText = await runpodResponse.text();
      console.error("RunPod error:", errorText);
      return new Response(
        JSON.stringify({ error: "RunPod request failed", details: errorText }),
        { status: 500 }
      );
    }

    const runpodResult = await runpodResponse.json();

    // RunPod returns immediately with job ID and IN_QUEUE status
    // Results will be saved directly to Supabase by the worker
    return new Response(
      JSON.stringify({
        ok: true,
        runpod_job_id: runpodResult.id,
        status: runpodResult.status,
        jobs_submitted: jobsToProcess.length,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    console.error("Edge function error:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500 }
    );
  }
});
```

## Environment Variables

Add these to your Supabase Edge Function secrets:

```bash
# In Supabase Dashboard → Settings → Edge Functions → Secrets
RUNPOD_ENDPOINT_ID=your-runpod-endpoint-id
RUNPOD_API_KEY=your-runpod-api-key
```

Or via CLI:
```bash
supabase secrets set RUNPOD_ENDPOINT_ID=your-endpoint-id
supabase secrets set RUNPOD_API_KEY=your-api-key
```

## Flow Diagram

```
┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Supabase PGMQ   │     │  Edge Function  │     │     RunPod       │
│     Queue        │     │                 │     │   Serverless     │
└────────┬─────────┘     └────────┬────────┘     └────────┬─────────┘
         │                        │                       │
         │  1. Read jobs          │                       │
         │<───────────────────────│                       │
         │                        │                       │
         │  jobs[]                │                       │
         │───────────────────────>│                       │
         │                        │                       │
         │                        │  2. POST /run         │
         │                        │  (async, immediate)   │
         │                        │──────────────────────>│
         │                        │                       │
         │                        │  {"id": "...",        │
         │                        │   "status": "IN_QUEUE"}
         │                        │<──────────────────────│
         │                        │                       │
         │                        │  3. Return 200 OK     │
         │                        │  (Edge Function done) │
         │                        │                       │
         │                        │                       │  4. Worker processes
         │                        │                       │     - Extract audio
         │                        │                       │     - Transcribe
         │                        │                       │     - Save to DB
         │                        │                       │
┌────────┴─────────┐                              ┌───────┴────────┐
│  Supabase DB     │<─────────────────────────────│   handler.py   │
│  (documents,     │   5. Results saved directly  │   (RunPod)     │
│  transcriptions) │                              └────────────────┘
└──────────────────┘
```

## Checking Job Status (Optional)

If you need to check RunPod job status:

```typescript
// Check status of a RunPod job
const statusResponse = await fetch(
  `https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/status/${runpodJobId}`,
  {
    headers: {
      "Authorization": `Bearer ${RUNPOD_API_KEY}`,
    },
  }
);

const status = await statusResponse.json();
// { "id": "...", "status": "COMPLETED", "output": {...} }
```

## Status Values

| RunPod Status | Meaning |
|---------------|---------|
| `IN_QUEUE` | Job received, waiting for worker |
| `IN_PROGRESS` | Worker processing the job |
| `COMPLETED` | Job finished successfully |
| `FAILED` | Job failed (check output for error) |

## Notes

1. **No polling needed**: Results are saved directly to `document_transcriptions` table by `job_service.py`
2. **Document status**: Updated in `documents` table: `pending` → `processing` → `completed`/`error`
3. **Retry logic**: Handled by existing `job_service.py` code (respects `read_ct` and `max_retries`)
4. **Rate limiting**: YouTube rate limiting preserved in `ytdlp_service.py`
