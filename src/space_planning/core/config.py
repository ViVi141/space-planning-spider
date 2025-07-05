#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件
"""

# 数据库配置
DATABASE_CONFIG = {
    'max_display_count': 1000,  # 最大显示数量
    'max_crawl_pages': 50,      # 最大爬取页数
    'timeout': 10,              # 网络请求超时时间
}

# 爬虫配置
SPIDER_CONFIG = {
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    'request_timeout': 15,
    'max_retries': 3,
    'min_delay': 1.0,
    'max_delay': 3.0,
    'max_requests_per_minute': 15,
}

# 防反爬虫配置
ANTI_CRAWLER_CONFIG = {
    'enable_proxy': False,  # 是否启用代理
    'enable_rotation': True,  # 是否启用会话轮换
    'enable_frequency_limit': True,  # 是否启用频率限制
    'max_concurrent_requests': 5,  # 最大并发请求数
    'session_rotation_interval': 300,  # 会话轮换间隔（秒）
}

# 界面配置
UI_CONFIG = {
    'window_width': 1400,
    'window_height': 900,
    'table_row_height': 60,
    'text_area_height': 250,
}

# 政策类型关键词
POLICY_TYPES = {
    '总体规划': ['总体规划', '国土空间规划', '城市总体规划', '县域规划'],
    '控制性详细规划': ['控制性详细规划', '控规', '详细规划'],
    '专项规划': ['专项规划', '专项', '交通规划', '绿地规划', '基础设施规划'],
    '土地利用': ['土地利用', '用地', '土地管理', '建设用地'],
    '环境保护': ['环境保护', '生态', '污染', '环境'],
    '历史文化': ['历史文化', '文物', '古迹', '保护'],
    '交通规划': ['交通', '道路', '轨道交通', '公交'],
    '市政设施': ['市政', '给排水', '电力', '通信', '燃气']
}

# 合规性关键词
COMPLIANCE_KEYWORDS = {
    '强制性': ['必须', '应当', '禁止', '不得', '严禁'],
    '指导性': ['建议', '鼓励', '推荐', '引导'],
    '程序性': ['程序', '流程', '审批', '备案', '公示'],
    '标准性': ['标准', '规范', '要求', '指标', '参数']
}

class Config:
    """配置管理类"""
    
    def __init__(self):
        self.database = DATABASE_CONFIG
        self.spider = SPIDER_CONFIG
        self.anti_crawler = ANTI_CRAWLER_CONFIG
        self.ui = UI_CONFIG
        self.policy_types = POLICY_TYPES
        self.compliance_keywords = COMPLIANCE_KEYWORDS
    
    @classmethod
    def get_database_config(cls):
        """获取数据库配置"""
        return DATABASE_CONFIG
    
    @classmethod
    def get_spider_config(cls):
        """获取爬虫配置"""
        return SPIDER_CONFIG
    
    @classmethod
    def get_anti_crawler_config(cls):
        """获取防反爬虫配置"""
        return ANTI_CRAWLER_CONFIG
    
    @classmethod
    def get_ui_config(cls):
        """获取界面配置"""
        return UI_CONFIG
    
    @classmethod
    def get_policy_types(cls):
        """获取政策类型关键词"""
        return POLICY_TYPES
    
    @classmethod
    def get_compliance_keywords(cls):
        """获取合规性关键词"""
        return COMPLIANCE_KEYWORDS 