#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空间规划政策爬虫系统 - 安装版打包脚本
版本：v2.1.4
"""

import os
import sys
import shutil
import subprocess
from datetime import datetime

def check_dependencies():
    """检查打包依赖"""
    try:
        import PyInstaller
        print("✅ PyInstaller 已安装")
    except ImportError:
        print("❌ PyInstaller 未安装，正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("✅ PyInstaller 安装完成")
    
    try:
        import pandas
        print("✅ pandas 已安装")
    except ImportError:
        print("❌ pandas 未安装，正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pandas"], check=True)
        print("✅ pandas 安装完成")
    
    try:
        import openpyxl
        print("✅ openpyxl 已安装")
    except ImportError:
        print("❌ openpyxl 未安装，正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "openpyxl"], check=True)
        print("✅ openpyxl 安装完成")

def create_spec_file():
    """创建PyInstaller配置文件"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/space_planning/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('docs/icon.ico', 'docs'),
        ('README.md', '.'),
        ('CHANGELOG.md', '.'),
        ('LICENSE', '.'),
        ('version_info.txt', '.'),
    ],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui', 
        'PyQt5.QtWidgets',
        'pandas',
        'openpyxl',
        'requests',
        'beautifulsoup4',
        'python-docx',
        'fuzzywuzzy',
        'python-Levenshtein',
        'lxml',
        'sqlite3',
        'urllib3',
        'warnings',
        'threading',
        'datetime',
        're',
        'os',
        'sys',
        'logging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='空间规划政策爬虫系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='docs/icon.ico',
    version_file=None,
)
'''
    
    with open('space_planning_spider.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print("✅ 已创建 PyInstaller 配置文件")

def build_executable():
    """构建可执行文件"""
    print("🔨 开始构建可执行文件...")
    
    # 使用spec文件构建
    result = subprocess.run([
        sys.executable, "-m", "PyInstaller", 
        "--clean",  # 清理临时文件
        "space_planning_spider.spec"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ 可执行文件构建成功")
        return True
    else:
        print(f"❌ 构建失败: {result.stderr}")
        return False

def create_installer_package():
    """创建安装版包"""
    print("📦 创建安装版包...")
    
    # 创建安装版目录
    installer_dir = "空间规划政策爬虫系统_安装版"
    if os.path.exists(installer_dir):
        shutil.rmtree(installer_dir)
    os.makedirs(installer_dir)
    
    # 复制可执行文件
    exe_source = "dist/空间规划政策爬虫系统.exe"
    if os.path.exists(exe_source):
        shutil.copy2(exe_source, installer_dir)
        print("✅ 已复制可执行文件")
    else:
        print("❌ 可执行文件不存在")
        return False
    
    # 复制文档文件
    docs_to_copy = [
        "README.md",
        "CHANGELOG.md", 
        "LICENSE",
        "version_info.txt",
        "requirements.txt"
    ]
    
    for doc in docs_to_copy:
        if os.path.exists(doc):
            shutil.copy2(doc, installer_dir)
            print(f"✅ 已复制 {doc}")
    
    # 创建安装说明
    install_readme = f"""# 空间规划政策爬虫系统 v2.1.4 安装版

## 安装说明

### 系统要求
- Windows 7/8/10/11 (64位)
- 至少 4GB 内存
- 需要稳定的互联网连接

### 安装步骤
1. 解压本压缩包到任意目录
2. 双击运行 "空间规划政策爬虫系统.exe"
3. 首次运行会自动创建数据目录

### 数据目录
- 安装模式：%USERPROFILE%\\Documents\\空间规划政策爬虫系统\\
- 便携模式：程序目录下的 data 文件夹

### 功能特性
- 多源政策数据爬取（国家住建部、广东省、自然资源部）
- 智能反爬虫机制
- 合规性分析和政策对比
- 多格式数据导出（Word、Excel、文本、Markdown）
- 政策选择和批量导出

### 技术支持
- 开发者：ViVi141
- 联系邮箱：747384120@qq.com
- 项目地址：https://gitee.com/ViVi141/space-planning-spider

### 更新日志
请查看 CHANGELOG.md 文件了解详细更新内容。

### 许可证
本项目采用 MIT 许可证，详见 LICENSE 文件。

---
生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
版本：v2.1.4
"""
    
    with open(os.path.join(installer_dir, "安装说明.txt"), 'w', encoding='utf-8') as f:
        f.write(install_readme)
    print("✅ 已创建安装说明")
    
    # 创建启动脚本
    start_script = f"""@echo off
chcp 65001 >nul
echo 正在启动空间规划政策爬虫系统...
echo 版本：v2.1.4
echo 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
echo.
start "" "空间规划政策爬虫系统.exe"
"""
    
    with open(os.path.join(installer_dir, "启动程序.bat"), 'w', encoding='utf-8') as f:
        f.write(start_script)
    print("✅ 已创建启动脚本")
    
    # 创建卸载脚本
    uninstall_script = f"""@echo off
chcp 65001 >nul
echo 空间规划政策爬虫系统卸载工具
echo 版本：v2.1.4
echo.
echo 注意：此操作将删除程序数据目录中的所有数据！
echo.
set /p confirm="确认要卸载程序吗？(y/N): "
if /i "%confirm%"=="y" (
    echo 正在删除数据目录...
    rmdir /s /q "%USERPROFILE%\\Documents\\空间规划政策爬虫系统" 2>nul
    echo 正在删除程序文件...
    rmdir /s /q "%~dp0" 2>nul
    echo 卸载完成！
) else (
    echo 取消卸载。
)
pause
"""
    
    with open(os.path.join(installer_dir, "卸载程序.bat"), 'w', encoding='utf-8') as f:
        f.write(uninstall_script)
    print("✅ 已创建卸载脚本")
    
    return True

def create_zip_package():
    """创建ZIP安装包"""
    print("📦 创建ZIP安装包...")
    
    import zipfile
    
    installer_dir = "空间规划政策爬虫系统_安装版"
    zip_name = f"空间规划政策爬虫系统_v2.1.4_安装版_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(installer_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, installer_dir)
                zipf.write(file_path, arcname)
    
    print(f"✅ ZIP安装包创建成功: {zip_name}")
    return zip_name

def cleanup():
    """清理临时文件"""
    print("🧹 清理临时文件...")
    
    # 清理PyInstaller临时文件
    temp_dirs = ["build", "__pycache__"]
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"✅ 已清理 {temp_dir}")
    
    # 清理spec文件
    if os.path.exists("space_planning_spider.spec"):
        os.remove("space_planning_spider.spec")
        print("✅ 已清理 spec 文件")

def main():
    """主函数"""
    print("🚀 空间规划政策爬虫系统 - 安装版打包工具")
    print("版本：v2.1.4")
    print("=" * 50)
    
    try:
        # 检查可执行文件是否存在
        exe_path = "dist/空间规划政策爬虫系统.exe"
        if not os.path.exists(exe_path):
            print("❌ 可执行文件不存在，请先构建程序")
            return
        
        print("✅ 发现可执行文件，跳过构建步骤")
        
        # 创建安装版包
        print("\n📦 创建安装版包...")
        if not create_installer_package():
            print("❌ 创建安装版包失败，退出")
            return
        
        # 创建ZIP包
        print("\n📦 创建ZIP安装包...")
        zip_name = create_zip_package()
        
        print("\n" + "=" * 50)
        print("🎉 安装版打包完成！")
        print(f"📦 安装包：{zip_name}")
        print("📁 安装版目录：空间规划政策爬虫系统_安装版")
        print("💡 提示：可以将安装版目录直接分发给用户")
        
    except Exception as e:
        print(f"\n❌ 打包过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 