# Supabase Integration Guide

Complete guide for storing transcriptions in Supabase database.

## Overview

The Supabase integration provides optional persistent storage for transcriptions from `/subtitles` and `/transcribe` endpoints. All transcription data is stored in PostgreSQL with full-text search capabilities.

## Setup

### 1. Create Supabase Project

1. Sign up at https://supabase.com
2. Create a new project
3. Copy your project URL and service role key from Settings → API

### 2. Environment Variables

Add to your `.env` file:

```bash
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-secret-key-here
```

**Important**: Use the **service role key** (not the anon key) for server-to-server authentication. The service role key bypasses Row Level Security (RLS) policies.

### 3. Database Schema

**Required Schema:**

This API expects your existing normalized database design with `documents` and `document_transcriptions` tables:

```sql
-- Documents table (stores video/audio metadata)
CREATE TABLE IF NOT EXISTS public.documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id TEXT NOT NULL UNIQUE,
  url TEXT,
  title TEXT NOT NULL,
  duration INTEGER,
  platform TEXT,
  provider TEXT,
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Transcriptions table (stores transcription data, linked to documents)
CREATE TABLE IF NOT EXISTS public.document_transcriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL,
  segments JSONB NOT NULL,
  language VARCHAR(5) NOT NULL,
  source VARCHAR(50) NOT NULL,
  model TEXT,
  source_format TEXT,
  full_text TEXT NOT NULL,
  word_count INTEGER NOT NULL,
  segment_count INTEGER NOT NULL,
  confidence_score DOUBLE PRECISION,
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  CONSTRAINT document_transcriptions_document_id_fkey FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  CONSTRAINT document_transcriptions_document_id_key UNIQUE (document_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_documents_video_id ON public.documents USING btree (video_id);
CREATE INDEX IF NOT EXISTS idx_documents_platform ON public.documents USING btree (platform);
CREATE INDEX IF NOT EXISTS idx_transcriptions_document ON public.document_transcriptions USING btree (document_id);
CREATE INDEX IF NOT EXISTS idx_transcriptions_language ON public.document_transcriptions USING btree (language);
CREATE INDEX IF NOT EXISTS idx_transcriptions_source ON public.document_transcriptions USING btree (source);

-- Full-text search
CREATE INDEX IF NOT EXISTS idx_full_text_search ON public.document_transcriptions USING gin(to_tsvector('english', full_text));

-- Triggers for auto-updating updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_documents_updated_at
  BEFORE UPDATE ON documents
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_transcriptions_updated_at
  BEFORE UPDATE ON document_transcriptions
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
```

**Key Features:**
- ✅ Proper normalization (documents separate from transcriptions)
- ✅ One transcription per document (via unique constraint on `document_id`)
- ✅ Referential integrity (foreign key with CASCADE delete)
- ✅ Auto-updating timestamps via trigger
- ✅ Supports UPSERT operations (update existing or insert new)

### 4. Optional: Row Level Security (RLS)

If you want to enable RLS for additional security:

```sql
-- Enable RLS
ALTER TABLE transcriptions ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS (already configured)
-- Create policies only if you need user-level access control

-- Example: Allow authenticated users to read all transcriptions
CREATE POLICY "Allow authenticated users to read transcriptions"
ON transcriptions FOR SELECT
TO authenticated
USING (true);

-- Example: Allow service role to insert/update/delete
CREATE POLICY "Allow service role full access"
ON transcriptions FOR ALL
TO service_role
USING (true);
```

## API Endpoints

### POST /transcriptions/save

Save transcription data to `document_transcriptions` table. Uses UPSERT: updates if exists, inserts if new.

**Important**: The document must already exist in the `documents` table before saving transcription.

**Request Body**:
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "segments": [
    {"start": 0.0, "end": 3.5, "text": "Hello world"},
    {"start": 3.5, "end": 7.2, "text": "How are you"}
  ],
  "language": "en",
  "source": "subtitle",
  "confidence_score": 0.95,
  "metadata": {
    "model": "whisper-large-v3",
    "provider": "local",
    "processing_time": 12.4
  }
}
```

**Response**:
```json
{
  "id": "7b3e8f12-c4d5-41a6-b8e7-9f6a5c3d2e1b",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2025-11-08T10:30:00Z",
  "message": "Transcription saved successfully to Supabase with ID: 7b3e8f12-c4d5-41a6-b8e7-9f6a5c3d2e1b"
}
```

### GET /transcriptions/check/{document_id}

Check if a transcription exists for a given document.

**Response** (when exists):
```json
{
  "exists": true,
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "transcription": {
    "id": "7b3e8f12-c4d5-41a6-b8e7-9f6a5c3d2e1b",
    "language": "en",
    "source": "subtitle",
    "confidence_score": 0.95,
    "created_at": "2025-11-08T10:30:00Z",
    "updated_at": "2025-11-08T10:30:00Z"
  }
}
```

**Response** (when not exists):
```json
{
  "exists": false,
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "transcription": null
}
```

## Example Workflows

### Workflow 1: Check and Save YouTube Subtitles

```bash
# Assumption: Document already created with ID 550e8400-e29b-41d4-a716-446655440000

# Step 1: Check if transcription already exists
curl -X GET "http://localhost:8000/transcriptions/check/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: your-api-key"
# Returns: {"exists": false, "document_id": "...", "transcription": null}

# Step 2: Extract subtitles from YouTube
curl -X GET "http://localhost:8000/subtitles?url=https://youtube.com/watch?v=dQw4w9WgXcQ&format=json&lang=en" \
  -H "X-API-Key: your-api-key"
# Returns: {"segments": [...], "language": "en", ...}

# Step 3: Save to Supabase
curl -X POST "http://localhost:8000/transcriptions/save" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "segments": [{"start": 0.0, "end": 3.5, "text": "Hello world"}],
    "language": "en",
    "source": "subtitle",
    "confidence_score": null,
    "metadata": {"provider": "youtube", "format": "srt"}
  }'
```

### Workflow 2: AI Transcription with Conditional Save

```bash
# Assumption: Document ID is 550e8400-e29b-41d4-a716-446655440000

# Step 1: Check if transcription exists
curl -X GET "http://localhost:8000/transcriptions/check/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: your-api-key"

# Step 2: If not exists, extract audio and transcribe
curl -X POST "http://localhost:8000/extract-audio?url=https://youtube.com/watch?v=dQw4w9WgXcQ" \
  -H "X-API-Key: your-api-key"
# Returns: {"audio_file": "/tmp/abc123.mp3", "video_id": "...", ...}

curl -X POST "http://localhost:8000/transcribe?audio_file=/tmp/abc123.mp3&output_format=json&provider=local&model_size=turbo" \
  -H "X-API-Key: your-api-key"
# Returns: {"segments": [...], "language": "en", ...}

# Step 3: Save to Supabase
curl -X POST "http://localhost:8000/transcriptions/save" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "segments": [{"start": 0.24, "end": 5.12, "text": "AI transcribed text"}],
    "language": "en",
    "source": "ai",
    "confidence_score": 0.92,
    "metadata": {"model": "whisper-turbo", "provider": "local", "processing_time": 15.3}
  }'
```

### Workflow 3: Update Existing Transcription (UPSERT)

```bash
# If transcription exists for document_id, it will be updated instead of creating duplicate

curl -X POST "http://localhost:8000/transcriptions/save" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "segments": [{"start": 0.0, "end": 3.5, "text": "Updated transcription"}],
    "language": "en",
    "source": "ai",
    "confidence_score": 0.98,
    "metadata": {"improved": true}
  }'
# This will UPDATE the existing transcription instead of creating a new one
```

## Advanced Queries

You can perform advanced queries directly in Supabase SQL Editor:

### Full-Text Search

```sql
-- Search transcriptions containing specific words
SELECT id, title, video_id,
       ts_rank(to_tsvector('english', full_text), query) as rank
FROM transcriptions,
     to_tsquery('english', 'artificial & intelligence') query
WHERE to_tsvector('english', full_text) @@ query
ORDER BY rank DESC
LIMIT 10;
```

### Filter by Date Range

```sql
SELECT * FROM transcriptions
WHERE created_at >= '2025-11-01'
  AND created_at < '2025-12-01'
ORDER BY created_at DESC;
```

### Group by Provider

```sql
SELECT provider, COUNT(*) as count,
       SUM(word_count) as total_words
FROM transcriptions
GROUP BY provider
ORDER BY count DESC;
```

### Find Duplicate Videos

```sql
SELECT video_id, COUNT(*) as count
FROM transcriptions
GROUP BY video_id
HAVING COUNT(*) > 1
ORDER BY count DESC;
```

## Troubleshooting

### Error: "Supabase not configured"

Make sure you have set both `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in your `.env` file and restarted the server.

### Error: "relation 'transcriptions' does not exist"

You need to create the database table using the SQL schema provided above.

### Error: "Failed to save transcription"

Check:
1. Your service role key is correct (not the anon key)
2. The database table exists
3. The request body matches the expected format
4. Your Supabase project is active

### Performance Tips

1. **Indexes**: The provided schema includes indexes for common queries. Add more indexes based on your query patterns.
2. **Pagination**: Always use `limit` and `offset` for large result sets.
3. **Connection Pooling**: For high-traffic production use, consider configuring Supabase connection pooling.
4. **Caching**: Cache frequently accessed transcriptions in Redis or similar.

## Security Best Practices

1. **Never expose service role key**: Keep it server-side only, never in frontend code
2. **Use RLS policies**: If exposing Supabase directly to clients, configure proper RLS policies
3. **Validate input**: The API validates all input, but add additional checks if needed
4. **Rate limiting**: Configure rate limiting in your API gateway or Supabase project settings
5. **Backup**: Enable Supabase daily backups in project settings
