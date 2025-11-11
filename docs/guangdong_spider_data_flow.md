# 广东省爬虫数据流说明

## 总体架构
广东省站点的抓取主要由 `GuangdongSpider` 提供基础单线程逻辑，`GuangdongMultiThreadSpider` 在并发场景下重用其能力，`GuangdongPolicyCrawler` 作为兼容包装统一对外接口。

```50:78:src/space_planning/spider/guangdong.py
class GuangdongSpider(EnhancedBaseCrawler):
    """广东省政策爬虫 - 使用真实API接口"""
    
    def __init__(self):
        super().__init__("广东省政策爬虫", enable_proxy=True)
        config = SpiderConfig.get_guangdong_config()
        
        self.base_url = config['base_url']
        self.search_url = config['search_url']
        self.level = config['level']
        self.headers = config['headers'].copy()
        self.speed_mode = config['default_speed_mode']
        self.category_config = config['category_config'].copy()
        
        self.monitor = CrawlerMonitor()
        self._init_session()
        self.seen_policy_ids = set()
        self.seen_policy_hashes = set()
        self.current_api_config = None
```

```3493:3579:src/space_planning/spider/guangdong.py
class GuangdongMultiThreadSpider(MultiThreadBaseCrawler):
    """广东省多线程爬虫"""
    
    def __init__(self, max_workers=4):
        super().__init__(max_workers, enable_proxy=True)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.level = "广东省人民政府"
        ...
    
    def _execute_task(self, task_data: Dict, session, lock, callback: Optional[Callable] = None) -> List[Dict]:
        """执行具体任务 - 使用成功的搜索策略"""
        ...
        temp_spider = GuangdongSpider()
        temp_spider.headers = self.headers
        temp_spider.enable_proxy = self.enable_proxy
        ...
```

```3669:3687:src/space_planning/spider/guangdong.py
class GuangdongPolicyCrawler(GuangdongSpider):
    """广东省政策爬虫 - 兼容性包装类"""
    
    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None, 
                      speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, policy_callback=None):
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
```

## 初始化阶段
1. 通过配置中心加载基础 URL、请求头、分类映射等运行参数，并为抓取器注册单例监控对象。
2. `_init_session` 创建持久 `requests.Session`，补齐站点要求的指纹、伪造 Cookie，必要时接入共享代理池并在首次请求后记录监控。
3. 初始化阶段就会访问首页以刷新 Cookie，同时借助 `CrawlerMonitor` 记录请求成功或失败信息。

```80:186:src/space_planning/spider/guangdong.py
    def _init_session(self):
        """初始化会话"""
        self.session = requests.Session()
        self.headers.update({
            'Origin': 'https://gd.pkulaw.com',
            'Referer': 'https://gd.pkulaw.com/china/adv',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        })
        self.session.headers.update(self.headers)
        self.session.cookies.set('JSESSIONID', '1234567890ABCDEF', domain='gd.pkulaw.com')
        if self.enable_proxy:
            ...
        resp = self.session.get(self.base_url, timeout=10)
        if resp.status_code == 200:
            self.monitor.record_request(self.base_url, success=True)
            ...
```

## 分类与 API 配置
系统维护两层映射：一层是业务分类树，另一层是分类代码到实际 API 入口的映射。抓取前会根据分类决定菜单、库名、Referer 等参数。

```42:48:src/space_planning/spider/guangdong.py
CATEGORY_API_MAP = {
    'XM07': 'dfxfg',
    'XU13': 'sfjs',
    'XO08': 'dfzfgz',
    'XP08': 'fljs'
}
```

```874:905:src/space_planning/spider/guangdong.py
    def _get_all_categories(self):
        """获取所有分类信息 - 基于网站层级结构分析结果"""
        categories = [
            ("地方性法规", "XM07", [
                ("省级地方性法规", "XM0701"),
                ("设区的市地方性法规", "XM0702"), 
                ("经济特区法规", "XM0703"),
                ("自治条例和单行条例", "XU13"),
            ]),
            ("地方政府规章", "XO08", [
                ("省级地方政府规章", "XO0802"),
                ("设区的市地方政府规章", "XO0803"),
            ]),
            ("规范性文件", "XP08", [
                ("地方规范性文件", "XP08"),
            ]),
        ]
        return categories
```

```2739:2768:src/space_planning/spider/guangdong.py
    def _get_category_api_config(self, category_code: str) -> Dict[str, str]:
        api_type = None
        for code_prefix, api_name in CATEGORY_API_MAP.items():
            if category_code and category_code.startswith(code_prefix):
                api_type = api_name
                break
        if not api_type:
            api_type = 'dfzfgz'
            logger.warning(f"未找到分类代码 {category_code} 的API映射，使用默认接口: {api_type}")
        api_config = API_PATH_MAP[api_type].copy()
        api_config.update({
            'search_url': f"{self.base_url}/{api_type}/search/RecordSearch",
            'init_page': f"{self.base_url}/{api_type}/adv",
            'referer': f'https://gd.pkulaw.com/{api_type}/adv'
        })
        return api_config
```

## 列表采集流程
1. `crawl_policies_optimized` 作为主流程入口；在入参中解析关键词、时间范围、速度模式并初始化分类循环。
2. 每个分类先访问高级搜索页提取可用年份，再逐年调用 `_crawl_category_year` 实现分页 POST 请求。
3. `_get_search_parameters` 按分类调整表单字段，确保菜单、库、ClassCodeKey、页码等满足站点要求。
4. `post_page` 来自 `EnhancedBaseCrawler`，统一处理重试、代理与监控。

```3084:3206:src/space_planning/spider/guangdong.py
    def crawl_policies_optimized(self, keywords=None, callback=None, start_date=None, end_date=None, 
                               speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, policy_callback=None):
        logger.info(f"开始优化爬取广东省政策，关键词: {keywords}, 时间范围: {start_date} 至 {end_date}, policy_callback={'已设置' if policy_callback else '未设置'}")
        ...
        categories = self._get_flat_categories()
        ...
        for category_name, category_code in categories:
            if stop_callback and stop_callback():
                break
            api_config = self._get_category_api_config(category_code)
            self.current_api_config = api_config
            category_policies = self._crawl_category_with_year_split(
                category_name, category_code, callback, stop_callback, policy_callback
            )
            ...
```

```2864:2940:src/space_planning/spider/guangdong.py
    def _crawl_category_with_year_split(self, category_name: str, category_code: str, callback=None, stop_callback=None, policy_callback=None):
        api_config = self._get_category_api_config(category_code)
        years_info = []
        resp = self.session.get(adv_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            years_info = self.extract_years_from_page(resp.text)
        ...
        for year, expected_count in years_info:
            year_policies = self._crawl_category_year(category_name, category_code, year, expected_count, callback, stop_callback, policy_callback)
            ...
```

```2941:3026:src/space_planning/spider/guangdong.py
    def _crawl_category_year(self, category_name: str, category_code: str, year: Optional[int], expected_count: Optional[int],
                           callback=None, stop_callback=None, policy_callback=None):
        while page_index <= max_pages and empty_page_count < max_empty_pages:
            post_data = self._get_search_parameters(
                keywords=None,
                category_code=category_code,
                page_index=page_index,
                page_size=20,
                filter_year=year
            )
            resp, request_info = self.post_page(
                self.search_url,
                data=post_data,
                headers=headers
            )
            if resp and resp.status_code == 200:
                page_policies = self._parse_policy_list_html(resp.text, callback, stop_callback, category_name, policy_callback)
                ...
```

```907:993:src/space_planning/spider/guangdong.py
    def _get_search_parameters(self, keywords=None, category_code=None, page_index=1, page_size=20, start_date=None, end_date=None, old_page_index=None, filter_year=None, api_config=None):
        if api_config is None:
            if category_code:
                api_config = self._get_category_api_config(category_code)
                self.current_api_config = api_config
            else:
                api_config = API_PATH_MAP['china'].copy()
                ...
        if api_config.get('menu') == 'fljs' and page_size == 20:
            page_size = 100
        search_params = {
            'Menu': api_config['menu'],
            'Keywords': keywords[0] if keywords and len(keywords) > 0 else '',
            ...
            'ClassFlag': api_config['class_flag'],
            'ClassCodeKey': (
                f',,,{category_code},,,{filter_year}' if filter_year and category_code
                else f',,,{filter_year}' if filter_year
                else f',,,{category_code},,,' if category_code
                else ',,,,,,'
            ),
            'Pager.PageIndex': str(page_index),
            'Pager.PageSize': str(page_size),
            ...
        }
```

## 列表解析与详情补全
1. `_parse_policy_list_html` 同时支持复选框 ID 抽取与多种结构选择器解析，所有候选项统一转化为政策字典。
2. 解析完成后批量进入详情填充阶段，`get_policy_detail` 按 URL 自动调整 Referer，并尝试多种容器提取正文与真实标题。
3. 详情抓取成功后，通过 `policy_callback` 将完整记录流式发往 GUI。

```469:718:src/space_planning/spider/guangdong.py
    def _parse_policy_list_html(self, html_content, callback=None, stop_callback=None, category_name=None, policy_callback=None):
        soup = BeautifulSoup(html_content, 'html.parser')
        checkboxes = soup.select('input.checkbox[name="recordList"]')
        ...
        for item in all_policy_items:
            if hasattr(item, 'from_checkbox') and item.from_checkbox:
                policy_data = item.policy_data
            else:
                policy_data = self._extract_policy_from_item(item, category_name)
            if policy_data:
                policies.append(policy_data)
        policies_needing_detail = [p for p in policies if p.get('_need_detail_fetch')]
        if policies_needing_detail:
            for policy in policies_needing_detail:
                content = self.get_policy_detail(url)
                ...
                policy['content'] = content
            if policy_callback:
                for policy in policies:
                    policy_callback(policy)
                    time.sleep(0.005)
```

```1936:2015:src/space_planning/spider/guangdong.py
    def get_policy_detail(self, url):
        headers = self.headers.copy()
        if '/gddigui/' in url:
            headers['Referer'] = 'https://gd.pkulaw.com/dfzfgz/adv'
        elif '/gddifang/' in url:
            headers['Referer'] = 'https://gd.pkulaw.com/dfxfg/adv'
        ...
        resp, request_info = self.get_page(url, headers=headers)
        if not resp:
            self.monitor.record_request(url, success=False, error_type="请求失败")
            return ""
        self.monitor.record_request(url, success=True)
        soup = BeautifulSoup(resp.content, 'html.parser')
        content_selectors = [
            'div.content',
            'div.article-content', 
            'div.text',
            ...
        ]
        ...
        if not content or len(content) < 100:
            for div in soup.find_all('div'):
                ...
            ...
        return content
```

## 数据过滤、去重与统计
1. 列表阶段会基于标题、文号、发布日期生成 MD5，防止重复政策进入后续环节。
2. `crawl_policies_optimized` 在分类汇总后执行关键词与时间过滤，并记录爬取、过滤、保存数量。
3. `_deduplicate_policies` 进一步对综合结果做唯一性校验。

```995:1056:src/space_planning/spider/guangdong.py
    def _generate_policy_hash(self, policy):
        if isinstance(policy, dict):
            title = policy.get('title', '')
            doc_number = policy.get('doc_number', '')
            pub_date = policy.get('pub_date', '')
            content = policy.get('content', '')
            hash_string = f"{title}|{doc_number}|{pub_date}|{content}"
        ...
    def _deduplicate_policies(self, policies):
        ...
        for policy in policies:
            if isinstance(policy, dict) and 'title' in policy:
                title = policy['title'].strip()
                policy_hash = self._generate_policy_hash(policy)
                if title and title not in seen_titles and policy_hash not in seen_hashes:
                    ...
```

```3161:3243:src/space_planning/spider/guangdong.py
            total_crawled += len(category_policies)
            filtered_policies = []
            for policy in category_policies:
                if keywords and not self._is_policy_match_keywords(policy, keywords):
                    continue
                if enable_time_filter:
                    if self._is_policy_in_date_range(policy, dt_start, dt_end):
                        filtered_policies.append(policy)
                        if policy_callback:
                            policy_callback(policy)
                        if callback:
                            callback(f"POLICY_DATA:{policy.get('title', '')}|{policy.get('pub_date', '')}|{policy.get('source', '')}|{policy.get('content', '')}")
                else:
                    filtered_policies.append(policy)
                    ...
```

## 输出与持久化
1. 前端通过 `policy_callback` 或 `callback` 接收实时数据，支持进度提示与数据流式展示。
2. `save_to_db` 使用核心数据库模块落库，保持层级、标题、发布日期、来源、正文与分类。

```2074:2096:src/space_planning/spider/guangdong.py
    def save_to_db(self, policies):
        for policy in policies:
            if isinstance(policy, dict):
                db.insert_policy(
                    policy['level'],
                    policy['title'],
                    policy['pub_date'],
                    policy['source'],
                    policy['content'],
                    policy['crawl_time'],
                    policy.get('category')
                )
            elif isinstance(policy, (list, tuple)) and len(policy) >= 6:
                db.insert_policy(
                    policy[1],
                    policy[2],
                    policy[3],
                    policy[4],
                    policy[5],
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    policy[6] if len(policy) > 6 else None
                )
```

## 监控、限速与代理
- 所有请求通过 `CrawlerMonitor` 记录成功率与异常类型，便于 GUI 状态面板使用。
- 速度模式与延时控制在 `crawl_policies_optimized` 内设置随机区间，兼顾反爬策略。
- 代理在 `_init_session`、多线程 `_execute_task` 中通过共享池复用，并提供 `ProxyVerifier` 校验。

```202:2060:src/space_planning/spider/guangdong.py
    def get_crawler_status(self):
        base_stats = self.get_crawling_stats()
        base_stats.update({
            'level': getattr(self, 'level', '广东省人民政府'),
            'speed_mode': getattr(self, 'speed_mode', '正常速度'),
            'monitor_stats': self.monitor.get_stats() if hasattr(self, 'monitor') and self.monitor else {},
            'proxy_enabled': getattr(self, 'enable_proxy', False),
        })
        ...
```

## 多线程扩展
`GuangdongMultiThreadSpider` 通过 `_prepare_tasks` 构造任务队列，`_execute_task` 在每个线程内实例化临时 `GuangdongSpider` 复用单线程逻辑，完成后统计到统一监控数据。该模式适合高并发需求，但仍依赖原有解析与详情填充流程，确保数据一致性。

## 数据流顺序总结
1. GUI/调度层实例化 `GuangdongPolicyCrawler` 并传入关键词、时间范围。
2. 抓取器加载配置、建立会话与代理 → 访问首页握手。
3. 遍历分类：提取年份 → 逐年构造表单 → `post_page` 获取列表 HTML。
4. 列表页面解析出 ID 与基础字段 → 批量抓取详情 → 修正标题、正文。
5. 按关键词、时间、去重规则过滤 → 通过回调流式输出。
6. 必要时调用 `save_to_db` 持久化 → 监控模块持续记录过程指标。

上述流程确保了广东省政策数据从页面到本地数据库的完整传输路径，同时为 GUI 提供实时反馈与后续分析所需的元数据。

