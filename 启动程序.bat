@echo off
chcp 65001 >nul
echo 正在启动空间规划政策合规性分析系统...
echo.

cd /d "%~dp0src"
python -m space_planning.main

echo.
echo 程序已退出，按任意键关闭窗口...
pause >nul 