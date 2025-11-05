#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
广东省政策爬虫
"""

import hashlib
import re
import time
import random
import threading
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any, Tuple
from urllib.parse import urljoin, urlparse
import logging

from bs4 import BeautifulSoup
import requests

from .enhanced_base_crawler import EnhancedBaseCrawler
from .multithread_base_crawler import MultiThreadBaseCrawler
from .monitor import CrawlerMonitor
from .spider_config import SpiderConfig
from ..core import database as db

# 机构名称常量
LEVEL_NAME = "广东省人民政府"

# 日志记录器
logger = logging.getLogger(__name__)

# ========== API路径映射（从测试脚本迁移） ==========
# API路径映射
API_PATH_MAP = {
    'dfxfg': {'menu': 'dfxfg', 'library': 'gddifang', 'class_flag': 'gddifang'},
    'sfjs': {'menu': 'sfjs', 'library': 'regularation', 'class_flag': 'regularation'},
    'dfzfgz': {'menu': 'dfzfgz', 'library': 'gddigui', 'class_flag': 'gddigui'},
    'fljs': {'menu': 'fljs', 'library': 'gdnormativedoc', 'class_flag': 'gdnormativedoc'},
    'china': {'menu': 'china', 'library': 'gdchinalaw', 'class_flag': 'gdchinalaw'}  # 兼容旧接口
}

# 分类代码到API映射
CATEGORY_API_MAP = {
    'XM07': 'dfxfg',
    'XU13': 'sfjs',
    'XO08': 'dfzfgz',
    'XP08': 'fljs'
}

class GuangdongSpider(EnhancedBaseCrawler):
    """广东省政策爬虫 - 使用真实API接口"""
    
    def __init__(self):
        # 初始化基础爬虫
        super().__init__("广东省政策爬虫", enable_proxy=True)
        
        # 从配置获取参数
        config = SpiderConfig.get_guangdong_config()
        
        self.base_url = config['base_url']
        self.search_url = config['search_url']
        self.level = config['level']
        self.headers = config['headers'].copy()
        self.speed_mode = config['default_speed_mode']
        self.category_config = config['category_config'].copy()
        
        # 初始化监控组件
        self.monitor = CrawlerMonitor()
        
        # 初始化会话
        self._init_session()
        
        # 添加去重缓存
        self.seen_policy_ids = set()
        self.seen_policy_hashes = set()
        
        # API配置缓存（用于存储当前分类的API配置）
        self.current_api_config = None
    
    def _init_session(self):
        """初始化会话"""
        self.session = requests.Session()
        
        # 更新headers，移除AJAX相关标识
        self.headers.update({
            'Origin': 'https://gd.pkulaw.com',
            'Referer': 'https://gd.pkulaw.com/china/adv',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        })
        
        self.session.headers.update(self.headers)
        
        # 设置Cookie
        self.session.cookies.set('JSESSIONID', '1234567890ABCDEF', domain='gd.pkulaw.com')
        
        # ✅ 添加代理支持 - 使用共享代理系统
        if self.enable_proxy:
            try:
                # 确保代理池已初始化
                from .proxy_pool import initialize_proxy_pool, get_shared_proxy, is_global_proxy_enabled
                import os
                
                # 初始化代理池（如果还未初始化）
                if is_global_proxy_enabled():
                    config_file = os.path.join(os.path.dirname(__file__), '..', 'gui', 'proxy_config.json')
                    if os.path.exists(config_file):
                        initialize_proxy_pool(config_file)
                
                # 获取共享代理
                proxy_dict = get_shared_proxy()
                
                if proxy_dict:
                    # 更新会话代理设置
                    self.session.proxies.update(proxy_dict)
                    logger.info(f"[代理验证] GuangdongSpider: 会话已设置代理: {proxy_dict}")
                    
                    # 验证代理设置是否成功
                    session_proxies = getattr(self.session, 'proxies', {})
                    if session_proxies:
                        logger.info(f"[代理验证] 会话代理已更新，当前代理: {session_proxies}")
                    else:
                        logger.warning("[代理验证] 警告: 代理字典更新后，会话中未检测到代理设置")
                    
                    # 记录当前代理信息
                    proxy_info_str = ""
                    if isinstance(proxy_dict, dict) and 'http' in proxy_dict:
                        proxy_url = proxy_dict['http']
                        if proxy_url.startswith('http://'):
                            proxy_info_str = proxy_url[7:]  # 移除 'http://' 前缀
                            logger.info(f"[代理验证] GuangdongSpider: 当前代理IP:端口 = {proxy_info_str}")
                        elif proxy_url.startswith('https://'):
                            proxy_info_str = proxy_url[8:]  # 移除 'https://' 前缀
                            logger.info(f"[代理验证] GuangdongSpider: 当前代理IP:端口 = {proxy_info_str}")
                    elif isinstance(proxy_dict, dict) and 'https' in proxy_dict:
                        proxy_url = proxy_dict['https']
                        if proxy_url.startswith('https://'):
                            proxy_info_str = proxy_url[8:]
                            logger.info(f"[代理验证] GuangdongSpider: 当前代理IP:端口 = {proxy_info_str}")
                    
                    # 执行代理验证测试（可选，仅在首次设置时或DEBUG模式下）
                    try:
                        from .proxy_verifier import ProxyVerifier
                        is_using, detected_ip, proxy_ip = ProxyVerifier.verify_proxy_usage(
                            proxy_dict, timeout=5
                        )
                        if is_using:
                            logger.info(f"[代理验证] ✓ 代理验证成功 - 检测到IP: {detected_ip}, 代理IP: {proxy_ip}")
                        else:
                            logger.warning(f"[代理验证] ⚠ 代理验证未通过 - 检测到IP: {detected_ip}, 代理IP: {proxy_ip}")
                    except Exception as verify_error:
                        logger.debug(f"[代理验证] 代理验证测试失败（不影响使用）: {verify_error}")
                else:
                    logger.warning("GuangdongSpider: 警告: 启用代理但无法获取有效代理，将使用直接连接")
            except (requests.exceptions.RequestException, ValueError, KeyError) as e:
                logger.warning(f"GuangdongSpider: 代理设置失败: {e}，将使用直接连接", exc_info=True)
        else:
            logger.info("GuangdongSpider: 代理已禁用，使用直接连接")
        
        # 访问首页获取必要的Cookie
        try:
            # 验证代理是否已设置
            if self.enable_proxy:
                current_proxies = getattr(self.session, 'proxies', {})
                if current_proxies:
                    proxy_info = str(current_proxies)
                    logger.info(f"[代理验证] 会话代理设置: {proxy_info}")
                else:
                    logger.warning("[代理验证] 警告: 启用代理但会话中未检测到代理设置")
            
            resp = self.session.get(self.base_url, timeout=10)
            if resp.status_code == 200:
                if hasattr(self, 'monitor') and self.monitor:
                    self.monitor.record_request(self.base_url, success=True)
                logger.info("成功访问首页，获取必要Cookie")
                
                # 验证请求是否使用了代理（通过检查响应头或日志）
                if self.enable_proxy and hasattr(self.session, 'proxies') and self.session.proxies:
                    logger.info(f"[代理验证] 请求已使用代理: {self.session.proxies}")
            else:
                if hasattr(self, 'monitor') and self.monitor:
                    self.monitor.record_request(self.base_url, success=False, error_type=f"HTTP {resp.status_code}")
                logger.warning(f"访问首页失败，状态码: {resp.status_code}")
        except requests.exceptions.Timeout as e:
            if hasattr(self, 'monitor') and self.monitor:
                self.monitor.record_request(self.base_url, success=False, error_type="timeout")
            logger.warning(f"访问首页超时: {e}", exc_info=True)
        except requests.exceptions.ConnectionError as e:
            if hasattr(self, 'monitor') and self.monitor:
                self.monitor.record_request(self.base_url, success=False, error_type="connection_error")
            logger.error(f"访问首页连接错误: {e}", exc_info=True)
        except requests.exceptions.RequestException as e:
            if hasattr(self, 'monitor') and self.monitor:
                self.monitor.record_request(self.base_url, success=False, error_type=str(e))
            logger.error(f"访问首页请求异常: {e}", exc_info=True)
        except Exception as e:
            if hasattr(self, 'monitor') and self.monitor:
                self.monitor.record_request(self.base_url, success=False, error_type="unknown")
            logger.error(f"访问首页未知错误: {e}", exc_info=True)
    
    def _rotate_session(self):
        """轮换会话，避免访问限制（保持代理设置）"""
        logger.info("轮换会话，避免访问限制...")
        
        # 保存当前代理设置
        current_proxies = getattr(self.session, 'proxies', {})
        
        # 创建新的会话
        new_session = requests.Session()
        new_session.headers.update(self.headers)
        
        # 恢复代理设置
        if current_proxies:
            new_session.proxies.update(current_proxies)
        
        # 生成新的JSESSIONID
        import random
        import string
        new_jsessionid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        new_session.cookies.set('JSESSIONID', new_jsessionid, domain='gd.pkulaw.com')
        
        # 访问首页获取新的Cookie
        try:
            resp = new_session.get(self.base_url, timeout=10)
            if resp.status_code == 200:
                logger.info("成功轮换会话（代理已保持）")
                self.session = new_session
                return True
            else:
                logger.warning(f"轮换会话失败，状态码: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"轮换会话异常: {e}", exc_info=True)
            return False
    
    def _handle_access_limit(self, response_text):
        """处理访问限制（优化版，从测试脚本迁移）"""
        limit_keywords = [
            '访问过于频繁',
            '访问限制',
            '请稍后再试',
            'Too many requests',
            'Access denied',
            'Rate limit',
            '您已超过全文最大访问数'
        ]
        
        response_text_lower = response_text.lower()
        for keyword in limit_keywords:
            if keyword.lower() in response_text_lower:
                logger.warning(f"检测到访问限制关键词: {keyword}，尝试轮换会话...")
                if self._rotate_session():
                    logger.info("会话轮换成功，继续爬取")
                    return True
                else:
                    logger.warning("会话轮换失败，等待后重试...")
                    delay = getattr(self, 'config', {}).get('session_rotation_delay', 30) if hasattr(self, 'config') else 30
                    time.sleep(delay)  # 等待配置的延时
                    return self._rotate_session()
        return False
    
    def _check_access_limit(self, response_text: str) -> bool:
        """检查响应是否包含访问限制提示（从测试脚本迁移，兼容方法）
        
        Returns:
            True if 检测到访问限制，False otherwise
        """
        return self._handle_access_limit(response_text)
    
    def _request_page_with_check(self, page_index, search_params, old_page_index=None, category_code=None):
        """带翻页校验的页面请求（支持动态API配置）"""
        max_retries = 3
        retry_count = 0
        
        # 根据分类代码获取API配置（从search_params中推断Menu，如果没有category_code）
        api_config = None
        if category_code:
            api_config = self._get_category_api_config(category_code)
            self.current_api_config = api_config
        elif self.current_api_config:
            api_config = self.current_api_config
        else:
            # 从search_params推断API类型
            menu = search_params.get('Menu', 'china')
            if menu in API_PATH_MAP:
                api_config = API_PATH_MAP[menu].copy()
                api_config.update({
                    'search_url': f"{self.base_url}/{menu}/search/RecordSearch",
                    'init_page': f"{self.base_url}/{menu}/adv",
                    'referer': f'https://gd.pkulaw.com/{menu}/adv'
                })
            else:
                # 使用默认配置（china接口，兼容旧代码）
                api_config = API_PATH_MAP['china'].copy()
                api_config.update({
                    'search_url': self.search_url,
                    'init_page': f"{self.base_url}/china/adv",
                    'referer': 'https://gd.pkulaw.com/china/adv'
                })
        
        # 注意：不修改self.headers，避免影响详情页请求
        # 所有搜索请求都使用临时headers，保持self.headers不变
        while retry_count < max_retries:
            try:
                # 1. 先请求翻页校验接口（仅在page_index > 1时，减少不必要的请求）
                if page_index > 1:
                    check_url = "https://gd.pkulaw.com/VerificationCode/GetRecordListTurningLimit"
                    check_headers = self.headers.copy()
                    # 使用正确的Referer
                    if api_config.get('referer'):
                        check_headers['Referer'] = api_config['referer']
                    check_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
                    
                    logger.debug(f"请求翻页校验接口: 第{page_index}页 (重试{retry_count + 1}/{max_retries})")
                    try:
                        # ✅ 使用代理进行校验请求
                        check_resp, check_info = self.post_page(check_url, headers=check_headers)
                        if check_resp and check_resp.status_code == 200:
                            self.monitor.record_request(check_url, success=True)
                            logger.debug(f"翻页校验成功: {check_resp.status_code}")
                        else:
                            self.monitor.record_request(check_url, success=False, error_type=f"HTTP {check_resp.status_code if check_resp else 'No response'}")
                            logger.warning(f"翻页校验失败: {check_resp.status_code if check_resp else 'No response'}")
                            # 如果校验失败，等待后重试整个流程
                            retry_count += 1
                            if retry_count < max_retries:
                                logger.warning(f"翻页校验失败，重试整个流程...")
                                time.sleep(3)
                                continue
                            else:
                                logger.warning(f"翻页校验达到最大重试次数，尝试跳过校验直接请求数据")
                    except Exception as check_error:
                        self.monitor.record_request(check_url, success=False, error_type=str(check_error))
                        logger.error(f"翻页校验请求异常: {check_error}", exc_info=True)
                        # 校验异常时，等待后重试
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.warning(f"翻页校验异常，重试整个流程...")
                            time.sleep(3)
                            continue
                        else:
                            logger.warning(f"翻页校验异常达到最大重试次数，尝试跳过校验直接请求数据")
                
                # 2. 再请求数据接口（使用动态API配置）
                search_url = api_config['search_url']
                # 使用临时headers（包含正确的Referer，但不修改self.headers）
                search_headers = self.headers.copy()
                if api_config.get('referer'):
                    search_headers['Referer'] = api_config['referer']
                search_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
                
                # 更新搜索参数中的OldPageIndex
                if old_page_index is not None:
                    search_params['OldPageIndex'] = str(old_page_index)
                
                logger.debug(f"请求数据接口: {search_url}, 第{page_index}页 (重试{retry_count + 1}/{max_retries})")
                
                # ✅ 使用代理进行数据请求
                search_resp, search_info = self.post_page(search_url, data=search_params, headers=search_headers)
                
                logger.debug(f"数据接口响应状态码: {search_resp.status_code if search_resp else 'No response'}")
                
                if search_resp and search_resp.status_code == 200:
                    # 检查响应内容是否包含访问限制
                    response_text = search_resp.text
                    if self._handle_access_limit(response_text):
                        logger.warning(f"检测到访问限制，已轮换会话，重试第{page_index}页")
                        retry_count += 1
                        time.sleep(5)  # 等待5秒后重试
                        continue
                    
                    self.monitor.record_request(search_url, success=True)
                    logger.info(f"第{page_index}页请求成功")
                    return search_resp
                else:
                    error_msg = f"HTTP {search_resp.status_code}" if search_resp else "请求失败"
                    self.monitor.record_request(search_url, success=False, error_type=error_msg)
                    logger.warning(f"数据请求失败，状态码: {error_msg}")
                    
                    # 如果是403或429错误，尝试轮换会话
                    if search_resp and search_resp.status_code in [403, 429]:
                        logger.warning(f"检测到访问限制，尝试轮换会话...")
                        if self._rotate_session():
                            logger.info("会话轮换成功，重试请求")
                            retry_count += 1
                            time.sleep(3)  # 等待3秒后重试
                            continue
                        else:
                            logger.warning("会话轮换失败")
                    
                    # 如果是其他错误，增加重试次数
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(2)  # 等待2秒后重试
                        continue
                    else:
                        logger.warning(f"达到最大重试次数({max_retries})，放弃请求")
                        return None
                        
            except requests.exceptions.Timeout as e:
                logger.warning(f"请求超时: {e}", exc_info=True)
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)
                    continue
                else:
                    logger.warning(f"达到最大重试次数({max_retries})，放弃请求")
                    return None
            except requests.exceptions.ConnectionError as e:
                logger.error(f"连接错误: {e}", exc_info=True)
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)
                    continue
                else:
                    logger.warning(f"达到最大重试次数({max_retries})，放弃请求")
                    return None
            except requests.exceptions.RequestException as e:
                logger.error(f"请求异常: {e}", exc_info=True)
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)
                    continue
                else:
                    logger.warning(f"达到最大重试次数({max_retries})，放弃请求")
                    return None
            except Exception as e:
                logger.error(f"未知请求错误: {e}", exc_info=True)
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)
                    continue
                else:
                    logger.warning(f"达到最大重试次数({max_retries})，放弃请求")
                    return None
        
        return None
    
    def extract_policy_count_from_html(self, html_content):
        """从HTML中提取政策数量 - 基于检测结果优化"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 方法1: 通过正则表达式提取
            text_content = soup.get_text()
            match = re.search(r'总共检索到(\d+)篇', text_content)
            if match:
                return int(match.group(1))
            
            # 方法2: 通过span标签提取
            count_spans = soup.find_all('span')
            for span in count_spans:
                text = span.get_text(strip=True)
                if re.search(r'\d+', text):
                    numbers = re.findall(r'\d+', text)
                    if numbers:
                        return int(numbers[0])
            
            return 0
            
        except (ValueError, AttributeError, TypeError) as e:
            logger.warning(f"提取政策数量失败（解析错误）: {e}", exc_info=True)
            return 0
        except Exception as e:
            logger.error(f"提取政策数量失败（未知错误）: {e}", exc_info=True)
            return 0
    
    def _parse_policy_list_html(self, html_content, callback=None, stop_callback=None, category_name=None, policy_callback=None):
        """解析HTML响应中的政策列表 - 优化版本，支持实时回调"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            policies = []

            # 调试：打印页面标题和基本信息
            page_title = soup.find('title')
            if page_title:
                logger.debug(f"页面标题: {page_title.get_text()}")

            # 方法1: 从复选框value提取政策ID并构建URL（最可靠）
            # 这是从测试脚本迁移的最可靠方法，直接从表单复选框提取政策ID
            checkboxes = soup.select('input.checkbox[name="recordList"]')
            checkbox_policies = []
            if checkboxes:
                logger.debug(f"从复选框提取到 {len(checkboxes)} 个政策ID")
                for checkbox in checkboxes:
                    policy_id = checkbox.get('value', '').strip()
                    if policy_id and len(policy_id) > 10:  # 政策ID通常是较长的字符串
                        # 根据当前API配置确定链接路径
                        current_config = getattr(self, 'current_api_config', None)
                        if current_config and isinstance(current_config, dict):
                            link_path = current_config.get('library', 'gddigui')
                        else:
                            link_path = 'gddigui'  # 默认值
                        url = f"{self.base_url}/{link_path}/{policy_id}.html"

                        # 创建基础政策数据
                        policy_data = {
                            'level': '广东省人民政府',
                            'title': f'政策ID: {policy_id}',  # 临时标题，后续会获取完整信息
                            'pub_date': '',  # 需要从详情页获取
                            'source': url,
                            'url': url,
                            'content': '',  # 需要从详情页获取
                            'category': category_name or '',
                            'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'policy_id': policy_id  # 保存政策ID用于后续处理
                        }

                        # 标记需要获取详情内容（延迟到所有政策解析完成后批量获取）
                        policy_data['_need_detail_fetch'] = True  # 标记需要获取详情
                        checkbox_policies.append(policy_data)

            # 方法2: 传统HTML解析方法（作为备用）
            policy_items = []

            # 尝试多种选择器
            selectors = [
                'tr[class*="item"]',
                'tr[class*="policy"]',
                'tr[class*="record"]',
                'tr[class*="list"]',
                'div[class*="item"]',
                'div[class*="policy"]',
                'div[class*="record"]',
                'div[class*="list"]',
                'li[class*="item"]',
                'li[class*="policy"]',
                'li[class*="record"]',
                'li[class*="list"]'
            ]

            for selector in selectors:
                items = soup.select(selector)
                if items:
                    policy_items.extend(items)
                    logger.debug(f"使用选择器 '{selector}' 找到 {len(items)} 个项目")
                    break

            # 如果上面的选择器都没找到，尝试查找所有包含链接的表格行
            if not policy_items:
                all_tr = soup.find_all('tr')
                for tr in all_tr:
                    if tr.find('a') and tr.find('a').get('href'):
                        policy_items.append(tr)
                logger.debug(f"通过表格行找到 {len(policy_items)} 个包含链接的项目")

            # 如果还是没有，尝试查找所有包含链接的div
            if not policy_items:
                all_divs = soup.find_all('div')
                for div in all_divs:
                    link = div.find('a')
                    if link and link.get('href') and link.get_text(strip=True):
                        policy_items.append(div)
                logger.debug(f"通过div找到 {len(policy_items)} 个包含链接的项目")
            
            # 合并两种方法的政策数据
            all_policy_items = policy_items.copy()

            # 如果有checkbox提取的政策，添加到列表中
            if checkbox_policies:
                # 为checkbox政策创建虚拟的HTML元素，以便统一处理
                for checkbox_policy in checkbox_policies:
                    # 创建一个简单的虚拟元素来传递数据
                    class VirtualItem:
                        def __init__(self, policy_data):
                            self.policy_data = policy_data
                            self.from_checkbox = True

                        def find(self, tag):
                            return None

                        def get_text(self):
                            return self.policy_data.get('title', '')

                    virtual_item = VirtualItem(checkbox_policy)
                    all_policy_items.append(virtual_item)

                logger.info(f"合并政策数据: checkbox方法 {len(checkbox_policies)} 个, 传统方法 {len(policy_items)} 个")

            logger.info(f"总共找到 {len(all_policy_items)} 个潜在的政策项目")

            # 调试：打印前几个项目的内容
            for i, item in enumerate(all_policy_items[:3]):
                if hasattr(item, 'from_checkbox') and item.from_checkbox:
                    logger.debug(f"项目 {i+1} (checkbox): {item.policy_data.get('title', '')}")
                else:
                    logger.debug(f"项目 {i+1}: {item.get_text()[:100]}...")

            for item in all_policy_items:
                # 检查是否停止
                if stop_callback and stop_callback():
                    logger.info("用户已停止爬取")
                    break

                try:
                    # 处理checkbox提取的政策
                    if hasattr(item, 'from_checkbox') and item.from_checkbox:
                        policy_data = item.policy_data
                    else:
                        # 传统HTML解析方法
                        policy_data = self._extract_policy_from_item(item, category_name)

                    if policy_data:
                        policies.append(policy_data)

                        # 注意：不在此处调用policy_callback，避免时序问题
                        # 批量详情获取完成后统一发送

                except Exception as e:
                    logger.warning(f"解析政策项目失败: {e}", exc_info=True)
                    continue
            
            # 批量获取需要详情内容的政策
            policies_needing_detail = [p for p in policies if p.get('_need_detail_fetch')]
            if policies_needing_detail:
                logger.info(f"批量获取 {len(policies_needing_detail)} 条政策的详情内容...")
                for policy in policies_needing_detail:
                    if stop_callback and stop_callback():
                        logger.info("用户已停止爬取")
                        break

                    url = policy.get('url')
                    if url:
                        try:
                            logger.debug(f"获取政策详情: {url}")
                            content = self.get_policy_detail(url)
                            if content and len(content) > 50:
                                # 从详情页提取真实标题
                                detail_soup = BeautifulSoup(content, 'html.parser')

                                # 尝试多种方式获取标题
                                real_title = None

                                # 方法1: 从<title>标签获取
                                title_tag = detail_soup.find('title')
                                if title_tag and title_tag.get_text(strip=True):
                                    title_text = title_tag.get_text(strip=True)
                                    # 清理标题（移除网站名称等）
                                    if ' - ' in title_text:
                                        real_title = title_text.split(' - ')[0].strip()
                                    elif ' | ' in title_text:
                                        real_title = title_text.split(' | ')[0].strip()
                                    elif '_' in title_text:
                                        real_title = title_text.split('_')[0].strip()
                                    else:
                                        real_title = title_text

                                # 方法2: 从所有<h1>、<h2>、<h3>获取
                                if not real_title or real_title.startswith('政策ID:'):
                                    for tag_name in ['h1', 'h2', 'h3']:
                                        headings = detail_soup.find_all(tag_name)
                                        for heading in headings:
                                            heading_text = heading.get_text(strip=True)
                                            if (heading_text and
                                                len(heading_text) > 5 and
                                                len(heading_text) < 200 and
                                                not heading_text.isdigit() and  # 排除纯数字
                                                not heading_text.startswith('http') and  # 排除URL
                                                '政策ID:' not in heading_text and  # 排除政策ID
                                                not heading_text.lower().startswith(('page', '第'))):  # 排除分页信息
                                                real_title = heading_text
                                                break
                                        if real_title:
                                            break

                                # 方法2.5: 从strong标签或特定class获取
                                if not real_title or real_title.startswith('政策ID:'):
                                    title_selectors = [
                                        'div.title', 'div.article-title', 'div.policy-title',
                                        'h4.title', 'strong', 'b', '.title'
                                    ]
                                    for selector in title_selectors:
                                        title_elements = detail_soup.select(selector)
                                        for element in title_elements:
                                            element_text = element.get_text(strip=True)
                                            if (element_text and
                                                len(element_text) > 5 and
                                                len(element_text) < 150 and
                                                not element_text.isdigit() and
                                                '政策ID:' not in element_text and
                                                not element_text.startswith('http')):
                                                real_title = element_text
                                                break
                                        if real_title:
                                            break

                                # 更新政策数据
                                if real_title and not real_title.startswith('政策ID:'):
                                    policy['title'] = real_title
                                    logger.info(f"✓ 成功提取真实标题: {real_title}")
                                else:
                                    logger.warning(f"⚠️ 未能提取有效标题，保持原标题: {policy.get('title', 'N/A')}")

                                policy['content'] = content
                                logger.info(f"✓ 成功获取政策正文，长度: {len(content)}")

                            else:
                                logger.warning(f"✗ 详情内容为空或过短: {len(content) if content else 0}")

                            # 移除标记
                            policy.pop('_need_detail_fetch', None)

                        except Exception as e:
                            logger.warning(f"✗ 获取政策详情失败: {url}, 错误: {e}")
                            policy.pop('_need_detail_fetch', None)

            # 批量详情获取完成后，统一发送所有政策数据到GUI
            if policy_callback:
                logger.info(f"批量详情获取完成，发送 {len(policies)} 条完整政策数据到GUI...")
                for policy in policies:
                    try:
                        policy_callback(policy)
                        # 小延迟确保界面流畅更新
                        time.sleep(0.005)
                    except Exception as cb_error:
                        logger.warning(f"发送政策数据到GUI失败: {cb_error}")

            # 发送解析完成信号
            if callback:
                callback(f"成功解析并获取详情: {len(policies)} 条政策")

            logger.info(f"成功解析 {len(policies)} 条政策并完成详情获取")
            return policies
            
        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.warning(f"解析政策列表失败（数据格式错误）: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"解析政策列表失败（未知错误）: {e}", exc_info=True)
            return []
    
    def _extract_policy_from_item(self, item, category_name):
        """从单个HTML元素中提取政策信息 - 优化版本"""
        try:
            # 查找标题链接
            title_link = None
            if hasattr(item, 'find'):
                title_link = item.find('a')  # type: ignore
            else:
                return None
                
            if not title_link:
                return None
            
            title = title_link.get_text(strip=True)
            url = title_link.get('href', '')

            # 过滤掉无效的JavaScript链接
            if self._is_invalid_link(url):
                return None

            # 验证标题和URL
            if not title or len(title) < 3:
                return None
            
                        # 处理URL
            if url and not url.startswith('http'):
                if url.startswith('/'):
                    url = self.base_url + url
                elif not url.startswith('http'):
                    url = self.base_url + '/' + url
            
            # 查找其他信息（日期、文号等）
            text_content = item.get_text()
            
            # 提取日期 - 多种格式
            date_patterns = [
                r'(\d{4}-\d{2}-\d{2})',
                r'(\d{4}/\d{2}/\d{2})',
                r'(\d{4}年\d{1,2}月\d{1,2}日)',
                r'(\d{4}\.\d{1,2}\.\d{1,2})'
            ]
            
            pub_date = ''
            for pattern in date_patterns:
                date_match = re.search(pattern, text_content)
                if date_match:
                    date_str = date_match.group(1)
                    # 统一转换为 YYYY-MM-DD 格式
                    if '年' in date_str:
                        # 处理 "2024年1月1日" 格式
                        import re as re_module
                        date_parts = re_module.findall(r'\d+', date_str)
                        if len(date_parts) >= 3:
                            year, month, day = date_parts[0], date_parts[1].zfill(2), date_parts[2].zfill(2)
                            pub_date = f"{year}-{month}-{day}"
                    elif '/' in date_str:
                        # 处理 "2024/01/01" 格式
                        parts = date_str.split('/')
                        if len(parts) == 3:
                            pub_date = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                    elif '.' in date_str:
                        # 处理 "2024.01.01" 格式
                        parts = date_str.split('.')
                        if len(parts) == 3:
                            pub_date = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                    else:
                        # 已经是 YYYY-MM-DD 格式
                        pub_date = date_str
                    break
            
            # 如果还是没有找到日期，尝试从URL中提取（有些URL包含日期）
            if not pub_date and url:
                url_date_match = re.search(r'(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})', url)
                if url_date_match:
                    year, month, day = url_date_match.groups()
                    pub_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            # 提取文号 - 多种格式
            doc_patterns = [
                r'[（\(](\d{4})[）\)]',
                r'粤府[（\(](\d{4})[）\)]',
                r'粤府办[（\(](\d{4})[）\)]',
                r'粤国土资[（\(](\d{4})[）\)]',
                r'粤建[（\(](\d{4})[）\)]'
            ]
            
            doc_number = ''
            for pattern in doc_patterns:
                doc_match = re.search(pattern, text_content)
                if doc_match:
                    doc_number = doc_match.group(1)
                    break
            
            # 生成政策哈希用于去重
            policy_hash = self._generate_policy_hash({
                'title': title,
                'url': url,
                'pub_date': pub_date
            })
            
            if policy_hash in self.seen_policy_hashes:
                return None
            
            self.seen_policy_hashes.add(policy_hash)
            
            # 调试信息
            logger.debug(f"提取政策: {title[:50]}... | 日期: {pub_date} | 文号: {doc_number}")
            
            # 尝试获取政策详情内容
            content = ""
            try:
                if url:
                    logger.debug(f"获取政策详情: {url}")
                    content = self.get_policy_detail(url)
                    if content and len(content) > 50:
                        logger.debug(f"成功获取政策详情，长度: {len(content)}")
                    else:
                        logger.debug(f"政策详情内容为空或过短: {len(content) if content else 0}")
            except Exception as e:
                logger.warning(f"获取政策详情失败: {url}, {e}")
            
            return {
                'level': '广东省人民政府',
                'title': title,
                'pub_date': pub_date,
                'doc_number': doc_number or '',
                'source': url or '广东省法律法规数据库',  # 主要字段：source
                'url': url or '',  # 兼容字段
                'link': url or '',  # 兼容字段
                'content': content or '',  # 确保content字段存在
                'category': category_name or '',  # 确保category字段存在
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except (ValueError, KeyError, AttributeError, TypeError) as e:
                logger.warning(f"提取政策信息失败（数据格式错误）: {e}", exc_info=True)
                return None
        except Exception as e:
                logger.error(f"提取政策信息失败（未知错误）: {e}", exc_info=True)
                return None
    
    def _get_all_categories(self):
        """获取所有分类信息 - 基于网站层级结构分析结果"""
        # 基于网站导航结构，使用父级和子级分类
        categories = [
            # 父级分类：广东地方性法规 (/dfxfg/)
            ("地方性法规", "XM07", [
                ("省级地方性法规", "XM0701"),
                ("设区的市地方性法规", "XM0702"), 
                ("经济特区法规", "XM0703"),
                ("自治条例和单行条例", "XU13"),
            ]),
            
            # 父级分类：广东地方政府规章 (/dfzfgz/)
            ("地方政府规章", "XO08", [
                ("省级地方政府规章", "XO0802"),
                ("设区的市地方政府规章", "XO0803"),
            ]),
            
            # 父级分类：广东规范性文件 (/fljs/)
            ("规范性文件", "XP08", [
                ("地方规范性文件", "XP08"),
            ]),
        ]
        return categories
    
    def _get_flat_categories(self):
        """获取扁平化的分类列表（兼容旧版本）"""
        flat_categories = []
        for parent_name, parent_code, sub_categories in self._get_all_categories():
            for sub_name, sub_code in sub_categories:
                flat_categories.append((sub_name, sub_code))
        return flat_categories
    
    def _get_search_parameters(self, keywords=None, category_code=None, page_index=1, page_size=20, start_date=None, end_date=None, old_page_index=None, filter_year=None, api_config=None):
        """获取搜索参数 - 支持动态API配置（从测试脚本迁移优化版）
        
        Args:
            keywords: 关键词列表
            category_code: 分类代码
            page_index: 页码
            page_size: 每页数量
            start_date: 开始日期
            end_date: 结束日期
            old_page_index: 上一页页码
            filter_year: 年份筛选（如果指定，将通过ClassCodeKey传递年份实现）
            api_config: API配置（包含menu, library, class_flag等），如果不提供则根据category_code自动获取
        """
        # 如果没有提供api_config，根据分类代码获取
        if api_config is None:
            if category_code:
                api_config = self._get_category_api_config(category_code)
                self.current_api_config = api_config
            else:
                # 使用默认配置（china接口，兼容旧代码）
                api_config = API_PATH_MAP['china'].copy()
                api_config.update({
                    'search_url': self.search_url,
                    'init_page': f"{self.base_url}/china/adv",
                    'referer': 'https://gd.pkulaw.com/china/adv'
                })
        
        # 根据接口类型调整页大小（fljs接口使用100条/页来突破500页限制）
        if api_config.get('menu') == 'fljs' and page_size == 20:
            page_size = 100  # fljs接口使用更大的页大小
            logger.debug(f"fljs接口检测到，调整页大小为 {page_size}")
        
        # 基于网站表单分析，使用正确的参数名称
        search_params = {
            'Menu': api_config['menu'],  # 根据分类类型动态选择菜单
            'Keywords': keywords[0] if keywords and len(keywords) > 0 else '',
            'SearchKeywordType': 'Title',
            'MatchType': 'Exact',
            'RangeType': 'Piece',
            'Library': api_config['library'],  # 根据分类类型动态选择库
            'ClassFlag': api_config['class_flag'],
            'GroupLibraries': '',
            'QueryOnClick': 'False',
            'AfterSearch': 'False',
            'pdfStr': '',
            'pdfTitle': '',
            'IsAdv': 'True',
            # 修复：同时支持分类代码和年份筛选
            # 格式：,,,XP08,,,2023 表示筛选XP08分类的2023年数据
            'ClassCodeKey': (
                f',,,{category_code},,,{filter_year}' if filter_year and category_code
                else f',,,{filter_year}' if filter_year
                else f',,,{category_code},,,' if category_code
                else ',,,,,,'
            ),
            'GroupByIndex': '0',
            'OrderByIndex': '0',
            'ShowType': 'Default',
            'GroupValue': '',  # 不使用GroupValue（改用ClassCodeKey传递年份筛选）
            'AdvSearchDic.Title': '',
            'AdvSearchDic.CheckFullText': '',
            'AdvSearchDic.IssueDepartment': '',
            'AdvSearchDic.DocumentNO': '',
            'AdvSearchDic.IssueDate': start_date or '',  # 保留日期筛选作为备用
            'AdvSearchDic.ImplementDate': end_date or '',  # 保留日期筛选作为备用
            'AdvSearchDic.TimelinessDic': '',
            'AdvSearchDic.EffectivenessDic': '',
            'TitleKeywords': ' '.join(keywords) if keywords else '',
            'FullTextKeywords': ' '.join(keywords) if keywords else '',
            'Pager.PageIndex': str(page_index),
            'Pager.PageSize': str(page_size),  # 注意：fljs接口需要使用100条/页来突破500页限制
            'QueryBase64Request': '',
            'VerifyCodeResult': '',
            'isEng': 'chinese',
            'OldPageIndex': str(old_page_index) if old_page_index is not None else '',
            'newPageIndex': str(page_index) if old_page_index is not None else '',
            'X-Requested-With': 'XMLHttpRequest',  # 必须的AJAX标识
        }
        
        # 如果有关键词，设置到多个字段中
        if keywords:
            search_params['Keywords'] = ' '.join(keywords)
            search_params['TitleKeywords'] = ' '.join(keywords)
            search_params['FullTextKeywords'] = ' '.join(keywords)
        
        return search_params
    
    def _generate_policy_hash(self, policy):
        """生成政策数据的哈希值用于去重"""
        if isinstance(policy, dict):
            # 使用标题和发文字号生成哈希
            title = policy.get('title', '')
            doc_number = policy.get('doc_number', '')
            pub_date = policy.get('pub_date', '')
            content = policy.get('content', '')
            
            hash_string = f"{title}|{doc_number}|{pub_date}|{content}"
        else:
            # 如果是其他格式，转换为字符串
            hash_string = str(policy)
        
        return hashlib.md5(hash_string.encode('utf-8')).hexdigest()
    
    def _is_duplicate_policy(self, policy):
        """检查政策是否重复"""
        # 生成政策哈希
        policy_hash = self._generate_policy_hash(policy)
        
        # 检查是否已存在
        if policy_hash in self.seen_policy_hashes:
            return True
        
        # 添加到已见集合
        self.seen_policy_hashes.add(policy_hash)
        return False
    
    def _deduplicate_policies(self, policies):
        """去重政策数据"""
        if not policies:
            return []
        
        # 使用多种方式去重
        seen_titles = set()
        seen_hashes = set()
        unique_policies = []
        
        for policy in policies:
            if isinstance(policy, dict) and 'title' in policy:
                title = policy['title'].strip()
                policy_hash = self._generate_policy_hash(policy)
                
                if title and title not in seen_titles and policy_hash not in seen_hashes:
                    seen_titles.add(title)
                    seen_hashes.add(policy_hash)
                    unique_policies.append(policy)
            elif isinstance(policy, (list, tuple)) and len(policy) >= 2:
                title = str(policy[2]).strip()  # 假设title在第3个位置
                policy_hash = self._generate_policy_hash(policy)
                
                if title and title not in seen_titles and policy_hash not in seen_hashes:
                    seen_titles.add(title)
                    seen_hashes.add(policy_hash)
                    unique_policies.append(policy)
        
        logger.info(f"去重前: {len(policies)} 条政策")
        logger.info(f"去重后: {len(unique_policies)} 条政策")
        logger.info(f"重复率: {(len(policies) - len(unique_policies)) / len(policies) * 100:.1f}%" if policies else "0%")
        
        return unique_policies

    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None,
                      speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, policy_callback=None):
        """爬取广东省政策

        Args:
            keywords: 关键词列表
            callback: 进度回调函数
            start_date: 起始日期
            end_date: 结束日期
            speed_mode: 速度模式
            disable_speed_limit: 是否禁用速度限制
            stop_callback: 停止回调函数
            policy_callback: 政策数据回调函数，每解析到一条政策时调用
        """
        logger.info(f"开始爬取广东省政策，关键词: {keywords}")

        # 解析时间范围
        dt_start = None
        dt_end = None
        enable_time_filter = False

        if start_date and end_date:
            try:
                dt_start = datetime.strptime(start_date, '%Y-%m-%d')
                dt_end = datetime.strptime(end_date, '%Y-%m-%d')
                enable_time_filter = True
                logger.info(f"启用时间过滤: {start_date} 至 {end_date}")
            except ValueError:
                logger.warning(f"时间格式错误，禁用时间过滤")

        # 设置速度模式
        if speed_mode == "快速模式":
            delay_range = (0.1, 0.5)
        elif speed_mode == "慢速模式":
            delay_range = (2, 4)
        else:  # 正常速度
            delay_range = (1, 2)

        # 获取所有分类
        categories = self._get_flat_categories()
        logger.info(f"找到 {len(categories)} 个分类")

        all_policies = []

        # 遍历所有分类进行年份分割爬取
        logger.info("开始传统分类爬取...")
        if callback:
            callback("开始传统分类爬取...")

        for category_name, category_code in categories:
            if stop_callback and stop_callback():
                logger.info("用户已停止爬取")
                break
                
            try:
                logger.debug(f"正在请求第 {page_index} 页...")
                if callback:
                    callback(f"正在请求第 {page_index} 页...")
                
                # 使用成功的策略1：高级搜索表单，添加分页参数
                search_params = self._get_search_parameters(
                    keywords=keywords,
                    page_index=page_index,
                    page_size=20
                )
                
                resp = self.session.post(
                    f"{self.base_url}/china/search/RecordSearch",
                    data=search_params,
                    timeout=30
                )
                
                if resp.status_code == 200:
                    self.monitor.record_request(f"{self.base_url}/china/search/RecordSearch", success=True)
                    
                    # 使用HTML解析，传递 policy_callback 实现流动显示
                    policies = self._parse_policy_list_html(resp.text, callback, stop_callback, "高级搜索表单", policy_callback)
                    
                    if policies:
                        logger.info(f"第{page_index}页获取到 {len(policies)} 条政策")
                        # 立即调用 policy_callback 实时返回每条政策（流动显示）
                        if policy_callback:
                            for policy in policies:
                                if stop_callback and stop_callback():
                                    logger.info("用户已停止爬取")
                                    break
                                try:
                                    # 立即调用回调，实现流动显示
                                    policy_callback(policy)
                                    # 添加小延迟，让界面有时间更新（避免界面卡顿）
                                    time.sleep(0.005)  # 5毫秒延迟，提高流动速度
                                except Exception as cb_error:
                                    logger.warning(f"调用 policy_callback 失败: {cb_error}")
                        all_policies.extend(policies)
                        empty_page_count = 0  # 重置连续空页计数
                        
                        if callback:
                            callback(f"第{page_index}页获取到 {len(policies)} 条政策")
                    else:
                        empty_page_count += 1
                        logger.debug(f"第{page_index}页无数据")
                        if callback:
                            callback(f"第{page_index}页无数据")
                else:
                    self.monitor.record_request(f"{self.base_url}/china/search/RecordSearch", success=False, error_type=f"HTTP {resp.status_code}")
                    logger.warning(f"第{page_index}页请求失败，状态码: {resp.status_code}")
                    empty_page_count += 1
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"第{page_index}页请求失败: {e}", exc_info=True)
                empty_page_count += 1
            except (ValueError, KeyError, AttributeError) as e:
                logger.warning(f"第{page_index}页解析失败: {e}", exc_info=True)
                empty_page_count += 1
            except Exception as e:
                logger.error(f"第{page_index}页处理失败: {e}", exc_info=True)
                empty_page_count += 1
                
            page_index += 1
            
            # 添加延迟避免请求过快
            time.sleep(1)
        
        # 处理需要详情获取的政策（china接口的结果）
        if all_policies:
            policies_needing_detail = [p for p in all_policies if p.get('_need_detail_fetch')]
            if policies_needing_detail:
                logger.info(f"china接口策略：批量获取 {len(policies_needing_detail)} 条政策的详情内容...")
                for policy in policies_needing_detail:
                    if stop_callback and stop_callback():
                        logger.info("用户已停止爬取")
                        break

                    url = policy.get('url')
                    if url:
                        try:
                            logger.debug(f"china接口：获取政策详情: {url}")
                            content = self.get_policy_detail(url)
                            if content and len(content) > 50:
                                # 从详情页提取真实标题
                                detail_soup = BeautifulSoup(content, 'html.parser')

                                # 尝试多种方式获取标题
                                real_title = None

                                # 方法1: 从<title>标签获取
                                title_tag = detail_soup.find('title')
                                if title_tag and title_tag.get_text(strip=True):
                                    title_text = title_tag.get_text(strip=True)
                                    # 清理标题（移除网站名称等）
                                    if ' - ' in title_text:
                                        real_title = title_text.split(' - ')[0].strip()
                                    elif ' | ' in title_text:
                                        real_title = title_text.split(' | ')[0].strip()
                                    elif '_' in title_text:
                                        real_title = title_text.split('_')[0].strip()
                                    else:
                                        real_title = title_text

                                # 方法2: 从所有<h1>、<h2>、<h3>获取
                                if not real_title or real_title.startswith('政策ID:'):
                                    for tag_name in ['h1', 'h2', 'h3']:
                                        headings = detail_soup.find_all(tag_name)
                                        for heading in headings:
                                            heading_text = heading.get_text(strip=True)
                                            if (heading_text and
                                                len(heading_text) > 5 and
                                                len(heading_text) < 200 and
                                                not heading_text.isdigit() and  # 排除纯数字
                                                not heading_text.startswith('http') and  # 排除URL
                                                '政策ID:' not in heading_text and  # 排除政策ID
                                                not heading_text.lower().startswith(('page', '第'))):  # 排除分页信息
                                                real_title = heading_text
                                                break
                                        if real_title:
                                            break

                                # 方法2.5: 从strong标签或特定class获取
                                if not real_title or real_title.startswith('政策ID:'):
                                    title_selectors = [
                                        'div.title', 'div.article-title', 'div.policy-title',
                                        'h4.title', 'strong', 'b', '.title'
                                    ]
                                    for selector in title_selectors:
                                        title_elements = detail_soup.select(selector)
                                        for element in title_elements:
                                            element_text = element.get_text(strip=True)
                                            if (element_text and
                                                len(element_text) > 5 and
                                                len(element_text) < 150 and
                                                not element_text.isdigit() and
                                                '政策ID:' not in element_text and
                                                not element_text.startswith('http')):
                                                real_title = element_text
                                                break
                                        if real_title:
                                            break

                                # 更新政策数据
                                if real_title and not real_title.startswith('政策ID:'):
                                    policy['title'] = real_title
                                    logger.info(f"✓ china接口：成功提取真实标题: {real_title}")
                                else:
                                    logger.warning(f"⚠️ china接口：未能提取有效标题，保持原标题: {policy.get('title', 'N/A')}")

                                policy['content'] = content
                                logger.info(f"✓ china接口：成功获取政策正文，长度: {len(content)}")

                            else:
                                logger.warning(f"✗ china接口：详情内容为空或过短: {len(content) if content else 0}")

                            # 移除标记
                            policy.pop('_need_detail_fetch', None)

                        except Exception as e:
                            logger.warning(f"✗ china接口：获取政策详情失败: {url}, 错误: {e}")
                            policy.pop('_need_detail_fetch', None)

        # 注意：china接口的政策已经在前面通过policy_callback发送过了
        # 这里批量详情获取是为了更新已发送的数据
        logger.info(f"china接口策略完成，共获取 {len(all_policies)} 条政策")
        return all_policies
    
    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None, 
                      speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, policy_callback=None):
        """爬取广东省政策
        
        Args:
            keywords: 关键词列表
            callback: 进度回调函数
            start_date: 起始日期
            end_date: 结束日期
            speed_mode: 速度模式
            disable_speed_limit: 是否禁用速度限制
            stop_callback: 停止回调函数
            policy_callback: 政策数据回调函数，每解析到一条政策时调用
        """
        logger.info(f"开始爬取广东省政策，关键词: {keywords}, 时间范围: {start_date} 至 {end_date}, policy_callback={'已设置' if policy_callback else '未设置'}")
        
        # 解析时间范围
        dt_start = None
        dt_end = None
        enable_time_filter = False  # 是否启用时间过滤
        
        if start_date and end_date:
            try:
                dt_start = datetime.strptime(start_date, '%Y-%m-%d')
                dt_end = datetime.strptime(end_date, '%Y-%m-%d')
                enable_time_filter = True
                logger.info(f"启用时间过滤: {start_date} 至 {end_date}")
            except ValueError:
                logger.warning(f"时间格式错误，禁用时间过滤")
                enable_time_filter = False
        else:
            logger.info("未设置时间范围，禁用时间过滤")
            enable_time_filter = False
        
        # 统计信息
        total_crawled = 0  # 总爬取数量
        total_filtered = 0  # 过滤后数量
        total_saved = 0     # 最终保存数量
        
        # 设置速度模式
        self.speed_mode = speed_mode
        if speed_mode == "快速模式":
            delay_range = (0.5, 1.5)
        elif speed_mode == "慢速模式":
            delay_range = (2, 4)
        else:  # 正常速度
            delay_range = (1, 2)
        
        # 获取所有分类（使用扁平化列表）
        categories = self._get_flat_categories()
        logger.info(f"找到 {len(categories)} 个分类")
        
        all_policies = []
        
        # 遍历所有分类进行年份分割爬取
        logger.info("开始传统分类爬取...")
        if callback:
            callback("开始传统分类爬取...")
        
        for category_name, category_code in categories:
            if stop_callback and stop_callback():
                logger.info("用户已停止爬取")
                break
                
            logger.info(f"正在爬取分类: {category_name} (代码: {category_code})")
            if callback:
                callback(f"正在爬取分类: {category_name}")
            
            # 爬取当前分类的所有页面
            page_index = 1
            max_pages = 999999  # 最大页数限制（无上限）
            category_policies = []
            empty_page_count = 0  # 连续空页计数
            max_empty_pages = 20   # 最大连续空页数（大幅增加容忍度）
            
            while page_index <= max_pages and empty_page_count < max_empty_pages:
                if stop_callback and stop_callback():
                    logger.info("用户已停止爬取")
                    break
                    
                try:
                    # 使用基于网站分析的搜索参数
                    post_data = self._get_search_parameters(
                        keywords=keywords,
                        category_code=category_code,
                        page_index=page_index,
                        page_size=20,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    search_keyword = ' '.join(keywords) if keywords else ''
                    logger.debug(f"搜索关键词: '{search_keyword}', 分类: {category_code}, 页码: {page_index}")
                    
                    headers = self.headers.copy()
                    
                    resp, request_info = self.post_page(
                        self.search_url,
                        data=post_data,
                        headers=headers
                    )
                    
                    if resp and resp.status_code == 200:
                        self.monitor.record_request(self.search_url, success=True)
                        # 使用HTML解析而不是JSON解析，传递 policy_callback 实现流动显示
                        page_policies = self._parse_policy_list_html(resp.text, callback, stop_callback, category_name, policy_callback)
                    else:
                        error_msg = f"HTTP {resp.status_code}" if resp else "请求失败"
                        self.monitor.record_request(self.search_url, success=False, error_type=error_msg)
                        logger.warning(f"请求失败: {error_msg}")
                        break
                    
                    if len(page_policies) == 0:
                        empty_page_count += 1
                        logger.debug(f"分类[{category_name}] 第 {page_index} 页未获取到政策，连续空页: {empty_page_count}")
                        if empty_page_count >= max_empty_pages:
                            logger.info(f"分类[{category_name}] 连续 {max_empty_pages} 页无数据，停止翻页")
                            break
                    else:
                        empty_page_count = 0  # 重置空页计数
                    
                    # 更新总爬取数量
                    total_crawled += len(page_policies)
                    
                    if callback:
                        callback(f"分类[{category_name}] 第 {page_index} 页获取 {len(page_policies)} 条政策（累计爬取: {total_crawled} 条）")
                    
                    # 过滤关键词、时间并发送政策数据信号
                    filtered_policies = []
                    for policy in page_policies:
                        # 关键词过滤
                        if keywords and not self._is_policy_match_keywords(policy, keywords):
                            continue
                        
                        # 时间过滤
                        if enable_time_filter:
                            if self._is_policy_in_date_range(policy, dt_start, dt_end):
                                filtered_policies.append(policy)
                                # 调用 policy_callback 实时返回政策数据
                                if policy_callback:
                                    try:
                                        policy_callback(policy)
                                    except Exception as cb_error:
                                        logger.warning(f"调用 policy_callback 失败: {cb_error}")
                                # 发送政策数据信号，格式：POLICY_DATA:title|pub_date|source|content（兼容旧代码）
                                if callback:
                                    callback(f"POLICY_DATA:{policy.get('title', '')}|{policy.get('pub_date', '')}|{policy.get('source', '')}|{policy.get('content', '')}")
                        else:
                            # 不启用时间过滤，直接包含所有政策
                            filtered_policies.append(policy)
                            # 调用 policy_callback 实时返回政策数据
                            if policy_callback:
                                try:
                                    policy_callback(policy)
                                except Exception as cb_error:
                                    logger.warning(f"调用 policy_callback 失败: {cb_error}")
                            # 发送政策数据信号，格式：POLICY_DATA:title|pub_date|source|content（兼容旧代码）
                            if callback:
                                callback(f"POLICY_DATA:{policy.get('title', '')}|{policy.get('pub_date', '')}|{policy.get('source', '')}|{policy.get('content', '')}")
                    
                    # 更新过滤后数量
                    total_filtered += len(filtered_policies)
                    
                    if callback:
                        if enable_time_filter:
                            callback(f"分类[{category_name}] 第 {page_index} 页过滤后保留 {len(filtered_policies)} 条政策（累计过滤后: {total_filtered} 条）")
                        else:
                            callback(f"分类[{category_name}] 第 {page_index} 页保留 {len(filtered_policies)} 条政策（累计: {total_filtered} 条）")
                    
                    all_policies.extend(filtered_policies)
                    category_policies.extend(filtered_policies)
                    
                    # 检查是否到达最大页数
                    if page_index >= max_pages:
                        logger.info(f"分类[{category_name}] 已到达最大页数限制 ({max_pages} 页)，停止翻页")
                        break
                    
                    page_index += 1
                    
                    # 添加延时
                    if not disable_speed_limit:
                        delay = random.uniform(*delay_range)
                        time.sleep(delay)
                        
                except requests.exceptions.RequestException as e:
                    logger.error(f"请求失败: {e}", exc_info=True)
                    self.monitor.record_request(self.search_url, success=False, error_type=str(type(e).__name__))
                    break
                except Exception as e:
                    logger.error(f"请求未知错误: {e}", exc_info=True)
                    self.monitor.record_request(self.search_url, success=False, error_type="unknown")
                    break
            
            # 显示当前分类的统计信息
            logger.info(f"分类[{category_name}] 爬取完成，共获取 {len(category_policies)} 条政策")
            if callback:
                callback(f"分类[{category_name}] 爬取完成，共获取 {len(category_policies)} 条政策")
        
        # 应用去重机制
        logger.info("应用数据去重...")
        if callback:
            callback("应用数据去重...")
        
        unique_policies = self._deduplicate_policies(all_policies)
        
        # 最终统计
        total_saved = len(unique_policies)
        
        logger.info(f"爬取完成统计:")
        logger.info(f"  总爬取数量: {total_crawled} 条")
        if keywords:
            logger.info(f"  关键词过滤: {keywords}")
        if enable_time_filter:
            logger.info(f"  时间过滤: {start_date} 至 {end_date}")
            logger.info(f"  过滤后数量: {total_filtered} 条")
        logger.info(f"  去重后数量: {total_saved} 条")
        
        if callback:
            callback(f"爬取完成统计:")
            callback(f"  总爬取数量: {total_crawled} 条")
            if keywords:
                callback(f"  关键词过滤: {keywords}")
            if enable_time_filter:
                callback(f"  时间过滤: {start_date} 至 {end_date}")
                callback(f"  过滤后数量: {total_filtered} 条") 
            callback(f"  去重后数量: {total_saved} 条")
        
        return unique_policies
    
    def _parse_policy_list_record_search(self, soup, callback=None, stop_callback=None, category_name=None):
        """解析RecordSearch接口返回的政策列表 - 基于最新HTML结构分析"""
        policies = []
        
        # 基于最新测试结果，HTML结构发生了变化：
        # 政策项目直接使用class="list-title"的div，不再使用checkbox容器
        
        # 方法1：直接查找list-title容器（最新结构）
        policy_containers = soup.find_all('div', class_='list-title')
        logger.debug(f"找到 {len(policy_containers)} 个list-title容器")
        
        if policy_containers:
            logger.info(f"使用list-title容器解析，找到 {len(policy_containers)} 个政策项目")
            for container in policy_containers:
                # 检查是否停止
                if stop_callback and stop_callback():
                    logger.info("用户已停止爬取")
                    break
                
                try:
                    policy_data = self._parse_policy_item_record_search(container, category_name or "广东省政策")
                    if policy_data:
                        policies.append(policy_data)
                        
                        # 发送政策数据信号
                        if callback:
                            callback(f"获取政策: {policy_data.get('title', '未知标题')}")
                            
                except Exception as e:
                    logger.warning(f"解析政策项目失败: {e}", exc_info=True)
        
        # 方法2：如果list-title容器为空，尝试查找checkbox容器（备用方法）
        if not policy_containers:
            checkbox_containers = soup.find_all('div', class_='checkbox')
            logger.debug(f"备用方法：找到 {len(checkbox_containers)} 个checkbox容器")
            
            if checkbox_containers:
                logger.info(f"使用checkbox容器解析，找到 {len(checkbox_containers)} 个政策项目")
                for container in checkbox_containers:
                    # 检查是否停止
                    if stop_callback and stop_callback():
                        logger.info("用户已停止爬取")
                        break
                    
                    try:
                        policy_data = self._parse_policy_item_record_search(container, category_name or "广东省政策")
                        if policy_data:
                            policies.append(policy_data)
                            
                            # 发送政策数据信号
                            if callback:
                                callback(f"获取政策: {policy_data.get('title', '未知标题')}")
                                
                    except (ValueError, KeyError, AttributeError, TypeError) as e:
                        logger.warning(f"解析政策项目失败（数据格式错误）: {e}", exc_info=True)
                    except Exception as e:
                        logger.error(f"解析政策项目失败（未知错误）: {e}", exc_info=True)
        
        return policies
    
    def _parse_policy_item_record_search(self, item, category_name):
        """解析RecordSearch接口返回的单个政策项目 - 基于最新HTML结构分析"""
        try:
            logger.debug(f"开始解析政策项目: {item.name if hasattr(item, 'name') else 'unknown'}")
            
            # 方法1：如果item本身就是list-title容器，直接解析
            if item.get('class') and 'list-title' in item.get('class'):
                logger.debug("检测到list-title容器，直接解析")
                return self._parse_list_title_container(item, category_name)
            
            # 方法2：查找标准结构 (list-title + related-info)
            title_div = item.find('div', class_='list-title')
            if title_div:
                logger.debug("找到list-title div，使用标准结构解析")
                return self._parse_standard_structure(item, category_name)
            
            # 方法3：如果item本身就是checkbox容器，查找其中的list-title
            if 'checkbox' in item.get('class', []):
                logger.debug("检测到checkbox容器，查找list-title")
                title_div = item.find('div', class_='list-title')
                if title_div:
                    return self._parse_standard_structure(item, category_name)
            
            # 方法4：查找其他可能的结构
            logger.debug("未找到list-title div，尝试其他结构")
            
            # 查找所有可能的标题链接
            title_links = item.find_all('a')
            title = ""
            link = ""
            
            for a_link in title_links:
                link_text = a_link.get_text(strip=True)
                link_href = a_link.get('href', '')

                # 过滤掉无效的JavaScript链接
                if self._is_invalid_link(link_href):
                    continue

                # 检查是否是政策标题链接（包含特定关键词且是有效的政策链接）
                if (link_text and link_href and
                    link_href.startswith('/gdchinalaw/') and
                    (any(keyword in link_text for keyword in ['条例', '规定', '办法', '通知', '意见', '决定', '公告', '细则', '规则', '标准']) or
                     len(link_text) > 10)):  # 标题通常较长
                    title = link_text
                    link = link_href
                    break
            
            # 方法5：如果没找到链接，从整个item的文本中提取标题
            if not title or not link:
                item_text = item.get_text(strip=True)
                # 尝试从文本中提取标题（通常是第一行或包含关键词的部分）
                lines = item_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if (len(line) > 10 and 
                        any(keyword in line for keyword in ['条例', '规定', '办法', '通知', '意见', '决定', '公告', '细则', '规则', '标准', '管理', '实施'])):
                        title = line
                        break
            
            if not title:
                logger.debug("未找到有效的标题")
                return None
            
            logger.debug(f"找到标题: {title}")
            logger.debug(f"找到链接: {link}")
            
            # 处理链接
            if link and not link.startswith('http'):
                link = urljoin(self.base_url, link)
            
            # 查找相关信息 - 尝试多种方式
            info_text = ""
            
            # 方式1：查找related-info
            info_div = item.find('div', class_='related-info')
            if info_div:
                info_text = info_div.get_text(strip=True)
                logger.debug(f"从related-info获取信息: {info_text}")
            
            # 方式2：如果没找到，从整个item的文本中提取
            if not info_text:
                item_text = item.get_text(strip=True)
                # 移除标题文本，获取剩余信息
                if title in item_text:
                    info_text = item_text.replace(title, '').strip()
                    logger.debug(f"从item文本获取信息: {info_text}")
            
            # 解析信息（基于实际HTML结构：时效性 / 发文字号 / 公布日期 / 施行日期）
            validity = ""
            document_number = ""
            publish_date = ""
            effective_date = ""
            
            if info_text:
                # 基于实际HTML结构：使用 " / " 作为分隔符（已验证）
                # 格式：现行有效 / 发文字号 / 2021.10.30公布 / 2021.10.30施行
                parts = [p.strip() for p in info_text.split(' / ')]
                
                logger.debug(f"分割后的部分（共{len(parts)}段）: {parts}")
                
                # 第一部分：时效性（如"现行有效"）
                if len(parts) >= 1:
                    validity = parts[0].strip()
                
                # 第二部分：发文字号
                if len(parts) >= 2:
                    document_number = parts[1].strip()
                
                # 第三部分：公布日期（格式：YYYY.MM.DD公布 或 YYYY-MM-DD公布）
                if len(parts) >= 3:
                    publish_date_raw = parts[2].strip()
                    # 使用正则提取日期部分（支持 . 和 - 分隔符）
                    import re
                    date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', publish_date_raw)
                    if date_match:
                        year, month, day = date_match.groups()
                        publish_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:
                        # 如果正则失败，尝试直接使用（可能已经是标准格式）
                        publish_date = publish_date_raw.replace('公布', '').replace('发布', '').strip()
                
                # 第四部分：施行日期（格式：YYYY.MM.DD施行 或 YYYY-MM-DD施行）
                if len(parts) >= 4:
                    effective_date_raw = parts[3].strip()
                    # 使用正则提取日期部分
                    date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', effective_date_raw)
                    if date_match:
                        year, month, day = date_match.groups()
                        effective_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:
                        # 如果正则失败，尝试直接使用
                        effective_date = effective_date_raw.replace('施行', '').replace('生效', '').strip()
            
            # 如果没有解析到日期，尝试多种方法提取
            if not publish_date:
                import re
                # 方法1：从标题中查找日期
                date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', title)
                if date_match:
                    year, month, day = date_match.groups()
                    publish_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
                # 方法2：从整个item文本中查找日期（如果没有找到）
                if not publish_date:
                    item_full_text = item.get_text() if hasattr(item, 'get_text') else ''
                    # 尝试多种日期格式
                    date_patterns = [
                        r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})',  # YYYY.MM.DD 或 YYYY-MM-DD
                        r'(\d{4})年(\d{1,2})月(\d{1,2})日',  # YYYY年MM月DD日
                        r'(\d{4})/(\d{1,2})/(\d{1,2})',  # YYYY/MM/DD
                    ]
                    for pattern in date_patterns:
                        date_match = re.search(pattern, item_full_text)
                        if date_match:
                            if '年' in pattern:
                                year, month, day = date_match.groups()
                            else:
                                year, month, day = date_match.groups()
                            publish_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                            break
                
                # 方法3：从URL中提取日期（最后的手段）
                if not publish_date and link:
                    url_date_match = re.search(r'(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})', link)
                    if url_date_match:
                        year, month, day = url_date_match.groups()
                        publish_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            # 如果仍然没有日期，使用当前日期作为占位符（但标记为可能不准确）
            if not publish_date:
                logger.warning(f"无法从政策中提取发布日期: {title[:50]}")
                # 不设置日期，让GUI显示"未知"
            
            logger.debug(f"解析结果: 时效性={validity}, 发文字号={document_number}, 公布日期={publish_date}, 施行日期={effective_date}")
            
            # 尝试从HTML元素中提取真实的分类信息（如果category_name为空或不准确）
            extracted_category = category_name or ''
            if hasattr(item, 'find'):
                # 查找可能的分类元素
                category_selectors = [
                    'span.category',
                    'div.category',
                    '.policy-category',
                    '[class*="category"]',
                    '.type-label',
                    '.policy-type'
                ]
                for selector in category_selectors:
                    category_elem = item.select_one(selector)
                    if category_elem:
                        extracted_category = category_elem.get_text(strip=True)
                        if extracted_category:
                            logger.debug(f"从HTML提取到分类: {extracted_category}")
                            break
                
                # 如果还是空，尝试从父级元素查找
                if not extracted_category and hasattr(item, 'find_parent'):
                    parent = item.find_parent()
                    if parent:
                        for selector in category_selectors:
                            category_elem = parent.select_one(selector)
                            if category_elem:
                                extracted_category = category_elem.get_text(strip=True)
                                if extracted_category:
                                    break
            
            # 如果仍然没有分类，使用传入的分类名或默认值
            if not extracted_category:
                extracted_category = category_name or '未分类'
            
            # 构建政策数据 - 兼容系统格式
            policy_data = {
                'level': LEVEL_NAME,
                'title': title or '',
                'pub_date': publish_date or '',  # 使用解析的发布日期（公布日期）
                'doc_number': document_number or '',
                'source': link or '',  # 主要字段：source
                'url': link or '',  # 兼容字段
                'link': link or '',  # 兼容字段
                'content': f"标题: {title or ''}\n时效性: {validity or ''}\n发文字号: {document_number or ''}\n公布日期: {publish_date or ''}\n施行日期: {effective_date or ''}" if title else '',
                'category': extracted_category,  # 使用提取的分类信息
                'validity': validity or '',
                'effective_date': effective_date or '',
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            logger.debug(f"成功解析政策: {title}")
            return policy_data
            
        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.warning(f"解析政策项目失败（数据格式错误）: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"解析政策项目失败（未知错误）: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_list_title_container(self, item, category_name):
        """解析list-title容器 - 直接处理list-title div"""
        try:
            logger.debug("解析list-title容器")

            # 查找标题链接
            title_link = item.find('a')
            if not title_link:
                logger.debug("未找到标题链接")
                return None

            title = title_link.get_text(strip=True)
            if not title:
                logger.debug("标题为空")
                return None

            link = title_link.get('href', '')

            # 过滤掉无效的JavaScript链接
            if self._is_invalid_link(link):
                logger.debug(f"过滤掉无效链接: {link}")
                return None

            if link and not link.startswith('http'):
                link = urljoin(self.base_url, link)
            
            logger.debug(f"找到标题: {title}")
            logger.debug(f"找到链接: {link}")
            
            # 尝试从父级容器或兄弟元素获取相关信息
            parent = item.parent
            info_text = ""
            
            # 查找兄弟元素中的相关信息
            if parent:
                # 查找related-info兄弟元素
                related_info = parent.find('div', class_='related-info')
                if related_info:
                    info_text = related_info.get_text(strip=True)
                    logger.debug(f"从related-info获取信息: {info_text}")
                
                # 如果没有related-info，尝试从其他兄弟元素获取
                if not info_text:
                    siblings = parent.find_all('div')
                    for sibling in siblings:
                        if sibling != item and 'related' in sibling.get('class', []):
                            info_text = sibling.get_text(strip=True)
                            logger.debug(f"从兄弟元素获取信息: {info_text}")
                            break
            
            # 解析信息
            validity = ""
            document_number = ""
            publish_date = ""
            effective_date = ""
            
            if info_text:
                # 尝试多种分隔符
                if ' / ' in info_text:
                    parts = info_text.split(' / ')
                elif '，' in info_text:
                    parts = info_text.split('，')
                elif '；' in info_text:
                    parts = info_text.split('；')
                elif ' ' in info_text:
                    parts = info_text.split(' ')
                else:
                    parts = [info_text]
                
                logger.debug(f"分割后的部分: {parts}")
                
                if len(parts) >= 1:
                    validity = parts[0].strip()
                if len(parts) >= 2:
                    document_number = parts[1].strip()
                if len(parts) >= 3:
                    publish_date = parts[2].strip()
                    # 清理日期格式
                    import re
                    date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', publish_date)
                    if date_match:
                        year, month, day = date_match.groups()
                        publish_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                if len(parts) >= 4:
                    effective_date = parts[3].strip()
                    # 清理日期格式
                    date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', effective_date)
                    if date_match:
                        year, month, day = date_match.groups()
                        effective_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            # 如果没有解析到日期，尝试从标题中提取
            if not publish_date:
                import re
                date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', title)
                if date_match:
                    year, month, day = date_match.groups()
                    publish_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            logger.debug(f"解析结果: 时效性={validity}, 发文字号={document_number}, 公布日期={publish_date}, 施行日期={effective_date}")
            
            # 构建政策数据
            policy_data = {
                'level': LEVEL_NAME,
                'title': title or '',
                'pub_date': publish_date or '',
                'doc_number': document_number or '',
                'source': link or '',  # 主要字段：source
                'url': link or '',  # 兼容字段
                'link': link or '',  # 兼容字段
                'content': f"标题: {title or ''}\n时效性: {validity or ''}\n发文字号: {document_number or ''}\n公布日期: {publish_date or ''}\n施行日期: {effective_date or ''}" if title else '',
                'category': category_name or '',  # 确保category字段存在
                'validity': validity or '',
                'effective_date': effective_date or '',
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            logger.debug(f"成功解析政策: {title}")
            return policy_data
            
        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.warning(f"解析list-title容器失败（数据格式错误）: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"解析list-title容器失败（未知错误）: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_standard_structure(self, item, category_name):
        """解析标准HTML结构 (list-title + related-info)"""
        try:
            title_div = item.find('div', class_='list-title')
            title_link = title_div.find('h4').find('a') if title_div.find('h4') else None
            if not title_link:
                return None

            title = title_link.get_text(strip=True)
            if not title:
                return None

            link = title_link.get('href', '')

            # 过滤掉无效的JavaScript链接
            if self._is_invalid_link(link):
                logger.debug(f"过滤掉无效链接: {link}")
                return None

            if link and not link.startswith('http'):
                link = urljoin(self.base_url, link)
            
            info_div = item.find('div', class_='related-info')
            if not info_div:
                return None
            
            info_text = info_div.get_text(strip=True)
            
            # 解析信息
            validity = ""
            document_number = ""
            publish_date = ""
            effective_date = ""
            
            if info_text:
                parts = info_text.split(' / ')
                if len(parts) >= 1:
                    validity = parts[0].strip()
                if len(parts) >= 2:
                    document_number = parts[1].strip()
                if len(parts) >= 3:
                    publish_date = parts[2].strip()
                    # 清理日期格式，移除"公布"等后缀
                    import re
                    date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', publish_date)
                    if date_match:
                        year, month, day = date_match.groups()
                        publish_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                if len(parts) >= 4:
                    effective_date = parts[3].strip()
                    # 清理日期格式，移除"施行"等后缀
                    date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', effective_date)
                    if date_match:
                        year, month, day = date_match.groups()
                        effective_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            return {
                'level': LEVEL_NAME,
                'title': title,
                'pub_date': publish_date,
                'doc_number': document_number,
                'source': link,
                'content': f"标题: {title}\n时效性: {validity}\n发文字号: {document_number}\n公布日期: {publish_date}\n施行日期: {effective_date}",
                'category': category_name,
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'link': link,
                'validity': validity,
                'effective_date': effective_date
            }
            
        except Exception as e:
            logger.warning(f"解析标准结构失败: {e}", exc_info=True)
            return None
    
    def _parse_policy_list_direct(self, soup, callback=None, stop_callback=None, category_name=None):
        """直接解析政策列表页面（不依赖grouping-title结构）"""
        policies = []
        
        # 查找所有政策项目 - 尝试多种方式
        policy_items = []
        
        # 方式1：查找所有li标签
        all_li = soup.find_all('li')
        if all_li:
            policy_items = all_li
        
        # 方式2：如果li标签太多，尝试查找特定容器内的li
        if len(policy_items) > 200:  # 如果li标签太多，可能包含导航等
            # 查找可能包含政策列表的容器
            containers = soup.find_all(['div', 'ul'], class_=['list', 'content', 'result', 'policy-list'])
            for container in containers:
                if hasattr(container, 'find_all'):
                    li_items = container.find_all('li')  # type: ignore
                    if li_items and len(li_items) < len(policy_items):
                        policy_items = li_items
                        break
        
        # 方式3：如果还是找不到，尝试查找所有包含链接的li
        if not policy_items:
            all_li = soup.find_all('li')
            policy_items = [li for li in all_li if li.find('a')]
        
        if not policy_items:
            logger.debug("未找到政策项目")
            return []
        
        logger.debug(f"找到 {len(policy_items)} 个政策项目")
        
        for item in policy_items:
            # 检查是否停止
            if stop_callback and stop_callback():
                logger.info("用户已停止爬取")
                break
            
            try:
                policy_data = self._parse_policy_item(item, category_name or "广东省政策")
                if policy_data:
                    policies.append(policy_data)
                    
                    # 发送政策数据信号
                    if callback:
                        callback(f"POLICY_DATA:{policy_data['title']}|{policy_data['pub_date']}|{policy_data['source']}|{policy_data['content']}")
            
            except Exception as e:
                logger.warning(f"解析政策项目失败: {e}", exc_info=True)
                continue
        
        return policies
    
    def _parse_policy_item(self, item, category_name):
        """解析单个政策项目"""
        try:
            # 查找标题和链接 - 尝试多种方式
            title = ""
            link = ""
            
            # 方式1：查找class_='list-title'的div
            title_div = item.find('div', class_='list-title')
            if title_div:
                title_link = title_div.find('h4').find('a') if title_div.find('h4') else None
                if title_link:
                    title = title_link.get_text(strip=True)  # type: ignore
                    link = title_link.get('href', '')  # type: ignore
            
            # 方式2：如果方式1失败，查找所有a标签
            if not title or not link:
                all_links = item.find_all('a')
                for a_link in all_links:
                    if hasattr(a_link, 'get_text'):
                        link_text = a_link.get_text(strip=True)  # type: ignore
                        link_href = a_link.get('href', '')  # type: ignore

                        # 过滤掉无效的JavaScript链接
                        if self._is_invalid_link(link_href):
                            continue

                        # 检查是否是政策标题链接（通常包含特定关键词，且链接有效）
                        policy_keywords = ['条例', '规定', '办法', '通知', '意见', '决定', '公告', '实施', '办法', '细则']
                        valid_paths = ['/gddigui/', '/gdchinalaw/', '/gdfgwj/', '/gddifang/', '/regularation/', '/gdnormativedoc/']
                        if (link_text and link_href and
                            any(keyword in link_text for keyword in policy_keywords) and
                            any(path in link_href for path in valid_paths)):
                            title = link_text
                            link = link_href
                            break
            
            # 方式3：如果还是找不到，使用第一个有意义的链接
            if not title or not link:
                all_links = item.find_all('a')
                for a_link in all_links:
                    if hasattr(a_link, 'get_text'):
                        link_text = a_link.get_text(strip=True)  # type: ignore
                        link_href = a_link.get('href', '')  # type: ignore

                        # 过滤掉无效的JavaScript链接
                        if self._is_invalid_link(link_href):
                            continue

                        # 更严格的链接验证：必须是政策库链接且标题有意义
                        valid_paths = ['/gddigui/', '/gdchinalaw/', '/gdfgwj/', '/gddifang/', '/regularation/', '/gdnormativedoc/']
                        if (link_text and link_href and len(link_text) > 5 and
                            any(path in link_href for path in valid_paths)):
                            title = link_text
                            link = link_href
                            break
            
            if not title or not link:
                return None
            
            # 处理链接
            if link and not link.startswith('http'):
                link = urljoin(self.base_url, link)
            
            # 解析相关信息 - 尝试多种方式
            doc_number = ""
            pub_date = ""
            
            # 方式1：查找class_='related-info'的div
            info_div = item.find('div', class_='related-info')
            if info_div and hasattr(info_div, 'get_text'):
                info_text = info_div.get_text(strip=True)  # type: ignore
                # 提取发文字号和日期
                parts = info_text.split(' / ')
                if len(parts) >= 2:
                    doc_number = parts[1].strip()
                if len(parts) >= 3:
                    date_text = parts[2].strip()
                    date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', date_text)
                    if date_match:
                        pub_date = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
            
            # 方式2：如果方式1失败，从整个item的文本中提取
            if not doc_number or not pub_date:
                item_text = item.get_text(strip=True)  # type: ignore
                # 尝试从文本中提取日期
                date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', item_text)
                if date_match:
                    pub_date = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
            
            # 获取详细内容
            content = ""
            if link:
                content = self.get_policy_detail(link)
            
            return {
                'level': '广东省人民政府',
                'title': title,
                'pub_date': pub_date,
                'doc_number': doc_number,
                'source': link,
                'content': content,
                'category': category_name,  # 添加分类信息
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.warning(f"解析政策项目失败（数据格式错误）: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"解析政策项目失败（未知错误）: {e}", exc_info=True)
            return None
    
    def get_policy_detail(self, url):
        """获取政策详情内容（优化版：根据URL路径动态设置Referer）"""
        try:
            # 根据URL路径确定正确的Referer（不修改self.headers）
            headers = self.headers.copy()
            
            # 根据详情页URL的路径确定正确的Referer
            # URL格式：https://gd.pkulaw.com/{library}/{id}.html
            if url:
                if '/gddigui/' in url:
                    headers['Referer'] = 'https://gd.pkulaw.com/dfzfgz/adv'
                elif '/gddifang/' in url:
                    headers['Referer'] = 'https://gd.pkulaw.com/dfxfg/adv'
                elif '/regularation/' in url:
                    headers['Referer'] = 'https://gd.pkulaw.com/sfjs/adv'
                elif '/gdnormativedoc/' in url:
                    headers['Referer'] = 'https://gd.pkulaw.com/fljs/adv'
                elif '/gdchinalaw/' in url or '/gdfgwj/' in url:
                    headers['Referer'] = 'https://gd.pkulaw.com/china/adv'
                # 如果URL不匹配任何路径，保持默认Referer
            
            # 使用增强基础爬虫发送请求
            resp, request_info = self.get_page(url, headers=headers)
            
            if not resp:
                self.monitor.record_request(url, success=False, error_type="请求失败")
                return ""
            
            # 记录成功的详情页面请求
            self.monitor.record_request(url, success=True)
            
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # 尝试多种方式提取正文内容
            content = ""
            
            # 方法1：查找常见的正文容器
            content_selectors = [
                'div.content',
                'div.article-content', 
                'div.text',
                'div.article',
                'div.main-content',
                'div.detail-content',
                'div.policy-content',
                'div.law-content'
            ]
            
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    content = content_div.get_text(strip=True)
                    if content and len(content) > 100:  # 确保内容足够长
                        logger.debug(f"使用选择器 '{selector}' 获取到正文")
                        break
            
            # 方法2：如果方法1失败，尝试查找包含政策文本的div
            if not content or len(content) < 100:
                for div in soup.find_all('div'):
                    text = div.get_text(strip=True)
                    if (text and len(text) > 200 and 
                        ('第一条' in text or '第一章' in text or '总则' in text or 
                         '条' in text or '款' in text or '项' in text)):
                        content = text
                        logger.debug("通过关键词匹配获取到正文")
                        break
            
            # 方法3：如果还是失败，返回页面主要内容
            if not content or len(content) < 100:
                # 移除导航、页脚等无关内容
                for tag in soup.find_all(['nav', 'header', 'footer', 'script', 'style']):
                    tag.decompose()
                
                content = soup.get_text(strip=True)
                if content:
                    # 清理多余空白字符
                    content = re.sub(r'\s+', ' ', content)
                    logger.debug("使用页面主要内容作为正文")
            
            return content
        
        except requests.exceptions.Timeout as e:
            self.monitor.record_request(url, success=False, error_type="timeout")
            logger.warning(f"获取政策详情超时: {e}", exc_info=True)
            return ""
        except requests.exceptions.ConnectionError as e:
            self.monitor.record_request(url, success=False, error_type="connection_error")
            logger.error(f"获取政策详情连接错误: {e}", exc_info=True)
            return ""
        except (ValueError, KeyError, AttributeError) as e:
            self.monitor.record_request(url, success=False, error_type="parse_error")
            logger.warning(f"获取政策详情解析错误: {e}", exc_info=True)
            return ""
        except Exception as e:
            self.monitor.record_request(url, success=False, error_type="unknown")
            logger.error(f"获取政策详情失败: {e}", exc_info=True)
            return ""
    
    def get_crawler_status(self):
        """获取爬虫状态"""
        try:
            # 获取父类的统计信息
            base_stats = self.get_crawling_stats()
            
            # 确保base_stats是字典类型
            if not isinstance(base_stats, dict):
                base_stats = {}
            
            # 添加广东省爬虫特有的状态信息
            base_stats.update({
                'level': getattr(self, 'level', '广东省人民政府'),
                'speed_mode': getattr(self, 'speed_mode', '正常速度'),
                'monitor_stats': self.monitor.get_stats() if hasattr(self, 'monitor') and self.monitor else {},
                'proxy_enabled': getattr(self, 'enable_proxy', False),
            })
            
            # 确保有必需的字段（兼容爬虫状态对话框）
            if 'total_pages' not in base_stats:
                base_stats['total_pages'] = base_stats.get('progress', {}).get('total_pages', 0)
            if 'successful_pages' not in base_stats:
                base_stats['successful_pages'] = base_stats.get('successful_requests', 0)
            if 'failed_pages' not in base_stats:
                base_stats['failed_pages'] = base_stats.get('failed_requests', 0)
            
            return base_stats
        except Exception as e:
            logger.error(f"获取爬虫状态失败: {e}", exc_info=True)
            # 返回基本状态信息
            return {
                'level': getattr(self, 'level', '广东省人民政府'),
                'speed_mode': getattr(self, 'speed_mode', '正常速度'),
                'total_pages': 0,
                'successful_pages': 0,
                'failed_pages': 0,
                'is_running': getattr(self, 'is_running', False),
                'proxy_enabled': getattr(self, 'enable_proxy', False),
            }
    
    def save_to_db(self, policies):
        """保存政策到数据库"""
        for policy in policies:
            if isinstance(policy, dict):
                db.insert_policy(
                    policy['level'],
                    policy['title'],
                    policy['pub_date'],
                    policy['source'],
                    policy['content'],
                    policy['crawl_time'],
                    policy.get('category')  # 添加分类信息
                )
            elif isinstance(policy, (list, tuple)) and len(policy) >= 6:
                db.insert_policy(
                    policy[1],  # level
                    policy[2],  # title
                    policy[3],  # pub_date
                    policy[4],  # source
                    policy[5],  # content
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # crawl_time
                    policy[6] if len(policy) > 6 else None  # category
                )
    
    def _is_policy_in_date_range(self, policy, dt_start, dt_end):
        """检查政策是否在指定的时间范围内"""
        if not policy or 'pub_date' not in policy:
            return True  # 如果没有发布日期，默认包含
        
        pub_date = policy['pub_date']
        if not pub_date:
            return True  # 如果发布日期为空，默认包含
        
        try:
            # 解析发布日期
            if isinstance(pub_date, str):
                # 处理不同的日期格式
                if '.' in pub_date:
                    # 格式：2021.08.01 或 2021.10.30公布
                    # 先提取日期部分
                    import re
                    date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', pub_date)
                    if date_match:
                        year, month, day = date_match.groups()
                        dt_policy = datetime(int(year), int(month), int(day))
                    else:
                        return True  # 无法解析的日期格式，默认包含
                elif '-' in pub_date:
                    # 格式：2021-08-01
                    dt_policy = datetime.strptime(pub_date, '%Y-%m-%d')
                else:
                    return True  # 无法解析的日期格式，默认包含
            else:
                return True  # 非字符串格式，默认包含
            
            # 检查时间范围
            if dt_start and dt_policy < dt_start:
                return False
            if dt_end and dt_policy > dt_end:
                return False
            
            return True
            
        except ValueError:
            logger.warning(f"无法解析发布日期: {pub_date}")
            return True  # 解析失败，默认包含

    def _is_policy_match_keywords(self, policy, keywords):
        """检查政策是否匹配关键词"""
        if not keywords:
            return True
        
        # 确保keywords是列表格式
        if isinstance(keywords, str):
            keywords = [keywords]
        
        policy_title = policy.get('title', '').lower()
        policy_content = policy.get('content', '').lower()
        
        # 检查是否包含任意一个关键词
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in policy_title or keyword_lower in policy_content:
                logger.debug(f"政策匹配关键词 '{keyword}': {policy.get('title', '')}")
                return True
        
        logger.debug(f"政策不匹配关键词: {policy.get('title', '')}")
        return False

    def _parse_policy_list_optimized(self, soup, callback=None, stop_callback=None, category_name=None):
        """优化的政策列表解析 - 基于最新HTML结构分析"""
        policies = []

        # 基于HTML分析，直接查找政策列表项
        policy_items = soup.find_all('li')
        logger.debug(f"找到 {len(policy_items)} 个li元素")

        for item in policy_items:
            # 检查是否停止
            if stop_callback and stop_callback():
                logger.info("用户已停止爬取")
                break

            try:
                # 检查是否包含政策内容
                if self._is_policy_item(item):
                    policy_data = self._parse_policy_item_optimized(item, category_name)
                    if policy_data and not self._is_duplicate_policy(policy_data):
                        policies.append(policy_data)

                        # 发送政策数据信号
                        if callback:
                            callback(f"POLICY_DATA:{policy_data.get('title', '')}|{policy_data.get('pub_date', '')}|{policy_data.get('source', '')}|{policy_data.get('content', '')}|{policy_data.get('category', '')}")

            except Exception as e:
                logger.warning(f"解析政策项目失败: {e}", exc_info=True)

        return policies

    def _extract_policy_detail_content_and_title(self, html_content, url):
        """从详情页面提取内容和标题"""
        try:
            detail_soup = BeautifulSoup(html_content, 'html.parser')
            content = ""
            real_title = ""

            # 调试：输出页面基本信息
            logger.debug(f"详情页面URL: {url}")
            logger.debug(f"页面标题标签数量: {len(detail_soup.find_all('title'))}")
            logger.debug(f"H1标签数量: {len(detail_soup.find_all('h1'))}")
            logger.debug(f"H2标签数量: {len(detail_soup.find_all('h2'))}")
            logger.debug(f"H3标签数量: {len(detail_soup.find_all('h3'))}")

            # 方法1: 从ArticleTitle隐藏输入框获取（最优先，从网页分析发现这是最可靠的）
            article_title_input = detail_soup.find('input', {'id': 'ArticleTitle'})
            if article_title_input and article_title_input.get('value'):
                real_title = article_title_input.get('value').strip()
                logger.debug(f"从ArticleTitle输入框提取标题: '{real_title}'")

            # 方法2: 从页面标题获取
            if not real_title or real_title.startswith('政策ID:'):
                title_tag = detail_soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text(strip=True)
                    logger.debug(f"页面title内容: '{title_text}'")
                    # 清理标题（移除网站名称等）
                    if ' - ' in title_text:
                        real_title = title_text.split(' - ')[0].strip()
                    elif ' | ' in title_text:
                        real_title = title_text.split(' | ')[0].strip()
                    elif '_' in title_text:
                        real_title = title_text.split('_')[0].strip()
                    else:
                        real_title = title_text

            # 方法3: 从h2.title获取（从网页分析发现的重要位置）
            if not real_title or real_title.startswith('政策ID:'):
                h2_title = detail_soup.find('h2', class_='title')
                if h2_title:
                    h2_text = h2_title.get_text(strip=True)
                    logger.debug(f"从h2.title提取标题: '{h2_text}'")
                    if len(h2_text) > 10 and len(h2_text) < 200:
                        real_title = h2_text

            # 方法4: 从.MTitle获取（从网页分析发现的位置）
            if not real_title or real_title.startswith('政策ID:'):
                mtitle_elem = detail_soup.find(class_='MTitle')
                if mtitle_elem:
                    mtitle_text = mtitle_elem.get_text(strip=True)
                    logger.debug(f"从.MTitle提取标题: '{mtitle_text}'")
                    if len(mtitle_text) > 10 and len(mtitle_text) < 200:
                        real_title = mtitle_text

            # 方法5: 从所有<h1>、<h2>、<h3>获取
            if not real_title or real_title.startswith('政策ID:'):
                for tag_name in ['h1', 'h2', 'h3']:
                    headings = detail_soup.find_all(tag_name)
                    for heading in headings:
                        heading_text = heading.get_text(strip=True)
                        if (heading_text and
                            len(heading_text) > 5 and
                            len(heading_text) < 200 and
                            not heading_text.isdigit() and  # 排除纯数字
                            not heading_text.startswith('http') and  # 排除URL
                            '政策ID:' not in heading_text and  # 排除政策ID
                            not heading_text.lower().startswith(('page', '第'))):  # 排除分页信息
                            real_title = heading_text
                            logger.debug(f"从{tag_name}标签提取标题: '{real_title}'")
                            break
                    if real_title:
                        break

            # 方法2.5: 从strong标签或特定class获取
            if not real_title or real_title.startswith('政策ID:'):
                title_selectors = [
                    'div.title', 'div.article-title', 'div.policy-title',
                    'h4.title', 'strong', 'b', '.title'
                ]
                for selector in title_selectors:
                    title_elements = detail_soup.select(selector)
                    for element in title_elements:
                        element_text = element.get_text(strip=True)
                        logger.debug(f"尝试选择器 '{selector}' 找到文本: '{element_text}'")
                        if (element_text and
                            len(element_text) > 5 and
                            len(element_text) < 150 and
                            not element_text.isdigit() and
                            '政策ID:' not in element_text and
                            not element_text.startswith('http')):
                            real_title = element_text
                            break
                    if real_title:
                        break

            # 方法3: 从页面meta标签获取
            if not real_title or real_title.startswith('政策ID:'):
                meta_title = detail_soup.find('meta', attrs={'property': 'og:title'}) or \
                            detail_soup.find('meta', attrs={'name': 'title'})
                if meta_title and meta_title.get('content'):
                    meta_title_text = meta_title.get('content').strip()
                    logger.debug(f"Meta title: '{meta_title_text}'")
                    if len(meta_title_text) > 5 and len(meta_title_text) < 200:
                        real_title = meta_title_text

            # 方法4: 从特定的政策标题容器获取
            if not real_title or real_title.startswith('政策ID:'):
                # 尝试一些常见的政策标题容器
                policy_title_selectors = [
                    '.policy-title', '.document-title', '.article-title',
                    '.content-title', '.main-title', '.header-title',
                    '.doc-title', '.law-title'
                ]
                for selector in policy_title_selectors:
                    title_elem = detail_soup.select_one(selector)
                    if title_elem:
                        title_text = title_elem.get_text(strip=True)
                        logger.debug(f"政策标题容器 '{selector}' 找到: '{title_text}'")
                        if (title_text and len(title_text) > 8 and len(title_text) < 200 and
                            '政策ID:' not in title_text and not title_text.startswith('http')):
                            real_title = title_text
                            break

            # 方法5: 从正文第一段获取可能的标题
            if not real_title or real_title.startswith('政策ID:'):
                # 查找正文内容的第一段，看是否包含标题信息
                content_divs = detail_soup.select('div.content, div.article, div.detail, div.main-content, div.text')
                for content_div in content_divs[:2]:  # 只检查前两个内容容器
                    if content_div:
                        # 获取前几段文字
                        paragraphs = content_div.find_all('p')[:3]  # 前3段
                        for p in paragraphs:
                            p_text = p.get_text(strip=True)
                            logger.debug(f"检查段落文本: '{p_text[:100]}...'")
                            # 检查是否包含政策关键词且长度合适
                            if (p_text and len(p_text) > 10 and len(p_text) < 150 and
                                any(keyword in p_text for keyword in ['关于', '印发', '决定', '通知', '办法', '规定']) and
                                '政策ID:' not in p_text):
                                real_title = p_text
                                logger.debug(f"从正文提取到标题: '{real_title}'")
                                break
                        if real_title:
                            break

            # 方法6: 从JavaScript变量获取（从网页分析发现shareTitle变量）
            if not real_title or real_title.startswith('政策ID:'):
                # 查找页面中的JavaScript变量，特别是shareTitle
                scripts = detail_soup.find_all('script')
                for script in scripts:
                    script_text = script.get_text() if script else ""
                    # 查找常见的标题变量模式，特别是shareTitle
                    import re
                    title_patterns = [
                        r'var\s+shareTitle\s*=\s*["\']([^"\']+)["\']',  # shareTitle变量
                        r'shareTitle\s*=\s*["\']([^"\']+)["\']',        # shareTitle赋值
                        r'var\s+title\s*=\s*["\']([^"\']+)["\']',
                        r'title\s*:\s*["\']([^"\']+)["\']',
                        r'"title"\s*:\s*["\']([^"\']+)["\']',
                        r'document\.title\s*=\s*["\']([^"\']+)["\']'
                    ]
                    for pattern in title_patterns:
                        matches = re.findall(pattern, script_text, re.IGNORECASE)
                        for match in matches:
                            if (match and len(match) > 8 and len(match) < 200 and
                                '政策ID:' not in match and not match.startswith('http')):
                                logger.debug(f"从JavaScript变量提取到标题: '{match}'")
                                real_title = match
                                break
                        if real_title:
                            break
                    if real_title:
                        break

            # 方法7: 从URL路径或其他meta信息推断标题
            if not real_title or real_title.startswith('政策ID:'):
                # 尝试从URL或其他方式生成一个描述性标题
                # URL格式通常是: /gddigui/{policy_id}.html
                url_parts = url.split('/')
                if len(url_parts) >= 3:
                    library = url_parts[-2]  # gddigui, gddifang 等
                    policy_id = url_parts[-1].replace('.html', '')

                    # 根据库类型生成标题
                    library_names = {
                        'gddigui': '广东省地方性法规',
                        'gddifang': '广东省政府规章',
                        'gdfgwj': '广东省规范性文件',
                        'gdchinalaw': '中国法律法规',
                        'regularation': '广东省行政规范性文件'
                    }

                    library_name = library_names.get(library, f'{library}政策文件')
                    real_title = f'{library_name} - {policy_id[:16]}...'  # 使用部分ID作为标识
                    logger.debug(f"从URL推断生成标题: '{real_title}'")

            # 方法8: 从页面的data属性或其他自定义属性获取
            if not real_title or real_title.startswith('政策ID:'):
                # 查找页面中可能包含标题的data属性
                elements_with_data = detail_soup.find_all(attrs={'data-title': True})
                for elem in elements_with_data:
                    data_title = elem.get('data-title', '').strip()
                    if (data_title and len(data_title) > 5 and len(data_title) < 200 and
                        '政策ID:' not in data_title):
                        logger.debug(f"从data-title属性提取到标题: '{data_title}'")
                        real_title = data_title
                        break

            # 方法9: 最后的备用方案 - 从内容中提取第一行作为标题
            if not real_title or real_title.startswith('政策ID:'):
                if content:
                    # 从内容中提取第一行或第一段作为标题
                    lines = content.split('\n')[:5]  # 前5行
                    for line in lines:
                        line = line.strip()
                        if (line and len(line) > 15 and len(line) < 100 and
                            not line.startswith('http') and '政策ID:' not in line and
                            any(keyword in line for keyword in ['关于', '印发', '决定', '通知', '办法', '规定', '实施', '意见'])):
                            real_title = line
                            logger.debug(f"从内容第一行提取标题: '{real_title}'")
                            break

            # 方法10: 直接从页面文本内容提取标题（最直接的方法）
            if not real_title or real_title.startswith('政策ID:'):
                # 获取页面所有可见文本，从开头查找可能的标题
                all_visible_text = detail_soup.get_text(separator=' ', strip=True)
                logger.debug(f"页面总文本长度: {len(all_visible_text)}")

                # 按句子或段落分割
                text_parts = all_visible_text.split('。')[:10]  # 前10个句子

                for part in text_parts:
                    part = part.strip()
                    logger.debug(f"检查文本段: '{part[:50]}...'")

                    # 查找包含政策关键词且长度合适的文本
                    if (part and len(part) > 15 and len(part) < 150 and
                        any(keyword in part for keyword in ['关于', '印发', '决定', '通知', '办法', '规定', '实施', '意见']) and
                        not part.startswith('http') and '政策ID:' not in part):
                        real_title = part
                        logger.debug(f"从页面文本提取标题: '{real_title}'")
                        break

            # 如果所有方法都失败了，输出详细的调试信息
            if not real_title or real_title.startswith('政策ID:'):
                logger.warning(f"⚠️ 所有标题提取方法都失败了！")
                logger.warning(f"详情页面URL: {url}")
                logger.warning(f"HTML文档标题标签数量: {len(detail_soup.find_all('title'))}")
                logger.warning(f"HTML文档input标签数量: {len(detail_soup.find_all('input'))}")
                article_inputs = detail_soup.find_all('input', {'id': 'ArticleTitle'})
                logger.warning(f"ArticleTitle输入框数量: {len(article_inputs)}")
                if article_inputs:
                    for i, inp in enumerate(article_inputs):
                        logger.warning(f"  ArticleTitle[{i}] value: '{inp.get('value', 'NO_VALUE')}'")
                else:
                    logger.warning("  未找到任何ArticleTitle输入框")

                # 检查其他可能的标题来源
                h2_titles = detail_soup.find_all('h2', class_='title')
                logger.warning(f"h2.title标签数量: {len(h2_titles)}")
                for i, h2 in enumerate(h2_titles):
                    logger.warning(f"  h2.title[{i}]: '{h2.get_text(strip=True)}'")

                mtitle_elements = detail_soup.find_all(class_='MTitle')
                logger.warning(f".MTitle元素数量: {len(mtitle_elements)}")
                for i, mtitle in enumerate(mtitle_elements):
                    logger.warning(f"  .MTitle[{i}]: '{mtitle.get_text(strip=True)}'")

            # 提取内容
            content_selectors = [
                'div.content', 'div.article', 'div.detail', 'div.main-content',
                'div.text', 'div.article-content', 'div.policy-content'
            ]

            for selector in content_selectors:
                content_div = detail_soup.select_one(selector)
                if content_div:
                    # 移除脚本和样式元素
                    for script in content_div(["script", "style"]):
                        script.decompose()

                    text = content_div.get_text(separator='\n', strip=True)
                    if text and len(text) > 100:  # 内容至少100字符
                        content = text
                        break

            # 如果没找到内容，尝试整个body
            if not content:
                body = detail_soup.find('body')
                if body:
                    for script in body(["script", "style", "nav", "header", "footer"]):
                        script.decompose()
                    text = body.get_text(separator='\n', strip=True)
                    if text and len(text) > 100:
                        content = text

            return content, real_title

        except Exception as e:
            logger.warning(f"提取详情内容和标题失败: {e}")
            return "", ""

    def _is_policy_item(self, item):
        """判断是否为政策项目"""
        # 更宽松的判断条件，只要包含链接或文本内容就认为是政策项目
        has_title = item.find('div', class_='list-title') is not None
        has_checkbox = item.find('input', class_='checkbox') is not None
        has_policy_link = item.find('a', href=re.compile(r'/gdchinalaw/')) is not None
        has_any_link = item.find('a') is not None
        has_text = item.get_text(strip=True) and len(item.get_text(strip=True)) > 10
        
        # 只要满足任一条件就认为是政策项目
        return has_title or has_checkbox or has_policy_link or (has_any_link and has_text)
    
    def _parse_policy_item_optimized(self, item, category_name):
        """优化的单个政策项目解析"""
        try:
            # 查找标题
            title = ""
            link = ""
            
            # 方法1：从list-title容器获取
            title_div = item.find('div', class_='list-title')
            if title_div:
                title_link = title_div.find('a')
                if title_link:
                    title = title_link.get_text(strip=True)
                    link = title_link.get('href', '')

                    # 过滤掉无效的JavaScript链接
                    if link and self._is_invalid_link(link):
                        link = ''
            
            # 方法2：从整个item中查找所有链接
            if not title:
                title_links = item.find_all('a')
                for a_link in title_links:
                    link_text = a_link.get_text(strip=True)
                    link_href = a_link.get('href', '')

                    # 过滤掉无效的JavaScript链接
                    if self._is_invalid_link(link_href):
                        continue

                    # 检查是否是政策标题链接（更宽松的条件）
                    valid_paths = ['/gddigui/', '/gdchinalaw/', '/gdfgwj/', '/gddifang/', '/regularation/', '/gdnormativedoc/']
                    if (link_text and link_href and
                        any(path in link_href for path in valid_paths) and
                        len(link_text) > 3):
                        title = link_text
                        link = link_href
                        break
            
            # 方法3：如果还是没有找到，尝试从文本内容中提取
            if not title:
                # 获取所有文本内容
                all_text = item.get_text(strip=True)
                if all_text and len(all_text) > 10:
                    # 尝试提取第一行作为标题
                    lines = all_text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and len(line) > 5:
                            title = line
                            break
            
            if not title:
                return None
            
            # 处理链接
            if link and not link.startswith('http'):
                link = urljoin(self.base_url, link)
            
            # 查找相关信息
            info_text = ""
            info_div = item.find('div', class_='related-info')
            if info_div:
                info_text = info_div.get_text(strip=True)
            
            # 解析信息
            validity, document_number, publish_date, effective_date = self._parse_policy_info(info_text)
            
            # 获取政策正文内容
            content = ""
            if link:
                try:
                    logger.debug(f"正在获取政策正文: {title}")
                    content = self.get_policy_detail(link)
                    if content:
                        logger.debug(f"成功获取正文，长度: {len(content)} 字符")
                    else:
                        logger.warning(f"未获取到正文内容")
                except Exception as e:
                    logger.error(f"获取政策正文失败: {e}", exc_info=True)
                    content = ""
            
            # 构建层级分类名称
            full_category_name = self._get_full_category_name(category_name)
            
            # 构建政策数据 - 使用层级分类名称作为政策类型
            policy_data = {
                'level': LEVEL_NAME,
                'title': title,
                'pub_date': publish_date,
                'doc_number': document_number,
                'validity': validity,
                'effective_date': effective_date,
                'source': link,
                'content': content,  # 使用获取到的正文内容
                'category': full_category_name or "广东省政策",  # 使用层级分类名称作为政策类型
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # 验证政策格式是否符合预期
            if not self._is_policy_format_valid(policy_data):
                logger.debug(f"政策格式不符合预期，已过滤: {title[:50]}...")
                return None

            return policy_data
            
        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.warning(f"解析政策项目异常（数据格式错误）: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"解析政策项目异常（未知错误）: {e}", exc_info=True)
            return None

    def _is_policy_format_valid(self, policy_data):
        """验证政策数据格式是否符合预期

        Args:
            policy_data: 政策数据字典

        Returns:
            bool: True if 格式符合预期，False otherwise
        """
        if not isinstance(policy_data, dict):
            logger.debug("政策数据不是字典格式")
            return False

        # 必填字段验证
        required_fields = ['level', 'title', 'source', 'category', 'crawl_time']
        for field in required_fields:
            if field not in policy_data or policy_data[field] is None:
                logger.debug(f"缺少必填字段: {field}")
                return False

        # 标题验证
        title = policy_data.get('title', '').strip()
        if not title or len(title) < 3:
            logger.debug(f"标题无效: '{title}' (长度过短)")
            return False

        # 检查标题是否包含政策相关关键词（至少一个）
        policy_keywords = [
            '条例', '规定', '办法', '通知', '意见', '决定', '公告',
            '实施', '办法', '细则', '规则', '指南', '标准', '规范',
            '指导', '要求', '管理', '制度', '措施', '规划', '方案'
        ]
        if not any(keyword in title for keyword in policy_keywords):
            logger.debug(f"标题不包含政策关键词: '{title[:50]}...'")
            return False

        # 来源链接验证
        source = policy_data.get('source', '').strip()
        if not source or not isinstance(source, str):
            logger.debug("来源链接无效")
            return False

        # 检查是否是有效的政策链接（至少包含一个政策库路径且以.html结尾）
        valid_paths = ['/gddigui/', '/gdchinalaw/', '/gdfgwj/', '/gddifang/', '/regularation/', '/gdnormativedoc/']
        if not any(path in source for path in valid_paths):
            logger.debug(f"来源链接不是有效的政策链接: {source}")
            return False

        # 确保URL以.html结尾
        if not source.lower().endswith('.html'):
            logger.debug(f"来源链接不是.html格式: {source}")
            return False

        # 内容验证（可选，但如果有内容应该有一定长度）
        content = policy_data.get('content', '')
        if content and len(content.strip()) < 50:
            logger.debug(f"正文内容过短: {len(content)} 字符")
            return False

        # 文号格式验证（如果有文号）
        doc_number = policy_data.get('doc_number', '').strip()
        if doc_number:
            # 文号通常包含年份和序号，如：粤府办〔2023〕1号
            if len(doc_number) < 5 or not any(char.isdigit() for char in doc_number):
                logger.debug(f"文号格式异常: '{doc_number}'")
                return False

        # 发布日期验证（如果有日期）
        pub_date = policy_data.get('pub_date', '').strip()
        if pub_date:
            # 检查是否包含年份
            if not any(str(year) in pub_date for year in range(2000, 2030)):
                logger.debug(f"发布日期不包含有效年份: '{pub_date}'")
                return False

        # 分类验证
        category = policy_data.get('category', '').strip()
        if not category:
            logger.debug("分类信息为空")
            return False

        # 爬取时间验证
        crawl_time = policy_data.get('crawl_time', '')
        if not crawl_time or len(crawl_time) < 10:
            logger.debug(f"爬取时间格式异常: '{crawl_time}'")
            return False

        # 所有验证通过
        return True

    def _is_invalid_link(self, link):
        """检查链接是否无效

        Args:
            link: 要检查的链接

        Returns:
            bool: True if 链接无效，False otherwise
        """
        if not link or not isinstance(link, str):
            return True

        link = link.strip().lower()

        # 过滤掉JavaScript代码
        if link.startswith('javascript:') or 'javascript:' in link:
            return True

        # 过滤掉void(0)等无效链接
        if 'void(0)' in link or link == '#':
            return True

        # 过滤掉mailto:等非HTTP链接
        if link.startswith(('mailto:', 'tel:', 'ftp:', 'file:')):
            return True

        # 过滤掉明显无效的链接
        if link in ('', '/', '#', 'javascript:void(0)', 'javascript:void(0);'):
            return True

    def _get_category_api_config(self, category_code: str) -> Dict[str, str]:
        """根据分类代码获取对应的API配置

        Args:
            category_code: 分类代码

        Returns:
            dict: 包含 search_url, menu, library, class_flag, init_page, referer
        """
        # 确定API类型
        api_type = None
        for code_prefix, api_name in CATEGORY_API_MAP.items():
            if category_code and category_code.startswith(code_prefix):
                api_type = api_name
                break

        # 默认使用dfzfgz接口
        if not api_type:
            api_type = 'dfzfgz'
            logger.warning(f"未找到分类代码 {category_code} 的API映射，使用默认接口: {api_type}")

        # 从映射表获取配置
        api_config = API_PATH_MAP[api_type].copy()
        api_config.update({
            'search_url': f"{self.base_url}/{api_type}/search/RecordSearch",
            'init_page': f"{self.base_url}/{api_type}/adv",
            'referer': f'https://gd.pkulaw.com/{api_type}/adv'
        })

        return api_config

    def extract_years_from_page(self, html_content: str) -> List[Tuple[int, int]]:
        """从页面HTML中提取可用的公布年份及其数量

        年份筛选器位于 <div class="block" cluster_index="6"> 中
        每个年份链接格式: <a href="javascript:void(0);" cluster_code="2021">2021 (70)</a>

        Args:
            html_content: 页面HTML内容

        Returns:
            List[Tuple[int, int]]: [(年份, 数量), ...] 按年份倒序排列
        """
        years = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            import re

            # 方法1: 查找 cluster_index="6" 的block（公布年份筛选器）
            year_block = soup.find('div', class_='block', attrs={'cluster_index': '6'})
            if year_block:
                # 在block中查找所有年份链接（包括被隐藏的）
                year_links = year_block.find_all('a', cluster_code=True)
                year_pattern = re.compile(r'(\d{4})\s*\((\d+)\)')

                for link in year_links:
                    cluster_code = link.get('cluster_code', '')
                    text = link.get_text(strip=True)
                    match = year_pattern.search(text)
                    if match:
                        year = int(match.group(1))
                        count = int(match.group(2))
                        # cluster_code 应该等于年份
                        if cluster_code.isdigit() and int(cluster_code) == year:
                            years.append((year, count))

            # 方法2: 如果方法1失败，尝试查找 cluster_index="3"
            if not years:
                year_block = soup.find('div', class_='block', attrs={'cluster_index': '3'})
                if year_block:
                    h4 = year_block.find('h4', class_='filter-title')
                    if h4 and '公布年份' in h4.get_text():
                        year_links = year_block.find_all('a', cluster_code=True)
                        year_pattern = re.compile(r'(\d{4})\s*\((\d+)\)')

                        for link in year_links:
                            cluster_code = link.get('cluster_code', '')
                            text = link.get_text(strip=True)
                            match = year_pattern.search(text)
                            if match:
                                year = int(match.group(1))
                                count = int(match.group(2))
                                if cluster_code.isdigit() and int(cluster_code) == year:
                                    years.append((year, count))

            # 方法3: 通过"公布年份"标题查找
            if not years:
                year_title = soup.find(string=re.compile(r'公布年份'))
                if year_title:
                    # 查找父级block
                    parent_block = year_title.find_parent('div', class_='block')
                    if parent_block:
                        year_links = parent_block.find_all('a', cluster_code=True)
                        year_pattern = re.compile(r'(\d{4})\s*\((\d+)\)')

                        for link in year_links:
                            cluster_code = link.get('cluster_code', '')
                            text = link.get_text(strip=True)
                            match = year_pattern.search(text)
                            if match:
                                year = int(match.group(1))
                                count = int(match.group(2))
                                if cluster_code.isdigit() and int(cluster_code) == year:
                                    years.append((year, count))

            # 方法4: 更宽泛的搜索
            if not years:
                all_links = soup.find_all('a', cluster_code=True)
                year_pattern = re.compile(r'(\d{4})\s*\((\d+)\)')
                for link in all_links:
                    cluster_code = link.get('cluster_code', '')
                    text = link.get_text(strip=True)
                    match = year_pattern.search(text)
                    if match:
                        year = int(match.group(1))
                        count = int(match.group(2))
                        # 验证cluster_code是否为4位数字且等于年份
                        if cluster_code.isdigit() and len(cluster_code) == 4 and int(cluster_code) == year:
                            years.append((year, count))

        except Exception as e:
            logger.warning(f"提取年份信息失败: {e}")

        return sorted(years, reverse=True)  # 按年份倒序排列

    def _crawl_category_with_year_split(self, category_name: str, category_code: str, callback=None, stop_callback=None, policy_callback=None):
        """使用年份分割策略爬取单个分类

        Args:
            category_name: 分类名称
            category_code: 分类代码
            callback: 进度回调函数
            stop_callback: 停止回调函数
            policy_callback: 政策数据回调函数
        """
        logger.info(f"开始年份分割爬取: {category_name} (代码: {category_code})")

        # 第一步：获取该分类的年份信息
        api_config = self._get_category_api_config(category_code)
        years_info = []

        try:
            # 访问分类的搜索页面获取年份信息
            adv_url = api_config.get('init_page', f"{self.base_url}/{api_config['menu']}/adv")
            headers = self.headers.copy()
            if api_config.get('referer'):
                headers['Referer'] = api_config['referer']

            resp = self.session.get(adv_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                years_info = self.extract_years_from_page(resp.text)
                if years_info:
                    logger.info(f"分类 {category_name} 找到 {len(years_info)} 个年份: {', '.join([f'{y[0]}年({y[1]}条)' for y in years_info[:10]])}")
                else:
                    logger.warning(f"分类 {category_name} 未找到年份信息，将进行全量爬取")
            else:
                logger.warning(f"获取分类 {category_name} 年份信息失败: {resp.status_code}")

        except Exception as e:
            logger.warning(f"获取分类 {category_name} 年份信息异常: {e}")

        # 第二步：为每个年份创建爬取任务
        all_policies = []

        if years_info:
            # 有年份信息，按年份分割爬取
            logger.info(f"分类 {category_name} 使用年份分割策略，共 {len(years_info)} 个年份任务")

            for year, expected_count in years_info:
                if stop_callback and stop_callback():
                    logger.info("用户已停止爬取")
                    break

                logger.info(f"正在爬取 {category_name} - {year}年 (预计 {expected_count} 条)")

                if callback:
                    callback(f"正在爬取 {category_name} - {year}年")

                # 爬取该年份的数据
                year_policies = self._crawl_category_year(category_name, category_code, year, expected_count, callback, stop_callback, policy_callback)

                if year_policies:
                    all_policies.extend(year_policies)
                    logger.info(f"{category_name} - {year}年 获取到 {len(year_policies)} 条政策")
                else:
                    logger.warning(f"{category_name} - {year}年 未获取到政策数据")
        else:
            # 没有年份信息，全量爬取
            logger.info(f"分类 {category_name} 无年份信息，进行全量爬取")

            if callback:
                callback(f"正在全量爬取 {category_name}")

            year_policies = self._crawl_category_year(category_name, category_code, None, None, callback, stop_callback, policy_callback)

            if year_policies:
                all_policies.extend(year_policies)
                logger.info(f"{category_name} 全量爬取获取到 {len(year_policies)} 条政策")

        logger.info(f"分类 {category_name} 年份分割爬取完成，共获取 {len(all_policies)} 条政策")
        return all_policies

    def _crawl_category_year(self, category_name: str, category_code: str, year: Optional[int], expected_count: Optional[int],
                           callback=None, stop_callback=None, policy_callback=None):
        """爬取分类的指定年份数据

        Args:
            category_name: 分类名称
            category_code: 分类代码
            year: 年份（None表示全量）
            expected_count: 预期数量
            callback: 进度回调函数
            stop_callback: 停止回调函数
            policy_callback: 政策数据回调函数
        """
        year_info = f" - {year}年" if year else " - 全量"
        logger.debug(f"开始爬取 {category_name}{year_info}")

        policies = []
        page_index = 1
        max_pages = 999999  # 无上限
        empty_page_count = 0
        max_empty_pages = 20  # 连续空页数限制

        api_config = self._get_category_api_config(category_code)

        # 设置当前API配置，用于_parse_policy_list_html方法
        self.current_api_config = api_config

        while page_index <= max_pages and empty_page_count < max_empty_pages:
            if stop_callback and stop_callback():
                logger.info("用户已停止爬取")
                break

            try:
                # 构建搜索参数
                post_data = self._get_search_parameters(
                    keywords=None,
                    category_code=category_code,
                    page_index=page_index,
                    page_size=20,
                    start_date=None,
                    end_date=None,
                    filter_year=year
                )

                headers = self.headers.copy()

                resp, request_info = self.post_page(
                    self.search_url,
                    data=post_data,
                    headers=headers
                )

                if resp and resp.status_code == 200:
                    self.monitor.record_request(self.search_url, success=True)

                    # 解析页面政策
                    page_policies = self._parse_policy_list_html(resp.text, callback, stop_callback, category_name, policy_callback)

                    if page_policies:
                        policies.extend(page_policies)
                        empty_page_count = 0

                        if callback:
                            callback(f"{category_name}{year_info} 第 {page_index} 页获取 {len(page_policies)} 条政策")
                    else:
                        empty_page_count += 1
                        if empty_page_count >= max_empty_pages:
                            logger.info(f"{category_name}{year_info} 连续 {max_empty_pages} 页无数据，停止翻页")
                            break
                else:
                    error_msg = f"HTTP {resp.status_code}" if resp else "请求失败"
                    self.monitor.record_request(self.search_url, success=False, error_type=error_msg)
                    logger.warning(f"{category_name}{year_info} 第 {page_index} 页请求失败: {error_msg}")
                    empty_page_count += 1

            except Exception as e:
                logger.error(f"{category_name}{year_info} 第 {page_index} 页处理失败: {e}", exc_info=True)
                empty_page_count += 1

            page_index += 1

            # 添加延时
            time.sleep(1)

        logger.debug(f"{category_name}{year_info} 爬取完成，共获取 {len(policies)} 条政策")
        return policies

    def _parse_policy_info(self, info_text):
        """解析政策信息文本"""
        validity = ""
        document_number = ""
        publish_date = ""
        effective_date = ""
        
        if info_text:
            # 尝试多种分隔符
            if ' / ' in info_text:
                parts = info_text.split(' / ')
            elif '，' in info_text:
                parts = info_text.split('，')
            elif '；' in info_text:
                parts = info_text.split('；')
            elif ' ' in info_text:
                parts = info_text.split(' ')
            else:
                parts = [info_text]
            
            if len(parts) >= 1:
                validity = parts[0].strip()
            if len(parts) >= 2:
                document_number = parts[1].strip()
            if len(parts) >= 3:
                publish_date = parts[2].strip()
                # 清理日期格式
                date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', publish_date)
                if date_match:
                    year, month, day = date_match.groups()
                    publish_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            if len(parts) >= 4:
                effective_date = parts[3].strip()
                # 清理日期格式
                date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', effective_date)
                if date_match:
                    year, month, day = date_match.groups()
                    effective_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        return validity, document_number, publish_date, effective_date
    
    def _get_full_category_name(self, sub_category_name):
        """获取完整的层级分类名称"""
        if not sub_category_name:
            return "广东省政策"
        
        # 查找子分类对应的父分类
        for parent_name, parent_code, sub_categories in self._get_all_categories():
            for sub_name, sub_code in sub_categories:
                if sub_name == sub_category_name:
                    # 返回 "父级分类 > 子级分类" 格式
                    return f"{parent_name} > {sub_name}"
        
        # 如果没找到，返回原分类名称
        return sub_category_name
    
    def crawl_policies_optimized(self, keywords=None, callback=None, start_date=None, end_date=None, 
                               speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, policy_callback=None):
        """优化的政策爬取方法
        
        Args:
            keywords: 关键词列表
            callback: 进度回调函数
            start_date: 起始日期
            end_date: 结束日期
            speed_mode: 速度模式
            disable_speed_limit: 是否禁用速度限制
            stop_callback: 停止回调函数
            policy_callback: 政策数据回调函数，每解析到一条政策时调用
        """
        logger.info(f"开始优化爬取广东省政策，关键词: {keywords}, 时间范围: {start_date} 至 {end_date}, policy_callback={'已设置' if policy_callback else '未设置'}")
        
        # 解析时间范围
        dt_start = None
        dt_end = None
        enable_time_filter = False
        
        if start_date and end_date:
            try:
                dt_start = datetime.strptime(start_date, '%Y-%m-%d')
                dt_end = datetime.strptime(end_date, '%Y-%m-%d')
                enable_time_filter = True
                logger.info(f"启用时间过滤: {start_date} 至 {end_date}")
            except ValueError:
                logger.warning(f"时间格式错误，禁用时间过滤")
                enable_time_filter = False
        else:
            logger.info("未设置时间范围，禁用时间过滤")
            enable_time_filter = False
        
        # 统计信息
        total_crawled = 0
        total_filtered = 0
        total_saved = 0
        
        # 设置速度模式
        self.speed_mode = speed_mode
        if speed_mode == "快速模式":
            delay_range = (0.5, 1.5)
        elif speed_mode == "慢速模式":
            delay_range = (2, 4)
        else:  # 正常速度
            delay_range = (1, 2)
        
        # 获取所有分类（使用扁平化列表）
        categories = self._get_flat_categories()
        logger.info(f"找到 {len(categories)} 个分类")

        all_policies = []

        # 使用年份分割策略遍历所有分类进行爬取
        logger.info("开始年份分割分类爬取...")
        if callback:
            callback("开始年份分割分类爬取...")

        for category_name, category_code in categories:
            if stop_callback and stop_callback():
                logger.info("用户已停止爬取")
                break

            logger.info(f"正在使用年份分割策略爬取分类: {category_name} (代码: {category_code})")
            if callback:
                callback(f"正在使用年份分割策略爬取分类: {category_name}")

            # 使用年份分割策略爬取当前分类
            # 设置当前API配置，用于_parse_policy_list_html方法
            api_config = self._get_category_api_config(category_code)
            self.current_api_config = api_config

            category_policies = self._crawl_category_with_year_split(
                category_name, category_code, callback, stop_callback, policy_callback
            )

            # 更新总爬取数量
            total_crawled += len(category_policies)

            # 过滤关键词、时间并发送政策数据信号
            filtered_policies = []
            for policy in category_policies:
                # 关键词过滤
                if keywords and not self._is_policy_match_keywords(policy, keywords):
                    continue

                # 时间过滤
                if enable_time_filter:
                    if self._is_policy_in_date_range(policy, dt_start, dt_end):
                        filtered_policies.append(policy)
                        # 调用 policy_callback 实时返回政策数据
                        if policy_callback:
                            try:
                                policy_callback(policy)
                            except Exception as cb_error:
                                logger.warning(f"调用 policy_callback 失败: {cb_error}")
                        # 发送政策数据信号，格式：POLICY_DATA:title|pub_date|source|content（兼容旧代码）
                        if callback:
                            callback(f"POLICY_DATA:{policy.get('title', '')}|{policy.get('pub_date', '')}|{policy.get('source', '')}|{policy.get('content', '')}")
                else:
                    # 不启用时间过滤，直接包含所有政策
                    filtered_policies.append(policy)
                    # 调用 policy_callback 实时返回政策数据
                    if policy_callback:
                        try:
                            policy_callback(policy)
                        except Exception as cb_error:
                            logger.warning(f"调用 policy_callback 失败: {cb_error}")
                    # 发送政策数据信号，格式：POLICY_DATA:title|pub_date|source|content（兼容旧代码）
                    if callback:
                        callback(f"POLICY_DATA:{policy.get('title', '')}|{policy.get('pub_date', '')}|{policy.get('source', '')}|{policy.get('content', '')}")

            # 更新过滤后数量
            total_filtered += len(filtered_policies)

            if callback:
                if enable_time_filter:
                    callback(f"分类[{category_name}] 年份分割爬取完成，过滤后保留 {len(filtered_policies)} 条政策（累计过滤后: {total_filtered} 条）")
                else:
                    callback(f"分类[{category_name}] 年份分割爬取完成，保留 {len(filtered_policies)} 条政策（累计: {total_filtered} 条）")

            all_policies.extend(filtered_policies)

            # 显示当前分类的统计信息
            logger.info(f"分类[{category_name}] 年份分割爬取完成，共获取 {len(category_policies)} 条原始政策，过滤后保留 {len(filtered_policies)} 条")
            if callback:
                callback(f"分类[{category_name}] 年份分割爬取完成，共获取 {len(category_policies)} 条原始政策，过滤后保留 {len(filtered_policies)} 条")
        
        # 应用去重机制
        logger.info("应用数据去重...")
        if callback:
            callback("应用数据去重...")
        
        unique_policies = self._deduplicate_policies(all_policies)
        
        # 最终统计
        total_saved = len(unique_policies)
        
        logger.info(f"爬取完成统计:")
        logger.info(f"  总爬取数量: {total_crawled} 条")
        if keywords:
            logger.info(f"  关键词过滤: {keywords}")
        if enable_time_filter:
            logger.info(f"  时间过滤: {start_date} 至 {end_date}")
            logger.info(f"  过滤后数量: {total_filtered} 条")
        logger.info(f"  去重后数量: {total_saved} 条")
        
        if callback:
            callback(f"爬取完成统计:")
            callback(f"  总爬取数量: {total_crawled} 条")
            if keywords:
                callback(f"  关键词过滤: {keywords}")
            if enable_time_filter:
                callback(f"  时间过滤: {start_date} 至 {end_date}")
                callback(f"  过滤后数量: {total_filtered} 条") 
            callback(f"  去重后数量: {total_saved} 条")
        
        return unique_policies
    
    def crawl_policies_fast(self, keywords=None, callback=None, start_date=None, end_date=None, 
                           speed_mode="正常速度", disable_speed_limit=False, stop_callback=None):
        """广东省政策快速爬取方法 - 跳过分类遍历，直接搜索"""
        logger.info(f"开始快速爬取广东省政策，关键词: {keywords}, 时间范围: {start_date} 至 {end_date}")
        
        # 解析时间范围
        dt_start = None
        dt_end = None
        enable_time_filter = False
        
        if start_date and end_date:
            try:
                dt_start = datetime.strptime(start_date, '%Y-%m-%d')
                dt_end = datetime.strptime(end_date, '%Y-%m-%d')
                enable_time_filter = True
                logger.info(f"启用时间过滤: {start_date} 至 {end_date}")
            except ValueError:
                logger.warning(f"时间格式错误，禁用时间过滤")
                enable_time_filter = False
        else:
            logger.info("未设置时间范围，禁用时间过滤")
            enable_time_filter = False
        
        # 统计信息
        total_crawled = 0
        total_filtered = 0
        total_saved = 0
        
        # 会话轮换计数器
        session_rotation_counter = 0
        max_requests_per_session = 50  # 每50个请求轮换一次会话
        
        # 设置速度模式 - 增加延迟避免访问限制
        self.speed_mode = speed_mode
        if disable_speed_limit:
            delay_range = (1.0, 3.0)  # 增加延迟避免访问限制
        elif speed_mode == "快速模式":
            delay_range = (2.0, 5.0)  # 增加延迟
        elif speed_mode == "慢速模式":
            delay_range = (5.0, 10.0)  # 更慢的延迟
        else:  # 正常速度
            delay_range = (3.0, 7.0)  # 增加正常延迟
        
        all_policies = []
        
        # 使用多种搜索策略，确保获取更多数据
        logger.info("使用多种搜索策略...")
        if callback:
            callback("使用多种搜索策略...")
        
        # 策略1：使用高级搜索表单（最有效）
        try:
            logger.info("策略1：尝试高级搜索表单...")
            if callback:
                callback("策略1：尝试高级搜索表单...")
            
            # 使用更大的页面大小减少翻页次数
            page_size = 50  # 增加页面大小
            page_index = 1
            max_pages = 999999  # 最大页数限制（无上限）
            empty_page_count = 0
            max_empty_pages = 20  # 大幅增加连续空页容忍度，避免过早停止
            
            while page_index <= max_pages and empty_page_count < max_empty_pages:
                if stop_callback and stop_callback():
                    logger.info("用户已停止爬取")
                    break
                
                try:
                    # 使用优化的搜索参数
                    post_data = self._get_search_parameters(
                        keywords=keywords,
                        category_code=None,  # 不限制分类，搜索所有
                        page_index=page_index,
                        page_size=page_size,
                        start_date=start_date,
                        end_date=end_date,
                        old_page_index=page_index - 1 if page_index > 1 else None
                    )
                    
                    search_keyword = ' '.join(keywords) if keywords else ''
                    logger.debug(f"快速搜索: '{search_keyword}', 页码: {page_index}")
                    if callback:
                        callback(f"正在请求第 {page_index} 页...")
                    
                    # 使用带翻页校验的请求方法（从post_data中推断category_code）
                    category_code_from_params = None
                    # 尝试从ClassCodeKey中提取category_code（格式：,,,code,,,）
                    class_code_key = post_data.get('ClassCodeKey', '')
                    if class_code_key and class_code_key.count(',') >= 4:
                        parts = class_code_key.split(',')
                        if len(parts) >= 4 and parts[3]:
                            category_code_from_params = parts[3]
                    resp = self._request_page_with_check(page_index, post_data, page_index - 1 if page_index > 1 else None, category_code=category_code_from_params)
                    
                    if not resp:
                        logger.warning(f"第 {page_index} 页请求失败")
                        if callback:
                            callback(f"第 {page_index} 页请求失败，停止翻页")
                        break
                    
                    # 解析页面
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    
                    # 使用优化的解析方法
                    page_policies = self._parse_policy_list_optimized(soup, callback, stop_callback, "快速搜索")
                    
                    if len(page_policies) == 0:
                        empty_page_count += 1
                        logger.debug(f"第 {page_index} 页未获取到政策，连续空页: {empty_page_count}")
                        if empty_page_count >= max_empty_pages:
                            logger.info(f"连续 {max_empty_pages} 页无数据，停止翻页")
                            break
                    else:
                        empty_page_count = 0  # 重置空页计数
                    
                    # 更新总爬取数量
                    total_crawled += len(page_policies)
                    
                    # 会话轮换逻辑
                    session_rotation_counter += 1
                    if session_rotation_counter >= max_requests_per_session:
                        logger.debug(f"已请求 {session_rotation_counter} 次，轮换会话...")
                        if self._rotate_session():
                            session_rotation_counter = 0
                            logger.info("会话轮换成功")
                        else:
                            logger.warning("会话轮换失败，继续使用当前会话")
                    
                    if callback:
                        callback(f"第 {page_index} 页获取 {len(page_policies)} 条政策（累计爬取: {total_crawled} 条）")
                    
                    # 过滤关键词、时间（信号已在_parse_policy_list_optimized中发送）
                    filtered_policies = []
                    for policy in page_policies:
                        # 关键词过滤
                        if keywords and not self._is_policy_match_keywords(policy, keywords):
                            continue
                        
                        # 时间过滤
                        if enable_time_filter:
                            if self._is_policy_in_date_range(policy, dt_start, dt_end):
                                filtered_policies.append(policy)
                        else:
                            # 不启用时间过滤，直接包含所有政策
                            filtered_policies.append(policy)
                    
                    # 更新过滤后数量
                    total_filtered += len(filtered_policies)
                    
                    if callback:
                        if enable_time_filter:
                            callback(f"第 {page_index} 页过滤后保留 {len(filtered_policies)} 条政策（累计过滤后: {total_filtered} 条）")
                        else:
                            callback(f"第 {page_index} 页保留 {len(filtered_policies)} 条政策（累计: {total_filtered} 条）")
                    
                    all_policies.extend(filtered_policies)
                    
                    # 检查是否到达最大页数
                    if page_index >= max_pages:
                        logger.info(f"已到达最大页数限制 ({max_pages} 页)，停止翻页")
                        break
                    
                    page_index += 1
                    
                    # 添加延时（快速模式下延迟更短）
                    if not disable_speed_limit:
                        delay = random.uniform(*delay_range)
                        time.sleep(delay)
                        
                except requests.exceptions.Timeout as e:
                    logger.warning(f"请求超时: {e}", exc_info=True)
                    self.monitor.record_request(self.search_url, success=False, error_type="timeout")
                    if callback:
                        callback(f"请求超时，等待3秒后重试...")
                    time.sleep(3)
                    continue
                    
                except requests.exceptions.ConnectionError as e:
                    logger.error(f"连接错误: {e}", exc_info=True)
                    self.monitor.record_request(self.search_url, success=False, error_type="connection_error")
                    if callback:
                        callback(f"连接错误，等待3秒后重试...")
                    time.sleep(3)
                    continue
                    
                except requests.exceptions.HTTPError as e:
                    error_code = getattr(e.response, 'status_code', None)
                    logger.error(f"HTTP错误 {error_code}: {e}", exc_info=True)
                    self.monitor.record_request(self.search_url, success=False, error_type=f"http_{error_code}")
                    
                    # 如果是反爬虫相关错误，增加延时
                    if error_code in [403, 429]:
                        logger.warning(f"检测到反爬虫限制，等待5秒后重试...")
                        if callback:
                            callback(f"检测到访问限制，等待重试...")
                        time.sleep(5)
                        continue
                    else:
                        # 其他HTTP错误，直接退出
                        break
                        
                except Exception as e:
                    logger.error(f"未知错误: {e}", exc_info=True)
                    import traceback
                    logger.error(f"详细错误信息: {traceback.format_exc()}")
                    self.monitor.record_request(self.search_url, success=False, error_type="unknown")
                    # 未知错误，退出循环
                    break
                    
                    # 其他错误，记录并继续
                    logger.warning(f"未知错误，跳过当前页面")
                    if callback:
                        callback(f"页面处理出错，跳过继续...")
                    break
            
            logger.info(f"策略1完成，共获取 {len(all_policies)} 条政策")
            if callback:
                callback(f"策略1完成，共获取 {len(all_policies)} 条政策")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"策略1请求失败: {e}", exc_info=True)
        except (ValueError, KeyError, AttributeError) as e:
            logger.warning(f"策略1解析失败: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"策略1失败: {e}", exc_info=True)
        
        
        # 应用去重机制
        logger.info("应用数据去重...")
        if callback:
            callback("应用数据去重...")
        
        unique_policies = self._deduplicate_policies(all_policies)
        
        # 最终统计
        total_saved = len(unique_policies)
        
        logger.info(f"快速爬取完成统计:")
        logger.info(f"  总爬取数量: {total_crawled} 条")
        logger.info(f"  过滤后数量: {total_filtered} 条")
        logger.info(f"  最终保存数量: {total_saved} 条")
        logger.info(f"  去重率: {(len(all_policies) - len(unique_policies)) / len(all_policies) * 100:.1f}%" if all_policies else "0%")
        
        if callback:
            callback(f"快速爬取完成！共获取 {total_saved} 条政策")
        
        return unique_policies

class GuangdongMultiThreadSpider(MultiThreadBaseCrawler):
    """广东省多线程爬虫"""
    
    def __init__(self, max_workers=4):
        super().__init__(max_workers, enable_proxy=True)
        
        # 设置广东省爬虫特定的headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        self.level = "广东省人民政府"  # 添加level属性
        
        # 导入必要的模块
        import string
        self.string = string
        
        logger.info(f"初始化多线程爬虫，最大线程数: {max_workers}")
    
    def _prepare_tasks(self):
        """准备多线程任务 - 只使用成功的搜索策略"""
        tasks = []
        
        # 只使用成功的搜索策略，不按分类遍历
        task_data = {
            'task_id': 'guangdong_search',
            'category_name': '广东省政策',
            'category_code': None,  # 不使用分类代码
            'description': '使用成功的高级搜索策略'
        }
        tasks.append(task_data)

        logger.info(f"准备完成，共 {len(tasks)} 个任务，使用 {self.max_workers} 个线程")
        return tasks

    def _get_flat_categories(self):
        """获取扁平化的分类列表"""
        # 这里需要从GuangdongSpider继承的方法
        # 为了简化，我们直接定义分类
        categories = [
            ('综合政务', '579/580'),
            ('土地管理', '579/581'),
            ('自然资源确权登记', '579/582'),
            ('地质', '579/583'),
            ('地质环境管理', '579/584'),
            ('矿产资源管理', '579/585'),
            ('海洋管理', '579/586'),
            ('测绘地理信息管理', '579/587'),
            ('法律', '569/570'),
            ('司法解释', '569/577')
        ]
        return categories

    def crawl_policies_multithread(self, keywords=None, callback=None, start_date=None, end_date=None, 
                                  speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, max_workers=None):
        """多线程爬取政策（兼容原有接口）"""
        # 使用基类的crawl_multithread方法
        return self.crawl_multithread(
            callback=callback,
            stop_callback=stop_callback,
            max_workers=max_workers,
            start_date=start_date,
            end_date=end_date
        )
    
    def get_multithread_stats(self):
        """获取多线程统计信息"""
        return super().get_multithread_stats()
    
    def get_error_summary(self):
        """获取错误摘要"""
        return super().get_error_summary()
    
    def crawl_multithread(self, callback=None, stop_callback=None, max_workers=None, start_date=None, end_date=None):
        """多线程爬取（兼容原有接口）"""
        return super().crawl_multithread(
            callback=callback,
            stop_callback=stop_callback,
            max_workers=max_workers,
            start_date=start_date,
            end_date=end_date
        )
    
    def _execute_task(self, task_data: Dict, session, lock, callback: Optional[Callable] = None) -> List[Dict]:
        """执行具体任务 - 使用成功的搜索策略"""
        
        task_id = task_data['task_id']
        category_name = task_data['category_name']
        description = task_data['description']
        
        thread_name = threading.current_thread().name
        
        if callback:
            callback(f"线程 {thread_name} 开始爬取 {description}")
        
        # 创建临时的爬虫实例来使用原有的爬取逻辑
        temp_spider = GuangdongSpider()
        temp_spider.headers = self.headers
        temp_spider.enable_proxy = self.enable_proxy
        
        # 使用共享代理系统 - 只在启用代理时
        if self.enable_proxy:
            try:
                from .proxy_pool import get_shared_proxy, report_shared_proxy_result
                temp_spider.get_shared_proxy = get_shared_proxy
                temp_spider.report_shared_proxy_result = report_shared_proxy_result
                logger.info(f"线程 {thread_name} 启用代理支持")
            except (requests.exceptions.RequestException, ValueError, KeyError) as e:
                logger.warning(f"线程 {thread_name} 代理初始化失败: {e}", exc_info=True)
                temp_spider.enable_proxy = False
            except Exception as e:
                logger.error(f"线程 {thread_name} 代理初始化未知错误: {e}", exc_info=True)
                temp_spider.enable_proxy = False
        else:
            logger.info(f"线程 {thread_name} 禁用代理，使用直接连接")
        
        # 使用配置中的URL（已在__init__中设置）
        temp_spider.base_url = self.base_url
        temp_spider.search_url = self.search_url
        
        # 确保有monitor对象
        if hasattr(self, 'monitor') and self.monitor:
            temp_spider.monitor = self.monitor
        else:
            # 创建一个简单的monitor对象
            from .monitor import CrawlerMonitor
            temp_spider.monitor = CrawlerMonitor()
        
        # 初始化会话
        temp_spider._init_session()
        
        # 使用成功的搜索策略 - 直接调用单线程的成功方法
        policies = []
        
        try:
            if callback:
                callback(f"线程 {thread_name} 使用年份分割策略爬取 {description}...")

            # 使用年份分割策略
            category_policies = temp_spider._crawl_category_with_year_split(
                category_name,
                task_data.get('category_code', ''),
                callback,
                lambda: self.check_stop() if hasattr(self, 'check_stop') else False
            )

            if category_policies:
                policies.extend(category_policies)
                if callback:
                    callback(f"线程 {thread_name} 获取到 {len(category_policies)} 条政策")
            else:
                if callback:
                    callback(f"线程 {thread_name} 未获取到政策")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"线程 {thread_name} 执行任务时请求错误: {e}", exc_info=True)
            if callback:
                callback(f"线程 {thread_name} 执行失败: {e}")
        except (ValueError, KeyError, AttributeError) as e:
            logger.warning(f"线程 {thread_name} 执行任务时解析错误: {e}", exc_info=True)
            if callback:
                callback(f"线程 {thread_name} 执行失败: {e}")
        except Exception as e:
            logger.error(f"线程 {thread_name} 执行任务时未知错误: {e}", exc_info=True)
            if callback:
                callback(f"线程 {thread_name} 执行失败: {e}")
        
        if callback:
            callback(f"线程 {thread_name} 爬取完成，共获取{len(policies)}条政策")
        
        return policies

class GuangdongPolicyCrawler(GuangdongSpider):
    """广东省政策爬虫 - 兼容性包装类"""
    
    def __init__(self):
        super().__init__()
    
    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None, 
                      speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, policy_callback=None):
        """兼容性方法，调用优化的爬取方法"""
        return self.crawl_policies_optimized(
            keywords=keywords,
            callback=callback,
            start_date=start_date,
            end_date=end_date,
            speed_mode=speed_mode,
            disable_speed_limit=disable_speed_limit,
            stop_callback=stop_callback,
            policy_callback=policy_callback
        )

if __name__ == "__main__":
    spider = GuangdongSpider()
    policies = spider.crawl_policies(['规划', '空间', '用地'])
    spider.save_to_db(policies)
    logger.info(f"爬取到 {len(policies)} 条广东省政策") 