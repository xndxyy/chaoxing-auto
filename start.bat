@echo off
cd /d "%~dp0"
title Chaoxing Auto

python --version >/dev/null 2>/dev/null
if errorlevel 1 (
    echo   [ERROR] Python not found. Run install.bat first.
    pause
    exit /b
)

python -c "import playwright; import httpx" >/dev/null 2>/dev/null
if errorlevel 1 (
    echo   [ERROR] Dependencies missing. Run install.bat first.
    pause
    exit /b
)

python menu.py
pause
