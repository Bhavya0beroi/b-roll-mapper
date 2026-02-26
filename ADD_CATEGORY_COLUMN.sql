-- Add category column to videos table (preserves existing data)
-- Run this in Supabase SQL Editor

ALTER TABLE videos 
ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'Videos';

-- Set all existing videos to 'Videos' category
UPDATE videos 
SET category = 'Videos' 
WHERE category IS NULL OR category = '';

-- Verify
SELECT id, filename, category, title FROM videos ORDER BY id LIMIT 10;
