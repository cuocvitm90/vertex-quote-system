@echo off
REM ==============================================================================
REM Vertex Construction & PCCC - Production Startup Script (Windows Server)
REM ==============================================================================

echo ==============================================================================
echo  Starting Vertex Construction & PCCC Quote Automation (Windows Server)
echo ==============================================================================

set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

if not exist ".env" (
    echo Warning: .env file not found. Copying .env.example...
    copy .env.example .env
)

python run.py --port 8000
pause
