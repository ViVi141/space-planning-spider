#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自然资源部多线程爬虫
"""

import threading
import queue
import time
import random
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

from .multithread_base_crawler import MultiThreadBaseCrawler
from .monitor import CrawlerMonitor
from .anti_crawler import AntiCrawlerManager
from .spider_config import SpiderConfig

logger = logging.getLogger(__name__)


class MNRMultiThreadSpider(MultiThreadBaseCrawler):
    """自然资源部多线程爬虫"""
    
    def __init__(self, max_workers=4, enable_proxy=True):
        super().__init__(max_workers, enable_proxy)
        
        # 从配置获取参数
        config = SpiderConfig.get_mnr_config()
        
        self.base_url = config['base_url']
        self.search_api = config['search_api']
        self.ajax_api = config['ajax_api']
        self.level = config['level']
        self.channel_id = config['channel_id']
        self.headers = config['headers'].copy()
        
        # 初始化防反爬虫管理器
        self.anti_crawler = AntiCrawlerManager()
        self.monitor = CrawlerMonitor()
        
        # 分类配置 - 更新为新的政府信息公开平台分类
        self.categories = {
            '自然资源调查监测': {'code': '1318', 'name': '自然资源调查监测'},
            '自然资源确权登记': {'code': '1319', 'name': '自然资源确权登记'},
            '自然资源合理开发利用': {'code': '1320', 'name': '自然资源合理开发利用'},
            '自然资源有偿使用': {'code': '1321', 'name': '自然资源有偿使用'},
            '国土空间规划': {'code': '1322', 'name': '国土空间规划'},
            '国土空间用途管制': {'code': '1663', 'name': '国土空间用途管制'},
            '国土空间生态修复': {'code': '1324', 'name': '国土空间生态修复'},
            '耕地保护': {'code': '1325', 'name': '耕地保护'},
            '地质勘查': {'code': '1326', 'name': '地质勘查'},
            '矿产勘查': {'code': '1327', 'name': '矿产勘查'},
            '矿产保护': {'code': '1328', 'name': '矿产保护'},
            '海洋预警监测': {'code': '1329', 'name': '海洋预警监测'},
            '海域海岛管理': {'code': '1330', 'name': '海域海岛管理'},
            '海洋预警': {'code': '1331', 'name': '海洋预警'},
            '海洋经济': {'code': '1664', 'name': '海洋经济'},
            '国家测绘': {'code': '1332', 'name': '国家测绘'},
            '地理信息管理': {'code': '1333', 'name': '地理信息管理'},
            '自然资源督察': {'code': '1334', 'name': '自然资源督察'},
            '法规': {'code': '1335', 'name': '法规'},
            '测绘管理': {'code': '1336', 'name': '测绘管理'},
            '财务管理': {'code': '1337', 'name': '财务管理'},
            '人事管理': {'code': '1662', 'name': '人事管理'},
            '矿业权评估': {'code': '1338', 'name': '矿业权评估'},
            '机构建设': {'code': '1339', 'name': '机构建设'},
            '综合管理': {'code': '1340', 'name': '综合管理'},
            '其他': {'code': '1341', 'name': '其他'}
        }
        
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
        
        logger.info(f"初始化自然资源部多线程爬虫，线程数: {max_workers}, 代理启用: {enable_proxy}")
    
    def _prepare_tasks(self) -> List[Dict]:
        """准备任务列表 - 按分类分割任务"""
        tasks = []
        task_id = 0
        
        for category_name, category_config in self.categories.items():
            task_data = {
                'task_id': f"mnr_{task_id:04d}",
                'category_name': category_name,
                'category_code': category_config['code'],
                'description': f"分类: {category_name}"
            }
            
            tasks.append(task_data)
            task_id += 1
        
        logger.info(f"准备完成，共 {len(tasks)} 个分类任务")
        return tasks
    
    def _execute_task(self, task_data: Dict, session, lock, callback: Optional[Callable] = None) -> List[Dict]:
        """执行具体任务 - 爬取指定分类的政策"""
        task_id = task_data['task_id']
        category_name = task_data['category_name']
        category_code = task_data['category_code']
        description = task_data['description']
        
        thread_name = threading.current_thread().name
        
        if callback:
            callback(f"线程 {thread_name} 开始爬取 {description}")
        
        policies = []
        page = 1
        
        # 从通用配置获取参数
        common_config = SpiderConfig.get_common_config()
        max_pages = getattr(self, 'max_pages', 100)  # 限制每个分类的最大页数
        max_consecutive_empty = common_config['max_empty_pages']
        consecutive_empty_pages = 0
        
        # 从任务数据或实例属性获取关键词
        keywords = getattr(self, 'keywords', None) or task_data.get('keywords', None)
        if keywords and isinstance(keywords, list):
            search_word = ' '.join(keywords)
        elif keywords and isinstance(keywords, str):
            search_word = keywords
        else:
            search_word = ""
        
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
        
        # 检查代理状态
        if self.enable_proxy and hasattr(self, 'proxy_manager') and self.proxy_manager:
            try:
                proxy_info = self.proxy_manager.get_proxy()
                if proxy_info:
                    logger.info(f"线程 {thread_name} 代理可用")
                else:
                    logger.warning(f"线程 {thread_name} 无法获取代理")
            except Exception as e:
                logger.warning(f"线程 {thread_name} 代理检查失败: {e}")
        else:
            logger.info(f"线程 {thread_name} 代理已禁用")
        
        while page <= max_pages:
            try:
                # 检查是否需要停止
                if hasattr(self, 'check_stop') and self.check_stop():
                    logger.info(f"线程 {thread_name} 检测到停止信号，退出任务")
                    if callback:
                        callback(f"线程 {thread_name} 已停止")
                    break
                
                if callback:
                    callback(f"线程 {thread_name} 分类[{category_name}]正在抓取第{page}页...")
                
                # 构建搜索参数
                # 注意：根据实际情况，可能服务器不支持themecat语法，暂时不使用分类搜索
                search_query = search_word
                
                params = {
                    'channelid': self.channel_id,
                    'searchword': search_query,
                    'page': page,
                    'perpage': 20,  # 每页20条
                    'searchtype': 'title',  # 搜索标题
                    'orderby': 'RELEVANCE'  # 按相关性排序
                }
                
                # 调试信息：显示搜索参数
                if callback:
                    callback(f"线程 {thread_name} 分类[{category_name}]搜索参数: {search_query}")
                
                # 使用统一请求管理器发送请求
                try:
                    with lock:
                        self.anti_crawler.sleep_between_requests(disable_speed_limit)
                        response = self.anti_crawler.make_request(
                            self.search_api,
                            method='GET',
                            params=params,
                            headers=self.headers.copy(),
                            timeout=15
                        )
                except Exception as e:
                    self.monitor.record_request(self.search_api, False)
                    logger.error(f"线程 {thread_name} 分类[{category_name}]请求失败: {e}")
                    break
                
                # 记录请求
                self.monitor.record_request(self.search_api, response.status_code == 200)
                
                if response.status_code != 200:
                    logger.warning(f"线程 {thread_name} 分类[{category_name}]第{page}页请求失败，状态码: {response.status_code}")
                    
                    # 对于特定状态码，尝试轮换代理
                    if response.status_code in [403, 429, 500, 502, 503, 504]:
                        if self.enable_proxy and hasattr(self, '_rotate_thread_proxy'):
                            if self._rotate_thread_proxy():
                                logger.info(f"线程 {thread_name} 状态码错误后轮换代理重试")
                                continue
                    
                    # 如果重试后仍然失败，跳过此页
                    break
                
                # 解析响应数据（与原始爬虫一致）
                try:
                    search_data = response.json()
                    page_policies = self._parse_json_results(search_data, callback)
                except json.JSONDecodeError:
                    # 如果不是JSON，尝试解析HTML
                    soup = BeautifulSoup(response.text, 'html.parser')
                    page_policies = self._parse_html_results(soup, callback, category_name)
                except Exception as e:
                    logger.error(f"线程 {thread_name} 分类[{category_name}]解析第{page}页失败: {e}")
                    # 如果是代理相关错误，尝试轮换代理
                    if 'ProxyError' in str(e) or '503' in str(e) or 'Tunnel connection failed' in str(e):
                        if self.enable_proxy and hasattr(self, '_rotate_thread_proxy'):
                            if self._rotate_thread_proxy():
                                logger.info(f"线程 {thread_name} 解析错误后轮换代理重试")
                                continue
                    break
                
                if not page_policies:
                    consecutive_empty_pages += 1
                    if callback:
                        callback(f"线程 {thread_name} 分类[{category_name}]第{page}页无数据")
                    
                    if consecutive_empty_pages >= max_consecutive_empty:
                        if callback:
                            callback(f"线程 {thread_name} 分类[{category_name}]连续{max_consecutive_empty}页无数据，停止爬取")
                        break
                    page += 1
                    continue
                else:
                    consecutive_empty_pages = 0  # 重置连续空页计数
                
                # 处理政策数据
                for policy in page_policies:
                    try:
                        # 检查是否需要停止
                        if hasattr(self, 'check_stop') and self.check_stop():
                            logger.info(f"线程 {thread_name} 检测到停止信号，退出政策处理")
                            if callback:
                                callback(f"线程 {thread_name} 已停止")
                            break
                        
                        # 添加分类信息
                        policy['category'] = category_name
                        
                        # 在发送实时回调之前进行去重检查
                        item_hash = self._generate_item_hash(policy)
                        if self._is_duplicate_item(item_hash):
                            # 跳过重复内容，不发送回调
                            if callback:
                                callback(f"跳过重复内容政策: {policy.get('title', '')}")
                            continue
                        
                        policies.append(policy)
                        
                        # 发送实时数据回调（与单线程爬虫一致）
                        if callback:
                            # 构建POLICY_DATA格式的消息
                            policy_data = f"POLICY_DATA:{policy.get('title', '')}|{policy.get('pub_date', '')}|{policy.get('link', '')}|{policy.get('content', '')}|{category_name}"
                            callback(policy_data)
                    except Exception as e:
                        logger.error(f"处理政策数据时出错: {e}")
                        continue
                
                # 如果在政策处理循环中被停止，跳出外层循环
                if hasattr(self, 'check_stop') and self.check_stop():
                    break
                
                if callback:
                    callback(f"线程 {thread_name} 分类[{category_name}]第{page}页获取{len(page_policies)}条政策")
                
                page += 1
                
            except Exception as e:
                logger.error(f"线程 {thread_name} 分类[{category_name}]处理第{page}页时出错: {e}")
                break
        
        logger.info(f"线程 {thread_name} 分类[{category_name}]完成，共获取 {len(policies)} 条政策")
        if callback:
            callback(f"线程 {thread_name} 分类[{category_name}]完成，共获取 {len(policies)} 条政策")
        
        return policies
    
    def _parse_json_results(self, data, callback):
        """解析JSON格式的搜索结果（与原始爬虫一致）"""
        policies = []
        
        try:
            # 根据实际返回的JSON结构解析（与原始爬虫一致）
            if 'results' in data:
                items = data['results']
            elif 'data' in data:
                items = data['data']
            elif 'docs' in data:
                items = data['docs']
            elif isinstance(data, list):
                items = data
            else:
                items = []
            
            for item in items:
                try:
                    title = item.get('title', '').strip()
                    if not title:
                        continue
                    
                    # 解析链接
                    link = item.get('url', '')
                    if link and not link.startswith('http'):
                        link = urljoin(self.base_url, link)
                    
                    # 解析日期
                    pub_date = item.get('pubdate', item.get('publishdate', ''))
                    if pub_date:
                        try:
                            # 尝试解析日期格式
                            parsed_date = self._parse_date(pub_date)
                            if parsed_date:
                                pub_date = parsed_date.strftime('%Y-%m-%d')
                        except:
                            pub_date = ''
                    
                    # 解析内容摘要
                    content = item.get('content', '').strip()
                    
                    policy = {
                        'level': self.level,
                        'title': title,
                        'link': link,
                        'pub_date': pub_date,
                        'content': content,
                        'doc_number': item.get('filenum', ''),
                        'source': item.get('url', ''),
                        'category': item.get('category', ''),
                        'validity': item.get('status', ''),
                        'effective_date': item.get('effectivedate', ''),
                        'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    policies.append(policy)
                    
                except Exception as e:
                    logger.error(f"解析政策项失败: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"解析JSON结果失败: {e}")
        
        return policies
    
    def _parse_html_results(self, soup, callback, category_name=''):
        """解析HTML格式的搜索结果（适配新网站结构）"""
        policies = []
        
        try:
            # 查找政策列表 - 适配新的网站结构
            table = soup.find('table', class_='table')
            if not table:
                if callback:
                    callback("未找到政策列表表格")
                return policies
            
            # 查找所有政策行（跳过表头）
            rows = table.find_all('tr')[1:]  # 跳过第一行表头
            if callback:
                callback(f"找到 {len(rows)} 条政策")
            
            for row in rows:
                try:
                    # 获取所有单元格
                    cells = row.find_all('td')
                    if len(cells) < 4:
                        continue
                    
                    # 检查是否是主政策行（不是详细信息行）
                    first_cell = cells[0].get_text(strip=True)
                    if not first_cell or first_cell in ['标    题', '索    引', '发文字号', '生成日期', '实施日期']:
                        # 这是详细信息行，跳过
                        continue
                    
                    # 检查是否是有效的政策索引号（应该包含年份和编号）
                    if not first_cell or len(first_cell) < 4 or not first_cell[0].isdigit():
                        continue
                    
                    # 解析表格数据 - 适配新结构
                    index = cells[0].get_text(strip=True)
                    title_cell = cells[1]
                    doc_number = cells[2].get_text(strip=True)
                    pub_date = cells[3].get_text(strip=True)
                    
                    # 获取标题和链接 - 新网站的结构
                    title_link = title_cell.find('a', target='_blank')
                    if not title_link:
                        # 尝试其他方式查找链接
                        title_link = title_cell.find('a')
                    
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    detail_url = title_link.get('href', '')
                    
                    # 检查解析的数据是否合理
                    if doc_number == "标    题" or pub_date == title:
                        # 如果发文字号是"标    题"或发布日期是标题内容，说明解析到了详细信息
                        # 尝试从详细信息中获取正确的数据
                        detail_info = title_cell.find('div', class_='box')
                        if detail_info:
                            detail_table = detail_info.find('table')
                            if detail_table:
                                detail_rows = detail_table.find_all('tr')
                                for detail_row in detail_rows:
                                    detail_cells = detail_row.find_all('td')
                                    if len(detail_cells) >= 2:
                                        label = detail_cells[0].get_text(strip=True)
                                        value = detail_cells[1].get_text(strip=True)
                                        
                                        if '发文字号' in label:
                                            doc_number = value
                                        elif '生成日期' in label:
                                            pub_date = value
                    
                    # 构建完整链接
                    if detail_url and not detail_url.startswith('http'):
                        detail_url = urljoin(self.base_url, detail_url)
                    
                    # 构建政策对象
                    policy = {
                        'level': self.level,
                        'title': title,
                        'pub_date': pub_date,
                        'doc_number': doc_number,
                        'source': detail_url,
                        'content': '',
                        'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'category': category_name,
                        'validity': '',
                        'effective_date': '',
                        'link': detail_url
                    }
                    
                    policies.append(policy)
                        
                except Exception as e:
                    if callback:
                        callback(f"解析政策项失败: {e}")
                    continue
                    
        except Exception as e:
            if callback:
                callback(f"解析HTML结果失败: {e}")
        
        return policies
    
    def _parse_date(self, date_str):
        """解析日期字符串（与原始爬虫一致）"""
        if not date_str:
            return None
        
        # 尝试多种日期格式
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%Y.%m.%d'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except:
                continue
        
        return None
    
    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None, 
                      speed_mode="正常速度", disable_speed_limit=False, stop_callback=None,
                      category=None):
        """兼容原有接口的多线程爬取方法"""
        self.speed_mode = speed_mode
        self.disable_speed_limit = disable_speed_limit
        self.anti_crawler.configure_speed_mode(speed_mode, disable_speed_limit)
        self.keywords = keywords  # 保存关键词供_execute_task使用
        
        # 如果指定了分类，过滤任务
        if category and category in self.categories:
            # 只爬取指定分类
            original_tasks = self._prepare_tasks()
            filtered_tasks = [task for task in original_tasks if task['category_name'] == category]
            
            # 临时替换任务列表
            original_prepare_tasks = self._prepare_tasks
            self._prepare_tasks = lambda: filtered_tasks
            
            try:
                return self.crawl_multithread(callback, stop_callback)
            finally:
                # 恢复原始方法
                self._prepare_tasks = original_prepare_tasks
        else:
            return self.crawl_multithread(callback, stop_callback)
    
    def crawl_policies_multithread(self, keywords=None, callback=None, start_date=None, end_date=None, 
                                  speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, max_workers=None,
                                  category=None):
        """多线程爬取政策（兼容广东省爬虫接口）"""
        self.speed_mode = speed_mode
        self.disable_speed_limit = disable_speed_limit
        self.anti_crawler.configure_speed_mode(speed_mode, disable_speed_limit)
        self.keywords = keywords  # 保存关键词供_execute_task使用
        
        # 如果指定了分类，过滤任务
        if category and category in self.categories:
            # 只爬取指定分类
            original_tasks = self._prepare_tasks()
            filtered_tasks = [task for task in original_tasks if task['category_name'] == category]
            
            # 临时替换任务列表
            original_prepare_tasks = self._prepare_tasks
            self._prepare_tasks = lambda: filtered_tasks
            
            try:
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
            finally:
                # 恢复原始方法
                self._prepare_tasks = original_prepare_tasks
        else:
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
            'enable_proxy': self.enable_proxy,
            'categories': list(self.categories.keys())
        } 