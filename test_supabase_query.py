#!/usr/bin/env python3
"""Test if Supabase queries are working"""

from supabase import create_client, Client

SUPABASE_URL = "https://frfrevcsrissjgtyowtb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyZnJldmNzcmlzc2pndHlvd3RiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU3ODkyNCwiZXhwIjoyMDg3MTU0OTI0fQ.tuIHwHLcWCjwJmWB6x8cGS6ZuEQZ8VGpsmuin1_zLg0"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Testing different query methods:")
print()

# Test 1: Simple count
print("1. Total clips (count only):")
try:
    result = supabase.table('clips').select('id', count='exact').execute()
    print(f"   ✅ Count: {result.count}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test 2: Select with limit
print("2. Select clips with limit(3):")
try:
    result = supabase.table('clips').select('id, transcript_text').limit(3).execute()
    print(f"   ✅ Returned: {len(result.data)} clips")
    for clip in result.data:
        print(f"      - Clip {clip['id']}: {clip.get('transcript_text', 'N/A')[:50]}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test 3: Select with embedding
print("3. Select clips with embedding column:")
try:
    result = supabase.table('clips').select('id, transcript_text, embedding').limit(3).execute()
    print(f"   ✅ Returned: {len(result.data)} clips")
    for clip in result.data:
        has_emb = clip.get('embedding') is not None
        print(f"      - Clip {clip['id']}: has embedding = {has_emb}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test 4: Visual frames
print("4. Visual frames with embedding:")
try:
    result = supabase.table('visual_frames').select('id, emotion, visual_embedding').limit(3).execute()
    print(f"   ✅ Returned: {len(result.data)} frames")
    for frame in result.data:
        has_emb = frame.get('visual_embedding') is not None
        print(f"      - Frame {frame['id']}: emotion={frame.get('emotion')}, has embedding = {has_emb}")
except Exception as e:
    print(f"   ❌ Error: {e}")
