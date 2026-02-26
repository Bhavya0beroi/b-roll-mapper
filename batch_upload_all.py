#!/usr/bin/env python3
"""
Automated batch upload of all videos in uploads/ folder
Uploads to Railway server which processes and stores in Supabase
"""

import os
import requests
from pathlib import Path
import time

RAILWAY_URL = "https://web-production-b5a81.up.railway.app"

print("╔" + "="*68 + "╗")
print("║" + " "*15 + "BATCH UPLOAD ALL VIDEOS" + " "*30 + "║")
print("╚" + "="*68 + "╝")
print()

# Find all videos in uploads folder
uploads_dir = Path("uploads")
video_files = sorted([f for f in uploads_dir.glob("*") if f.suffix.lower() in ['.mp4', '.mov', '.webm', '.gif', '.avi']])

if not video_files:
    print("❌ No videos found in uploads/ folder!")
    exit(1)

print(f"📁 Found {len(video_files)} videos to upload")
print(f"🌐 Target: {RAILWAY_URL}")
print()

# Calculate total size
total_size = sum(f.stat().st_size for f in video_files)
print(f"📦 Total size: {total_size / 1024 / 1024 / 1024:.2f} GB")
print()

# Estimate time (average 45 seconds per video for AI processing)
estimated_minutes = (len(video_files) * 45) / 60
print(f"⏱️  Estimated time: {estimated_minutes:.0f} minutes")
print()

print("="*70)
input("Press ENTER to start batch upload...")
print("="*70)
print()

uploaded = 0
failed = 0
failed_videos = []

start_time = time.time()

for i, video_path in enumerate(video_files, 1):
    filename = video_path.name
    file_size_mb = video_path.stat().st_size / 1024 / 1024
    
    print(f"[{i}/{len(video_files)}] {filename} ({file_size_mb:.1f}MB)")
    print(f"   ⏳ Uploading and processing...")
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': (filename, f, 'video/mp4')}
            
            # Upload with 5 minute timeout (AI processing takes time)
            response = requests.post(
                f"{RAILWAY_URL}/upload",
                files=files,
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    uploaded += 1
                    print(f"   ✅ SUCCESS! ({uploaded}/{len(video_files)})")
                else:
                    failed += 1
                    failed_videos.append((filename, result.get('error', 'Unknown error')))
                    print(f"   ❌ FAILED: {result.get('error', 'Unknown')[:50]}")
            else:
                failed += 1
                error_msg = response.text[:100]
                failed_videos.append((filename, f"HTTP {response.status_code}"))
                print(f"   ❌ FAILED: HTTP {response.status_code}")
                
    except requests.exceptions.Timeout:
        # Timeout might mean it's still processing - check if video exists
        print(f"   ⚠️  TIMEOUT (still processing in background)")
        time.sleep(5)
        
        # Check if video was created
        try:
            check_response = requests.get(f"{RAILWAY_URL}/videos", timeout=10)
            videos = check_response.json().get('videos', [])
            if any(v['filename'] == filename for v in videos):
                uploaded += 1
                print(f"   ✅ SUCCESS (found in database)")
            else:
                failed += 1
                failed_videos.append((filename, "Timeout"))
                print(f"   ❌ FAILED (timeout)")
        except:
            failed += 1
            failed_videos.append((filename, "Timeout"))
            print(f"   ❌ FAILED (timeout)")
            
    except Exception as e:
        failed += 1
        failed_videos.append((filename, str(e)[:100]))
        print(f"   ❌ ERROR: {str(e)[:50]}")
    
    print()
    
    # Small delay between uploads
    if i < len(video_files):
        time.sleep(2)

elapsed_minutes = (time.time() - start_time) / 60

print("="*70)
print("✅ BATCH UPLOAD COMPLETE")
print("="*70)
print(f"   ✅ Successful: {uploaded}")
print(f"   ❌ Failed: {failed}")
print(f"   ⏱️  Time taken: {elapsed_minutes:.1f} minutes")
print()

if failed_videos:
    print("Failed videos:")
    for fname, error in failed_videos:
        print(f"   - {fname}: {error}")
    print()

print(f"🌐 Check your tool: {RAILWAY_URL}")
print()
