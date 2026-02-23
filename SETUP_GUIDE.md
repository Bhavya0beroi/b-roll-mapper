# B-Roll Mapper - Complete Setup Guide

## System Requirements

Your system is experiencing compatibility issues with PyTorch-based libraries. I've created a **Cloud Version** that uses only OpenAI's APIs, which is more reliable.

## Prerequisites

### 1. Install FFmpeg

FFmpeg is required for video/audio processing:

```bash
brew install ffmpeg
```

Verify installation:
```bash
ffmpeg -version
```

### 2. Verify Python

You need Python 3.8 or higher:
```bash
python3 --version
```

## Quick Start

### Option 1: One-Click Run (Recommended)

```bash
chmod +x RUN_ME.sh
./RUN_ME.sh
```

### Option 2: Manual Setup

1. **Create virtual environment:**
```bash
python3 -m venv venv_simple
source venv_simple/bin/activate
```

2. **Install dependencies:**
```bash
pip install --upgrade pip
pip install flask flask-cors openai "numpy<2" python-dotenv
```

3. **Start the server:**
```bash
python app_cloud.py
```

4. **Open in browser:**
```
http://localhost:5000
```

## Files Overview

- **app_cloud.py** - Main application (OpenAI API version)
- **index.html** - Web interface
- **.env** - Your API key (already configured)
- **RUN_ME.sh** - One-click startup script

## How It Works

### Upload & Processing

1. **Upload videos** (MP4, MOV, AVI, MKV, WEBM)
2. **Auto-extract audio** using FFmpeg
3. **Transcribe** using OpenAI Whisper API
4. **Create embeddings** using OpenAI text-embedding-3-small
5. **Store** in local SQLite database

### Searching

1. Type natural language queries
2. System creates embedding for your query
3. Finds most similar clips using cosine similarity
4. Returns top 20 results sorted by relevance

## API Costs

Using OpenAI APIs (very affordable for 10-20 videos):

- **Whisper transcription**: $0.006/minute
- **Embeddings**: $0.00002/1K tokens

**Example cost for 10 videos (5 minutes each):**
- Transcription: $0.30
- Embeddings: ~$0.05
- **Total: ~$0.35**

## Troubleshooting

### "FFmpeg not found"
```bash
brew install ffmpeg
```

### "Module not found" errors
Make sure you're in the virtual environment:
```bash
source venv_simple/bin/activate
```

### "Permission denied" on RUN_ME.sh
```bash
chmod +x RUN_ME.sh
```

### Server won't start
1. Check if port 5000 is available:
```bash
lsof -i :5000
```

2. Kill any process using port 5000:
```bash
kill -9 <PID>
```

### API errors
- Verify your API key in `.env`
- Check your OpenAI account has credits
- Test at: https://platform.openai.com/playground

## Alternative: Local Version (If You Want to Try)

The local version uses open-source Whisper, but your system has compatibility issues with PyTorch. If you want to troubleshoot this:

1. Try updating your macOS
2. Try a different Python version (3.10 or 3.11)
3. Check Apple Silicon compatibility

But the **Cloud Version works great** and is actually faster!

## Next Steps

1. Run `./RUN_ME.sh`
2. Open `http://localhost:5000`
3. Upload your videos
4. Start searching!

## Support

If you encounter issues:
1. Check FFmpeg is installed: `ffmpeg -version`
2. Check Python version: `python3 --version`
3. Verify API key in `.env`
4. Look at terminal output for specific errors

Enjoy your B-Roll Mapper! 🎥✨
