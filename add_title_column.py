#!/usr/bin/env python3
"""Add title column to videos table"""

from supabase import create_client, Client
import psycopg2

SUPABASE_URL = "https://frfrevcsrissjgtyowtb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyZnJldmNzcmlzc2pndHlvd3RiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU3ODkyNCwiZXhwIjoyMDg3MTU0OTI0fQ.tuIHwHLcWCjwJmWB6x8cGS6ZuEQZ8VGpsmuin1_zLg0"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("="*70)
print("🔧 ADDING TITLE COLUMN TO VIDEOS TABLE")
print("="*70)
print()

try:
    # Execute SQL via RPC or direct query
    sql = "ALTER TABLE videos ADD COLUMN IF NOT EXISTS title TEXT;"
    
    # Use Supabase's postgREST API to execute raw SQL
    result = supabase.rpc('exec_sql', {'sql': sql}).execute()
    print("✅ Title column added!")
    
except Exception as e:
    print(f"⚠️  SQL execution via Supabase client not supported: {e}")
    print()
    print("📋 Please run this SQL manually in Supabase SQL Editor:")
    print()
    print("   ALTER TABLE videos ADD COLUMN IF NOT EXISTS title TEXT;")
    print()
    print("   URL: https://supabase.com/dashboard/project/frfrevcsrissjgtyowtb/sql/new")
    print()
