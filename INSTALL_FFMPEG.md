# Install FFmpeg - Simple Guide

## What is FFmpeg?

FFmpeg is a tool that extracts audio from your videos so they can be transcribed.

## How to Install (Choose One Method)

### Method 1: Using Homebrew (Easiest)

1. Open **Terminal** app on your Mac

2. Copy and paste this command:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

3. Enter your Mac password when asked

4. After Homebrew installs, run:
```bash
brew install ffmpeg
```

5. Verify it worked:
```bash
ffmpeg -version
```

### Method 2: Download Binary (No Homebrew)

1. Go to: https://evermeet.cx/ffmpeg/
2. Download "ffmpeg-xxx.7z"
3. Extract the file
4. Move `ffmpeg` to `/usr/local/bin/`:
```bash
sudo cp ~/Downloads/ffmpeg /usr/local/bin/
sudo chmod +x /usr/local/bin/ffmpeg
```

### Method 3: Using MacPorts

If you have MacPorts:
```bash
sudo port install ffmpeg
```

## Verify Installation

Run this in Terminal:
```bash
ffmpeg -version
```

You should see version information.

## After Installing FFmpeg

Your B-Roll Mapper will be fully functional! Just:

1. Make sure the server is running:
```bash
cd "/Users/bhavya/Desktop/Cursor/b-roll mapper"
source venv_final/bin/activate
python3 app_simple.py
```

2. Open: http://localhost:5000

3. Upload videos and start searching!

## Troubleshooting

### "Command not found"
Try closing Terminal and opening a new window.

### "Permission denied"
Use `sudo` before the command and enter your Mac password.

### Still stuck?
Open Terminal and run:
```bash
which ffmpeg
```

If it shows a path, FFmpeg is installed!
