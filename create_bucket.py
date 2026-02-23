#!/usr/bin/env python3
"""
Create Supabase Storage Bucket
Simple script to create the broll-videos bucket
"""

from supabase import create_client, Client

# Supabase credentials
SUPABASE_URL = "https://frfrevcsrissjgtyowtb.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyZnJldmNzcmlzc2pndHlvd3RiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU3ODkyNCwiZXhwIjoyMDg3MTU0OTI0fQ.tuIHwHLcWCjwJmWB6x8cGS6ZuEQZ8VGpsmuin1_zLg0"

BUCKET_NAME = "broll-videos"

print("🗄️  Creating Supabase Storage Bucket...")
print()

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

try:
    # Check if bucket exists first
    print(f"Checking if bucket '{BUCKET_NAME}' exists...")
    
    try:
        bucket_info = supabase.storage.get_bucket(BUCKET_NAME)
        print(f"✅ Bucket '{BUCKET_NAME}' already exists!")
        print()
        print("="*60)
        print("✅ STORAGE BUCKET READY!")
        print("="*60)
        
    except:
        # Bucket doesn't exist, create it
        print(f"Creating bucket '{BUCKET_NAME}'...")
        
        # Create bucket with minimal config
        result = supabase.storage.create_bucket(
            BUCKET_NAME,
            options={"public": True}
        )
        
        print()
        print("="*60)
        print(f"✅ CREATED BUCKET: {BUCKET_NAME}")
        print("="*60)
        print()
        print("Bucket settings:")
        print("  Public: Yes")
        print("  URL: https://frfrevcsrissjgtyowtb.supabase.co/storage/v1/object/public/broll-videos/")
        
except Exception as e:
    print(f"❌ Failed to create bucket: {str(e)}")
    print()
    print("⚠️  Please create manually:")
    print("1. Go to: https://supabase.com/dashboard/project/frfrevcsrissjgtyowtb/storage/buckets")
    print("2. Click 'New Bucket'")
    print("3. Name: broll-videos")
    print("4. Check 'Public bucket'")
    print("5. Click 'Create Bucket'")
    print()
    exit(1)

print()
print("🎯 Next: Run SQL schema")
print()
print("Go to: https://supabase.com/dashboard/project/frfrevcsrissjgtyowtb/sql")
print("Then:")
print("1. Click 'New Query'")
print("2. Copy ALL contents from supabase_schema.sql")
print("3. Paste and click RUN")
print()
