@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ----------------------------------------------------
echo  🚀 正在搜索 WinPython 解释器并启动关务风控引擎...
echo ----------------------------------------------------

:: 向上推一级，在 WinPython 根目录中自动搜索 python.exe
set "PY_EXEC="
for /f "delims=" %%I in ('dir /b /s "%~dp0..\python.exe" 2^>nul') do (
    set "PY_EXEC=%%I"
    goto :FOUND
)

:FOUND
:: 如果自动搜索没找到，则回退尝试全局 python 命令
if not defined PY_EXEC set "PY_EXEC=python"

echo 找到解释器: "%PY_EXEC%"
echo.

"%PY_EXEC%" auto_customs_control_tower.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ 运行出现错误，请检查上方窗口提示！
)
pause