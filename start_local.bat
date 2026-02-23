@echo off
echo 🎥 B-Roll Mapper - Local Version
echo ================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
if not exist "venv\installed" (
    echo 📥 Installing dependencies (this may take a few minutes)...
    pip install -r requirements_local.txt
    type nul > venv\installed
    echo ✅ Dependencies installed!
)

echo.
echo 🚀 Starting B-Roll Mapper...
echo    Open your browser to: http://localhost:5000
echo.
echo    Press Ctrl+C to stop the server
echo.

REM Run the app
python app_local.py
