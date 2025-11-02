#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫监控模块
"""

import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict

class CrawlerMonitor:
    """爬虫监控器"""
    
    def __init__(self):
        self.request_stats = defaultdict(list)
        self.error_stats = defaultdict(int)
        self.success_stats = defaultdict(int)
        self.start_time = time.time()
        self.lock = threading.Lock()
        
    def record_request(self, url, success=True, error_type=None):
        """记录请求（增强错误处理和参数验证）"""
        try:
            # 验证URL参数
            if not url:
                url = 'unknown'
            
            domain = self._extract_domain(str(url))
            current_time = time.time()
            
            with self.lock:
                self.request_stats[domain].append({
                    'time': current_time,
                    'success': bool(success),
                    'error_type': str(error_type) if error_type else None
                })
                
                if success:
                    self.success_stats[domain] += 1
                else:
                    self.error_stats[domain] += 1
        except Exception as e:
            # 记录请求失败不应该影响主流程，只记录日志
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"记录请求监控数据失败: {e}, url={url}")
    
    def _extract_domain(self, url):
        """提取域名（增强错误处理）"""
        if not url or not isinstance(url, str):
            return 'unknown'
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc
            # 如果没有netloc，可能是不完整的URL，尝试从path中提取
            if not domain:
                # 尝试从path中提取（如：/api/test -> api.test）
                if parsed.path:
                    parts = parsed.path.strip('/').split('/')
                    if parts:
                        domain = parts[0]
            return domain if domain else 'unknown'
        except (AttributeError, ValueError, TypeError) as e:
            # 记录但不抛出异常，返回unknown
            return 'unknown'
    
    def get_success_rate(self, domain=None):
        """获取成功率（增强错误处理）"""
        try:
            with self.lock:
                if domain:
                    success_count = self.success_stats.get(domain, 0)
                    error_count = self.error_stats.get(domain, 0)
                    total = success_count + error_count
                    return success_count / total if total > 0 else 0.0
                else:
                    total_success = sum(self.success_stats.values())
                    total_errors = sum(self.error_stats.values())
                    total = total_success + total_errors
                    return total_success / total if total > 0 else 0.0
        except (KeyError, ZeroDivisionError, AttributeError, TypeError):
            return 0.0
    
    def get_request_frequency(self, domain=None, minutes=5):
        """获取请求频率（增强错误处理）"""
        try:
            current_time = time.time()
            time_window = minutes * 60 if minutes > 0 else 300  # 默认5分钟
            
            with self.lock:
                if domain:
                    requests = self.request_stats.get(domain, [])
                else:
                    requests = []
                    for domain_requests in self.request_stats.values():
                        if isinstance(domain_requests, list):
                            requests.extend(domain_requests)
                
                recent_requests = [
                    req for req in requests 
                    if isinstance(req, dict) and 
                       'time' in req and 
                       (current_time - req['time']) < time_window
                ]
                
                return len(recent_requests) / minutes if minutes > 0 else 0.0
        except (KeyError, AttributeError, TypeError, ZeroDivisionError):
            return 0.0
    
    def get_error_summary(self):
        """获取错误摘要（增强错误处理）"""
        try:
            with self.lock:
                error_summary = defaultdict(int)
                for domain_requests in self.request_stats.values():
                    if isinstance(domain_requests, list):
                        for req in domain_requests:
                            if isinstance(req, dict) and not req.get('success') and req.get('error_type'):
                                error_type = str(req['error_type'])
                                error_summary[error_type] += 1
                return dict(error_summary)
        except (AttributeError, TypeError, KeyError):
            return {}
    
    def get_runtime_stats(self):
        """获取运行时间统计（增强错误处理）"""
        try:
            current_time = time.time()
            runtime = current_time - self.start_time if hasattr(self, 'start_time') else 0
            
            with self.lock:
                total_requests = sum(
                    len(requests) if isinstance(requests, list) else 0 
                    for requests in self.request_stats.values()
                )
                total_success = sum(self.success_stats.values()) if hasattr(self, 'success_stats') else 0
                total_errors = sum(self.error_stats.values()) if hasattr(self, 'error_stats') else 0
                
                # 计算成功率
                success_rate = total_success / total_requests if total_requests > 0 else 0.0
                
                # 计算每小时请求数
                requests_per_hour = total_requests / (runtime / 3600) if runtime > 0 else 0.0
                
                # 计算最近1小时的请求数
                one_hour_ago = current_time - 3600
                recent_requests = 0
                for domain_requests in self.request_stats.values():
                    if isinstance(domain_requests, list):
                        recent_requests += len([
                            req for req in domain_requests 
                            if isinstance(req, dict) and 
                               'time' in req and 
                               req['time'] > one_hour_ago
                        ])
                
                return {
                    'runtime_seconds': runtime,
                    'runtime_hours': runtime / 3600.0 if runtime > 0 else 0.0,
                    'total_requests': total_requests,
                    'total_success': total_success,
                    'total_errors': total_errors,
                    'success_rate': success_rate,
                    'requests_per_hour': requests_per_hour,
                    'recent_requests_1h': recent_requests,
                    'active_domains': len(self.request_stats) if self.request_stats else 0
                }
        except (AttributeError, TypeError, ZeroDivisionError, KeyError) as e:
            # 返回默认值而不是抛出异常
            return {
                'runtime_seconds': 0.0,
                'runtime_hours': 0.0,
                'total_requests': 0,
                'total_success': 0,
                'total_errors': 0,
                'success_rate': 0.0,
                'requests_per_hour': 0.0,
                'recent_requests_1h': 0,
                'active_domains': 0
            }
    
    def should_slow_down(self, domain):
        """判断是否需要降低速度（增强错误处理）"""
        try:
            success_rate = self.get_success_rate(domain)
            error_count = self.error_stats.get(domain, 0)
            
            # 如果成功率低于80%或错误次数过多，建议降低速度
            return success_rate < 0.8 or error_count > 10
        except (KeyError, AttributeError, TypeError):
            # 如果domain不存在或出现其他错误，默认不降低速度
            return False
    
    def get_recommendations(self):
        """获取建议"""
        recommendations = []
        
        runtime_stats = self.get_runtime_stats()
        success_rate = runtime_stats['success_rate']
        
        if success_rate < 0.7:
            recommendations.append("成功率较低，建议增加请求间隔")
        
        if runtime_stats['requests_per_hour'] > 100:
            recommendations.append("请求频率过高，建议降低爬取速度")
        
        error_summary = self.get_error_summary()
        if '403' in error_summary:
            recommendations.append("检测到403错误，可能被反爬虫检测，建议更换User-Agent")
        
        if '429' in error_summary:
            recommendations.append("检测到429错误，请求过于频繁，建议增加延迟")
        
        return recommendations
    
    def reset_stats(self):
        """重置统计（增强错误处理）"""
        try:
            with self.lock:
                if hasattr(self, 'request_stats'):
                    self.request_stats.clear()
                if hasattr(self, 'error_stats'):
                    self.error_stats.clear()
                if hasattr(self, 'success_stats'):
                    self.success_stats.clear()
                self.start_time = time.time()
        except (AttributeError, TypeError):
            # 如果属性不存在，重新初始化
            self.__init__()
    
    def export_stats(self):
        """导出统计信息（增强错误处理）"""
        try:
            runtime_stats = self.get_runtime_stats()
            error_summary = self.get_error_summary()
            recommendations = self.get_recommendations()
            
            # 构建域名统计（增强错误处理）
            domain_stats = {}
            try:
                with self.lock:
                    for domain, requests in self.request_stats.items():
                        if isinstance(requests, list):
                            domain_stats[str(domain)] = {
                                'success_rate': self.get_success_rate(domain),
                                'request_frequency': self.get_request_frequency(domain),
                                'total_requests': len(requests)
                            }
            except (KeyError, AttributeError, TypeError):
                domain_stats = {}
            
            return {
                'runtime_stats': runtime_stats,
                'error_summary': error_summary,
                'recommendations': recommendations or [],
                'domain_stats': domain_stats
            }
        except Exception as e:
            # 即使出现错误，也返回基本的统计信息
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"导出监控统计信息失败: {e}", exc_info=True)
            return {
                'runtime_stats': self.get_runtime_stats(),
                'error_summary': {},
                'recommendations': [],
                'domain_stats': {}
            }
    
    def get_stats(self):
        """获取统计信息（完整版，增强错误处理）"""
        try:
            runtime_stats = self.get_runtime_stats()
            error_summary = self.get_error_summary()
            recommendations = self.get_recommendations()
            
            # 构建域名统计（增强错误处理）
            domain_stats = {}
            try:
                with self.lock:
                    for domain, requests in self.request_stats.items():
                        if isinstance(requests, list):
                            domain_stats[str(domain)] = {
                                'success_rate': self.get_success_rate(domain),
                                'request_frequency': self.get_request_frequency(domain),
                                'total_requests': len(requests)
                            }
            except (KeyError, AttributeError, TypeError):
                domain_stats = {}
            
            return {
                'runtime_stats': runtime_stats,
                'error_summary': error_summary,
                'recommendations': recommendations or [],
                'domain_stats': domain_stats
            }
        except Exception as e:
            # 即使出现错误，也返回基本的统计信息
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"获取监控统计信息失败: {e}", exc_info=True)
            return {
                'runtime_stats': self.get_runtime_stats(),
                'error_summary': {},
                'recommendations': [],
                'domain_stats': {}
            } 