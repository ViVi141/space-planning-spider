@echo off
chcp 65001 >nul
title 空间规划政策爬虫系统 - 完整Windows安装程序打包
echo ============================================================
echo 空间规划政策爬虫系统 - 完整Windows安装程序打包
echo 版本：v2.1.0
echo 更新时间：2025.7.8
echo ============================================================
echo.

echo 正在检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未找到Python环境
    echo 请先安装Python 3.7或更高版本
    pause
    exit /b 1
)

echo ✅ Python环境检查通过
echo.

echo 正在检查虚拟环境...
if not exist "venv" (
    echo ⚠️ 未找到虚拟环境，正在创建...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ 创建虚拟环境失败
        pause
        exit /b 1
    )
)

echo ✅ 虚拟环境检查通过
echo.

echo 正在激活虚拟环境...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ 激活虚拟环境失败
    pause
    exit /b 1
)

echo ✅ 虚拟环境激活成功
echo.

echo 正在安装依赖包...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ 安装依赖包失败
    pause
    exit /b 1
)

echo ✅ 依赖包安装完成
echo.

echo 正在安装PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo ❌ 安装PyInstaller失败
    pause
    exit /b 1
)

echo ✅ PyInstaller安装完成
echo.

echo 正在检查Inno Setup...
iscc /? >nul 2>&1
if errorlevel 1 (
    echo ⚠️ Inno Setup未安装或不在PATH中
    echo 将只生成便携版，不生成标准安装程序
    echo 如需标准安装程序，请安装Inno Setup: https://jrsoftware.org/isinfo.php
    echo.
    echo 是否继续？(Y/N)
    set /p choice=
    if /i not "%choice%"=="Y" (
        echo 用户取消操作
        pause
        exit /b 0
    )
) else (
    echo ✅ Inno Setup已安装
)

echo.
echo 开始执行完整打包程序...
python build_complete_installer.py
if errorlevel 1 (
    echo ❌ 打包程序执行失败
    pause
    exit /b 1
)

echo.
echo ============================================================
echo 打包完成！
echo ============================================================
echo.
echo 打包文件位置：
echo - 标准安装程序：installer\空间规划政策爬虫系统_v2.1.0_安装程序.exe
echo - 便携版：dist\空间规划政策爬虫系统_便携版\
echo - 可执行文件：dist\空间规划政策爬虫系统.exe
echo.
echo 文件说明：
echo - 标准安装程序：可在"程序和功能"中看到，包含完整安装向导
echo - 便携版：适合U盘携带，包含启动脚本和卸载程序
echo - 可执行文件：单个exe文件，包含所有依赖
echo.
echo 按任意键退出...
pause >nul 