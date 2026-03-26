#!/usr/bin/env python3
"""
Bulk restore script — sends local video/image files to Railway.
For files already in MongoDB, Railway SKIPS all AI processing
and just restores the file to persistent storage (seconds per file).

Usage:
    python3 bulk_restore.py /path/to/your/videos/folder
"""

import os
import sys
import requests
import time

RAILWAY_URL = "https://b-roll-mapper-production.up.railway.app"
UPLOAD_ENDPOINT = f"{RAILWAY_URL}/upload"

SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.gif', '.jpg', '.jpeg', '.png', '.heic', '.webm'}

def restore_files(folder_path):
    if not os.path.isdir(folder_path):
        print(f"❌ Folder not found: {folder_path}")
        sys.exit(1)

    files = [
        f for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f))
        and os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        print("❌ No supported video/image files found in that folder.")
        sys.exit(1)

    print(f"📁 Found {len(files)} files in: {folder_path}")
    print(f"🚀 Uploading to: {RAILWAY_URL}\n")

    success, failed = 0, []

    for i, filename in enumerate(sorted(files), 1):
        filepath = os.path.join(folder_path, filename)
        size_mb = os.path.getsize(filepath) / 1024 / 1024
        print(f"[{i}/{len(files)}] {filename} ({size_mb:.1f} MB) ... ", end='', flush=True)

        try:
            with open(filepath, 'rb') as f:
                resp = requests.post(
                    UPLOAD_ENDPOINT,
                    files={'file': (filename, f)},
                    timeout=300
                )
            if resp.status_code == 200:
                data = resp.json()
                if data.get('restored'):
                    print("♻️  Restored (skipped AI processing)")
                else:
                    print("✅ Uploaded & processed")
                success += 1
            else:
                print(f"❌ HTTP {resp.status_code}: {resp.text[:100]}")
                failed.append(filename)
        except Exception as e:
            print(f"❌ Error: {e}")
            failed.append(filename)

        time.sleep(0.3)

    print(f"\n{'='*50}")
    print(f"✅ Success: {success}/{len(files)}")
    if failed:
        print(f"❌ Failed ({len(failed)}):")
        for f in failed:
            print(f"   - {f}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 bulk_restore.py /path/to/your/videos/folder")
        sys.exit(1)
    restore_files(sys.argv[1])
