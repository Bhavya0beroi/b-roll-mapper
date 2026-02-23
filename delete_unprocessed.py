#!/usr/bin/env python3
"""Delete unprocessed videos"""

from supabase import create_client, Client

SUPABASE_URL = "https://frfrevcsrissjgtyowtb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyZnJldmNzcmlzc2pndHlvd3RiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU3ODkyNCwiZXhwIjoyMDg3MTU0OTI0fQ.tuIHwHLcWCjwJmWB6x8cGS6ZuEQZ8VGpsmuin1_zLg0"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("🗑️  Deleting unprocessed videos...")

# Delete all videos
result = supabase.table('videos').select('id').execute()
for video in result.data:
    video_id = video['id']
    supabase.table('clips').delete().eq('video_id', video_id).execute()
    supabase.table('visual_frames').delete().eq('video_id', video_id).execute()
    supabase.table('videos').delete().eq('id', video_id).execute()

print("✅ All videos cleared! Ready for fresh uploads with full processing.")
