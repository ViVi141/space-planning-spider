#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫模块包
"""

import pkgutil
import importlib
import os
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

def get_all_spider_levels() -> List[str]:
    """获取所有爬虫模块的机构名称"""
    levels = []
    spider_dir = os.path.dirname(__file__)
    
    for _, modname, ispkg in pkgutil.iter_modules([spider_dir]):
        if not ispkg and modname not in ['__init__', 'anti_crawler', 'monitor']:
            try:
                mod = importlib.import_module(f"space_planning.spider.{modname}")
                level = getattr(mod, "LEVEL_NAME", None)
                if level:
                    levels.append(level)
            except Exception as e:
                logger.error(f"加载爬虫模块{modname}失败: {e}", exc_info=True)
    
    return sorted(levels)

def get_spider_by_level(level: str):
    """根据机构名称获取对应的爬虫实例"""
    spider_dir = os.path.dirname(__file__)
    
    for _, modname, ispkg in pkgutil.iter_modules([spider_dir]):
        if not ispkg and modname not in ['__init__', 'anti_crawler', 'monitor']:
            try:
                mod = importlib.import_module(f"space_planning.spider.{modname}")
                if getattr(mod, "LEVEL_NAME", None) == level:
                    # 查找爬虫类（通常以Spider结尾）
                    for attr_name in dir(mod):
                        if attr_name.endswith('Spider') and not attr_name.startswith('_'):
                            spider_class = getattr(mod, attr_name)
                            if hasattr(spider_class, '__call__'):  # 确保是可调用的类
                                return spider_class()
            except Exception as e:
                logger.error(f"获取爬虫实例失败 {modname}: {e}", exc_info=True)
    
    return None

def get_spider_class_by_level(level: str):
    """根据机构名称获取对应的爬虫类（不实例化）"""
    spider_dir = os.path.dirname(__file__)
    
    for _, modname, ispkg in pkgutil.iter_modules([spider_dir]):
        if not ispkg and modname not in ['__init__', 'anti_crawler', 'monitor']:
            try:
                mod = importlib.import_module(f"space_planning.spider.{modname}")
                if getattr(mod, "LEVEL_NAME", None) == level:
                    # 查找爬虫类（通常以Spider结尾）
                    for attr_name in dir(mod):
                        if attr_name.endswith('Spider') and not attr_name.startswith('_'):
                            spider_class = getattr(mod, attr_name)
                            if hasattr(spider_class, '__call__'):  # 确保是可调用的类
                                return spider_class
            except Exception as e:
                logger.error(f"获取爬虫类失败 {modname}: {e}", exc_info=True)
    
    return None 