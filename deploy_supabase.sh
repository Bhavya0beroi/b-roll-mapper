#!/bin/bash

# B-Roll Mapper - Supabase Deployment Quick Start
# Run this script to deploy your tool step-by-step

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         B-ROLL MAPPER - SUPABASE DEPLOYMENT                ║"
echo "║                   QUICK START SCRIPT                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check prerequisites
echo -e "${YELLOW}STEP 1: Checking prerequisites...${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.9+${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python 3 found: $(python3 --version)${NC}"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip3 not found. Please install pip${NC}"
    exit 1
fi
echo -e "${GREEN}✅ pip3 found${NC}"

# Check if database exists
if [ ! -f "broll_semantic.db" ]; then
    echo -e "${RED}❌ broll_semantic.db not found. Please ensure your database exists.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ SQLite database found${NC}"

echo ""
echo -e "${YELLOW}STEP 2: Installing dependencies...${NC}"
pip3 install supabase python-dotenv psycopg2-binary

echo ""
echo -e "${GREEN}✅ Dependencies installed${NC}"

echo ""
echo "════════════════════════════════════════════════════════════"
echo ""
echo -e "${YELLOW}STEP 3: Supabase Setup Instructions${NC}"
echo ""
echo "Before running the migration, complete these steps:"
echo ""
echo "1. Go to: https://supabase.com/dashboard/project/frfrevcsrissjgtyowtb"
echo "2. Click 'SQL Editor' in the left sidebar"
echo "3. Click 'New Query'"
echo "4. Open the file: supabase_schema.sql"
echo "5. Copy ALL contents and paste into the SQL Editor"
echo "6. Click 'RUN'"
echo ""
echo "Expected result: 'Success. No rows returned.'"
echo ""
read -p "Press ENTER once you've completed the SQL schema setup..."

echo ""
echo -e "${YELLOW}STEP 4: Creating Storage Bucket${NC}"
echo ""
echo "Now create the storage bucket:"
echo ""
echo "1. Go to: https://supabase.com/dashboard/project/frfrevcsrissjgtyowtb/storage/buckets"
echo "2. Click 'New Bucket'"
echo "3. Name: broll-videos"
echo "4. ✅ Check 'Public bucket'"
echo "5. Click 'Create Bucket'"
echo ""
read -p "Press ENTER once you've created the storage bucket..."

echo ""
echo -e "${YELLOW}STEP 5: Running Database Migration${NC}"
echo ""
read -p "Ready to migrate your data from SQLite to Supabase? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 migrate_to_supabase.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Database migration completed!${NC}"
    else
        echo -e "${RED}❌ Migration failed. Please check errors above.${NC}"
        exit 1
    fi
else
    echo "Migration skipped."
fi

echo ""
echo -e "${YELLOW}STEP 6: Uploading Videos to Supabase Storage${NC}"
echo ""
read -p "Ready to upload videos to Supabase Storage? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 upload_videos_to_supabase.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Videos uploaded successfully!${NC}"
    else
        echo -e "${RED}❌ Upload failed. Please check errors above.${NC}"
        exit 1
    fi
else
    echo "Video upload skipped."
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo ""
echo -e "${GREEN}🎉 SUPABASE MIGRATION COMPLETE!${NC}"
echo ""
echo "Next Steps:"
echo ""
echo "1. Update Flask app to use Supabase (I'll help with this)"
echo "2. Test locally with Supabase backend"
echo "3. Deploy to Railway"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📖 For detailed instructions, see: DEPLOYMENT_GUIDE.md"
echo ""
