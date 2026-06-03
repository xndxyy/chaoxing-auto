@echo off
chcp 65001 >nul 2>nul
title Chaoxing Auto

REM Check deps
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [ERROR] Python not found! Run install.bat first.
    echo.
    pause
    exit /b
)

python -c "import playwright; import httpx" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [ERROR] Dependencies missing! Run install.bat first.
    echo.
    pause
    exit /b
)

cd /d "%~dp0"
python menu.py

if errorlevel 1 (
    echo.
    echo   [ERROR] menu.py failed. Check the error above.
    echo.
)
pause
