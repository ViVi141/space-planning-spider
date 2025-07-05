@echo off
chcp 65001 >nul
echo ========================================
echo 空间规划政策爬虫系统 - 打包脚本 v1.1.1
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

echo 正在创建虚拟环境...
echo.

:: 检查虚拟环境是否存在
if exist venv (
    echo 虚拟环境已存在，正在激活...
    call venv\Scripts\activate.bat
) else (
    echo 创建新的虚拟环境...
    python -m venv venv
    call venv\Scripts\activate.bat
)

echo 正在检查并安装打包依赖...
echo.

:: 升级pip
python -m pip install --upgrade pip

:: 安装PyInstaller
pip install pyinstaller

:: 安装项目依赖
echo 正在安装项目依赖...
pip install -r requirements.txt

echo.
echo 开始打包应用程序...
echo.

:: 使用PyInstaller打包
pyinstaller --onefile --windowed --icon=docs/icon.ico --name="空间规划政策爬虫系统" src/space_planning/main.py

if errorlevel 1 (
    echo.
    echo 打包失败！请检查错误信息。
    pause
    exit /b 1
)

:: 退出虚拟环境
deactivate

echo.
echo ========================================
echo 打包完成！
echo ========================================
echo.
echo 可执行文件位置: dist\空间规划政策爬虫系统.exe
echo.
echo 版本信息: v1.1.1
echo 主要更新: 修复数据库路径问题，解决打包后无法爬取的问题
echo.
echo 您可以将整个dist文件夹复制到其他电脑上运行。
echo.

:: 询问是否打开输出目录
set /p choice="是否打开输出目录？(y/n): "
if /i "%choice%"=="y" (
    explorer dist
)

pause 