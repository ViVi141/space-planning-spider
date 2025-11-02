#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强的基础爬虫类
集成持久化代理管理器和爬取进度保存功能
"""

import time
import json
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import requests
from urllib.parse import urljoin, urlparse

from .smart_request_manager import smart_request_manager
from .config import crawler_config, AntiDetectionMode
from .persistent_proxy_manager import persistent_proxy_manager

class CrawlProgress:
    """爬取进度管理类"""
    
    def __init__(self, crawler_name: str):
        self.crawler_name = crawler_name
        self.progress_file = os.path.join(
            os.path.dirname(__file__), 
            f'crawl_progress_{crawler_name}.json'
        )
        self.progress_data = self._load_progress()
    
    def _load_progress(self) -> Dict:
        """加载进度数据"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"加载进度文件失败: {e}")
        
        return {
            'last_page': 0,
            'total_pages': 0,
            'completed_urls': [],
            'failed_urls': [],
            'last_update': None,
            'search_params': {}
        }
    
    def save_progress(self):
        """保存进度数据"""
        try:
            self.progress_data['last_update'] = datetime.now().isoformat()
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存进度文件失败: {e}")
    
    def update_page_progress(self, current_page: int, total_pages: Optional[int] = None):
        """更新页面进度"""
        self.progress_data['last_page'] = current_page
        if total_pages is not None:
            self.progress_data['total_pages'] = total_pages
        self.save_progress()
    
    def add_completed_url(self, url: str):
        """添加已完成的URL"""
        if url not in self.progress_data['completed_urls']:
            self.progress_data['completed_urls'].append(url)
            self.save_progress()
    
    def add_failed_url(self, url: str):
        """添加失败的URL"""
        if url not in self.progress_data['failed_urls']:
            self.progress_data['failed_urls'].append(url)
            self.save_progress()
    
    def is_url_completed(self, url: str) -> bool:
        """检查URL是否已完成"""
        return url in self.progress_data['completed_urls']
    
    def get_resume_page(self) -> int:
        """获取恢复爬取的页面"""
        return self.progress_data.get('last_page', 0)
    
    def set_search_params(self, params: Dict):
        """设置搜索参数"""
        self.progress_data['search_params'] = params
        self.save_progress()
    
    def get_search_params(self) -> Dict:
        """获取搜索参数"""
        return self.progress_data.get('search_params', {})
    
    def clear_progress(self):
        """清除进度数据"""
        self.progress_data = {
            'last_page': 0,
            'total_pages': 0,
            'completed_urls': [],
            'failed_urls': [],
            'last_update': None,
            'search_params': {}
        }
        self.save_progress()

class EnhancedBaseCrawler:
    """增强的基础爬虫类"""
    
    def __init__(self, name: str = "EnhancedBaseCrawler", enable_proxy: bool = True):
        self.name = name
        self.logger = logging.getLogger(f"crawler.{name}")
        
        # 使用持久化代理管理器
        self.proxy_manager = persistent_proxy_manager
        self.enable_proxy = enable_proxy
        
        # 使用智能请求管理器作为备用
        self.request_manager = smart_request_manager
        
        # 爬取进度管理
        self.progress = CrawlProgress(name)
        
        # 爬虫状态
        self.is_running = False
        self.start_time = None
        self.end_time = None
        
        # 统计信息
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.proxy_switches = 0
        
        # 配置
        self.config = crawler_config
        
        # 当前代理状态
        self.current_proxy_info = None
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 2
        self.retry_backoff = 2.0
        
        self.logger.info(f"初始化增强爬虫: {name}, 代理启用: {enable_proxy}")
    
    def set_mode(self, mode: AntiDetectionMode) -> None:
        """设置防检测模式"""
        self.request_manager.switch_mode(mode)
        self.logger.info(f"切换到{mode.value}模式")
    
    def _get_proxy_for_request(self) -> Optional[Dict[str, str]]:
        """获取用于请求的代理"""
        if not self.enable_proxy:
            return None
        
        proxy_info = self.proxy_manager.get_proxy()
        if proxy_info:
            # 检查proxy_info的类型
            if hasattr(proxy_info, 'ip') and hasattr(proxy_info, 'port'):
                # 这是ProxyInfo对象
                proxy_dict = {
                    'http': f'http://{proxy_info.ip}:{proxy_info.port}',
                    'https': f'http://{proxy_info.ip}:{proxy_info.port}'
                }
            elif isinstance(proxy_info, dict):
                # 检查是否是标准的requests代理字典格式（已经包含 'http' 和/或 'https' 键）
                if 'http' in proxy_info or 'https' in proxy_info:
                    # 这是标准的requests代理格式，直接使用
                    proxy_dict = proxy_info.copy()
                    # 如果只有http或只有https，补充另一个
                    if 'http' in proxy_dict and 'https' not in proxy_dict:
                        proxy_dict['https'] = proxy_dict['http']
                    elif 'https' in proxy_dict and 'http' not in proxy_dict:
                        proxy_dict['http'] = proxy_dict['https']
                    self.logger.debug(f"使用标准代理字典格式: {proxy_dict}")
                elif 'ip' in proxy_info and 'port' in proxy_info:
                    # 这是包含ip和port的字典，需要转换
                    proxy_dict = {
                        'http': f'http://{proxy_info["ip"]}:{proxy_info["port"]}',
                        'https': f'http://{proxy_info["ip"]}:{proxy_info["port"]}'
                    }
                    self.logger.debug(f"从ip:port格式转换代理: {proxy_dict}")
                else:
                    self.logger.warning(f"代理信息格式错误（缺少http/https或ip/port）: {proxy_info}")
                    return None
            else:
                self.logger.warning(f"不支持的代理信息类型: {type(proxy_info)}")
                return None
            
            # 更新当前代理信息
            proxy_status = self.proxy_manager.get_status()
            self.current_proxy_info = proxy_status.get('current_proxy')
            
            # 如果是新代理，记录切换
            if self.current_proxy_info:
                current_ip = self.current_proxy_info['ip']
                if not hasattr(self, '_last_proxy_ip') or self._last_proxy_ip != current_ip:
                    self.proxy_switches += 1
                    self._last_proxy_ip = current_ip
                    self.logger.info(f"切换到代理: {current_ip}:{self.current_proxy_info['port']}")
            
            return proxy_dict
        
        return None
    
    def _make_request(self, url: str, method: str = 'GET', headers: Optional[Dict] = None, 
                     data: Optional[Dict] = None, timeout: int = 30) -> Tuple[Optional[requests.Response], Dict]:
        """发送HTTP请求"""
        request_info = {
            'url': url,
            'method': method,
            'proxy_used': False,
            'proxy_ip': None,
            'response_time': 0,
            'retry_count': 0,
            'success': False
        }
        
        start_time = time.time()
        
        for attempt in range(self.max_retries + 1):
            try:
                # 获取代理
                proxy_dict = self._get_proxy_for_request()
                if proxy_dict:
                    request_info['proxy_used'] = True
                    request_info['proxy_ip'] = self.current_proxy_info['ip'] if self.current_proxy_info else None
                
                # 发送请求
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=data,
                    proxies=proxy_dict,
                    timeout=timeout,
                    verify=True
                )
                
                request_info['response_time'] = time.time() - start_time
                request_info['retry_count'] = attempt
                
                # 检查响应状态
                if response.status_code == 200:
                    request_info['success'] = True
                    self.successful_requests += 1
                    
                    # 报告代理使用成功
                    if proxy_dict:
                        try:
                            # PersistentProxyManager.report_result() 只需要 success 和 response_time 两个参数
                            self.proxy_manager.report_result(True, request_info['response_time'])
                        except Exception as report_error:
                            self.logger.debug(f"报告代理结果失败: {report_error}")
                    
                    self.logger.debug(f"请求成功: {url} (耗时: {request_info['response_time']:.2f}s)")
                    return response, request_info
                
                elif response.status_code in [403, 429, 500, 502, 503, 504]:
                    # 这些状态码可能需要重试
                    error_msg = f"HTTP {response.status_code}"
                    if response.status_code == 500:
                        error_msg += " (服务器内部错误)"
                    elif response.status_code == 403:
                        error_msg += " (访问被拒绝)"
                    elif response.status_code == 429:
                        error_msg += " (请求过于频繁)"
                    
                    self.logger.warning(f"请求返回错误状态码: {url} - {error_msg}")
                    raise requests.exceptions.HTTPError(error_msg)
                
                else:
                    # 其他状态码直接返回
                    request_info['success'] = True
                    self.successful_requests += 1
                    return response, request_info
                    
            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries + 1}): {url}, 错误: {e}")
                
                # 报告代理使用失败
                if proxy_dict:
                    try:
                        # PersistentProxyManager.report_result() 接受 success, response_time 和可选的 error_msg
                        self.proxy_manager.report_result(False, time.time() - start_time, error_msg)
                    except Exception as report_error:
                        self.logger.debug(f"报告代理结果失败: {report_error}")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < self.max_retries:
                    delay = self.retry_delay * (self.retry_backoff ** attempt)
                    self.logger.info(f"等待 {delay:.1f} 秒后重试...")
                    time.sleep(delay)
                else:
                    # 最后一次尝试失败
                    self.failed_requests += 1
                    request_info['retry_count'] = attempt
                    self.logger.error(f"请求最终失败: {url}")
                    return None, request_info
        
        return None, request_info
    
    def get_page(self, url: str, headers: Optional[Dict] = None) -> Tuple[Optional[requests.Response], Dict]:
        """获取页面"""
        self.total_requests += 1
        return self._make_request(url, 'GET', headers)
    
    def post_page(self, url: str, data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Tuple[Optional[requests.Response], Dict]:
        """POST请求"""
        self.total_requests += 1
        return self._make_request(url, 'POST', headers, data)
    
    def start_crawling(self, search_params: Optional[Dict] = None) -> None:
        """开始爬取"""
        self.is_running = True
        self.start_time = datetime.now()
        
        # 保存搜索参数
        if search_params:
            self.progress.set_search_params(search_params)
        
        self.logger.info(f"开始爬取: {self.name}")
        
        # 输出当前代理状态
        proxy_status = self.proxy_manager.get_status()
        self.logger.info(f"代理状态: {proxy_status}")
        
        if proxy_status['enabled'] and proxy_status['current_proxy']:
            proxy_info = proxy_status['current_proxy']
            self.logger.info(f"当前代理: {proxy_info['ip']}:{proxy_info['port']} "
                           f"(使用次数: {proxy_info['use_count']}, 成功率: {proxy_info['success_rate']:.2%})")
        elif proxy_status['enabled']:
            self.logger.info("代理已启用但无可用代理，正在获取...")
        else:
            self.logger.info("代理已禁用，使用直接连接")
    
    def stop_crawling(self) -> None:
        """停止爬取"""
        self.is_running = False
        self.end_time = datetime.now()
        
        # 保存最终进度
        self.progress.save_progress()
        
        self.logger.info(f"停止爬取: {self.name}")
        self._print_statistics()
    
    def _print_statistics(self):
        """打印统计信息"""
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            self.logger.info(f"爬取统计:")
            self.logger.info(f"  总耗时: {duration:.1f}秒")
            self.logger.info(f"  总请求数: {self.total_requests}")
            self.logger.info(f"  成功请求: {self.successful_requests}")
            self.logger.info(f"  失败请求: {self.failed_requests}")
            self.logger.info(f"  成功率: {self.successful_requests/self.total_requests:.2%}" if self.total_requests > 0 else "  成功率: 0%")
            self.logger.info(f"  代理切换次数: {self.proxy_switches}")
            
            if self.total_requests > 0:
                self.logger.info(f"  平均请求速度: {self.total_requests/duration:.2f} 请求/秒")
    
    def get_resume_page(self) -> int:
        """获取恢复爬取的页面"""
        return self.progress.get_resume_page()
    
    def update_progress(self, current_page: int, total_pages: Optional[int] = None):
        """更新爬取进度"""
        self.progress.update_page_progress(current_page, total_pages)
        
        if total_pages:
            progress_percent = (current_page / total_pages) * 100
            self.logger.info(f"爬取进度: {current_page}/{total_pages} ({progress_percent:.1f}%)")
    
    def mark_url_completed(self, url: str):
        """标记URL为已完成"""
        self.progress.add_completed_url(url)
    
    def mark_url_failed(self, url: str):
        """标记URL为失败"""
        self.progress.add_failed_url(url)
    
    def is_url_completed(self, url: str) -> bool:
        """检查URL是否已完成"""
        return self.progress.is_url_completed(url)
    
    def clear_progress(self):
        """清除爬取进度"""
        self.progress.clear_progress()
        self.logger.info("已清除爬取进度")
    
    def force_refresh_proxy(self):
        """强制刷新代理"""
        if self.enable_proxy:
            self.proxy_manager.force_refresh()
            self.logger.info("已强制刷新代理")
    
    def get_crawling_stats(self) -> Dict:
        """获取爬取统计信息"""
        duration = None
        if self.start_time:
            end_time = self.end_time or datetime.now()
            duration = (end_time - self.start_time).total_seconds()
        
        proxy_status = self.proxy_manager.get_status()
        
        return {
            'crawler_name': self.name,
            'is_running': self.is_running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': duration,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
            'proxy_switches': self.proxy_switches,
            'proxy_status': proxy_status,
            'progress': {
                'last_page': self.progress.get_resume_page(),
                'total_pages': self.progress.progress_data.get('total_pages', 0),
                'completed_urls_count': len(self.progress.progress_data.get('completed_urls', [])),
                'failed_urls_count': len(self.progress.progress_data.get('failed_urls', []))
            }
        } 