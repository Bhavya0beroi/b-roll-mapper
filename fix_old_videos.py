#!/usr/bin/env python3
"""
Fix old migrated videos:
1. Upload missing video files to Supabase Storage
2. Update database with Supabase URLs
3. Generate titles from filenames
"""

import os
from pathlib import Path
from supabase import create_client, Client

SUPABASE_URL = "https://frfrevcsrissjgtyowtb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyZnJldmNzcmlzc2pndHlvd3RiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU3ODkyNCwiZXhwIjoyMDg3MTU0OTI0fQ.tuIHwHLcWCjwJmWB6x8cGS6ZuEQZ8VGpsmuin1_zLg0"
BUCKET_NAME = "broll-videos"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("="*70)
print("🔧 FIXING OLD VIDEOS IN SUPABASE")
print("="*70)
print()

# Get all videos from database
result = supabase.table('videos').select('*').execute()
videos = result.data

print(f"📊 Found {len(videos)} videos in database")
print()

# Check local uploads folder
uploads_dir = Path("uploads")
if not uploads_dir.exists():
    print("❌ uploads/ folder not found!")
    print("   Please ensure videos are in the uploads/ folder")
    exit(1)

local_files = {f.name: f for f in uploads_dir.glob("*") if f.suffix in ['.mp4', '.mov', '.webm', '.gif']}
print(f"📁 Found {len(local_files)} video files in uploads/")
print()

print("="*70)
print("🚀 PROCESSING VIDEOS")
print("="*70)
print()

uploaded = 0
updated = 0
skipped = 0
failed = 0

for i, video in enumerate(videos, 1):
    video_id = video['id']
    filename = video['filename']
    current_url = video.get('supabase_video_url') or ''
    
    print(f"[{i}/{len(videos)}] {filename[:50]}...", end=" ")
    
    # Check if video needs URL update
    needs_upload = not current_url or len(current_url) < 100
    
    if needs_upload and filename in local_files:
        try:
            # Upload to Supabase Storage
            local_path = local_files[filename]
            with open(local_path, 'rb') as f:
                video_data = f.read()
            
            storage_path = f"videos/{filename}"
            supabase.storage.from_(BUCKET_NAME).upload(
                storage_path,
                video_data,
                file_options={"content-type": "video/mp4", "upsert": "true"}
            )
            
            new_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{storage_path}"
            uploaded += 1
            print(f"📤 uploaded", end=" ")
            
        except Exception as e:
            if "already exists" in str(e):
                # File already in storage, just use the URL
                new_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/videos/{filename}"
                skipped += 1
                print(f"✓ exists", end=" ")
            else:
                failed += 1
                print(f"❌ {str(e)[:30]}")
                continue
    elif needs_upload:
        # Video file not found locally
        failed += 1
        print(f"❌ file not found")
        continue
    else:
        # Already has valid URL
        new_url = current_url
        skipped += 1
        print(f"✓ has URL", end=" ")
    
    # Generate title from filename if missing
    title = video.get('title') or ''
    if not title or title == 'No title':
        # Extract title from filename
        title = filename.replace('.mp4', '').replace('.mov', '').replace('.webm', '').replace('.gif', '')
        title = title.replace('_', ' ').replace('-', ' ')
        # Clean up "Copy of " prefix
        if title.startswith("Copy of "):
            title = title[8:]
    
    # Update database with URL and title
    try:
        supabase.table('videos').update({
            'supabase_video_url': new_url,
            'title': title
        }).eq('id', video_id).execute()
        updated += 1
        print(f"→ ✅ updated")
    except Exception as e:
        print(f"→ ❌ DB update failed: {str(e)[:40]}")
        failed += 1

print()
print("="*70)
print("✅ PROCESSING COMPLETE")
print("="*70)
print(f"   📤 Uploaded: {uploaded}")
print(f"   ✓ Already existed: {skipped}")
print(f"   ✏️  Database updated: {updated}")
print(f"   ❌ Failed: {failed}")
print()
print(f"🌐 Your videos are now accessible at:")
print(f"   https://web-production-b5a81.up.railway.app")
print()
