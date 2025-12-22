-- Screenshot Jobs System Migration
-- Created: 2025-12-18
-- Description: Schema changes and functions for screenshot extraction job processing

-- ============================================================================
-- 1. Add document_id column to public_media (optional FK to documents table)
-- ============================================================================

ALTER TABLE public.public_media
ADD COLUMN IF NOT EXISTS document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL;

-- Index for document_id lookups (partial - only where document_id is set)
CREATE INDEX IF NOT EXISTS idx_public_media_document_id
ON public.public_media (document_id)
WHERE document_id IS NOT NULL;


-- ============================================================================
-- 2. Fix UNIQUE constraint on source_url_hash (only for thumbnails)
-- ============================================================================

-- Drop existing constraint if it exists (might fail silently if doesn't exist)
DO $$
BEGIN
    ALTER TABLE public.public_media
    DROP CONSTRAINT IF EXISTS unique_source_url_hash;
EXCEPTION
    WHEN undefined_object THEN NULL;
END $$;

-- Drop old index if exists
DROP INDEX IF EXISTS unique_source_url_hash_thumbnails;

-- Re-add as partial unique constraint (only for thumbnails)
-- Screenshots can have multiple entries per video (different timestamps)
CREATE UNIQUE INDEX IF NOT EXISTS unique_source_url_hash_thumbnails
ON public.public_media (source_url_hash)
WHERE type = 'thumbnail' AND source_url_hash IS NOT NULL;


-- ============================================================================
-- 3. Add indexes for job queries
-- ============================================================================

-- Index for fast job_id lookups (stored in metadata JSONB)
CREATE INDEX IF NOT EXISTS idx_public_media_metadata_job_id
ON public.public_media ((metadata->>'job_id'));

-- Index for storage_status filtering (temp/confirmed lifecycle)
CREATE INDEX IF NOT EXISTS idx_public_media_metadata_storage_status
ON public.public_media ((metadata->>'storage_status'));

-- Composite index for temp cleanup queries (status + created_at)
-- Optimizes: SELECT * FROM public_media WHERE metadata->>'storage_status' = 'temp' AND created_at < X
CREATE INDEX IF NOT EXISTS idx_public_media_temp_cleanup
ON public.public_media (created_at)
WHERE (metadata->>'storage_status') = 'temp';


-- ============================================================================
-- 4. Function: Get Screenshots by Job ID
-- ============================================================================

-- Get all screenshots for a specific job_id with commonly used fields extracted
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
    pm.document_id,
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


-- ============================================================================
-- 5. Function: Confirm Screenshots (temp -> confirmed)
-- ============================================================================

-- Confirm screenshots by array of public_media IDs
-- Usage (multiple): SELECT confirm_screenshots(ARRAY['uuid1', 'uuid2']::UUID[]);
-- Usage (single): SELECT confirm_screenshots(ARRAY['uuid1']::UUID[]);
CREATE OR REPLACE FUNCTION confirm_screenshots(p_ids UUID[])
RETURNS INTEGER AS $$
DECLARE
  updated_count INTEGER;
BEGIN
  UPDATE public.public_media
  SET metadata = jsonb_set(
    COALESCE(metadata, '{}'::jsonb),
    '{storage_status}',
    '"confirmed"'
  )
  WHERE id = ANY(p_ids)
    AND (metadata->>'storage_status' = 'temp' OR metadata->>'storage_status' IS NULL);

  GET DIAGNOSTICS updated_count = ROW_COUNT;
  RETURN updated_count;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- 6. Function: Get Expired Temp Screenshots (for cleanup preview)
-- ============================================================================

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


-- ============================================================================
-- Done!
-- ============================================================================
-- Note: Edge Function for actual deletion (cleanup-temp-screenshots) is
-- deployed separately as it needs access to Storage API.
