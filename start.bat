@echo off
echo ========================================
echo  HR Hiring Platform - Local Startup
echo ========================================

REM Check that install.bat has been run first
if not exist ".venv" (
    echo ERROR: Virtual environment not found.
    echo Please run install.bat first.
    pause
    exit /b 1
)

if not exist ".env" (
    echo ERROR: .env file not found.
    echo Please run install.bat first and configure your GROQ_API_KEY.
    pause
    exit /b 1
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Start API server in background
echo Starting FastAPI backend on http://localhost:8000 ...
start "HR API" cmd /c "call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"

REM Wait a moment
timeout /t 3 /nobreak >nul

REM Start Streamlit UI
echo Starting Streamlit UI on http://localhost:8501 ...
echo.
echo ========================================
echo  CREDENTIALS:
echo  Admin: admin@hrplatform.com / Admin@123
echo  Panel: panel@hrplatform.com / Panel@123
echo ========================================
echo.
streamlit run ui/app.py --server.port 8501
