#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志配置模块
提供统一的日志系统，替代print语句
"""

import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime


class AppLogger:
    """应用程序日志管理器"""
    
    _initialized = False
    _log_dir = None
    
    @classmethod
    def initialize(cls, log_dir=None, level=logging.INFO):
        """
        初始化日志系统
        
        Args:
            log_dir: 日志目录路径，如果为None则使用应用数据目录
            level: 日志级别，默认为INFO
        """
        if cls._initialized:
            return
        
        # 确定日志目录
        if log_dir is None:
            from . import config
            app_data_dir = config.app_config.app_data_dir
            log_dir = os.path.join(app_data_dir, 'logs')
        else:
            log_dir = os.path.abspath(log_dir)
        
        cls._log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # 清除已有的处理器
        root_logger.handlers.clear()
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # 文件处理器（带日志轮转）
        log_file = os.path.join(log_dir, 'app.log')
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # 文件记录更详细的日志
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # 错误日志单独记录
        error_log_file = os.path.join(log_dir, 'error.log')
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
        cls._initialized = True
        logging.info(f"日志系统初始化完成，日志目录: {log_dir}")
    
    @classmethod
    def get_logger(cls, name=None):
        """
        获取日志记录器
        
        Args:
            name: 日志记录器名称，通常使用模块名
        
        Returns:
            logging.Logger实例
        """
        if not cls._initialized:
            cls.initialize()
        
        if name is None:
            # 自动获取调用模块的名称
            import inspect
            frame = inspect.currentframe().f_back
            module_name = frame.f_globals.get('__name__', 'unknown')
            return logging.getLogger(module_name)
        else:
            return logging.getLogger(name)
    
    @classmethod
    def get_log_dir(cls):
        """获取日志目录"""
        if not cls._initialized:
            cls.initialize()
        return cls._log_dir


# 便捷函数
def get_logger(name=None):
    """
    获取日志记录器的便捷函数
    
    Args:
        name: 日志记录器名称
    
    Returns:
        logging.Logger实例
    """
    return AppLogger.get_logger(name)


def initialize_logging(log_dir=None, level=logging.INFO):
    """
    初始化日志系统的便捷函数
    
    Args:
        log_dir: 日志目录路径
        level: 日志级别
    """
    AppLogger.initialize(log_dir, level)

