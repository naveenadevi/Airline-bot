@echo off
REM Windows Restart Script for Airline Bot
REM Run this in your project folder with venv

echo.
echo ========================================
echo   RESTARTING AIRLINE BOT SERVER
echo ========================================
echo.

REM Step 1: Stop old server
echo [1/5] Stopping old server...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul
echo       Done!
echo.

REM Step 2: Check files exist
echo [2/5] Checking for files...
if not exist "nlu.py" (
    echo       ERROR: nlu.py not found!
    echo       Please copy nlu.py to this folder first.
    pause
    exit /b 1
)
if not exist "workflow.py" (
    echo       ERROR: workflow.py not found!
    echo       Please copy workflow.py to this folder first.
    pause
    exit /b 1
)
echo       Files found!
echo.

REM Step 3: Check virtual environment
echo [3/5] Checking virtual environment...
if not exist "venv\Scripts\activate.bat" (
    echo       ERROR: Virtual environment not found!
    echo       Expected: venv\Scripts\activate.bat
    pause
    exit /b 1
)
echo       Virtual environment found!
echo.

REM Step 4: Activate venv
echo [4/5] Activating virtual environment...
call venv\Scripts\activate
echo       Activated!
echo.

REM Step 5: Start server
echo [5/5] Starting server...
echo       Running: python main.py
echo.
echo ========================================
echo   SERVER STARTING...
echo   Press Ctrl+C to stop
echo ========================================
echo.

python main.py

echo.
echo ========================================
echo   SERVER STOPPED
echo ========================================
echo.
pause