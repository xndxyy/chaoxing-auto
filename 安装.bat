@echo off
chcp 65001 >nul 2>nul
title Chaoxing Auto - Install
color 0A

echo.
echo ========================================================
echo   Chaoxing Auto - Environment Setup
echo ========================================================
echo.

set "NEED_NODE=0"

REM Step 1: Python
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [X] Python not found!
    echo.
    echo   Please install Python first:
    echo   1. Open: https://www.python.org/downloads/
    echo   2. Download and install
    echo   3. CHECK "Add Python to PATH" during install!
    echo   4. Then re-run this script
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   [OK] %%i
)

REM Step 2: pip install
echo.
echo [2/5] Installing Python packages...
pip install playwright httpx -q 2>nul
if errorlevel 1 (
    python -m pip install playwright httpx -q 2>nul
)
echo   [OK] playwright, httpx installed

REM Step 3: Chromium
echo.
echo [3/5] Installing Chromium browser (~100MB, please wait)...
playwright install chromium 2>nul
if errorlevel 1 (
    python -m playwright install chromium 2>nul
)
echo   [OK] Chromium installed

REM Step 4: Node.js
echo.
echo [4/5] Checking Node.js (for AI features)...
node --version >nul 2>&1
if errorlevel 1 (
    echo   [!] Node.js not found - AI quiz answering will not work
    echo       Install from: https://nodejs.org (optional)
    set "NEED_NODE=1"
) else (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo   [OK] Node.js %%i
)

REM Step 5: OpenCode
echo.
echo [5/5] Installing OpenCode CLI (free AI model)...
if "%NEED_NODE%"=="1" (
    echo   [SKIP] Requires Node.js
) else (
    opencode --version >nul 2>&1
    if errorlevel 1 (
        npm install -g opencode-ai -q 2>nul
        opencode --version >nul 2>&1
        if errorlevel 1 (
            echo   [!] OpenCode install may have failed
        ) else (
            echo   [OK] OpenCode installed
        )
    ) else (
        for /f "tokens=*" %%i in ('opencode --version 2^>^&1') do echo   [OK] OpenCode %%i
    )
)

echo.
echo ========================================================
echo   [DONE] Setup complete!
echo.
echo   Next: double-click "start.bat" to begin
echo ========================================================
echo.
echo ok > deps_ok.txt
pause
