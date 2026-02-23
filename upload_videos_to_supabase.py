#!/usr/bin/env python3
"""
Upload Videos to Supabase Storage
Uploads all videos from local uploads/ folder to Supabase Storage bucket
"""

import os
from supabase import create_client, Client
from pathlib import Path
import mimetypes

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Supabase credentials - load from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://frfrevcsrissjgtyowtb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_KEY:
    print("❌ ERROR: SUPABASE_SERVICE_KEY not found in environment variables!")
    print("Please set it in .env.supabase or export it:")
    print("export SUPABASE_SERVICE_KEY='your-service-role-key'")
    exit(1)

# Storage bucket name
BUCKET_NAME = "broll-videos"

# Local folders
UPLOADS_FOLDER = "uploads"
THUMBNAILS_FOLDER = "thumbnails"

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def create_bucket_if_not_exists():
    """Create the storage bucket if it doesn't exist"""
    try:
        # Try to get bucket info
        supabase.storage.get_bucket(BUCKET_NAME)
        print(f"✅ Bucket '{BUCKET_NAME}' already exists")
    except:
        # Create bucket if it doesn't exist
        try:
            supabase.storage.create_bucket(BUCKET_NAME, options={"public": True})
            print(f"✅ Created bucket '{BUCKET_NAME}'")
        except Exception as e:
            print(f"⚠️  Could not create bucket: {e}")
            print("   Please create it manually in Supabase dashboard")

def upload_file(local_path, remote_path, file_type="video"):
    """Upload a single file to Supabase Storage"""
    try:
        with open(local_path, 'rb') as f:
            file_data = f.read()
        
        # Get MIME type
        mime_type = mimetypes.guess_type(local_path)[0] or 'application/octet-stream'
        
        # Upload to Supabase Storage
        result = supabase.storage.from_(BUCKET_NAME).upload(
            remote_path,
            file_data,
            file_options={"content-type": mime_type, "upsert": "true"}
        )
        
        # Get public URL
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(remote_path)
        
        return True, public_url
        
    except Exception as e:
        return False, str(e)

def upload_videos():
    """Upload all videos from uploads/ folder"""
    print("\n" + "="*60)
    print("📹 UPLOADING VIDEOS TO SUPABASE STORAGE")
    print("="*60)
    
    if not os.path.exists(UPLOADS_FOLDER):
        print(f"❌ ERROR: '{UPLOADS_FOLDER}' folder not found!")
        return 0, 0
    
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(Path(UPLOADS_FOLDER).glob(f'*{ext}'))
        video_files.extend(Path(UPLOADS_FOLDER).glob(f'*{ext.upper()}'))
    
    print(f"Found {len(video_files)} videos to upload...")
    
    uploaded = 0
    failed = 0
    
    for video_path in video_files:
        filename = video_path.name
        remote_path = f"videos/{filename}"
        
        print(f"\n  Uploading: {filename}...", end=" ")
        
        success, result = upload_file(str(video_path), remote_path, "video")
        
        if success:
            uploaded += 1
            print(f"✅")
            print(f"    URL: {result}")
        else:
            failed += 1
            print(f"❌")
            print(f"    Error: {result}")
    
    print(f"\n{'='*60}")
    print(f"✅ Videos upload complete: {uploaded} success, {failed} failed")
    
    return uploaded, failed

def upload_thumbnails():
    """Upload all thumbnails from thumbnails/ folder"""
    print("\n" + "="*60)
    print("🖼️  UPLOADING THUMBNAILS TO SUPABASE STORAGE")
    print("="*60)
    
    if not os.path.exists(THUMBNAILS_FOLDER):
        print(f"⚠️  '{THUMBNAILS_FOLDER}' folder not found, skipping...")
        return 0, 0
    
    thumbnail_files = list(Path(THUMBNAILS_FOLDER).glob('*.jpg')) + \
                     list(Path(THUMBNAILS_FOLDER).glob('*.png'))
    
    print(f"Found {len(thumbnail_files)} thumbnails to upload...")
    
    uploaded = 0
    failed = 0
    
    for thumb_path in thumbnail_files:
        filename = thumb_path.name
        remote_path = f"thumbnails/{filename}"
        
        print(f"  Uploading: {filename}...", end=" ")
        
        success, result = upload_file(str(thumb_path), remote_path, "thumbnail")
        
        if success:
            uploaded += 1
            print(f"✅")
        else:
            failed += 1
            print(f"❌ {result}")
    
    print(f"\n{'='*60}")
    print(f"✅ Thumbnails upload complete: {uploaded} success, {failed} failed")
    
    return uploaded, failed

def update_database_urls():
    """Update video URLs in Supabase database"""
    print("\n" + "="*60)
    print("🔄 UPDATING VIDEO URLS IN DATABASE")
    print("="*60)
    
    try:
        # Get all videos from database
        videos = supabase.table('videos').select('id, filename').execute()
        
        updated = 0
        
        for video in videos.data:
            video_id = video['id']
            filename = video['filename']
            
            # Construct Supabase Storage URL
            video_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/videos/{filename}"
            thumbnail_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/thumbnails/{filename}.jpg"
            
            # Update database
            result = supabase.table('videos').update({
                'supabase_video_url': video_url,
                'thumbnail': thumbnail_url
            }).eq('id', video_id).execute()
            
            updated += 1
            print(f"  ✅ Updated: {filename}")
        
        print(f"\n✅ Updated {updated} video URLs in database")
        return updated
        
    except Exception as e:
        print(f"❌ Failed to update URLs: {e}")
        return 0

if __name__ == "__main__":
    print("╔" + "="*58 + "╗")
    print("║" + " "*10 + "UPLOAD VIDEOS TO SUPABASE STORAGE" + " "*15 + "║")
    print("╚" + "="*58 + "╝")
    
    print(f"\n✅ Supabase URL: {SUPABASE_URL}")
    print(f"✅ Storage Bucket: {BUCKET_NAME}")
    
    input("\n⚠️  Press ENTER to start upload (or Ctrl+C to cancel)...\n")
    
    try:
        # Create bucket if needed
        create_bucket_if_not_exists()
        
        # Upload videos
        videos_ok, videos_failed = upload_videos()
        
        # Upload thumbnails
        thumbs_ok, thumbs_failed = upload_thumbnails()
        
        # Update database URLs
        if videos_ok > 0:
            updated = update_database_urls()
        
        print("\n" + "="*60)
        print("🎉 UPLOAD COMPLETE!")
        print("="*60)
        print(f"\nVideos uploaded: {videos_ok}/{videos_ok + videos_failed}")
        print(f"Thumbnails uploaded: {thumbs_ok}/{thumbs_ok + thumbs_failed}")
        print(f"\nYour videos are now accessible at:")
        print(f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/videos/")
        
    except KeyboardInterrupt:
        print("\n\n❌ Upload cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Upload failed: {str(e)}")
        import traceback
        traceback.print_exc()
