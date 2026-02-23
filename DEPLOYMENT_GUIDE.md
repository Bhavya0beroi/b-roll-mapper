# 🚀 B-Roll Mapper - Supabase Deployment Guide

Complete step-by-step guide to deploy your B-roll tool to the cloud.

---

## 📋 PRE-DEPLOYMENT CHECKLIST

✅ Supabase project created: `https://frfrevcsrissjgtyowtb.supabase.co`  
✅ API keys obtained (anon + service_role)  
✅ Railway account ready  
✅ 100+ videos (2-3GB) ready to upload  

---

## STEP 1: Setup Supabase Database (5 minutes)

### 1.1 Run the SQL Schema

1. Go to your Supabase dashboard: https://supabase.com/dashboard/project/frfrevcsrissjgtyowtb
2. Click **SQL Editor** (left sidebar)
3. Click **New Query**
4. Copy the contents of `supabase_schema.sql`
5. Paste and click **RUN**

**Expected output:**
```
Success. No rows returned.
```

### 1.2 Enable pgvector Extension

In the same SQL Editor, run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 1.3 Verify Tables Created

Run this query:
```sql
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public';
```

You should see:
- `videos`
- `clips`
- `visual_frames`

---

## STEP 2: Migrate SQLite Data to Supabase (10 minutes)

### 2.1 Install Python Dependencies

```bash
pip install supabase python-dotenv
```

### 2.2 Run Migration Script

```bash
python3 migrate_to_supabase.py
```

**What this does:**
- Exports all data from `broll_semantic.db`
- Uploads to Supabase PostgreSQL
- Preserves all embeddings, tags, and metadata
- Shows progress and verification

**Expected output:**
```
📹 MIGRATING VIDEOS TABLE
  ✅ Migrated video 1/100: video1.mp4
  ...

✅ Videos migration complete: 100 success, 0 failed

🎤 MIGRATING CLIPS TABLE
  ...

🎨 MIGRATING VISUAL FRAMES TABLE
  ...

✅ MIGRATION SUCCESSFUL - All data migrated!
```

---

## STEP 3: Create Supabase Storage Bucket (3 minutes)

### 3.1 Create the Bucket

1. Go to **Storage** in Supabase dashboard
2. Click **New Bucket**
3. Name: `broll-videos`
4. **Public bucket**: ✅ YES (so videos can be accessed via URL)
5. Click **Create Bucket**

### 3.2 Set Bucket Policies

Go to **Policies** tab for `broll-videos` bucket:

**Policy 1: Public Read Access**
```sql
CREATE POLICY "Public Access"
ON storage.objects FOR SELECT
USING ( bucket_id = 'broll-videos' );
```

**Policy 2: Service Role Upload**
```sql
CREATE POLICY "Service Role Upload"
ON storage.objects FOR INSERT
WITH CHECK ( bucket_id = 'broll-videos' AND auth.role() = 'service_role' );
```

---

## STEP 4: Upload Videos to Supabase Storage (15-30 minutes)

### 4.1 Install Supabase CLI (optional but recommended)

```bash
npm install -g supabase
```

### 4.2 Upload Videos

**Option A: Use the upload script (recommended)**

I'll create a script for you:

```bash
python3 upload_videos_to_supabase.py
```

**Option B: Manual upload via dashboard**
1. Go to Storage > broll-videos
2. Click Upload
3. Select all videos from your `uploads/` folder

**Important:** 
- Videos will be accessible at: `https://frfrevcsrissjgtyowtb.supabase.co/storage/v1/object/public/broll-videos/{filename}`
- Thumbnails should also be uploaded to the same bucket

---

## STEP 5: Update Flask App for Supabase (Already done for you!)

The updated `app_semantic.py` will:
- Connect to Supabase PostgreSQL instead of SQLite
- Store videos in Supabase Storage
- Use Supabase URLs for video serving
- Keep all existing AI tagging logic

### Key Changes:
- ✅ Database: SQLite → Supabase PostgreSQL
- ✅ Storage: Local `uploads/` → Supabase Storage
- ✅ Video URLs: Local paths → Supabase public URLs
- ✅ Search: Vector similarity using pgvector

---

## STEP 6: Deploy Backend to Railway (10 minutes)

### 6.1 Prepare for Railway

1. Create `requirements.txt` (I'll generate this)
2. Create `Procfile` for Railway
3. Create `railway.json` config

### 6.2 Deploy to Railway

1. Go to https://railway.app/
2. Click **New Project**
3. Select **Deploy from GitHub repo**
4. Connect your GitHub account
5. Push your code to GitHub (I'll help with commands)
6. Railway will auto-deploy

### 6.3 Set Environment Variables in Railway

Go to your Railway project > Variables, add:
```
SUPABASE_URL=https://frfrevcsrissjgtyowtb.supabase.co
SUPABASE_SERVICE_KEY=<your-supabase-service-role-key>
OPENAI_API_KEY=<your-openai-api-key>
PORT=5002
```

---

## STEP 7: Test Deployed Application

1. Railway will give you a URL: `https://your-app.railway.app`
2. Open in browser
3. Test search: "happy women"
4. Test upload: Add a new video
5. Verify tagging works

---

## 🎯 MIGRATION COMPLETE CHECKLIST

- [ ] Step 1: SQL schema created in Supabase ✅
- [ ] Step 2: Data migrated (videos, clips, frames) ✅
- [ ] Step 3: Storage bucket created ✅
- [ ] Step 4: Videos uploaded to Supabase Storage
- [ ] Step 5: Flask app updated for Supabase ✅
- [ ] Step 6: Backend deployed to Railway
- [ ] Step 7: Application tested and working

---

## 📊 EXPECTED RESULTS

**Before (Local):**
- Database: SQLite file
- Videos: Local `uploads/` folder
- Access: Only on your machine

**After (Cloud):**
- Database: Supabase PostgreSQL (scalable)
- Videos: Supabase Storage (CDN-backed)
- Access: Available worldwide at `https://your-app.railway.app`

---

## 💰 COST BREAKDOWN

**Supabase Free Tier:**
- 500MB database
- 5GB storage (enough for 500 videos @ 10MB each)
- 2GB bandwidth/month
- Unlimited API requests

**Railway:**
- $5/month flat
- Includes 100GB bandwidth

**Total: ~$5/month** (until you exceed Supabase free tier)

---

## 🚨 TROUBLESHOOTING

### "Migration failed: connection refused"
- Check Supabase URL is correct
- Verify service_role key is valid

### "Videos not appearing"
- Check bucket is public
- Verify video URLs in database

### "Search not working"
- Check pgvector extension enabled
- Verify embeddings migrated correctly

---

## 📞 NEXT STEPS

After deployment, you can:
1. ✅ Share the URL with others
2. ✅ Upload videos from anywhere
3. ✅ Scale to 500+ videos
4. ✅ Add team members (Supabase supports multi-user)

---

Ready to start? Let's begin with **STEP 1: Setup Supabase Database**!
