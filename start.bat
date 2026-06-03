@echo off
chcp 65001 >nul
title 超星学习通 智能刷课助手

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║     超星学习通 智能刷课助手 v2.0                    ║
echo ╚══════════════════════════════════════════════════════╝
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    echo        下载: https://www.python.org/downloads/
    pause
    exit /b
)

REM 首次检查依赖
if not exist "deps_ok.txt" (
    echo [首次运行] 正在安装依赖，请稍候...
    pip install playwright httpx -q 2>nul
    playwright install chromium 2>nul
    echo ok > deps_ok.txt
    echo [完成] 依赖已安装
    echo.
)

REM 启动菜单
python menu.py

pause
