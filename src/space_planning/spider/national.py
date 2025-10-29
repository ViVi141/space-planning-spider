import requests
from datetime import datetime
import time
import random
import sys
import os
from typing import Dict, Optional

# 添加路径以便导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from core import database as db
from .anti_crawler import AntiCrawlerManager
from .monitor import CrawlerMonitor
from bs4 import BeautifulSoup, Tag

# 机构名称常量
LEVEL_NAME = "住房和城乡建设部"

class NationalSpider:
    def __init__(self):
        self.api_url = "https://www.mohurd.gov.cn/api-gateway/jpaas-publish-server/front/page/build/unit"
        
        # 设置级别
        self.level = "住房和城乡建设部"
        
        # 初始化防反爬虫管理器
        self.anti_crawler = AntiCrawlerManager()
        self.monitor = CrawlerMonitor()
        
        # 速度模式配置
        self.speed_mode = "正常速度"
        
        # 基础参数
        self.base_params = {
            'webId': '86ca573ec4df405db627fdc2493677f3',
            'pageId': 'vhiC3JxmPC8o7Lqg4Jw0E',
            'parseType': 'bulidstatic',
            'pageType': 'column',
            'tagId': '内容1',
            'tplSetId': 'fc259c381af3496d85e61997ea7771cb',
            'unitUrl': '/api-gateway/jpaas-publish-server/front/page/build/unit'
        }
        
        # 设置特定的请求头（住建部网站需要）
        self.special_headers = {
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Referer': 'https://www.mohurd.gov.cn/gongkai/zc/wjk/index.html',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-KL-SaaS-Ajax-Request': 'Ajax_Request',
            'X-Requested-With': 'XMLHttpRequest'
        }

    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None, speed_mode="正常速度", disable_speed_limit=False, stop_callback=None):
        """
        通过API获取住建部政策文件，基于时间区间过滤
        Args:
            keywords: 关键词列表，None表示不限制
            callback: 进度回调函数，用于GUI显示进度
            start_date: 起始日期（yyyy-MM-dd）
            end_date: 结束日期（yyyy-MM-dd）
            speed_mode: 速度模式（"快速模式"、"正常速度"、"慢速模式"）
            disable_speed_limit: 是否禁用速度限制
        """
        # 设置速度模式
        self.speed_mode = speed_mode
        
        # 根据速度模式调整防反爬虫设置
        if disable_speed_limit:
            # 禁用速度限制：最快速度，忽略所有延迟
            self.anti_crawler.min_delay = 0.0
            self.anti_crawler.max_delay = 0.0
            self.anti_crawler.max_requests_per_minute = 999999  # 无限制
        elif speed_mode == "快速模式":
            self.anti_crawler.min_delay = 0.1
            self.anti_crawler.max_delay = 0.3
            self.anti_crawler.max_requests_per_minute = 100
        elif speed_mode == "慢速模式":
            self.anti_crawler.min_delay = 2.0
            self.anti_crawler.max_delay = 5.0
            self.anti_crawler.max_requests_per_minute = 10
        else:  # 正常速度
            self.anti_crawler.min_delay = 0.2
            self.anti_crawler.max_delay = 0.8
            self.anti_crawler.max_requests_per_minute = 60
        
        policies = []
        page_size = 30
        page_no = 1
        total_processed = 0
        
        # 时间区间状态跟踪
        dt_start = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        dt_end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
        in_target_range = False  # 是否已进入目标时间区间
        consecutive_out_of_range = 0  # 连续超出范围的页数
        max_consecutive_out_of_range = 5  # 最大连续超出范围页数
        
        while True:
            # 检查是否停止
            if stop_callback and stop_callback():
                print("用户已停止爬取")
                break
                
            print(f"正在检索第 {page_no} 页...")
            if callback:
                callback(f"正在检索第 {page_no} 页...")
            
            try:
                # 检查请求频率限制
                # self.rate_limiter.wait_if_needed() # Removed as per edit hint
                
                import json
                param_json = {
                    "pageNo": page_no,
                    "pageSize": page_size,
                    "loadEnabled": True,
                    "search": "{}"
                }
                params = self.base_params.copy()
                params['paramJson'] = json.dumps(param_json)
                
                # 合并请求头
                headers = self.special_headers.copy()
                headers.update(self.anti_crawler.get_random_headers())
                
                # 使用防反爬虫管理器发送请求
                try:
                    resp = self.anti_crawler.make_request(
                        self.api_url, 
                        method='GET',
                        params=params, 
                        headers=headers
                    )
                    data = resp.json()
                    self.monitor.record_request(self.api_url, success=True)
                except Exception as e:
                    self.monitor.record_request(self.api_url, success=False, error_type=str(e))
                    raise
                html_content = data.get('data', {}).get('html', '')
                if not html_content:
                    print(f"第 {page_no} 页无HTML内容，停止检索")
                    return policies
                
                soup = BeautifulSoup(html_content, 'html.parser')
                table = soup.find('table')
                if not isinstance(table, Tag):
                    print(f"第 {page_no} 页未找到表格，停止检索")
                    return policies
                tbody = table.find('tbody')
                if not isinstance(tbody, Tag):
                    print(f"第 {page_no} 页未找到tbody，停止检索")
                    return policies
                rows = tbody.find_all('tr')
                print(f"第 {page_no} 页找到 {len(rows)} 条政策")
                page_policies = []
                page_dates = []
                
                for row in rows:
                    if not isinstance(row, Tag):
                        continue
                    # 检查是否停止
                    if stop_callback and stop_callback():
                        print("用户已停止爬取")
                        break
                        
                    cells = row.find_all('td') if hasattr(row, 'find_all') else []
                    if len(cells) >= 4:
                        # 将ResultSet转换为列表，避免索引问题
                        cells_list = list(cells)
                        title_cell = cells_list[1] if len(cells_list) > 1 else None
                        title_link = None
                        if isinstance(title_cell, Tag):
                            title_link = title_cell.find('a')
                        if title_link and isinstance(title_link, Tag):
                            title = title_link.get('title', '') or title_link.get_text(strip=True)
                            url = title_link.get('href', '')
                        else:
                            title = ''
                            url = ''
                        doc_number = cells_list[2].get_text(strip=True) if len(cells_list) > 2 and isinstance(cells_list[2], Tag) else ''
                        pub_date = cells_list[3].get_text(strip=True) if len(cells_list) > 3 and isinstance(cells_list[3], Tag) else ''
                        if isinstance(url, str) and not url.startswith('http'):
                            url = 'https://www.mohurd.gov.cn' + url
                            
                            # 解析日期
                            try:
                                dt_pub = datetime.strptime(pub_date, '%Y-%m-%d')
                                page_dates.append(dt_pub)
                            except Exception:
                                continue
                            
                            # 时间区间过滤
                            if dt_start and dt_pub < dt_start:
                                continue
                            if dt_end and dt_pub > dt_end:
                                continue
                            
                            # 关键词过滤
                            if keywords and keywords != [''] and not any(kw in title for kw in keywords):
                                continue
                            
                            print(f"处理政策: {title}")
                            if callback:
                                callback(f"正在处理: {title[:30]}...")
                            
                            # 根据速度设置决定是否添加延迟
                            if not disable_speed_limit:
                                time.sleep(random.uniform(0.5, 2.0))
                            content = self.get_policy_detail(url, stop_callback)
                            policy_data = {
                                'level': '住房和城乡建设部',
                                'title': title,
                                'pub_date': pub_date,
                                'doc_number': doc_number,
                                'source': url,
                                'content': content,
                                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            page_policies.append(policy_data)
                            
                            # 立即发送单条政策数据到界面
                            if callback:
                                callback(f"已获取: {title[:30]}...")
                                # 发送政策数据信号 - 发送完整内容
                                callback(f"POLICY_DATA:{title}|{pub_date}|{url}|{content}")
                
                print(f"第 {page_no} 页：找到 {len(rows)} 条，保留 {len(page_policies)} 条")
                total_processed += len(page_policies)
                policies.extend(page_policies)
                
                # 时间区间状态检查 - 优化版本
                if dt_start and dt_end and page_dates:
                    # 更精确的时间区间判断
                    if not in_target_range:
                        # 检查是否有任何数据在目标时间范围内
                        has_target_data = any(dt_start <= d <= dt_end for d in page_dates)
                        if has_target_data:
                            in_target_range = True
                            consecutive_out_of_range = 0
                            print(f"第 {page_no} 页：进入目标时间区间 [{start_date} - {end_date}]")
                    
                    elif in_target_range:
                        # 检查是否所有数据都在目标范围外
                        all_out_of_range = all(d < dt_start or d > dt_end for d in page_dates)
                        if all_out_of_range:
                            consecutive_out_of_range += 1
                            print(f"第 {page_no} 页：脱离目标时间区间，连续 {consecutive_out_of_range} 页")
                            
                            # 如果连续多页都脱离范围，停止检索
                            if consecutive_out_of_range >= max_consecutive_out_of_range:
                                print(f"连续 {max_consecutive_out_of_range} 页脱离目标时间区间，停止检索")
                                return policies
                        else:
                            consecutive_out_of_range = 0
                
                # 更新进度
                if page_policies:
                    if callback:
                        callback(f"在第 {page_no} 页找到 {len(page_policies)} 条政策")
                else:
                    if callback:
                        callback(f"第 {page_no} 页无匹配政策")
                
                page_no += 1
                
            except Exception as e:
                import traceback
                print(f"检索第 {page_no} 页时出错: {e}")
                print(f"错误详情: {traceback.format_exc()}")
                if callback:
                    callback(f"检索第 {page_no} 页时出错: {e}")
                
                # 根据错误类型决定是否继续
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ['timeout', 'connection', 'network', 'dns']):
                    # 网络相关错误，可以重试
                    print(f"网络错误，尝试继续下一页...")
                    page_no += 1
                    continue
                elif any(keyword in error_str for keyword in ['json', 'parse', 'decode']):
                    # 解析错误，可能是服务器返回了错误页面
                    print(f"解析错误，尝试继续下一页...")
                    page_no += 1
                    continue
                else:
                    # 其他错误，停止爬取
                    print(f"遇到严重错误，停止爬取")
                    break
        
        print(f"爬取完成，共获取 {len(policies)} 条政策")
        if callback:
            callback(f"爬取完成，共获取 {len(policies)} 条政策")
        
        return policies

    def get_crawler_status(self):
        """获取爬虫状态"""
        return {
            'speed_mode': self.speed_mode,
            'monitor_stats': self.monitor.get_stats(),
            # Removed rate_limiter_stats as per edit hint
        }

    def _parse_policy_item(self, item: Dict) -> Optional[Dict]:
        """解析单个政策项（与多线程版本保持一致）"""
        try:
            title = item.get('title', '').strip()
            if not title:
                return None
            
            pub_date = item.get('pub_date', '')
            doc_number = item.get('doc_number', '')
            url = item.get('source', '')
            
            # 获取政策详情内容
            content = self.get_policy_detail(url) if url else ''
            
            return {
                'level': self.level,
                'title': title,
                'pub_date': pub_date,
                'doc_number': doc_number,
                'source': url,
                'content': content,
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            print(f"解析政策项失败: {e}")
            return None

    def get_policy_detail(self, url, stop_callback=None):
        """获取政策详情内容"""
        try:
            # 检查是否停止
            if stop_callback and stop_callback():
                return ""
            
            # 使用防反爬虫管理器发送请求
            headers = self.special_headers.copy()
            headers.update(self.anti_crawler.get_random_headers())
            
            resp = self.anti_crawler.make_request(url, headers=headers)
            
            # 记录成功的详情页面请求
            self.monitor.record_request(url, success=True)
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # 提取正文内容
            content_div = soup.find('div', class_='content')
            if content_div:
                return content_div.get_text(strip=True)
            else:
                return soup.get_text(strip=True)
        except Exception as e:
            # 记录失败的详情页面请求
            self.monitor.record_request(url, success=False, error_type=str(e))
            import traceback
            print(f"获取政策详情失败: {e}")
            print(f"错误详情: {traceback.format_exc()}")
            return ""

    def save_to_db(self, policies):
        """保存政策到数据库"""
        for policy in policies:
            # 检查policy是字典还是其他格式
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
                # 如果是元组格式：(id, level, title, pub_date, source, content)
                db.insert_policy(
                    policy[1],  # level
                    policy[2],  # title
                    policy[3],  # pub_date
                    policy[4],  # source
                    policy[5],  # content
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # crawl_time
                )

# 为兼容性添加别名类
class NationalPolicyCrawler(NationalSpider):
    """国家级政策爬虫类（NationalSpider的别名）"""
    pass

if __name__ == "__main__":
    spider = NationalSpider()
    policies = spider.crawl_policies(['规划', '空间', '用地'])
    spider.save_to_db(policies)
    print(f"爬取到 {len(policies)} 条国家住建部政策") 