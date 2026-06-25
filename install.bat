@echo off
echo ========================================
echo  HR Hiring Platform - Setup & Install
echo ========================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+
    pause
    exit /b 1
)

REM Create virtual environment if not exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate
call .venv\Scripts\activate.bat

REM Install dependencies (torch CPU wheel fetched from PyTorch index — first run ~280MB)
echo Installing dependencies...
pip install -r requirements.txt -q

REM Check .env
if not exist ".env" (
    echo WARNING: .env file not found. Copying from .env.example...
    copy .env.example .env
    echo.
    echo Please edit .env and add your GROQ_API_KEY (free at https://console.groq.com)
    echo Then run start.bat to launch the platform.
    pause
    exit /b 1
)

REM Create required directories
if not exist "uploads\resumes" mkdir uploads\resumes
if not exist "chroma_data" mkdir chroma_data

REM Seed database
echo Seeding database...
python scripts/seed_db.py

echo.
echo ========================================
echo  Installation complete!
echo  Run start.bat to launch the platform.
echo ========================================
pause
