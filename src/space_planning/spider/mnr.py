import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import random
import re
import json
from urllib.parse import urljoin, urlencode

# 模块级别的常量，用于动态加载
LEVEL_NAME = "自然资源部"

# 导入监控和防反爬虫模块
from .monitor import CrawlerMonitor
from .anti_crawler import AntiCrawlerManager

class MNRSpider:
    """
    自然资源部 法律法规库 爬虫
    """
    def __init__(self):
        self.base_url = 'https://f.mnr.gov.cn/'
        self.search_api = 'https://search.mnr.gov.cn/was5/web/search'
        self.ajax_api = 'https://search.mnr.gov.cn/was/ajaxdata_jsonp.jsp'
        self.level = '自然资源部'
        self.speed_mode = "正常速度"  # 添加速度模式
        
        # 初始化监控和防反爬虫管理器
        self.monitor = CrawlerMonitor()
        self.anti_crawler = AntiCrawlerManager()
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://f.mnr.gov.cn/',
            'X-Requested-With': 'XMLHttpRequest'
        }
        self.max_pages = 50  # 最大翻页数
        self.channel_id = '174757'  # 法律法规库的频道ID
        
        # 分类配置
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

    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None, 
                      speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, 
                      category=None):
        """
        爬取自然资源部法律法规库
        :param keywords: 关键词列表
        :param callback: 进度回调
        :param start_date: 起始日期 yyyy-MM-dd
        :param end_date: 结束日期 yyyy-MM-dd
        :param category: 分类名称，None表示搜索全部分类
        :return: list[dict]
        """
        if keywords is None:
            keywords = []
        
        dt_start = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        dt_end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
        
        results = []
        
        # 确定要搜索的分类列表
        if category and category in self.categories:
            # 搜索指定分类
            categories_to_search = [category]
            if callback:
                callback(f"开始爬取指定分类: {category}")
        else:
            # 搜索全部分类
            categories_to_search = list(self.categories.keys())
            if callback:
                callback(f"开始爬取全部{len(categories_to_search)}个分类...")
        
        # 用于去重的集合
        seen_titles = set()
        seen_links = set()
        
        # 遍历每个分类进行搜索
        for category_name in categories_to_search:
            if stop_callback and stop_callback():
                break
                
            category_config = self.categories[category_name]
            
            if callback:
                callback(f"正在搜索分类: {category_name}")
            
            # 构建搜索关键词
            search_keywords = []
            if keywords:
                search_keywords.extend(keywords)
            
            search_word = ' '.join(search_keywords) if search_keywords else ''
            
            if callback:
                callback(f"分类[{category_name}]搜索关键词: {search_word}")
            
            # 分页获取数据
            page = 1
            category_results = []
            consecutive_empty_pages = 0  # 连续空页计数
            max_consecutive_empty = 3  # 最大连续空页数
            
            while page <= self.max_pages:
                if stop_callback and stop_callback():
                    break
                    
                if callback:
                    callback(f"分类[{category_name}]正在抓取第{page}页...")
                    
                try:
                    # 构建搜索参数
                    params = {
                        'channelid': self.channel_id,
                        'searchword': search_word,
                        'page': page,
                        'perpage': 20,  # 每页20条
                        'searchtype': 'title',  # 搜索标题
                        'orderby': 'RELEVANCE'  # 按相关性排序
                    }
                    
                    # 添加时间过滤
                    if start_date:
                        params['starttime'] = start_date
                    if end_date:
                        params['endtime'] = end_date
                    
                    # 发送搜索请求
                    try:
                        resp = requests.get(self.search_api, params=params, headers=self.headers, timeout=15)
                        
                        if resp.status_code == 200:
                            self.monitor.record_request(self.search_api, success=True)
                        else:
                            self.monitor.record_request(self.search_api, success=False, error_type=f"HTTP {resp.status_code}")
                            if callback:
                                callback(f"分类[{category_name}]第{page}页搜索失败: {resp.status_code}")
                            break
                    except Exception as e:
                        self.monitor.record_request(self.search_api, success=False, error_type=str(e))
                        if callback:
                            callback(f"分类[{category_name}]第{page}页搜索异常: {str(e)}")
                        break
                    
                    # 解析搜索结果
                    try:
                        search_data = resp.json()
                    except json.JSONDecodeError:
                        # 如果不是JSON，尝试解析HTML
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        page_policies = self._parse_html_results(soup, callback)
                    else:
                        page_policies = self._parse_json_results(search_data, callback)
                    
                    if not page_policies:
                        consecutive_empty_pages += 1
                        if callback:
                            callback(f"分类[{category_name}]第{page}页无数据")
                        
                        if consecutive_empty_pages >= max_consecutive_empty:
                            if callback:
                                callback(f"分类[{category_name}]连续{max_consecutive_empty}页无数据，停止爬取")
                            break
                        page += 1
                        continue
                    else:
                        consecutive_empty_pages = 0  # 重置连续空页计数
                    
                    # 过滤和验证数据
                    filtered_policies = []
                    new_policies_count = 0  # 新增政策计数
                    
                    for policy in page_policies:
                        # 去重检查
                        title = policy.get('title', '')
                        link = policy.get('link', '')
                        
                        # 使用标题和链接的组合作为唯一标识
                        unique_id = f"{title}|{link}"
                        
                        if unique_id in seen_titles:
                            if callback:
                                callback(f"跳过重复政策: {title}")
                            continue
                        
                        # 时间过滤 - 只有当日期解析成功时才进行过滤
                        pub_date_fmt = self._parse_date(policy.get('pub_date', ''))
                        time_filtered = False
                        if pub_date_fmt:
                            if dt_start and pub_date_fmt < dt_start:
                                time_filtered = True
                            if dt_end and pub_date_fmt > dt_end:
                                time_filtered = True
                        # 如果日期解析失败，不进行时间过滤，避免误删数据
                        
                        if time_filtered:
                            continue
                        
                        # 关键词过滤
                        if keywords and not any(kw in title for kw in keywords):
                            continue
                        
                        # 设置分类信息
                        policy['category'] = category_name
                        
                        # 获取详情页内容
                        if link:
                            content = self.get_policy_detail(link)
                            policy['content'] = content
                        
                        # 添加到已见集合
                        seen_titles.add(unique_id)
                        seen_links.add(link)
                        
                        filtered_policies.append(policy)
                        new_policies_count += 1
                        
                        # 发送政策数据信号（包含正文）
                        if callback:
                            callback(f"POLICY_DATA:{policy['title']}|{policy['pub_date']}|{policy['link']}|{policy['content']}|{category_name}")
                    
                    category_results.extend(filtered_policies)
                    
                    if callback:
                        callback(f"分类[{category_name}]第{page}页获取{len(filtered_policies)}条政策（新增{new_policies_count}条）")
                    
                    # 如果连续多页没有新增政策，可能已经到达数据末尾
                    if new_policies_count == 0:
                        consecutive_empty_pages += 1
                        if consecutive_empty_pages >= max_consecutive_empty:
                            if callback:
                                callback(f"分类[{category_name}]连续{max_consecutive_empty}页无新增政策，停止爬取")
                            break
                    else:
                        consecutive_empty_pages = 0
                    
                    # 控制速度
                    if not disable_speed_limit:
                        time.sleep(random.uniform(1, 2))
                    
                    page += 1
                    
                except Exception as e:
                    if callback:
                        callback(f"分类[{category_name}]第{page}页抓取失败: {e}")
                    break
            
            # 将当前分类的结果添加到总结果中
            results.extend(category_results)
            
            if callback:
                callback(f"分类[{category_name}]爬取完成，获取{len(category_results)}条政策")
        
        if callback:
            callback(f"全部爬取完成，共获取{len(results)}条政策")
            
        return results

    def _parse_json_results(self, data, callback):
        """解析JSON格式的搜索结果"""
        policies = []
        
        try:
            # 根据实际返回的JSON结构解析
            if 'results' in data:
                items = data['results']
            elif 'data' in data:
                items = data['data']
            elif isinstance(data, list):
                items = data
            else:
                items = []
            
            for item in items:
                policy = {
                    'level': self.level,
                    'title': item.get('title', ''),
                    'pub_date': item.get('pubdate', item.get('publishdate', '')),
                    'doc_number': item.get('filenum', ''),
                    'source': item.get('url', ''),
                    'content': '',
                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'category': item.get('category', ''),
                    'validity': item.get('status', ''),
                    'effective_date': item.get('effectivedate', ''),
                    'link': item.get('url', '')
                }
                policies.append(policy)
                    
        except Exception as e:
            if callback:
                callback(f"解析JSON结果失败: {e}")
        
        return policies

    def _parse_html_results(self, soup, callback):
        """解析HTML格式的搜索结果"""
        policies = []
        
        try:
            # 查找政策列表 - 使用正确的选择器
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
                            elif '时效状态' in label:
                                status = value
                    
                    # 构建完整链接
                    if detail_url and not detail_url.startswith('http'):
                        detail_url = urljoin(self.base_url, detail_url)
                    
                    policy = {
                        'level': self.level,
                        'title': title,
                        'pub_date': pub_date,
                        'doc_number': doc_number,
                        'source': detail_url,
                        'content': '',
                        'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'category': business_type,
                        'validity': status,
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

    def get_policy_detail(self, url):
        """获取政策详情页正文"""
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            self.monitor.record_request(url, success=True)
            resp.encoding = resp.apparent_encoding
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 尝试多种正文容器
            content_div = soup.find('div', class_='TRS_Editor')
            if not content_div:
                content_div = soup.find('div', class_='content')
            if not content_div:
                content_div = soup.find('div', id='content')
            if not content_div:
                content_div = soup.find('div', class_='article-content')
            if not content_div:
                content_div = soup.find('div', class_='main-content')
            if not content_div:
                content_div = soup.find('div', class_='article')
                
            if content_div:
                return content_div.get_text(strip=True)
            
            # 兜底：返回全页文本
            return soup.get_text(strip=True)
        except Exception as e:
            self.monitor.record_request(url, success=False, error_type=str(e))
            return ''

    def _parse_date(self, date_str):
        """解析日期字符串为datetime对象"""
        if not date_str:
            return None
        for fmt in ('%Y年%m月%d日', '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'):
            try:
                return datetime.strptime(date_str, fmt)
            except Exception:
                continue
        return None

    def get_available_categories(self):
        """获取可用的分类列表"""
        return list(self.categories.keys())

    def test_search_api(self, callback=None):
        """测试搜索API是否可用"""
        if callback:
            callback("测试搜索API...")
        
        try:
            params = {
                'channelid': self.channel_id,
                'searchword': '土地',
                'page': 1,
                'perpage': 5
            }
            
            resp = requests.get(self.search_api, params=params, headers=self.headers, timeout=10)
            
            if callback:
                callback(f"API测试状态码: {resp.status_code}")
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if callback:
                        callback(f"API返回数据类型: {type(data)}")
                        if isinstance(data, dict):
                            callback(f"API返回字段: {list(data.keys())}")
                    return True
                except json.JSONDecodeError:
                    if callback:
                        callback("API返回非JSON格式数据")
                    return True  # HTML格式也可能可用
            else:
                if callback:
                    callback(f"API测试失败: {resp.status_code}")
                return False
                
        except Exception as e:
            if callback:
                callback(f"API测试异常: {e}")
            return False
    
    def get_crawler_status(self):
        """获取爬虫状态"""
        return {
            'speed_mode': self.speed_mode,
            'monitor_stats': self.monitor.get_stats(),
            'rate_limiter_stats': {
                'max_requests': self.anti_crawler.max_requests_per_minute,
                'time_window': 60  # 固定为60秒
            }
        } 