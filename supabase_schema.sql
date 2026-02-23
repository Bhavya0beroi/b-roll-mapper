-- B-Roll Mapper Supabase Database Schema
-- Create tables for videos, clips, and visual frames with embeddings

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Videos table
CREATE TABLE IF NOT EXISTS videos (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
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
CREATE TABLE IF NOT EXISTS clips (
    id BIGSERIAL PRIMARY KEY,
    video_id BIGINT REFERENCES videos(id) ON DELETE CASCADE,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    transcript_text TEXT,
    embedding vector(1536),  -- OpenAI embedding dimension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Visual frames table
CREATE TABLE IF NOT EXISTS visual_frames (
    id BIGSERIAL PRIMARY KEY,
    video_id BIGINT REFERENCES videos(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL,
    description TEXT,
    embedding vector(1536),  -- OpenAI embedding dimension
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better search performance
CREATE INDEX IF NOT EXISTS idx_videos_filename ON videos(filename);
CREATE INDEX IF NOT EXISTS idx_clips_video_id ON clips(video_id);
CREATE INDEX IF NOT EXISTS idx_visual_frames_video_id ON visual_frames(video_id);
CREATE INDEX IF NOT EXISTS idx_visual_frames_series_movie ON visual_frames(series_movie);
CREATE INDEX IF NOT EXISTS idx_visual_frames_actors ON visual_frames(actors);

-- Create indexes for embedding similarity search (cosine distance)
CREATE INDEX IF NOT EXISTS idx_clips_embedding ON clips USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_visual_frames_embedding ON visual_frames USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

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

-- Create a function for cosine similarity search (helper for queries)
CREATE OR REPLACE FUNCTION match_clips(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id bigint,
    video_id bigint,
    transcript_text text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        clips.id,
        clips.video_id,
        clips.transcript_text,
        1 - (clips.embedding <=> query_embedding) as similarity
    FROM clips
    WHERE 1 - (clips.embedding <=> query_embedding) > match_threshold
    ORDER BY clips.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Create a function for visual frame similarity search
CREATE OR REPLACE FUNCTION match_visual_frames(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id bigint,
    video_id bigint,
    description text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        visual_frames.id,
        visual_frames.video_id,
        visual_frames.description,
        1 - (visual_frames.embedding <=> query_embedding) as similarity
    FROM visual_frames
    WHERE 1 - (visual_frames.embedding <=> query_embedding) > match_threshold
    ORDER BY visual_frames.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Comments
COMMENT ON TABLE videos IS 'Main videos table storing video metadata';
COMMENT ON TABLE clips IS 'Audio transcripts and embeddings for semantic search';
COMMENT ON TABLE visual_frames IS 'Visual analysis frames with AI-generated tags and embeddings';
COMMENT ON COLUMN clips.embedding IS 'OpenAI text-embedding-3-small vector (1536 dimensions)';
COMMENT ON COLUMN visual_frames.embedding IS 'OpenAI text-embedding-3-small vector (1536 dimensions)';
