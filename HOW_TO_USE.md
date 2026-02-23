# 🎥 How to Use Your B-Roll Mapper

## Quick Start (Every Time You Want to Use It)

### 1. Start the Server

Open Terminal and run these commands:

```bash
# Navigate to the project folder
cd "/Users/bhavya/Desktop/Cursor/b-roll mapper"

# Activate the virtual environment
source venv_final/bin/activate

# Start the server
python3 app_simple.py
```

You'll see:
```
🎥 B-ROLL MAPPER - READY TO USE!
✅ Server running at: http://localhost:5000
```

### 2. Open Your Browser

Go to: **http://localhost:5000**

### 3. Upload Videos

- **Click** the upload zone OR **drag and drop** videos
- Supported formats: MP4, MOV, AVI, MKV, WEBM
- Upload 1-20 videos

**What happens during upload:**
1. Audio is extracted from video
2. OpenAI Whisper transcribes the audio
3. Embeddings are created for semantic search
4. Everything is saved to local database

**⏱️ Processing time:** ~30 seconds per 5-minute video

### 4. Search Your Videos

Type natural language queries in the search bar:

**Example searches:**
- "sunset over water"
- "person talking to camera"
- "city traffic at night"
- "close-up of hands typing"
- "aerial drone shot"
- "someone laughing"

### 5. View Results

- Results show as cards with:
  - Video filename
  - Transcript snippet
  - Similarity score (higher = better match)
  - Timestamp

- **Click any card** to play the video at that exact moment!

## Tips for Best Results

### Better Search Queries

✅ **Good queries:**
- "sunset reflection on water"
- "close-up of coffee being poured"
- "wide shot of mountain landscape"

❌ **Less effective:**
- "video" (too vague)
- "good" (no specific meaning)
- "clip 5" (use descriptions, not numbers)

### Upload Strategy

1. **Name your files descriptively** (helps you identify them)
2. **Upload in batches** (process 5 videos, test search, then add more)
3. **Quality matters** - Clear audio = better transcription

### Organizing Your Library

- Videos stay in the `uploads/` folder
- Database is in `broll.db`
- To start fresh: delete `broll.db` and `uploads/` folder

## Common Actions

### Stop the Server

In Terminal, press: `Ctrl + C`

### Restart the Server

```bash
cd "/Users/bhavya/Desktop/Cursor/b-roll mapper"
source venv_final/bin/activate
python3 app_simple.py
```

### Check What's Running

```bash
lsof -i :5000
```

### View All Uploaded Videos

The web interface shows all processed videos.

## Keyboard Shortcuts (In Browser)

- `Cmd + F` - Focus search bar
- `Escape` - Close video player modal
- `Space` - Play/pause video

## Cost Tracking

Each video costs approximately:
- **Whisper transcription:** $0.006/minute
- **Embeddings:** $0.00002/1K tokens

**Example:**
- 10 videos × 5 minutes each = **~$0.35 total**

Check usage at: https://platform.openai.com/usage

## Troubleshooting

### "FFmpeg not found" error
Install FFmpeg first: See `INSTALL_FFMPEG.md`

### Video won't play
- Check the video file isn't corrupted
- Try a different browser
- Check console for errors (F12)

### Search returns no results
- Make sure videos have been processed
- Try broader search terms
- Check if audio was clear in the video

### Server won't start
```bash
# Kill any existing server
lsof -i :5000
kill -9 <PID>

# Start fresh
python3 app_simple.py
```

### "API key not found" error
Check your `.env` file exists and contains:
```
OPENAI_API_KEY=your_key_here
```

## File Locations

```
b-roll mapper/
├── app_simple.py          # The app (this is what runs)
├── index.html             # Web interface
├── .env                   # Your API key
├── venv_final/            # Python environment
├── uploads/               # Your uploaded videos
└── broll.db              # Search database
```

## Advanced: Database Queries

To see what's in your database:

```bash
sqlite3 broll.db "SELECT filename, COUNT(*) as clips FROM clips GROUP BY filename;"
```

## Need Help?

1. Check the terminal output for error messages
2. Verify FFmpeg is installed: `ffmpeg -version`
3. Check API key is valid
4. Try with a different video file

---

**Enjoy your B-Roll Mapper!** 🎬✨
