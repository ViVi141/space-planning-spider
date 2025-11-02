#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国家住建部多线程爬虫
基于MultiThreadBaseCrawler实现多线程爬取
"""

import requests
from datetime import datetime, timedelta
import time
import random
from typing import List, Dict, Optional, Callable
from bs4 import BeautifulSoup
import logging
import threading

from .multithread_base_crawler import MultiThreadBaseCrawler
from .anti_crawler import AntiCrawlerManager
from .monitor import CrawlerMonitor
from .spider_config import SpiderConfig

logger = logging.getLogger(__name__)


class NationalMultiThreadSpider(MultiThreadBaseCrawler):
    """国家住建部多线程爬虫"""
    
    def __init__(self, max_workers=4, enable_proxy=True):
        super().__init__(max_workers, enable_proxy)
        
        # 从配置获取参数
        config = SpiderConfig.get_national_config()
        
        self.api_url = config['api_url']
        self.level = config['level']
        self.base_url = config['base_url']
        self.base_params = config['base_params'].copy()
        
        # 初始化防反爬虫管理器
        self.anti_crawler = AntiCrawlerManager()
        self.monitor = CrawlerMonitor()
        
        # 初始化代理管理器 - 使用proxy_pool.py中的ProxyManager
        if enable_proxy:
            try:
                from .proxy_pool import ProxyManager, initialize_proxy_pool
                import os
                
                # 初始化代理池
                config_file = os.path.join(os.path.dirname(__file__), '..', 'gui', 'proxy_config.json')
                if os.path.exists(config_file):
                    initialize_proxy_pool(config_file)
                    self.proxy_manager = ProxyManager()
                    logger.info("多线程爬虫使用proxy_pool代理管理器")
                else:
                    logger.warning("代理配置文件不存在，禁用代理")
                    self.proxy_manager = None
            except Exception as e:
                logger.error(f"初始化代理管理器失败: {e}")
                self.proxy_manager = None
        else:
            self.proxy_manager = None
        
        # 设置特定的请求头（住建部网站需要）
        self.special_headers = config['headers'].copy()
        self.special_headers.update({
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-KL-SaaS-Ajax-Request': 'Ajax_Request',
            'X-Requested-With': 'XMLHttpRequest'
        })
        
        logger.info(f"初始化国家住建部多线程爬虫，线程数: {max_workers}, 代理启用: {enable_proxy}")
    
    def _prepare_tasks(self) -> List[Dict]:
        """准备任务列表 - 按时间区间分割任务（保持多线程效率）"""
        tasks = []
        
        # 获取用户指定的时间范围
        user_start_date = getattr(self, 'user_start_date', None)
        user_end_date = getattr(self, 'user_end_date', None)
        
        if user_start_date and user_end_date:
            # 使用用户指定的时间范围
            start_date = datetime.strptime(user_start_date, '%Y-%m-%d')
            end_date = datetime.strptime(user_end_date, '%Y-%m-%d')
            logger.info(f"使用用户指定的时间范围: {user_start_date} 至 {user_end_date}")
        else:
            # 取消时间限制时，设置一个很大的时间范围，确保爬取所有数据
            start_date = datetime(1990, 1, 1)  # 设置很早的开始时间
            end_date = datetime.now()
            logger.info(f"取消时间限制，爬取所有可用数据")
        
        # 按月分割任务（保持多线程效率）
        current_date = start_date
        task_id = 0
        
        while current_date <= end_date:
            # 计算当月结束日期
            if current_date.month == 12:
                next_month = datetime(current_date.year + 1, 1, 1)
            else:
                next_month = datetime(current_date.year, current_date.month + 1, 1)
            
            month_end = next_month - timedelta(days=1)
            
            # 确保不超过结束日期
            if month_end > end_date:
                month_end = end_date
            
            task_data = {
                'task_id': f"national_{task_id:04d}",
                'start_date': current_date.strftime('%Y-%m-%d'),
                'end_date': month_end.strftime('%Y-%m-%d'),
                'year': current_date.year,
                'month': current_date.month,
                'description': f"{current_date.year}年{current_date.month}月"
            }
            
            tasks.append(task_data)
            task_id += 1
            current_date = next_month
        
        logger.info(f"准备完成，共 {len(tasks)} 个时间区间任务")
        return tasks
    
    def _execute_task(self, task_data: Dict, session, lock, callback: Optional[Callable] = None) -> List[Dict]:
        """执行具体任务 - 完全按照单线程爬虫逻辑"""
        task_id = task_data['task_id']
        start_date = task_data['start_date']
        end_date = task_data['end_date']
        description = task_data['description']
        
        thread_name = threading.current_thread().name
        
        if callback:
            callback(f"线程 {thread_name} 开始处理 {description}")
        
        policies = []
        
        # 从通用配置获取参数
        common_config = SpiderConfig.get_common_config()
        page_size = common_config['page_size']
        page_no = 1  # 每个任务从第1页开始
        max_pages = 50  # 每个任务最多爬取50页
        max_consecutive_out_of_range = common_config['max_consecutive_out_of_range']
        
        # 设置速度模式
        speed_mode = getattr(self, 'speed_mode', '正常速度')
        if speed_mode == "快速模式":
            self.anti_crawler.min_delay = 0.1
            self.anti_crawler.max_delay = 0.3
        elif speed_mode == "慢速模式":
            self.anti_crawler.min_delay = 2.0
            self.anti_crawler.max_delay = 5.0
        else:  # 正常速度
            self.anti_crawler.min_delay = 0.2
            self.anti_crawler.max_delay = 0.8
        
        # 完全按照单线程爬虫的时间处理逻辑
        dt_start = datetime.strptime(start_date, '%Y-%m-%d')
        dt_end = datetime.strptime(end_date, '%Y-%m-%d')
        in_target_range = False  # 是否已进入目标时间区间
        consecutive_out_of_range = 0  # 连续超出范围的页数
        
        # 检查代理状态
        if self.enable_proxy and hasattr(self, 'proxy_manager') and self.proxy_manager:
            try:
                # 尝试获取代理信息
                proxy_info = self.proxy_manager.get_proxy()
                if proxy_info:
                    logger.info(f"线程 {thread_name} 代理可用")
                else:
                    logger.warning(f"线程 {thread_name} 无法获取代理")
            except Exception as e:
                logger.warning(f"线程 {thread_name} 代理检查失败: {e}")
        else:
            logger.info(f"线程 {thread_name} 代理已禁用")
        
        while page_no <= max_pages:
            try:
                # 检查是否需要停止
                if hasattr(self, 'check_stop') and self.check_stop():
                    logger.info(f"线程 {thread_name} 检测到停止信号，退出任务")
                    if callback:
                        callback(f"线程 {thread_name} 已停止")
                    break
                
                # 构建请求参数
                params = self.base_params.copy()
                params.update({
                    'pageNo': str(page_no),
                    'pageSize': str(page_size)
                })
                
                # 添加特殊请求头
                headers = self.special_headers.copy()
                
                # 使用线程专用会话发送请求
                with lock:
                    # 应用防反爬虫延迟
                    time.sleep(random.uniform(self.anti_crawler.min_delay, self.anti_crawler.max_delay))
                    
                    response = session.get(
                        self.api_url,
                        params=params,
                        headers=headers,
                        timeout=30
                    )
                
                # 记录请求
                self.monitor.record_request(self.api_url, response.status_code == 200)
                
                if response.status_code != 200:
                    logger.warning(f"线程 {thread_name} 第{page_no}页请求失败，状态码: {response.status_code}")
                    # 尝试轮换代理
                    if self.enable_proxy and hasattr(self, '_rotate_thread_proxy'):
                        if self._rotate_thread_proxy():
                            logger.info(f"线程 {thread_name} 轮换代理后重试")
                            continue
                    break
                
                # 解析响应数据
                try:
                    data = response.json()
                except Exception as e:
                    logger.error(f"线程 {thread_name} 解析JSON失败: {e}")
                    break
                
                # 检查是否有数据
                html_content = data.get('data', {}).get('html', '')
                if not html_content:
                    logger.info(f"线程 {thread_name} 第{page_no}页无HTML内容")
                    break
                
                # 解析HTML内容
                from bs4 import BeautifulSoup, Tag
                soup = BeautifulSoup(html_content, 'html.parser')
                table = soup.find('table')
                if not isinstance(table, Tag):
                    logger.info(f"线程 {thread_name} 第{page_no}页未找到表格")
                    break
                
                tbody = table.find('tbody')
                if not isinstance(tbody, Tag):
                    logger.info(f"线程 {thread_name} 第{page_no}页未找到tbody")
                    break
                
                rows = tbody.find_all('tr')
                logger.info(f"线程 {thread_name} 第{page_no}页找到 {len(rows)} 条政策")
                
                page_policies = []
                page_dates = []  # 记录当前页的日期范围
                
                for row in rows:
                    try:
                        # 检查是否需要停止
                        if hasattr(self, 'check_stop') and self.check_stop():
                            logger.info(f"线程 {thread_name} 检测到停止信号，退出政策处理")
                            if callback:
                                callback(f"线程 {thread_name} 已停止")
                            break
                        
                        if not isinstance(row, Tag):
                            continue
                        cells = row.find_all('td')
                        if len(cells) >= 4:
                            cells_list = list(cells)
                            title_cell = cells_list[1] if len(cells_list) > 1 else None
                            title_link = None
                            if isinstance(title_cell, Tag):
                                title_link = title_cell.find('a')
                            
                            if isinstance(title_link, Tag):
                                title = title_link.get('title', '') or title_link.get_text(strip=True)
                                url = str(title_link.get('href', ''))
                            else:
                                title = ''
                                url = ''
                            
                            doc_number = cells_list[2].get_text(strip=True) if len(cells_list) > 2 and isinstance(cells_list[2], Tag) else ''
                            pub_date = cells_list[3].get_text(strip=True) if len(cells_list) > 3 and isinstance(cells_list[3], Tag) else ''
                            
                            if url and not str(url).startswith('http'):
                                url = self.base_url + str(url)
                            
                            # 解析日期
                            try:
                                dt_pub = datetime.strptime(pub_date, '%Y-%m-%d')
                                page_dates.append(dt_pub)
                            except Exception:
                                # 如果日期解析失败，跳过该政策
                                continue
                            
                            # 时间区间过滤（与原始爬虫完全一致）
                            # 检查是否取消时间限制
                            user_start_date = getattr(self, 'user_start_date', None)
                            user_end_date = getattr(self, 'user_end_date', None)
                            
                            # 只有当用户指定了时间范围时才进行过滤
                            if user_start_date and user_end_date:
                                if dt_start and dt_pub < dt_start:
                                    continue
                                if dt_end and dt_pub > dt_end:
                                    continue
                            
                            # 创建政策数据
                            policy = {
                                'level': self.level,
                                'title': title,
                                'pub_date': pub_date,
                                'doc_number': doc_number,
                                'source': url,
                                'content': '',  # 暂时为空，可以后续获取
                                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            
                            page_policies.append(policy)
                            
                    except Exception as e:
                        logger.error(f"线程 {thread_name} 解析政策行失败: {e}")
                        continue
                
                policies.extend(page_policies)
                
                # 如果在政策处理循环中被停止，跳出外层循环
                if hasattr(self, 'check_stop') and self.check_stop():
                    break
                
                # 时间区间状态检查（与原始爬虫完全一致）
                # 只有当用户指定了时间范围时才进行状态检查
                user_start_date = getattr(self, 'user_start_date', None)
                user_end_date = getattr(self, 'user_end_date', None)
                
                if user_start_date and user_end_date and dt_start and dt_end and page_dates:
                    min_date = min(page_dates)
                    max_date = max(page_dates)
                    
                    # 检查是否进入目标时间区间
                    if not in_target_range and min_date <= dt_end and max_date >= dt_start:
                        in_target_range = True
                        consecutive_out_of_range = 0
                        logger.info(f"线程 {thread_name} 第{page_no}页：进入目标时间区间 [{start_date} - {end_date}]")
                    
                    # 检查是否完全脱离目标时间区间
                    elif in_target_range and (max_date < dt_start or min_date > dt_end):
                        consecutive_out_of_range += 1
                        logger.info(f"线程 {thread_name} 第{page_no}页：脱离目标时间区间，连续 {consecutive_out_of_range} 页")
                        
                        # 如果连续多页都脱离范围，停止检索
                        if consecutive_out_of_range >= max_consecutive_out_of_range:
                            logger.info(f"线程 {thread_name} 连续 {max_consecutive_out_of_range} 页脱离目标时间区间，停止检索")
                            break
                    else:
                        consecutive_out_of_range = 0
                
                # 更新进度
                if callback:
                    callback(f"线程 {thread_name} {description} 第{page_no}页: 获取{len(rows)}条，范围内{len(page_policies)}条")
                
                page_no += 1
                
            except Exception as e:
                logger.error(f"线程 {thread_name} 第{page_no}页处理失败: {e}")
                break
        
        logger.info(f"线程 {thread_name} {description} 完成，共获取 {len(policies)} 条政策")
        if callback:
            callback(f"线程 {thread_name} {description} 完成，共获取 {len(policies)} 条政策")
        
        return policies
    
    def _parse_policy_item(self, item: Dict) -> Optional[Dict]:
        """解析单个政策项"""
        try:
            title = item.get('title', '').strip()
            if not title:
                return None
            
            # 解析发布日期
            pub_date_str = item.get('pub_date', '')
            if pub_date_str:
                try:
                    # 尝试解析日期格式
                    pub_date = datetime.strptime(pub_date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
                except Exception:
                    pub_date = ''
            else:
                pub_date = ''
            
            # 解析来源
            source = item.get('source', '').strip()
            
            # 解析内容
            content = item.get('content', '').strip()
            
            # 解析链接
            url = item.get('url', '')
            if url and not url.startswith('http'):
                url = f"{self.base_url}{url}"
            
            return {
                'level': self.level,
                'title': title or '',
                'pub_date': pub_date or '',
                'source': source or url or '',  # 主要字段：source，优先使用source，否则使用url
                'url': url or source or '',  # 兼容字段
                'link': url or source or '',  # 兼容字段
                'content': content or '',
                'category': '',  # 添加category字段（住建部没有分类）
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logger.error(f"解析政策项失败: {e}")
            return None
    
    def _is_policy_in_date_range(self, policy: Dict, dt_start: datetime, dt_end: datetime) -> bool:
        """检查政策是否在指定时间范围内（与原始爬虫保持一致）"""
        # 如果没有指定时间范围（取消时间限制），则接受所有政策
        if dt_start is None or dt_end is None:
            return True
        
        pub_date_str = policy.get('pub_date', '')
        if not pub_date_str:
            return True  # 如果没有日期，默认包含
        
        try:
            policy_date = datetime.strptime(pub_date_str, '%Y-%m-%d')
            return dt_start <= policy_date <= dt_end
        except Exception:
            return False  # 日期解析失败，不包含
    
    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None, 
                      speed_mode="正常速度", disable_speed_limit=False, stop_callback=None):
        """兼容原有接口的多线程爬取方法"""
        self.speed_mode = speed_mode
        
        # 保存用户指定的时间范围
        if start_date and end_date:
            self.user_start_date = start_date
            self.user_end_date = end_date
            logger.info(f"设置用户时间范围: {start_date} 至 {end_date}")
        else:
            self.user_start_date = None
            self.user_end_date = None
            logger.info("未指定时间范围，使用默认范围")
        
        return self.crawl_multithread(callback, stop_callback)
    
    def crawl_policies_multithread(self, keywords=None, callback=None, start_date=None, end_date=None, 
                                  speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, max_workers=None):
        """多线程爬取政策（兼容广东省爬虫接口）"""
        self.speed_mode = speed_mode
        
        # 保存用户指定的时间范围
        if start_date and end_date:
            self.user_start_date = start_date
            self.user_end_date = end_date
            logger.info(f"设置用户时间范围: {start_date} 至 {end_date}")
        else:
            self.user_start_date = None
            self.user_end_date = None
            logger.info("未指定时间范围，使用默认范围")
        
        # 使用指定的线程数或默认线程数
        if max_workers is not None:
            original_max_workers = self.max_workers
            self.max_workers = max_workers
            try:
                return self.crawl_multithread(callback, stop_callback)
            finally:
                self.max_workers = original_max_workers
        else:
            return self.crawl_multithread(callback, stop_callback)
    
    def get_crawler_status(self) -> Dict:
        """获取爬虫状态"""
        stats = self.get_multithread_stats()
        proxy_stats = self.get_proxy_stats()
        
        return {
            'level': self.level,
            'multithread_stats': stats,
            'proxy_stats': proxy_stats,
            'speed_mode': getattr(self, 'speed_mode', '正常速度'),
            'enable_proxy': self.enable_proxy
        } 