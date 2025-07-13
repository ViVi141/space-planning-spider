#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
支持代理池的基础爬虫类
集成快代理私密代理功能
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import requests
import json
import os

from .smart_request_manager import smart_request_manager
from .config import crawler_config, AntiDetectionMode
from .proxy_pool import ProxyManager, ProxyInfo

class ProxyBaseCrawler:
    """支持代理池的基础爬虫类"""
    
    def __init__(self, name: str = "ProxyBaseCrawler", enable_proxy: bool = True):
        self.name = name
        self.logger = logging.getLogger(f"crawler.{name}")
        
        # 使用智能请求管理器
        self.request_manager = smart_request_manager
        
        # 代理管理器
        self.proxy_manager = ProxyManager()
        self.enable_proxy = enable_proxy
        
        # 加载代理配置
        self.proxy_config = self.load_proxy_config()
        
        # 爬虫状态
        self.is_running = False
        self.start_time = None
        self.end_time = None
        
        # 统计信息
        self.total_pages = 0
        self.successful_pages = 0
        self.failed_pages = 0
        self.proxy_usage_count = 0
        
        # 配置
        self.config = crawler_config
        
        # 当前使用的代理
        self.current_proxy: Optional[ProxyInfo] = None
        
        # 重试配置
        self.max_retries = 3  # 最大重试次数
        self.retry_delay = 5  # 初始重试延迟（秒）
        self.max_retry_delay = 60  # 最大重试延迟（秒）
        self.retry_codes = {403, 429, 500, 502, 503, 504}  # 需要重试的HTTP状态码
        
        # 如果启用代理，启动代理管理器
        if self.enable_proxy and self.proxy_config.get('enabled', False):
            self.proxy_manager.start()
            self.logger.info("代理池已启动")
    
    def load_proxy_config(self) -> Dict:
        """加载代理配置"""
        config_file = os.path.join(
            os.path.dirname(__file__), '..', 'gui', 'proxy_config.json'
        )
        
        default_config = {
            'enabled': False,
            'secret_id': '',
            'secret_key': '',
            'username': '',
            'password': '',
            'max_proxies': 5,
            'check_interval': 300
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并配置，保留默认值
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                self.logger.error(f"加载代理配置失败: {e}")
        
        return default_config
    
    def set_mode(self, mode: AntiDetectionMode) -> None:
        """设置防检测模式"""
        self.request_manager.switch_mode(mode)
        self.logger.info(f"切换到{mode.value}模式")
    
    def get_proxy(self) -> Optional[Dict[str, str]]:
        """获取代理"""
        if not self.enable_proxy or not self.proxy_config.get('enabled', False):
            return None
        
        try:
            proxy_dict = self.proxy_manager.get_proxy_dict()
            if proxy_dict:
                self.current_proxy = self.proxy_manager.get_proxy()
                self.logger.debug(f"使用代理: {self.current_proxy.ip}:{self.current_proxy.port}")
                return proxy_dict
            else:
                self.logger.warning("无法获取代理")
                return None
        except Exception as e:
            self.logger.error(f"获取代理失败: {e}")
            return None
    
    def report_proxy_success(self, response_time: float = None):
        """报告代理使用成功"""
        if self.current_proxy and self.enable_proxy:
            self.proxy_manager.proxy_pool.report_proxy_result(self.current_proxy, True, response_time)
            self.proxy_usage_count += 1
    
    def report_proxy_failure(self, response_time: float = None):
        """报告代理使用失败"""
        if self.current_proxy and self.enable_proxy:
            self.proxy_manager.proxy_pool.report_proxy_result(self.current_proxy, False, response_time)
    
    def get_page(self, url: str, headers: Optional[Dict] = None, use_proxy: bool = True, 
                retry_count: int = 0, last_error: Optional[Exception] = None) -> Tuple[requests.Response, Dict]:
        """获取页面（带重试机制）"""
        proxy_dict = None
        start_time = time.time()
        response_time = None
        
        try:
            if use_proxy and self.enable_proxy:
                # 如果上次请求失败，尝试更换代理
                if retry_count > 0:
                    self.logger.info(f"第{retry_count}次重试，更换代理重试")
                proxy_dict = self.get_proxy()
            
            if proxy_dict:
                # 使用代理请求
                response = requests.get(
                    url,
                    headers=headers,
                    proxies=proxy_dict,
                    timeout=30,
                    verify=True
                )
                response_time = time.time() - start_time
                info = {
                    'proxy_used': True, 
                    'proxy_ip': self.current_proxy.ip if self.current_proxy else None,
                    'proxy_port': self.current_proxy.port if self.current_proxy else None,
                    'response_time': response_time,
                    'retry_count': retry_count
                }
                self.logger.info(f"使用代理 {self.current_proxy.ip}:{self.current_proxy.port} "
                               f"访问: {url} (耗时: {response_time:.2f}s)")
                
                # 检查响应状态码
                if response.status_code in self.retry_codes and retry_count < self.max_retries:
                    self.report_proxy_failure(response_time)
                    return self._handle_retry(url, headers, use_proxy, retry_count, 
                                           Exception(f"HTTP {response.status_code}"))
                
                self.report_proxy_success(response_time)
            else:
                # 不使用代理
                response, info = self.request_manager.get_page(url, headers)
                response_time = time.time() - start_time
                info['proxy_used'] = False
                info['response_time'] = response_time
                info['retry_count'] = retry_count
                self.logger.info(f"直接访问（不使用代理）: {url} (耗时: {response_time:.2f}s)")
                
                # 检查响应状态码
                if response.status_code in self.retry_codes and retry_count < self.max_retries:
                    return self._handle_retry(url, headers, use_proxy, retry_count, 
                                           Exception(f"HTTP {response.status_code}"))
            
            return response, info
            
        except Exception as e:
            response_time = time.time() - start_time
            if proxy_dict:
                self.report_proxy_failure(response_time)
                self.logger.error(f"代理 {self.current_proxy.ip}:{self.current_proxy.port} "
                                f"访问失败: {url}, 错误: {e}, 耗时: {response_time:.2f}s")
            else:
                self.logger.error(f"直接访问失败: {url}, 错误: {e}, 耗时: {response_time:.2f}s")
            
            # 处理重试
            if retry_count < self.max_retries:
                return self._handle_retry(url, headers, use_proxy, retry_count, e)
            else:
                self.logger.error(f"达到最大重试次数({self.max_retries})，放弃请求: {url}")
                if last_error:
                    self.logger.error(f"首次错误: {last_error}")
                raise
    
    def _handle_retry(self, url: str, headers: Optional[Dict], use_proxy: bool, 
                     retry_count: int, error: Exception) -> Tuple[requests.Response, Dict]:
        """处理重试逻辑"""
        retry_count += 1
        # 使用指数退避策略计算延迟时间
        delay = min(self.retry_delay * (2 ** (retry_count - 1)), self.max_retry_delay)
        
        self.logger.warning(f"请求失败，{delay}秒后进行第{retry_count}次重试: {url}")
        self.logger.warning(f"失败原因: {error}")
        
        time.sleep(delay)
        return self.get_page(url, headers, use_proxy, retry_count, error)
    
    def get_page_with_behavior(self, url: str, behavior_type: Optional[str] = None, use_proxy: bool = True) -> Tuple[requests.Response, Dict]:
        """获取页面并模拟行为"""
        proxy_dict = None
        if use_proxy and self.enable_proxy:
            proxy_dict = self.get_proxy()
        
        try:
            if proxy_dict:
                # 使用代理请求
                response = requests.get(
                    url,
                    headers=self.request_manager.get_headers(),
                    proxies=proxy_dict,
                    timeout=30,
                    verify=True
                )
                info = {'proxy_used': True, 'proxy_ip': self.current_proxy.ip if self.current_proxy else None}
                self.report_proxy_success()
            else:
                # 不使用代理
                response, info = self.request_manager.get_page_with_behavior(url, behavior_type)
                info['proxy_used'] = False
            
            self.logger.info(f"成功获取页面(行为模拟): {url}")
            return response, info
            
        except Exception as e:
            if proxy_dict:
                self.report_proxy_failure()
            self.logger.error(f"获取页面失败: {url}, 错误: {e}")
            raise
    
    def get_page_with_js_injection(self, url: str, js_code: Optional[str] = None, use_proxy: bool = True) -> Tuple[requests.Response, Dict]:
        """获取页面并注入JavaScript"""
        proxy_dict = None
        if use_proxy and self.enable_proxy:
            proxy_dict = self.get_proxy()
        
        try:
            if proxy_dict:
                # 使用代理请求
                response = requests.get(
                    url,
                    headers=self.request_manager.get_headers(),
                    proxies=proxy_dict,
                    timeout=30,
                    verify=True
                )
                info = {'proxy_used': True, 'proxy_ip': self.current_proxy.ip if self.current_proxy else None}
                self.report_proxy_success()
            else:
                # 不使用代理
                response, info = self.request_manager.get_page_with_js_injection(url, js_code)
                info['proxy_used'] = False
            
            self.logger.info(f"成功获取页面(JS注入): {url}")
            return response, info
            
        except Exception as e:
            if proxy_dict:
                self.report_proxy_failure()
            self.logger.error(f"获取页面失败: {url}, 错误: {e}")
            raise
    
    def start_crawling(self) -> None:
        """开始爬取"""
        self.is_running = True
        self.start_time = datetime.now()
        self.logger.info(f"开始爬取: {self.name}")
    
    def stop_crawling(self) -> None:
        """停止爬取"""
        self.is_running = False
        self.end_time = datetime.now()
        self.logger.info(f"停止爬取: {self.name}")
        
        # 停止代理管理器
        if self.enable_proxy:
            self.proxy_manager.stop()
    
    def record_page_result(self, url: str, success: bool, response_time: float = 0) -> None:
        """记录页面爬取结果"""
        self.total_pages += 1
        
        if success:
            self.successful_pages += 1
            self.logger.info(f"页面爬取成功: {url} (耗时: {response_time:.2f}s)")
        else:
            self.failed_pages += 1
            self.logger.error(f"页面爬取失败: {url}")
    
    def get_crawling_stats(self) -> Dict:
        """获取爬取统计信息"""
        duration = None
        if self.start_time:
            end_time = self.end_time or datetime.now()
            duration = (end_time - self.start_time).total_seconds()
        
        # 获取代理统计
        proxy_stats = self.proxy_manager.get_stats() if self.enable_proxy else {}
        
        # 添加重试相关统计
        retry_stats = {
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'max_retry_delay': self.max_retry_delay,
            'retry_codes': list(self.retry_codes)
        }
        
        return {
            'name': self.name,
            'is_running': self.is_running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': duration,
            'total_pages': self.total_pages,
            'successful_pages': self.successful_pages,
            'failed_pages': self.failed_pages,
            'success_rate': round(self.successful_pages / self.total_pages * 100, 2) if self.total_pages > 0 else 0,
            'mode': self.config.get_mode().value,
            'proxy_enabled': self.enable_proxy and self.proxy_config.get('enabled', False),
            'proxy_usage_count': self.proxy_usage_count,
            'proxy_stats': proxy_stats,
            'retry_stats': retry_stats
        }
    
    def get_session_info(self) -> Dict:
        """获取会话信息"""
        info = {
            'name': self.name,
            'running': self.is_running,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else None,
            'end_time': self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else None,
            'total_pages': self.total_pages,
            'successful_pages': self.successful_pages,
            'failed_pages': self.failed_pages,
            'proxy_usage_count': self.proxy_usage_count,
            'proxy_enabled': self.enable_proxy,
            'current_proxy': f"{self.current_proxy.ip}:{self.current_proxy.port}" if self.current_proxy else None
        }
        return info
    
    def print_status(self) -> None:
        """打印状态信息"""
        stats = self.get_crawling_stats()
        print(f"\n=== {self.name} 状态 ===")
        print(f"运行状态: {'运行中' if stats['is_running'] else '已停止'}")
        print(f"总页面数: {stats['total_pages']}")
        print(f"成功页面: {stats['successful_pages']}")
        print(f"失败页面: {stats['failed_pages']}")
        print(f"成功率: {stats['success_rate']}%")
        print(f"当前模式: {stats['mode']}")
        print(f"代理状态: {'启用' if stats['proxy_enabled'] else '禁用'}")
        print(f"代理使用次数: {stats['proxy_usage_count']}")
        
        if stats['duration']:
            print(f"运行时长: {stats['duration']:.1f} 秒")
        
        # 打印代理统计
        if stats['proxy_enabled'] and 'proxy_stats' in stats:
            proxy_stats = stats['proxy_stats']
            print(f"\n代理池统计:")
            print(f"  总代理数: {proxy_stats.get('total_proxies', 0)}")
            print(f"  活跃代理数: {proxy_stats.get('active_proxies', 0)}")
            
            # 打印详细的代理信息
            if 'proxy_details' in proxy_stats:
                print("\n代理详情:")
                for proxy in proxy_stats['proxy_details']:
                    print(f"  {proxy['ip']}:{proxy['port']}")
                    print(f"    评分: {proxy['score']:.1f}")
                    print(f"    使用次数: {proxy['use_count']}")
                    print(f"    成功率: {proxy['success_rate']:.2%}")
                    print(f"    平均响应时间: {proxy['avg_response_time']:.2f}s" if proxy['avg_response_time'] else "    平均响应时间: 未知")
                    print(f"    连续失败次数: {proxy['consecutive_failures']}")
                    print(f"    存活时间: {proxy['age_seconds']:.0f}秒")
                    print(f"    最后使用: {proxy['last_used'] or '未使用'}")
                    print("")
        
        # 打印重试配置
        retry_stats = stats.get('retry_stats', {})
        print("\n重试配置:")
        print(f"  最大重试次数: {retry_stats.get('max_retries')}")
        print(f"  初始重试延迟: {retry_stats.get('retry_delay')}秒")
        print(f"  最大重试延迟: {retry_stats.get('max_retry_delay')}秒")
        print(f"  重试状态码: {', '.join(map(str, retry_stats.get('retry_codes', [])))}")
        
        # 打印请求管理器状态
        self.request_manager.print_status()
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.total_pages = 0
        self.successful_pages = 0
        self.failed_pages = 0
        self.proxy_usage_count = 0
        self.start_time = None
        self.end_time = None
        self.logger.info("统计信息已重置")
    
    def crawl_page(self, url: str, use_proxy: bool = True, **kwargs) -> Tuple[requests.Response, Dict]:
        """爬取单个页面（子类可重写）"""
        return self.get_page(url, use_proxy=use_proxy, **kwargs)
    
    def crawl_pages(self, urls: List[str], use_proxy: bool = True, **kwargs) -> List[Tuple[requests.Response, Dict]]:
        """爬取多个页面"""
        results = []
        
        for i, url in enumerate(urls):
            if not self.is_running:
                self.logger.info("爬取已停止")
                break
            
            try:
                start_time = time.time()
                response, info = self.get_page(url, use_proxy=use_proxy, **kwargs)
                response_time = time.time() - start_time
                
                # 记录重试信息
                retry_count = info.get('retry_count', 0)
                if retry_count > 0:
                    self.logger.info(f"页面 {url} 经过 {retry_count} 次重试后成功获取")
                
                self.record_page_result(url, True, response_time)
                results.append((response, info))
                
                # 添加延迟
                if i < len(urls) - 1:  # 不是最后一个
                    delay = self.config.get_config('request_delay.min')
                    time.sleep(delay)
                    
            except Exception as e:
                self.record_page_result(url, False)
                self.logger.error(f"爬取页面失败: {url}, 错误: {e}")
                results.append((None, {'error': str(e), 'retry_count': info.get('retry_count', 0)}))
        
        return results
    
    def parse_page(self, response: requests.Response) -> Dict:
        """解析页面（子类必须实现）"""
        raise NotImplementedError("子类必须实现parse_page方法")
    
    def save_data(self, data: Dict) -> bool:
        """保存数据（子类可重写）"""
        # 默认实现：打印数据
        print(f"数据: {data}")
        return True
    
    def run(self, urls: List[str], use_proxy: bool = True) -> List[Dict]:
        """运行爬虫"""
        self.start_crawling()
        results = []
        
        try:
            for url in urls:
                if not self.is_running:
                    break
                
                try:
                    response, info = self.crawl_page(url, use_proxy=use_proxy)
                    data = self.parse_page(response)
                    if data:
                        self.save_data(data)
                        results.append(data)
                except Exception as e:
                    self.logger.error(f"处理页面失败: {url}, 错误: {e}")
                    
        finally:
            self.stop_crawling()
        
        return results 