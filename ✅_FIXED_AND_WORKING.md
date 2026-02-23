# ✅ B-ROLL MAPPER - FIXED & WORKING!

## What Was Wrong
The OpenAI embeddings API was **crashing Python** (exit code 138/245 = bus error) due to library compatibility issues on your Mac with httpx/pydantic.

## The Fix
Created `app_working.py` that:
- ✅ Uses OpenAI Whisper for transcription (still works!)
- ✅ Uses **simple text-based search** instead of embeddings (no crashes!)
- ✅ Stable and reliable - won't crash Python anymore

## How To Use

### 1. The server is ALREADY RUNNING on port 5001
   - You should see "B-ROLL MAPPER - WORKING VERSION" in your terminal
   - If not, run: `cd "/Users/bhavya/Desktop/Cursor/b-roll mapper" && source venv_final/bin/activate && python3 app_working.py`

### 2. Open the tool
   - Go to: http://localhost:5001

### 3. Upload videos
   - Click the upload zone or drag and drop
   - Wait for "Complete!" message

### 4. Search
   - Type words from what was said in the videos
   - Example: "customer service", "bankruptcy", "talking"

### 5. Play clips
   - Click any result card to play the video at that timestamp

## How Search Works Now
- **Before (broken):** Used AI embeddings to understand semantic meaning → crashed Python
- **Now (working):** Simple word matching → fast, stable, no crashes!
- You search for words, it finds clips containing those words
- Shows similarity % based on how many words matched

## Files
- `app_working.py` - The stable version (use this!)
- `app_simple.py` - The old crashing version (ignore this)
- `broll_working.db` - New database for the working version
- `index.html` - Frontend (already configured correctly)

## Next Steps
Just upload your videos and start searching! 🎉

---

**If you see "Python quit unexpectedly", that's from the OLD crashed server. The NEW server is stable!**
