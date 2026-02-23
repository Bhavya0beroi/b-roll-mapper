#!/bin/bash

echo "🎥 B-Roll Mapper - Local Version"
echo "================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if [ ! -f "venv/installed" ]; then
    echo "📥 Installing dependencies (this may take a few minutes)..."
    pip install -r requirements_local.txt
    touch venv/installed
    echo "✅ Dependencies installed!"
fi

echo ""
echo "🚀 Starting B-Roll Mapper..."
echo "   Open your browser to: http://localhost:5000"
echo ""
echo "   Press Ctrl+C to stop the server"
echo ""

# Run the app
python app_local.py
