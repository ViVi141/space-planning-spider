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
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import re

from .anti_crawler import AntiCrawlerManager
from .monitor import CrawlerMonitor
from ..core import database as db

class GuangdongSpider:
    """广东省政策爬虫类"""
    
    def __init__(self):
        self.base_url = "https://gd.pkulaw.com"
        # 根据真实请求URL更新
        self.search_url = "https://gd.pkulaw.com/china/related/gdchinalaw/"
        self.result_url = "https://gd.pkulaw.com/china/related/gdchinalaw/"
        self.session = requests.Session()
        
        # 防反爬虫管理器
        self.anti_crawler = AntiCrawlerManager()
        
        # 监控器
        self.monitor = CrawlerMonitor()
        
        # 速率限制器
        from .anti_crawler import RequestRateLimiter
        self.rate_limiter = RequestRateLimiter()
        
        # 速度模式
        self.speed_mode = "正常速度"
        
        # 请求头 - 根据真实XHR请求优化
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0',
            'Accept': 'text/html, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Host': 'gd.pkulaw.com',
            'Referer': 'https://gd.pkulaw.com/',
            'Sec-Ch-Ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        # 设置会话
        self.session.headers.update(self.headers)
        
        # 初始化会话，获取必要的Cookie
        try:
            # 先访问首页获取会话Cookie
            resp = self.session.get(self.base_url, timeout=10)
            if resp.status_code == 200:
                print("✓ 成功获取广东省法规规章数据库会话")
                
                # 设置一些基本的Cookie（根据真实请求）
                self.session.cookies.set('xCloseNew', '8', domain='gd.pkulaw.com')
                self.session.cookies.set('redSpot', 'false', domain='gd.pkulaw.com')
            else:
                print(f"⚠️ 获取会话失败，状态码: {resp.status_code}")
        except Exception as e:
            print(f"⚠️ 初始化会话失败: {e}")
        
    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None, 
                      speed_mode="正常速度", disable_speed_limit=False, stop_callback=None):
        """爬取广东省政策文件"""
        print(f"开始爬取广东省政策文件，关键词: {keywords}")
        
        # 设置速度模式
        self.speed_mode = speed_mode
        
        # 根据速度模式调整延迟
        if speed_mode == "快速模式":
            delay_range = (0.1, 0.5)
        elif speed_mode == "慢速模式":
            delay_range = (2.0, 5.0)
        else:  # 正常速度
            delay_range = (0.5, 2.0)
        
        # 处理时间参数
        dt_start = None
        dt_end = None
        if start_date:
            try:
                dt_start = datetime.strptime(start_date, '%Y-%m-%d')
                print(f"时间过滤：起始日期 {start_date}")
            except ValueError:
                print(f"起始日期格式错误: {start_date}")
        
        if end_date:
            try:
                dt_end = datetime.strptime(end_date, '%Y-%m-%d')
                print(f"时间过滤：结束日期 {end_date}")
            except ValueError:
                print(f"结束日期格式错误: {end_date}")
        
        policies = []
        page_no = 1
        max_pages = 50  # 最大爬取页数
        
        # 处理关键词 - 如果没有关键词，使用空字符串进行全量搜索
        if not keywords or (isinstance(keywords, list) and len(keywords) == 0):
            search_keyword = ""  # 空关键词，搜索所有政策
            print("使用空关键词进行全量搜索")
        else:
            search_keyword = ' '.join(keywords) if isinstance(keywords, list) else str(keywords)
            print(f"使用关键词: {search_keyword}")
        
        # 构建搜索参数 - 根据真实请求参数
        search_params = {
            'currentMenu': 'china',
            'keywords': search_keyword,
            'searchKeywordType': 'Title',
            'matchType': 'Exact',
            'rangeType': 'Piece'
        }
        
        if callback:
            callback("正在连接广东省法规规章数据库...")
        
        try:
            while page_no <= max_pages:
                # 检查是否停止
                if stop_callback and stop_callback():
                    print("用户已停止爬取")
                    break
                
                # 注意：真实请求没有分页参数，这里先尝试单次请求
                if page_no > 1:
                    print("当前请求不支持分页，停止爬取")
                    break
                
                if callback:
                    callback(f"正在爬取第 {page_no} 页...")
                
                # 发送搜索请求 - 尝试多种方式
                resp = None
                success = False
                
                # 方法1：尝试直接搜索
                try:
                    resp = self.session.get(
                        self.search_url, 
                        params=search_params,
                        timeout=15
                    )
                    if resp.status_code == 200:
                        success = True
                        self.monitor.record_request(self.search_url, success=True)
                except Exception as e:
                    print(f"方法1失败: {e}")
                
                # 方法2：如果方法1失败，尝试POST请求
                if not success:
                    try:
                        resp = self.session.post(
                            self.search_url,
                            data=search_params,
                            timeout=15
                        )
                        if resp.status_code == 200:
                            success = True
                            self.monitor.record_request(self.search_url, success=True)
                    except Exception as e:
                        print(f"方法2失败: {e}")
                
                # 方法3：如果前两种方法都失败，尝试直接访问结果页面
                if not success:
                    try:
                        # 构建一个简单的查询URL
                        simple_params = {'keyword': search_keyword}
                        resp = self.session.get(
                            self.result_url,
                            params=simple_params,
                            timeout=15
                        )
                        if resp.status_code == 200:
                            success = True
                            self.monitor.record_request(self.result_url, success=True)
                    except Exception as e:
                        print(f"方法3失败: {e}")
                
                if not success:
                    self.monitor.record_request(self.search_url, success=False, error_type="所有方法都失败")
                    print("所有搜索方法都失败")
                    if callback:
                        callback("所有搜索方法都失败")
                    break
                
                # 解析搜索结果
                if resp and resp.content:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                else:
                    print("响应内容为空")
                    break
                
                # 查找所有可能的分类链接 - 不限制特定分类
                category_links = soup.find_all('a', href=True)
                
                if not category_links:
                    print(f"第 {page_no} 页未找到分类链接")
                    if callback:
                        callback(f"第 {page_no} 页未找到分类链接")
                    break
                
                # 初始化页面政策列表
                page_policies = []
                
                # 处理每个分类 - 不限制特定分类，处理所有可能的分类
                for link in category_links:
                    href = link.get('href')
                    if not href:
                        continue
                    
                    # 检查是否是有效的分类链接（包含常见的关键词）
                    if any(keyword in href.lower() for keyword in ['dfxfg', 'sfjs', 'dfzfgz', 'fljs', 'gdnormativedoc', 'gddigui', 'gdchinalaw']):
                        category_name = link.get_text().strip()
                        print(f"处理分类: {category_name}")
                        
                        if callback:
                            callback(f"正在处理分类: {category_name}")
                        
                        # 获取该分类下的具体法规列表
                        category_policies = self._get_category_policies(href, callback, stop_callback)
                        if category_policies:
                            # 对分类政策进行时间过滤
                            filtered_policies = []
                            for policy in category_policies:
                                if self._is_policy_in_date_range(policy, dt_start, dt_end):
                                    filtered_policies.append(policy)
                            
                            if filtered_policies:
                                page_policies.extend(filtered_policies)
                                print(f"分类 {category_name} 过滤后保留 {len(filtered_policies)} 条政策")
                
                # 如果没有找到特定分类，尝试直接解析页面中的政策项目
                if not page_policies:
                    print("尝试直接解析页面中的政策项目...")
                    if callback:
                        callback("尝试直接解析页面中的政策项目...")
                    
                    # 直接查找页面中的政策项目
                    policy_items = soup.find_all('li')
                    for item in policy_items:
                        try:
                            policy_data = self._parse_policy_item(item)
                            if policy_data and self._is_policy_in_date_range(policy_data, dt_start, dt_end):
                                page_policies.append(policy_data)
                                
                                # 发送政策数据信号
                                if callback:
                                    callback(f"POLICY_DATA:{policy_data['title']}|{policy_data['pub_date']}|{policy_data['source']}|{policy_data['content']}")
                        except Exception as e:
                            print(f"解析政策项目失败: {e}")
                            continue
                
                if not page_policies:
                    print(f"第 {page_no} 页未获取到政策")
                    if callback:
                        callback(f"第 {page_no} 页未获取到政策")
                    break
                
                policies.extend(page_policies)
                
                if callback:
                    callback(f"第 {page_no} 页获取 {len(page_policies)} 条政策")
                
                # 根据速度设置决定是否添加延迟
                if not disable_speed_limit:
                    time.sleep(random.uniform(*delay_range))
                
                page_no += 1
                
                # 检查是否有下一页
                next_page = soup.find('a', string=re.compile(r'下一页|下页|>'))
                if not next_page:
                    break
        
        except Exception as e:
            print(f"爬取过程中出错: {e}")
            if callback:
                callback(f"爬取过程中出错: {e}")
        
        print(f"爬取完成，共获取 {len(policies)} 条广东省政策")
        if callback:
            callback(f"爬取完成，共获取 {len(policies)} 条广东省政策")
        
        return policies
    
    def _get_category_policies(self, category_url, callback=None, stop_callback=None):
        """获取指定分类下的政策列表"""
        try:
            # 构建完整的URL
            if not category_url.startswith('http'):
                category_url = urljoin(self.base_url, category_url)
            
            if callback:
                callback(f"正在获取分类页面: {category_url}")
            
            # 发送请求获取分类页面
            resp = self.session.get(category_url, timeout=15)
            if resp.status_code != 200:
                print(f"获取分类页面失败: {resp.status_code}")
                return []
            
            self.monitor.record_request(category_url, success=True)
            
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # 查找政策列表 - 根据网站实际HTML结构
            policy_items = soup.find_all('li')  # 所有li标签，因为政策项目都在li中
            
            if not policy_items:
                print(f"分类页面未找到政策项目")
                return []
            
            category_policies = []
            
            for item in policy_items:
                # 检查是否停止
                if stop_callback and stop_callback():
                    print("用户已停止爬取")
                    break
                
                try:
                    policy_data = self._parse_policy_item(item)
                    if policy_data:
                        category_policies.append(policy_data)
                        
                        # 发送政策数据信号
                        if callback:
                            callback(f"POLICY_DATA:{policy_data['title']}|{policy_data['pub_date']}|{policy_data['source']}|{policy_data['content']}")
                
                except Exception as e:
                    print(f"解析政策项目失败: {e}")
                    continue
            
            return category_policies
            
        except Exception as e:
            print(f"获取分类政策失败: {e}")
            self.monitor.record_request(category_url, success=False, error_type=str(e))
            return []
    
    def _parse_policy_item(self, item):
        """解析单个政策项目 - 根据网站实际结构优化"""
        try:
            # 检查是否包含政策内容（必须有list-title和related-info）
            title_div = item.find('div', class_='list-title')
            info_div = item.find('div', class_='related-info')
            
            if not title_div or not info_div:
                return None
            
            # 查找标题和链接
            title_elem = title_div.find('h4').find('a') if title_div.find('h4') else None
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            if not title:
                return None
            
            # 获取链接
            link = title_elem.get('href', '')
            if link and not link.startswith('http'):
                link = urljoin(self.base_url, link)
            
            # 解析相关信息（时效性 / 发文字号 / 公布日期 / 施行日期）
            info_text = info_div.get_text(strip=True)
            
            # 提取发文字号（在第一个/之后，第二个/之前）
            doc_number = ""
            parts = info_text.split(' / ')
            if len(parts) >= 2:
                doc_number = parts[1].strip()
            
            # 提取公布日期（在第二个/之后，第三个/之前）
            pub_date = ""
            if len(parts) >= 3:
                date_text = parts[2].strip()
                # 解析日期格式：2021.10.30公布
                date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_text)
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
                return content_div.get_text(strip=True)
            else:
                return soup.get_text(strip=True)
        
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
                    policy['crawl_time']
                )
            elif isinstance(policy, (list, tuple)) and len(policy) >= 6:
                db.insert_policy(
                    policy[1],  # level
                    policy[2],  # title
                    policy[3],  # pub_date
                    policy[4],  # source
                    policy[5],  # content
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # crawl_time
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
                    # 格式：2021.10.30
                    dt_policy = datetime.strptime(pub_date, '%Y.%m.%d')
                elif '-' in pub_date:
                    # 格式：2021-10-30
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