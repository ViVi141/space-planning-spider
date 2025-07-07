#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
广东省政策爬虫模块
爬取广东省法规规章数据库 (https://gd.pkulaw.com/)
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

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .anti_crawler import AntiCrawlerManager, RequestRateLimiter
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
        self.rate_limiter = RequestRateLimiter()
        
        # 创建会话
        self.session = requests.Session()
        self.session.verify = False
        
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
    
    def _init_session(self):
        """初始化会话"""
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 设置Cookie
        self.session.cookies.set('JSESSIONID', '1234567890ABCDEF', domain='gd.pkulaw.com')
        
        # 访问首页获取必要的Cookie
        try:
            resp = self.session.get(self.base_url, timeout=10)
            if resp.status_code == 200:
                print("成功访问首页，获取必要Cookie")
            else:
                print(f"访问首页失败，状态码: {resp.status_code}")
        except Exception as e:
            print(f"访问首页异常: {e}")
    
    def _get_all_categories(self):
        """获取所有分类信息"""
        # 定义广东省政策分类
        categories = [
            ("地方性法规", "XM07"),
            ("自治条例和单行条例", "XU13"), 
            ("地方政府规章", "XO08"),
            ("地方规范性文件", "XP08")
        ]
        return categories
    
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
        
        # 获取所有分类
        categories = self._get_all_categories()
        print(f"找到 {len(categories)} 个分类")
        
        all_policies = []
        
        # 遍历所有分类
        for category_name, category_url in categories:
            if stop_callback and stop_callback():
                print("用户已停止爬取")
                break
                
            print(f"正在爬取分类: {category_name}")
            if callback:
                callback(f"正在爬取分类: {category_name}")
            
            # 爬取当前分类的所有页面
            page_index = 1
            max_pages = 100  # 设置最大页数限制，避免无限循环
            category_policies = []
            
            while page_index <= max_pages:
                if stop_callback and stop_callback():
                    print("用户已停止爬取")
                    break
                    
                try:
                    # 构建请求参数
                    post_data = {
                        'searchWord': keywords[0] if keywords else '',
                        'searchType': '1',
                        'searchScope': '1',
                        'searchField': '1',
                        'searchSort': '1',
                        'searchPage': str(page_index),
                        'searchPageSize': '20',
                        'searchCategory': category_name,
                        'searchDateStart': start_date or '',
                        'searchDateEnd': end_date or ''
                    }
                    
                    headers = self.headers.copy()
                    headers.update(self.anti_crawler.get_random_headers())
                    
                    resp = self.session.post(
                        "https://gd.pkulaw.com/china/search/RecordSearch",
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
                        print(f"分类[{category_name}] 第 {page_index} 页未获取到政策，停止翻页")
                        break
                    
                    # 更新总爬取数量
                    total_crawled += len(page_policies)
                    
                    if callback:
                        callback(f"分类[{category_name}] 第 {page_index} 页获取 {len(page_policies)} 条政策（累计爬取: {total_crawled} 条）")
                    
                    # 过滤时间并发送政策数据信号
                    filtered_policies = []
                    for policy in page_policies:
                        # 如果启用时间过滤，则进行过滤
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
        
        # 最终统计
        total_saved = len(all_policies)
        
        print(f"爬取完成统计:")
        print(f"  总爬取数量: {total_crawled} 条")
        if enable_time_filter:
            print(f"  过滤后数量: {total_filtered} 条")
            print(f"  最终保存数量: {total_saved} 条")
        else:
            print(f"  最终保存数量: {total_saved} 条（未启用时间过滤）")
        
        if callback:
            callback(f"爬取完成统计:")
            callback(f"  总爬取数量: {total_crawled} 条")
            if enable_time_filter:
                callback(f"  过滤后数量: {total_filtered} 条") 
                callback(f"  最终保存数量: {total_saved} 条")
            else:
                callback(f"  最终保存数量: {total_saved} 条（未启用时间过滤）")
        
        return all_policies
    
    def _parse_policy_list_record_search(self, soup, callback=None, stop_callback=None, category_name=None):
        """解析RecordSearch接口返回的政策列表"""
        policies = []
        
        # 查找所有政策项目 - 根据真实HTML结构
        policy_items = []
        
        # 方法1：查找所有包含list-title的li标签（这是最准确的方法）
        all_li = soup.find_all('li')
        policy_items = [li for li in all_li if li.find('div', class_='list-title')]
        print(f"方法1找到 {len(policy_items)} 个包含list-title的li标签")
        
        # 方法2：如果没找到，尝试查找所有包含block类的div的li
        if not policy_items:
            policy_items = [li for li in all_li if li.find('div', class_='block')]
            print(f"方法2找到 {len(policy_items)} 个包含block的li标签")
        
        # 方法3：如果还是没找到，查找所有包含政策链接的li
        if not policy_items:
            policy_items = []
            for li in all_li:
                links = li.find_all('a')
                for link in links:
                    link_text = link.get_text(strip=True)
                    link_href = link.get('href', '')
                    # 检查是否是政策链接（包含特定关键词且不是javascript链接）
                    if (link_text and link_href and 
                        link_href.startswith('/gdchinalaw/') and
                        any(keyword in link_text for keyword in ['条例', '规定', '办法', '通知', '意见', '决定', '公告'])):
                        policy_items.append(li)
                        break
            print(f"方法3找到 {len(policy_items)} 个包含政策链接的li标签")
        
        if not policy_items:
            print("未找到政策项目")
            return []
        
        print(f"最终找到 {len(policy_items)} 个政策项目")
        
        for item in policy_items:
            # 检查是否停止
            if stop_callback and stop_callback():
                print("用户已停止爬取")
                break
            
            try:
                policy_data = self._parse_policy_item_record_search(item, category_name or "广东省政策")
                if policy_data:
                    policies.append(policy_data)
                    
                    # 发送政策数据信号
                    if callback:
                        callback(f"获取政策: {policy_data.get('title', '未知标题')}")
                        
            except Exception as e:
                print(f"解析政策项目失败: {e}")
                continue
        
        return policies
    
    def _parse_policy_item_record_search(self, item, category_name):
        """解析RecordSearch接口返回的单个政策项目 - 支持多种HTML结构"""
        try:
            print(f"开始解析政策项目: {item.name if hasattr(item, 'name') else 'unknown'}")
            
            # 方法1：查找标准结构 (list-title + related-info)
            title_div = item.find('div', class_='list-title')
            if title_div:
                print("找到list-title div，使用标准结构解析")
                return self._parse_standard_structure(item, category_name)
            
            # 方法2：查找其他可能的结构
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
                    (any(keyword in link_text for keyword in ['条例', '规定', '办法', '通知', '意见', '决定', '公告', '细则']) or
                     len(link_text) > 10)):  # 标题通常较长
                    title = link_text
                    link = link_href
                    break
            
            if not title or not link:
                print("未找到有效的标题链接")
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
                    date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_text)
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
            
            # 提取正文内容
            content_div = soup.find('div', class_='content') or \
                         soup.find('div', class_='article-content') or \
                         soup.find('div', class_='text')
            
            if content_div:
                return content_div.get_text(strip=True)  # type: ignore
            else:
                return soup.get_text(strip=True)  # type: ignore
        
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
            'rate_limiter_stats': {
                'max_requests': self.rate_limiter.max_requests,
                'time_window': self.rate_limiter.time_window
            }
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

# 为兼容性添加别名类
class GuangdongPolicyCrawler(GuangdongSpider):
    """广东省政策爬虫类（GuangdongSpider的别名）"""
    pass

if __name__ == "__main__":
    spider = GuangdongSpider()
    policies = spider.crawl_policies(['规划', '空间', '用地'])
    spider.save_to_db(policies)
    print(f"爬取到 {len(policies)} 条广东省政策") 