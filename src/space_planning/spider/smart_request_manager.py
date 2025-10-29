#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能请求管理器
根据配置选择不同的防检测策略（无代理池）
"""

import time
import random
import threading
import requests
import logging
from typing import Dict, Optional, Any, Tuple, List
from datetime import datetime
from urllib.parse import urlparse

from .config import crawler_config, AntiDetectionMode
from .advanced_anti_detection import AdvancedAntiDetection
from .javascript_fingerprint import JavaScriptFingerprint

class RetryStrategy:
    """智能重试策略"""
    def __init__(self, max_retries=3, base_delay=1, max_delay=30):
        self.max_retries = max_retries  # 最大重试次数
        self.base_delay = base_delay    # 基础延迟（秒）
        self.max_delay = max_delay      # 最大延迟（秒）
        self.retry_count = 0            # 当前重试次数
        self.last_error = None          # 最后一次错误
        self.error_counts = {}          # 错误类型统计
    
    def should_retry(self, error) -> bool:
        """判断是否应该重试"""
        # 记录错误
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        self.last_error = error
        
        # 超过最大重试次数
        if self.retry_count >= self.max_retries:
            return False
        
        # 判断错误类型是否可重试
        if isinstance(error, (requests.exceptions.Timeout,
                            requests.exceptions.ConnectionError,
                            requests.exceptions.ProxyError,
                            requests.exceptions.SSLError,
                            requests.exceptions.ChunkedEncodingError)):
            return True
        
        # 特定HTTP状态码可重试
        if isinstance(error, requests.exceptions.HTTPError):
            status_code = error.response.status_code
            return status_code in [429, 500, 502, 503, 504]
        
        return False
    
    def get_delay(self) -> float:
        """获取重试延迟时间（指数退避）"""
        delay = min(self.base_delay * (2 ** self.retry_count), self.max_delay)
        # 添加随机抖动，避免多个请求同时重试
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter
    
    def increment(self):
        """增加重试计数"""
        self.retry_count += 1
    
    def reset(self):
        """重置重试状态"""
        self.retry_count = 0
        self.last_error = None
    
    @property
    def stats(self) -> Dict:
        """获取重试统计信息"""
        return {
            'retry_count': self.retry_count,
            'last_error': str(self.last_error) if self.last_error else None,
            'error_counts': self.error_counts
        }

class SmartRequestManager:
    """智能请求管理器"""
    
    def __init__(self):
        # 初始化logger
        self.logger = logging.getLogger("SmartRequestManager")
        
        # 初始化组件
        self.anti_detection = AdvancedAntiDetection()
        self.js_fingerprint = JavaScriptFingerprint()
        
        # 请求配置
        self.session = requests.Session()
        self.request_history = []
        
        # 统计信息
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 初始化会话
        self._initialize_session()
        self.retry_strategy = RetryStrategy()
        
        # 初始化代理
        self._init_proxy()
    
    def _initialize_session(self):
        """初始化会话"""
        # 设置默认请求头
        headers = self._get_basic_headers()
        self.session.headers.update(headers)
    
    def _init_proxy(self):
        """初始化代理设置"""
        try:
            from .proxy_pool import get_shared_proxy, is_global_proxy_enabled
            if is_global_proxy_enabled():
                proxy_dict = get_shared_proxy()
                if proxy_dict:
                    self.session.proxies.update(proxy_dict)
                    self.logger.info(f"SmartRequestManager: 已设置代理")
        except Exception as e:
            self.logger.debug(f"SmartRequestManager: 初始化代理失败（可能未配置）: {e}")
    
    def _get_basic_headers(self) -> Dict[str, str]:
        """获取基础请求头"""
        return {
            'User-Agent': self._get_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def _get_user_agent(self) -> str:
        """获取User-Agent"""
        if crawler_config.get_config('headers_settings.randomize_user_agent'):
            return self.anti_detection.get_random_headers()['User-Agent']
        else:
            return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    def _get_enhanced_headers(self, url: str) -> Dict[str, str]:
        """获取增强模式请求头"""
        headers = self._get_basic_headers()
        
        # 添加Referer
        if crawler_config.get_config('headers_settings.add_referer'):
            parsed_url = urlparse(url)
            headers['Referer'] = f"{parsed_url.scheme}://{parsed_url.netloc}/"
        
        # 添加指纹信息
        if crawler_config.get_config('headers_settings.add_fingerprint'):
            fingerprint = self.js_fingerprint.generate_complete_fingerprint()
            headers['X-Client-Data'] = self.js_fingerprint.encode_fingerprint(fingerprint)
        
        return headers
    
    def get_headers(self, url: Optional[str] = None) -> Dict[str, str]:
        """获取请求头"""
        if url and crawler_config.is_enhanced_mode():
            return self._get_enhanced_headers(url)
        else:
            return self._get_basic_headers()
    
    def _simulate_behavior(self) -> None:
        """模拟人类行为"""
        if not crawler_config.get_config('behavior_settings.simulate_human_behavior'):
            return
        
        # 根据模式选择行为类型
        if crawler_config.is_enhanced_mode():
            # 增强模式：复杂行为模拟
            behavior_type = random.choice(['mouse', 'scroll', 'click', 'delay'])
            self.anti_detection.simulate_human_behavior(behavior_type)
        else:
            # 正常模式：简单延迟
            delay = random.uniform(
                crawler_config.get_config('request_delay.min'),
                crawler_config.get_config('request_delay.max')
            )
            time.sleep(delay)
    
    def make_request(self, url: str, method: str = 'GET', 
                    data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Tuple[requests.Response, Dict]:
        """发送请求（无代理池）"""
        start_time = time.time()
        
        # 准备请求参数
        request_params = self._prepare_request_params(url, method, data, headers)
        
        # 模拟人类行为
        self._simulate_behavior()
        
        # 发送请求
        response = self._send_request_with_retry(request_params)
        
        # 记录请求历史
        self._record_request(url, method, response, time.time() - start_time)
        
        return response, {
            'response_time': time.time() - start_time,
            'status_code': response.status_code,
            'mode': crawler_config.get_mode().value
        }
    
    def _prepare_request_params(self, url: str, method: str, data: Optional[Dict], 
                              headers: Optional[Dict]) -> Dict:
        """准备请求参数（无代理池）"""
        # 获取请求头
        if crawler_config.is_enhanced_mode():
            request_headers = self._get_enhanced_headers(url)
        else:
            request_headers = self._get_basic_headers()
        
        # 合并自定义请求头
        if headers:
            request_headers.update(headers)
        
        return {
            'url': url,
            'method': method,
            'data': data if data is not None else {},
            'headers': request_headers,
            'timeout': 30
        }
    
    def _send_request_with_retry(self, request_params: Dict) -> requests.Response:
        """发送请求并重试（支持代理）"""
        # 更新代理（每次请求前检查）
        try:
            from .proxy_pool import get_shared_proxy, is_global_proxy_enabled
            if is_global_proxy_enabled():
                proxy_dict = get_shared_proxy()
                if proxy_dict:
                    self.session.proxies.update(proxy_dict)
        except Exception:
            pass  # 代理获取失败时继续使用当前代理或无代理
        
        max_retries = crawler_config.get_config('retry_settings.max_retries')
        retry_delay = crawler_config.get_config('retry_settings.retry_delay')
        
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
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
                time.sleep(retry_delay * (attempt + 1))
        raise last_exception or Exception("请求失败")
    
    def _record_request(self, url: str, method: str, response: requests.Response, response_time: float):
        """记录请求历史"""
        with self.lock:
            self.total_requests += 1
            
            if response.status_code == 200:
                self.successful_requests += 1
            else:
                self.failed_requests += 1
            
            # 记录到历史
            self.request_history.append({
                'url': url,
                'method': method,
                'status_code': response.status_code,
                'response_time': response_time,
                'timestamp': datetime.now()
            })
            
            # 保持历史记录在合理范围内（取消限制）
            if len(self.request_history) > 10000:
                self.request_history = self.request_history[-5000:]
    
    def get_page(self, url: str, headers: Optional[Dict] = None, use_proxy: bool = True) -> Tuple[requests.Response, Dict]:
        """获取页面（带重试机制）"""
        self.retry_strategy.reset()
        start_time = time.time()
        
        while True:
            try:
                # 准备请求信息
                request_info = {
                    'proxy_used': False,  # 基础请求管理器不支持代理
                    'proxy_ip': None,
                    'proxy_port': None,
                    'retry_count': self.retry_strategy.retry_count,
                }
                
                # 发送请求
                response = requests.get(
                    url,
                    headers=headers or self.get_headers(),
                    timeout=30,
                    verify=True
                )
                response.raise_for_status()
                
                # 计算响应时间
                response_time = time.time() - start_time
                request_info['response_time'] = response_time
                
                # 记录成功
                self.record_success(url, response_time)
                
                return response, request_info
                
            except Exception as e:
                # 计算当前尝试的响应时间
                current_response_time = time.time() - start_time
                
                # 判断是否需要重试
                if not self.retry_strategy.should_retry(e):
                    # 记录失败
                    self.record_failure(url, str(e))
                    raise
                
                # 获取重试延迟时间
                delay = self.retry_strategy.get_delay()
                
                # 记录重试信息
                self.logger.warning(
                    f"请求失败 (重试 {self.retry_strategy.retry_count + 1}/{self.retry_strategy.max_retries}): "
                    f"URL={url}, 错误={str(e)}, 延迟={delay:.1f}秒"
                )
                
                # 增加重试计数
                self.retry_strategy.increment()
                
                # 等待重试
                time.sleep(delay)
                
                # 更新开始时间
                start_time = time.time()
    
    def record_success(self, url: str, response_time: float):
        """记录成功请求"""
        self.logger.info(f"请求成功: URL={url}, 响应时间={response_time:.2f}秒, "
                        f"重试次数={self.retry_strategy.retry_count}")
    
    def record_failure(self, url: str, error: str):
        """记录失败请求"""
        stats = self.retry_strategy.stats
        self.logger.error(
            f"请求最终失败: URL={url}, 错误={error}, "
            f"重试次数={stats['retry_count']}, "
            f"错误统计={stats['error_counts']}"
        )
    
    def get_request_stats(self) -> Dict:
        """获取请求统计信息"""
        stats = {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': round(self.successful_requests / self.total_requests * 100, 2) if self.total_requests > 0 else 0,
            'mode': crawler_config.get_mode().value
        }
        # 添加重试统计
        stats['retry_stats'] = self.retry_strategy.stats
        return stats
    
    def get_page_with_behavior(self, url: str, behavior_type: Optional[str] = None) -> Tuple[requests.Response, Dict]:
        """获取页面并模拟行为（无代理池）"""
        # 模拟行为
        if behavior_type:
            self.anti_detection.simulate_human_behavior(behavior_type)
        else:
            self._simulate_behavior()
        
        # 发送请求
        return self.make_request(url)
    
    def get_page_with_js_injection(self, url: str, js_code: Optional[str] = None) -> Tuple[requests.Response, Dict]:
        """获取页面并注入JavaScript（无代理池）"""
        # 如果有JS代码，可以在这里处理
        if js_code:
            # 这里可以添加JS注入逻辑
            pass
        
        # 发送请求
        return self.make_request(url)
    
    def get_session_info(self) -> Dict:
        """获取会话信息（无代理池）"""
        return {
            'mode': crawler_config.get_mode().value,
            'config': crawler_config.get_config(),
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
    
    def switch_mode(self, mode: AntiDetectionMode) -> None:
        """切换防检测模式"""
        crawler_config.set_mode(mode)
        print(f"已切换到{mode.value}模式")
    
    def print_status(self) -> None:
        """打印当前状态"""
        crawler_config.print_current_config()
        print(f"\n请求统计:")
        print(f"总请求数: {self.total_requests}")
        print(f"成功请求: {self.successful_requests}")
        print(f"失败请求: {self.failed_requests}")
        if self.total_requests > 0:
            print(f"成功率: {self.successful_requests / self.total_requests * 100:.1f}%")

# 全局实例
smart_request_manager = SmartRequestManager() 