#!/usr/bin/env python3
"""
Download videos from Google Drive and upload to Supabase Storage
"""

import os
import requests
from supabase import create_client, Client
from pathlib import Path
import time

# Supabase credentials
SUPABASE_URL = "https://frfrevcsrissjgtyowtb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyZnJldmNzcmlzc2pndHlvd3RiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU3ODkyNCwiZXhwIjoyMDg3MTU0OTI0fQ.tuIHwHLcWCjwJmWB6x8cGS6ZuEQZ8VGpsmuin1_zLg0"

BUCKET_NAME = "broll-videos"

# Google Drive folder ID
GDRIVE_FOLDER_ID = "1U4wRpULwe0CLj2hqg5wWOSgPbdOK-MCz"

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# List of videos from Google Drive (extracted from the link)
VIDEOS = [
    "Demolition - Candy Vending Machine Scene.mp4",
    "Demolition - Danicng at Metro Station Scene.mp4",
    "Demolition - Danicng Carefree in Public Scene_2.mp4",
    "Demolition - Danicng Carefree in Public Scene.mp4",
    "Demolition - Destructing the house scene.mp4",
    "Demolition - Destructing the wall Scene.mp4",
    "Demolition - Driving Scene.mp4",
    "Demolition - Merry go round Scene.mp4",
    "Demolition - Mourning in Car Scene.mp4",
    "Demolition - Mourning in Graveyard Scene.mp4",
    "Demolition - Paying the Workers Scene.mp4",
    "Demolition - Refrigerator Frustration Scene.mp4",
    "Demolition - Refrigerator Scene.mp4",
    "Demolition - Running Scene.mp4",
    "Demolition - Smile Scene.mp4",
    "Demolition - Stamping Letters Scene.mp4",
    "Demolition - Talking to Construction Workers Scene.mp4",
    "Demolition - Walking Confused and Smiling Scene.mp4",
    "Demolition - walking through office gallery Scene.mp4",
    "Demolition - Walking With Headphones in a crowd Scene.mp4",
    "Demolition - Writing Letters Scene.mp4",
    "Fight Club 1999_ cab and catastrophe scene.mp4",
    "Fight Club 1999_ calling from booth scene.mp4",
    "Fight Club 1999_ Coming back to senses.mp4",
    "Fight Club 1999_ Confused scene.mp4",
    "Fight Club 1999_ Desperately picking up the call.mp4",
    "Fight Club 1999_ Lost in thoughts scene.mp4",
    "Fight Club 1999_ Luggage at airport scene.mp4",
    "Fight Club 1999_ Luxury Car Scene.mp4",
    "Fight Club 1999_ meeting scene.mp4",
    "Fight Club 1999_ Realization scene.mp4",
    "Fight Club 1999_ Thinking scene.mp4",
    "Fight Club 1999_ waking up scene.mp4",
    "Jobs (2013) - Board Meeting Scene.mp4",
    "Jobs (2013) - Ideas coming to life.mp4",
    "Jobs (2013) - Steve talks about his vision.mp4",
    "Jobs and Markkula negotiating the investment deal sealed.mp4",
    "Jobs and Markkula negotiating the investment deal.mp4",
    "Jobs frustrated_sad.mp4",
    "Jobs relaxing in office.mp4",
    "Jobs studying under lamp light.mp4",
    "Jobs working with a friend.mp4",
    "Jobs_Leaving work scene.mp4",
    "Steve commands to present samples.mp4",
    "Steve fires due to Francis's lack of vision for the company.mp4",
    "Steve fires Francis due to lack of fonts.mp4",
    "Steve Jobs Building PC.mp4",
    "Steve Jobs calls Bill Gates in JOBS.mp4",
    "Steve Jobs Frustrated while talking on phone.mp4",
    "Steve Jobs Meets the team in Garage.mp4",
]

print("╔" + "="*58 + "╗")
print("║" + " "*10 + "GOOGLE DRIVE → SUPABASE UPLOAD" + " "*17 + "║")
print("╚" + "="*58 + "╝")
print()
print(f"📁 Google Drive folder: {GDRIVE_FOLDER_ID}")
print(f"🗄️  Supabase bucket: {BUCKET_NAME}")
print(f"📹 Videos to process: {len(VIDEOS)}")
print()
print("⚠️  NOTE: Google Drive direct download requires authentication.")
print("    Please manually download videos to 'uploads/' folder first.")
print()
print("="*60)
print("ALTERNATIVE: Upload from local uploads/ folder")
print("="*60)
print()

# Check if uploads folder exists
uploads_dir = Path("uploads")
if uploads_dir.exists():
    local_videos = list(uploads_dir.glob("*.mp4")) + list(uploads_dir.glob("*.gif"))
    
    if local_videos:
        print(f"✅ Found {len(local_videos)} videos in uploads/ folder")
        print()
        print("🚀 Starting automatic upload...")
        print()
        
        if True:  # Auto-proceed
            print()
            print("="*60)
            print("📤 UPLOADING VIDEOS TO SUPABASE STORAGE")
            print("="*60)
            print()
            
            uploaded = 0
            failed = 0
            
            for video_path in local_videos:
                filename = video_path.name
                
                try:
                    print(f"  [{uploaded + failed + 1}/{len(local_videos)}] Uploading: {filename}...", end=" ")
                    
                    # Read video file
                    with open(video_path, 'rb') as f:
                        video_data = f.read()
                    
                    # Upload to Supabase Storage
                    storage_path = f"videos/{filename}"
                    supabase.storage.from_(BUCKET_NAME).upload(
                        storage_path,
                        video_data,
                        file_options={"content-type": "video/mp4", "upsert": "true"}
                    )
                    
                    # Get public URL
                    video_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{storage_path}"
                    
                    # Update database with Supabase URL
                    result = supabase.table('videos').update({
                        'supabase_video_url': video_url
                    }).eq('filename', filename).execute()
                    
                    uploaded += 1
                    print("✅")
                    
                except Exception as e:
                    failed += 1
                    print(f"❌ {str(e)[:50]}")
            
            print()
            print("="*60)
            print(f"✅ UPLOAD COMPLETE: {uploaded} success, {failed} failed")
            print("="*60)
            print()
            print(f"🌐 Videos are now accessible at:")
            print(f"   {SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/videos/")
            print()
            print(f"🎯 Next: Open your deployed tool:")
            print(f"   https://web-production-b5a81.up.railway.app")
            print()
        else:
            print("Upload cancelled.")
    else:
        print("❌ No videos found in uploads/ folder")
else:
    print("❌ uploads/ folder not found")
    print()
    print("📋 MANUAL STEPS:")
    print()
    print("1. Download videos from Google Drive:")
    print(f"   https://drive.google.com/drive/folders/1U4wRpULwe0CLj2hqg5wWOSgPbdOK-MCz")
    print()
    print("2. Save them to: uploads/ folder")
    print()
    print("3. Run this script again:")
    print("   python3 download_and_upload_videos.py")
    print()
