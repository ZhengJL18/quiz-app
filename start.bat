@echo off
title Quiz App

echo ============================================
echo   Quiz App
echo ============================================
echo.

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
taskkill /F /IM ngrok.exe >nul 2>&1
timeout /t 1 /nobreak >nul

start "Quiz" /MIN cmd /c "cd /d %~dp0backend && uvicorn app.main:app --host 0.0.0.0 --port 8001"
timeout /t 2 /nobreak >nul

start "ngrok" /MIN cmd /c "%LOCALAPPDATA%\ngrok\ngrok.exe http 8001 --url https://glandular-cadet-anthem.ngrok-free.dev"
timeout /t 3 /nobreak >nul

echo ============================================
echo   Local:  http://localhost:8001
echo   Phone:  https://glandular-cadet-anthem.ngrok-free.dev
echo          (first visit: click "Visit Site")
echo ============================================
echo.
pause
