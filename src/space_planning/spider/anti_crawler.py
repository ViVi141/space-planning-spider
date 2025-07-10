#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
防反爬虫工具模块
"""

import random
import time
import requests
from urllib.parse import urlparse
import socket
import threading
from datetime import datetime, timedelta
import ssl
import certifi

# 只保留高级防封禁模块
from .advanced_anti_detection import (
    advanced_anti_detection, 
    cookie_manager, 
    ip_rotation_manager, 
    request_rate_limiter
)

class AntiCrawlerManager:
    """防反爬虫管理器（已移除代理池相关功能）"""
    
    def __init__(self):
        self.request_history = []  # 记录请求历史
        self.ip_blacklist = set()  # IP黑名单
        self.session = requests.Session()
        self.lock = threading.Lock()
        
        # 配置SSL - 安全优先
        self.session.verify = certifi.where()
        
        # 创建安全的SSL上下文
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.ssl_context.check_hostname = True  # 启用主机名验证
        self.ssl_context.verify_mode = ssl.CERT_REQUIRED  # 要求证书验证
        
        # 请求频率控制 - 优化速度
        self.min_delay = 0.2  # 最小延迟（秒）
        self.max_delay = 0.8  # 最大延迟（秒）
        self.max_requests_per_minute = 60  # 每分钟最大请求数
        
        # 高级防封禁配置
        self.use_advanced_anti_detection = True  # 是否使用高级防封禁
        self.use_cookie_management = True  # 是否使用Cookie管理
        self.use_ip_rotation = True  # 是否使用IP轮换
        self.use_rate_limiting = True  # 是否使用频率限制
        
        # 重试配置 - 优化速度
        self.max_retries = 2
        self.retry_delay = 2
    
    def make_request(self, url, method='GET', **kwargs):
        """发起请求（已移除代理相关逻辑）"""
        ssl_strategies = [
            {'verify': True},
            {'verify': self.session.verify, 'cert': None}
        ]
        
        # 不再有代理策略，全部直连
        proxy_strategies = [{}]
        
        # 重试机制
        for attempt in range(self.max_retries):
            for ssl_strategy in ssl_strategies:
                for proxy_strategy in proxy_strategies:
                    try:
                        # 合并配置
                        request_kwargs = kwargs.copy()
                        request_kwargs.update(ssl_strategy)
                        request_kwargs.update(proxy_strategy)
                        
                        # 添加额外的网络兼容性设置
                        request_kwargs['allow_redirects'] = True
                        request_kwargs['stream'] = False
                        
                        # 确保SSL安全验证
                        if not request_kwargs.get('verify', True):
                            print("警告: 检测到不安全的SSL配置，已跳过")
                            continue
                        
                        response = self.session.request(method, url, **request_kwargs)
                            return response
                    except Exception as e:
                        last_exception = e
                        time.sleep(self.retry_delay)
        raise Exception(f"请求失败: {url}") 
    
    def get_random_headers(self) -> dict:
        """获取随机请求头"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0'
        ]
        
        return {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        } 