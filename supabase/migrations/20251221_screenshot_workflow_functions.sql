-- ============================================================================
-- Migration: Screenshot Workflow Functions
-- Created: 2025-12-21
-- Description: Functions to support n8n AI-driven screenshot generation workflow
-- ============================================================================

-- ============================================================================
-- Function: get_unprocessed_transcriptions_for_screenshots
-- Purpose: Returns transcriptions that need screenshot processing
-- Used by: n8n workflow scheduler
-- ============================================================================

CREATE OR REPLACE FUNCTION get_unprocessed_transcriptions_for_screenshots(
  p_limit INTEGER DEFAULT 5,
  p_stuck_threshold_minutes INTEGER DEFAULT 30
)
RETURNS TABLE (
  transcription_id UUID,
  document_id UUID,
  canonical_url TEXT,
  title TEXT,
  segments JSONB,
  language VARCHAR(5),
  metadata JSONB,
  created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  SELECT
    dt.id AS transcription_id,
    dt.document_id,
    d.canonical_url,
    d.title,
    dt.segments,
    dt.language,
    dt.metadata,
    dt.created_at
  FROM document_transcriptions dt
  JOIN documents d ON d.id = dt.document_id
  WHERE
    -- Has a canonical_url (needed for screenshots)
    d.canonical_url IS NOT NULL
    AND d.canonical_url != ''
    -- Not yet processed for screenshots (screenshots_generated is NULL or not set)
    AND (
      dt.metadata IS NULL
      OR dt.metadata->>'screenshots_generated' IS NULL
      OR dt.metadata->>'screenshots_generated' = ''
    )
    -- Not currently being processed, OR stuck in processing for too long
    AND (
      dt.metadata IS NULL
      OR dt.metadata->>'screenshots_status' IS NULL
      OR dt.metadata->>'screenshots_status' = ''
      OR dt.metadata->>'screenshots_status' NOT IN ('processing', 'completed', 'failed', 'timeout')
      OR (
        -- Stuck jobs: status is 'processing' but requested too long ago
        dt.metadata->>'screenshots_status' = 'processing'
        AND (
          dt.metadata->>'screenshots_requested_at' IS NULL
          OR (dt.metadata->>'screenshots_requested_at')::timestamptz < NOW() - (p_stuck_threshold_minutes || ' minutes')::INTERVAL
        )
      )
    )
  ORDER BY dt.created_at ASC
  LIMIT p_limit;
END;
$$;

-- Grant access to anon and authenticated roles
GRANT EXECUTE ON FUNCTION get_unprocessed_transcriptions_for_screenshots(INTEGER, INTEGER) TO anon, authenticated;

COMMENT ON FUNCTION get_unprocessed_transcriptions_for_screenshots IS
'Returns transcriptions that need screenshot processing for the n8n AI workflow.
Parameters:
  - p_limit: Maximum number of transcriptions to return (default: 5)
  - p_stuck_threshold_minutes: Minutes after which a "processing" job is considered stuck (default: 30)
Returns transcriptions where:
  - Document has a canonical_url
  - screenshots_generated is not set or is NULL
  - Not currently processing (or stuck for > threshold)';


-- ============================================================================
-- Function: get_all_screenshots_for_document
-- Purpose: Returns all screenshots for a document across all jobs
-- Used by: n8n workflow to show AI agent existing screenshots
-- ============================================================================

CREATE OR REPLACE FUNCTION get_all_screenshots_for_document(
  p_document_id UUID
)
RETURNS TABLE (
  id UUID,
  storage_path TEXT,
  storage_bucket TEXT,
  content_type TEXT,
  size_bytes BIGINT,
  title TEXT,
  created_at TIMESTAMPTZ,
  timestamp_seconds NUMERIC,
  timestamp_formatted TEXT,
  width INTEGER,
  height INTEGER,
  platform TEXT,
  job_id TEXT,
  storage_status TEXT,
  public_url TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_supabase_url TEXT;
BEGIN
  -- Get Supabase URL for building public URLs
  -- This assumes you have a way to get the URL, or hardcode it
  -- For now, we'll construct relative URLs

  RETURN QUERY
  SELECT
    pm.id,
    pm.storage_path,
    pm.storage_bucket,
    pm.content_type,
    pm.size_bytes,
    pm.title,
    pm.created_at,
    (pm.metadata->>'timestamp')::NUMERIC AS timestamp_seconds,
    pm.metadata->>'timestamp_formatted' AS timestamp_formatted,
    (pm.metadata->>'width')::INTEGER AS width,
    (pm.metadata->>'height')::INTEGER AS height,
    pm.metadata->>'platform' AS platform,
    pm.metadata->>'job_id' AS job_id,
    pm.metadata->>'storage_status' AS storage_status,
    -- Construct public URL pattern (caller should prepend SUPABASE_URL)
    '/storage/v1/object/public/' || pm.storage_bucket || '/' || pm.storage_path AS public_url
  FROM public_media pm
  WHERE pm.document_id = p_document_id
    AND pm.type = 'screenshot'
  ORDER BY (pm.metadata->>'timestamp')::NUMERIC ASC NULLS LAST;
END;
$$;

-- Grant access
GRANT EXECUTE ON FUNCTION get_all_screenshots_for_document(UUID) TO anon, authenticated;

COMMENT ON FUNCTION get_all_screenshots_for_document IS
'Returns all screenshots associated with a document, ordered by timestamp.
Used to show existing screenshots to AI agent before requesting new ones.';


-- ============================================================================
-- Function: mark_transcription_screenshots_processing
-- Purpose: Atomically mark a transcription as processing screenshots
-- Used by: n8n workflow to claim a transcription before processing
-- ============================================================================

CREATE OR REPLACE FUNCTION mark_transcription_screenshots_processing(
  p_transcription_id UUID,
  p_runpod_job_id TEXT,
  p_requested_count INTEGER,
  p_requests JSONB DEFAULT '[]'::JSONB
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_current_status TEXT;
  v_updated_count INTEGER;
BEGIN
  -- Check current status
  SELECT metadata->>'screenshots_status' INTO v_current_status
  FROM document_transcriptions
  WHERE id = p_transcription_id;

  -- Only proceed if not already processing (or stuck)
  IF v_current_status = 'processing' THEN
    -- Check if stuck (> 30 minutes)
    IF EXISTS (
      SELECT 1 FROM document_transcriptions
      WHERE id = p_transcription_id
        AND (metadata->>'screenshots_requested_at')::timestamptz > NOW() - INTERVAL '30 minutes'
    ) THEN
      -- Not stuck, already being processed
      RETURN FALSE;
    END IF;
  END IF;

  -- Update metadata to mark as processing
  UPDATE document_transcriptions
  SET
    metadata = COALESCE(metadata, '{}'::JSONB) || jsonb_build_object(
      'screenshots_status', 'processing',
      'screenshots_runpod_job_id', p_runpod_job_id,
      'screenshots_requested_at', NOW()::TEXT,
      'screenshots_requested_count', p_requested_count,
      'screenshots_requests', p_requests
    ),
    updated_at = NOW()
  WHERE id = p_transcription_id;

  GET DIAGNOSTICS v_updated_count = ROW_COUNT;

  RETURN v_updated_count > 0;
END;
$$;

-- Grant access
GRANT EXECUTE ON FUNCTION mark_transcription_screenshots_processing(UUID, TEXT, INTEGER, JSONB) TO anon, authenticated;

COMMENT ON FUNCTION mark_transcription_screenshots_processing IS
'Atomically marks a transcription as processing screenshots.
Returns FALSE if already being processed (within 30 min threshold).
Returns TRUE if successfully marked as processing.';


-- ============================================================================
-- Function: complete_transcription_screenshots
-- Purpose: Mark a transcription''s screenshot job as complete
-- Used by: n8n workflow after RunPod job completes
-- ============================================================================

CREATE OR REPLACE FUNCTION complete_transcription_screenshots(
  p_transcription_id UUID,
  p_runpod_job_id TEXT,
  p_internal_job_id TEXT,
  p_count INTEGER,
  p_failed_timestamps JSONB DEFAULT '[]'::JSONB
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_existing_metadata JSONB;
  v_existing_jobs JSONB;
  v_new_job JSONB;
  v_all_jobs JSONB;
  v_total_count INTEGER;
  v_updated_count INTEGER;
BEGIN
  -- Get existing metadata
  SELECT COALESCE(metadata, '{}'::JSONB) INTO v_existing_metadata
  FROM document_transcriptions
  WHERE id = p_transcription_id;

  -- Get existing jobs array
  v_existing_jobs := COALESCE(v_existing_metadata->'screenshots_jobs', '[]'::JSONB);

  -- Build new job entry
  v_new_job := jsonb_build_object(
    'runpod_job_id', p_runpod_job_id,
    'internal_job_id', p_internal_job_id,
    'count', p_count,
    'completed_at', NOW()::TEXT,
    'failed_timestamps', p_failed_timestamps
  );

  -- Append new job to existing jobs
  v_all_jobs := v_existing_jobs || jsonb_build_array(v_new_job);

  -- Calculate total count across all jobs
  SELECT COALESCE(SUM((job->>'count')::INTEGER), 0) INTO v_total_count
  FROM jsonb_array_elements(v_all_jobs) AS job;

  -- Update metadata
  UPDATE document_transcriptions
  SET
    metadata = v_existing_metadata || jsonb_build_object(
      'screenshots_generated', TRUE,
      'screenshots_status', 'completed',
      'screenshots_total_count', v_total_count,
      'screenshots_jobs', v_all_jobs,
      'screenshots_completed_at', NOW()::TEXT
    ),
    updated_at = NOW()
  WHERE id = p_transcription_id;

  GET DIAGNOSTICS v_updated_count = ROW_COUNT;

  RETURN v_updated_count > 0;
END;
$$;

-- Grant access
GRANT EXECUTE ON FUNCTION complete_transcription_screenshots(UUID, TEXT, TEXT, INTEGER, JSONB) TO anon, authenticated;

COMMENT ON FUNCTION complete_transcription_screenshots IS
'Marks a screenshot job as complete and appends to the jobs array.
Supports multiple screenshot jobs per transcription.
Automatically calculates total screenshot count across all jobs.';


-- ============================================================================
-- Function: fail_transcription_screenshots
-- Purpose: Mark a transcription''s screenshot job as failed
-- Used by: n8n workflow when RunPod job fails or times out
-- ============================================================================

CREATE OR REPLACE FUNCTION fail_transcription_screenshots(
  p_transcription_id UUID,
  p_error TEXT,
  p_status TEXT DEFAULT 'failed'  -- 'failed' or 'timeout'
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_existing_metadata JSONB;
  v_updated_count INTEGER;
BEGIN
  -- Get existing metadata
  SELECT COALESCE(metadata, '{}'::JSONB) INTO v_existing_metadata
  FROM document_transcriptions
  WHERE id = p_transcription_id;

  -- Update metadata with failure info
  UPDATE document_transcriptions
  SET
    metadata = v_existing_metadata || jsonb_build_object(
      'screenshots_generated', FALSE,
      'screenshots_status', p_status,
      'screenshots_error', p_error,
      'screenshots_failed_at', NOW()::TEXT
    ),
    updated_at = NOW()
  WHERE id = p_transcription_id;

  GET DIAGNOSTICS v_updated_count = ROW_COUNT;

  RETURN v_updated_count > 0;
END;
$$;

-- Grant access
GRANT EXECUTE ON FUNCTION fail_transcription_screenshots(UUID, TEXT, TEXT) TO anon, authenticated;

COMMENT ON FUNCTION fail_transcription_screenshots IS
'Marks a screenshot job as failed or timed out.
Parameters:
  - p_transcription_id: The transcription UUID
  - p_error: Error message to store
  - p_status: Either "failed" or "timeout" (default: "failed")';


-- ============================================================================
-- Function: reset_transcription_screenshots
-- Purpose: Reset screenshot status to allow reprocessing
-- Used by: Manual retry or batch reset
-- ============================================================================

CREATE OR REPLACE FUNCTION reset_transcription_screenshots(
  p_transcription_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_existing_metadata JSONB;
  v_updated_count INTEGER;
BEGIN
  -- Get existing metadata
  SELECT COALESCE(metadata, '{}'::JSONB) INTO v_existing_metadata
  FROM document_transcriptions
  WHERE id = p_transcription_id;

  -- Remove screenshot-related keys to allow reprocessing
  UPDATE document_transcriptions
  SET
    metadata = v_existing_metadata
      - 'screenshots_generated'
      - 'screenshots_status'
      - 'screenshots_error'
      - 'screenshots_failed_at'
      - 'screenshots_runpod_job_id'
      - 'screenshots_requested_at'
      - 'screenshots_requested_count'
      - 'screenshots_requests',
    updated_at = NOW()
  WHERE id = p_transcription_id;

  GET DIAGNOSTICS v_updated_count = ROW_COUNT;

  RETURN v_updated_count > 0;
END;
$$;

-- Grant access
GRANT EXECUTE ON FUNCTION reset_transcription_screenshots(UUID) TO anon, authenticated;

COMMENT ON FUNCTION reset_transcription_screenshots IS
'Resets screenshot processing status to allow reprocessing.
Note: Does NOT delete existing screenshots from public_media.
Use this to retry failed jobs or request additional screenshots.';


-- ============================================================================
-- Summary of Functions
-- ============================================================================
/*
Functions created:

1. get_unprocessed_transcriptions_for_screenshots(p_limit, p_stuck_threshold_minutes)
   - Returns transcriptions needing screenshot processing
   - Used by n8n scheduler

2. get_all_screenshots_for_document(p_document_id)
   - Returns all screenshots for a document
   - Used to show AI agent existing screenshots

3. mark_transcription_screenshots_processing(p_transcription_id, p_runpod_job_id, p_requested_count, p_requests)
   - Atomically claims a transcription for processing
   - Returns FALSE if already processing

4. complete_transcription_screenshots(p_transcription_id, p_runpod_job_id, p_internal_job_id, p_count, p_failed_timestamps)
   - Marks job as complete, appends to jobs array
   - Calculates total count

5. fail_transcription_screenshots(p_transcription_id, p_error, p_status)
   - Marks job as failed/timeout

6. reset_transcription_screenshots(p_transcription_id)
   - Resets status to allow reprocessing
*/
