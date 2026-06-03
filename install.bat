@echo off
setlocal
cd /d "%~dp0"
title Chaoxing Auto Setup

echo ========================================================
echo   Chaoxing Auto - Core Setup
echo ========================================================
echo.

echo [1/3] Checking Python...
python --version >/dev/null 2>/dev/null
if errorlevel 1 (
    echo   [ERROR] Python not found.
    echo   Please install Python 3.10+ and check Add Python to PATH
    pause
    exit /b 1
)
for /f "delims=" %%i in ('python --version 2^>^&1') do echo   [OK] %%i

echo.
echo [2/3] Installing Python packages...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo   [ERROR] Failed to install Python packages.
    pause
    exit /b 1
)
echo   [OK] Requirements installed

echo.
echo [3/3] Installing Chromium browser...
python -m playwright install chromium
if errorlevel 1 (
    echo   [ERROR] Failed to install Chromium.
    pause
    exit /b 1
)
echo   [OK] Chromium installed

echo.
echo ========================================================
echo   [DONE] Core setup complete!
echo.
echo   If you want AI answering, run: install_ai.bat
echo   Then start with: start.bat
echo ========================================================
echo.
echo ok > deps_ok.txt
pause
