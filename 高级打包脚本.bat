@echo off
chcp 65001 >nul
echo ========================================
echo 空间规划政策爬虫系统 - 高级打包脚本
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
echo 开始高级打包...
echo.

:: 创建临时spec文件
echo # -*- mode: python ; coding: utf-8 -*- > temp_build.spec
echo. >> temp_build.spec
echo block_cipher = None >> temp_build.spec
echo. >> temp_build.spec
echo a = Analysis( >> temp_build.spec
echo     ['src/space_planning/main.py'], >> temp_build.spec
echo     pathex=[], >> temp_build.spec
echo     binaries=[], >> temp_build.spec
echo     datas=[ >> temp_build.spec
echo         ('docs/icon.ico', 'docs'), >> temp_build.spec
echo     ], >> temp_build.spec
echo     hiddenimports=[ >> temp_build.spec
echo         'PyQt5.QtCore', >> temp_build.spec
echo         'PyQt5.QtGui', >> temp_build.spec
echo         'PyQt5.QtWidgets', >> temp_build.spec
echo         'PyQt5.sip', >> temp_build.spec
echo         'requests', >> temp_build.spec
echo         'beautifulsoup4', >> temp_build.spec
echo         'docx', >> temp_build.spec
echo         'fuzzywuzzy', >> temp_build.spec
echo         'Levenshtein', >> temp_build.spec
echo         'lxml', >> temp_build.spec
echo         'lxml.etree', >> temp_build.spec
echo         'lxml.html', >> temp_build.spec
echo         'urllib3', >> temp_build.spec
echo         'certifi', >> temp_build.spec
echo         'ssl', >> temp_build.spec
echo         'sqlite3', >> temp_build.spec
echo     ], >> temp_build.spec
echo     hookspath=[], >> temp_build.spec
echo     hooksconfig={}, >> temp_build.spec
echo     runtime_hooks=[], >> temp_build.spec
echo     excludes=[], >> temp_build.spec
echo     win_no_prefer_redirects=False, >> temp_build.spec
echo     win_private_assemblies=False, >> temp_build.spec
echo     cipher=block_cipher, >> temp_build.spec
echo     noarchive=False, >> temp_build.spec
echo ) >> temp_build.spec
echo. >> temp_build.spec
echo pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher) >> temp_build.spec
echo. >> temp_build.spec
echo exe = EXE( >> temp_build.spec
echo     pyz, >> temp_build.spec
echo     a.scripts, >> temp_build.spec
echo     a.binaries, >> temp_build.spec
echo     a.zipfiles, >> temp_build.spec
echo     a.datas, >> temp_build.spec
echo     [], >> temp_build.spec
echo     name='空间规划政策爬虫系统', >> temp_build.spec
echo     debug=False, >> temp_build.spec
echo     bootloader_ignore_signals=False, >> temp_build.spec
echo     strip=False, >> temp_build.spec
echo     upx=True, >> temp_build.spec
echo     upx_exclude=[], >> temp_build.spec
echo     runtime_tmpdir=None, >> temp_build.spec
echo     console=False, >> temp_build.spec
echo     disable_windowed_traceback=False, >> temp_build.spec
echo     argv_emulation=False, >> temp_build.spec
echo     target_arch=None, >> temp_build.spec
echo     codesign_identity=None, >> temp_build.spec
echo     entitlements_file=None, >> temp_build.spec
echo     icon='docs/icon.ico', >> temp_build.spec
echo ) >> temp_build.spec

:: 使用spec文件打包
pyinstaller temp_build.spec --clean

if errorlevel 1 (
    echo.
    echo 高级打包失败！尝试简单打包...
    pyinstaller --onefile --windowed --icon=docs/icon.ico --name="空间规划政策爬虫系统" src/space_planning/main.py
)

if errorlevel 1 (
    echo.
    echo 打包失败！请检查错误信息。
    pause
    exit /b 1
)

:: 清理临时文件
del temp_build.spec

:: 退出虚拟环境
deactivate

echo.
echo ========================================
echo 高级打包完成！
echo ========================================
echo.
echo 可执行文件位置: dist\空间规划政策爬虫系统.exe
echo.
echo 版本信息: v1.1.1
echo 主要更新: 修复数据库路径问题，解决打包后无法爬取的问题
echo.
echo 包含的改进:
echo - 修复数据库路径问题
echo - 增强网络环境兼容性
echo - 添加诊断工具
echo - 改进错误处理
echo.
echo 您可以将整个dist文件夹复制到其他电脑上运行。
echo.

:: 询问是否打开输出目录
set /p choice="是否打开输出目录？(y/n): "
if /i "%choice%"=="y" (
    explorer dist
)

pause 