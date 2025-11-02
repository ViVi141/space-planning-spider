@echo off
chcp 65001 >nul
echo 正在启动空间规划政策合规性分析系统...
echo.

REM 设置脚本目录为当前目录
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM 检查虚拟环境是否存在，优先使用虚拟环境中的Python
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    echo 检测到虚拟环境，使用虚拟环境中的Python...
    set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
) else (
    echo 警告: 未找到虚拟环境 .venv，使用系统Python
    set "PYTHON_EXE=python"
)

cd /d "%SCRIPT_DIR%src"
"%PYTHON_EXE%" -m space_planning.main

echo.
echo 程序已退出，按任意键关闭窗口...
pause >nul 