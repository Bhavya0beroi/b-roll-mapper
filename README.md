# 🎥 B-Roll Mapper - Semantic Video Search Tool

Upload videos, search by meaning, find perfect clips instantly.

> **⚠️ START HERE:** Read [START_HERE.md](START_HERE.md) for setup instructions!

## What This Does

A local AI-powered tool that lets you upload videos, automatically transcribe them, and search for specific moments using natural language queries.

Upload 10-20 videos → AI transcribes → Search "sunset over water" → Get exact 15s clips

## ✨ Features

- 🎥 **Video Upload**: Drag and drop or select multiple videos
- 🎙️ **Auto Transcription**: Uses OpenAI Whisper API
- 🧠 **Semantic Search**: Find clips by meaning, not just keywords
- ⚡ **15-Second Clips**: Automatically segments into searchable chunks
- 🌙 **Dark Mode UI**: Beautiful, modern Tailwind CSS interface
- 💾 **Local Storage**: SQLite database on your machine

## 🚀 Quick Start

### Prerequisites

1. **Install FFmpeg:**
```bash
brew install ffmpeg
```

2. **Install Python 3.10+:**
```bash
brew install python@3.11
```

### Run the App

```bash
# Navigate to project
cd "/Users/bhavya/Desktop/Cursor/b-roll mapper"

# Create virtual environment  
python3.11 -m venv venv_working
source venv_working/bin/activate

# Install dependencies
pip install flask flask-cors openai numpy python-dotenv

# Start the app
python app_cloud.py
```

### Open in Browser

```
http://localhost:5000
```

## 📂 Available Versions

| File | Description | Pros | Cons |
|------|-------------|------|------|
| **app_cloud.py** | Uses OpenAI API for everything | ✅ Fast, reliable, works on your system | Small API cost (~$0.35 for 10 videos) |
| app_local.py | Uses local Whisper model | Free | ❌ Compatibility issues on your Mac |
| app.py | Hybrid approach | Balanced | ❌ Still has PyTorch issues |

**Recommended:** Use `app_cloud.py` - It's faster and actually works!

## 💰 Cost Estimate

Using `app_cloud.py` with OpenAI API:

**10 videos × 5 minutes each:**
- Whisper transcription: $0.30
- Text embeddings: $0.05
- **Total: ~$0.35**

Very affordable for the reliability and speed!

## 🎯 How to Use

1. **Upload Videos**
   - Click upload zone or drag & drop
   - Supported: MP4, MOV, AVI, MKV, WEBM

2. **Wait for Processing**
   - AI extracts audio
   - Transcribes with timestamps  
   - Creates semantic embeddings

3. **Search**
   - Type natural language queries:
     - "sunset over water"
     - "person talking to camera"
     - "city traffic at night"
     - "close-up of hands typing"

4. **Play Clips**
   - Click any result
   - Video plays at exact timestamp
   - See 15-second window

## 🛠️ Technical Details

- **Backend**: Flask (Python)
- **Transcription**: OpenAI Whisper API (whisper-1)
- **Embeddings**: OpenAI text-embedding-3-small
- **Database**: SQLite
- **Search**: Cosine similarity
- **Frontend**: HTML + Tailwind CSS + JavaScript

## 📁 Project Structure

```
b-roll mapper/
├── app_cloud.py          # Main app (recommended)
├── app.py                # Original version
├── app_local.py          # Local version (has issues)
├── index.html            # Web interface
├── .env                  # Your API key (configured)
├── START_HERE.md         # Setup guide
├── SETUP_GUIDE.md        # Detailed instructions
├── RUN_ME.sh             # One-click startup
├── uploads/              # Videos (auto-created)
└── broll.db             # Database (auto-created)
```

## 🔧 Troubleshooting

### FFmpeg not found
```bash
brew install ffmpeg
```

### NumPy crashes / Segmentation fault
Your system has Python/NumPy compatibility issues. See [START_HERE.md](START_HERE.md) for solutions.

### Port 5000 already in use
```bash
# Find process
lsof -i :5000

# Kill it
kill -9 <PID>
```

### API errors
- Check `.env` has your OpenAI key
- Verify account has credits at https://platform.openai.com

## 🎓 Why Cloud Version?

Your Mac (Apple Silicon) has compatibility issues with:
- PyTorch (required for local Whisper)
- Some NumPy binaries

The cloud version (`app_cloud.py`):
- ✅ Avoids these issues completely
- ✅ Actually faster than local processing
- ✅ Costs pennies per video
- ✅ More reliable

## 📖 Additional Resources

- [START_HERE.md](START_HERE.md) - First-time setup guide
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Detailed instructions
- [LOCAL_VERSION.md](LOCAL_VERSION.md) - Local vs Cloud comparison

## 📝 License

MIT License - Feel free to modify and use for your projects!

---

**Need help?** Check [START_HERE.md](START_HERE.md) for troubleshooting steps.
