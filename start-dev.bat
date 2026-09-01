@echo off
echo.
echo ============================================
echo   CloudForge - Local Development Setup
echo ============================================
echo.

REM Check if PostgreSQL is running
echo [1/3] Checking PostgreSQL...
pg_isready -h localhost -p 5432 >nul 2>&1
if errorlevel 1 (
    echo WARNING: PostgreSQL doesn't seem to be running on port 5432.
    echo Please start PostgreSQL and create a database named 'cloudforge'.
    echo.
    echo Create DB:  psql -U postgres -c "CREATE DATABASE cloudforge;"
    echo.
    pause
)

echo [2/3] Starting Backend (FastAPI on port 8000)...
cd backend
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt -q

set DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cloudforge
set SECRET_KEY=cloudforge-dev-secret

start "CloudForge Backend" cmd /k "venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"
cd ..

echo [3/3] Starting Frontend (Vite on port 5173)...
cd frontend
start "CloudForge Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ============================================
echo  CloudForge is starting up!
echo.
echo  Frontend: http://localhost:5173
echo  Backend:  http://localhost:8000
echo  API Docs: http://localhost:8000/docs
echo ============================================
echo.
timeout /t 3 >nul
start http://localhost:5173
