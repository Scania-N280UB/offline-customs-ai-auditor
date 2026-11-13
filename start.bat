@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 关务控制塔 v2.6.2 (WinPython版)

echo 正在加载 WinPython 环境...
call "E:\Winpython\WPy64-31470\scripts\env.bat"

echo 正在启动关务控制塔...
python "%~dp0app.py"

echo.
echo 程序已退出（错误码：%ERRORLEVEL%）。
pause