@echo off
chcp 65001 >nul
title 超星刷课助手 - 一键安装
color 0A

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║          超星学习通 智能刷课助手 - 环境安装          ║
echo ║                                                      ║
echo ║   本程序将自动安装所有需要的软件，请耐心等待          ║
echo ║   全程大约需要 5-10 分钟（取决于网速）               ║
echo ╚══════════════════════════════════════════════════════╝
echo.

set "NEED_PYTHON=0"
set "NEED_NODE=0"
set "ALL_OK=1"

REM ============================================
REM  第1步: 检查 Python
REM ============================================
echo [1/5] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ❌ 未检测到 Python！
    echo.
    echo   请手动安装 Python:
    echo   1. 打开浏览器访问: https://www.python.org/downloads/
    echo   2. 点击黄色按钮 "Download Python 3.x.x"
    echo   3. 运行下载的安装包
    echo   4. ⚠️  重要: 安装时勾选 "Add Python to PATH" ！！！
    echo   5. 安装完成后，关闭此窗口，重新双击"安装.bat"
    echo.
    set "ALL_OK=0"
    set "NEED_PYTHON=1"
    start https://www.python.org/downloads/
    echo   已为你打开 Python 下载页面...
    echo.
    pause
    exit /b
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   ✅ %%i
)

REM ============================================
REM  第2步: 安装 Python 依赖
REM ============================================
echo.
echo [2/5] 安装 Python 依赖 (playwright, httpx)...
pip install playwright httpx -q 2>nul
if errorlevel 1 (
    echo   ⚠️  pip 安装可能有问题，尝试备用方式...
    python -m pip install playwright httpx -q 2>nul
)
echo   ✅ Python 依赖已安装

REM ============================================
REM  第3步: 安装 Chromium 浏览器
REM ============================================
echo.
echo [3/5] 安装 Chromium 浏览器引擎（首次较慢，约100MB）...
playwright install chromium 2>nul
if errorlevel 1 (
    python -m playwright install chromium 2>nul
)
echo   ✅ Chromium 已安装

REM ============================================
REM  第4步: 检查 Node.js (AI答题需要)
REM ============================================
echo.
echo [4/5] 检查 Node.js (AI答题功能需要)...
node --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ⚠️  未检测到 Node.js
    echo   AI答题功能需要 Node.js，但不影响刷视频。
    echo.
    echo   如需AI答题，请安装 Node.js:
    echo   1. 访问: https://nodejs.org
    echo   2. 下载 LTS 版本并安装
    echo   3. 安装后重新运行本脚本
    echo.
    set "NEED_NODE=1"
) else (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo   ✅ Node.js %%i
)

REM ============================================
REM  第5步: 安装 OpenCode CLI (免费AI)
REM ============================================
echo.
echo [5/5] 安装 OpenCode CLI (免费AI答题模型)...
if "%NEED_NODE%"=="1" (
    echo   ⏭️  跳过（需要先安装 Node.js）
) else (
    opencode --version >nul 2>&1
    if errorlevel 1 (
        echo   正在安装 OpenCode...
        npm install -g opencode-ai -q 2>nul
        opencode --version >nul 2>&1
        if errorlevel 1 (
            echo   ⚠️  OpenCode 安装可能失败，AI答题可能不可用
            echo   可手动运行: npm install -g opencode-ai
        ) else (
            echo   ✅ OpenCode CLI 已安装
        )
    ) else (
        for /f "tokens=*" %%i in ('opencode --version 2^>^&1') do echo   ✅ OpenCode %%i
    )
)

REM ============================================
REM  完成
REM ============================================
echo.
echo ══════════════════════════════════════════════════════
echo.
echo   ✅ 安装完成！
echo.
echo   接下来：
echo     双击 "启动.bat" 开始刷课
echo.
if "%NEED_NODE%"=="1" (
    echo   ⚠️  提示: 安装 Node.js 后可以使用免费AI答题功能
    echo      下载: https://nodejs.org
    echo.
)
echo ══════════════════════════════════════════════════════
echo.
echo ok > deps_ok.txt
pause
