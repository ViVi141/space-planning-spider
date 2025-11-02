#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
广东省爬虫网页链接统计脚本
功能：遍历所有分类的列表页，提取政策链接（不访问详情页），统计去重后的链接数量
     不使用代理，仅列出链接但不访问具体政策网页
"""

import os
import sys
import time
import re
import argparse
import requests
from bs4 import BeautifulSoup
from typing import List, Tuple, Dict, Optional, Set
from datetime import datetime
from urllib.parse import urlparse, urlunparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# 添加src目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# 导入配置
from space_planning.spider.spider_config import SpiderConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('guangdong_counter.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ========== 常量定义 ==========
# API路径映射
API_PATH_MAP = {
    'dfxfg': {'menu': 'dfxfg', 'library': 'gddifang', 'class_flag': 'gddifang'},
    'sfjs': {'menu': 'sfjs', 'library': 'regularation', 'class_flag': 'regularation'},
    'dfzfgz': {'menu': 'dfzfgz', 'library': 'gddigui', 'class_flag': 'gddigui'},
    'fljs': {'menu': 'fljs', 'library': 'gdnormativedoc', 'class_flag': 'gdnormativedoc'}
}

# 分类代码到API映射
CATEGORY_API_MAP = {
    'XM07': 'dfxfg',
    'XU13': 'sfjs',
    'XO08': 'dfzfgz',
    'XP08': 'fljs'
}

# 通用配置
MAX_PAGES = 5000  # 最大页数限制
MAX_EMPTY_PAGES = 15  # 最大连续空页数
MAX_NO_NEW_LINKS = 8  # 最大连续无新链接数
PAGE_SIZE = 20  # 标准页大小
PAGE_SIZE_FLJS = 100  # fljs接口页大小（突破500页限制）


class GuangdongPageCounter:
    """广东省爬虫网页链接统计器（仅提取链接，不访问详情页，不使用代理）"""
    
    def __init__(self, max_workers: int = 1):
        """初始化计数器
        
        Args:
            max_workers: 最大线程数（用于多线程处理分类）
        """
        # 获取配置
        config = SpiderConfig.get_guangdong_config()
        
        self.base_url = config['base_url']
        # 默认使用dfzfgz接口（后续会根据分类动态选择）
        self.default_search_url = f"{config['base_url']}/dfzfgz/search/RecordSearch"
        self.headers = config['headers'].copy()
        self.category_config = config['category_config'].copy()
        
        # 多线程相关
        self.max_workers = max(1, max_workers)  # 至少1个线程
        self._thread_local = threading.local()  # 线程局部存储，每个线程独立的会话
        self._result_lock = threading.Lock()  # 保护共享结果的锁
        
        # 创建主会话（用于单线程模式或初始化）
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 设置Cookie
        self.session.cookies.set('JSESSIONID', '1234567890ABCDEF', domain='gd.pkulaw.com')
        
        # 访问首页获取必要的Cookie
        try:
            print("正在初始化会话...")
            # 使用dfzfgz页面初始化会话（对应/dfzfgz/adv页面）
            home_resp = self.session.get('https://gd.pkulaw.com/dfzfgz/adv', timeout=10)
            if home_resp.status_code == 200:
                print("会话初始化成功")
            else:
                print(f"警告: 首页访问返回状态码 {home_resp.status_code}")
        except Exception as e:
            print(f"警告: 访问首页失败: {e}，继续测试...")
        
        print("=" * 80)
        print("广东省政策爬虫网页链接统计")
        print("=" * 80)
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"基础URL: {self.base_url}")
        print("代理状态: 已禁用（不使用代理）")
        print("工作模式: 仅提取链接，不访问详情页")
        print(f"线程模式: {'多线程' if self.max_workers > 1 else '单线程'} (最大 {self.max_workers} 个线程)")
        print("去重策略: 按URL去重")
        print("接口说明: 根据分类类型自动选择正确的接口（dfxfg/sfjs/dfzfgz/fljs）")
        print("=" * 80)
        print()
    
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
    
    def _get_thread_session(self, init_page: str = None):
        """获取当前线程的会话（线程安全）"""
        if not hasattr(self._thread_local, 'session'):
            # 为当前线程创建独立的会话
            session = requests.Session()
            session.headers.update(self.headers)
            session.cookies.set('JSESSIONID', '1234567890ABCDEF', domain='gd.pkulaw.com')
            
            # 初始化会话（访问首页，使用传入的init_page）
            try:
                init_url = init_page or 'https://gd.pkulaw.com/dfzfgz/adv'
                home_resp = session.get(init_url, timeout=10)
                if home_resp.status_code == 200:
                    pass  # 初始化成功
            except Exception as e:
                print(f"  警告 [线程 {threading.current_thread().name}]: 会话初始化失败: {e}")
            
            self._thread_local.session = session
        
        return self._thread_local.session
    
    def _get_all_categories(self) -> List[Tuple]:
        """获取所有分类信息"""
        categories = [
            # 父级分类：地方性法规
            ("地方性法规", "XM07", [
                ("省级地方性法规", "XM0701"),
                ("设区的市地方性法规", "XM0702"), 
                ("经济特区法规", "XM0703"),
                ("自治条例和单行条例", "XU13"),
            ]),
            # 父级分类：地方政府规章
            ("地方政府规章", "XO08", [
                ("省级地方政府规章", "XO0802"),
                ("设区的市地方政府规章", "XO0803"),
            ]),
            # 父级分类：规范性文件
            ("规范性文件", "XP08", [
                ("地方规范性文件", "XP08"),
            ]),
        ]
        return categories
    
    def _get_flat_categories(self) -> List[Tuple[str, str]]:
        """获取扁平化的分类列表"""
        flat_categories = []
        for parent_name, parent_code, sub_categories in self._get_all_categories():
            for sub_name, sub_code in sub_categories:
                flat_categories.append((sub_name, sub_code))
        return flat_categories
    
    def _get_search_parameters(self, category_code: str = None, page_index: int = 1, page_size: int = 20, old_page_index: int = None,             filter_year: int = None, api_config: Dict = None) -> Dict:
        """获取搜索参数
        
        Args:
            category_code: 分类代码
            page_index: 页码
            page_size: 每页数量
            old_page_index: 上一页页码
            filter_year: 年份筛选（如果指定，将通过ClassCodeKey传递年份实现）
            api_config: API配置（包含menu, library, class_flag等）
        """
        # 如果没有提供api_config，根据分类代码获取
        if api_config is None:
            api_config = self._get_category_api_config(category_code)
        
        search_params = {
            'Menu': api_config['menu'],  # 根据分类类型动态选择菜单
            'Keywords': '',
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
            # 关键修复：年份筛选应该通过ClassCodeKey传递年份，而不是分类代码
            # 格式：,,,2020 表示筛选2020年的数据
            'ClassCodeKey': f',,,{filter_year}' if filter_year else (f',,,{category_code},,,' if category_code else ',,,,,,'),
            'GroupByIndex': '0',
            'OrderByIndex': '0',
            'ShowType': 'Default',
            'GroupValue': '',  # 不使用GroupValue（改用ClassCodeKey传递年份筛选）
            'AdvSearchDic.Title': '',
            'AdvSearchDic.CheckFullText': '',
            'AdvSearchDic.IssueDepartment': '',
            'AdvSearchDic.DocumentNO': '',
            'AdvSearchDic.IssueDate': '',  # 不使用日期筛选（改用ClassCodeKey传递年份）
            'AdvSearchDic.ImplementDate': '',  # 不使用日期筛选（改用ClassCodeKey传递年份）
            'AdvSearchDic.TimelinessDic': '',
            'AdvSearchDic.EffectivenessDic': '',
            'TitleKeywords': '',
            'FullTextKeywords': '',
            'Pager.PageIndex': str(page_index),
            'Pager.PageSize': str(page_size),  # 注意：fljs接口需要使用100条/页来突破500页限制
            'QueryBase64Request': '',
            'VerifyCodeResult': '',
            'isEng': 'chinese',
            'OldPageIndex': str(old_page_index) if old_page_index is not None else '',
            'newPageIndex': str(page_index) if old_page_index is not None else '',
            'X-Requested-With': 'XMLHttpRequest',
        }
        return search_params
    
    def _normalize_url(self, url: str) -> str:
        """标准化URL（移除查询参数和锚点）"""
        try:
            parsed = urlparse(url)
            return urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                '',  # params
                '',  # query
                ''   # fragment
            ))
        except Exception:
            return url
    
    def _build_full_url(self, href: str) -> str:
        """构建完整URL"""
        if href.startswith('http'):
            return href
        elif href.startswith('/'):
            return self.base_url + href
        else:
            return self.base_url + '/' + href
    
    def _is_valid_policy_url(self, url: str) -> bool:
        """检查是否是有效的政策URL"""
        valid_paths = ['/gddigui/', '/gdchinalaw/', '/gdfgwj/', '/gddifang/', '/regularation/', '/gdnormativedoc/']
        return any(path in url for path in valid_paths)
    
    def extract_policy_links_from_html(self, html_content: str, api_config: Dict = None) -> List[str]:
        """从HTML中提取所有政策链接（优化版）
        
        Args:
            html_content: HTML内容
            api_config: API配置（用于确定链接路径）
            
        Returns:
            提取到的政策链接列表
        """
        found_links: Set[str] = set()
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 根据API配置确定链接路径
            link_path = api_config.get('library', 'gddigui') if api_config else 'gddigui'
            
            # 方法1：从复选框value提取政策ID并构建URL（最可靠）
            checkboxes = soup.select('input.checkbox[name="recordList"]')
            for checkbox in checkboxes:
                policy_id = checkbox.get('value', '').strip()
                if policy_id and len(policy_id) > 10:  # 政策ID通常是较长的字符串
                    url = f"{self.base_url}/{link_path}/{policy_id}.html"
                    found_links.add(url)
            
            # 方法2：从链接标签提取（与方法1并行，确保不遗漏）
            link_elems = soup.select('ul > li > div.block > div.list-title > h4 > a')
            for link_elem in link_elems:
                href = link_elem.get('href', '').strip()
                if href:
                    full_url = self._build_full_url(href)
                    normalized = self._normalize_url(full_url)
                    if self._is_valid_policy_url(normalized):
                        found_links.add(normalized)
            
            # 方法3（备用）：如果前两种方法都没找到，使用更宽泛的搜索
            if not found_links:
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link.get('href', '').strip()
                    if href and self._is_valid_policy_url(href):
                        full_url = self._build_full_url(href)
                        normalized = self._normalize_url(full_url)
                        found_links.add(normalized)
            
        except Exception as e:
            logger.warning(f"提取链接失败: {e}")
        
        return list(found_links)
    
    def extract_total_count_from_html(self, html_content: str) -> int:
        """从HTML中提取总政策数（优化版）"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 方法1: 从 "总共检索到X篇" 提取（最准确）
            # 查找所有h3元素，找到包含"总共检索到"的h3
            h3_elems = soup.find_all('h3')
            for h3 in h3_elems:
                h3_text = h3.get_text()
                if '总共检索到' in h3_text:
                    # 优先从span标签提取（最可靠，因为HTML格式为 <h3>总共检索到<span>40231</span>篇</h3>）
                    span = h3.find('span')
                    if span:
                        try:
                            span_text = span.get_text(strip=True)
                            if span_text.isdigit():
                                return int(span_text)
                        except (ValueError, AttributeError):
                            pass
                    
                    # 如果span提取失败，使用正则从h3完整文本提取
                    match = re.search(r'总共检索到\s*(\d+)\s*篇', h3_text)
                    if match:
                        return int(match.group(1))
                    break
            
            # 方法2: 从全文内容中搜索（备用）
            text_content = soup.get_text()
            match = re.search(r'总共检索到\s*(\d+)\s*篇', text_content)
            if match:
                return int(match.group(1))
            
            # 方法3: 从分页信息提取（备用，不准确）
            label = soup.find('label', string=re.compile(r'页数'))
            if label:
                label_text = label.get_text()
                match = re.search(r'页数\s*\d+/(\d+)', label_text)
                if match:
                    total_pages = int(match.group(1))
                    # 需要知道每页数量，默认20
                    return total_pages * 20  # 估算值，不准确
            
            return 0
            
        except Exception as e:
            print(f"  警告: 提取总政策数失败: {e}")
            return 0
    
    
    def extract_years_from_page(self, html_content: str) -> List[Tuple[int, int]]:
        """从页面HTML中提取可用的公布年份及其数量
        
        年份筛选器位于 <div class="block" cluster_index="6"> 中（注意：是6，不是3）
        每个年份链接格式: <a href="javascript:void(0);" cluster_code="2021">2021 (70)</a>
        
        注意：列表页的响应通常不包含筛选信息（通过AJAX动态加载），
        但如果响应中包含筛选信息，应该能从 cluster_index="6" 的区块中提取
        """
        years = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            import re
            
            # 方法1: 查找 cluster_index="6" 的block（公布年份筛选器）
            # 根据实际页面分析，年份筛选器的 cluster_index 是 6，不是 3
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
            
            # 方法2: 如果方法1失败，尝试查找 cluster_index="3"（某些情况下可能是3）
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
            
            # 方法3: 如果方法1和2失败，通过"公布年份"标题查找
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
            
            # 方法4: 如果还是找不到，尝试更宽泛的搜索（查找所有带cluster_code的4位数字链接）
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
            print(f"  警告: 提取年份信息失败: {e}")
        
        return sorted(years, reverse=True)  # 按年份倒序排列
    
    def extract_links_for_category(self, category_name: str, category_code: str, filter_year: int = None, use_thread_session: bool = False) -> Dict:
        """提取某个分类的所有政策链接（不访问详情页）
        
        Args:
            category_name: 分类名称
            category_code: 分类代码
            filter_year: 如果指定，只提取该年份的政策（通过日期范围筛选）
        """
        year_info = f"（筛选年份: {filter_year}年）" if filter_year else ""
        thread_name = threading.current_thread().name if use_thread_session else "主线程"
        thread_prefix = f"[线程 {thread_name}]" if use_thread_session else ""
        
        # 使用线程安全的输出
        with self._result_lock:
            print(f"{thread_prefix} 正在提取分类: {category_name} (代码: {category_code}){year_info}")
        
        # 根据分类代码获取API配置
        api_config = self._get_category_api_config(category_code)
        
        # 选择会话（多线程模式下使用线程局部会话）
        if use_thread_session:
            session = self._get_thread_session(init_page=api_config['init_page'])
        else:
            session = self.session
            # 更新会话的Referer（如果需要）
            if api_config.get('referer'):
                session.headers['Referer'] = api_config['referer']
        
        all_links = set()  # 使用set自动去重
        page_index = 1
        page_size = 20  # 标准页大小
        max_empty_pages = 15  # 最大连续空页数（增加容错，某些分类可能数据稀疏）
        empty_page_count = 0
        max_pages = 5000  # 最大页数限制（防止无限循环）
        total_policies_from_html = 0  # 从HTML提取的总政策数
        expected_total_pages = 0  # 预期的总页数
        use_year_split = False  # 是否使用年份分割策略
        
        # 累计去重后计数不变检测
        no_new_links_count = 0  # 连续没有新链接的页数
        max_no_new_links = 8  # 累计去重后计数相同8次后换类（增加容错，因为某些分类数据可能较少）
        previous_link_count = 0  # 上一页的累计链接数
        
        headers = self.headers.copy()
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        
        try:
            # 先请求第一页获取总政策数和年份信息
            first_page_params = self._get_search_parameters(
                category_code=category_code,
                page_index=1,
                page_size=page_size,
                old_page_index=None,
                filter_year=filter_year,  # 直接传递年份参数
                api_config=api_config
            )
            
            # 调试：打印第一页的搜索参数（仅前几个分类，单线程模式）
            if not use_thread_session:
                with self._result_lock:
                    print(f"{thread_prefix} [调试] API配置 - 接口: {api_config['search_url']}, Menu: {api_config['menu']}, Library: {api_config['library']}")
                    print(f"{thread_prefix} [调试] 搜索参数 - ClassCodeKey: '{first_page_params.get('ClassCodeKey')}', category_code: {category_code}")
            
            first_resp = session.post(
                api_config['search_url'],  # 使用动态选择的搜索URL
                data=first_page_params,
                headers=headers,
                timeout=30
            )
            
            if first_resp.status_code == 200:
                # 提取年份信息（仅在未指定年份时）
                # 注意：列表页响应通常不包含筛选信息（通过AJAX动态加载），
                # 所以可能无法提取年份信息，但年份筛选功能仍然可以通过参数实现
                if not filter_year:
                    available_years = self.extract_years_from_page(first_resp.text)
                    if available_years:
                        print(f"  页面显示可用年份: {', '.join([f'{y[0]}年({y[1]})' for y in available_years[:10]])}")
                        if len(available_years) > 10:
                            print(f"    ... 共 {len(available_years)} 个年份")
                    # 如果没有找到年份信息，这是正常的（列表页响应不包含筛选区块）
                
                # 提取总政策数（线程安全输出）
                total_policies_from_html = self.extract_total_count_from_html(first_resp.text)
                
                # 优先使用配置文件中的预期数（更准确）
                # 因为dfzfgz接口可能返回所有分类的总数，而不是当前分类的总数
                # 但是：如果应用了年份筛选，则不能使用配置总数，必须使用实际筛选结果
                expected_count_from_config = None
                if category_code and category_name in self.category_config:
                    config_info = self.category_config.get(category_name, {})
                    if isinstance(config_info, dict):
                        expected_count_from_config = config_info.get('expected_count')
                
                # 选择使用的预期总数
                # 如果应用了年份筛选，则不能使用配置总数，必须使用实际筛选结果
                if expected_count_from_config and not filter_year:
                    total_policies_from_html = expected_count_from_config
                    using_source = "配置"
                elif total_policies_from_html > 0:
                    using_source = "HTML"
                else:
                    using_source = None
                
                if total_policies_from_html > 0:
                    expected_total_pages = (total_policies_from_html + page_size - 1) // page_size
                    with self._result_lock:
                        if using_source == "配置":
                            print(f"{thread_prefix} 预期总政策数: {total_policies_from_html:,} 篇（来自配置）")
                        else:
                            print(f"{thread_prefix} 从HTML提取到总政策数: {total_policies_from_html:,} 篇")
                        print(f"{thread_prefix} 预期总页数: {expected_total_pages:,} 页（每页{page_size}条）")
                        
                        if filter_year:
                            print(f"{thread_prefix} 提示: 已应用年份筛选（{filter_year}年），筛选后预期数量: {total_policies_from_html:,} 篇")
                        if using_source == "HTML":
                            # 如果使用HTML提取的数，检查是否与配置不同
                            if expected_count_from_config and total_policies_from_html != expected_count_from_config:
                                diff = abs(total_policies_from_html - expected_count_from_config)
                                print(f"{thread_prefix} 提示: HTML提取数({total_policies_from_html:,})与配置预期数({expected_count_from_config:,})不一致，差异: {diff:,}，将以HTML提取数为准")
                else:
                    with self._result_lock:
                        print(f"{thread_prefix} 警告: 未能获取总政策数（HTML提取失败且配置中无预期数）")
                        # 尝试调试：检查HTML中是否包含相关文本
                        if '总共检索到' in first_resp.text:
                            print(f"{thread_prefix} 调试: HTML中包含'总共检索到'文本，但提取失败，可能需要检查提取逻辑")
                        else:
                            print(f"{thread_prefix} 调试: HTML中未找到'总共检索到'文本，可能页面结构已变化或使用了AJAX")
                        print(f"{thread_prefix} 将继续遍历，完成后根据实际提取数进行对比")
                
                # 提取第一页的链接（避免重复请求）
                page_links = self.extract_policy_links_from_html(first_resp.text, api_config=api_config)
                if page_links:
                    before_count = len(all_links)
                for link in page_links:
                    normalized = self._normalize_url(link)
                    all_links.add(normalized)
                    after_count = len(all_links)
                    previous_link_count = after_count
                    with self._result_lock:
                        page_size_info = f"（页大小: {page_size}条/页）" if api_config.get('menu') == 'fljs' else ""
                        print(f"{thread_prefix} 第 1 页: 提取到 {len(page_links)} 个链接，新增 {after_count - before_count} 个（累计去重后: {after_count} 个）{page_size_info}")
                    page_index = 2  # 从第2页开始
                else:
                    with self._result_lock:
                        print(f"{thread_prefix} 警告: 第一页未提取到链接")
                    page_index = 1
            else:
                with self._result_lock:
                    print(f"{thread_prefix} 警告: 第一页请求失败，状态码: {first_resp.status_code}")
                page_index = 1
            
            while page_index <= max_pages:
                # 检查连续空页数，如果达到上限则立即退出
                if empty_page_count >= max_empty_pages:
                    with self._result_lock:
                        print(f"{thread_prefix} 连续 {max_empty_pages} 页无链接，自动切换到下一个分类")
                    break
                
                # 检查累计去重后计数是否连续相同，如果相同5次则退出
                if no_new_links_count >= max_no_new_links:
                    with self._result_lock:
                        print(f"{thread_prefix} 累计去重后链接数连续 {max_no_new_links} 页未增加，立即切换到下一个分类")
                    break
                
                # 对于fljs接口，如果超过500页且连续多页无数据，可能已达到限制
                if api_config['menu'] == 'fljs' and page_index > 500:
                    if empty_page_count >= 3 or no_new_links_count >= 3:
                        with self._result_lock:
                            print(f"{thread_prefix} [确认] 已达到500页限制，已提取约 {len(all_links):,} 条数据")
                
                # 如果已经提取的链接数达到或接近预期数（考虑分页误差），提前退出
                # 但只在实际提取数接近预期数时才提前退出（避免因分类过滤不准确导致提前停止）
                if total_policies_from_html > 0:
                    coverage = len(all_links) / total_policies_from_html if total_policies_from_html > 0 else 0
                    # 如果覆盖率超过95%或者提取数接近预期数（允许5%的误差），提前退出
                    if coverage >= 0.95 or (len(all_links) >= total_policies_from_html * 0.95 and len(all_links) > 100):
                        with self._result_lock:
                            print(f"{thread_prefix} 提示: 已提取 {len(all_links)} 个链接，覆盖率 {coverage*100:.1f}%，接近预期数 {total_policies_from_html}，提前结束遍历")
                        break
                
                # 设置OldPageIndex为上一页（分页可能需要）
                # 注意：china接口可能需要old_page_index，dfzfgz接口可能不需要
                # 对于第一页，old_page_index应该是None或空字符串
                if page_index == 1:
                    old_page_index = None
                else:
                    old_page_index = page_index - 1
                
                # 重试机制：尝试获取当前页（最多重试3次，多线程模式下快速失败）
                max_retries = 1 if use_thread_session else 3  # 多线程模式下仅重试1次以提升速度
                retry_count = 0
                page_success = False
                page_links = []
                
                while retry_count < max_retries and not page_success:
                    try:
                        # 如果翻页（page_index > 1），先请求验证码接口（根据网站分析）
                        # 快速模式：跳过验证码接口以提升速度（验证码接口通常不影响主请求）
                        if page_index > 1 and not use_thread_session:
                            # 单线程模式下保留验证码校验
                            try:
                                check_url = "https://gd.pkulaw.com/VerificationCode/GetRecordListTurningLimit"
                                check_headers = headers.copy()
                                check_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
                                check_resp = session.post(check_url, headers=check_headers, timeout=5)  # 减少timeout
                            except:
                                pass  # 验证码接口失败不影响主请求
                        
                        search_params = self._get_search_parameters(
                            category_code=category_code,
                            page_index=page_index,
                            page_size=page_size,
                            old_page_index=old_page_index,
                            filter_year=filter_year,  # 直接传递年份参数
                            api_config=api_config
                        )
                        
                        # 调试：打印分页参数（对于fljs接口，始终打印前几页的页大小信息）
                        if api_config.get('menu') == 'fljs' and page_index <= 3:
                            with self._result_lock:
                                if retry_count > 0:
                                    print(f"{thread_prefix} [重试 {retry_count}/{max_retries}] 分页参数: PageIndex={page_index}, PageSize={page_size}, OldPageIndex={old_page_index}")
                                else:
                                    print(f"{thread_prefix} [调试] 分页参数: PageIndex={page_index}, PageSize={page_size}, Pager.PageSize={search_params.get('Pager.PageSize')}, OldPageIndex={old_page_index}")
                        elif not use_thread_session and (page_index <= 3 or (page_index == 6)):
                            if retry_count > 0:
                                print(f"      [重试 {retry_count}/{max_retries}] 分页参数: PageIndex={page_index}, OldPageIndex={old_page_index}")
                            else:
                                print(f"      [调试] 分页参数: PageIndex={page_index}, OldPageIndex={old_page_index}")
                        
                        resp = session.post(
                            api_config['search_url'],  # 使用动态选择的搜索URL
                            data=search_params,
                            headers=headers,
                            timeout=20 if use_thread_session else 30  # 多线程模式减少timeout
                        )
                        
                        if resp.status_code == 200:
                            # 提取当前页的所有链接
                            page_links = self.extract_policy_links_from_html(resp.text, api_config=api_config)
                            
                            if page_links and len(page_links) > 0:
                                # 检查是否所有链接都是重复的
                                before_count = len(all_links)
                                normalized_new = {self._normalize_url(link) for link in page_links}
                                
                                # 检查是否有新链接
                                new_links = normalized_new - all_links
                                
                                if len(new_links) > 0:
                                    # 有新链接，成功
                                    page_success = True
                                else:
                                    # 所有链接都是重复的，需要重试
                                    if retry_count < max_retries - 1:
                                        retry_count += 1
                                        if not use_thread_session:  # 减少多线程模式下的输出
                                            with self._result_lock:
                                                print(f"  警告: 第 {page_index} 页所有链接都是重复的，重试 {retry_count}/{max_retries}...")
                                        time.sleep(0.1 if use_thread_session else 0.5)  # 多线程模式下快速重试
                                        continue
                                    else:
                                        # 重试用尽，标记为失败并退出重试循环
                                        page_success = False
                                        with self._result_lock:
                                            print(f"{thread_prefix} 警告: 第 {page_index} 页所有链接都是重复的（重试{max_retries}次后仍失败）")
                                        break  # 退出重试循环
                            else:
                                # 空页：状态码200但没有链接
                                if retry_count < max_retries - 1:
                                    retry_count += 1
                                    if not use_thread_session:  # 减少多线程模式下的输出
                                        with self._result_lock:
                                            print(f"  警告: 第 {page_index} 页无链接，重试 {retry_count}/{max_retries}...")
                                    time.sleep(0.1 if use_thread_session else 0.5)  # 多线程模式下快速重试
                                    continue
                                else:
                                    # 重试用尽，标记为失败并退出重试循环
                                    page_success = False
                                    with self._result_lock:
                                        print(f"{thread_prefix} 警告: 第 {page_index} 页无链接（重试{max_retries}次后仍失败）")
                                    break  # 退出重试循环
                        else:
                            # 请求失败：状态码不是200
                            if retry_count < max_retries - 1:
                                retry_count += 1
                                if not use_thread_session:  # 减少多线程模式下的输出
                                    with self._result_lock:
                                        print(f"  警告: 第 {page_index} 页请求失败（状态码: {resp.status_code}），重试 {retry_count}/{max_retries}...")
                                time.sleep(0.1 if use_thread_session else 0.5)  # 多线程模式下快速重试
                                continue
                            else:
                                # 重试用尽，标记为失败并退出重试循环
                                page_success = False
                                with self._result_lock:
                                    print(f"{thread_prefix} 警告: 第 {page_index} 页请求失败（状态码: {resp.status_code}，重试{max_retries}次后仍失败）")
                                break  # 退出重试循环
                                
                    except Exception as e:
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            if not use_thread_session:  # 减少多线程模式下的输出
                                with self._result_lock:
                                    print(f"  警告: 第 {page_index} 页请求异常: {str(e)[:50]}，重试 {retry_count}/{max_retries}...")
                            time.sleep(0.1 if use_thread_session else 0.5)  # 多线程模式下快速重试
                            continue
                        else:
                            # 重试用尽，标记为失败并退出重试循环
                            page_success = False
                            with self._result_lock:
                                print(f"{thread_prefix} 警告: 第 {page_index} 页请求异常（重试{max_retries}次后仍失败）: {str(e)[:50]}")
                            break  # 退出重试循环
                
                # 处理页面结果
                if page_links and len(page_links) > 0:
                    # 标准化并添加到集合中（自动去重）
                    before_count = len(all_links)
                for link in page_links:
                    normalized = self._normalize_url(link)
                    all_links.add(normalized)
                    after_count = len(all_links)
                    
                    # 检查是否有新链接增加
                    if after_count > previous_link_count:
                        # 有新链接增加，重置计数器
                        no_new_links_count = 0
                        empty_page_count = 0
                        # 线程安全的输出（快速模式：减少输出频率）
                        if not use_thread_session or page_index % 10 == 0 or page_index <= 3:
                            with self._result_lock:
                                page_size_info = f"（页大小: {page_size}条/页）" if api_config.get('menu') == 'fljs' and page_index <= 3 else ""
                                print(f"{thread_prefix} 第 {page_index} 页: 提取到 {len(page_links)} 个链接，新增 {after_count - before_count} 个（累计去重后: {after_count} 个）{page_size_info}")
                    else:
                        # 累计链接数没有增加（可能都是重复的）
                        no_new_links_count += 1
                        empty_page_count = 0
                        sample_links = list(page_links)[:3]
                        sample_ids = []
                        for link in sample_links:
                            # 兼容所有可能的链接路径
                            match = re.search(r'/(?:gddigui|gdchinalaw|gdfgwj|gddifang|regularation|gdnormativedoc)/([^/]+)\.html', link)
                            if match:
                                sample_ids.append(match.group(1)[:20] + '...')
                        sample_info = f"，样本链接ID: {', '.join(sample_ids)}" if sample_ids else ""
                        with self._result_lock:
                            print(f"{thread_prefix} 第 {page_index} 页: 提取到 {len(page_links)} 个链接，但累计数未增加（连续未增加: {no_new_links_count}/{max_no_new_links}{sample_info}）")
                        
                        if no_new_links_count >= max_no_new_links:
                            with self._result_lock:
                                print(f"{thread_prefix} 累计去重后链接数连续 {max_no_new_links} 页未增加，立即切换到下一个分类")
                            break
                    
                    previous_link_count = after_count
                else:
                    # 空页或请求失败
                    empty_page_count += 1
                    no_new_links_count += 1
                    with self._result_lock:
                        print(f"{thread_prefix} 警告: 第 {page_index} 页无链接（连续空页: {empty_page_count}/{max_empty_pages}，累计未增加: {no_new_links_count}/{max_no_new_links}）")
                    
                    if empty_page_count >= max_empty_pages:
                        with self._result_lock:
                            print(f"{thread_prefix} 连续 {max_empty_pages} 页无链接，立即切换到下一个分类")
                        break
                    if no_new_links_count >= max_no_new_links:
                        with self._result_lock:
                            print(f"{thread_prefix} 累计去重后链接数连续 {max_no_new_links} 页未增加，立即切换到下一个分类")
                        break
                
                page_index += 1
                # 添加延迟避免请求过快（多线程模式下减少延迟）
                time.sleep(0.1 if use_thread_session else 0.3)
            
            total_links = len(all_links)
            with self._result_lock:
                print(f"{thread_prefix} 提取完成: 共 {total_links:,} 个不重复的政策链接（遍历了 {page_index - 1} 页）")
            
            # 与预期总数对比（线程安全输出）
            if total_policies_from_html > 0:
                coverage = (total_links / total_policies_from_html * 100) if total_policies_from_html > 0 else 0
                diff = total_policies_from_html - total_links
                with self._result_lock:
                    print(f"{thread_prefix} 预期总数: {total_policies_from_html:,} 篇")
                    print(f"{thread_prefix} 实际提取: {total_links:,} 个不重复链接")
                    print(f"{thread_prefix} 覆盖率: {coverage:.1f}% ({diff:+,} 篇差异)")
                    if coverage < 80:
                        print(f"{thread_prefix} 警告: 覆盖率较低（{coverage:.1f}%），可能存在以下问题：")
                        print(f"{thread_prefix}   - 链接提取不完整（某些页面的链接未正确提取）")
                        print(f"{thread_prefix}   - 分页逻辑问题（可能提前停止遍历）")
                        print(f"{thread_prefix}   - 页面结构变化（网站结构已更新）")
                    elif coverage > 100:
                        print(f"{thread_prefix} 提示: 实际提取数({total_links:,})大于预期数({total_policies_from_html:,})")
                        print(f"{thread_prefix}   - 可能是预期数提取不准确")
                        print(f"{thread_prefix}   - 或实际提取包含了额外的数据")
            else:
                with self._result_lock:
                    print(f"{thread_prefix} 注意: 未能获取预期总数，无法进行覆盖率分析")
            
        except Exception as e:
            print(f"  提取失败: {e}")
            return {
                'category_name': category_name,
                'category_code': category_code,
                'total_links': 0,
                'total_pages': 0,
                'status': 'error',
                'error': str(e)
            }
        
        result = {
            'category_name': category_name,
            'category_code': category_code,
            'total_links': total_links,
            'total_pages': page_index - 1,
            'total_policies_from_html': total_policies_from_html,  # 从HTML提取的预期总数
            'coverage': (total_links / total_policies_from_html * 100) if total_policies_from_html > 0 else 0,
            'status': 'success' if total_links > 0 else 'empty',
            'links': list(all_links) if total_links > 0 else []
        }
        
        print()
        return result
    
    def test_single_category(self, category_code: str = None, category_name: str = None, filter_year: int = None):
        """测试单个分类"""
        if category_code and category_name:
            categories = [(category_name, category_code)]
        elif category_code:
            # 通过代码查找
            all_categories = self._get_flat_categories()
            found = [c for c in all_categories if c[1] == category_code]
            if not found:
                print(f"错误: 未找到分类代码 '{category_code}'")
                return None
            categories = found
        elif category_name:
            # 通过名称查找（支持部分匹配）
            all_categories = self._get_flat_categories()
            found = [c for c in all_categories if category_name in c[0]]
            if not found:
                print(f"错误: 未找到分类名称包含 '{category_name}' 的分类")
                return None
            categories = found
        else:
            print("错误: 必须指定 category_code 或 category_name")
            return None
        
        print(f"找到 {len(categories)} 个匹配的分类，开始提取链接...")
        print()
        
        results = []
        all_unique_links = set()
        total_links_all = 0
        total_pages_all = 0
        
        for idx, (cat_name, cat_code) in enumerate(categories, 1):
            print(f"\n[{idx}/{len(categories)}] ", end='')
            result = self.extract_links_for_category(cat_name, cat_code, filter_year=filter_year)
            results.append(result)
            
            if result['status'] == 'success':
                category_links = result.get('links', [])
                for link in category_links:
                    normalized = self._normalize_url(link)
                    all_unique_links.add(normalized)
                total_links_all += result['total_links']
                total_pages_all += result['total_pages']
        
        # 输出结果
        self._print_summary(results, total_links_all, total_pages_all, all_unique_links)
        
        return results, list(all_unique_links)
    
    def _print_summary(self, results, total_links_all, total_pages_all, all_unique_links):
        """输出汇总结果"""
        print("\n" + "=" * 90)
        print("链接提取结果汇总")
        print("=" * 90)
        print(f"{'序号':<6} {'分类名称':<25} {'分类代码':<15} {'提取数':<12} {'预期数':<12} {'覆盖率':<10} {'状态':<10}")
        print("-" * 90)
        
        for idx, result in enumerate(results, 1):
            status_display = result['status']
            if result['status'] == 'success':
                links_str = f"{result['total_links']:,}"
                expected_str = f"{result.get('total_policies_from_html', 0):,}"
                coverage_str = f"{result.get('coverage', 0):.1f}%"
                print(f"{idx:<6} {result['category_name']:<25} {result['category_code']:<15} "
                      f"{links_str:<12} {expected_str:<12} {coverage_str:<10} {status_display:<10}")
            elif result['status'] == 'empty':
                print(f"{idx:<6} {result['category_name']:<25} {result['category_code']:<15} "
                      f"{'0':<12} {'0':<12} {'0.0%':<10} {status_display:<10}")
            else:
                error = result.get('error', 'unknown')[:20]
                print(f"{idx:<6} {result['category_name']:<25} {result['category_code']:<15} "
                      f"{'0':<12} {'0':<12} {'0.0%':<10} {status_display:<10} ({error})")
        
        print("-" * 90)
        total_links_str = f"{total_links_all:,}"
        total_pages_str = f"{total_pages_all:,}"
        global_unique_str = f"{len(all_unique_links):,}"
        print(f"{'各分类合计':<6} {'':<25} {'':<15} {total_links_str:<15} {total_pages_str:<15} {'成功':<10}")
        print("-" * 90)
        print(f"{'全局去重后':<6} {'':<25} {'':<15} {global_unique_str:<15} {'':<15} {'完成':<10}")
        print("=" * 90)
        print(f"\n提取完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"说明: '各分类合计'为各分类链接数之和（可能有重复），'全局去重后'为所有分类去重后的唯一链接数")
    
    def _test_all_categories_with_year_split(self, categories: List[Tuple[str, str]], skip_codes: List[str] = None):
        """使用年份分割+多线程模式提取所有分类的政策链接
        
        为每个分类的每个年份创建独立任务，并行提取，突破500页限制
        
        Args:
            categories: 分类列表 [(name, code), ...]
            skip_codes: 要跳过的分类代码列表
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # 过滤跳过的分类
        if skip_codes:
            original_count = len(categories)
            categories = [c for c in categories if c[1] not in skip_codes]
            skipped_count = original_count - len(categories)
            if skipped_count > 0:
                print(f"跳过 {skipped_count} 个分类: {', '.join(skip_codes)}")
        
        # 第一步：为每个分类获取年份列表（并行获取以提升速度）
        print("第一步：获取各分类的可用年份（并行获取）...")
        category_years = {}  # {category_code: [(year, count), ...]}
        
        def get_category_years(args):
            """获取单个分类的年份列表"""
            category_name, category_code = args
            api_config = self._get_category_api_config(category_code)
            try:
                adv_url = api_config.get('init_page', f"{self.base_url}/{api_config['menu']}/adv")
                headers = self.headers.copy()
                if api_config.get('referer'):
                    headers['Referer'] = api_config['referer']
                
                resp = self.session.get(adv_url, headers=headers, timeout=10)  # 减少timeout
                if resp.status_code == 200:
                    years = self.extract_years_from_page(resp.text)
                    return category_code, years if years else None
                else:
                    return category_code, None
            except Exception as e:
                return category_code, None
        
        # 并行获取年份（使用小线程池）
        year_worker_count = min(7, len(categories), max(2, self.max_workers // 2))
        with ThreadPoolExecutor(max_workers=year_worker_count) as executor:
            year_futures = {executor.submit(get_category_years, (cat_name, cat_code)): (cat_name, cat_code) 
                           for cat_name, cat_code in categories}
            
            for future in as_completed(year_futures):
                cat_name, cat_code = year_futures[future]
                try:
                    result_code, years = future.result()
                    category_years[result_code] = years
                    if years:
                        print(f"  {cat_name} ({result_code}): 找到 {len(years)} 个年份")
                    else:
                        print(f"  {cat_name} ({result_code}): 未找到年份信息，将全量提取")
                except Exception as e:
                    category_years[cat_code] = None
                    print(f"  {cat_name} ({cat_code}): 获取年份异常，将全量提取")
        
        # 第二步：创建所有任务（每个分类的每个年份一个任务，如果没有年份则一个全量任务）
        tasks = []
        task_info = {}  # {task_id: (category_name, category_code, year)}
        task_id = 0
        
        for category_name, category_code in categories:
            years = category_years.get(category_code)
            if years:
                # 为每个年份创建一个任务
                for year, count in years:
                    task_id += 1
                    tasks.append((task_id, category_name, category_code, year))
                    task_info[task_id] = (category_name, category_code, year)
            else:
                # 没有年份信息，创建一个全量任务
                task_id += 1
                tasks.append((task_id, category_name, category_code, None))
                task_info[task_id] = (category_name, category_code, None)
        
        total_tasks = len(tasks)
        print(f"\n第二步：创建了 {total_tasks} 个提取任务（每个分类的每年一个任务）")
        print(f"使用 {self.max_workers} 个线程并行处理（快速模式：已优化延迟、重试和输出）...")
        print()
        
        # 第三步：并行执行所有任务
        def process_year_task(args):
            task_id, category_name, category_code, year = args
            thread_name = threading.current_thread().name
            try:
                result = self.extract_links_for_category(
                    category_name=category_name,
                    category_code=category_code,
                    filter_year=year,
                    use_thread_session=True
                )
                # 在结果中添加任务信息
                result['task_id'] = task_id
                result['year'] = year
                return task_id, result
            except Exception as e:
                return task_id, {
                    'task_id': task_id,
                    'category_name': category_name,
                    'category_code': category_code,
                    'year': year,
                    'total_links': 0,
                    'total_pages': 0,
                    'status': 'error',
                    'error': str(e)
                }
        
        start_time = time.time()
        results_by_category = {}  # {category_code: [result1, result2, ...]}
        all_unique_links = set()
        total_links_all = 0
        total_pages_all = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_task = {executor.submit(process_year_task, task): task for task in tasks}
            
            # 收集结果
            completed = 0
            task_results = {}
            
            for future in as_completed(future_to_task):
                completed += 1
                try:
                    task_id, result = future.result()
                    task_results[task_id] = result
                    
                    category_code = result['category_code']
                    if category_code not in results_by_category:
                        results_by_category[category_code] = []
                    results_by_category[category_code].append(result)
                    
                    # 添加到全局去重集合
                    if result['status'] == 'success':
                        category_links = result.get('links', [])
                        for link in category_links:
                            normalized = self._normalize_url(link)
                            all_unique_links.add(normalized)
                        total_links_all += result['total_links']
                        total_pages_all += result['total_pages']
                    
                    year_info = f" [{result['year']}年]" if result.get('year') else " [全量]"
                    # 快速模式：减少输出，每完成10%或最后几个任务才输出
                    should_print = (completed % max(1, total_tasks // 10) == 0) or (completed <= 5) or (completed > total_tasks - 5)
                    if should_print:
                        with self._result_lock:
                            print(f"[进度 {completed}/{total_tasks}] {result['category_name']}{year_info}: {result['status']}, {result.get('total_links', 0)} 个链接")
                        
                except Exception as e:
                    task = future_to_task[future]
                    task_id = task[0]
                    with self._result_lock:
                        print(f"[进度 {completed}/{total_tasks}] 任务 {task_id} 处理失败: {e}")
        
        elapsed_time = time.time() - start_time
        
        # 第四步：汇总结果（按分类汇总）
        print(f"\n年份分割+多线程处理完成，耗时: {elapsed_time:.2f} 秒")
        print()
        
        # 合并每个分类的年份结果
        final_results = []
        for category_name, category_code in categories:
            category_results = results_by_category.get(category_code, [])
            if not category_results:
                continue
            
            # 合并该分类所有年份的链接
            category_links = []
            category_total_links = 0
            category_total_pages = 0
            success_count = 0
            
            for result in category_results:
                if result['status'] == 'success':
                    success_count += 1
                    category_links.extend(result.get('links', []))
                    category_total_links += result.get('total_links', 0)
                    category_total_pages += result.get('total_pages', 0)
            
            # 去重该分类的链接
            category_unique_links = len(set(self._normalize_url(link) for link in category_links))
            
            final_result = {
                'category_name': category_name,
                'category_code': category_code,
                'total_links': category_unique_links,
                'total_pages': category_total_pages,
                'status': 'success' if success_count > 0 else 'error',
                'links': list(set(self._normalize_url(link) for link in category_links)),
                'year_tasks': len(category_results),
                'successful_years': success_count
            }
            final_results.append(final_result)
        
        # 打印汇总表格
        self._print_summary_table(final_results, all_unique_links, total_links_all, total_pages_all)
        
        return final_results, all_unique_links
    
    def test_all_categories(self, skip_codes: List[str] = None, use_year_split: bool = False):
        """提取所有分类的政策链接（去重）
        
        Args:
            skip_codes: 要跳过的分类代码列表
            use_year_split: 是否使用年份分割（对每个分类的每个年份分别提取，突破500页限制）
        """
        categories = self._get_flat_categories()
        
        # 过滤跳过的分类
        if skip_codes:
            original_count = len(categories)
            categories = [c for c in categories if c[1] not in skip_codes]
            skipped_count = original_count - len(categories)
            if skipped_count > 0:
                print(f"跳过 {skipped_count} 个分类: {', '.join(skip_codes)}")
        
        # 如果启用年份分割，使用专门的方法
        if use_year_split:
            return self._test_all_categories_with_year_split(categories, skip_codes)
        
        print(f"找到 {len(categories)} 个分类，开始提取链接...")
        print()
        
        # 根据线程数决定使用单线程还是多线程
        if self.max_workers == 1 or len(categories) == 1:
            # 单线程模式（保持原有逻辑）
            results = []
            all_unique_links = set()  # 全局去重集合
            total_links_all = 0
            total_pages_all = 0
            
            for idx, (category_name, category_code) in enumerate(categories, 1):
                print(f"\n[{idx}/{len(categories)}] ", end='')
                result = self.extract_links_for_category(category_name, category_code, use_thread_session=False)
                results.append(result)
                
                if result['status'] == 'success':
                    # 添加到全局去重集合
                    category_links = result.get('links', [])
                    for link in category_links:
                        normalized = self._normalize_url(link)
                        all_unique_links.add(normalized)
                    
                    total_links_all += result['total_links']
                    total_pages_all += result['total_pages']
                    print(f"分类 [{category_name}] 处理完成，继续下一个分类...")
                elif result['status'] == 'empty':
                    print(f"分类 [{category_name}] 无数据，自动切换到下一个分类...")
                else:
                    print(f"分类 [{category_name}] 处理出错，自动切换到下一个分类...")
                
                # 分类之间添加延迟
                if idx < len(categories):
                    time.sleep(1)
        else:
            # 多线程模式
            print(f"使用多线程模式处理 {len(categories)} 个分类（最大 {self.max_workers} 个线程）...")
            print()
            
            results = []
            all_unique_links = set()  # 全局去重集合（需要线程安全）
            total_links_all = 0
            total_pages_all = 0
            
            # 定义任务执行函数
            def process_category(args):
                idx, category_name, category_code = args
                try:
                    result = self.extract_links_for_category(
                        category_name, 
                        category_code, 
                        use_thread_session=True
                    )
                    return idx, result
                except Exception as e:
                    return idx, {
                        'category_name': category_name,
                        'category_code': category_code,
                        'total_links': 0,
                        'total_pages': 0,
                        'status': 'error',
                        'error': str(e)
                    }
            
            # 准备任务列表
            tasks = [(idx + 1, cat_name, cat_code) for idx, (cat_name, cat_code) in enumerate(categories)]
            
            # 使用线程池执行
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_task = {executor.submit(process_category, task): task for task in tasks}
                
                # 收集结果（按提交顺序）
                completed = 0
                task_results = {}
                
                for future in as_completed(future_to_task):
                    completed += 1
                    try:
                        idx, result = future.result()
                        task_results[idx] = result
                        
                        with self._result_lock:
                            print(f"[进度 {completed}/{len(categories)}] 分类 [{result['category_name']}] 处理完成")
                        
                    except Exception as e:
                        task = future_to_task[future]
                        idx = task[0]
                        with self._result_lock:
                            print(f"[进度 {completed}/{len(categories)}] 分类处理失败: {e}")
                        task_results[idx] = {
                            'category_name': task[1],
                            'category_code': task[2],
                            'total_links': 0,
                            'total_pages': 0,
                            'status': 'error',
                            'error': str(e)
                        }
            
            # 按原始顺序整理结果
            for idx in sorted(task_results.keys()):
                result = task_results[idx]
                results.append(result)
                
                if result['status'] == 'success':
                    # 添加到全局去重集合（线程安全）
                    category_links = result.get('links', [])
                    with self._result_lock:
                        for link in category_links:
                            normalized = self._normalize_url(link)
                            all_unique_links.add(normalized)
                    
                    total_links_all += result['total_links']
                    total_pages_all += result['total_pages']
            
            elapsed_time = time.time() - start_time
            print(f"\n多线程处理完成，耗时: {elapsed_time:.2f} 秒")
        
        # 输出汇总结果
        self._print_summary(results, total_links_all, total_pages_all, all_unique_links)
        
        return results, list(all_unique_links)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='广东省政策爬虫链接统计工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 测试所有分类（智能多线程模式，自动调整）
  python test_guangdong_pages.py
  
  # 测试所有分类（指定4个线程）
  python test_guangdong_pages.py --threads 4
  
  # 测试单个分类（智能模式：自动2线程）
  python test_guangdong_pages.py --category-code XP08
  
  # 按年份筛选单个分类
  python test_guangdong_pages.py --category-code XP08 --year 2020
  
  # 单线程模式（如需调试）
  python test_guangdong_pages.py --threads 1
  
  # 测试所有分类，但跳过异常分类
  python test_guangdong_pages.py --skip XP08,XU13
  
  # 列出所有分类
  python test_guangdong_pages.py --list

智能多线程说明:
  - 默认启用智能多线程模式，根据任务自动调整线程数
  - 单个分类：自动使用2线程
  - 所有分类：自动使用分类数（最多8线程）
  - 如需单线程调试，使用 --threads 1
  - 多线程可以显著提高处理速度

年份分割模式 (突破500页限制):
  - 使用 --year-split 启用年份分割+多线程模式
  - 为每个分类的每个年份创建独立任务，并行提取
  - 特别适用于数据量大的分类（如地方规范性文件XP08）
  - 示例: python test_guangdong_pages.py --year-split --threads 10

已知分类:
  - XP08 (地方规范性文件): 数据量大（40,231篇），可使用年份筛选或--year-split
  - XU13 (自治条例和单行条例): 覆盖率较低
        """
    )
    
    parser.add_argument(
        '--category-code', '-c',
        type=str,
        help='指定要测试的分类代码（如: XP08）'
    )
    parser.add_argument(
        '--category-name', '-n',
        type=str,
        help='指定要测试的分类名称（支持部分匹配，如: "地方规范性文件"）'
    )
    parser.add_argument(
        '--skip',
        type=str,
        help='要跳过的分类代码，用逗号分隔（如: XP08,XU13）'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='列出所有可用的分类'
    )
    parser.add_argument(
        '--year', '-y',
        type=int,
        help='按指定年份筛选（如: --year 2021）'
    )
    parser.add_argument(
        '--show-years',
        action='store_true',
        help='显示每个分类的可用年份（不提取链接）'
    )
    parser.add_argument(
        '--threads', '-t',
        type=int,
        default=None,
        help='多线程模式下的线程数（默认: 智能模式，自动调整；单线程使用 --threads 1）'
    )
    parser.add_argument(
        '--year-split',
        action='store_true',
        help='使用年份分割模式：为每个分类的每个年份创建独立任务，并行提取（突破500页限制）'
    )
    
    args = parser.parse_args()
    
    # 智能线程数：如果未指定threads，根据任务自动调整
    if args.threads is None:
        # 智能模式：根据任务自动决定线程数
        if args.category_code or args.category_name:
            # 单个分类：使用2个线程（一个主任务，一个备用）
            args.threads = 2
        else:
            # 所有分类：根据分类数设置
            from space_planning.spider.spider_config import SpiderConfig
            config = SpiderConfig.get_guangdong_config()
            category_config = config.get('category_config', {})
            num_categories = len([k for k in category_config.keys() if isinstance(category_config[k], dict)])
            # 自动设置线程数为分类数，但不超过8
            args.threads = min(num_categories, 8)
        
        print(f"[智能多线程] 自动启用 {args.threads} 个线程")
        print()
    
    try:
        counter = GuangdongPageCounter(max_workers=args.threads)
        
        # 列出所有分类
        if args.list:
            categories = counter._get_flat_categories()
            print("=" * 90)
            print("所有可用分类")
            print("=" * 90)
            print(f"{'序号':<6} {'分类名称':<40} {'分类代码':<15}")
            print("-" * 90)
            for idx, (name, code) in enumerate(categories, 1):
                print(f"{idx:<6} {name:<40} {code:<15}")
            print("=" * 90)
            return
        
        # 显示各分类的可用年份
        if args.show_years:
            categories = counter._get_flat_categories()
            print("=" * 90)
            print("各分类的可用年份")
            print("=" * 90)
            for idx, (category_name, category_code) in enumerate(categories, 1):
                print(f"\n[{idx}/{len(categories)}] {category_name} (代码: {category_code})")
                # 获取API配置
                api_config = counter._get_category_api_config(category_code)
                
                # 直接从高级搜索页面获取年份信息（年份筛选器通常在adv页面）
                try:
                    adv_url = api_config.get('init_page', f"{counter.base_url}/{api_config['menu']}/adv")
                    headers = counter.headers.copy()
                    if api_config.get('referer'):
                        headers['Referer'] = api_config['referer']
                    
                    resp = counter.session.get(adv_url, headers=headers, timeout=30)
                    if resp.status_code == 200:
                        years = counter.extract_years_from_page(resp.text)
                        if years:
                            print(f"  可用年份 ({len(years)}个):")
                            # 每行显示5个年份
                            for i in range(0, len(years), 5):
                                year_line = years[i:i+5]
                                year_str = ', '.join([f"{y[0]}年({y[1]})" for y in year_line])
                                print(f"    {year_str}")
                        else:
                            # 如果仍然找不到，尝试从搜索结果页面的第一页提取（备用）
                            search_params = counter._get_search_parameters(category_code=category_code, page_index=1, api_config=api_config)
                            search_headers = counter.headers.copy()
                            search_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
                            if api_config.get('referer'):
                                search_headers['Referer'] = api_config['referer']
                            search_resp = counter.session.post(api_config['search_url'], data=search_params, headers=search_headers, timeout=30)
                            if search_resp.status_code == 200:
                                years = counter.extract_years_from_page(search_resp.text)
                                if years:
                                    print(f"  可用年份 ({len(years)}个):")
                                    for i in range(0, len(years), 5):
                                        year_line = years[i:i+5]
                                        year_str = ', '.join([f"{y[0]}年({y[1]})" for y in year_line])
                                        print(f"    {year_str}")
                                else:
                                    print(f"  未找到年份信息（搜索结果页面通常不包含年份筛选器）")
                            else:
                                print(f"  备用请求失败: {search_resp.status_code}")
                    else:
                        print(f"  请求失败: {resp.status_code}")
                except Exception as e:
                    print(f"  错误: {e}")
                # 快速模式：减少延迟
            print("\n" + "=" * 90)
            return
        
        # 测试单个分类
        if args.category_code or args.category_name:
            results, unique_links = counter.test_single_category(
                category_code=args.category_code,
                category_name=args.category_name,
                filter_year=args.year
            )
            if results is None:
                sys.exit(1)
        else:
            # 测试所有分类
            skip_codes = None
            if args.skip:
                skip_codes = [code.strip() for code in args.skip.split(',')]
            
            # 如果启用年份分割模式，使用年份分割+多线程
            if args.year_split:
                print("[模式] 年份分割+多线程模式（为每个分类的每个年份创建独立任务）")
                print(f"[配置] 线程数: {args.threads}")
                print()
                results, unique_links = counter.test_all_categories(skip_codes=skip_codes, use_year_split=True)
            else:
                results, unique_links = counter.test_all_categories(skip_codes=skip_codes)
        
        print(f"\n脚本执行完成！")
        print(f"共提取到 {len(unique_links):,} 个不重复的政策链接（未访问详情页）")
        
    except KeyboardInterrupt:
        print("\n\n用户中断提取")
        sys.exit(0)
    except Exception as e:
        print(f"\n提取失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

