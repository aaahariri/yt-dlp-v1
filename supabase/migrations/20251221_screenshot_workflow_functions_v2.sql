-- ============================================================================
-- Migration: Screenshot Workflow Functions v2
-- Created: 2025-12-21
-- Description: Simplify state management - use only screenshots_status
-- ============================================================================

-- ============================================================================
-- Function: get_unprocessed_transcriptions_for_screenshots
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
    -- Either: not yet processed OR stuck in processing
    AND (
      -- Not yet processed: screenshots_status is NULL or empty
      (
        dt.metadata IS NULL
        OR dt.metadata->>'screenshots_status' IS NULL
        OR dt.metadata->>'screenshots_status' = ''
      )
      -- OR stuck in processing for too long
      OR (
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

COMMENT ON FUNCTION get_unprocessed_transcriptions_for_screenshots IS
'Returns transcriptions that need screenshot processing.
Status values: NULL=unprocessed, processing, completed, skipped, failed, timeout';


-- ============================================================================
-- Function: complete_transcription_screenshots
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

  UPDATE document_transcriptions
  SET
    metadata = v_existing_metadata || jsonb_build_object(
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

COMMENT ON FUNCTION complete_transcription_screenshots IS
'Marks a screenshot job as complete (screenshots_status = completed).
Appends job to screenshots_jobs array.
Calculates total screenshot count across all jobs.';


-- ============================================================================
-- Function: skip_transcription_screenshots (NEW)
-- Purpose: Mark when AI determines no screenshots are needed
-- ============================================================================

CREATE OR REPLACE FUNCTION skip_transcription_screenshots(
  p_transcription_id UUID,
  p_reason TEXT DEFAULT 'No visual content identified'
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

  -- Update metadata with skipped status
  UPDATE document_transcriptions
  SET
    metadata = v_existing_metadata || jsonb_build_object(
      'screenshots_status', 'skipped',
      'screenshots_skipped_reason', p_reason,
      'screenshots_skipped_at', NOW()::TEXT
    ),
    updated_at = NOW()
  WHERE id = p_transcription_id;

  GET DIAGNOSTICS v_updated_count = ROW_COUNT;

  RETURN v_updated_count > 0;
END;
$$;

-- Grant access
GRANT EXECUTE ON FUNCTION skip_transcription_screenshots(UUID, TEXT) TO anon, authenticated;

COMMENT ON FUNCTION skip_transcription_screenshots IS
'Marks a transcription as skipped (AI determined no screenshots needed).
Sets screenshots_status = skipped with reason.';


-- ============================================================================
-- Function: fail_transcription_screenshots
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
  -- Validate status
  IF p_status NOT IN ('failed', 'timeout') THEN
    p_status := 'failed';
  END IF;

  -- Get existing metadata
  SELECT COALESCE(metadata, '{}'::JSONB) INTO v_existing_metadata
  FROM document_transcriptions
  WHERE id = p_transcription_id;

  UPDATE document_transcriptions
  SET
    metadata = v_existing_metadata || jsonb_build_object(
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

COMMENT ON FUNCTION fail_transcription_screenshots IS
'Marks a screenshot job as failed or timed out.
Sets screenshots_status to failed or timeout.';


-- ============================================================================
-- Function: reset_transcription_screenshots
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

  -- Remove all screenshot-related keys to allow reprocessing
  UPDATE document_transcriptions
  SET
    metadata = v_existing_metadata
      - 'screenshots_status'
      - 'screenshots_error'
      - 'screenshots_failed_at'
      - 'screenshots_skipped_reason'
      - 'screenshots_skipped_at'
      - 'screenshots_runpod_job_id'
      - 'screenshots_requested_at'
      - 'screenshots_requested_count'
      - 'screenshots_requests'
      -- Keep these if you want to preserve history:
      -- - 'screenshots_jobs'
      -- - 'screenshots_total_count'
      -- - 'screenshots_completed_at'
    ,
    updated_at = NOW()
  WHERE id = p_transcription_id;

  GET DIAGNOSTICS v_updated_count = ROW_COUNT;

  RETURN v_updated_count > 0;
END;
$$;

COMMENT ON FUNCTION reset_transcription_screenshots IS
'Resets screenshot processing status to allow reprocessing.
Clears: screenshots_status, error, failed_at, skipped fields, processing fields.
Preserves: screenshots_jobs, total_count, completed_at (history).
Note: Does NOT delete existing screenshots from public_media.';


