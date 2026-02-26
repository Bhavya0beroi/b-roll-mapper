-- ⚡ ADD EMBEDDING COLUMNS WITHOUT DELETING DATA
-- This preserves your 42 videos!

-- Add embedding column to clips if it doesn't exist
ALTER TABLE clips ADD COLUMN IF NOT EXISTS embedding JSONB;

-- Add visual_embedding column to visual_frames if it doesn't exist  
ALTER TABLE visual_frames ADD COLUMN IF NOT EXISTS visual_embedding JSONB;

-- Add performance indexes
CREATE INDEX IF NOT EXISTS idx_clips_video_id ON clips(video_id);
CREATE INDEX IF NOT EXISTS idx_clips_transcript_text ON clips USING gin(to_tsvector('english', transcript_text));
CREATE INDEX IF NOT EXISTS idx_visual_frames_video_id ON visual_frames(video_id);
CREATE INDEX IF NOT EXISTS idx_visual_frames_emotion ON visual_frames(emotion);
CREATE INDEX IF NOT EXISTS idx_visual_frames_tags ON visual_frames USING gin(to_tsvector('english', tags));
CREATE INDEX IF NOT EXISTS idx_videos_filename ON videos(filename);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);

-- Done! Your 42 videos are safe, now have embedding columns + indexes
