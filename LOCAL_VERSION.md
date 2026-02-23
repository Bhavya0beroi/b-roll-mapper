# 🎯 Fully Local B-Roll Mapper

This version runs **100% locally** on your computer - no API keys, no internet needed after setup!

## Two Versions Available

### Option 1: API Version (app.py)
- ✅ Faster transcription
- ✅ Better accuracy
- ❌ Requires OpenAI API key (costs ~$0.006/minute)
- ❌ Needs internet connection

### Option 2: Local Version (app_local.py) ⭐ RECOMMENDED
- ✅ **100% free**
- ✅ **100% private** - data never leaves your computer
- ✅ **No internet needed** after initial setup
- ✅ No API costs
- ⚠️ Slower transcription (but still very usable)
- ⚠️ Requires more disk space (~500MB for models)

## Setup Local Version

### 1. Install Dependencies

```bash
pip install -r requirements_local.txt
```

**Note**: First time setup will download two models:
- Whisper "base" model (~150MB) - for transcription
- Sentence transformer (~100MB) - for semantic search

### 2. Install FFmpeg (if not already installed)

**macOS**:
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian)**:
```bash
sudo apt install ffmpeg
```

**Windows**:
Download from https://ffmpeg.org/download.html

### 3. Run the Local App

```bash
python app_local.py
```

That's it! No API keys needed. Open `http://localhost:5000`

## Whisper Model Options

In `app_local.py`, line 32, you can change the model size:

```python
whisper_model = whisper.load_model("base")  # Change this
```

Available models (speed vs accuracy trade-off):

| Model  | Size  | Speed      | Accuracy | Use Case |
|--------|-------|------------|----------|----------|
| tiny   | 39M   | Very Fast  | Good     | Quick testing |
| base   | 74M   | Fast       | Better   | **Recommended** |
| small  | 244M  | Moderate   | Great    | High quality |
| medium | 769M  | Slow       | Excellent| Best quality |
| large  | 1550M | Very Slow  | Best     | Professional |

## Performance Comparison

**10-minute video transcription:**
- API Version (app.py): ~30 seconds
- Local "base" model: ~2-3 minutes
- Local "small" model: ~5-7 minutes

**Search speed:** Both versions are equally fast (instant)

## Which Should You Use?

Choose **Local Version** if:
- 💰 You want it completely free
- 🔒 Privacy is important (sensitive content)
- 📴 Limited/no internet access
- 🎥 Processing 10-20 videos occasionally

Choose **API Version** if:
- ⚡ Need fastest possible transcription
- 💼 Processing hundreds of videos
- 💻 Limited local compute power
- 💵 Cost is not a concern ($0.006/min)

## Already Have API Key?

Your API key has been saved to `.env`. You can use either version:

```bash
# Local version (no API needed)
python app_local.py

# API version (uses your key)
python app.py
```

Both use the same `index.html` frontend!
