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
        """记录请求"""
        domain = self._extract_domain(url)
        current_time = time.time()
        
        with self.lock:
            self.request_stats[domain].append({
                'time': current_time,
                'success': success,
                'error_type': error_type
            })
            
            if success:
                self.success_stats[domain] += 1
            else:
                self.error_stats[domain] += 1
    
    def _extract_domain(self, url):
        """提取域名"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return 'unknown'
    
    def get_success_rate(self, domain=None):
        """获取成功率"""
        with self.lock:
            if domain:
                total = self.success_stats[domain] + self.error_stats[domain]
                return self.success_stats[domain] / total if total > 0 else 0
            else:
                total_success = sum(self.success_stats.values())
                total_errors = sum(self.error_stats.values())
                total = total_success + total_errors
                return total_success / total if total > 0 else 0
    
    def get_request_frequency(self, domain=None, minutes=5):
        """获取请求频率"""
        current_time = time.time()
        time_window = minutes * 60
        
        with self.lock:
            if domain:
                requests = self.request_stats[domain]
            else:
                requests = []
                for domain_requests in self.request_stats.values():
                    requests.extend(domain_requests)
            
            recent_requests = [
                req for req in requests 
                if current_time - req['time'] < time_window
            ]
            
            return len(recent_requests) / minutes  # 每分钟请求数
    
    def get_error_summary(self):
        """获取错误摘要"""
        with self.lock:
            error_summary = defaultdict(int)
            for domain_requests in self.request_stats.values():
                for req in domain_requests:
                    if not req['success'] and req['error_type']:
                        error_summary[req['error_type']] += 1
            return dict(error_summary)
    
    def get_runtime_stats(self):
        """获取运行时间统计"""
        current_time = time.time()
        runtime = current_time - self.start_time
        
        with self.lock:
            total_requests = sum(len(requests) for requests in self.request_stats.values())
            total_success = sum(self.success_stats.values())
            total_errors = sum(self.error_stats.values())
            
            return {
                'runtime_seconds': runtime,
                'runtime_hours': runtime / 3600,
                'total_requests': total_requests,
                'total_success': total_success,
                'total_errors': total_errors,
                'success_rate': total_success / total_requests if total_requests > 0 else 0,
                'requests_per_hour': total_requests / (runtime / 3600) if runtime > 0 else 0
            }
    
    def should_slow_down(self, domain):
        """判断是否需要降低速度"""
        success_rate = self.get_success_rate(domain)
        error_count = self.error_stats[domain]
        
        # 如果成功率低于80%或错误次数过多，建议降低速度
        return success_rate < 0.8 or error_count > 10
    
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
        """重置统计"""
        with self.lock:
            self.request_stats.clear()
            self.error_stats.clear()
            self.success_stats.clear()
            self.start_time = time.time()
    
    def export_stats(self):
        """导出统计信息"""
        runtime_stats = self.get_runtime_stats()
        error_summary = self.get_error_summary()
        recommendations = self.get_recommendations()
        
        return {
            'runtime_stats': runtime_stats,
            'error_summary': error_summary,
            'recommendations': recommendations,
            'domain_stats': {
                domain: {
                    'success_rate': self.get_success_rate(domain),
                    'request_frequency': self.get_request_frequency(domain),
                    'total_requests': len(requests)
                }
                for domain, requests in self.request_stats.items()
            }
        }
    
    def get_stats(self):
        """获取统计信息（简化版）"""
        runtime_stats = self.get_runtime_stats()
        return {
            'total_requests': runtime_stats['total_requests'],
            'success_rate': runtime_stats['success_rate'],
            'requests_per_hour': runtime_stats['requests_per_hour'],
            'runtime_hours': runtime_stats['runtime_hours']
        } 