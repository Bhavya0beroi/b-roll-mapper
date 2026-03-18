"""
Migration script: Supabase PostgreSQL → MongoDB Atlas

Copies all data from:
  - videos table
  - clips table
  - visual_frames table

Maps supabase_video_url → video_url in MongoDB.
Sets MongoDB ID counters to match the max Supabase IDs so new inserts don't conflict.

Run this ONCE locally:
    python migrate_supabase_to_mongo.py

After migration, run cleanup_supabase_storage.py to delete video files from Supabase Storage.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

try:
    from supabase import create_client
except ImportError:
    print("❌ supabase package not installed. Run: pip install supabase")
    sys.exit(1)

try:
    from pymongo import MongoClient
except ImportError:
    print("❌ pymongo package not installed. Run: pip install pymongo")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────────────────

SUPABASE_URL         = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
MONGODB_URI          = os.getenv('MONGODB_URI')

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    # Try loading from .env.supabase if not in .env
    from dotenv import dotenv_values
    sb_env = dotenv_values('.env.supabase')
    SUPABASE_URL         = SUPABASE_URL         or sb_env.get('SUPABASE_URL')
    SUPABASE_SERVICE_KEY = SUPABASE_SERVICE_KEY or sb_env.get('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("❌ SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (in .env or .env.supabase)")
    sys.exit(1)

if not MONGODB_URI:
    print("❌ MONGODB_URI must be set in .env")
    sys.exit(1)

# ── Connect ──────────────────────────────────────────────────────────────────

print("🔌 Connecting to Supabase...")
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
print("✅ Supabase connected")

print("🔌 Connecting to MongoDB...")
mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10000)
mongo.admin.command('ping')
db = mongo['broll_mapper']
print("✅ MongoDB connected")

videos_col   = db['videos']
clips_col    = db['clips']
frames_col   = db['visual_frames']
counters_col = db['counters']

# ── Helpers ──────────────────────────────────────────────────────────────────

def fetch_all(table, columns='*', batch=1000):
    """Fetch all rows from a Supabase table using pagination."""
    rows = []
    offset = 0
    while True:
        resp = sb.table(table).select(columns).range(offset, offset + batch - 1).execute()
        batch_data = resp.data or []
        rows.extend(batch_data)
        print(f"  Fetched {len(rows)} rows from {table}...", end='\r')
        if len(batch_data) < batch:
            break
        offset += batch
    print(f"  ✅ Total fetched from {table}: {len(rows)}")
    return rows


def set_counter(name, value):
    """Set the auto-increment counter to a given value."""
    counters_col.update_one(
        {'_id': name},
        {'$set': {'seq': value}},
        upsert=True
    )


# ── Migrate videos ───────────────────────────────────────────────────────────

print("\n📋 Fetching videos from Supabase...")
sb_videos = fetch_all('videos')

if not sb_videos:
    print("⚠️  No videos found in Supabase. Nothing to migrate.")
else:
    print(f"\n💾 Inserting {len(sb_videos)} videos into MongoDB...")
    inserted = 0
    skipped  = 0
    max_id   = 0

    for v in sb_videos:
        vid_id = v['id']
        if vid_id > max_id:
            max_id = vid_id

        if videos_col.find_one({'id': vid_id}):
            skipped += 1
            continue

        doc = {
            'id':          vid_id,
            'filename':    v.get('filename', ''),
            'title':       v.get('title', ''),
            'upload_date': v.get('upload_date'),   # kept as-is (ISO string or datetime)
            'duration':    v.get('duration', 0),
            'status':      v.get('status', 'complete'),
            'thumbnail':   v.get('thumbnail', ''),
            'custom_tags': v.get('custom_tags', ''),
            'video_url':   v.get('supabase_video_url', ''),  # renamed field
            'category':    v.get('category', 'Videos'),
        }
        videos_col.insert_one(doc)
        inserted += 1

    set_counter('videos', max_id)
    print(f"  ✅ Videos: {inserted} inserted, {skipped} already existed (skipped)")
    print(f"  🔢 Counter set to {max_id}")


# ── Migrate clips ─────────────────────────────────────────────────────────────

print("\n📋 Fetching clips from Supabase...")
sb_clips = fetch_all('clips')

if not sb_clips:
    print("⚠️  No clips found.")
else:
    print(f"\n💾 Inserting {len(sb_clips)} clips into MongoDB...")
    inserted = 0
    skipped  = 0
    max_id   = 0

    for c in sb_clips:
        clip_id = c['id']
        if clip_id > max_id:
            max_id = clip_id

        if clips_col.find_one({'id': clip_id}):
            skipped += 1
            continue

        doc = {
            'id':              clip_id,
            'video_id':        c.get('video_id'),
            'start_time':      c.get('start_time', 0),
            'end_time':        c.get('end_time', 0),
            'transcript_text': c.get('transcript_text', ''),
            'embedding':       c.get('embedding'),   # list or None
        }
        clips_col.insert_one(doc)
        inserted += 1

    set_counter('clips', max_id)
    print(f"  ✅ Clips: {inserted} inserted, {skipped} already existed (skipped)")
    print(f"  🔢 Counter set to {max_id}")


# ── Migrate visual_frames ──────────────────────────────────────────────────────

print("\n📋 Fetching visual_frames from Supabase...")
sb_frames = fetch_all('visual_frames')

if not sb_frames:
    print("⚠️  No visual frames found.")
else:
    print(f"\n💾 Inserting {len(sb_frames)} visual frames into MongoDB...")
    inserted = 0
    skipped  = 0
    max_id   = 0

    for f in sb_frames:
        frame_id = f['id']
        if frame_id > max_id:
            max_id = frame_id

        if frames_col.find_one({'id': frame_id}):
            skipped += 1
            continue

        doc = {
            'id':                 frame_id,
            'video_id':           f.get('video_id'),
            'timestamp':          f.get('timestamp', 0),
            'visual_description': f.get('visual_description', ''),
            'emotion':            f.get('emotion', ''),
            'ocr_text':           f.get('ocr_text', ''),
            'tags':               f.get('tags', ''),
            'genres':             f.get('genres', ''),
            'deep_emotions':      f.get('deep_emotions', ''),
            'scene_context':      f.get('scene_context', ''),
            'people_description': f.get('people_description', ''),
            'environment':        f.get('environment', ''),
            'dialogue_context':   f.get('dialogue_context', ''),
            'series_movie':       f.get('series_movie', ''),
            'target_audience':    f.get('target_audience', ''),
            'scene_type':         f.get('scene_type', ''),
            'actors':             f.get('actors', ''),
            'media_type':         f.get('media_type', 'Unknown'),
            'emotion_tags':       f.get('emotion_tags', ''),
            'laugh_tags':         f.get('laugh_tags', ''),
            'contextual_tags':    f.get('contextual_tags', ''),
            'character_tags':     f.get('character_tags', ''),
            'semantic_tags':      f.get('semantic_tags', ''),
            'visual_embedding':   f.get('visual_embedding'),  # list or None
        }
        frames_col.insert_one(doc)
        inserted += 1

    set_counter('visual_frames', max_id)
    print(f"  ✅ Visual frames: {inserted} inserted, {skipped} already existed (skipped)")
    print(f"  🔢 Counter set to {max_id}")


# ── Summary ───────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("✅ MIGRATION COMPLETE")
print("="*60)
print(f"  Videos:        {videos_col.count_documents({})} in MongoDB")
print(f"  Clips:         {clips_col.count_documents({})} in MongoDB")
print(f"  Visual frames: {frames_col.count_documents({})} in MongoDB")
print("\nNext step: run  python cleanup_supabase_storage.py  to delete")
print("video files from Supabase Storage and free up space.")
