@echo off
echo Setting up DDNS auto-update (every 10 minutes)...

schtasks /create /tn "Quiz-DDNS" /tr "python %~dp0ddns_update.py" /sc minute /mo 10 /f

if errorlevel 1 (
    echo.
    echo If failed, run this script as Administrator (right-click -^> Run as Administrator)
) else (
    echo.
    echo Done! DNS will auto-update every 10 minutes.
    echo Verify: schtasks /query /tn "Quiz-DDNS"
)
pause
