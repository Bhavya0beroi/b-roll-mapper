#!/usr/bin/env python3
"""Debug search issue - check database state"""

from supabase import create_client, Client

SUPABASE_URL = "https://frfrevcsrissjgtyowtb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyZnJldmNzcmlzc2pndHlvd3RiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU3ODkyNCwiZXhwIjoyMDg3MTU0OTI0fQ.tuIHwHLcWCjwJmWB6x8cGS6ZuEQZ8VGpsmuin1_zLg0"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("="*70)
print("🔍 DEBUGGING SEARCH ISSUE")
print("="*70)
print()

# Check videos
videos = supabase.table('videos').select('*').execute()
print(f"📹 Videos: {len(videos.data)}")
for v in videos.data:
    print(f"   - ID {v['id']}: {v['filename']} (status: {v['status']}, clips: ?)")

print()

# Check clips
clips = supabase.table('clips').select('*').execute()
print(f"📝 Clips (transcribed audio): {len(clips.data)}")
if clips.data:
    for c in clips.data[:3]:
        print(f"   - Video {c['video_id']}: {c.get('transcript_text', 'N/A')[:60]}...")
        print(f"     Has embedding: {c.get('embedding') is not None}")
else:
    print("   ❌ NO CLIPS FOUND!")

print()

# Check visual frames
vf = supabase.table('visual_frames').select('*').execute()
print(f"🎨 Visual Frames: {len(vf.data)}")
if vf.data:
    for frame in vf.data[:3]:
        print(f"   - Video {frame['video_id']}, t={frame['timestamp']}s")
        print(f"     Description: {frame.get('visual_description', 'N/A')[:60]}...")
        print(f"     Has embedding: {frame.get('visual_embedding') is not None}")
        print(f"     Tags: {frame.get('tags', 'N/A')}")
else:
    print("   ❌ NO VISUAL FRAMES FOUND!")

print()
print("="*70)
print("DIAGNOSIS:")
print("="*70)

if len(clips.data) == 0 and len(vf.data) == 0:
    print("❌ NO SEARCHABLE DATA!")
    print("   Videos uploaded but AI processing didn't create clips/frames")
    print("   Possible causes:")
    print("   - OpenAI API key missing on Railway")
    print("   - Processing crashed silently")
    print("   - Embeddings not created")
elif len(clips.data) > 0 or len(vf.data) > 0:
    has_embeddings = any(c.get('embedding') for c in clips.data) or any(f.get('visual_embedding') for f in vf.data)
    if has_embeddings:
        print("✅ Data exists with embeddings - search should work!")
        print("   Issue might be in similarity calculation or thresholds")
    else:
        print("⚠️ Data exists but NO EMBEDDINGS!")
        print("   Search cannot work without embeddings")
