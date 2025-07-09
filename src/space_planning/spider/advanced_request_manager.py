#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级请求管理器
集成所有防封禁功能（已移除代理池相关功能）
"""

import time
import random
import threading
import requests
from typing import Dict, Optional, Any, Tuple, List
from datetime import datetime, timedelta
from urllib.parse import urlparse

from .advanced_anti_detection import AdvancedAntiDetection
from .javascript_fingerprint import JavaScriptFingerprint

class AdvancedRequestManager:
    """高级请求管理器（无代理池）"""
    
    def __init__(self):
        # 初始化各个组件
        self.anti_detection = AdvancedAntiDetection()
        self.js_fingerprint = JavaScriptFingerprint()
        
        # 请求配置
        self.session = requests.Session()
        self.request_history = []
        self.max_retries = 3
        self.retry_delay = 2
        
        # 统计信息
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 初始化会话
        self._initialize_session()
    
    def _initialize_session(self):
        """初始化会话"""
        # 设置默认请求头
        self.session.headers.update({
            'User-Agent': self.anti_detection.get_random_headers()['User-Agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def _prepare_request_params(self, url: str, method: str, data: Optional[Dict], 
                              headers: Optional[Dict]) -> Dict:
        """准备请求参数（无代理池）"""
        # 获取随机请求头
        random_headers = self.anti_detection.get_random_headers(url)
        
        # 合并自定义请求头
        if headers:
            random_headers.update(headers)
        
        # 检查频率限制
        domain = urlparse(url).netloc
        self.anti_detection.wait_if_needed(domain)
        
        return {
            'url': url,
            'method': method,
            'data': data if data is not None else {},
            'headers': random_headers,
            'timeout': 30
        }
    
    def _send_request_with_retry(self, request_params: Dict, retry_on_failure: bool) -> requests.Response:
        """发送请求并重试（无代理池）"""
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                # 轮换会话
                self.anti_detection.rotate_session()
                
                # 发送请求
                response = self.session.request(
                    method=request_params['method'],
                    url=request_params['url'],
                    data=request_params['data'],
                    headers=request_params['headers'],
                    timeout=request_params['timeout']
                )
                
                # 检查响应状态
                if response.status_code == 200:
                    return response
                else:
                    raise requests.RequestException(f"HTTP {response.status_code}")
            except Exception as e:
                last_exception = e
                time.sleep(self.retry_delay)
        raise last_exception or Exception("请求失败")
    
    def get_page(self, url: str, headers: Optional[Dict] = None) -> Tuple[requests.Response, Dict]:
        """获取页面（无代理池）"""
        request_params = self._prepare_request_params(url, 'GET', None, headers)
        response = self._send_request_with_retry(request_params, retry_on_failure=True)
        return response, {
            'response_time': 0,
            'status_code': response.status_code
        }
    
    def get_session_info(self) -> Dict:
        """获取会话信息（无代理池）"""
        return {
            'anti_detection': self.anti_detection.get_session_info(),
            'request_stats': {
                'total_requests': self.total_requests,
                'successful_requests': self.successful_requests,
                'failed_requests': self.failed_requests,
                'success_rate': round(self.successful_requests / self.total_requests * 100, 2) if self.total_requests > 0 else 0
            }
        }
    
    def get_request_history(self, limit: int = 50) -> List[Dict]:
        """获取请求历史"""
        with self.lock:
            return self.request_history[-limit:]
    
    def clear_request_history(self):
        """清除请求历史"""
        with self.lock:
            self.request_history.clear() 