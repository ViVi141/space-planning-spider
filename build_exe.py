#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空间规划政策合规性分析系统 - EXE打包脚本
支持多种打包方式：单文件、目录、安装程序
"""

import os
import sys
import shutil
import subprocess
import platform
from datetime import datetime

class ExeBuilder:
    def __init__(self):
        self.project_name = "空间规划政策合规性分析系统"
        self.version = "v3.0.0"
        self.main_file = "src/space_planning/main.py"
        self.icon_file = "docs/icon.ico"
        self.dist_dir = "dist"
        self.build_dir = "build"
        
    def check_requirements(self):
        """检查打包环境"""
        print("🔍 检查打包环境...")
        
        # 检查PyInstaller
        try:
            import PyInstaller
            print(f"✅ PyInstaller版本: {PyInstaller.__version__}")
        except ImportError:
            print("❌ PyInstaller未安装，正在安装...")
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
        
        # 检查主文件
        if not os.path.exists(self.main_file):
            print(f"❌ 主文件不存在: {self.main_file}")
            return False
        
        # 检查图标文件
        if not os.path.exists(self.icon_file):
            print(f"⚠️  图标文件不存在: {self.icon_file}")
            self.icon_file = None
        
        print("✅ 环境检查完成")
        return True
    
    def clean_build_dirs(self):
        """清理构建目录"""
        print("🧹 清理构建目录...")
        
        for dir_path in [self.dist_dir, self.build_dir]:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
                print(f"   已清理: {dir_path}")
        
        # 清理spec文件
        spec_files = [f for f in os.listdir(".") if f.endswith(".spec")]
        for spec_file in spec_files:
            if spec_file != "空间规划政策爬虫系统.spec":  # 保留原始spec
                os.remove(spec_file)
                print(f"   已清理: {spec_file}")
    
    def build_single_file(self):
        """构建单文件exe"""
        print("\n📦 构建单文件exe...")
        
        cmd = [
            "pyinstaller",
            "--onefile",
            "--windowed",
            "--name", f"{self.project_name}_{self.version}",
            "--distpath", self.dist_dir,
            "--workpath", self.build_dir,
            "--specpath", ".",
            "--clean",
            "--noconfirm"
        ]
        
        if self.icon_file and os.path.exists(self.icon_file):
            cmd.extend(["--icon", self.icon_file])
        
        # 添加数据文件
        cmd.extend(["--add-data", "src/space_planning;space_planning"])
        
        # 添加隐藏导入
        hidden_imports = [
            "PyQt5.QtCore",
            "PyQt5.QtGui", 
            "PyQt5.QtWidgets",
            "requests",
            "bs4",
            "sqlite3",
            "threading",
            "queue",
            "concurrent.futures"
        ]
        
        for imp in hidden_imports:
            cmd.extend(["--hidden-import", imp])
        
        cmd.append(self.main_file)
        
        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 单文件exe构建成功")
            return True
        else:
            print(f"❌ 构建失败: {result.stderr}")
            return False
    
    def build_directory(self):
        """构建目录模式exe"""
        print("\n📁 构建目录模式exe...")
        
        cmd = [
            "pyinstaller",
            "--onedir",
            "--windowed",
            "--name", f"{self.project_name}_{self.version}_目录版",
            "--distpath", self.dist_dir,
            "--workpath", self.build_dir,
            "--specpath", ".",
            "--clean",
            "--noconfirm"
        ]
        
        if self.icon_file and os.path.exists(self.icon_file):
            cmd.extend(["--icon", self.icon_file])
        
        # 添加数据文件
        cmd.extend(["--add-data", "src/space_planning;space_planning"])
        
        # 添加隐藏导入
        hidden_imports = [
            "PyQt5.QtCore",
            "PyQt5.QtGui", 
            "PyQt5.QtWidgets",
            "requests",
            "bs4",
            "sqlite3",
            "threading",
            "queue",
            "concurrent.futures"
        ]
        
        for imp in hidden_imports:
            cmd.extend(["--hidden-import", imp])
        
        cmd.append(self.main_file)
        
        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 目录模式exe构建成功")
            return True
        else:
            print(f"❌ 构建失败: {result.stderr}")
            return False
    
    def build_with_spec(self):
        """使用spec文件构建"""
        print("\n🔧 使用spec文件构建...")
        
        if not os.path.exists("空间规划政策爬虫系统.spec"):
            print("❌ spec文件不存在")
            return False
        
        cmd = [
            "pyinstaller",
            "--clean",
            "--noconfirm",
            "空间规划政策爬虫系统.spec"
        ]
        
        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ spec文件构建成功")
            return True
        else:
            print(f"❌ 构建失败: {result.stderr}")
            return False
    
    def create_launcher_scripts(self):
        """创建启动脚本"""
        print("\n📝 创建启动脚本...")
        
        # 创建Windows批处理文件
        launcher_content = f"""@echo off
chcp 65001 >nul
title {self.project_name} {self.version}
echo.
echo ========================================
echo {self.project_name} {self.version}
echo ========================================
echo.
echo 正在启动程序...
echo.

cd /d "%~dp0"
"{self.project_name}_{self.version}.exe"

echo.
echo 程序已退出，按任意键关闭窗口...
pause >nul
"""
        
        launcher_file = f"启动_{self.project_name}_{self.version}.bat"
        with open(launcher_file, "w", encoding="utf-8") as f:
            f.write(launcher_content)
        
        print(f"✅ 已创建启动脚本: {launcher_file}")
    
    def create_readme(self):
        """创建说明文档"""
        print("\n📖 创建说明文档...")
        
        readme_content = f"""# {self.project_name} {self.version}

## 系统要求
- Windows 7/8/10/11 (64位)
- 至少2GB可用内存
- 至少500MB可用磁盘空间

## 安装说明
1. 解压所有文件到任意目录
2. 双击"启动_{self.project_name}_{self.version}.bat"启动程序
3. 或直接双击exe文件启动

## 功能特性
- 多源政策数据爬取（国家级、省级、部级）
- 智能数据分析和合规性检查
- 多线程爬取支持（广东省）
- 数据导出（Word、Excel、文本、Markdown）
- 实时监控和状态管理

## 使用说明
1. 选择政策来源机构
2. 输入关键词或选择时间范围
3. 点击"智能查询"开始爬取
4. 查看结果并进行合规性分析
5. 导出报告或保存数据

## 注意事项
- 首次运行可能需要较长时间初始化
- 建议在非高峰期使用多线程功能
- 如遇到问题，请查看日志文件

## 技术支持
如有问题，请联系技术支持团队。

---
版本: {self.version}
构建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        readme_file = f"README_{self.project_name}_{self.version}.txt"
        with open(readme_file, "w", encoding="utf-8") as f:
            f.write(readme_content)
        
        print(f"✅ 已创建说明文档: {readme_file}")
    
    def package_release(self):
        """打包发布版本"""
        print("\n📦 打包发布版本...")
        
        release_dir = f"{self.project_name}_{self.version}_发布版"
        if os.path.exists(release_dir):
            shutil.rmtree(release_dir)
        
        os.makedirs(release_dir)
        
        # 复制exe文件
        exe_files = []
        for file in os.listdir(self.dist_dir):
            if file.endswith(".exe"):
                src = os.path.join(self.dist_dir, file)
                dst = os.path.join(release_dir, file)
                shutil.copy2(src, dst)
                exe_files.append(file)
        
        # 复制启动脚本
        launcher_file = f"启动_{self.project_name}_{self.version}.bat"
        if os.path.exists(launcher_file):
            shutil.copy2(launcher_file, release_dir)
        
        # 复制说明文档
        readme_file = f"README_{self.project_name}_{self.version}.txt"
        if os.path.exists(readme_file):
            shutil.copy2(readme_file, release_dir)
        
        # 复制使用说明
        if os.path.exists("多线程爬虫使用说明.md"):
            shutil.copy2("多线程爬虫使用说明.md", release_dir)
        
        print(f"✅ 发布版本已打包到: {release_dir}")
        print(f"包含文件: {', '.join(exe_files)}")
    
    def show_menu(self):
        """显示菜单"""
        print("\n" + "="*60)
        print(f"🚀 {self.project_name} {self.version} - EXE打包工具")
        print("="*60)
        print("请选择打包方式:")
        print("1. 构建单文件exe (推荐)")
        print("2. 构建目录模式exe")
        print("3. 使用spec文件构建")
        print("4. 完整打包 (构建+启动脚本+说明文档)")
        print("5. 清理构建文件")
        print("0. 退出")
        print("="*60)
        
        choice = input("请输入选择 (0-5): ").strip()
        return choice
    
    def run(self):
        """运行打包程序"""
        print(f"欢迎使用{self.project_name}打包工具!")
        
        if not self.check_requirements():
            print("❌ 环境检查失败，请检查依赖")
            return
        
        while True:
            choice = self.show_menu()
            
            if choice == "0":
                print("👋 再见!")
                break
            elif choice == "1":
                self.clean_build_dirs()
                if self.build_single_file():
                    print("✅ 单文件exe构建完成!")
                else:
                    print("❌ 构建失败!")
            elif choice == "2":
                self.clean_build_dirs()
                if self.build_directory():
                    print("✅ 目录模式exe构建完成!")
                else:
                    print("❌ 构建失败!")
            elif choice == "3":
                if self.build_with_spec():
                    print("✅ spec文件构建完成!")
                else:
                    print("❌ 构建失败!")
            elif choice == "4":
                print("🔄 开始完整打包流程...")
                self.clean_build_dirs()
                
                if self.build_single_file():
                    self.create_launcher_scripts()
                    self.create_readme()
                    self.package_release()
                    print("✅ 完整打包完成!")
                else:
                    print("❌ 构建失败!")
            elif choice == "5":
                self.clean_build_dirs()
                print("✅ 清理完成!")
            else:
                print("❌ 无效选择，请重新输入")
            
            input("\n按回车键继续...")

if __name__ == "__main__":
    builder = ExeBuilder()
    builder.run() 