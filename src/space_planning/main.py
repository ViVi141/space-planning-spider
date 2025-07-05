#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空间规划政策爬虫系统 - 主程序入口
"""

import os
import sys

# 自动设置Qt平台插件路径
def setup_qt_environment():
    """设置Qt环境变量，解决平台插件问题"""
    try:
        import PyQt5
        pyqt5_path = os.path.dirname(PyQt5.__file__)
        plugins_path = os.path.join(pyqt5_path, 'Qt5', 'plugins')
        
        if os.path.exists(plugins_path):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugins_path
            print(f"已设置Qt插件路径: {plugins_path}")
        else:
            # 尝试其他可能的路径
            alt_plugins_path = os.path.join(pyqt5_path, 'Qt', 'plugins')
            if os.path.exists(alt_plugins_path):
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = alt_plugins_path
                print(f"已设置Qt插件路径: {alt_plugins_path}")
            else:
                print(f"警告: 未找到Qt插件目录，尝试路径: {plugins_path}")
    except ImportError:
        print("警告: PyQt5未安装")
    except Exception as e:
        print(f"设置Qt环境时出错: {e}")

# 在导入PyQt5相关模块之前设置环境
setup_qt_environment()

from space_planning.gui.main_window import main

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"运行失败: {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...") 