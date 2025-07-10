#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
广东省政策爬虫模块 - 优化版本
爬取广东省法规规章数据库 (https://gd.pkulaw.com/)
解决重复爬取和解析问题
"""

# 机构名称常量
LEVEL_NAME = "广东省人民政府"

import requests
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin, urlparse
import urllib3
import hashlib

# 启用SSL安全验证
# 移除SSL警告禁用，确保安全连接

from .anti_crawler import AntiCrawlerManager
from .monitor import CrawlerMonitor
from ..core import database as db

class GuangdongSpider:
    """广东省政策爬虫 - 使用真实API接口"""
    
    def __init__(self):
        self.base_url = "https://gd.pkulaw.com"
        self.search_url = "https://gd.pkulaw.com/china/search/RecordSearch"
        
        # 初始化防反爬虫组件
        self.anti_crawler = AntiCrawlerManager()
        self.monitor = CrawlerMonitor()
        
        # 创建会话
        self.session = requests.Session()
        # 启用SSL证书验证，确保安全连接
        self.session.verify = True
        
        # 设置基础请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://gd.pkulaw.com',
            'Referer': 'https://gd.pkulaw.com/china/adv'
        }
        
        # 设置速度模式
        self.speed_mode = "正常速度"
        
        # 初始化会话
        self._init_session()
        
        # 添加去重缓存
        self.seen_policy_ids = set()
        self.seen_policy_hashes = set()
    
    def _init_session(self):
        """初始化会话"""
        self.session = requests.Session()
        
        # 更新headers，添加必要的AJAX和浏览器标识
        self.headers.update({
            'Origin': 'https://gd.pkulaw.com',
            'Referer': 'https://gd.pkulaw.com/china/adv',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        })
        
        self.session.headers.update(self.headers)
        
        # 设置Cookie
        self.session.cookies.set('JSESSIONID', '1234567890ABCDEF', domain='gd.pkulaw.com')
        
        # 访问首页获取必要的Cookie
        try:
            resp = self.session.get(self.base_url, timeout=10)
            if resp.status_code == 200:
                self.monitor.record_request(self.base_url, success=True)
                print("成功访问首页，获取必要Cookie")
            else:
                self.monitor.record_request(self.base_url, success=False, error_type=f"HTTP {resp.status_code}")
                print(f"访问首页失败，状态码: {resp.status_code}")
        except Exception as e:
            self.monitor.record_request(self.base_url, success=False, error_type=str(e))
            print(f"访问首页异常: {e}")
    
    def _request_page_with_check(self, page_index, search_params, old_page_index=None):
        """带翻页校验的页面请求"""
        try:
            # 1. 先请求翻页校验接口
            check_url = "https://gd.pkulaw.com/VerificationCode/GetRecordListTurningLimit"
            check_headers = self.headers.copy()
            check_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
            
            print(f"请求翻页校验接口: 第{page_index}页")
            try:
                check_resp = self.session.post(check_url, headers=check_headers, timeout=15)
                if check_resp.status_code == 200:
                    self.monitor.record_request(check_url, success=True)
                else:
                    self.monitor.record_request(check_url, success=False, error_type=f"HTTP {check_resp.status_code}")
                print(f"翻页校验响应状态码: {check_resp.status_code}")
            except Exception as check_error:
                self.monitor.record_request(check_url, success=False, error_type=str(check_error))
                print(f"翻页校验请求失败: {check_error}")
                # 翻页校验失败不影响主请求，继续执行
            
            # 2. 再请求数据接口
            search_url = "https://gd.pkulaw.com/china/search/RecordSearch"
            search_headers = self.headers.copy()
            search_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
            
            # 更新搜索参数中的OldPageIndex
            if old_page_index is not None:
                search_params['OldPageIndex'] = str(old_page_index)
            
            print(f"请求数据接口: 第{page_index}页")
            search_resp = self.session.post(search_url, data=search_params, headers=search_headers, timeout=30)
            
            print(f"数据接口响应状态码: {search_resp.status_code}")
            
            if search_resp.status_code == 200:
                self.monitor.record_request(search_url, success=True)
                print(f"第{page_index}页请求成功")
                return search_resp
            else:
                self.monitor.record_request(search_url, success=False, error_type=f"HTTP {search_resp.status_code}")
                print(f"数据请求失败，状态码: {search_resp.status_code}")
                return None
                
        except Exception as e:
            print(f"页面请求异常: {e}")
            import traceback
            print(f"详细错误信息: {traceback.format_exc()}")
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
    
    def _get_search_parameters(self, keywords=None, category_code=None, page_index=1, page_size=20, start_date=None, end_date=None, old_page_index=None):
        """获取搜索参数 - 基于网站表单分析结果"""
        # 基于网站表单分析，使用正确的参数名称
        search_params = {
            'Menu': 'china',
            'Keywords': keywords[0] if keywords and len(keywords) > 0 else '',
            'SearchKeywordType': 'Title',
            'MatchType': 'Exact',
            'RangeType': 'Piece',
            'Library': 'gdchinalaw',
            'ClassFlag': 'gdchinalaw',
            'GroupLibraries': '',
            'QueryOnClick': 'False',
            'AfterSearch': 'False',
            'pdfStr': '',
            'pdfTitle': '',
            'IsAdv': 'True',
            'ClassCodeKey': f',,,{category_code},,,' if category_code else ',,,,,,',
            'GroupByIndex': '0',
            'OrderByIndex': '0',
            'ShowType': 'Default',
            'GroupValue': '',
            'AdvSearchDic.Title': '',
            'AdvSearchDic.CheckFullText': '',
            'AdvSearchDic.IssueDepartment': '',
            'AdvSearchDic.DocumentNO': '',
            'AdvSearchDic.IssueDate': start_date or '',
            'AdvSearchDic.ImplementDate': end_date or '',
            'AdvSearchDic.TimelinessDic': '',
            'AdvSearchDic.EffectivenessDic': '',
            'TitleKeywords': ' '.join(keywords) if keywords else '',
            'FullTextKeywords': ' '.join(keywords) if keywords else '',
            'Pager.PageIndex': str(page_index),  # 使用1基索引
            'Pager.PageSize': str(page_size),
            'QueryBase64Request': '',
            'VerifyCodeResult': '',
            'isEng': 'chinese',
            'OldPageIndex': str(old_page_index) if old_page_index is not None else '',
            'newPageIndex': '',
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
        
        print(f"去重前: {len(policies)} 条政策")
        print(f"去重后: {len(unique_policies)} 条政策")
        print(f"重复率: {(len(policies) - len(unique_policies)) / len(policies) * 100:.1f}%" if policies else "0%")
        
        return unique_policies
    
    def _try_different_search_strategies(self, keywords=None, callback=None, stop_callback=None):
        """尝试不同的搜索策略来获取更多数据"""
        print("尝试不同的搜索策略...")
        
        strategies = [
            # 策略1：使用高级搜索表单
            {
                'name': '高级搜索表单',
                'url': f"{self.base_url}/china/search/RecordSearch",
                'method': 'POST',
                'data': self._get_search_parameters(keywords=keywords)
            },
            # 策略2：使用分类搜索
            {
                'name': '分类搜索',
                'url': f"{self.base_url}/china/search/ClassSearch",
                'method': 'POST',
                'data': self._get_search_parameters(keywords=keywords)
            },
            # 策略3：直接访问分类页面
            {
                'name': '直接分类页面',
                'url': f"{self.base_url}/dfxfg/",
                'method': 'GET',
                'data': None
            },
            # 策略4：使用简单搜索
            {
                'name': '简单搜索',
                'url': f"{self.base_url}/china/search/SimpleSearch",
                'method': 'POST',
                'data': {
                    'Keywords': ' '.join(keywords) if keywords else '',
                    'Library': 'gdchinalaw'
                }
            }
        ]
        
        all_policies = []
        
        for strategy in strategies:
            if stop_callback and stop_callback():
                break
                
            try:
                print(f"尝试策略: {strategy['name']}")
                if callback:
                    callback(f"尝试搜索策略: {strategy['name']}")
                
                if strategy['method'] == 'POST':
                    resp = self.session.post(strategy['url'], data=strategy['data'], timeout=30)
                else:
                    resp = self.session.get(strategy['url'], timeout=30)
                
                if resp.status_code == 200:
                    self.monitor.record_request(strategy['url'], success=True)
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    policies = self._parse_policy_list_record_search(soup, callback, stop_callback, strategy['name'])
                    
                    if policies:
                        print(f"策略 {strategy['name']} 获取到 {len(policies)} 条政策")
                        all_policies.extend(policies)
                    else:
                        print(f"策略 {strategy['name']} 未获取到政策")
                else:
                    self.monitor.record_request(strategy['url'], success=False, error_type=f"HTTP {resp.status_code}")
                    print(f"策略 {strategy['name']} 请求失败，状态码: {resp.status_code}")
                    
            except Exception as e:
                print(f"策略 {strategy['name']} 执行失败: {e}")
                continue
        
        return all_policies
    
    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None, 
                      speed_mode="正常速度", disable_speed_limit=False, stop_callback=None):
        """爬取广东省政策"""
        print(f"开始爬取广东省政策，关键词: {keywords}, 时间范围: {start_date} 至 {end_date}")
        
        # 解析时间范围
        dt_start = None
        dt_end = None
        enable_time_filter = False  # 是否启用时间过滤
        
        if start_date and end_date:
            try:
                dt_start = datetime.strptime(start_date, '%Y-%m-%d')
                dt_end = datetime.strptime(end_date, '%Y-%m-%d')
                enable_time_filter = True
                print(f"启用时间过滤: {start_date} 至 {end_date}")
            except ValueError:
                print(f"时间格式错误，禁用时间过滤")
                enable_time_filter = False
        else:
            print("未设置时间范围，禁用时间过滤")
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
        print(f"找到 {len(categories)} 个分类")
        
        all_policies = []
        
        # 首先尝试不同的搜索策略
        print("开始尝试多种搜索策略...")
        if callback:
            callback("开始尝试多种搜索策略...")
        
        strategy_policies = self._try_different_search_strategies(keywords, callback, stop_callback)
        if strategy_policies:
            all_policies.extend(strategy_policies)
            print(f"通过搜索策略获取到 {len(strategy_policies)} 条政策")
            if callback:
                callback(f"通过搜索策略获取到 {len(strategy_policies)} 条政策")
        
        # 然后遍历所有分类进行传统爬取
        print("开始传统分类爬取...")
        if callback:
            callback("开始传统分类爬取...")
        
        for category_name, category_code in categories:
            if stop_callback and stop_callback():
                print("用户已停止爬取")
                break
                
            print(f"正在爬取分类: {category_name} (代码: {category_code})")
            if callback:
                callback(f"正在爬取分类: {category_name}")
            
            # 爬取当前分类的所有页面
            page_index = 1
            max_pages = 50  # 增加最大页数限制，确保能获取更多数据
            category_policies = []
            empty_page_count = 0  # 连续空页计数
            max_empty_pages = 3   # 最大连续空页数
            
            while page_index <= max_pages and empty_page_count < max_empty_pages:
                if stop_callback and stop_callback():
                    print("用户已停止爬取")
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
                    print(f"搜索关键词: '{search_keyword}', 分类: {category_code}, 页码: {page_index}")
                    
                    headers = self.headers.copy()
                    headers.update(self.anti_crawler.get_random_headers())
                    
                    resp = self.session.post(
                        self.search_url,
                        data=post_data,
                        headers=headers,
                        timeout=30
                    )
                    
                    if resp.status_code == 200:
                        self.monitor.record_request(self.search_url, success=True)
                    else:
                        self.monitor.record_request(self.search_url, success=False, error_type=f"HTTP {resp.status_code}")
                        print(f"请求失败，状态码: {resp.status_code}")
                        break
                    
                    # 解析页面
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    
                    # 解析政策列表
                    page_policies = self._parse_policy_list_record_search(soup, callback, stop_callback, category_name)
                    
                    if len(page_policies) == 0:
                        empty_page_count += 1
                        print(f"分类[{category_name}] 第 {page_index} 页未获取到政策，连续空页: {empty_page_count}")
                        if empty_page_count >= max_empty_pages:
                            print(f"分类[{category_name}] 连续 {max_empty_pages} 页无数据，停止翻页")
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
                                # 发送政策数据信号，格式：POLICY_DATA:title|pub_date|source|content
                                if callback:
                                    callback(f"POLICY_DATA:{policy.get('title', '')}|{policy.get('pub_date', '')}|{policy.get('source', '')}|{policy.get('content', '')}")
                        else:
                            # 不启用时间过滤，直接包含所有政策
                            filtered_policies.append(policy)
                            # 发送政策数据信号，格式：POLICY_DATA:title|pub_date|source|content
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
                        print(f"分类[{category_name}] 已到达最大页数限制 ({max_pages} 页)，停止翻页")
                        break
                    
                    page_index += 1
                    
                    # 添加延时
                    if not disable_speed_limit:
                        delay = random.uniform(*delay_range)
                        time.sleep(delay)
                        
                except Exception as e:
                    print(f"请求失败: {e}")
                    self.monitor.record_request(self.search_url, success=False, error_type=str(e))
                    break
            
            # 显示当前分类的统计信息
            print(f"分类[{category_name}] 爬取完成，共获取 {len(category_policies)} 条政策")
            if callback:
                callback(f"分类[{category_name}] 爬取完成，共获取 {len(category_policies)} 条政策")
        
        # 应用去重机制
        print("应用数据去重...")
        if callback:
            callback("应用数据去重...")
        
        unique_policies = self._deduplicate_policies(all_policies)
        
        # 最终统计
        total_saved = len(unique_policies)
        
        print(f"爬取完成统计:")
        print(f"  总爬取数量: {total_crawled} 条")
        if keywords:
            print(f"  关键词过滤: {keywords}")
        if enable_time_filter:
            print(f"  时间过滤: {start_date} 至 {end_date}")
            print(f"  过滤后数量: {total_filtered} 条")
        print(f"  去重后数量: {total_saved} 条")
        
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
        print(f"找到 {len(policy_containers)} 个list-title容器")
        
        if policy_containers:
            print(f"使用list-title容器解析，找到 {len(policy_containers)} 个政策项目")
            for container in policy_containers:
                # 检查是否停止
                if stop_callback and stop_callback():
                    print("用户已停止爬取")
                    break
                
                try:
                    policy_data = self._parse_policy_item_record_search(container, category_name or "广东省政策")
                    if policy_data:
                        policies.append(policy_data)
                        
                        # 发送政策数据信号
                        if callback:
                            callback(f"获取政策: {policy_data.get('title', '未知标题')}")
                            
                except Exception as e:
                    print(f"解析政策项目失败: {e}")
        
        # 方法2：如果list-title容器为空，尝试查找checkbox容器（备用方法）
        if not policy_containers:
            checkbox_containers = soup.find_all('div', class_='checkbox')
            print(f"备用方法：找到 {len(checkbox_containers)} 个checkbox容器")
            
            if checkbox_containers:
                print(f"使用checkbox容器解析，找到 {len(checkbox_containers)} 个政策项目")
                for container in checkbox_containers:
                    # 检查是否停止
                    if stop_callback and stop_callback():
                        print("用户已停止爬取")
                        break
                    
                    try:
                        policy_data = self._parse_policy_item_record_search(container, category_name or "广东省政策")
                        if policy_data:
                            policies.append(policy_data)
                            
                            # 发送政策数据信号
                            if callback:
                                callback(f"获取政策: {policy_data.get('title', '未知标题')}")
                                
                    except Exception as e:
                        print(f"解析政策项目失败: {e}")
        
        return policies
    
    def _parse_policy_item_record_search(self, item, category_name):
        """解析RecordSearch接口返回的单个政策项目 - 基于最新HTML结构分析"""
        try:
            print(f"开始解析政策项目: {item.name if hasattr(item, 'name') else 'unknown'}")
            
            # 方法1：如果item本身就是list-title容器，直接解析
            if item.get('class') and 'list-title' in item.get('class'):
                print("检测到list-title容器，直接解析")
                return self._parse_list_title_container(item, category_name)
            
            # 方法2：查找标准结构 (list-title + related-info)
            title_div = item.find('div', class_='list-title')
            if title_div:
                print("找到list-title div，使用标准结构解析")
                return self._parse_standard_structure(item, category_name)
            
            # 方法3：如果item本身就是checkbox容器，查找其中的list-title
            if 'checkbox' in item.get('class', []):
                print("检测到checkbox容器，查找list-title")
                title_div = item.find('div', class_='list-title')
                if title_div:
                    return self._parse_standard_structure(item, category_name)
            
            # 方法4：查找其他可能的结构
            print("未找到list-title div，尝试其他结构")
            
            # 查找所有可能的标题链接
            title_links = item.find_all('a')
            title = ""
            link = ""
            
            for a_link in title_links:
                link_text = a_link.get_text(strip=True)
                link_href = a_link.get('href', '')
                
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
                print("未找到有效的标题")
                return None
            
            print(f"找到标题: {title}")
            print(f"找到链接: {link}")
            
            # 处理链接
            if link and not link.startswith('http'):
                link = urljoin(self.base_url, link)
            
            # 查找相关信息 - 尝试多种方式
            info_text = ""
            
            # 方式1：查找related-info
            info_div = item.find('div', class_='related-info')
            if info_div:
                info_text = info_div.get_text(strip=True)
                print(f"从related-info获取信息: {info_text}")
            
            # 方式2：如果没找到，从整个item的文本中提取
            if not info_text:
                item_text = item.get_text(strip=True)
                # 移除标题文本，获取剩余信息
                if title in item_text:
                    info_text = item_text.replace(title, '').strip()
                    print(f"从item文本获取信息: {info_text}")
            
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
                
                print(f"分割后的部分: {parts}")
                
                if len(parts) >= 1:
                    validity = parts[0].strip()
                if len(parts) >= 2:
                    document_number = parts[1].strip()
                if len(parts) >= 3:
                    publish_date = parts[2].strip()
                    # 清理日期格式，移除"公布"等后缀
                    import re
                    date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', publish_date)
                    if date_match:
                        year, month, day = date_match.groups()
                        publish_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                if len(parts) >= 4:
                    effective_date = parts[3].strip()
                    # 清理日期格式，移除"施行"等后缀
                    date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', effective_date)
                    if date_match:
                        year, month, day = date_match.groups()
                        effective_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            # 如果没有解析到日期，尝试从标题或其他地方提取
            if not publish_date:
                import re
                # 从标题中查找日期
                date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', title)
                if date_match:
                    year, month, day = date_match.groups()
                    publish_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            print(f"解析结果: 时效性={validity}, 发文字号={document_number}, 公布日期={publish_date}, 施行日期={effective_date}")
            
            # 构建政策数据 - 兼容系统格式
            policy_data = {
                'level': LEVEL_NAME,
                'title': title,
                'pub_date': publish_date,
                'doc_number': document_number,
                'source': link,
                'content': f"标题: {title}\n时效性: {validity}\n发文字号: {document_number}\n公布日期: {publish_date}\n施行日期: {effective_date}",
                'category': category_name,
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                # 保留原始字段用于兼容
                'link': link,
                'validity': validity,
                'effective_date': effective_date
            }
            
            print(f"成功解析政策: {title}")
            return policy_data
            
        except Exception as e:
            print(f"解析政策项目失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_list_title_container(self, item, category_name):
        """解析list-title容器 - 直接处理list-title div"""
        try:
            print("解析list-title容器")
            
            # 查找标题链接
            title_link = item.find('a')
            if not title_link:
                print("未找到标题链接")
                return None
            
            title = title_link.get_text(strip=True)
            if not title:
                print("标题为空")
                return None
            
            link = title_link.get('href', '')
            if link and not link.startswith('http'):
                link = urljoin(self.base_url, link)
            
            print(f"找到标题: {title}")
            print(f"找到链接: {link}")
            
            # 尝试从父级容器或兄弟元素获取相关信息
            parent = item.parent
            info_text = ""
            
            # 查找兄弟元素中的相关信息
            if parent:
                # 查找related-info兄弟元素
                related_info = parent.find('div', class_='related-info')
                if related_info:
                    info_text = related_info.get_text(strip=True)
                    print(f"从related-info获取信息: {info_text}")
                
                # 如果没有related-info，尝试从其他兄弟元素获取
                if not info_text:
                    siblings = parent.find_all('div')
                    for sibling in siblings:
                        if sibling != item and 'related' in sibling.get('class', []):
                            info_text = sibling.get_text(strip=True)
                            print(f"从兄弟元素获取信息: {info_text}")
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
                
                print(f"分割后的部分: {parts}")
                
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
            
            print(f"解析结果: 时效性={validity}, 发文字号={document_number}, 公布日期={publish_date}, 施行日期={effective_date}")
            
            # 构建政策数据
            policy_data = {
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
            
            print(f"成功解析政策: {title}")
            return policy_data
            
        except Exception as e:
            print(f"解析list-title容器失败: {e}")
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
            print(f"解析标准结构失败: {e}")
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
            print("未找到政策项目")
            return []
        
        print(f"找到 {len(policy_items)} 个政策项目")
        
        for item in policy_items:
            # 检查是否停止
            if stop_callback and stop_callback():
                print("用户已停止爬取")
                break
            
            try:
                policy_data = self._parse_policy_item(item, category_name or "广东省政策")
                if policy_data:
                    policies.append(policy_data)
                    
                    # 发送政策数据信号
                    if callback:
                        callback(f"POLICY_DATA:{policy_data['title']}|{policy_data['pub_date']}|{policy_data['source']}|{policy_data['content']}")
            
            except Exception as e:
                print(f"解析政策项目失败: {e}")
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
                        # 检查是否是政策标题链接（通常包含特定关键词）
                        if link_text and link_href and any(keyword in link_text for keyword in ['条例', '规定', '办法', '通知', '意见', '决定', '公告']):
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
                        if link_text and link_href and len(link_text) > 5:  # 标题长度大于5
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
        
        except Exception as e:
            print(f"解析政策项目失败: {e}")
            return None
    
    def get_policy_detail(self, url):
        """获取政策详情内容"""
        try:
            # 使用防反爬虫管理器发送请求
            headers = self.headers.copy()
            headers.update(self.anti_crawler.get_random_headers())
            
            resp = self.anti_crawler.make_request(url, headers=headers)
            
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
                        print(f"使用选择器 '{selector}' 获取到正文")
                        break
            
            # 方法2：如果方法1失败，尝试查找包含政策文本的div
            if not content or len(content) < 100:
                for div in soup.find_all('div'):
                    text = div.get_text(strip=True)
                    if (text and len(text) > 200 and 
                        ('第一条' in text or '第一章' in text or '总则' in text or 
                         '条' in text or '款' in text or '项' in text)):
                        content = text
                        print("通过关键词匹配获取到正文")
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
                    print("使用页面主要内容作为正文")
            
            return content
        
        except Exception as e:
            # 记录失败的详情页面请求
            self.monitor.record_request(url, success=False, error_type=str(e))
            print(f"获取政策详情失败: {e}")
            return ""
    
    def get_crawler_status(self):
        """获取爬虫状态"""
        return {
            'speed_mode': self.speed_mode,
            'monitor_stats': self.monitor.get_stats(),
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
            print(f"无法解析发布日期: {pub_date}")
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
                print(f"政策匹配关键词 '{keyword}': {policy.get('title', '')}")
                return True
        
        print(f"政策不匹配关键词: {policy.get('title', '')}")
        return False

    def _parse_policy_list_optimized(self, soup, callback=None, stop_callback=None, category_name=None):
        """优化的政策列表解析 - 基于最新HTML结构分析"""
        policies = []
        
        # 基于HTML分析，直接查找政策列表项
        policy_items = soup.find_all('li')
        print(f"找到 {len(policy_items)} 个li元素")
        
        for item in policy_items:
            # 检查是否停止
            if stop_callback and stop_callback():
                print("用户已停止爬取")
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
                print(f"解析政策项目失败: {e}")
        
        return policies
    
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
            
            # 方法2：从整个item中查找所有链接
            if not title:
                title_links = item.find_all('a')
                for a_link in title_links:
                    link_text = a_link.get_text(strip=True)
                    link_href = a_link.get('href', '')
                    
                    # 检查是否是政策标题链接（更宽松的条件）
                    if (link_text and link_href and 
                        (link_href.startswith('/gdchinalaw/') or link_href.startswith('/')) and
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
                    print(f"正在获取政策正文: {title}")
                    content = self.get_policy_detail(link)
                    if content:
                        print(f"成功获取正文，长度: {len(content)} 字符")
                    else:
                        print(f"未获取到正文内容")
                except Exception as e:
                    print(f"获取政策正文失败: {e}")
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
            
            return policy_data
            
        except Exception as e:
            print(f"解析政策项目异常: {e}")
            return None
    
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
                               speed_mode="正常速度", disable_speed_limit=False, stop_callback=None):
        """优化的政策爬取方法"""
        print(f"开始优化爬取广东省政策，关键词: {keywords}, 时间范围: {start_date} 至 {end_date}")
        
        # 解析时间范围
        dt_start = None
        dt_end = None
        enable_time_filter = False
        
        if start_date and end_date:
            try:
                dt_start = datetime.strptime(start_date, '%Y-%m-%d')
                dt_end = datetime.strptime(end_date, '%Y-%m-%d')
                enable_time_filter = True
                print(f"启用时间过滤: {start_date} 至 {end_date}")
            except ValueError:
                print(f"时间格式错误，禁用时间过滤")
                enable_time_filter = False
        else:
            print("未设置时间范围，禁用时间过滤")
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
        print(f"找到 {len(categories)} 个分类")
        
        all_policies = []
        
        # 遍历所有分类进行爬取
        for category_name, category_code in categories:
            if stop_callback and stop_callback():
                print("用户已停止爬取")
                break
                
            print(f"正在爬取分类: {category_name} (代码: {category_code})")
            if callback:
                callback(f"正在爬取分类: {category_name}")
            
            # 爬取当前分类的所有页面
            page_index = 1
            max_pages = 100  # 增加最大页数限制
            category_policies = []
            empty_page_count = 0
            max_empty_pages = 5  # 增加连续空页容忍度
            
            while page_index <= max_pages and empty_page_count < max_empty_pages:
                if stop_callback and stop_callback():
                    print("用户已停止爬取")
                    break
                    
                try:
                    # 使用优化的搜索参数
                    post_data = self._get_search_parameters(
                        keywords=keywords,
                        category_code=category_code,
                        page_index=page_index,
                        page_size=20,
                        start_date=start_date,
                        end_date=end_date,
                        old_page_index=page_index - 1 if page_index > 1 else None
                    )
                    
                    search_keyword = ' '.join(keywords) if keywords else ''
                    print(f"搜索关键词: '{search_keyword}', 分类: {category_code}, 页码: {page_index}")
                    
                    # 使用带翻页校验的请求方法
                    resp = self._request_page_with_check(page_index, post_data, page_index - 1 if page_index > 1 else None)
                    
                    if not resp:
                        print(f"第{page_index}页请求失败")
                        break
                    
                    # 解析页面
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    
                    # 使用优化的解析方法
                    page_policies = self._parse_policy_list_optimized(soup, callback, stop_callback, category_name)
                    
                    if len(page_policies) == 0:
                        empty_page_count += 1
                        print(f"分类[{category_name}] 第 {page_index} 页未获取到政策，连续空页: {empty_page_count}")
                        if empty_page_count >= max_empty_pages:
                            print(f"分类[{category_name}] 连续 {max_empty_pages} 页无数据，停止翻页")
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
                                # 发送政策数据信号
                                if callback:
                                    callback(f"POLICY_DATA:{policy.get('title', '')}|{policy.get('pub_date', '')}|{policy.get('source', '')}|{policy.get('content', '')}|{policy.get('category', '')}")
                        else:
                            # 不启用时间过滤，直接包含所有政策
                            filtered_policies.append(policy)
                            # 发送政策数据信号
                            if callback:
                                callback(f"POLICY_DATA:{policy.get('title', '')}|{policy.get('pub_date', '')}|{policy.get('source', '')}|{policy.get('content', '')}|{policy.get('category', '')}")
                    
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
                        print(f"分类[{category_name}] 已到达最大页数限制 ({max_pages} 页)，停止翻页")
                        break
                    
                    page_index += 1
                    
                    # 添加延时
                    if not disable_speed_limit:
                        delay = random.uniform(*delay_range)
                        time.sleep(delay)
                        
                except Exception as e:
                    print(f"请求失败: {e}")
                    import traceback
                    print(f"详细错误信息: {traceback.format_exc()}")
                    self.monitor.record_request(self.search_url, success=False, error_type=str(e))
                    
                    # 如果是网络相关错误，尝试重试
                    if "timeout" in str(e).lower() or "connection" in str(e).lower():
                        print(f"检测到网络错误，等待5秒后重试...")
                        if callback:
                            callback(f"网络错误，等待重试...")
                        time.sleep(5)
                        continue
                    
                    # 如果是反爬虫相关错误，增加延时
                    if "403" in str(e) or "429" in str(e) or "block" in str(e).lower():
                        print(f"检测到反爬虫限制，等待10秒后重试...")
                        if callback:
                            callback(f"检测到访问限制，等待重试...")
                        time.sleep(10)
                        continue
                    
                    # 其他错误，记录并继续
                    print(f"未知错误，跳过当前页面")
                    if callback:
                        callback(f"页面处理出错，跳过继续...")
                    break
            
            # 显示当前分类的统计信息
            print(f"分类[{category_name}] 爬取完成，共获取 {len(category_policies)} 条政策")
            if callback:
                callback(f"分类[{category_name}] 爬取完成，共获取 {len(category_policies)} 条政策")
        
        # 应用去重机制
        print("应用数据去重...")
        if callback:
            callback("应用数据去重...")
        
        unique_policies = self._deduplicate_policies(all_policies)
        
        # 最终统计
        total_saved = len(unique_policies)
        
        print(f"爬取完成统计:")
        print(f"  总爬取数量: {total_crawled} 条")
        print(f"  过滤后数量: {total_filtered} 条")
        print(f"  最终保存数量: {total_saved} 条")
        print(f"  去重减少: {total_filtered - total_saved} 条")
        
        if callback:
            callback(f"爬取完成！总爬取: {total_crawled} 条，过滤后: {total_filtered} 条，最终保存: {total_saved} 条")
        
        return unique_policies

    def crawl_policies_fast(self, keywords=None, callback=None, start_date=None, end_date=None, 
                           speed_mode="正常速度", disable_speed_limit=False, stop_callback=None):
        """广东省政策快速爬取方法 - 跳过分类遍历，直接搜索"""
        print(f"开始快速爬取广东省政策，关键词: {keywords}, 时间范围: {start_date} 至 {end_date}")
        
        # 解析时间范围
        dt_start = None
        dt_end = None
        enable_time_filter = False
        
        if start_date and end_date:
            try:
                dt_start = datetime.strptime(start_date, '%Y-%m-%d')
                dt_end = datetime.strptime(end_date, '%Y-%m-%d')
                enable_time_filter = True
                print(f"启用时间过滤: {start_date} 至 {end_date}")
            except ValueError:
                print(f"时间格式错误，禁用时间过滤")
                enable_time_filter = False
        else:
            print("未设置时间范围，禁用时间过滤")
            enable_time_filter = False
        
        # 统计信息
        total_crawled = 0
        total_filtered = 0
        total_saved = 0
        
        # 设置速度模式 - 快速模式下使用更激进的设置
        self.speed_mode = speed_mode
        if disable_speed_limit:
            delay_range = (0.0, 0.1)  # 几乎无延迟
        elif speed_mode == "快速模式":
            delay_range = (0.1, 0.3)
        elif speed_mode == "慢速模式":
            delay_range = (1.0, 2.0)
        else:  # 正常速度
            delay_range = (0.2, 0.5)
        
        all_policies = []
        
        # 直接使用最有效的搜索策略，跳过分类遍历
        print("使用快速搜索策略...")
        if callback:
            callback("使用快速搜索策略...")
        
        # 策略1：使用高级搜索表单（最有效）
        try:
            print("尝试高级搜索表单...")
            if callback:
                callback("尝试高级搜索表单...")
            
            # 使用更大的页面大小减少翻页次数
            page_size = 50  # 增加页面大小
            page_index = 1
            max_pages = 50  # 减少最大页数
            empty_page_count = 0
            max_empty_pages = 3
            
            while page_index <= max_pages and empty_page_count < max_empty_pages:
                if stop_callback and stop_callback():
                    print("用户已停止爬取")
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
                    print(f"快速搜索: '{search_keyword}', 页码: {page_index}")
                    if callback:
                        callback(f"正在请求第 {page_index} 页...")
                    
                    # 使用带翻页校验的请求方法
                    resp = self._request_page_with_check(page_index, post_data, page_index - 1 if page_index > 1 else None)
                    
                    if not resp:
                        print(f"第{page_index}页请求失败")
                        if callback:
                            callback(f"第 {page_index} 页请求失败，停止翻页")
                        break
                    
                    # 解析页面
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    
                    # 使用优化的解析方法
                    page_policies = self._parse_policy_list_optimized(soup, callback, stop_callback, "快速搜索")
                    
                    if len(page_policies) == 0:
                        empty_page_count += 1
                        print(f"第 {page_index} 页未获取到政策，连续空页: {empty_page_count}")
                        if empty_page_count >= max_empty_pages:
                            print(f"连续 {max_empty_pages} 页无数据，停止翻页")
                            break
                    else:
                        empty_page_count = 0  # 重置空页计数
                    
                    # 更新总爬取数量
                    total_crawled += len(page_policies)
                    
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
                        print(f"已到达最大页数限制 ({max_pages} 页)，停止翻页")
                        break
                    
                    page_index += 1
                    
                    # 添加延时（快速模式下延迟更短）
                    if not disable_speed_limit:
                        delay = random.uniform(*delay_range)
                        time.sleep(delay)
                        
                except Exception as e:
                    print(f"请求失败: {e}")
                    import traceback
                    print(f"详细错误信息: {traceback.format_exc()}")
                    self.monitor.record_request(self.search_url, success=False, error_type=str(e))
                    
                    # 如果是网络相关错误，尝试重试
                    if "timeout" in str(e).lower() or "connection" in str(e).lower():
                        print(f"检测到网络错误，等待3秒后重试...")
                        if callback:
                            callback(f"网络错误，等待重试...")
                        time.sleep(3)
                        continue
                    
                    # 如果是反爬虫相关错误，增加延时
                    if "403" in str(e) or "429" in str(e) or "block" in str(e).lower():
                        print(f"检测到反爬虫限制，等待5秒后重试...")
                        if callback:
                            callback(f"检测到访问限制，等待重试...")
                        time.sleep(5)
                        continue
                    
                    # 其他错误，记录并继续
                    print(f"未知错误，跳过当前页面")
                    if callback:
                        callback(f"页面处理出错，跳过继续...")
                    break
            
            print(f"快速搜索完成，共获取 {len(all_policies)} 条政策")
            if callback:
                callback(f"快速搜索完成，共获取 {len(all_policies)} 条政策")
                
        except Exception as e:
            print(f"快速搜索策略失败: {e}")
            if callback:
                callback(f"快速搜索策略失败，尝试备用策略...")
        
        # 应用去重机制
        print("应用数据去重...")
        if callback:
            callback("应用数据去重...")
        
        unique_policies = self._deduplicate_policies(all_policies)
        
        # 最终统计
        total_saved = len(unique_policies)
        
        print(f"快速爬取完成统计:")
        print(f"  总爬取数量: {total_crawled} 条")
        print(f"  过滤后数量: {total_filtered} 条")
        print(f"  最终保存数量: {total_saved} 条")
        print(f"  去重率: {(len(all_policies) - len(unique_policies)) / len(all_policies) * 100:.1f}%" if all_policies else "0%")
        
        if callback:
            callback(f"快速爬取完成！共获取 {total_saved} 条政策")
        
        return unique_policies

# 为兼容性添加别名类
class GuangdongPolicyCrawler(GuangdongSpider):
    """广东省政策爬虫类（GuangdongSpider的别名）"""
    pass

if __name__ == "__main__":
    spider = GuangdongSpider()
    policies = spider.crawl_policies(['规划', '空间', '用地'])
    spider.save_to_db(policies)
    print(f"爬取到 {len(policies)} 条广东省政策") 