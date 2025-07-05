"""
核心功能模块

包含配置管理、数据库操作等核心功能
"""

# 移除相对导入，避免打包时出现问题
# from .config import Config
# from .database import DatabaseManager
# from . import database as db

__all__ = ['Config', 'DatabaseManager', 'db'] 