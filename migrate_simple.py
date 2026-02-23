#!/usr/bin/env python3
"""
Simplified Migration: SQLite → Supabase (Skip Embeddings)
Migrates metadata only, embeddings will be regenerated later
"""

import sqlite3
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.supabase')

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://frfrevcsrissjgtyowtb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_KEY:
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyZnJldmNzcmlzc2pndHlvd3RiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU3ODkyNCwiZXhwIjoyMDg3MTU0OTI0fQ.tuIHwHLcWCjwJmWB6x8cGS6ZuEQZ8VGpsmuin1_zLg0"

SQLITE_DB = "broll_semantic.db"

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def migrate_videos():
    """Migrate videos table"""
    print("\n" + "="*60)
    print("📹 MIGRATING VIDEOS TABLE")
    print("="*60)
    
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, filename, upload_date, duration, status, thumbnail, custom_tags FROM videos')
    videos = cursor.fetchall()
    
    print(f"Found {len(videos)} videos to migrate...")
    
    migrated = 0
    
    for video in videos:
        try:
            video_id, filename, upload_date, duration, status, thumbnail, custom_tags = video
            
            data = {
                'id': video_id,
                'filename': filename,
                'upload_date': upload_date,
                'duration': duration,
                'status': status,
                'thumbnail': thumbnail,
                'custom_tags': custom_tags
            }
            
            result = supabase.table('videos').upsert(data).execute()
            migrated += 1
            
            if migrated % 10 == 0 or migrated == len(videos):
                print(f"  ✅ Migrated {migrated}/{len(videos)} videos")
            
        except Exception as e:
            print(f"  ❌ Failed {filename}: {str(e)}")
    
    conn.close()
    print(f"\n✅ Videos: {migrated}/{len(videos)} migrated")
    return migrated

def migrate_clips_no_embeddings():
    """Migrate clips without embeddings"""
    print("\n" + "="*60)
    print("🎤 MIGRATING CLIPS (Metadata Only)")
    print("="*60)
    print("⚠️  Skipping embeddings - will regenerate later")
    
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, video_id, start_time, end_time, transcript_text FROM clips')
    clips = cursor.fetchall()
    
    print(f"Found {len(clips)} clips to migrate...")
    
    migrated = 0
    batch_size = 100
    
    for i in range(0, len(clips), batch_size):
        batch = clips[i:i + batch_size]
        batch_data = []
        
        for clip in batch:
            clip_id, video_id, start_time, end_time, transcript_text = clip
            
            data = {
                'id': clip_id,
                'video_id': video_id,
                'start_time': start_time,
                'end_time': end_time,
                'transcript_text': transcript_text
            }
            
            batch_data.append(data)
        
        try:
            result = supabase.table('clips').upsert(batch_data).execute()
            migrated += len(batch_data)
            print(f"  ✅ Migrated batch: {migrated}/{len(clips)} clips")
        except Exception as e:
            print(f"  ❌ Batch failed: {str(e)}")
    
    conn.close()
    print(f"\n✅ Clips: {migrated}/{len(clips)} migrated")
    return migrated

def migrate_visual_frames_no_embeddings():
    """Migrate visual frames without embeddings"""
    print("\n" + "="*60)
    print("🎨 MIGRATING VISUAL FRAMES (Metadata Only)")
    print("="*60)
    print("⚠️  Skipping embeddings - will regenerate later")
    
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    cursor.execute('''SELECT id, video_id, timestamp, visual_description,
                      emotion, ocr_text, tags, genres, deep_emotions, scene_context, 
                      people_description, environment, dialogue_context, series_movie, 
                      target_audience, scene_type, actors, media_type,
                      emotion_tags, laugh_tags, contextual_tags, character_tags, semantic_tags 
                      FROM visual_frames''')
    frames = cursor.fetchall()
    
    print(f"Found {len(frames)} visual frames to migrate...")
    
    migrated = 0
    batch_size = 50
    
    for i in range(0, len(frames), batch_size):
        batch = frames[i:i + batch_size]
        batch_data = []
        
        for frame in batch:
            (frame_id, video_id, timestamp, visual_description,
             emotion, ocr_text, tags, genres, deep_emotions, scene_context,
             people_description, environment, dialogue_context, series_movie,
             target_audience, scene_type, actors, media_type,
             emotion_tags, laugh_tags, contextual_tags, character_tags, semantic_tags) = frame
            
            data = {
                'id': frame_id,
                'video_id': video_id,
                'timestamp': timestamp,
                'visual_description': visual_description or '',
                'emotion': emotion,
                'ocr_text': ocr_text,
                'tags': tags,
                'genres': genres,
                'deep_emotions': deep_emotions,
                'scene_context': scene_context,
                'people_description': people_description,
                'environment': environment,
                'dialogue_context': dialogue_context,
                'series_movie': series_movie,
                'target_audience': target_audience,
                'scene_type': scene_type,
                'actors': actors,
                'media_type': media_type,
                'emotion_tags': emotion_tags,
                'laugh_tags': laugh_tags,
                'contextual_tags': contextual_tags,
                'character_tags': character_tags,
                'semantic_tags': semantic_tags
            }
            
            batch_data.append(data)
        
        try:
            result = supabase.table('visual_frames').upsert(batch_data).execute()
            migrated += len(batch_data)
            print(f"  ✅ Migrated batch: {migrated}/{len(frames)} frames")
        except Exception as e:
            print(f"  ❌ Batch failed: {str(e)}")
    
    conn.close()
    print(f"\n✅ Visual frames: {migrated}/{len(frames)} migrated")
    return migrated

if __name__ == "__main__":
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "SIMPLIFIED MIGRATION" + " "*22 + "║")
    print("║" + " "*12 + "SQLite → Supabase (Metadata Only)" + " "*13 + "║")
    print("╚" + "="*58 + "╝")
    
    if not os.path.exists(SQLITE_DB):
        print(f"\n❌ ERROR: '{SQLITE_DB}' not found!")
        exit(1)
    
    print(f"\n✅ Found database: {SQLITE_DB}")
    print(f"✅ Supabase URL: {SUPABASE_URL}")
    print(f"\n🚀 Starting migration...\n")
    
    try:
        videos_count = migrate_videos()
        clips_count = migrate_clips_no_embeddings()
        frames_count = migrate_visual_frames_no_embeddings()
        
        print("\n" + "="*60)
        print("🎉 MIGRATION COMPLETE!")
        print("="*60)
        print(f"\n📊 Results:")
        print(f"  Videos: {videos_count}")
        print(f"  Clips: {clips_count}")
        print(f"  Visual Frames: {frames_count}")
        print()
        print("✅ All metadata migrated successfully!")
        print("⚠️  Embeddings skipped - will regenerate when needed")
        print()
        
    except Exception as e:
        print(f"\n\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
