#!/bin/bash

echo "============================================================"
echo "🚀 Starting B-Roll Semantic Search System"
echo "============================================================"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv_embeddings" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python3 -m venv venv_embeddings"
    exit 1
fi

# Activate venv
source venv_embeddings/bin/activate

# Check API key
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please create .env with your OPENAI_API_KEY"
    exit 1
fi

# Start server
echo "✅ Starting server on http://localhost:5002"
echo "✅ Open index_semantic.html in your browser"
echo ""
echo "Press Ctrl+C to stop the server"
echo "============================================================"
echo ""

python3 app_semantic.py
