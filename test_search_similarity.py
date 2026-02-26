#!/usr/bin/env python3
"""Test search similarity calculation"""

from supabase import create_client, Client
from openai import OpenAI
import json
import math
import os

SUPABASE_URL = "https://frfrevcsrissjgtyowtb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyZnJldmNzcmlzc2pndHlvd3RiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU3ODkyNCwiZXhwIjoyMDg3MTU0OTI0fQ.tuIHwHLcWCjwJmWB6x8cGS6ZuEQZ8VGpsmuin1_zLg0"

from dotenv import load_dotenv
load_dotenv('.env.supabase')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

print("="*70)
print("🧪 TESTING SEARCH SIMILARITY")
print("="*70)
print()

# Create embedding for test query
query = "sad"
print(f"🔍 Query: '{query}'")
print("📊 Creating embedding...")

response = client.embeddings.create(model='text-embedding-3-small', input=query)
query_embedding = response.data[0].embedding
print(f"✅ Query embedding created: {len(query_embedding)} dimensions")
print()

# Get first 3 clips with embeddings
clips = supabase.table('clips').select('id, transcript_text, embedding').limit(3).execute()

print(f"📝 Testing with {len(clips.data)} clips:")
print()

for clip in clips.data:
    clip_emb = clip.get('embedding')
    text = clip.get('transcript_text', '')
    
    if not clip_emb:
        print(f"   ❌ Clip {clip['id']}: No embedding")
        continue
    
    # Calculate similarity
    vec1 = query_embedding
    vec2 = clip_emb if isinstance(clip_emb, list) else json.loads(clip_emb)
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    similarity = dot_product / (magnitude1 * magnitude2)
    
    print(f"   Clip {clip['id']}: similarity = {similarity:.4f}")
    print(f"      Text: {text[:80]}...")
    print(f"      Embedding dims: {len(vec2)}")
    
    if similarity > 0.40:
        print(f"      ✅ PASSES threshold (>0.40)")
    else:
        print(f"      ❌ FAILS threshold (>0.40)")
    print()

# Test visual frames
vf = supabase.table('visual_frames').select('id, visual_description, visual_embedding, emotion').limit(3).execute()

print(f"🎨 Testing with {len(vf.data)} visual frames:")
print()

for frame in vf.data:
    frame_emb = frame.get('visual_embedding')
    desc = frame.get('visual_description', '')
    emotion = frame.get('emotion', '')
    
    if not frame_emb:
        print(f"   ❌ Frame {frame['id']}: No embedding")
        continue
    
    vec1 = query_embedding
    vec2 = frame_emb if isinstance(frame_emb, list) else json.loads(frame_emb)
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    similarity = dot_product / (magnitude1 * magnitude2)
    
    print(f"   Frame {frame['id']}: similarity = {similarity:.4f}")
    print(f"      Emotion: {emotion}")
    print(f"      Description: {desc[:80]}...")
    
    if similarity > 0.30:
        print(f"      ✅ PASSES threshold (>0.30)")
    else:
        print(f"      ❌ FAILS threshold (>0.30)")
    print()

print("="*70)
