#!/usr/bin/env python3
"""Clear all old migrated videos from Supabase"""

from supabase import create_client, Client

SUPABASE_URL = "https://frfrevcsrissjgtyowtb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyZnJldmNzcmlzc2pndHlvd3RiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU3ODkyNCwiZXhwIjoyMDg3MTU0OTI0fQ.tuIHwHLcWCjwJmWB6x8cGS6ZuEQZ8VGpsmuin1_zLg0"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("="*70)
print("🗑️  CLEARING OLD VIDEOS FROM SUPABASE")
print("="*70)
print()

# Get all videos
result = supabase.table('videos').select('id, filename').execute()
videos = result.data

print(f"📊 Found {len(videos)} videos to delete")
print()

if len(videos) == 0:
    print("✅ Database is already empty!")
    exit(0)

print("🗑️  Deleting clips and visual frames...")
for video in videos:
    video_id = video['id']
    supabase.table('clips').delete().eq('video_id', video_id).execute()
    supabase.table('visual_frames').delete().eq('video_id', video_id).execute()

print("🗑️  Deleting video records...")
supabase.table('videos').delete().neq('id', 0).execute()  # Delete all

print()
print("="*70)
print("✅ ALL OLD VIDEOS CLEARED!")
print("="*70)
print()
print("🎯 Your database is now clean and ready for new uploads!")
print("   Visit: https://web-production-b5a81.up.railway.app")
print()
