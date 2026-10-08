@echo off
title Groww NIFTY 10-15 Pt Scalping Bot - Chrome Dashboard
echo ========================================================
echo     GROWW NIFTY 10-15 POINT SCALPER - CHROME DASHBOARD
echo ========================================================
echo.
echo Starting Scalping Web Server & Scanner...
echo Terminal Login URL: http://127.0.0.1:5000/login
echo Default Login: admin / groww123
echo.

where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3.11 app.py
    pause
    exit /b
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    python app.py
    pause
    exit /b
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" app.py
    pause
    exit /b
)

echo [ERROR] Python not found in current environment.
pause
