#!/usr/bin/env python3
"""
Direct PostgreSQL Setup for Supabase
Connects directly to PostgreSQL to create schema
"""

import psycopg2
from psycopg2 import sql
import os

# Supabase PostgreSQL connection
# Format: postgresql://postgres.[project-ref]:[password]@aws-0-us-west-1.pooler.supabase.com:6543/postgres
SUPABASE_URL = "https://frfrevcsrissjgtyowtb.supabase.co"
PROJECT_REF = "frfrevcsrissjgtyowtb"

print("╔" + "="*58 + "╗")
print("║" + " "*10 + "SUPABASE DATABASE SETUP (DIRECT)" + " "*16 + "║")
print("╚" + "="*58 + "╝")
print()

print("To connect directly to PostgreSQL, I need your database password.")
print()
print("📋 HOW TO GET YOUR DATABASE PASSWORD:")
print()
print("1. Go to: https://supabase.com/dashboard/project/frfrevcsrissjgtyowtb/settings/database")
print("2. Look for 'Database Password' section")
print("3. Click 'Generate new password' if you haven't set one")
print("4. Copy the password")
print()

db_password = input("Enter your Supabase database password: ").strip()

if not db_password:
    print("❌ No password provided. Exiting.")
    exit(1)

print()
print("🔗 Connecting to PostgreSQL...")

# URL-encode the password to handle special characters
from urllib.parse import quote_plus
encoded_password = quote_plus(db_password)

# Connection string
conn_string = f"postgresql://postgres.{PROJECT_REF}:{encoded_password}@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

try:
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
    
    print("✅ Connected to Supabase PostgreSQL!")
    print()
    
    # Read SQL schema
    print("📄 Reading supabase_schema.sql...")
    with open('supabase_schema.sql', 'r') as f:
        sql_schema = f.read()
    
    print("📊 Executing SQL schema...")
    print()
    
    # Execute the entire SQL file
    cursor.execute(sql_schema)
    conn.commit()
    
    print("✅ Database schema created successfully!")
    print()
    
    # Verify tables were created
    print("🔍 Verifying tables...")
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('videos', 'clips', 'visual_frames')
    """)
    
    tables = cursor.fetchall()
    print()
    for table in tables:
        print(f"  ✅ Table '{table[0]}' created")
    
    cursor.close()
    conn.close()
    
    print()
    print("="*60)
    print("🎉 DATABASE SETUP COMPLETE!")
    print("="*60)
    print()
    print("Next steps:")
    print("1. Create storage bucket (I'll do this next)")
    print("2. Run: python3 migrate_to_supabase.py")
    print("3. Run: python3 upload_videos_to_supabase.py")
    print()
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    print()
    print("⚠️  Please run the SQL manually:")
    print("1. Go to: https://supabase.com/dashboard/project/frfrevcsrissjgtyowtb/sql")
    print("2. Copy all contents of supabase_schema.sql")
    print("3. Paste and click RUN")
    print()
    exit(1)
