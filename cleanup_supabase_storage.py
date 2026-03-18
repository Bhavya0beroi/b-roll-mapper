"""
Supabase Storage Cleanup Script

Deletes ALL video files and thumbnails from the Supabase Storage bucket
to free up storage space on the free plan.

⚠️  Run AFTER migrate_supabase_to_mongo.py has completed successfully.
⚠️  This is IRREVERSIBLE. Video files will be permanently deleted from Supabase.

Run:
    python cleanup_supabase_storage.py
"""

import os
import sys
from dotenv import load_dotenv, dotenv_values

load_dotenv()

try:
    from supabase import create_client
except ImportError:
    print("❌ supabase package not installed. Run: pip install supabase")
    sys.exit(1)

SUPABASE_URL         = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    sb_env = dotenv_values('.env.supabase')
    SUPABASE_URL         = SUPABASE_URL         or sb_env.get('SUPABASE_URL')
    SUPABASE_SERVICE_KEY = SUPABASE_SERVICE_KEY or sb_env.get('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("❌ SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (in .env or .env.supabase)")
    sys.exit(1)

BUCKET_NAME = 'broll-videos'

print("🔌 Connecting to Supabase...")
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
print("✅ Connected\n")


def list_all_files(folder):
    """List all files in a Supabase Storage folder."""
    try:
        files = sb.storage.from_(BUCKET_NAME).list(folder)
        return [f"{folder}/{f['name']}" for f in files if f.get('name') and not f['name'].startswith('.')]
    except Exception as e:
        print(f"  ⚠️  Could not list {folder}/: {e}")
        return []


def delete_in_batches(paths, batch_size=100):
    """Delete files in batches (Supabase has a limit per request)."""
    total_deleted = 0
    for i in range(0, len(paths), batch_size):
        batch = paths[i:i + batch_size]
        try:
            sb.storage.from_(BUCKET_NAME).remove(batch)
            total_deleted += len(batch)
            print(f"  🗑️  Deleted {total_deleted}/{len(paths)} files...", end='\r')
        except Exception as e:
            print(f"\n  ⚠️  Batch delete error: {e}")
    return total_deleted


# ── List files ────────────────────────────────────────────────────────────────

print("📂 Listing files in Supabase Storage...")
video_files     = list_all_files('videos')
thumbnail_files = list_all_files('thumbnails')
all_files       = video_files + thumbnail_files

print(f"  Found {len(video_files)} video files")
print(f"  Found {len(thumbnail_files)} thumbnail files")
print(f"  Total: {len(all_files)} files\n")

if not all_files:
    print("✅ Nothing to delete. Supabase Storage is already empty.")
    sys.exit(0)

# ── Confirm ───────────────────────────────────────────────────────────────────

print("⚠️  WARNING: This will PERMANENTLY delete all files from Supabase Storage.")
print("   Make sure migrate_supabase_to_mongo.py has already run successfully.\n")
confirm = input(f"Type  YES  to delete all {len(all_files)} files: ").strip()

if confirm != 'YES':
    print("❌ Aborted. No files deleted.")
    sys.exit(0)

# ── Delete ────────────────────────────────────────────────────────────────────

print(f"\n🗑️  Deleting {len(all_files)} files...")
deleted = delete_in_batches(all_files)
print(f"\n✅ Deleted {deleted} files from Supabase Storage.")
print("   Your Supabase storage usage is now free.")
