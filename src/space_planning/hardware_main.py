#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空间规划政策爬虫系统 - 主程序入口（无授权版）
"""

import sys
import os
import traceback
from pathlib import Path

# 让 space-planning-spider 目录（即包含 src 的那一层）加入 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def setup_qt_environment():
    """设置Qt环境变量，解决平台插件问题"""
    try:
        import PyQt5
        pyqt5_path = os.path.dirname(PyQt5.__file__)
        plugins_path = os.path.join(pyqt5_path, 'Qt5', 'plugins')
        
        if os.path.exists(plugins_path):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugins_path
            print(f"✅ Qt插件路径已设置: {plugins_path}")
        else:
            # 尝试其他可能的路径
            alt_plugins_path = os.path.join(pyqt5_path, 'Qt', 'plugins')
            if os.path.exists(alt_plugins_path):
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = alt_plugins_path
                print(f"✅ Qt插件路径已设置: {alt_plugins_path}")
            else:
                print(f"⚠️ 未找到Qt插件目录")
    except ImportError:
        print("❌ PyQt5未安装")
    except Exception as e:
        print(f"⚠️ 设置Qt环境时出错: {e}")

def check_system_environment():
    """检查系统环境"""
    print("🔍 检查系统环境...")
    
    # 检查Python版本
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 7):
        print(f"❌ Python版本过低: {python_version.major}.{python_version.minor}")
        print("   需要Python 3.7或更高版本")
        return False
    else:
        print(f"✅ Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # 检查必要模块
    required_modules = ['PyQt5', 'requests', 'bs4', 'lxml']
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module} 已安装")
        except ImportError:
            print(f"❌ {module} 未安装")
            return False
    
    # 检查网络连接
    try:
        import requests
        response = requests.get('https://www.baidu.com', timeout=5)
        if response.status_code == 200:
            print("✅ 网络连接正常")
        else:
            print("⚠️ 网络连接异常")
    except:
        print("⚠️ 网络连接检查失败")
    
    return True

def main():
    """主程序入口"""
    try:
        print("=" * 60)
        print("空间规划政策爬虫系统")
        print("版本：v2.1.1")
        print("开发者：ViVi141")
        print("联系邮箱：747384120@qq.com")
        print("=" * 60)
        print()
        
        # 检查系统环境
        if not check_system_environment():
            print("❌ 系统环境检查失败，程序退出")
            input("按回车键退出...")
            return
        
        print()
        
        # 设置Qt环境
        setup_qt_environment()
        print()
        
        # 导入主程序模块
        print("🚀 正在启动主程序...")
        
        # 启动主程序
        from .gui.main_window import main as gui_main
        gui_main()
            
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序运行失败: {e}")
        print("\n详细错误信息:")
        traceback.print_exc()
        print("\n" + "=" * 60)
        print("如果问题持续存在，请检查：")
        print("1. Python版本是否为3.7或更高")
        print("2. 依赖包是否正确安装")
        print("3. 网络连接是否正常")
        print("=" * 60)
    finally:
        print("\n程序已退出")
        input("按回车键关闭窗口...")

if __name__ == "__main__":
    main() 