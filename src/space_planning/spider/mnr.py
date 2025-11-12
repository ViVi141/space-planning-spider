from bs4 import BeautifulSoup
from datetime import datetime
import json
from urllib.parse import urljoin

import logging

# 导入监控和防反爬虫模块
from .monitor import CrawlerMonitor
from .anti_crawler import AntiCrawlerManager
from .spider_config import SpiderConfig

# 模块级别的常量，用于动态加载
LEVEL_NAME = "自然资源部"

logger = logging.getLogger(__name__)

class MNRSpider:
    """
    自然资源部 法律法规库 爬虫
    """
    def __init__(self):
        # 从配置获取参数
        config = SpiderConfig.get_mnr_config()
        
        self.base_url = config['base_url']
        self.search_api = config['search_api']
        self.ajax_api = config['ajax_api']
        self.level = config['level']
        self.speed_mode = config['default_speed_mode']
        self.headers = config['headers'].copy()
        self.max_pages = config['max_pages']
        self.channel_id = config['channel_id']
        
        # 初始化监控和防反爬虫管理器
        self.monitor = CrawlerMonitor()
        self.anti_crawler = AntiCrawlerManager()
        self.anti_crawler.configure_speed_mode(self.speed_mode, False)
        self.anti_crawler.session.headers.update(self.headers)
        self._init_proxy()
        
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
            '矿产开发': {'code': '1329', 'name': '矿产开发'},
            '地质环境保护': {'code': '1330', 'name': '地质环境保护'},
            '海洋资源': {'code': '1331', 'name': '海洋资源'},
            '测绘地理信息': {'code': '1332', 'name': '测绘地理信息'},
            '国土空间用途管制': {'code': '1333', 'name': '国土空间用途管制'},  # noqa: F601
            '地质灾害防治': {'code': '1334', 'name': '地质灾害防治'},
            '地质公园': {'code': '1335', 'name': '地质公园'},
            '地质遗迹保护': {'code': '1336', 'name': '地质遗迹保护'},
            '矿业权评估': {'code': '1338', 'name': '矿业权评估'},
            '机构建设': {'code': '1339', 'name': '机构建设'},
            '综合管理': {'code': '1340', 'name': '综合管理'},
            '其他': {'code': '1341', 'name': '其他'}
        }
    
    def _init_proxy(self):
        """初始化代理设置"""
        try:
            self.anti_crawler.refresh_proxy()
            logger.info("MNRSpider: 已刷新代理设置")
        except Exception as e:  # noqa: BLE001
            logger.warning("MNRSpider: 初始化代理失败: %s", e, exc_info=True)
    
    def _update_proxy(self):
        """更新代理（每次请求前调用）"""
        try:
            self.anti_crawler.refresh_proxy()
        except Exception as e:  # noqa: BLE001
            logger.debug("[代理验证] MNRSpider: 更新代理失败: %s，继续使用当前代理或无代理", e)

    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None, 
                      speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, 
                      category=None, policy_callback=None):
        """
        爬取自然资源部法律法规库
        :param keywords: 关键词列表
        :param callback: 进度回调
        :param start_date: 起始日期 yyyy-MM-dd
        :param end_date: 结束日期 yyyy-MM-dd
        :param category: 分类名称，None表示搜索全部分类
        :param policy_callback: 政策数据回调函数，每解析到一条政策时调用
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
        
        # 由于服务器不支持分类搜索，只搜索一次，不分分类遍历
        # 构建搜索关键词
        search_keywords = []
        if keywords:
            search_keywords.extend(keywords)
        
        search_word = ' '.join(search_keywords) if search_keywords else ''
        self.disable_speed_limit = disable_speed_limit
        self.anti_crawler.configure_speed_mode(self.speed_mode, disable_speed_limit)
        
        if callback:
            callback(f"搜索关键词: {search_word or '(无关键词，搜索全部政策)'}")
        
        # 分页获取数据 - 重置所有计数变量
        page = 1
        category_results = []
        
        # 从通用配置获取参数
        common_config = SpiderConfig.get_common_config()
        max_consecutive_empty = common_config['max_empty_pages']  # 最大连续空页数
        max_consecutive_filtered = common_config['max_empty_pages']  # 最大连续过滤页数
        
        consecutive_empty_pages = 0  # 连续空页计数
        new_policies_count = 0  # 新增政策计数
        consecutive_filtered_pages = 0  # 连续过滤页计数（有数据但都被过滤）
        
        while page <= self.max_pages:
            if stop_callback and stop_callback():
                break
                
            if callback:
                callback(f"正在抓取第{page}页...")
            
            try:
                # 构建搜索参数
                # 注意：根据实际情况，可能服务器不支持themecat语法，暂时不使用分类搜索
                if search_word:
                    search_query = search_word
                else:
                    search_query = ""
                    
                params = {
                    'channelid': self.channel_id,
                    'searchword': search_query,
                    'page': page,
                    'perpage': 20,  # 每页20条
                    'searchtype': 'title',  # 搜索标题
                    'orderby': 'RELEVANCE'  # 按相关性排序
                }
                
                # 调试信息：显示搜索参数
                if callback and page == 1:
                    callback(f"搜索参数: {search_query or '(搜索全部)'}")
                
                # 添加时间过滤
                if start_date:
                    params['starttime'] = start_date
                if end_date:
                    params['endtime'] = end_date
                
                # 发送搜索请求
                try:
                    # 更新代理（每次请求前）
                    self._update_proxy()
                    # 使用统一请求管理器发送请求（支持代理与防爬配置）
                    resp = self.anti_crawler.make_request(
                        self.search_api,
                        method='GET',
                        params=params,
                        headers=self.headers.copy(),
                        timeout=15
                    )
                    
                    if resp.status_code == 200:
                        self.monitor.record_request(self.search_api, success=True)
                    else:
                        self.monitor.record_request(self.search_api, success=False, error_type=f"HTTP {resp.status_code}")
                        if callback:
                            callback(f"第{page}页搜索失败: {resp.status_code}")
                        break
                except Exception as e:
                    self.monitor.record_request(self.search_api, success=False, error_type=str(e))
                    if callback:
                        callback(f"第{page}页搜索异常: {str(e)}")
                    break
                
                # 解析搜索结果
                try:
                    search_data = resp.json()
                except json.JSONDecodeError:
                    # 如果不是JSON，尝试解析HTML
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    page_policies = self._parse_html_results(soup, callback, '全部')
                else:
                    page_policies = self._parse_json_results(search_data, callback)
                    
                if not page_policies:
                    consecutive_empty_pages += 1
                    if callback:
                        callback(f"第{page}页无数据")
                    
                    if consecutive_empty_pages >= max_consecutive_empty:
                        if callback:
                            callback(f"连续{max_consecutive_empty}页无数据，停止爬取")
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
                    
                    # 保存原始分类信息（如果存在），用于检测分类不匹配
                    original_category = policy.get('category', '')
                    
                    # 设置分类信息（使用原标题的原始分类）
                    policy['category'] = original_category if original_category else '未分类'
                    policy['original_category'] = original_category  # 保存原始分类用于调试
                    
                    # 获取详情页内容
                    if link:
                        content = self.get_policy_detail(link)
                        policy['content'] = content
                    else:
                        # 确保 content 字段存在
                        policy['content'] = policy.get('content', '')
                    
                    # 添加到已见集合
                    seen_titles.add(unique_id)
                    seen_links.add(link)
                    
                    filtered_policies.append(policy)
                    new_policies_count += 1
                    self.anti_crawler.register_policy_success()
                    
                    # 调用 policy_callback 实时返回政策数据（确保 content 已填充）
                    if policy_callback:
                        try:
                            policy_callback(policy)
                        except Exception as cb_error:
                            logger.warning(f"调用 policy_callback 失败: {cb_error}")
                    
                    # 发送政策数据信号（包含正文）
                    if callback:
                        callback(f"POLICY_DATA:{policy['title']}|{policy['pub_date']}|{policy['link']}|{policy['content']}|{policy['category']}")
                    
                category_results.extend(filtered_policies)
                
                if callback:
                    callback(f"第{page}页获取{len(filtered_policies)}条政策（新增{new_policies_count}条）")
                
                # 如果连续多页没有新增政策，可能已经到达数据末尾
                # 注意：这里不应该重复计数consecutive_empty_pages
                # 因为上面已经处理了空页情况
                if new_policies_count == 0 and len(page_policies) > 0:
                    # 这种情况表示所有数据都被过滤掉了，但不是真正的空页
                    # 可能是分类不匹配、时间过滤、关键词过滤等原因
                    consecutive_filtered_pages += 1
                    
                    if consecutive_filtered_pages >= max_consecutive_filtered:
                        # 连续多页所有数据都被过滤，很可能是分类不匹配或搜索参数有问题
                        # 避免无限翻页的假象
                        if callback:
                            callback(f"连续{consecutive_filtered_pages}页所有数据被过滤（找到数据但全部被过滤），已无相关数据，停止爬取")
                        break
                    else:
                        # 还可以继续尝试
                        if callback:
                            callback(f"第{page}页所有数据被过滤（连续{consecutive_filtered_pages}页），继续下一页")
                elif new_policies_count > 0:
                    # 有新增数据，重置过滤页计数
                    consecutive_filtered_pages = 0
                # new_policies_count == 0 and len(page_policies) == 0 的情况已经在上面处理过了
                # 其他情况下如果page_policies不为空，说明有数据，重置空页计数（虽然不会到这里）
                
                # 控制速度
                self.anti_crawler.sleep_between_requests(disable_speed_limit)
                
                page += 1
                
            except Exception as e:
                if callback:
                    callback(f"第{page}页抓取失败: {e}")
                break
        
        # 将结果添加到总结果中
        results.extend(category_results)
        
        if callback:
            callback(f"爬取完成，获取{len(category_results)}条政策")
        
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
                # 尝试获取内容（如果API返回）
                content = item.get('content', '').strip()
                # 如果API没有返回内容，尝试从其他字段获取
                if not content:
                    content = item.get('summary', '').strip() or item.get('abstract', '').strip()
                
                # 解析并格式化日期
                raw_date = item.get('pubdate', item.get('publishdate', ''))
                pub_date = ''
                if raw_date:
                    parsed_date = self._parse_date(raw_date)
                    if parsed_date:
                        pub_date = parsed_date.strftime('%Y-%m-%d')
                    else:
                        # 如果解析失败，尝试直接使用原始值（可能已经是标准格式）
                        pub_date = raw_date.strip()
                
                policy = {
                    'level': self.level,
                    'title': item.get('title', '') or '',
                    'pub_date': pub_date or '',  # 统一为 YYYY-MM-DD 格式
                    'doc_number': item.get('filenum', '') or '',
                    'source': item.get('url', '') or '',  # 主要字段：source
                    'url': item.get('url', '') or '',  # 兼容字段
                    'link': item.get('url', '') or '',  # 兼容字段
                    'content': content or '',  # 确保content字段存在
                    'category': item.get('category', '') or '',  # 确保category字段存在
                    'validity': item.get('status', '') or '',
                    'effective_date': item.get('effectivedate', '') or '',
                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                policies.append(policy)
                self.anti_crawler.register_policy_success()
                    
        except Exception as e:
            if callback:
                callback(f"解析JSON结果失败: {e}")
        
        return policies

    def _parse_html_results(self, soup, callback, category_name=''):
        """解析HTML格式的搜索结果"""
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
                    
                    # 尝试从详细信息中获取更多数据
                    detail_info = title_cell.find('div', class_='box')
                    if detail_info:
                        # 提取发文字号
                        doc_number_cells = detail_info.find_all('td')
                        for i, cell in enumerate(doc_number_cells):
                            if '发文字号' in cell.get_text():
                                if i + 1 < len(doc_number_cells):
                                    doc_number = doc_number_cells[i + 1].get_text(strip=True)
                                break
                    
                    # 解析并格式化日期
                    pub_date_formatted = ''
                    if pub_date:
                        parsed_date = self._parse_date(pub_date)
                        if parsed_date:
                            pub_date_formatted = parsed_date.strftime('%Y-%m-%d')
                        else:
                            # 如果解析失败，尝试直接使用原始值（可能已经是标准格式）
                            pub_date_formatted = pub_date.strip()
                    
                    policy = {
                        'level': self.level,
                        'title': title,
                        'pub_date': pub_date_formatted,  # 统一为 YYYY-MM-DD 格式
                        'doc_number': doc_number,
                        'source': detail_url,
                        'content': '',  # 初始为空，会在crawl_policies中填充
                        'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'category': category_name,
                        'validity': '',
                        'effective_date': '',
                        'link': detail_url
                    }
                    
                    policies.append(policy)
                    self.anti_crawler.register_policy_success()
                        
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
            # 更新代理
            self._update_proxy()
            # 使用会话发送请求（支持代理）
            resp = self.anti_crawler.make_request(url, headers=self.headers.copy(), timeout=15)
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
            
            # 更新代理
            self._update_proxy()
            # 使用会话发送请求（支持代理）
            resp = self.anti_crawler.make_request(
                self.search_api,
                method='GET',
                params=params,
                headers=self.headers.copy(),
                timeout=10
            )
            
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