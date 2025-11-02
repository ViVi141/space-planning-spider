#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级防封禁模块
集成多种防检测策略
"""

import random
import time
import hashlib
import base64
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from urllib.parse import urlparse, parse_qs
import re
import logging

logger = logging.getLogger(__name__)

class AdvancedAntiDetection:
    """高级防封禁管理器"""
    
    def __init__(self):
        # 基础配置
        self.session_rotation_interval = 300  # 会话轮换间隔（秒）
        self.last_session_rotation = datetime.now()
        self.request_count = 0
        self.lock = threading.Lock()
        
        # 指纹伪装
        self.fingerprint_config = {
            'screen_resolution': ['1920x1080', '1366x768', '1440x900', '2560x1440'],
            'color_depth': [24, 32],
            'timezone': ['Asia/Shanghai', 'Asia/Beijing', 'Asia/Hong_Kong'],
            'language': ['zh-CN', 'zh-TW', 'en-US', 'en-GB'],
            'platform': ['Win32', 'MacIntel', 'Linux x86_64'],
            'do_not_track': [None, '1', '0'],
            'webgl_vendor': ['Google Inc.', 'Intel Inc.', 'NVIDIA Corporation'],
            'webgl_renderer': ['ANGLE (Intel, Intel(R) HD Graphics 620 Direct3D11 vs_5_0 ps_5_0)', 
                              'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0)']
        }
        
        # 请求头伪装
        self.headers_pool = self._generate_headers_pool()
        
        # 行为模拟
        self.behavior_patterns = {
            'mouse_movements': self._generate_mouse_patterns(),
            'scroll_patterns': self._generate_scroll_patterns(),
            'click_patterns': self._generate_click_patterns()
        }
        
        # 时间间隔随机化
        self.time_patterns = {
            'human_delay': (1, 3),  # 人类化延迟
            'page_load_delay': (2, 5),  # 页面加载延迟
            'session_delay': (30, 120)  # 会话间延迟
        }
        
        # 会话管理
        self.active_sessions = {}
        self.session_history = []
        
    def _generate_headers_pool(self) -> List[Dict]:
        """生成请求头池"""
        headers_pool = []
        
        # 基础浏览器配置
        browsers = [
            {
                'name': 'Chrome',
                'versions': ['120.0.0.0', '119.0.0.0', '118.0.0.0'],
                'platforms': ['Windows NT 10.0; Win64; x64', 'Macintosh; Intel Mac OS X 10_15_7']
            },
            {
                'name': 'Firefox',
                'versions': ['120.0', '119.0', '118.0'],
                'platforms': ['Windows NT 10.0; Win64; x64', 'Macintosh; Intel Mac OS X 10.15; rv:120.0']
            },
            {
                'name': 'Edge',
                'versions': ['120.0.0.0', '119.0.0.0'],
                'platforms': ['Windows NT 10.0; Win64; x64']
            }
        ]
        
        for browser in browsers:
            for version in browser['versions']:
                for platform in browser['platforms']:
                    headers = {
                        'User-Agent': f'Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) {browser["name"]}/{version} Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': random.choice(['zh-CN,zh;q=0.9,en;q=0.8', 'en-US,en;q=0.9,zh;q=0.8']),
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Cache-Control': 'max-age=0'
                    }
                    
                    # 添加随机指纹
                    if random.choice([True, False]):
                        headers['DNT'] = random.choice(['1', '0'])
                    
                    headers_pool.append(headers)
        
        return headers_pool
    
    def _generate_mouse_patterns(self) -> List[Dict]:
        """生成鼠标移动模式"""
        patterns = []
        
        # 人类化鼠标移动模式
        for _ in range(10):
            pattern = {
                'type': 'mouse_move',
                'coordinates': [(random.randint(0, 1920), random.randint(0, 1080)) for _ in range(random.randint(3, 8))],
                'duration': random.uniform(0.5, 2.0),
                'smoothness': random.uniform(0.7, 1.0)
            }
            patterns.append(pattern)
        
        return patterns
    
    def _generate_scroll_patterns(self) -> List[Dict]:
        """生成滚动模式"""
        patterns = []
        
        # 人类化滚动模式
        for _ in range(5):
            pattern = {
                'type': 'scroll',
                'direction': random.choice(['up', 'down']),
                'distance': random.randint(100, 800),
                'speed': random.uniform(0.5, 2.0),
                'pauses': random.randint(0, 3)
            }
            patterns.append(pattern)
        
        return patterns
    
    def _generate_click_patterns(self) -> List[Dict]:
        """生成点击模式"""
        patterns = []
        
        # 人类化点击模式
        for _ in range(5):
            pattern = {
                'type': 'click',
                'position': (random.randint(100, 1820), random.randint(100, 980)),
                'duration': random.uniform(0.1, 0.3),
                'pressure': random.uniform(0.5, 1.0)
            }
            patterns.append(pattern)
        
        return patterns
    
    def get_random_fingerprint(self) -> Dict:
        """获取随机浏览器指纹"""
        return {
            'screen_resolution': random.choice(self.fingerprint_config['screen_resolution']),
            'color_depth': random.choice(self.fingerprint_config['color_depth']),
            'timezone': random.choice(self.fingerprint_config['timezone']),
            'language': random.choice(self.fingerprint_config['language']),
            'platform': random.choice(self.fingerprint_config['platform']),
            'do_not_track': random.choice(self.fingerprint_config['do_not_track']),
            'webgl_vendor': random.choice(self.fingerprint_config['webgl_vendor']),
            'webgl_renderer': random.choice(self.fingerprint_config['webgl_renderer'])
        }
    
    def get_random_headers(self, referer: Optional[str] = None) -> Dict:
        """获取随机请求头"""
        headers = random.choice(self.headers_pool).copy()
        
        if referer:
            headers['Referer'] = referer
        
        # 添加随机指纹
        fingerprint = self.get_random_fingerprint()
        headers['X-Client-Data'] = self._encode_fingerprint(fingerprint)
        
        return headers
    
    def _encode_fingerprint(self, fingerprint: Dict) -> str:
        """编码指纹信息"""
        fingerprint_str = json.dumps(fingerprint, sort_keys=True)
        return base64.b64encode(fingerprint_str.encode()).decode()
    
    def simulate_human_behavior(self, behavior_type: Optional[str] = None) -> None:
        """模拟人类行为"""
        if behavior_type is None:
            behavior_type = random.choice(['mouse', 'scroll', 'click', 'delay'])
        
        if behavior_type == 'mouse':
            pattern = random.choice(self.behavior_patterns['mouse_movements'])
            self._simulate_mouse_movement(pattern)
        elif behavior_type == 'scroll':
            pattern = random.choice(self.behavior_patterns['scroll_patterns'])
            self._simulate_scroll_behavior(pattern)
        elif behavior_type == 'click':
            pattern = random.choice(self.behavior_patterns['click_patterns'])
            self._simulate_click_behavior(pattern)
        else:  # delay
            self._simulate_human_delay()
    
    def _simulate_mouse_movement(self, pattern: Dict) -> None:
        """模拟鼠标移动"""
        # 模拟鼠标移动的轨迹
        coordinates = pattern.get('coordinates', [])
        duration = pattern.get('duration', 1.0)
        smoothness = pattern.get('smoothness', 0.8)
        
        if coordinates:
            # 计算每个坐标点之间的时间间隔
            interval = duration / len(coordinates)
            
            for i, coord in enumerate(coordinates):
                # 添加随机性，模拟人类移动的不规则性
                if i > 0:
                    # 根据平滑度调整延迟
                    delay = interval * (1 + random.uniform(-0.2, 0.2)) * smoothness
                    time.sleep(delay)
                else:
                    time.sleep(interval * 0.5)  # 第一个点稍快
        else:
            # 如果没有坐标，使用默认延迟
            time.sleep(duration * 0.1)
    
    def _simulate_scroll_behavior(self, pattern: Dict) -> None:
        """模拟滚动行为"""
        direction = pattern.get('direction', 'down')
        distance = pattern.get('distance', 300)
        speed = pattern.get('speed', 1.0)
        pauses = pattern.get('pauses', 1)
        
        # 模拟滚动速度变化
        scroll_steps = max(1, int(distance / 50))  # 每50像素一步
        step_delay = (distance / speed) / scroll_steps
        
        for step in range(scroll_steps):
            # 添加随机暂停
            if pauses > 0 and random.random() < 0.3:
                time.sleep(random.uniform(0.1, 0.5))
            
            # 模拟滚动步骤
            time.sleep(step_delay * (1 + random.uniform(-0.3, 0.3)))
    
    def _simulate_click_behavior(self, pattern: Dict) -> None:
        """模拟点击行为"""
        position = pattern.get('position', (100, 100))
        duration = pattern.get('duration', 0.2)
        pressure = pattern.get('pressure', 0.8)
        
        # 模拟鼠标按下
        time.sleep(duration * 0.3)
        
        # 模拟点击保持
        time.sleep(duration * 0.4 * pressure)
        
        # 模拟鼠标释放
        time.sleep(duration * 0.3)
    
    def _simulate_human_delay(self) -> None:
        """模拟人类化延迟"""
        delay = random.uniform(*self.time_patterns['human_delay'])
        time.sleep(delay)
    
    def rotate_session(self) -> None:
        """轮换会话"""
        with self.lock:
            current_time = datetime.now()
            if (current_time - self.last_session_rotation).total_seconds() > self.session_rotation_interval:
                self._create_new_session()
                self.last_session_rotation = current_time
    
    def _create_new_session(self) -> None:
        """创建新会话"""
        session_id = hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:8]
        
        # 记录旧会话
        if self.active_sessions:
            self.session_history.append({
                'session_id': list(self.active_sessions.keys())[0],
                'duration': (datetime.now() - self.last_session_rotation).total_seconds(),
                'request_count': self.request_count
            })
        
        # 创建新会话
        self.active_sessions = {session_id: {
            'created_at': datetime.now(),
            'request_count': 0,
            'headers': self.get_random_headers()
        }}
        
        self.request_count = 0
        logger.info(f"会话已轮换: {session_id}")
    
    def get_session_info(self) -> Dict:
        """获取会话信息"""
        with self.lock:
            return {
                'active_sessions': len(self.active_sessions),
                'session_history': len(self.session_history),
                'total_requests': self.request_count,
                'last_rotation': self.last_session_rotation.isoformat()
            }
    
    def add_request_tracking(self, url: str, success: bool) -> None:
        """添加请求跟踪"""
        with self.lock:
            self.request_count += 1
            
            # 记录请求
            if self.active_sessions:
                session_id = list(self.active_sessions.keys())[0]
                self.active_sessions[session_id]['request_count'] += 1
    
    def get_behavior_pattern(self) -> Dict:
        """获取行为模式"""
        return {
            'mouse_pattern': random.choice(self.behavior_patterns['mouse_movements']),
            'scroll_pattern': random.choice(self.behavior_patterns['scroll_patterns']),
            'click_pattern': random.choice(self.behavior_patterns['click_patterns']),
            'delay_pattern': self.time_patterns['human_delay']
        }
    
    def wait_if_needed(self, domain: str) -> None:
        """如果需要则等待"""
        # 简单的频率控制
        time.sleep(random.uniform(0.5, 2.0))
    
    def enable_all_features(self) -> None:
        """启用所有功能"""
        logger.info("启用所有防检测功能")
    
    def disable_all_features(self) -> None:
        """禁用所有功能"""
        logger.info("禁用所有防检测功能")

class CookieManager:
    """Cookie管理器"""
    
    def __init__(self):
        self.cookies = {}
        self.cookie_history = []
        self.lock = threading.Lock()
    
    def set_cookies(self, domain: str, cookies: Dict) -> None:
        """设置Cookie"""
        with self.lock:
            self.cookies[domain] = cookies
    
    def get_cookies(self, domain: str) -> Dict:
        """获取Cookie"""
        with self.lock:
            return self.cookies.get(domain, {})
    
    def update_cookies(self, domain: str, new_cookies: Dict) -> None:
        """更新Cookie"""
        with self.lock:
            if domain not in self.cookies:
                self.cookies[domain] = {}
            self.cookies[domain].update(new_cookies)
    
    def clear_cookies(self, domain: Optional[str] = None) -> None:
        """清除Cookie"""
        with self.lock:
            if domain:
                self.cookies.pop(domain, None)
            else:
                self.cookies.clear()

class IPRotationManager:
    """IP轮换管理器"""
    
    def __init__(self):
        self.ip_pool = []
        self.current_ip_index = 0
        self.ip_usage_count = {}
        self.lock = threading.Lock()
    
    def add_ip(self, ip: str) -> None:
        """添加IP到池中"""
        with self.lock:
            if ip not in self.ip_pool:
                self.ip_pool.append(ip)
                self.ip_usage_count[ip] = 0
    
    def get_next_ip(self) -> Optional[str]:
        """获取下一个IP"""
        with self.lock:
            if not self.ip_pool:
                return None
            
            # 轮换策略：选择使用次数最少的IP
            min_usage = min(self.ip_usage_count.values())
            candidates = [ip for ip, count in self.ip_usage_count.items() if count == min_usage]
            
            if candidates:
                selected_ip = random.choice(candidates)
                self.ip_usage_count[selected_ip] += 1
                return selected_ip
            
            return None
    
    def mark_ip_failed(self, ip: str) -> None:
        """标记IP为失败"""
        with self.lock:
            if ip in self.ip_usage_count:
                self.ip_usage_count[ip] += 10  # 增加使用次数，降低优先级
    
    def get_ip_stats(self) -> Dict:
        """获取IP统计信息"""
        with self.lock:
            return {
                'total_ips': len(self.ip_pool),
                'ip_usage': self.ip_usage_count.copy()
            }

class RequestRateLimiter:
    """请求频率限制器"""
    
    def __init__(self):
        self.domain_limits = {}
        self.request_history = {}
        self.lock = threading.Lock()
    
    def set_domain_limit(self, domain: str, max_requests: int, time_window: int) -> None:
        """设置域名限制"""
        with self.lock:
            self.domain_limits[domain] = {
                'max_requests': max_requests,
                'time_window': time_window
            }
    
    def can_request(self, domain: str) -> bool:
        """检查是否可以请求"""
        with self.lock:
            if domain not in self.domain_limits:
                return True
            
            limit = self.domain_limits[domain]
            current_time = time.time()
            
            # 清理过期记录
            if domain in self.request_history:
                self.request_history[domain] = [
                    req_time for req_time in self.request_history[domain]
                    if current_time - req_time < limit['time_window']
                ]
            else:
                self.request_history[domain] = []
            
            # 检查是否超过限制
            if len(self.request_history[domain]) >= limit['max_requests']:
                return False
            
            # 记录本次请求
            self.request_history[domain].append(current_time)
            return True
    
    def wait_if_needed(self, domain: str) -> None:
        """如果需要则等待"""
        while not self.can_request(domain):
            time.sleep(1)

# 全局实例
advanced_anti_detection = AdvancedAntiDetection()
cookie_manager = CookieManager()
ip_rotation_manager = IPRotationManager()
request_rate_limiter = RequestRateLimiter() 