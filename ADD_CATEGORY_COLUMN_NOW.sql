-- ⚠️ RUN THIS IN SUPABASE SQL EDITOR NOW! ⚠️
-- This adds the category column to your videos table
-- Your existing 42 videos will NOT be deleted

-- Add category column (safe operation - keeps all data)
ALTER TABLE videos 
ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'Videos';

-- Set all existing videos to 'Videos' category
UPDATE videos 
SET category = 'Videos' 
WHERE category IS NULL OR category = '';

-- Verify the column was added
SELECT id, filename, category, title 
FROM videos 
ORDER BY id DESC 
LIMIT 10;

-- ✅ After running this:
-- 1. Your 42 existing videos will be in "Videos" category
-- 2. You can upload new videos with category selection
-- 3. Category filtering will work
-- 4. No data loss!
