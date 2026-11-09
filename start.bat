@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Custom Control Tower Launcher

echo ====================================================
echo  🚀 离线关务单证风控引擎 v2.6 (Web UI Launcher)
echo ====================================================
echo.

:: 1. 优先检查当前目录或父目录下是否有绿色版 Python
set "PY_CMD="
if exist "%~dp0python.exe" set "PY_CMD=%~dp0python.exe"
if not defined PY_CMD if exist "%~dp0..\python\python.exe" set "PY_CMD=%~dp0..\python\python.exe"
if not defined PY_CMD if exist "%~dp0..\python.exe" set "PY_CMD=%~dp0..\python.exe"

:: 2. 如果没找到，再去系统环境变量里找 python 或 python3
if not defined PY_CMD (
    where python >nul 2>nul
    if !errorlevel! equ 0 set "PY_CMD=python"
)
if not defined PY_CMD (
    where python3 >nul 2>nul
    if !errorlevel! equ 0 set "PY_CMD=python3"
)

:: 3. 如果还是找不到，给用户一个友好的提示并退出
if not defined PY_CMD (
    echo [ERROR] Python environment was not found on this system!
    echo Please install Python 3.9+ and add it to your system PATH.
    echo Or place a portable Python folder next to this script.
    echo.
    pause
    exit /b
)

echo [INFO] Found Python environment: !PY_CMD!
echo [INFO] Checking core dependencies (streamlit / httpx / pandas)...

:: 4. 检查依赖是否完整 (屏蔽输出)
"!PY_CMD!" -c "import streamlit, httpx, pandas" >nul 2>nul
if !errorlevel! neq 0 (
    echo [WARNING] Missing required packages.
    echo [INFO] Attempting to install from Tsinghua Mirror...
    "!PY_CMD!" -m pip install streamlit httpx pandas -i https://pypi.tuna.tsinghua.edu.cn/simple
    
    :: 再检查一次，如果还是失败，提示用户手动安装
    "!PY_CMD!" -c "import streamlit, httpx, pandas" >nul 2>nul
    if !errorlevel! neq 0 (
        echo.
        echo [ERROR] Dependency installation failed.
        echo Please manually run: pip install streamlit httpx pandas
        pause
        exit /b
    )
)

echo [INFO] All dependencies are satisfied!
echo [INFO] Launching Web UI (Please wait for the browser to open)...
echo.

:: 5. 直接运行主程序，v2.6 内部会自动处理 Web 端的启动
"!PY_CMD!" auto_customs_control_tower_v2.6.py

if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Program exited unexpectedly. Please check the logs above.
    pause
)