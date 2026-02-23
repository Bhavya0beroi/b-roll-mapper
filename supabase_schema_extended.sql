-- Extension to add embedding columns for semantic search
-- Run this AFTER supabase_schema.sql if you need semantic search

-- Add embedding to clips (JSONB array of floats for OpenAI text-embedding-3-small)
ALTER TABLE clips ADD COLUMN IF NOT EXISTS embedding JSONB;
ALTER TABLE clips ADD COLUMN IF NOT EXISTS filename TEXT;
ALTER TABLE clips ADD COLUMN IF NOT EXISTS duration REAL;

-- Add visual_embedding and filename to visual_frames
ALTER TABLE visual_frames ADD COLUMN IF NOT EXISTS visual_embedding JSONB;
ALTER TABLE visual_frames ADD COLUMN IF NOT EXISTS filename TEXT;
