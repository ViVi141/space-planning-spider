#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整Windows安装程序打包脚本
版本：v2.1.0
更新时间：2025.7.8
包含标准安装程序和便携版
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def check_dependencies():
    """检查打包依赖"""
    print("检查打包依赖...")
    
    try:
        import PyInstaller
        print("✅ PyInstaller 已安装")
    except ImportError:
        print("❌ PyInstaller 未安装，正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("✅ PyInstaller 安装完成")

def clean_build_dirs():
    """清理构建目录"""
    print("清理构建目录...")
    
    dirs_to_clean = ['build', 'dist', '__pycache__', 'installer']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"✅ 清理目录: {dir_name}")

def build_executable():
    """构建可执行文件"""
    print("开始构建可执行文件...")
    
    # 检查图标文件
    icon_path = 'docs/icon.ico'
    if not os.path.exists(icon_path):
        print(f"⚠️ 图标文件不存在: {icon_path}")
        icon_path = None
    
    # 构建命令
    cmd = [
        'pyinstaller',
        '--onefile',  # 打包成单个文件
        '--windowed',  # 无控制台窗口
        '--clean',  # 清理临时文件
        '--noconfirm',  # 不确认覆盖
        '--name=空间规划政策爬虫系统',  # 可执行文件名称
    ]
    
    # 添加图标
    if icon_path:
        cmd.extend(['--icon', icon_path])
    
    # 添加数据文件
    cmd.extend([
        '--add-data', 'docs/icon.ico;docs',
        '--add-data', 'LICENSE;.',
        '--add-data', 'README.md;.',
        '--add-data', 'CHANGELOG.md;.',
        '--add-data', '版本管理说明.md;.',
    ])
    
    # 添加隐藏导入
    cmd.extend([
        '--hidden-import', 'PyQt5.QtCore',
        '--hidden-import', 'PyQt5.QtGui',
        '--hidden-import', 'PyQt5.QtWidgets',
        '--hidden-import', 'requests',
        '--hidden-import', 'bs4',
        '--hidden-import', 'lxml',
        '--hidden-import', 'fuzzywuzzy',
        '--hidden-import', 'Levenshtein',
        '--hidden-import', 'docx',
    ])
    
    # 添加主程序文件
    cmd.append('src/space_planning/main.py')
    
    print("执行命令:", ' '.join(cmd))
    print()
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ 可执行文件构建成功")
        print(f"输出目录: {os.path.abspath('dist')}")
        return True
    else:
        print("❌ 构建失败")
        print("错误信息:")
        print(result.stderr)
        return False

def create_version_info():
    """创建版本信息文件"""
    print("创建版本信息文件...")
    
    version_info = '''# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0.
    filevers=(2, 1, 0, 0),
    prodvers=(2, 1, 0, 0),
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x40004,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'080404b0',
        [StringStruct(u'CompanyName', u'空间规划政策分析团队'),
        StringStruct(u'FileDescription', u'空间规划政策爬虫与合规性分析系统'),
        StringStruct(u'FileVersion', u'2.1.0'),
        StringStruct(u'InternalName', u'空间规划政策爬虫系统'),
        StringStruct(u'LegalCopyright', u'Copyright (C) 2025 空间规划政策分析团队'),
        StringStruct(u'OriginalFilename', u'空间规划政策爬虫系统.exe'),
        StringStruct(u'ProductName', u'空间规划政策爬虫与合规性分析系统'),
        StringStruct(u'ProductVersion', u'2.1.0')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)'''
    
    with open('version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_info)
    
    print("✅ 创建版本信息文件: version_info.txt")

def create_installer_script():
    """创建Inno Setup安装脚本"""
    print("创建Inno Setup安装脚本...")
    
    installer_script = '''[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName=空间规划政策爬虫与合规性分析系统
AppVersion=2.1.0
AppVerName=空间规划政策爬虫与合规性分析系统 2.1.0
AppPublisher=空间规划政策分析团队
AppPublisherURL=https://gitee.com/ViVi141/space-planning-spider
AppSupportURL=https://gitee.com/ViVi141/space-planning-spider
AppUpdatesURL=https://gitee.com/ViVi141/space-planning-spider
DefaultDirName={autopf}\\空间规划政策爬虫系统
DefaultGroupName=空间规划政策爬虫系统
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=installer
OutputBaseFilename=空间规划政策爬虫系统_v2.1.0_安装程序
SetupIconFile=docs\\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\\空间规划政策爬虫系统.exe
UninstallDisplayName=空间规划政策爬虫与合规性分析系统
VersionInfoVersion=2.1.0.0
VersionInfoCompany=空间规划政策分析团队
VersionInfoDescription=空间规划政策爬虫与合规性分析系统
VersionInfoCopyright=Copyright (C) 2025 空间规划政策分析团队
VersionInfoProductName=空间规划政策爬虫与合规性分析系统
VersionInfoProductVersion=2.1.0.0

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "startmenuicon"; Description: "{cm:CreateStartMenuIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checked

[Files]
Source: "dist\\空间规划政策爬虫系统.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "版本管理说明.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\\空间规划政策爬虫系统"; Filename: "{app}\\空间规划政策爬虫系统.exe"; Tasks: startmenuicon
Name: "{group}\\{cm:UninstallProgram,空间规划政策爬虫系统}"; Filename: "{uninstallexe}"; Tasks: startmenuicon
Name: "{autodesktop}\\空间规划政策爬虫系统"; Filename: "{app}\\空间规划政策爬虫系统.exe"; Tasks: desktopicon
Name: "{userappdata}\\Microsoft\\Internet Explorer\\Quick Launch\\空间规划政策爬虫系统"; Filename: "{app}\\空间规划政策爬虫系统.exe"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\\空间规划政策爬虫系统.exe"; Description: "{cm:LaunchProgram,空间规划政策爬虫系统}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\\空间规划政策爬虫系统"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\\空间规划政策爬虫系统"; ValueType: string; ValueName: "Version"; ValueData: "2.1.0"; Flags: uninsdeletekey

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // 安装完成后的操作
  end;
end;
'''
    
    with open('installer_script.iss', 'w', encoding='utf-8') as f:
        f.write(installer_script)
    
    print("✅ 创建安装脚本: installer_script.iss")

def build_installer():
    """构建安装程序"""
    print("构建安装程序...")
    
    # 检查Inno Setup是否可用
    try:
        result = subprocess.run(['iscc', '/?'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ 找到Inno Setup编译器")
            
            # 创建installer目录
            os.makedirs('installer', exist_ok=True)
            
            # 运行Inno Setup编译
            cmd = ['iscc', 'installer_script.iss']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 安装程序构建成功")
                print(f"安装程序位置: {os.path.abspath('installer')}")
                return True
            else:
                print("❌ 安装程序构建失败")
                print("错误信息:")
                print(result.stderr)
                return False
        else:
            print("⚠️ Inno Setup编译器不可用，跳过安装程序构建")
            return False
    except FileNotFoundError:
        print("⚠️ Inno Setup未安装，跳过安装程序构建")
        print("请安装Inno Setup: https://jrsoftware.org/isinfo.php")
        return False

def create_portable_package():
    """创建便携版打包"""
    print("创建便携版打包...")
    
    portable_dir = "dist/空间规划政策爬虫系统_便携版"
    if os.path.exists(portable_dir):
        shutil.rmtree(portable_dir)
    
    os.makedirs(portable_dir, exist_ok=True)
    
    # 复制可执行文件
    exe_source = "dist/空间规划政策爬虫系统.exe"
    exe_dest = f"{portable_dir}/空间规划政策爬虫系统.exe"
    
    if os.path.exists(exe_source):
        shutil.copy2(exe_source, exe_dest)
        print(f"✅ 复制可执行文件: {exe_dest}")
    else:
        print(f"❌ 可执行文件不存在: {exe_source}")
        return False
    
    # 复制文档文件
    docs_to_copy = ['LICENSE', 'README.md', 'CHANGELOG.md', '版本管理说明.md']
    for doc in docs_to_copy:
        if os.path.exists(doc):
            shutil.copy2(doc, portable_dir)
            print(f"✅ 复制文档: {doc}")
    
    # 创建启动脚本
    startup_script = '''@echo off
chcp 65001 >nul
title 空间规划政策爬虫系统 - 便携版
echo ============================================================
echo 空间规划政策爬虫与合规性分析系统
echo 版本：v2.1.0
echo 便携版
echo ============================================================
echo.
echo 正在启动程序...
echo.
start "" "空间规划政策爬虫系统.exe"
'''
    
    with open(f"{portable_dir}/启动程序.bat", 'w', encoding='utf-8') as f:
        f.write(startup_script)
    
    # 创建说明文件
    readme_content = '''空间规划政策爬虫与合规性分析系统 - 便携版
版本：v2.1.0
更新时间：2025.7.8

使用说明：
1. 双击"启动程序.bat"启动程序
2. 程序数据将保存在程序目录下的database.db文件中
3. 删除整个文件夹即可完全卸载程序

注意事项：
- 请勿将程序放在需要管理员权限的目录中
- 建议将程序放在用户目录下
- 数据文件与程序文件在同一目录，请妥善保管
- 便携版不会在系统中注册，不会出现在"程序和功能"中

技术支持：
https://gitee.com/ViVi141/space-planning-spider

更新日志：
请查看CHANGELOG.md文件了解详细更新内容
'''
    
    with open(f"{portable_dir}/使用说明.txt", 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"✅ 便携版打包完成: {portable_dir}")
    return True

def create_uninstaller():
    """创建卸载程序"""
    print("创建卸载程序...")
    
    uninstaller_script = '''@echo off
chcp 65001 >nul
title 空间规划政策爬虫系统 - 卸载程序
echo ============================================================
echo 空间规划政策爬虫与合规性分析系统 - 卸载程序
echo ============================================================
echo.

echo 正在卸载程序...
echo.

REM 删除程序文件
if exist "%~dp0空间规划政策爬虫系统.exe" (
    del /f /q "%~dp0空间规划政策爬虫系统.exe"
    echo ✅ 删除程序文件
)

REM 删除数据文件
if exist "%~dp0database.db" (
    del /f /q "%~dp0database.db"
    echo ✅ 删除数据文件
)

REM 删除文档文件
for %%f in (LICENSE README.md CHANGELOG.md "版本管理说明.md") do (
    if exist "%~dp0%%f" (
        del /f /q "%~dp0%%f"
        echo ✅ 删除文档文件: %%f
    )
)

echo.
echo ============================================================
echo 卸载完成！
echo ============================================================
echo.
echo 程序已从当前目录完全删除。
echo.
pause
'''
    
    with open("dist/空间规划政策爬虫系统_便携版/卸载程序.bat", 'w', encoding='utf-8') as f:
        f.write(uninstaller_script)
    
    print("✅ 创建卸载程序: dist/空间规划政策爬虫系统_便携版/卸载程序.bat")

def main():
    """主函数"""
    print("=" * 80)
    print("空间规划政策爬虫系统 - 完整Windows安装程序打包")
    print("版本：v2.1.0")
    print("更新时间：2025.7.8")
    print("=" * 80)
    
    # 检查依赖
    check_dependencies()
    
    # 清理构建目录
    clean_build_dirs()
    
    # 创建版本信息
    create_version_info()
    
    # 构建可执行文件
    if not build_executable():
        print("❌ 构建失败，退出")
        return
    
    # 创建安装脚本
    create_installer_script()
    
    # 构建安装程序
    installer_success = build_installer()
    
    # 创建便携版
    if create_portable_package():
        # 创建卸载程序
        create_uninstaller()
        
        print("\n" + "=" * 80)
        print("打包完成！")
        print("=" * 80)
        
        if installer_success:
            print("✅ 标准安装程序: installer/空间规划政策爬虫系统_v2.1.0_安装程序.exe")
            print("   - 可在'程序和功能'中看到")
            print("   - 包含完整的安装向导")
            print("   - 支持卸载功能")
        
        print("✅ 便携版: dist/空间规划政策爬虫系统_便携版/")
        print("   - 包含启动脚本和说明文件")
        print("   - 包含卸载程序")
        print("   - 适合U盘携带")
        
        print("✅ 可执行文件: dist/空间规划政策爬虫系统.exe")
        
        print("\n打包文件说明：")
        if installer_success:
            print("- 标准安装程序：适合正式安装，可在'程序和功能'中管理")
        print("- 便携版：适合临时使用，数据存储在程序目录")
        print("- 可执行文件：单个exe文件，包含所有依赖")
    else:
        print("❌ 便携版创建失败")

if __name__ == "__main__":
    main() 