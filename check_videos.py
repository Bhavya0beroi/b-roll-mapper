#!/usr/bin/env python3
"""Check videos in Supabase database"""

from supabase import create_client, Client

SUPABASE_URL = "https://frfrevcsrissjgtyowtb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyZnJldmNzcmlzc2pndHlvd3RiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU3ODkyNCwiZXhwIjoyMDg3MTU0OTI0fQ.tuIHwHLcWCjwJmWB6x8cGS6ZuEQZ8VGpsmuin1_zLg0"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("="*70)
print("📊 CHECKING VIDEOS IN SUPABASE DATABASE")
print("="*70)
print()

# Get all videos
result = supabase.table('videos').select('*').execute()
videos = result.data

print(f"✅ Total videos in database: {len(videos)}")
print()

# Check video URLs
with_supabase_url = 0
with_local_path = 0
no_url = 0

for video in videos:
    if video.get('supabase_video_url'):
        with_supabase_url += 1
    elif video.get('filepath'):
        with_local_path += 1
    else:
        no_url += 1

print("📹 VIDEO STATUS:")
print(f"   ✅ With Supabase URL: {with_supabase_url}")
print(f"   📁 With local path only: {with_local_path}")
print(f"   ❌ No URL/path: {no_url}")
print()

# Show sample videos
print("="*70)
print("📋 SAMPLE VIDEOS (first 5):")
print("="*70)
for i, video in enumerate(videos[:5]):
    print(f"\n{i+1}. {video.get('title', 'No title')}")
    print(f"   Filename: {video.get('filename', 'N/A')}")
    print(f"   Supabase URL: {video.get('supabase_video_url', 'MISSING')[:80] if video.get('supabase_video_url') else 'MISSING'}")
    print(f"   Local path: {video.get('filepath', 'MISSING')}")

print()
print("="*70)
