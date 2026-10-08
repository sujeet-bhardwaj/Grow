@echo off
title Groww NIFTY 10-15 Pt Scalping Bot - Console Terminal
echo ========================================================
echo     GROWW NIFTY 10-15 POINT SCALPER - CONSOLE RUNNER
echo ========================================================
echo.

where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3.11 main.py
    pause
    exit /b
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    python main.py
    pause
    exit /b
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" main.py
    pause
    exit /b
)

echo [ERROR] Python not found in current environment.
pause
