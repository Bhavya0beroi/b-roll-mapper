#!/usr/bin/env python3
"""
Migration Script: SQLite → Supabase PostgreSQL
Migrates all data from local SQLite to Supabase
"""

import sqlite3
import json
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase credentials - load from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://frfrevcsrissjgtyowtb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_KEY:
    print("❌ ERROR: SUPABASE_SERVICE_KEY not found in environment variables!")
    print("Please set it in .env.supabase or export it:")
    print("export SUPABASE_SERVICE_KEY='your-service-role-key'")
    exit(1)

# SQLite database
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
    failed = 0
    
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
            
            # Insert into Supabase
            result = supabase.table('videos').upsert(data).execute()
            
            migrated += 1
            print(f"  ✅ Migrated video {migrated}/{len(videos)}: {filename}")
            
        except Exception as e:
            failed += 1
            print(f"  ❌ Failed to migrate {filename}: {str(e)}")
    
    conn.close()
    
    print(f"\n✅ Videos migration complete: {migrated} success, {failed} failed")
    return migrated, failed

def migrate_clips():
    """Migrate clips table (audio transcripts)"""
    print("\n" + "="*60)
    print("🎤 MIGRATING CLIPS TABLE (Audio Transcripts)")
    print("="*60)
    
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, video_id, filename, start_time, end_time, duration, transcript_text, embedding FROM clips')
    clips = cursor.fetchall()
    
    print(f"Found {len(clips)} clips to migrate...")
    
    migrated = 0
    failed = 0
    batch_size = 100
    
    for i in range(0, len(clips), batch_size):
        batch = clips[i:i + batch_size]
        batch_data = []
        
        for clip in batch:
            try:
                clip_id, video_id, filename, start_time, end_time, duration, transcript_text, embedding_blob = clip
                
                # Convert embedding blob to list
                if embedding_blob:
                    import struct
                    embedding_list = list(struct.unpack(f'{len(embedding_blob)//4}f', embedding_blob))
                else:
                    embedding_list = None
                
                data = {
                    'id': clip_id,
                    'video_id': video_id,
                    'filename': filename,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': duration,
                    'transcript_text': transcript_text,
                    'embedding': embedding_list
                }
                
                batch_data.append(data)
                
            except Exception as e:
                failed += 1
                print(f"  ❌ Failed to prepare clip {clip_id}: {str(e)}")
        
        # Insert batch into Supabase
        if batch_data:
            try:
                result = supabase.table('clips').upsert(batch_data).execute()
                migrated += len(batch_data)
                print(f"  ✅ Migrated batch: {migrated}/{len(clips)} clips")
            except Exception as e:
                print(f"  ❌ Failed to migrate batch: {str(e)}")
                failed += len(batch_data)
    
    conn.close()
    
    print(f"\n✅ Clips migration complete: {migrated} success, {failed} failed")
    return migrated, failed

def migrate_visual_frames():
    """Migrate visual_frames table"""
    print("\n" + "="*60)
    print("🎨 MIGRATING VISUAL FRAMES TABLE")
    print("="*60)
    
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    cursor.execute('''SELECT id, video_id, filename, timestamp, frame_path, visual_description, visual_embedding, emotion, ocr_text, 
                      tags, genres, deep_emotions, scene_context, people_description, environment,
                      dialogue_context, series_movie, target_audience, scene_type, actors, media_type,
                      emotion_tags, laugh_tags, contextual_tags, character_tags, semantic_tags 
                      FROM visual_frames''')
    frames = cursor.fetchall()
    
    print(f"Found {len(frames)} visual frames to migrate...")
    
    migrated = 0
    failed = 0
    batch_size = 50  # Smaller batch for visual frames (more data per row)
    
    for i in range(0, len(frames), batch_size):
        batch = frames[i:i + batch_size]
        batch_data = []
        
        for frame in batch:
            try:
                (frame_id, video_id, filename, timestamp, frame_path, visual_description, visual_embedding_blob, emotion, ocr_text,
                 tags, genres, deep_emotions, scene_context, people_description, environment,
                 dialogue_context, series_movie, target_audience, scene_type, actors, media_type,
                 emotion_tags, laugh_tags, contextual_tags, character_tags, semantic_tags) = frame
                
                # Convert embedding blob to list
                if visual_embedding_blob:
                    import struct
                    embedding_list = list(struct.unpack(f'{len(visual_embedding_blob)//4}f', visual_embedding_blob))
                else:
                    embedding_list = None
                
                data = {
                    'id': frame_id,
                    'video_id': video_id,
                    'filename': filename,
                    'timestamp': timestamp,
                    'frame_path': frame_path,
                    'visual_description': visual_description,
                    'visual_embedding': embedding_list,
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
                
            except Exception as e:
                failed += 1
                print(f"  ❌ Failed to prepare frame {frame_id}: {str(e)}")
        
        # Insert batch into Supabase
        if batch_data:
            try:
                result = supabase.table('visual_frames').upsert(batch_data).execute()
                migrated += len(batch_data)
                print(f"  ✅ Migrated batch: {migrated}/{len(frames)} frames")
            except Exception as e:
                print(f"  ❌ Failed to migrate batch: {str(e)}")
                failed += len(batch_data)
    
    conn.close()
    
    print(f"\n✅ Visual frames migration complete: {migrated} success, {failed} failed")
    return migrated, failed

def verify_migration():
    """Verify migration counts"""
    print("\n" + "="*60)
    print("🔍 VERIFYING MIGRATION")
    print("="*60)
    
    # Check SQLite counts
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM videos')
    sqlite_videos = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM clips')
    sqlite_clips = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM visual_frames')
    sqlite_frames = cursor.fetchone()[0]
    
    conn.close()
    
    # Check Supabase counts
    supabase_videos = len(supabase.table('videos').select('id').execute().data)
    supabase_clips = len(supabase.table('clips').select('id').execute().data)
    supabase_frames = len(supabase.table('visual_frames').select('id').execute().data)
    
    print(f"\n📊 MIGRATION SUMMARY:")
    print(f"  Videos:        SQLite: {sqlite_videos} → Supabase: {supabase_videos}")
    print(f"  Clips:         SQLite: {sqlite_clips} → Supabase: {supabase_clips}")
    print(f"  Visual Frames: SQLite: {sqlite_frames} → Supabase: {supabase_frames}")
    
    if (sqlite_videos == supabase_videos and 
        sqlite_clips == supabase_clips and 
        sqlite_frames == supabase_frames):
        print(f"\n✅ MIGRATION SUCCESSFUL - All data migrated!")
        return True
    else:
        print(f"\n⚠️  WARNING - Count mismatch! Please review.")
        return False

if __name__ == "__main__":
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "B-ROLL MAPPER MIGRATION" + " "*20 + "║")
    print("║" + " "*12 + "SQLite → Supabase PostgreSQL" + " "*17 + "║")
    print("╚" + "="*58 + "╝")
    
    # Check if SQLite database exists
    if not os.path.exists(SQLITE_DB):
        print(f"\n❌ ERROR: SQLite database '{SQLITE_DB}' not found!")
        exit(1)
    
    print(f"\n✅ Found SQLite database: {SQLITE_DB}")
    print(f"✅ Supabase URL: {SUPABASE_URL}")
    print(f"\n🚀 Starting migration automatically...")
    
    try:
        # Run migrations
        videos_ok, videos_failed = migrate_videos()
        clips_ok, clips_failed = migrate_clips()
        frames_ok, frames_failed = migrate_visual_frames()
        
        # Verify
        success = verify_migration()
        
        print("\n" + "="*60)
        if success:
            print("🎉 MIGRATION COMPLETE!")
            print("="*60)
            print("\nNext steps:")
            print("1. Update Flask app to use Supabase")
            print("2. Upload videos to Supabase Storage")
            print("3. Deploy to Railway")
        else:
            print("⚠️  MIGRATION COMPLETED WITH WARNINGS")
            print("="*60)
            print("\nPlease review the counts above and check for errors.")
        
    except KeyboardInterrupt:
        print("\n\n❌ Migration cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
