# 📖 Quick Start Guide - Advanced B-Roll Search Tool

## 🚀 Getting Started

### 1. Start the Server (If Not Running)
```bash
cd "/Users/bhavya/Desktop/Cursor/b-roll mapper"
source venv_embeddings/bin/activate
python3 app_semantic.py
```

### 2. Open the Tool
```
http://localhost:5002/index_semantic.html
```

---

## 📤 Upload Videos

### Single Video Upload
1. Click **"Choose File"** button
2. Select a video file (MP4, MOV, AVI, GIF)
3. Wait for upload + transcription
4. Video appears in **Video Library**

### Batch Upload (5+ Videos)
1. Click **"Choose File"** button
2. Hold **Shift** or **Cmd** and select multiple files
3. All files upload sequentially
4. Progress bar shows: "Processing: [filename] (X/Y)"
5. All videos appear in library when complete

**Supported Formats:** MP4, MOV, AVI, WEBM, MKV, GIF

---

## 🎨 Generate Visual Analysis (Actor Detection)

### For Each Video
1. **Find video** in Video Library
2. **Hover** over the video card
3. Click **"🎨 Generate Visuals"** button
4. **Confirm** the action (shows features + cost)
5. **Wait** 30-60 seconds

### Button States
- **🎨 Generate Visuals** → Initial state
- **⏳ Processing...** → Analysis in progress
- **✓ Complete** → Success (shows for 3 seconds)
- **🔄 Regenerate** → Can re-analyze anytime

### What Gets Analyzed
✅ **Actor Recognition** (e.g., Shahid Kapoor, Bhuvan Arora)  
✅ **Series Identification** (e.g., Farzi, Scam 1992)  
✅ **Deep Emotions** (triumphant, euphoric, rebellious joy)  
✅ **Scene Context** (business deal, celebration, confrontation)  
✅ **Visual Elements** (sunglasses, suits, environments)  
✅ **On-Screen Text** (OCR detection)  

**Cost:** ~$0.05 per video (3 frames analyzed)

---

## 🔍 Search Your B-Roll Library

### Search Types

#### 1. Actor Name Search
```
Search: "Shahid Kapoor"
→ Returns all clips with Shahid Kapoor
→ High relevance (80%+ similarity)
```

#### 2. Series/Movie Search
```
Search: "Farzi"
→ Returns all Farzi clips
→ High relevance (88%+ similarity)
```

#### 3. Deep Emotion Search
```
Search: "triumphant"
→ Returns clips with triumphant mood
→ More specific than just "happy"
```

#### 4. Scene Context Search
```
Search: "business deal"
→ Returns negotiation/business scenes
→ Context-aware results
```

#### 5. Visual Element Search
```
Search: "sunglasses"
→ Returns clips where sunglasses appear
→ Ranked by prominence
```

#### 6. Combo Search
```
Search: "Shahid Kapoor sunglasses"
→ Returns Farzi clips matching both
→ High relevance for exact matches
```

---

## 🎯 Filters (Optional)

### Using Filters with Search
1. Click **"Filter"** button (right of search bar)
2. Select **Emotions** (happy, sad, confident, etc.)
3. Select **Genres** (Drama, Comedy, Crime, etc.)
4. Click **"Search with Filters"** button inside panel
5. Results show only matching videos

### Filter-Only (No Search Text)
1. Leave search bar empty
2. Open filter panel
3. Select filters
4. Click **"Search with Filters"**
5. Returns all videos matching selected filters

**Note:** Filters work **alongside** semantic search, not instead of it.

---

## 🎬 Play Videos

### From Library
1. Click on any video card in **Video Library**
2. Video plays in the **Video Player** below search
3. Shows filename, timestamp, and metadata

### From Search Results
1. Type a search query
2. Click on any result card
3. Video plays at the exact timestamp

---

## 🗑️ Delete Videos

### To Remove a Video
1. **Hover** over video card
2. Click **🗑️ Delete** button
3. **Confirm** deletion
4. Video removed from:
   - Database
   - Storage
   - Search index
   - All embeddings

**Note:** You can re-upload the same file after deletion.

---

## 💡 Search Examples (Farzi Video)

### Example 1: Find Shahid Kapoor Clips
```
Search: "Shahid Kapoor"

Results:
✅ Farzi Scene 1 - 81.09%
✅ Farzi Scene 2 - 79.25%
✅ Farzi Scene 3 - 76.22%

All Farzi clips with Shahid Kapoor returned!
```

### Example 2: Find Triumphant Moments
```
Search: "triumphant"

Results:
✅ Wolf of Wall Street - 71.64%
✅ Farzi Scene 1 - 54.61%
✅ Farzi Scene 3 - 51.80%

Deep emotion search working!
```

### Example 3: Find Business Scenes
```
Search: "business deal negotiation"

Results:
✅ Farzi clips (business deal context)
✅ Office B-roll
✅ Corporate scenes

Scene context search working!
```

---

## 🎯 Best Practices

### 1. Generate Visuals for All Videos
- Visual analysis is **optional** but highly recommended
- Without it, only transcripts are searchable
- With it, actors, series, emotions, visuals are searchable

### 2. Be Specific with Searches
- **Good:** "Shahid Kapoor sunglasses"
- **Better:** "triumphant celebration scene"
- **Best:** "Farzi business deal negotiation"

### 3. Use Filters for Precision
- Combine search + filters for best results
- Example: "office" + Emotion: "serious" → serious office scenes

### 4. Re-Generate if Needed
- If tagging seems off, click **"🔄 Regenerate"**
- Vision API improves over time
- Re-analysis overwrites old data

### 5. Batch Upload Wisely
- Upload 5-10 videos at once (not 100)
- Generate visuals one-by-one as needed
- Transcription happens automatically

---

## 🔧 Troubleshooting

### "No results found"
**Solution:**
- Make sure video has visual analysis (click "Generate Visuals")
- Try more general search terms
- Check spelling of actor/series names

### "Video not playing"
**Solution:**
- Check video format (must be MP4, MOV, AVI, WEBM, MKV, GIF)
- Re-upload the video if needed
- Check browser console (F12) for errors

### "Generate Visuals" stuck on "Processing..."
**Solution:**
- Wait 60 seconds (Vision API can be slow)
- Check terminal logs for errors
- Restart server if needed:
  ```bash
  pkill -9 -f app_semantic.py
  python3 app_semantic.py
  ```

### "Search returns wrong videos"
**Solution:**
- Videos without visual analysis only match transcripts
- Click "Generate Visuals" on all videos for best results
- Use filters to narrow down results

---

## 📊 System Status

### Check if Server is Running
```bash
curl http://localhost:5002/videos
```
✅ Should return JSON with your video library

### View All Videos
```bash
curl http://localhost:5002/videos | python3 -m json.tool
```

### Test Search
```bash
curl -X POST http://localhost:5002/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Shahid Kapoor", "emotions": [], "genres": []}'
```

---

## 🎉 You're Ready!

### Next Steps
1. ✅ Upload your B-roll library (5-10 videos)
2. ✅ Click "Generate Visuals" on each video
3. ✅ Wait for analysis (30-60s per video)
4. ✅ Start searching!

### Pro Tips
- **Search actors** → Find all clips with specific actors
- **Search series** → Find all clips from a show
- **Search emotions** → Find clips by mood
- **Search visuals** → Find clips by objects/settings
- **Combine searches** → "Shahid Kapoor triumphant" = very specific results

---

## 🏆 What Makes This Tool Special

### Traditional Video Search
```
Search: "Shahid Kapoor"
→ Only finds videos with "Shahid Kapoor" in filename/metadata
→ Misses videos where he appears but isn't mentioned
```

### This Tool (AI-Powered)
```
Search: "Shahid Kapoor"
→ Recognizes his face in frames
→ Returns all clips where he appears
→ Even if filename doesn't mention him
→ 80%+ relevance scores
```

### Why It's Better
✅ **Face Recognition** - Identifies actors automatically  
✅ **Series Detection** - Knows which show it's from  
✅ **Emotion Analysis** - Understands mood/context  
✅ **Visual Search** - Searches what you *see*, not just what's *said*  
✅ **Semantic Understanding** - "triumphant" finds victory scenes, not just keyword matches  

---

**Tool URL:** http://localhost:5002/index_semantic.html  
**Status:** ✅ Running  
**Support:** Check `✅_IMPLEMENTATION_COMPLETE.md` for technical details

🚀 **Happy Searching!**
