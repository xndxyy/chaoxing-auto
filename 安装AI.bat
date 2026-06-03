@echo off
setlocal
cd /d "%~dp0"
title Chaoxing Auto - AI Setup

echo ========================================================
echo   Chaoxing Auto - AI Setup (Optional)
echo ========================================================
echo.

echo [1/3] Checking Node.js...
where node >nul 2>nul
if errorlevel 1 (
    echo   [ERROR] Node.js not found.
    echo   Install from: https://nodejs.org
    pause
    exit /b 1
)
for /f "delims=" %%i in ('node --version 2^>nul') do echo   [OK] Node.js %%i

echo.
echo [2/3] Setting npm mirror (China)...
call npm config set registry https://registry.npmmirror.com >nul 2>nul
echo   [OK] Mirror set

echo.
echo [3/3] Installing OpenCode CLI...
where opencode >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%i in ('call opencode --version 2^>nul') do echo   [OK] Already installed: %%i
    goto done
)
call npm install -g opencode-ai
if errorlevel 1 (
    echo   [WARN] Install failed. Core features still work.
    echo   Try later: npm install -g opencode-ai
    pause
    exit /b 0
)
echo   [OK] OpenCode installed

:done
echo.
echo ========================================================
echo   [DONE] AI setup complete!
echo   Start with:  启动.bat
echo ========================================================
echo.
pause
