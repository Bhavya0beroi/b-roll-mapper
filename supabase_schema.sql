-- B-Roll Mapper Supabase Database Schema
-- Create tables for videos, clips, and visual frames with embeddings

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop existing tables if they exist (for clean migration)
DROP TABLE IF EXISTS visual_frames CASCADE;
DROP TABLE IF EXISTS clips CASCADE;
DROP TABLE IF EXISTS videos CASCADE;

-- Videos table
CREATE TABLE videos (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    title TEXT,  -- Human-readable title extracted from filename
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration REAL,
    status TEXT DEFAULT 'pending',
    thumbnail TEXT,
    custom_tags TEXT,
    supabase_video_url TEXT,  -- URL to video in Supabase Storage
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clips table (audio transcripts)
CREATE TABLE clips (
    id BIGSERIAL PRIMARY KEY,
    video_id BIGINT REFERENCES videos(id) ON DELETE CASCADE,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    transcript_text TEXT,
    embedding JSONB,  -- Store embeddings as JSONB (not vector type)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Visual frames table
CREATE TABLE visual_frames (
    id BIGSERIAL PRIMARY KEY,
    video_id BIGINT REFERENCES videos(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL,
    visual_description TEXT,
    emotion TEXT,
    ocr_text TEXT,
    tags TEXT,
    genres TEXT,
    deep_emotions TEXT,
    scene_context TEXT,
    people_description TEXT,
    environment TEXT,
    dialogue_context TEXT,
    series_movie TEXT,
    target_audience TEXT,
    scene_type TEXT,
    actors TEXT,
    media_type TEXT,
    -- New categorized tags
    emotion_tags TEXT,
    laugh_tags TEXT,
    contextual_tags TEXT,
    character_tags TEXT,
    semantic_tags TEXT,
    visual_embedding JSONB,  -- Store embeddings as JSONB (not vector type)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for faster search performance
CREATE INDEX idx_clips_video_id ON clips(video_id);
CREATE INDEX idx_clips_transcript_text ON clips USING gin(to_tsvector('english', transcript_text));
CREATE INDEX idx_visual_frames_video_id ON visual_frames(video_id);
CREATE INDEX idx_visual_frames_emotion ON visual_frames(emotion);
CREATE INDEX idx_visual_frames_tags ON visual_frames USING gin(to_tsvector('english', tags));
CREATE INDEX idx_videos_filename ON videos(filename);
CREATE INDEX idx_videos_status ON videos(status);

-- Create indexes for better search performance
CREATE INDEX IF NOT EXISTS idx_videos_filename ON videos(filename);
CREATE INDEX IF NOT EXISTS idx_clips_video_id ON clips(video_id);
CREATE INDEX IF NOT EXISTS idx_visual_frames_video_id ON visual_frames(video_id);
CREATE INDEX IF NOT EXISTS idx_visual_frames_series_movie ON visual_frames(series_movie);
CREATE INDEX IF NOT EXISTS idx_visual_frames_actors ON visual_frames(actors);

-- Create indexes for embedding similarity search (cosine distance)
-- Note: ivfflat indexes removed due to dimension size limits
-- We'll use direct vector search or regenerate embeddings with proper dimensions later

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON videos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add Row Level Security (RLS) policies
ALTER TABLE videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE clips ENABLE ROW LEVEL SECURITY;
ALTER TABLE visual_frames ENABLE ROW LEVEL SECURITY;

-- Allow public read access (for anon key)
CREATE POLICY "Public read access for videos" ON videos FOR SELECT USING (true);
CREATE POLICY "Public read access for clips" ON clips FOR SELECT USING (true);
CREATE POLICY "Public read access for visual_frames" ON visual_frames FOR SELECT USING (true);

-- Allow service_role full access (for backend operations)
CREATE POLICY "Service role full access for videos" ON videos FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access for clips" ON clips FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access for visual_frames" ON visual_frames FOR ALL USING (auth.role() = 'service_role');

-- Comments
COMMENT ON TABLE videos IS 'Main videos table storing video metadata';
COMMENT ON TABLE clips IS 'Audio transcripts for semantic search';
COMMENT ON TABLE visual_frames IS 'Visual analysis frames with AI-generated tags';
