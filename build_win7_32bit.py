import os
import sys
import shutil
from pathlib import Path

def create_win7_32bit_portable():
    """创建Windows 7 32位系统便携版"""
    
    # 确保使用32位Python
    if sys.maxsize > 2**32:
        print("错误：请使用32位Python运行此脚本")
        sys.exit(1)
        
    # 创建requirements_win7.txt
    win7_requirements = """
PyQt5==5.15.2
requests==2.27.1
beautifulsoup4==4.9.3
python-docx==0.8.11
fuzzywuzzy==0.18.0
python-Levenshtein==0.12.2
lxml==4.9.1
pandas==1.3.5
openpyxl==3.0.9
    """.strip()
    
    with open("requirements_win7.txt", "w", encoding="utf-8") as f:
        f.write(win7_requirements)
    
    # 创建spec文件
    spec_content = """
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/space_planning/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 添加资源文件
a.datas += [('docs/icon.ico', 'docs/icon.ico', 'DATA')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='空间规划政策爬虫',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86',
    codesign_identity=None,
    entitlements_file=None,
    icon='docs/icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='空间规划政策爬虫_Win7_32位便携版',
)
    """.strip()
    
    with open("win7_32bit.spec", "w", encoding="utf-8") as f:
        f.write(spec_content)
    
    # 创建打包批处理文件
    bat_content = """
@echo off
chcp 65001
echo 正在创建Windows 7 32位便携版...

REM 安装依赖
pip install -r requirements_win7.txt

REM 使用PyInstaller打包
pyinstaller win7_32bit.spec --noconfirm

REM 创建data目录
mkdir "dist\空间规划政策爬虫_Win7_32位便携版\data"

REM 复制版本信息
copy "version_info.txt" "dist\空间规划政策爬虫_Win7_32位便携版\"

REM 创建ZIP包
powershell Compress-Archive -Path "dist\空间规划政策爬虫_Win7_32位便携版" -DestinationPath "dist\空间规划政策爬虫_Win7_32位便携版.zip" -Force

echo 打包完成！
pause
    """.strip()
    
    with open("build_win7_32bit.bat", "w", encoding="utf-8") as f:
        f.write(bat_content)

if __name__ == "__main__":
    create_win7_32bit_portable() 