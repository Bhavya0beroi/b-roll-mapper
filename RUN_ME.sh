#!/bin/bash

echo "🎥 B-Roll Mapper Setup & Startup"
echo "================================"
echo ""

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg is not installed!"
    echo "   Please install it with: brew install ffmpeg"
    echo ""
    exit 1
fi

echo "✅ FFmpeg found"

# Check if venv_simple exists
if [ ! -d "venv_simple" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv_simple
    source venv_simple/bin/activate
    pip install --upgrade pip
    pip install flask flask-cors openai "numpy<2" python-dotenv
else
    source venv_simple/bin/activate
fi

echo "✅ Environment ready"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "   Create a .env file with your OpenAI API key:"
    echo "   OPENAI_API_KEY=your_key_here"
    exit 1
fi

echo "✅ API key configured"
echo ""
echo "🚀 Starting server..."
echo "   URL: http://localhost:5000"
echo "   Press Ctrl+C to stop"
echo ""

python app_cloud.py
