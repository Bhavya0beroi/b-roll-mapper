-- Add title column to videos table
ALTER TABLE videos ADD COLUMN IF NOT EXISTS title TEXT;

-- Generate titles from filenames for existing videos
UPDATE videos 
SET title = CASE 
    WHEN filename IS NOT NULL THEN 
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(filename, '.mp4', ''),
                    '.mov', ''
                ),
                '.webm', ''
            ),
            '_', ' '
        )
    ELSE 'Untitled Video'
END
WHERE title IS NULL OR title = '';
