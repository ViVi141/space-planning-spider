#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础爬虫类
使用智能请求管理器和配置系统（无代理池）
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import requests

from .smart_request_manager import smart_request_manager
from .config import crawler_config, AntiDetectionMode

class BaseCrawler:
    """基础爬虫类（无代理池）"""
    
    def __init__(self, name: str = "BaseCrawler"):
        self.name = name
        self.logger = logging.getLogger(f"crawler.{name}")
        
        # 使用智能请求管理器
        self.request_manager = smart_request_manager
        
        # 爬虫状态
        self.is_running = False
        self.start_time = None
        self.end_time = None
        
        # 统计信息
        self.total_pages = 0
        self.successful_pages = 0
        self.failed_pages = 0
        
        # 配置
        self.config = crawler_config
    
    def set_mode(self, mode: AntiDetectionMode) -> None:
        """设置防检测模式"""
        self.request_manager.switch_mode(mode)
        self.logger.info(f"切换到{mode.value}模式")
    
    def get_page(self, url: str, headers: Optional[Dict] = None) -> Tuple[requests.Response, Dict]:
        """获取页面"""
        try:
            response, info = self.request_manager.get_page(url, headers)
            self.logger.info(f"成功获取页面: {url}")
            return response, info
        except Exception as e:
            self.logger.error(f"获取页面失败: {url}, 错误: {e}")
            raise
    
    def get_page_with_behavior(self, url: str, behavior_type: Optional[str] = None) -> Tuple[requests.Response, Dict]:
        """获取页面并模拟行为"""
        try:
            response, info = self.request_manager.get_page_with_behavior(url, behavior_type)
            self.logger.info(f"成功获取页面(行为模拟): {url}")
            return response, info
        except Exception as e:
            self.logger.error(f"获取页面失败: {url}, 错误: {e}")
            raise
    
    def get_page_with_js_injection(self, url: str, js_code: Optional[str] = None) -> Tuple[requests.Response, Dict]:
        """获取页面并注入JavaScript"""
        try:
            response, info = self.request_manager.get_page_with_js_injection(url, js_code)
            self.logger.info(f"成功获取页面(JS注入): {url}")
            return response, info
        except Exception as e:
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
            'proxy_enabled': False
        }
    
    def get_session_info(self) -> Dict:
        """获取会话信息"""
        return self.request_manager.get_session_info()
    
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
        print(f"代理状态: 禁用")
        
        if stats['duration']:
            print(f"运行时长: {stats['duration']:.1f} 秒")
        
        # 打印请求管理器状态
        self.request_manager.print_status()
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.total_pages = 0
        self.successful_pages = 0
        self.failed_pages = 0
        self.start_time = None
        self.end_time = None
        self.logger.info("统计信息已重置")
    
    def crawl_page(self, url: str, **kwargs) -> Tuple[requests.Response, Dict]:
        """爬取单个页面（子类可重写）"""
        return self.get_page(url, **kwargs)
    
    def crawl_pages(self, urls: List[str], **kwargs) -> List[Tuple[requests.Response, Dict]]:
        """爬取多个页面"""
        results = []
        
        for i, url in enumerate(urls):
            if not self.is_running:
                self.logger.info("爬取已停止")
                break
            
            try:
                start_time = time.time()
                response, info = self.crawl_page(url, **kwargs)
                response_time = time.time() - start_time
                
                self.record_page_result(url, True, response_time)
                results.append((response, info))
                
                # 添加延迟
                if i < len(urls) - 1:  # 不是最后一个
                    delay = self.config.get_config('request_delay.min')
                    time.sleep(delay)
                    
            except Exception as e:
                self.record_page_result(url, False)
                self.logger.error(f"爬取页面失败: {url}, 错误: {e}")
                results.append((None, {'error': str(e)}))
        
        return results
    
    def parse_page(self, response: requests.Response) -> Dict:
        """解析页面（子类必须实现）"""
        raise NotImplementedError("子类必须实现parse_page方法")
    
    def save_data(self, data: Dict) -> bool:
        """保存数据（子类可重写）"""
        # 默认实现：打印数据
        print(f"数据: {data}")
        return True
    
    def run(self, urls: List[str]) -> List[Dict]:
        """运行爬虫"""
        self.start_crawling()
        results = []
        
        try:
            for url in urls:
                if not self.is_running:
                    break
                
                try:
                    response, info = self.crawl_page(url)
                    data = self.parse_page(response)
                    
                    if self.save_data(data):
                        results.append(data)
                    
                except Exception as e:
                    self.logger.error(f"处理页面失败: {url}, 错误: {e}")
                    
        finally:
            self.stop_crawling()
        
        return results 