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

# 使用独立代理池
# 代理池功能已移除，不再使用代理

class AntiCrawlerManager:
    """防反爬虫管理器"""
    
    def __init__(self):
        self.request_history = {}  # 记录请求历史
        self.ip_blacklist = set()  # IP黑名单
        self.session = requests.Session()
        self.lock = threading.Lock()
        
        # 配置SSL
        self.session.verify = certifi.where()
        
        # 创建自定义SSL上下文
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # 请求频率控制 - 优化速度
        self.min_delay = 0.2  # 最小延迟（秒）
        self.max_delay = 0.8  # 最大延迟（秒）
        self.max_requests_per_minute = 60  # 每分钟最大请求数
        
        # 代理池功能已移除
        
        # 重试配置 - 优化速度
        self.max_retries = 2
        self.retry_delay = 2
        
    def get_random_user_agent(self):
        """获取随机User-Agent"""
        # 使用内置的User-Agent列表，避免fake_useragent的兼容性问题
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/119.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/118.0.0.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:119.0) Gecko/20100101 Firefox/119.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (X11; Linux x86_64; rv:119.0) Gecko/20100101 Firefox/119.0'
        ]
        return random.choice(user_agents)
    
    def get_random_headers(self, referer=None):
        """生成随机请求头"""
        headers = {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }
        
        if referer:
            headers['Referer'] = referer
            
        return headers
    
    # 代理池相关方法已移除
    
    def check_request_frequency(self, domain):
        """检查请求频率"""
        # 如果设置为无限制，直接返回True
        if self.max_requests_per_minute >= 999999:
            return True
            
        current_time = datetime.now()
        
        with self.lock:
            if domain not in self.request_history:
                self.request_history[domain] = []
            
            # 清理超过1分钟的历史记录
            self.request_history[domain] = [
                t for t in self.request_history[domain] 
                if current_time - t < timedelta(minutes=1)
            ]
            
            # 检查频率
            if len(self.request_history[domain]) >= self.max_requests_per_minute:
                return False
            
            # 记录本次请求
            self.request_history[domain].append(current_time)
            return True
    
    def random_delay(self):
        """随机延迟"""
        if self.min_delay == 0 and self.max_delay == 0:
            return  # 禁用延迟时直接返回
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
    
    def is_ip_blocked(self, ip):
        """检查IP是否被屏蔽"""
        return ip in self.ip_blacklist
    
    def add_blocked_ip(self, ip):
        """添加被屏蔽的IP"""
        self.ip_blacklist.add(ip)
    
    def make_request(self, url, method='GET', **kwargs):
        """发送请求（带防反爬虫机制，不使用代理池）"""
        domain = urlparse(url).netloc
        
        # 检查请求频率
        if not self.check_request_frequency(domain):
            raise Exception(f"请求频率过高，域名: {domain}")
        
        # 随机延迟
        self.random_delay()
        
        # 获取随机请求头
        headers = kwargs.get('headers', {})
        if not headers:
            headers = self.get_random_headers()
        else:
            headers['User-Agent'] = self.get_random_user_agent()
        kwargs['headers'] = headers
        
        # 设置超时 - 优化速度
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 15
        
        # 使用自定义SSL配置
        if 'verify' not in kwargs:
            kwargs['verify'] = certifi.where()
        
        # 重试机制
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    print(f"警告: 收到403状态码，可能被反爬虫检测")
                    self.random_delay()
                    self.rotate_session()  # 轮换会话
                    continue
                elif response.status_code == 429:
                    print(f"警告: 收到429状态码，请求过于频繁，等待10秒")
                    time.sleep(10)
                    self.rotate_session()  # 轮换会话
                    continue
                elif response.status_code in [502, 503, 504]:
                    print(f"警告: 服务器错误 {response.status_code}，等待重试")
                    time.sleep(3)
                    continue
                else:
                    response.raise_for_status()
                    
            except requests.exceptions.SSLError as e:
                print(f"SSL错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
            except requests.exceptions.RequestException as e:
                print(f"请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
        
        raise Exception("所有重试都失败了")
    
    def rotate_session(self):
        """轮换会话"""
        self.session.close()
        self.session = requests.Session()
        
        # 设置新的会话参数
        self.session.headers.update(self.get_random_headers())
    
    def get_session_info(self):
        """获取会话信息"""
        return {
            'total_requests': len([reqs for reqs in self.request_history.values()]),
            'blocked_ips': len(self.ip_blacklist),
            'proxy_count': 0,  # 代理池已移除
            'current_proxy': None
        }

class RequestRateLimiter:
    """请求频率限制器"""
    
    def __init__(self, max_requests=20, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = threading.Lock()
    
    def can_request(self):
        """检查是否可以发送请求"""
        # 如果设置为无限制，直接返回True
        if self.max_requests >= 999999:
            return True
            
        current_time = time.time()
        
        with self.lock:
            # 清理过期的请求记录
            self.requests = [req_time for req_time in self.requests 
                           if current_time - req_time < self.time_window]
            
            # 检查是否超过限制
            if len(self.requests) >= self.max_requests:
                return False
            
            # 记录本次请求
            self.requests.append(current_time)
            return True
    
    def wait_if_needed(self):
        """如果需要则等待"""
        while not self.can_request():
            time.sleep(1)

class IPRotator:
    """IP轮换器"""
    
    def __init__(self):
        self.proxy_list = []
        self.current_index = 0
        self.lock = threading.Lock()
    
    def add_proxy(self, proxy):
        """添加代理"""
        self.proxy_list.append(proxy)
    
    def get_proxy(self):
        """获取代理"""
        if not self.proxy_list:
            return None
        
        with self.lock:
            proxy = self.proxy_list[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxy_list)
            return proxy
    
    def remove_proxy(self, proxy):
        """移除失效的代理"""
        if proxy in self.proxy_list:
            self.proxy_list.remove(proxy) 