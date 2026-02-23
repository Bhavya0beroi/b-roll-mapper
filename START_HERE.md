# 🎥 B-Roll Mapper - START HERE

## ⚠️ IMPORTANT: Setup Required

Your system needs two things before the app can run:

## 1️⃣ Install FFmpeg (Required)

FFmpeg handles video/audio processing. Install it:

```bash
brew install ffmpeg
```

**Don't have Homebrew?** Install it first:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

## 2️⃣ Fix Python/NumPy Issue

Your system has a Python environment issue causing crashes. **Two solutions:**

### Solution A: Use System Python (Recommended)

Try using macOS system Python instead:

```bash
# Navigate to project
cd "/Users/bhavya/Desktop/Cursor/b-roll mapper"

# Remove old virtual environment
rm -rf venv_simple

# Create new one with system Python
/usr/bin/python3 -m venv venv_system
source venv_system/bin/activate

# Install dependencies
pip3 install --upgrade pip
pip3 install flask flask-cors openai python-dotenv
pip3 install numpy --no-binary numpy  # Build numpy from source

# Start the app
python3 app_cloud.py
```

### Solution B: Use Python 3.10+ from Homebrew

Your Python 3.9 may have compatibility issues:

```bash
# Install Python 3.11
brew install python@3.11

# Create venv with new Python
/opt/homebrew/bin/python3.11 -m venv venv_new
source venv_new/bin/activate

# Install dependencies
pip install flask flask-cors openai numpy python-dotenv

# Start app
python app_cloud.py
```

## 🚀 Quick Start (After Setup)

1. **Install FFmpeg** (see above)
2. **Fix Python/NumPy** (see above)
3. **Run the app:**

```bash
cd "/Users/bhavya/Desktop/Cursor/b-roll mapper"
source venv_system/bin/activate  # or venv_new
python app_cloud.py
```

4. **Open browser:** http://localhost:5000

## 📁 Files in This Project

| File | Purpose |
|------|---------|
| `app_cloud.py` | Main app (uses OpenAI API - works reliably) |
| `app.py` | Original app (requires local Whisper) |
| `app_local.py` | Local version (has compatibility issues on your system) |
| `index.html` | Web interface |
| `.env` | Your API key (already configured) |
| `START_HERE.md` | **This file** |

## 💰 Cost Estimate

Using `app_cloud.py` with OpenAI API:

- **10 videos × 5 minutes each = ~$0.35 total**
- Whisper: $0.006/min = $0.30
- Embeddings: $0.00002/1K tokens ≈ $0.05

Very affordable!

## ❓ Why These Issues?

Your Mac (Apple Silicon) is having compatibility problems with:
1. **NumPy binary**: ARM64 architecture mismatch
2. **PyTorch**: Required by local Whisper, but crashing

**Solution**: Use the cloud version (`app_cloud.py`) which avoids these issues!

## 🆘 Still Not Working?

Try running in your actual terminal (not through Cursor) to see full error messages:

```bash
cd "/Users/bhavya/Desktop/Cursor/b-roll mapper"

# Check FFmpeg
ffmpeg -version

# Check Python
python3 --version

# Try importing numpy
python3 -c "import numpy; print('NumPy works!')"

# If numpy fails, reinstall:
pip3 install --force-reinstall numpy
```

## ✅ Recommended Path Forward

1. Open **Terminal.app** (not Cursor terminal)
2. Run:
```bash
# Install FFmpeg
brew install ffmpeg

# Go to project
cd "/Users/bhavya/Desktop/Cursor/b-roll mapper"

# Install Python 3.11
brew install python@3.11

# Create fresh environment
/opt/homebrew/bin/python3.11 -m venv venv_working
source venv_working/bin/activate

# Install packages
pip install flask flask-cors openai numpy python-dotenv

# Test it works
python -c "import flask, openai, numpy; print('✅ All working!')"

# Start the app
python app_cloud.py
```

3. Open http://localhost:5000
4. Upload videos and search!

The cloud version is actually **faster** than local Whisper, and costs pennies per video. It's the best solution for your setup! 🎉
