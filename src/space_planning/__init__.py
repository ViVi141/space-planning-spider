"""
空间规划政策爬虫系统

一个用于爬取中国城市空间规划政策的Python GUI程序，
支持国家、省、市、区四个层级的政策爬取，具备智能检索、
数据管理、导出、定时更新和智能对比等功能。
"""

__version__ = "1.0.0"
__author__ = "空间规划政策爬虫开发团队"
__description__ = "空间规划政策爬虫系统"

# 移除相对导入，避免启动时出现问题
# from .core.config import Config
# from .core.database import DatabaseManager
# from .spider.anti_crawler import AntiCrawlerManager
# from .spider.national import NationalPolicyCrawler

__all__ = [
    'Config',
    'DatabaseManager', 
    'AntiCrawlerManager',
    'NationalPolicyCrawler'
] 