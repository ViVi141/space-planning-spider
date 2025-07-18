#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空间规划政策爬虫系统 - EXE打包脚本（修复版）
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import PyInstaller
        print("✅ PyInstaller已安装")
    except ImportError:
        print("❌ PyInstaller未安装，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller安装完成")
    
    # 检查其他必要依赖
    required_packages = [
        "PyQt5", "requests", "beautifulsoup4", "python-docx", 
        "fuzzywuzzy", "python-Levenshtein", "lxml", "pandas", 
        "openpyxl", "kdl"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} 未安装")
    
    if missing_packages:
        print(f"\n正在安装缺失的包: {', '.join(missing_packages)}")
        for package in missing_packages:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"✅ {package} 安装完成")
            except subprocess.CalledProcessError:
                print(f"❌ {package} 安装失败")
                return False
    
    return True

def create_spec_file():
    """创建PyInstaller spec文件"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# 获取项目根目录
project_root = Path.cwd()
src_path = project_root / 'src'

# 数据文件
datas = [
    (str(src_path / 'space_planning' / 'gui' / 'proxy_config.json'), 'space_planning/gui'),
    (str(src_path / 'crawler_config.json'), 'space_planning'),
    (str(project_root / 'docs' / 'icon.ico'), 'docs'),
]

# 隐藏导入
hiddenimports = [
    'PyQt5.QtCore',
    'PyQt5.QtGui', 
    'PyQt5.QtWidgets',
    'requests',
    'bs4',
    'docx',
    'fuzzywuzzy',
    'Levenshtein',
    'lxml',
    'pandas',
    'openpyxl',
    'kdl',
    'kdl.auth',
    'kdl.client',
    'space_planning.gui.main_window',
    'space_planning.gui.crawler_settings_dialog',
    'space_planning.gui.crawler_status_dialog',
    'space_planning.gui.database_manager_dialog',
    'space_planning.gui.rag_export_dialog',
    'space_planning.spider.guangdong',
    'space_planning.spider.national',
    'space_planning.spider.mnr',
    'space_planning.spider.enhanced_base_crawler',
    'space_planning.spider.persistent_proxy_manager',
    'space_planning.spider.smart_request_manager',
    'space_planning.spider.advanced_anti_detection',
    'space_planning.spider.javascript_fingerprint',
    'space_planning.core.database',
    'space_planning.core.config',
    'space_planning.utils.export',
    'space_planning.utils.rag_export',
    'space_planning.utils.compliance',
    'space_planning.utils.compare',
    'space_planning.utils.migrate',
    # 添加必要的标准库模块
    'email',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    'email.mime.base',
    'email.mime.nonmultipart',
    'urllib',
    'urllib.parse',
    'urllib.request',
    'urllib.error',
    'urllib.response',
    'xml',
    'xml.etree',
    'xml.etree.ElementTree',
    'http',
    'http.client',
    'http.cookiejar',
    'html',
    'html.parser',
    'html.entities',
]

# 排除模块（修复版本）
excludes = [
    'matplotlib',
    'numpy',
    'scipy',
    'PIL',
    'cv2',
    'tkinter',
    'test',
    'unittest',
    'doctest',
    'pdb',
    'pydoc',
    'pydoc_data',
    'setuptools',
    'pkg_resources',
    'pkg_resources._vendor',
    'pkg_resources.extern',
    'pkg_resources._vendor.packaging',
    'pkg_resources._vendor.pyparsing',
    'pkg_resources._vendor.six',
    'pkg_resources._vendor.requests',
    'pkg_resources._vendor.urllib3',
    'pkg_resources._vendor.chardet',
    'pkg_resources._vendor.certifi',
    'pkg_resources._vendor.idna',
    'pkg_resources._vendor.requests.packages',
    'pkg_resources._vendor.requests.packages.urllib3',
    'pkg_resources._vendor.requests.packages.urllib3.util',
    'pkg_resources._vendor.requests.packages.urllib3.contrib',
    'pkg_resources._vendor.requests.packages.urllib3.packages',
    'pkg_resources._vendor.requests.packages.urllib3.packages.ssl_match_hostname',
    'pkg_resources._vendor.requests.packages.urllib3.packages.rfc3986',
    'pkg_resources._vendor.requests.packages.urllib3.packages.ordered_dict',
    'pkg_resources._vendor.requests.packages.urllib3.packages.backports',
    'pkg_resources._vendor.requests.packages.urllib3.packages.backports.makefile',
    'pkg_resources._vendor.requests.packages.urllib3.packages.backports.ssl_match_hostname',
    'pkg_resources._vendor.requests.packages.urllib3.packages.backports.ordered_dict',
    'pkg_resources._vendor.requests.packages.urllib3.packages.backports.makefile',
    'pkg_resources._vendor.requests.packages.urllib3.packages.backports.ssl_match_hostname',
    'pkg_resources._vendor.requests.packages.urllib3.packages.backports.ordered_dict',
]

a = Analysis(
    [str(src_path / 'space_planning' / 'main.py')],
    pathex=[str(src_path)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

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
    icon=str(project_root / 'docs' / 'icon.ico'),
)
'''
    
    with open('space_planning_spider_fixed.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✅ 已创建修复版 spec 文件")

def build_exe():
    """构建EXE文件"""
    print("\n=== 开始构建EXE文件（修复版）===")
    
    # 检查依赖
    if not check_dependencies():
        print("❌ 依赖检查失败，无法继续构建")
        return False
    
    # 创建spec文件
    create_spec_file()
    
    # 清理之前的构建
    if os.path.exists('build'):
        shutil.rmtree('build')
        print("✅ 已清理build目录")
    
    if os.path.exists('dist'):
        shutil.rmtree('dist')
        print("✅ 已清理dist目录")
    
    # 构建EXE
    try:
        print("正在构建EXE文件，请稍候...")
        subprocess.check_call([
            sys.executable, "-m", "PyInstaller", 
            "--clean", "--noconfirm", "space_planning_spider_fixed.spec"
        ])
        
        # 检查构建结果
        exe_path = os.path.join('dist', '空间规划政策爬虫系统.exe')
        if os.path.exists(exe_path):
            file_size = os.path.getsize(exe_path) / (1024 * 1024)  # MB
            print(f"✅ EXE构建成功!")
            print(f"文件路径: {exe_path}")
            print(f"文件大小: {file_size:.1f} MB")
            
            # 复制必要文件到dist目录
            dist_dir = 'dist'
            if not os.path.exists(dist_dir):
                os.makedirs(dist_dir)
            
            # 复制README和LICENSE
            for file in ['README.md', 'LICENSE', 'CHANGELOG.md']:
                if os.path.exists(file):
                    shutil.copy2(file, dist_dir)
                    print(f"✅ 已复制 {file}")
            
            # 复制启动脚本
            if os.path.exists('启动程序.bat'):
                shutil.copy2('启动程序.bat', dist_dir)
                print("✅ 已复制启动脚本")
            
            print(f"\n🎉 构建完成! EXE文件位于: {exe_path}")
            return True
        else:
            print("❌ EXE文件未生成")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 构建过程中出错: {e}")
        return False

def main():
    """主函数"""
    print("=== 空间规划政策爬虫系统 - EXE打包工具（修复版）===")
    print("版本: v3.0.0")
    print("修复内容: 解决email模块和distutils冲突问题")
    print()
    
    # 检查当前目录
    if not os.path.exists('src/space_planning/main.py'):
        print("❌ 错误: 请在项目根目录运行此脚本")
        return
    
    # 开始构建
    if build_exe():
        print("\n✅ 打包完成!")
        print("\n使用说明:")
        print("1. EXE文件位于 dist/ 目录")
        print("2. 可以直接运行 空间规划政策爬虫系统.exe")
        print("3. 首次运行可能需要几秒钟启动时间")
        print("4. 如果遇到问题，请检查是否有杀毒软件拦截")
    else:
        print("\n❌ 打包失败!")
        print("请检查错误信息并重试")

if __name__ == "__main__":
    main() 