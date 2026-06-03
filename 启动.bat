@echo off
chcp 65001 >nul
title 超星学习通 智能刷课助手

REM 检查是否已安装
if not exist "deps_ok.txt" (
    python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   ❌ 请先双击"安装.bat"安装环境！
        echo.
        pause
        exit /b
    )
    REM 快速检查依赖
    python -c "import playwright; import httpx" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   ❌ 依赖未安装，请先双击"安装.bat"！
        echo.
        pause
        exit /b
    )
)

python menu.py
pause
