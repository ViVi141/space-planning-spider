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

logger = logging.getLogger(__name__)


class MNRMultiThreadSpider(MultiThreadBaseCrawler):
    """自然资源部多线程爬虫"""
    
    def __init__(self, max_workers=4, enable_proxy=True):
        super().__init__(max_workers, enable_proxy)
        
        # 自然资源部特定配置（与原始爬虫一致）
        self.base_url = 'https://f.mnr.gov.cn/'
        self.search_api = 'https://search.mnr.gov.cn/was5/web/search'
        self.ajax_api = 'https://search.mnr.gov.cn/was/ajaxdata_jsonp.jsp'
        self.level = '自然资源部'
        self.channel_id = '174757'  # 法律法规库的频道ID
        
        # 初始化防反爬虫管理器
        self.anti_crawler = AntiCrawlerManager()
        self.monitor = CrawlerMonitor()
        
        # 设置请求头（与原始爬虫一致）
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://f.mnr.gov.cn/',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        # 分类配置（与原始爬虫一致）
        self.categories = {
            '综合管理': {'code': '579/580', 'name': '综合管理'},
            '土地管理': {'code': '579/581', 'name': '土地管理'},
            '自然资源确权登记': {'code': '579/582', 'name': '自然资源确权登记'},
            '地质': {'code': '579/583', 'name': '地质'},
            '地质环境管理': {'code': '579/584', 'name': '地质环境管理'},
            '矿产资源管理': {'code': '579/585', 'name': '矿产资源管理'},
            '海洋管理': {'code': '579/586', 'name': '海洋管理'},
            '测绘地理信息管理': {'code': '579/587', 'name': '测绘地理信息管理'},
            '法律': {'code': '569/570', 'name': '法律'},
            '司法解释': {'code': '569/577', 'name': '司法解释'}
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
        max_pages = 100  # 限制每个分类的最大页数
        consecutive_empty_pages = 0
        max_consecutive_empty = 3
        
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
                
                # 构建搜索参数（与原始爬虫一致）
                params = {
                    'channelid': self.channel_id,
                    'searchword': '',  # 空关键词，搜索全部分类
                    'page': page,
                    'perpage': 20,  # 每页20条
                    'searchtype': 'title',  # 搜索标题
                    'orderby': 'RELEVANCE'  # 按相关性排序
                }
                
                # 使用线程专用会话发送请求
                with lock:
                    # 应用防反爬虫延迟
                    time.sleep(random.uniform(self.anti_crawler.min_delay, self.anti_crawler.max_delay))
                    
                    # 记录重试次数
                    retry_count = 0
                    max_retries = 3
                    
                    while retry_count < max_retries:
                        try:
                            # 检查是否需要停止
                            if hasattr(self, 'check_stop') and self.check_stop():
                                logger.info(f"线程 {thread_name} 检测到停止信号，退出重试")
                                if callback:
                                    callback(f"线程 {thread_name} 已停止")
                                break
                            
                            response = session.get(
                                self.search_api,
                                params=params,
                                headers=self.headers,
                                timeout=15
                            )
                            
                            # 请求成功，跳出重试循环
                            break
                            
                        except Exception as e:
                            retry_count += 1
                            error_msg = str(e)
                            
                            # 检查是否需要停止
                            if hasattr(self, 'check_stop') and self.check_stop():
                                logger.info(f"线程 {thread_name} 检测到停止信号，退出重试")
                                if callback:
                                    callback(f"线程 {thread_name} 已停止")
                                break
                            
                            # 处理代理错误
                            if ('ProxyError' in error_msg or '503' in error_msg or 
                                'Tunnel connection failed' in error_msg or 
                                'Connection timeout' in error_msg or
                                'Connection refused' in error_msg):
                                
                                logger.warning(f"线程 {thread_name} 分类[{category_name}]代理错误 (重试 {retry_count}/{max_retries}): {error_msg}")
                                
                                # 尝试轮换代理
                                if self.enable_proxy and hasattr(self, '_rotate_thread_proxy'):
                                    if self._rotate_thread_proxy():
                                        logger.info(f"线程 {thread_name} 轮换代理后重试")
                                        continue  # 继续重试
                                    else:
                                        logger.error(f"线程 {thread_name} 无法获取新代理")
                                        break
                                else:
                                    logger.error(f"线程 {thread_name} 代理已禁用，无法轮换")
                                    break
                            else:
                                logger.error(f"线程 {thread_name} 分类[{category_name}]请求异常: {error_msg}")
                                break
                    
                    # 如果在重试循环中被停止，跳出外层循环
                    if hasattr(self, 'check_stop') and self.check_stop():
                        break
                    
                    # 如果所有重试都失败了
                    if retry_count >= max_retries:
                        logger.error(f"线程 {thread_name} 分类[{category_name}]第{page}页请求失败，已达到最大重试次数")
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
                    page_policies = self._parse_html_results(soup, callback)
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
    
    def _parse_html_results(self, soup, callback):
        """解析HTML格式的搜索结果（与原始爬虫一致）"""
        policies = []
        
        try:
            # 查找政策列表 - 使用正确的选择器（与原始爬虫一致）
            ul = soup.find('ul', id='ul')
            if not ul:
                if callback:
                    callback("未找到政策列表容器")
                return policies
            
            # 查找所有政策项
            policy_items = ul.find_all('li', class_='p123')
            if callback:
                callback(f"找到 {len(policy_items)} 条政策")
            
            for item in policy_items:
                try:
                    # 标题和详情页链接
                    a = item.select_one('div.ffbox a[target="_blank"]')
                    if not a:
                        continue
                        
                    title = a.get_text(strip=True)
                    detail_url = a.get('href', '')
                    
                    # 详细字段 - 从表格中提取
                    dasite = item.select_one('div.dasite table')
                    tds = dasite.find_all('td') if dasite else []
                    
                    # 解析表格数据
                    doc_number = ''
                    pub_date = ''
                    publish_org = ''
                    area = ''
                    business_type = ''
                    effect_level = ''
                    abolish_record = ''
                    status = ''
                    
                    for i in range(0, len(tds), 2):
                        if i + 1 < len(tds):
                            label = tds[i].get_text(strip=True)
                            value = tds[i + 1].get_text(strip=True)
                            
                            if '文号' in label:
                                doc_number = value
                            elif '成文时间' in label or '发文时间' in label:
                                pub_date = value
                            elif '发布机构' in label:
                                publish_org = value
                            elif '适用区域' in label:
                                area = value
                            elif '业务类型' in label:
                                business_type = value
                            elif '效力级别' in label:
                                effect_level = value
                            elif '废止记录' in label:
                                abolish_record = value
                            elif '状态' in label:
                                status = value
                    
                    # 构建政策对象
                    policy = {
                        'level': self.level,
                        'title': title,
                        'link': detail_url,
                        'pub_date': pub_date,
                        'doc_number': doc_number,
                        'source': publish_org,
                        'content': '',
                        'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'category': '',
                        'validity': status,
                        'effective_date': '',
                        'area': area,
                        'business_type': business_type,
                        'effect_level': effect_level,
                        'abolish_record': abolish_record
                    }
                    
                    policies.append(policy)
                    
                except Exception as e:
                    logger.error(f"解析HTML政策项失败: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"解析HTML结果失败: {e}")
        
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