#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
广东省政策爬虫
"""

import hashlib
import logging
import random
import re
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests

from .enhanced_base_crawler import EnhancedBaseCrawler
from .multithread_base_crawler import MultiThreadBaseCrawler
from .monitor import CrawlerMonitor
from .spider_config import SpiderConfig
from .config import crawler_config
from .smart_request_manager import smart_request_manager
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
}

# 分类代码到API映射
CATEGORY_API_MAP = {
    'XM07': 'dfxfg',
    'XM0701': 'dfxfg',
    'XU13': 'sfjs',
    'XO08': 'dfzfgz',
    'XP08': 'fljs'
}

# 支持双请求链路的菜单
DUAL_REQUEST_MENUS = {'dfxfg', 'dfzfgz', 'fljs', 'sfjs'}

MAX_RECORDS_PER_BATCH = 10000  # 单次筛选的最大记录数（20条/页 * 500页）

class GuangdongSpider(EnhancedBaseCrawler):
    """广东省政策爬虫 - 使用真实API接口"""
    
    def _load_runtime_settings(self) -> None:
        """从全局配置加载防反爬相关设置"""
        cfg = crawler_config
        
        # 请求延迟配置
        min_delay_cfg = cfg.get_config('request_delay.min')
        max_delay_cfg = cfg.get_config('request_delay.max')
        try:
            self.min_delay = float(min_delay_cfg) if min_delay_cfg is not None else 1.0
        except (TypeError, ValueError):
            self.min_delay = 1.0
        try:
            self.max_delay = float(max_delay_cfg) if max_delay_cfg is not None else 3.0
        except (TypeError, ValueError):
            self.max_delay = 3.0
        if self.min_delay < 0:
            self.min_delay = 0.0
        if self.max_delay < self.min_delay:
            self.max_delay = self.min_delay
        
        # 会话配置
        session_cfg = cfg.get_config('session_settings') or {}
        self.enable_session_rotation = bool(session_cfg.get('enable_rotation', True))
        self.enable_cookie_management = bool(session_cfg.get('enable_cookie_management', True))
        try:
            self.session_rotation_interval = int(session_cfg.get('rotation_interval', 300) or 0)
        except (TypeError, ValueError):
            self.session_rotation_interval = 300
        try:
            self.max_requests_per_session = int(session_cfg.get('max_requests_per_session', 50) or 0)
        except (TypeError, ValueError):
            self.max_requests_per_session = 50
        
        # 请求头配置
        header_cfg = cfg.get_config('headers_settings') or {}
        self.randomize_user_agent = bool(header_cfg.get('randomize_user_agent', True))
        self.add_referer_header = bool(header_cfg.get('add_referer', True))
        self.add_fingerprint_header = bool(header_cfg.get('add_fingerprint', False))
        
        # 行为模拟配置
        behavior_cfg = cfg.get_config('behavior_settings') or {}
        self.simulate_human_behavior = bool(behavior_cfg.get('simulate_human_behavior', True))
        self.random_delay_enabled = bool(behavior_cfg.get('random_delay', True))
        intensity = behavior_cfg.get('intensity', 5)
        try:
            intensity = int(intensity)
        except (TypeError, ValueError):
            intensity = 5
        self.behavior_intensity = max(1, min(intensity, 10))
        
        # 频率限制配置
        rate_cfg = cfg.get_config('rate_limit_settings') or {}
        self.rate_limit_enabled = bool(rate_cfg.get('enabled', False))
        rpm_cfg = rate_cfg.get('max_requests_per_minute', 60)
        try:
            rpm = int(rpm_cfg)
        except (TypeError, ValueError):
            rpm = 60
        self.requests_per_minute = max(1, rpm)
        proxy_cfg = cfg.get_config('proxy_settings') or {}
        try:
            self.rotate_after_success_count = max(0, int(proxy_cfg.get('rotate_after_success_count', 0) or 0))
        except (TypeError, ValueError):
            self.rotate_after_success_count = 0
        if self.rotate_after_success_count == 0:
            self._policy_success_counter = 0
        
        # 会话状态
        self._session_started_at = time.time()
        self._requests_since_rotation = 0
        self._request_timestamps = deque()
        
        # 针对广东站点调慢节奏
        self.min_delay = max(self.min_delay, 3.0)
        self.max_delay = max(self.max_delay, 7.0)
        if self.requests_per_minute > 20:
            self.requests_per_minute = 20
        self.rate_limit_enabled = True
    
    def _reset_session_counters(self) -> None:
        """重置会话计数"""
        self._session_started_at = time.time()
        self._requests_since_rotation = 0
        self._policy_success_counter = 0

    def _capture_blocked_snapshot(self, url: str, html: str) -> Optional[str]:
        """保存被限制页面的快照，便于后续分析"""
        try:
            snapshot_dir = Path(__file__).resolve().parent / "blocked_snapshots"
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            parsed = urlparse(url)
            slug_parts = [parsed.netloc or "", parsed.path.replace("/", "_")]
            slug = "_".join(filter(None, slug_parts)).strip("_")
            if not slug:
                slug = "detail"
            slug = re.sub(r"[^0-9A-Za-z_\-]+", "_", slug)[:80]

            file_path = snapshot_dir / f"{timestamp}_{slug}.html"
            file_path.write_text(html, encoding="utf-8")

            meta_path = file_path.with_suffix(".meta.txt")
            meta_path.write_text(
                f"URL: {url}\nCapturedAt: {datetime.now().isoformat()}\n",
                encoding="utf-8"
            )
            return str(file_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("保存限制页面快照失败: %s", exc, exc_info=True)
            return None
    
    def _apply_dynamic_headers(self) -> None:
        """根据配置动态更新会话请求头"""
        base_headers = self.headers.copy()
        base_headers.setdefault('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8')
        base_headers.setdefault('Accept-Encoding', 'gzip, deflate, br, zstd')
        base_headers.setdefault('Cache-Control', 'max-age=0')
        base_headers.setdefault('Upgrade-Insecure-Requests', '1')
        base_headers.setdefault('Sec-Fetch-Site', 'same-origin')
        base_headers.setdefault('Sec-Fetch-Mode', 'navigate')
        base_headers.setdefault('Sec-Fetch-Dest', 'document')
        base_headers.setdefault('sec-ch-ua', '"Not/A)Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"')
        base_headers.setdefault('sec-ch-ua-mobile', '?0')
        base_headers.setdefault('sec-ch-ua-platform', '"Windows"')
        
        random_headers = None
        if self.randomize_user_agent or self.add_fingerprint_header:
            try:
                random_headers = smart_request_manager.anti_detection.get_random_headers(
                    referer=f"{self.base_url}/china/adv"
                )
            except Exception:
                random_headers = None
        
        if self.randomize_user_agent and random_headers:
            base_headers['User-Agent'] = random_headers.get('User-Agent', base_headers.get('User-Agent'))
        if self.add_referer_header:
            base_headers.setdefault('Referer', f"{self.base_url}/china/adv")
        if self.add_fingerprint_header and random_headers:
            fingerprint_header = random_headers.get('X-Client-Data')
            if fingerprint_header:
                base_headers['X-Client-Data'] = fingerprint_header
        
        self.headers = base_headers.copy()
        self.session.headers.clear()
        self.session.headers.update(base_headers)
    
    def _preheat_session(
        self,
        session: Optional[requests.Session] = None,
        api_config: Optional[Dict[str, str]] = None,
    ) -> bool:
        """访问入口页，获取必要的 Cookie 和动态参数"""
        target_session = session or self.session
        if target_session is None:
            return False
    
        api_config = api_config or self.current_api_config or {}
        adv_url = api_config.get('init_page', f"{self.base_url}/dfxfg/adv")
        referer = api_config.get('referer', adv_url)
    
        headers = target_session.headers.copy()
        headers.setdefault('Referer', referer)
        headers.setdefault('Cache-Control', 'no-cache')
    
        try:
            resp = target_session.get(
                adv_url,
                headers=headers,
                timeout=20,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                logger.debug("预热入口页成功: %s", adv_url)
                self._access_limit_strikes = 0
                return True
            logger.warning("预热入口页失败 [%s]: HTTP %s", adv_url, resp.status_code)
        except requests.RequestException as exc:
            logger.warning("预热入口页异常 [%s]: %s", adv_url, exc, exc_info=True)
        return False
    
    def _prepare_request_headers(self, headers: Optional[Dict] = None) -> Dict:
        """合并基础请求头与动态头信息"""
        combined = self.session.headers.copy()
        
        additional_random_headers = None
        if self.randomize_user_agent or self.add_fingerprint_header:
            try:
                additional_random_headers = smart_request_manager.anti_detection.get_random_headers(
                    referer=f"{self.base_url}/china/adv"
                )
            except Exception:
                additional_random_headers = None
        
        if self.randomize_user_agent and additional_random_headers:
            combined['User-Agent'] = additional_random_headers.get('User-Agent', combined.get('User-Agent'))
        if self.add_referer_header:
            combined.setdefault('Referer', f"{self.base_url}/china/adv")
        if self.add_fingerprint_header and additional_random_headers:
            fingerprint_header = additional_random_headers.get('X-Client-Data')
            if fingerprint_header:
                combined['X-Client-Data'] = fingerprint_header
        
        if headers:
            combined.update(headers)
        return combined
    
    def _maybe_rotate_session(self, force: bool = False) -> bool:
        """根据配置判断是否需要轮换会话"""
        if not self.enable_session_rotation:
            return False
        
        now = time.time()
        need_rotate = force
        if self.session_rotation_interval and now - self._session_started_at >= self.session_rotation_interval:
            need_rotate = True
        if (self.max_requests_per_session and
                self._requests_since_rotation >= self.max_requests_per_session):
            need_rotate = True
        
        if not need_rotate:
            return False
        
        rotated = self._rotate_session()
        if rotated:
            self._reset_session_counters()
            self._apply_dynamic_headers()
        return rotated
    
    def _apply_rate_limit(self) -> None:
        """按照配置限制请求频率"""
        if not self.rate_limit_enabled or self.requests_per_minute <= 0:
            return
        
        now = time.time()
        window = 60.0
        while self._request_timestamps and now - self._request_timestamps[0] > window:
            self._request_timestamps.popleft()
        
        if len(self._request_timestamps) >= self.requests_per_minute:
            earliest = self._request_timestamps[0]
            sleep_time = window - (now - earliest) + 0.01
            if sleep_time > 0:
                time.sleep(min(sleep_time, self.max_delay))
        
        self._request_timestamps.append(time.time())
    
    def _get_delay_range_for_speed(self, speed_mode: Optional[str] = None) -> Tuple[float, float]:
        """根据速度模式返回延迟区间"""
        mode = speed_mode or self.speed_mode or "正常速度"
        base_min = self.min_delay
        base_max = self.max_delay
        if mode == "快速模式":
            factor = 0.5
        elif mode == "慢速模式":
            factor = 2.0
        else:
            factor = 1.0
        delay_min = max(0.0, base_min * factor)
        delay_max = max(delay_min, base_max * factor)
        return delay_min, delay_max
    
    def _sleep_between_requests(self, speed_mode: Optional[str] = None, disable_speed_limit: bool = False) -> None:
        """根据配置在请求之间延迟"""
        if disable_speed_limit:
            return
        if not self.random_delay_enabled:
            time.sleep(self.min_delay)
            return
        
        delay_min, delay_max = self._get_delay_range_for_speed(speed_mode)
        delay = random.uniform(delay_min, delay_max)
        # 根据行为强度稍微波动
        jitter = random.uniform(-0.1, 0.1) * (self.behavior_intensity / 10)
        delay *= (1 + jitter)
        if delay < 0:
            delay = 0
        time.sleep(delay)
    
    def _session_request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict] = None,
        data: Optional[Dict] = None,
        timeout: int = 15
    ) -> Tuple[Optional[requests.Response], Dict]:
        """使用会话对象发送请求，并应用所有防反爬策略"""
        request_info = {
            'url': url,
            'method': method,
            'headers': headers or {},
            'timeout': timeout
        }
        
        self._apply_rate_limit()
        self._maybe_rotate_session()
        self._sleep_between_requests(self.speed_mode)
        
        prepared_headers = self._prepare_request_headers(headers)
        start_time = time.time()
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=prepared_headers,
                data=data,
                timeout=timeout
            )
            elapsed = time.time() - start_time
            request_info['response_time'] = elapsed
            request_info['status_code'] = response.status_code
            request_info['access_blocked'] = False
            self._requests_since_rotation += 1
            
            response_text = ""
            content_type = response.headers.get("Content-Type", "") if response else ""
            if "text" in content_type or "json" in content_type:
                try:
                    response_text = response.text
                except Exception:  # noqa: BLE001
                    response_text = ""

            if response_text:
                if self._handle_access_limit(response_text):
                    request_info['access_blocked'] = True

            if self.monitor:
                success = 200 <= response.status_code < 400
                error_type = None if success else f"HTTP {response.status_code}"
                self.monitor.record_request(url, success=success, error_type=error_type)
            
            return response, request_info
        except requests.RequestException as exc:
            elapsed = time.time() - start_time
            request_info['error'] = str(exc)
            request_info['response_time'] = elapsed
            self._requests_since_rotation += 1
            if self.monitor:
                self.monitor.record_request(url, success=False, error_type=type(exc).__name__)
            return None, request_info
    
    def _session_get(
        self,
        url: str,
        *,
        headers: Optional[Dict] = None,
        timeout: int = 15
    ) -> Tuple[Optional[requests.Response], Dict]:
        """封装GET请求"""
        return self._session_request('GET', url, headers=headers, timeout=timeout)
    
    def _session_post(
        self,
        url: str,
        *,
        headers: Optional[Dict] = None,
        data: Optional[Dict] = None,
        timeout: int = 15
    ) -> Tuple[Optional[requests.Response], Dict]:
        """封装POST请求"""
        return self._session_request('POST', url, headers=headers, data=data, timeout=timeout)
    
    def __init__(self, disable_proxy=False):
        # 初始化基础爬虫，条件性启用代理
        super().__init__("广东省政策爬虫", enable_proxy=not disable_proxy)
        
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
        
        # 添加去重缓存
        self.seen_policy_ids = set()
        self.seen_policy_hashes = set()
        
        # API配置缓存（用于存储当前分类的API配置）
        self.current_api_config = None
        
        if disable_proxy:
            self.proxies = None
            logger.info("测试模式：代理已全面禁用")
        
        self._category_api_configs = self._load_category_configs()
        
        # 分类年份统计缓存
        self.category_year_counts: Dict[str, List[Tuple[int, int]]] = {}
        self._policy_success_counter = 0
        self._access_limit_strikes = 0
        
        # 载入运行时配置
        self._load_runtime_settings()
        
        self._init_session()
    
    def _init_session(self):
        """初始化会话"""
        self.session = requests.Session()
        self._reset_session_counters()
        
        # 更新headers，移除AJAX相关标识并应用动态配置
        self.headers.update({
            'Origin': 'https://gd.pkulaw.com',
            'Referer': 'https://gd.pkulaw.com/dfxfg/adv',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        })
        
        self._apply_dynamic_headers()
        
        # 设置Cookie（使用随机值降低指纹风险）
        if self.enable_cookie_management:
            self.session.cookies.set(
                'JSESSIONID',
                uuid.uuid4().hex.upper(),
                domain='gd.pkulaw.com'
            )
        
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
        
        if self.enable_proxy:
            current_proxies = getattr(self.session, 'proxies', {})
            if not current_proxies:
                logger.warning("[代理验证] 警告: 启用代理但会话中未检测到代理设置")
            else:
                logger.info(f"[代理验证] 会话代理设置: {current_proxies}")

        if not self._preheat_session():
            logger.warning("初始化会话时预热入口页失败，后续请求可能需要额外重试")
    
    def _rotate_session(self):
        """轮换会话，避免访问限制 (借鉴 old)"""
        if not self.enable_session_rotation:
            return False
        logger.info("轮换会话，避免访问限制...")
        
        # 创建新的会话
        new_session = requests.Session()
        new_session.headers.update(self.headers)
        
        # 生成新的JSESSIONID (随机)
        if self.enable_cookie_management:
            import random
            import string
            new_jsessionid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
            new_session.cookies.set('JSESSIONID', new_jsessionid, domain='gd.pkulaw.com')
        
        # 如果启用代理，设置到新会话
        if self.enable_proxy:
            try:
                from .proxy_pool import get_shared_proxy
                proxy_dict = get_shared_proxy()
                if proxy_dict:
                    new_session.proxies.update(proxy_dict)
                    logger.info(f"新会话设置代理: {proxy_dict}")
            except Exception as e:
                logger.warning(f"新会话代理设置失败: {e}")
        
        # 访问入口页获取新的Cookie
        if not self._preheat_session(new_session, self.current_api_config):
            logger.warning("轮换会话时预热入口页失败")
            return False

        logger.info("成功轮换会话")
        self.session = new_session
        self._reset_session_counters()
        self._apply_dynamic_headers()
        if hasattr(self, 'monitor'):
            self.monitor.record_request(self.base_url, success=True)
        return True
    
    def _handle_access_limit(self, response_text: str) -> bool:
        """检测并处理访问限制"""
        limit_tokens = [
            "您已超过全文最大访问数",
            "访问限制",
            "最大访问数",
            "抱歉，您已超过全文最大访问数",
        ]
        if not any(token in response_text for token in limit_tokens):
            self._access_limit_strikes = 0
            return False

        self._access_limit_strikes += 1
        backoff_seconds = min(180, 30 * self._access_limit_strikes)

        logger.warning(
            "检测到访问限制，第%s次尝试，%s秒后重建会话并刷新代理",
            self._access_limit_strikes,
            backoff_seconds,
        )

        try:
            self.force_refresh_proxy()
        except Exception as exc:  # noqa: BLE001
            logger.debug("刷新代理时出现异常（忽略继续）: %s", exc)

        time.sleep(backoff_seconds)
        if self._rotate_session():
            self._preheat_session(api_config=self.current_api_config)
            logger.info("会话轮换成功，准备继续请求")
            return True

        logger.warning("会话轮换失败，仍将继续使用原会话")
        return False
    
    def _check_access_limit(self, response_text: str) -> bool:
        """检查响应是否包含访问限制提示（从测试脚本迁移，兼容方法）
        
        Returns:
            True if 检测到访问限制，False otherwise
        """
        return self._handle_access_limit(response_text)
    
    def _request_page_with_check(self, page_index, search_params, old_page_index=None, api_config=None):
        """带翻页校验的页面请求 (借鉴 old，重试 3 次)"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 1. 先请求翻页校验接口 (从第2页开始，如果 api_config 提供)
                # 注意：翻页校验接口需要正确的OldPageIndex和newPageIndex参数
                if api_config and page_index > 1 and old_page_index is not None:
                    check_url = f"{self.base_url}/VerificationCode/GetRecordListTurningLimit"
                    check_headers = self.headers.copy()
                    check_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
                    
                    # 构建翻页校验参数（需要包含OldPageIndex和newPageIndex）
                    check_params = search_params.copy()
                    check_params['OldPageIndex'] = str(old_page_index)
                    check_params['newPageIndex'] = str(page_index)
                    
                    logger.debug(f"请求翻页校验接口: 第{page_index}页 (上一页={old_page_index}, 重试{retry_count + 1}/{max_retries})")
                    check_resp, check_info = self._session_post(
                        check_url,
                        data=check_params,
                        headers=check_headers,
                        timeout=15
                    )
                    if not check_resp or check_resp.status_code != 200:
                        logger.warning(f"翻页校验失败: {check_info.get('status_code', 'No response')}")
                    else:
                        logger.debug(f"翻页校验成功: 第{page_index}页")
                
                # 2. 再请求数据接口
                if api_config:
                    default_search_url = f"{self.base_url}/{api_config.get('menu', 'dfxfg')}/search/RecordSearch"
                    search_url = api_config.get('search_url', default_search_url)
                else:
                    search_url = f"{self.base_url}/dfxfg/search/RecordSearch"
                search_headers = self.headers.copy()
                search_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
                
                # 更新搜索参数中的OldPageIndex和newPageIndex（确保正确设置）
                if old_page_index is not None:
                    search_params['OldPageIndex'] = str(old_page_index)
                    search_params['newPageIndex'] = str(page_index)
                else:
                    # 第一页不需要OldPageIndex
                    search_params['OldPageIndex'] = ''
                    search_params['newPageIndex'] = ''
                
                logger.debug(f"请求数据接口: 第{page_index}页 (重试{retry_count + 1}/{max_retries})")
                
                search_resp, search_info = self._session_post(
                    search_url,
                    data=search_params,
                    headers=search_headers,
                    timeout=20
                )
                
                if search_resp and search_resp.status_code == 200:
                    # 检查响应内容是否包含访问限制
                    if search_info.get('access_blocked'):
                        logger.info(f"检测到访问限制，已完成会话轮换，准备重试第{page_index}页")
                        retry_count += 1
                        time.sleep(5)
                        continue

                    if self._handle_access_limit(search_resp.text):
                        logger.info(f"检测到访问限制，已轮换会话，重试第{page_index}页")
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
                        logger.info("检测到访问限制，尝试轮换会话...")
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
                    
            except Exception as e:
                logger.error(f"请求异常: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)  # 等待2秒后重试
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
        """解析HTML响应中的政策列表 - 优先使用 checkbox 方法，失败时使用备用方法"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            policies = []

            # 方法1：优先使用 checkbox 方法提取政策 ID
            checkboxes = soup.select('input.checkbox[name="recordList"]')
            checkbox_policies = []
            if checkboxes:
                logger.debug(f"从 checkbox 提取到 {len(checkboxes)} 个政策 ID")
                for checkbox in checkboxes:
                    policy_id = checkbox.get('value', '').strip()
                    if policy_id and len(policy_id) > 10:  # 有效 ID
                        # 根据当前 API 配置确定链接路径
                        current_config = getattr(self, 'current_api_config', None)
                        if current_config and isinstance(current_config, dict):
                            link_path = current_config.get('library', 'gddigui')
                        else:
                            link_path = 'gddigui'  # 默认
                        url = f"{self.base_url}/{link_path}/{policy_id}.html"

                        policy_data = {
                            'level': '广东省人民政府',
                            'title': f'政策ID: {policy_id}',  # 临时标题，后续详情提取
                            'pub_date': '',  
                            'source': url,
                            'url': url,
                            'content': '',  
                            'category': category_name or '',
                            'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'policy_id': policy_id,
                            '_need_detail_fetch': True  # 标记需要详情
                        }
                        # 计算 checksum (基于临时数据)
                        policy_data['checksum'] = self._generate_policy_hash(policy_data)
                        logger.debug(f"生成 checkbox 政策 checksum: {policy_data['checksum'][:8]}...")

                        checkbox_policies.append(policy_data)

            # 方法2：如果 checkbox 方法失败，使用备用解析方法（list-title等）
            if not checkbox_policies:
                logger.debug("checkbox 方法未找到政策，尝试使用备用解析方法...")
                try:
                    # 使用 _parse_policy_list_record_search 作为备用方法
                    backup_policies = self._parse_policy_list_record_search(
                        soup, callback=callback, stop_callback=stop_callback, category_name=category_name
                    )
                    if backup_policies:
                        logger.info(f"备用解析方法成功，找到 {len(backup_policies)} 条政策")
                        # 将备用方法解析的政策转换为标准格式
                        for policy in backup_policies:
                            # 如果政策没有 policy_id，尝试从 URL 中提取
                            if not policy.get('policy_id') and policy.get('url'):
                                url = policy.get('url', '')
                                # 尝试从 URL 中提取 policy_id（格式：/library/policy_id.html）
                                import re
                                match = re.search(r'/([^/]+)\.html$', url)
                                if match:
                                    policy['policy_id'] = match.group(1)
                                    policy['_need_detail_fetch'] = True
                            
                            # 如果没有 checksum，生成一个
                            if not policy.get('checksum'):
                                policy['checksum'] = self._generate_policy_hash(policy)
                        
                        checkbox_policies = backup_policies
                    else:
                        logger.warning("备用解析方法也未找到政策，返回空列表")
                except Exception as e:
                    logger.warning(f"备用解析方法失败: {e}", exc_info=True)
            
            if not checkbox_policies:
                logger.warning("所有解析方法都失败，返回空列表")
                return []

            policies = checkbox_policies
            logger.info(f"使用 checkbox 方法解析 {len(policies)} 条政策")

            # 检查停止
            if stop_callback and stop_callback():
                logger.info("用户已停止解析")
                return policies

            # 批量获取详情并筛选地区
            policies_needing_detail = [p for p in policies if p.get('_need_detail_fetch')]
            if policies_needing_detail:
                logger.info(f"批量获取 {len(policies_needing_detail)} 条政策的详情内容...")
                filtered_policies = []
                
                # 获取分类代码（用于辅助判断）
                category_code = None
                if category_name:
                    # 从分类名称获取分类代码
                    flat_categories = self._get_flat_categories()
                    for cat_name, cat_code in flat_categories:
                        if cat_name == category_name:
                            category_code = cat_code
                            break
                
                for policy in policies_needing_detail:
                    if stop_callback and stop_callback():
                        break

                    url = policy.get('url')
                    if url:
                        try:
                            logger.debug(f"获取政策详情: {url}")
                            detail_data = self.get_policy_detail(url, expected_title=policy.get('title'))

                            content = ''
                            real_title = None
                            doc_number = None
                            pub_date = None
                            validity = None

                            if isinstance(detail_data, dict):
                                content = detail_data.get('content', '')
                                real_title = detail_data.get('title')
                                doc_number = detail_data.get('doc_number')
                                pub_date = detail_data.get('pub_date')
                                validity = detail_data.get('validity')
                                issue_department = detail_data.get('issue_department', '')  # 发布机关
                            else:
                                content = detail_data
                                issue_department = ''

                            if real_title:
                                policy['title'] = real_title
                            if doc_number:
                                policy['doc_number'] = doc_number
                            if pub_date:
                                policy['pub_date'] = pub_date
                            if validity:
                                policy['validity'] = validity
                            if issue_department:
                                policy['issue_department'] = issue_department

                            if content and len(content) > 50:
                                policy['content'] = content
                                policy['checksum'] = self._generate_policy_hash(policy)
                                logger.info(
                                    "✓ 详情更新: 标题=%s, checksum=%s...",
                                    policy.get('title', '')[:50],
                                    policy.get('checksum', '')[:8]
                                )
                            else:
                                logger.warning(f"详情内容为空或过短: {len(content) if content else 0}")

                            policy.pop('_need_detail_fetch', None)
                            
                            # 地区筛选：只保留省级和中山市政策（作用于全省或全市）
                            if self._should_keep_policy(policy, category_code):
                                filtered_policies.append(policy)
                                # 记录详细信息
                                region = self._identify_policy_region(policy)
                                scope = self._identify_scope(policy)
                                level = self._identify_level(policy)
                                logger.debug(
                                    f"保留政策: {policy.get('title', '')[:50]} | "
                                    f"地区: {region} | 作用范围: {scope} | 层级: {level}"
                                )
                            else:
                                region = self._identify_policy_region(policy)
                                scope = self._identify_scope(policy)
                                validity = policy.get('validity', '')
                                logger.info(
                                    f"已过滤政策: {policy.get('title', '')[:50]} | "
                                    f"地区: {region} | 作用范围: {scope} | 时效性: {validity}"
                                )

                        except Exception as e:
                            logger.warning(f"获取政策详情失败: {url}, 错误: {e}")
                            policy.pop('_need_detail_fetch', None)
                            # 获取失败的政策，默认保留（避免误删）
                            filtered_policies.append(policy)
                
                # 使用筛选后的政策列表
                policies = filtered_policies
                filtered_count = len(policies_needing_detail) - len(policies)
                logger.info(
                    f"筛选完成 - 保留: {len(policies)} 条（省级全省适用 + 中山市全市适用），"
                    f"已过滤: {filtered_count} 条（其他城市/特定区域/已废止）"
                )

            # 发送解析完成信号 (保持原有)
            if policy_callback:
                logger.info(f"checkbox 方法完成，发送 {len(policies)} 条政策数据...")
                for policy in policies:
                    if stop_callback and stop_callback():
                        break
                    try:
                        policy_callback(policy)
                        time.sleep(0.005)  # 小延迟保持兼容
                    except Exception as cb_error:
                        logger.warning(f"发送政策数据失败: {cb_error}")

            return policies

            # 移除所有传统解析代码 (no policy_items, no selectors loop, no all_policy_items merge, no traditional for loop)

        except Exception as e:
            logger.error(f"解析政策列表失败: {e}", exc_info=True)
            return []
    
    def _extract_policy_from_item(self, item, category_name):
        """从单个HTML元素中提取政策信息 - 优化版本"""
        try:
            # 查找标题链接
            title_link = None
            if hasattr(item, 'find'):
                title_link = item.find('a')  
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
            detail_title = None
            detail_doc_number = None
            detail_pub_date = None
            try:
                if url:
                    logger.debug(f"获取政策详情: {url}")
                    detail_data = self.get_policy_detail(url, expected_title=title)
                    if isinstance(detail_data, dict):
                        content = detail_data.get('content', '')
                        detail_title = detail_data.get('title')
                        detail_doc_number = detail_data.get('doc_number')
                        detail_pub_date = detail_data.get('pub_date')
                    else:
                        content = detail_data

                    if content and len(content) > 50:
                        logger.debug(f"成功获取政策详情，长度: {len(content)}")
                    else:
                        logger.debug(f"政策详情内容为空或过短: {len(content) if content else 0}")
            except Exception as e:
                logger.warning(f"获取政策详情失败: {url}, {e}")

            if detail_title:
                title = detail_title
            if detail_doc_number:
                doc_number = detail_doc_number
            if detail_pub_date:
                pub_date = detail_pub_date
            
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
        """
        获取扁平化的分类列表（用于中山市特化法规知识库）
        只返回需要的分类，不包含自治条例和单行条例
        """
        flat_categories = [
            # 地方性法规
            ("省级地方性法规", "XM0701"),  # 获取全部 (859)
            ("设区的市地方性法规", "XM0702"),  # 只获取中山市人大 (8)
            
            # 地方政府规章
            ("省级地方政府规章", "XO0802"),  # 获取广东省人民政府 (764)
            ("设区的市地方政府规章", "XO0803"),  # 获取中山市人民政府 (21)
            
            # 规范性文件
            ("地方规范性文件", "XP08"),  # 获取中山市人大、政府、其他机构 (9+640+292)
            
            # 不包含：经济特区法规 (XM0703)、自治条例和单行条例 (XU13)
        ]
        return flat_categories
    
    def _generate_filter_keywords(self, use_keyword_search=True):
        """
        生成用于筛选的关键词组合（用于中山市特化法规知识库）
        
        Args:
            use_keyword_search: 是否使用关键词检索（True：使用关键词直接检索，False：爬取后筛选）
        
        Returns:
            List[str]: 关键词列表，用于直接检索省级和中山市政策
        """
        if not use_keyword_search:
            return None
        
        # 省级政策关键词（用于检索全省适用的政策）
        provincial_keywords = [
            '广东省',  # 最通用的省级关键词
            # 注意：不包含"粤府"等文号，因为文号在标题中可能不完整
        ]
        
        # 中山市政策关键词
        zhongshan_keywords = [
            '中山市',  # 最通用的中山市关键词
            # 注意：不包含"中府"等文号，因为文号在标题中可能不完整
        ]
        
        # 组合关键词：使用OR逻辑（任何一个匹配即可）
        # 注意：由于网站搜索可能不支持OR逻辑，我们需要分别搜索
        # 这里返回一个组合关键词列表，实际使用时可能需要分别搜索
        
        # 返回组合关键词（如果网站支持OR搜索）
        # 如果不支持，需要在调用方分别搜索
        return provincial_keywords + zhongshan_keywords
    
    def _get_issue_department_lvalues(self, category_code: str):
        """
        根据分类代码获取发布机关的lvalue值列表（用于高级搜索）
        按照中山市特化法规知识库需求精确配置
        注意：规范性文件(XP08)包含省级和中山市相关机构
        
        Args:
            category_code: 分类代码
        
        Returns:
            List[str]: 发布机关lvalue值列表，空列表表示不使用发布机关筛选
        """
        # 省级地方性法规 (XM0701)：获取全部省级机构
        # 注意：测试显示81903在dfxfg菜单中无数据，需要使用81901（广东省人大）
        # 或者可能需要分别获取多个发布机关
        if category_code == 'XM0701':
            # 先尝试使用81901（广东省人大），如果不够再考虑其他方式
            return ['81901']  # 广东省人大(含常委会)
        
        # 设区的市地方性法规 (XM0702)：只获取中山市人大
        # 注意：测试显示81937在dfxfg菜单中无效，需要不使用发布机关筛选
        # 改为获取所有XM0702数据，在后续筛选阶段过滤出中山市的
        if category_code == 'XM0702':
            # 不使用发布机关筛选，获取所有设区的市地方性法规，后续筛选出中山市的
            return []  # 返回空列表表示不使用发布机关筛选
        
        # 省级地方政府规章 (XO0802)：只获取广东省人民政府
        if category_code == 'XO0802':
            return ['81902']  # 广东省人民政府 (764条)
        
        # 设区的市地方政府规章 (XO0803)：只获取中山市人民政府
        if category_code == 'XO0803':
            return ['81938']  # 中山市人民政府 (21条)
        
        # 规范性文件 (XP08)：获取省级和中山市相关机构
        # 注意：测试显示81937在XP08分类中无效（即使使用ClassCodeKey=XP08）
        # 虽然之前保存的HTML显示有9条数据，但当前测试无法获取
        # 如果确实需要81937的数据，可以考虑不使用发布机关筛选，后续筛选出中山市人大的政策
        if category_code == 'XP08':
            return [
                # 省级机构
                '81901',  # 广东省人大(含常委会) (40条)
                '81902',  # 广东省人民政府 (1923条)
                '81903',  # 广东省其他机构 (8740条)
                # 中山市机构
                # '81937',  # 中山市人大(含常委会) - 当前测试显示无效，暂不使用
                '81938',  # 中山市人民政府 (640条)
                '81939',  # 中山市其他机构 (292条)
            ]
        
        # 其他分类：不使用发布机关筛选
        return []
    
    def _get_issue_department_lvalue(self, category_code: str):
        """
        根据分类代码获取发布机关的lvalue值（用于高级搜索）
        注意：对于需要多个发布机关的分类（如XP08），返回None，需要分别处理
        
        Args:
            category_code: 分类代码
        
        Returns:
            str: 发布机关lvalue值，None表示需要分别处理多个发布机关
        """
        lvalues = self._get_issue_department_lvalues(category_code)
        if not lvalues:
            return None
        
        # 如果只有一个lvalue，直接返回
        if len(lvalues) == 1:
            return lvalues[0]
        
        # 如果有多个lvalue（如规范性文件），返回None，需要分别处理
        return None
    
    def _get_search_keywords_for_category(self, category_code: str, use_keyword_search=True):
        """
        根据分类代码获取搜索关键词（用于中山市特化法规知识库）
        
        注意：如果已有发布机关筛选，则不需要关键词检索（发布机关筛选更精确）
        
        Args:
            category_code: 分类代码
            use_keyword_search: 是否使用关键词检索
        
        Returns:
            List[str]: 关键词列表，None表示不使用关键词检索
        """
        if not use_keyword_search:
            return None
        
        # 检查是否有发布机关筛选
        issue_department_lvalue = self._get_issue_department_lvalue(category_code)
        if issue_department_lvalue:
            # 有发布机关筛选，不需要关键词检索（发布机关筛选更精确）
            logger.debug(f"分类 {category_code} 已有发布机关筛选（lvalue={issue_department_lvalue}），跳过关键词检索")
            return None
        
        # 无发布机关筛选的分类，考虑使用关键词检索
        # 规范性文件：需要分别处理省级和市级，不使用关键词检索（在后续筛选阶段处理）
        if category_code == 'XP08':
            return None
        
        # 其他分类（经济特区法规、自治条例等）：不使用关键词检索，将在后续筛选阶段处理
        return None
    
    def _get_search_parameters(self, keywords=None, category_code=None, page_index=1, page_size=20, start_date=None, end_date=None, old_page_index=None, filter_year=None, api_config=None, issue_department_lvalue=None):
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
            issue_department_lvalue: 发布机关lvalue值（如果提供，将优先使用，否则根据category_code自动获取）
        """
        # 如果没有提供api_config，根据分类代码获取
        if api_config is None:
            if category_code:
                api_config = self._get_category_api_config(category_code)
                self.current_api_config = api_config
            else:
                # 使用默认配置（dfxfg 接口）
                api_config = API_PATH_MAP['dfxfg'].copy()
                api_config.update({
                    'search_url': f"{self.base_url}/dfxfg/search/RecordSearch",
                    'init_page': f"{self.base_url}/dfxfg/adv",
                    'referer': f"{self.base_url}/dfxfg/adv"
                })
        
        # 根据接口类型调整页大小（fljs接口使用100条/页来突破500页限制）
        # if api_config.get('menu') == 'fljs' and page_size == 20:
        #     page_size = 100  # fljs接口使用更大的页大小
        #     logger.debug(f"fljs接口检测到，调整页大小为 {page_size}")
        
        # 获取发布机关lvalue（优先使用传入的值，否则根据category_code自动获取）
        if issue_department_lvalue is None and category_code:
            issue_department_lvalue = self._get_issue_department_lvalue(category_code)
            if issue_department_lvalue:
                logger.debug(f"自动获取发布机关筛选: category_code={category_code}, lvalue={issue_department_lvalue}")
        
        # 基于网站表单分析，使用正确的参数名称
        search_params = {
            'Menu': api_config['menu'],  # 根据分类类型动态选择菜单
            'Keywords': ' '.join(keywords) if keywords and len(keywords) > 0 else '',  # 支持多个关键词
            'SearchKeywordType': 'Title',  # 标题搜索
            'MatchType': 'Fuzzy',  # 模糊匹配（更灵活，能匹配包含关键词的标题）
            'RangeType': 'Piece',
            'Library': api_config['library'],  # 根据分类类型动态选择库
            'ClassFlag': api_config['class_flag'],
            'GroupLibraries': '',
            'QueryOnClick': 'False',
            'AfterSearch': 'False',
            'pdfStr': '',
            'pdfTitle': '',
            'IsAdv': 'True',
            # 注意：测试显示，当使用 AdvSearchDic.IssueDepartment 时，仍然需要同时设置 ClassCodeKey
            # 两者可以同时使用，ClassCodeKey限制分类，IssueDepartment限制发布机关
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
            'AdvSearchDic.IssueDepartment': issue_department_lvalue or '',  # 使用发布机关lvalue直接筛选
            'AdvSearchDic.DocumentNO': '',
            'AdvSearchDic.IssueDate': start_date or '',  # 保留日期筛选作为备用
            'AdvSearchDic.ImplementDate': end_date or '',  # 保留日期筛选作为备用
            'AdvSearchDic.TimelinessDic': '',
            'AdvSearchDic.EffectivenessDic': '',
            'TitleKeywords': ' '.join(keywords) if keywords else '',
            'FullTextKeywords': ' '.join(keywords) if keywords else '',
            'Pager.PageIndex': str(page_index),
            'Pager.PageSize': str(page_size),  # 页面大小保持与前端一致（默认20条）
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
    
    def _identify_region_by_department(self, issue_department: str) -> str:
        """
        基于发布机关识别地区
        
        Returns:
            'provincial': 省级
            'zhongshan': 中山市
            'other': 其他城市
            'unknown': 无法识别
        """
        if not issue_department:
            return 'unknown'
        
        # 省级识别
        if '广东省人民政府' in issue_department:
            return 'provincial'
        if '广东省' in issue_department and ('人大' in issue_department or '人大常委会' in issue_department):
            return 'provincial'
        if '广东省' in issue_department and '政协' in issue_department:
            return 'provincial'
        
        # 中山市识别
        if '中山市人民政府' in issue_department:
            return 'zhongshan'
        if '中山市' in issue_department and ('人大' in issue_department or '人大常委会' in issue_department):
            return 'zhongshan'
        if '中山市' in issue_department and '政协' in issue_department:
            return 'zhongshan'
        
        # 其他城市识别（排除）
        exclude_cities = [
            '广州市', '深圳市', '珠海市', '汕头市', '佛山市',
            '韶关市', '湛江市', '肇庆市', '江门市', '茂名市',
            '惠州市', '梅州市', '汕尾市', '河源市', '阳江市',
            '清远市', '东莞市', '潮州市', '揭阳市', '云浮市'
        ]
        for city in exclude_cities:
            if city in issue_department:
                return 'other'
        
        return 'unknown'
    
    def _identify_region_by_doc_number(self, doc_number: str) -> str:
        """
        基于文号识别地区
        
        Returns:
            'provincial': 省级
            'zhongshan': 中山市
            'other': 其他城市
            'unknown': 无法识别
        """
        if not doc_number:
            return 'unknown'
        
        # 省级文号模式
        provincial_patterns = [
            r'^粤府[（\(]?\d{4}[）\)]?',  # 粤府[2024]1号
            r'^粤府办[（\(]?\d{4}[）\)]?',  # 粤府办[2024]1号
            r'^粤[A-Z]{0,3}[（\(]?\d{4}[）\)]?',  # 粤XX[2024]1号
            r'^广东省',  # 广东省XX号
        ]
        for pattern in provincial_patterns:
            if re.search(pattern, doc_number):
                return 'provincial'
        
        # 中山市文号模式
        zhongshan_patterns = [
            r'^中府[（\(]?\d{4}[）\)]?',  # 中府[2024]1号
            r'^中府办[（\(]?\d{4}[）\)]?',  # 中府办[2024]1号
            r'^中山市',  # 中山市XX号
            r'^中[A-Z]{0,3}[（\(]?\d{4}[）\)]?',  # 中XX[2024]1号
        ]
        for pattern in zhongshan_patterns:
            if re.search(pattern, doc_number):
                return 'zhongshan'
        
        # 其他城市文号模式（排除）
        exclude_patterns = [
            r'^穗府', r'^深府', r'^珠府', r'^汕府', r'^佛府',
            r'^韶府', r'^湛府', r'^肇府', r'^江府', r'^茂府',
            r'^惠府', r'^梅府', r'^河府', r'^阳府', r'^清府',
            r'^东府', r'^潮府', r'^揭府', r'^云府'
        ]
        for pattern in exclude_patterns:
            if re.search(pattern, doc_number):
                return 'other'
        
        return 'unknown'
    
    def _identify_region_by_title(self, title: str) -> str:
        """
        基于标题识别地区（辅助方法，准确性较低）
        """
        if not title:
            return 'unknown'
        
        # 省级标题模式
        if title.startswith('广东省'):
            # 需要进一步检查，因为可能是"广东省XX市XX条例"
            if '市' in title and not title.startswith('广东省人民政府'):
                # 可能是市级政策，需要结合其他字段判断
                return 'unknown'
            return 'provincial'
        
        # 中山市标题模式
        if title.startswith('中山市'):
            return 'zhongshan'
        
        # 其他城市标题模式（排除）
        exclude_cities = [
            '广州市', '深圳市', '珠海市', '汕头市', '佛山市',
            '韶关市', '湛江市', '肇庆市', '江门市', '茂名市',
            '惠州市', '梅州市', '汕尾市', '河源市', '阳江市',
            '清远市', '东莞市', '潮州市', '揭阳市', '云浮市'
        ]
        for city in exclude_cities:
            if title.startswith(city):
                return 'other'
        
        return 'unknown'
    
    def _identify_policy_region(self, policy: Dict) -> str:
        """
        综合识别政策所属地区
        
        优先级：
        1. 发布机关（最准确）
        2. 文号（次准确）
        3. 标题（辅助）
        
        Returns:
            'provincial': 省级政策
            'zhongshan': 中山市政策
            'other': 其他地区政策（需排除）
            'unknown': 无法识别（默认保留，避免误删）
        """
        issue_department = policy.get('issue_department', '')
        doc_number = policy.get('doc_number', '')
        title = policy.get('title', '')
        
        # 优先级1: 发布机关
        region = self._identify_region_by_department(issue_department)
        if region != 'unknown':
            return region
        
        # 优先级2: 文号
        region = self._identify_region_by_doc_number(doc_number)
        if region != 'unknown':
            return region
        
        # 优先级3: 标题
        region = self._identify_region_by_title(title)
        if region != 'unknown':
            return region
        
        return 'unknown'  # 返回unknown，由调用方决定是否保留
    
    def _identify_scope(self, policy: Dict) -> str:
        """
        识别政策作用范围
        
        Returns:
            'province_wide': 全省适用
            'city_wide': 全市适用（中山市）
            'both': 同时适用于全省和全市
            'specific': 特定区域（需要排除）
            'unknown': 无法识别
        """
        content = policy.get('content', '')
        title = policy.get('title', '')
        
        # 只检查前2000字符，提高效率
        content_preview = content[:2000] if content else ''
        text_to_check = f"{title} {content_preview}"
        
        # 检查是否包含全省关键词
        province_keywords = [
            '全省', '本省行政区域', '全省范围内', '全省各地', '全省各市', 
            '全省统一', '全省通办', '全省建立', '本省', '全省范围内'
        ]
        has_province_scope = any(keyword in text_to_check for keyword in province_keywords)
        
        # 检查是否包含全市关键词（中山市）
        city_keywords = [
            '全市', '本市行政区域', '全市范围内', '全市各地', 
            '全市统一', '全市通办', '全市建立', '本市', '全市范围内'
        ]
        has_city_scope = any(keyword in text_to_check for keyword in city_keywords)
        
        # 判断作用范围
        if has_province_scope and has_city_scope:
            return 'both'
        elif has_province_scope:
            return 'province_wide'
        elif has_city_scope:
            return 'city_wide'
        else:
            # 检查是否特定区域（需要更精确的判断）
            # 这里暂时返回unknown，由调用方根据其他信息判断
            return 'unknown'
    
    def _check_validity(self, policy: Dict) -> bool:
        """
        检查政策是否有效（时效性过滤）
        
        Returns:
            True: 有效（保留）
            False: 已废止/失效（排除）
        """
        validity = policy.get('validity', '')
        
        if not validity:
            # 如果没有时效性信息，默认保留（保守处理）
            return True
        
        # 已废止/失效关键词
        invalid_keywords = ['已废止', '已失效', '废止', '失效', '不再执行', '已停止执行']
        if any(keyword in validity for keyword in invalid_keywords):
            logger.debug(f"政策已废止/失效，排除: {policy.get('title', '')[:50]}, 时效性: {validity}")
            return False
        
        # 有效关键词
        valid_keywords = ['现行有效', '有效', '正在执行', '执行中']
        if any(keyword in validity for keyword in valid_keywords):
            return True
        
        # 默认保留（保守处理）
        return True
    
    def _identify_level(self, policy: Dict) -> str:
        """
        识别政策层级
        
        Returns:
            'national': 国家层级
            'provincial': 省级层级
            'city': 市级层级（中山市）
            'unknown': 无法识别
        """
        issue_department = policy.get('issue_department', '')
        doc_number = policy.get('doc_number', '')
        
        # 国家层级
        if '国务院' in issue_department or '全国人大' in issue_department or '全国人大常委会' in issue_department:
            return 'national'
        if doc_number and (doc_number.startswith('国') or doc_number.startswith('中华人民共和国')):
            return 'national'
        
        # 省级层级
        if '广东省' in issue_department and ('人民政府' in issue_department or '人大' in issue_department):
            return 'provincial'
        if doc_number and doc_number.startswith('粤'):
            return 'provincial'
        
        # 市级层级（中山市）
        if '中山市' in issue_department:
            return 'city'
        if doc_number and doc_number.startswith('中'):
            return 'city'
        
        return 'unknown'
    
    def _should_keep_policy(self, policy: Dict, category_code: str = None) -> bool:
        """
        判断是否应该保留该政策（用于中山市特化法规知识库）
        
        保留条件：
        1. 地区：省级 OR 中山市
        2. 作用范围：全省适用 OR 全市适用（中山市）OR 两者都适用
        3. 时效性：现行有效
        4. 层级：国家 OR 省级 OR 市级（中山市）
        
        Args:
            policy: 政策字典
            category_code: 分类代码（用于辅助判断）
        
        Returns:
            True: 保留
            False: 排除
        """
        # 1. 地区识别（省级或中山市）
        region = self._identify_policy_region(policy)
        if region == 'other':
            logger.debug(f"排除其他城市政策: {policy.get('title', '')[:50]}")
            return False  # 排除其他城市政策
        
        # 2. 时效性检查（优先检查，避免处理无效政策）
        if not self._check_validity(policy):
            return False  # 排除已废止/失效政策
        
        # 3. 作用范围识别
        scope = self._identify_scope(policy)
        
        # 4. 层级识别（用于日志记录，但不影响筛选结果）
        # level = self._identify_level(policy)  # 暂时注释，避免未使用变量警告
        
        # 5. 综合判断
        # 省级政策：需要全省适用
        if region == 'provincial':
            if scope in ['province_wide', 'both', 'unknown']:
                # unknown时，省级政策默认视为全省适用
                logger.debug(f"保留省级政策（全省适用）: {policy.get('title', '')[:50]}")
                return True
            else:
                logger.debug(f"省级政策但作用范围不是全省，排除: {policy.get('title', '')[:50]}, 作用范围: {scope}")
                return False
        
        # 中山市政策：需要全市适用
        elif region == 'zhongshan':
            if scope in ['city_wide', 'both', 'unknown']:
                # unknown时，中山市政策默认视为全市适用
                logger.debug(f"保留中山市政策（全市适用）: {policy.get('title', '')[:50]}")
                return True
            else:
                logger.debug(f"中山市政策但作用范围不是全市，排除: {policy.get('title', '')[:50]}, 作用范围: {scope}")
                return False
        
        # 无法识别地区时，根据分类判断
        else:
            if category_code in ['XM0701', 'XO0802']:
                # 省级分类，默认保留（视为全省适用）
                logger.warning(f"无法识别地区，但属于省级分类，默认保留: {policy.get('title', '')[:50]}")
                return True
            else:
                # 其他情况，保守处理：保留（避免误删）
                logger.warning(f"无法识别地区，默认保留: {policy.get('title', '')[:50]}")
                return True
    
    def _are_pages_identical(self, page1_policies: List[Dict], page2_policies: List[Dict]) -> bool:
        """
        检查两页政策数据是否完全一致
        
        Args:
            page1_policies: 第一页的政策列表
            page2_policies: 第二页的政策列表
        
        Returns:
            True: 完全一致
            False: 不一致
        """
        # 如果数量不同，肯定不一致
        if len(page1_policies) != len(page2_policies):
            return False
        
        # 如果都为空，视为一致
        if len(page1_policies) == 0:
            return True
        
        # 比较每条政策的唯一标识（使用title和doc_number的组合）
        # 如果所有政策的标识都相同，则认为两页完全一致
        page1_identifiers = set()
        for policy in page1_policies:
            title = policy.get('title', '').strip()
            doc_number = policy.get('doc_number', '').strip()
            identifier = f"{title}|{doc_number}"
            page1_identifiers.add(identifier)
        
        page2_identifiers = set()
        for policy in page2_policies:
            title = policy.get('title', '').strip()
            doc_number = policy.get('doc_number', '').strip()
            identifier = f"{title}|{doc_number}"
            page2_identifiers.add(identifier)
        
        # 如果两个集合完全相同，则认为两页完全一致
        return page1_identifiers == page2_identifiers
    
    def _generate_policy_hash(self, policy):
        """生成政策 checksum (优先 content MD5，用于唯一标识)"""
        if isinstance(policy, dict):
            content = policy.get('content', '').strip()
            if content and len(content) > 50:  # 有效内容
                return hashlib.md5(content.encode('utf-8')).hexdigest()
            else:
                # Fallback: title + pub_date + doc_number
                title = policy.get('title', '')
                pub_date = policy.get('pub_date', '')
                doc_number = policy.get('doc_number', '')
                hash_string = f"{title}|{pub_date}|{doc_number}"
                return hashlib.md5(hash_string.encode('utf-8')).hexdigest()
        else:
            return hashlib.md5(str(policy).encode('utf-8')).hexdigest()
    
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
        """去重政策数据 (优先用 checksum)"""
        if not policies:
            return []
        
        seen_checksums = set()
        seen_titles = set()
        unique_policies = []
        
        for policy in policies:
            if isinstance(policy, dict):
                checksum = policy.get('checksum', '')
                title = policy.get('title', '').strip()
                
                if checksum and checksum not in seen_checksums and title and title not in seen_titles:
                    seen_checksums.add(checksum)
                    seen_titles.add(title)
                    unique_policies.append(policy)
                elif not checksum:  # 无 checksum，fallback 原逻辑
                    policy_hash = self._generate_policy_hash(policy)
                    if title and title not in seen_titles and policy_hash not in self.seen_policy_hashes:
                        self.seen_policy_hashes.add(policy_hash)
                        seen_titles.add(title)
                        unique_policies.append(policy)
            elif isinstance(policy, (list, tuple)) and len(policy) >= 2:
                title = str(policy[2]).strip()  # 假设title在第3个位置
                policy_hash = self._generate_policy_hash(policy)
                
                if title and title not in seen_titles and policy_hash not in seen_checksums:
                    seen_checksums.add(policy_hash)
                    seen_titles.add(title)
                    unique_policies.append(policy)
        
        logger.info(f"去重前: {len(policies)} 条 (checksum 唯一)")
        logger.info(f"去重后: {len(unique_policies)} 条")
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

        # 注意：已取消年份分割策略，不再需要刷新年份统计
        # self._refresh_category_year_counts()  # 已废弃，不再使用年份分割策略

        # 解析时间范围（目前未使用，预留功能）
        if start_date and end_date:
            try:
                logger.info(f"时间范围设置: {start_date} 至 {end_date}")
            except ValueError:
                logger.warning("时间格式错误，禁用时间过滤")

        # 设置速度模式（延迟控制已在循环中实现）

        # 获取所有分类
        categories = self._get_flat_categories()
        logger.info(f"找到 {len(categories)} 个分类")

        all_policies = []
        total_crawled = 0

        # 遍历所有分类，直接按分类代码和发布机关获取（取消年份分割策略）
        logger.info("开始按分类代码和发布机关直接获取...")
        if callback:
            callback("开始按分类代码和发布机关直接获取...")

        for category_name, category_code in categories:
            if stop_callback and stop_callback():
                logger.info("用户已停止爬取")
                break

            logger.info(f"正在爬取分类: {category_name} (代码: {category_code})")
            if callback:
                callback(f"正在爬取分类: {category_name}")

            # 获取该分类需要的发布机关列表
            issue_department_lvalues = self._get_issue_department_lvalues(category_code)
            
            if not issue_department_lvalues:
                # 对于不使用发布机关筛选的分类（如XM0702），使用空lvalue获取所有数据，后续筛选
                logger.info(f"分类 {category_name} 不使用发布机关筛选，获取所有数据后筛选")
                dept_policies = self._crawl_category_by_department(
                    category_name,
                    category_code,
                    '',  # 空字符串表示不使用发布机关筛选
                    callback,
                    stop_callback,
                    policy_callback,
                    keywords=keywords,
                    start_date=start_date,
                    end_date=end_date,
                    disable_speed_limit=disable_speed_limit
                )
                
                if dept_policies:
                    category_policies = dept_policies
                    total_crawled += len(category_policies)
                    all_policies.extend(category_policies)
                    logger.info(f"分类[{category_name}] 完成，获取 {len(category_policies)} 条政策")
                else:
                    logger.warning(f"分类[{category_name}] 未获取到政策数据")
                continue
            
            # 对于需要多个发布机关的分类（如规范性文件），分别获取
            category_policies = []
            for lvalue in issue_department_lvalues:
                # 获取发布机关名称（用于日志）
                dept_name = self._get_department_name_by_lvalue(lvalue)
                logger.info(f"  获取发布机关: {dept_name} (lvalue={lvalue})")
                if callback:
                    callback(f"  获取发布机关: {dept_name}")
                
                # 直接按分类和发布机关获取（不使用年份分割）
                dept_policies = self._crawl_category_by_department(
                    category_name,
                    category_code,
                    lvalue,
                    callback,
                    stop_callback,
                    policy_callback,
                    keywords=keywords,
                    start_date=start_date,
                    end_date=end_date,
                    disable_speed_limit=disable_speed_limit
                )
                
                if dept_policies:
                    category_policies.extend(dept_policies)
                    logger.info(f"  发布机关 {dept_name} 获取到 {len(dept_policies)} 条政策")
                else:
                    logger.warning(f"  发布机关 {dept_name} 未获取到政策数据")

            if category_policies:
                total_crawled += len(category_policies)
                all_policies.extend(category_policies)
                logger.info(f"分类[{category_name}] 完成，获取 {len(category_policies)} 条政策")
            else:
                logger.warning(f"分类[{category_name}] 未获取到政策数据")

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
                            detail_data = self.get_policy_detail(url, expected_title=policy.get('title'))

                            if isinstance(detail_data, dict):
                                content = detail_data.get('content', '')
                                real_title = detail_data.get('title')
                                doc_number = detail_data.get('doc_number')
                                pub_date = detail_data.get('pub_date')
                                validity = detail_data.get('validity')
                            else:
                                content = detail_data
                                real_title = None
                                doc_number = None
                                pub_date = None
                                validity = None

                            if real_title:
                                policy['title'] = real_title
                            if doc_number:
                                policy['doc_number'] = doc_number
                            if pub_date:
                                policy['pub_date'] = pub_date
                            if validity:
                                policy['validity'] = validity

                            if content and len(content) > 50:
                                policy['content'] = content
                                policy['checksum'] = self._generate_policy_hash(policy)
                                logger.info(
                                    "✓ china接口：详情更新 标题=%s, checksum=%s...",
                                    policy.get('title', '')[:50],
                                    policy.get('checksum', '')[:8]
                                )
                            else:
                                logger.warning(f"✗ 详情内容为空或过短: {len(content) if content else 0}")

                            policy.pop('_need_detail_fetch', None)

                        except Exception as e:
                            logger.warning(f"✗ china接口：获取政策详情失败: {url}, 错误: {e}")
                            policy.pop('_need_detail_fetch', None)

        # 注意：china接口的政策已经在前面通过policy_callback发送过了
        # 这里批量详情获取是为了更新已发送的数据
        logger.info(f"china接口策略完成，共获取 {len(all_policies)} 条政策")
        return all_policies

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
                    li_items = container.find_all('li')  
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
                    title = title_link.get_text(strip=True)  
                    link = title_link.get('href', '')  
            
            # 方式2：如果方式1失败，查找所有a标签
            if not title or not link:
                all_links = item.find_all('a')
                for a_link in all_links:
                    if hasattr(a_link, 'get_text'):
                        link_text = a_link.get_text(strip=True)  
                        link_href = a_link.get('href', '')  

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
                        link_text = a_link.get_text(strip=True)  
                        link_href = a_link.get('href', '')  

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
                info_text = info_div.get_text(strip=True)  
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
                item_text = item.get_text(strip=True)  
                # 尝试从文本中提取日期
                date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', item_text)
                if date_match:
                    pub_date = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
            
            # 获取详细内容
            content = ""
            if link:
                content = self.get_policy_detail(link, expected_title=title)
            
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
    
    def get_policy_detail(self, url, expected_title=None):
        """获取政策详情内容并提取标题、文号等元数据"""
        max_detail_attempts = 3
        last_detail_data: Dict[str, Any] = {}
    
        for attempt in range(1, max_detail_attempts + 1):
            try:
                headers = self.headers.copy()
    
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
    
                resp, request_info = self.get_page(url, headers=headers)
    
                if not resp:
                    self.monitor.record_request(url, success=False, error_type="request_failed")
                    last_detail_data = {}
                    if attempt < max_detail_attempts:
                        self._maybe_rotate_session(force=True)
                        self.force_refresh_proxy()
                        self._sleep_between_requests(self.speed_mode, False)
                        continue
                    return {}
    
                soup = BeautifulSoup(resp.content, 'html.parser')
                access_blocked = bool(request_info.get('access_blocked'))
                snapshot_path = ""
    
                # 标题提取
                real_title = ''
                title_h2 = soup.select_one('h2.title')
                if title_h2 and title_h2.get_text(strip=True):
                    real_title = title_h2.get_text(strip=True)
    
                if not real_title:
                    title_tag = soup.find('title')
                    if title_tag and title_tag.get_text(strip=True):
                        title_text = re.sub(r' - .*$', '', title_tag.get_text(strip=True)).strip()
                        if title_text and not title_text.startswith('政策ID:'):
                            real_title = title_text
    
                if not real_title:
                    for tag_name in ['h1', 'h2', 'h3']:
                        headings = soup.find_all(tag_name)
                        for heading in headings:
                            heading_text = heading.get_text(strip=True)
                            if heading_text and len(heading_text) > 5 and '政策ID:' not in heading_text:
                                real_title = heading_text
                                break
                        if real_title:
                            break
    
                # 元数据提取
                doc_number = ''
                pub_date = ''
                validity = ''
                issue_department = ''  # 发布机关（用于地区识别）
                
                for li in soup.select('li'):
                    strong = li.find('strong')
                    if not strong:
                        continue
                    label = strong.get_text(strip=True)
                    value = li.get_text(strip=True).replace(label, '').replace('：', '').strip()
                    if '发文字号' in label and value:
                        doc_number = value
                    elif '公布日期' in label and value:
                        pub_date = value.replace('.', '-')
                    elif '施行日期' in label and value and not pub_date:
                        pub_date = value.replace('.', '-')
                    elif ('发布机关' in label or '制定机关' in label) and value:
                        issue_department = value
    
                validity_elem = soup.select_one('.timelinessDic')
                if validity_elem:
                    validity = validity_elem.get_text(strip=True)
    
                # 内容提取
                content_text = ''
                content_div = soup.select_one('div.content')
                if content_div:
                    for tag in content_div.find_all(['script', 'style', 'section', 'aside']):
                        tag.decompose()
                    content_text = content_div.get_text('\n', strip=True)
    
                if not content_text or len(content_text) < 100:
                    for div in soup.find_all('div'):
                        text = div.get_text('\n', strip=True)
                        if text and len(text) > 200 and ('第一条' in text or '条例' in text):
                            content_text = text
                            break
    
                if not content_text:
                    stripped_soup = soup
                    for tag in stripped_soup.find_all(['nav', 'header', 'footer', 'script', 'style']):
                        tag.decompose()
                    content_text = re.sub(r'\s+', ' ', stripped_soup.get_text(strip=True))
    
                # 如果提取到的标题疑似为通用站点名称或拦截页内容，则回退到列表标题
                if real_title:
                    normalized_title = real_title.strip()
                    if normalized_title:
                        generic_titles = {
                            '广东省法规规章数据库',
                            '广东省法规规章数据库检索结果',
                            '广东省法规规章数据库-检索结果',
                            '广东省法规规章数据库（移动版）'
                        }
                        generic_tokens = [
                            '登录注册首页',
                            '抱歉，您已超过全文最大访问数',
                            '北大法宝',
                            '返回广东省人大',
                            '错误提示'
                        ]
                        fallback_required = (
                            normalized_title in generic_titles
                            or (normalized_title.endswith('数据库') and len(normalized_title) <= 12)
                            or any(token in normalized_title for token in generic_tokens)
                            or len(normalized_title) >= 100
                        )
                        if fallback_required:
                            expected_clean = (expected_title or '').strip()
                            if expected_clean:
                                logger.debug(
                                    "详情页返回泛化/拦截标题[%s]，改用列表标题[%s]",
                                    normalized_title[:120],
                                    expected_clean
                                )
                                real_title = expected_clean
                            else:
                                real_title = ''
    
                # 判定是否命中全文访问限制提示
                block_tokens = [
                    '抱歉，您已超过全文最大访问数',
                    '为了保证服务质量',
                    '错误提示',
                    '请登录后再访问全文'
                ]
                if not access_blocked and any(token in resp.text for token in block_tokens):
                    access_blocked = True
                    logger.warning("检测到全文访问限制提示: %s", url)
                    snapshot_path = self._capture_blocked_snapshot(url, resp.text)
                    if snapshot_path:
                        logger.info("限制页面快照已保存: %s", snapshot_path)
                    # 避免把限制页的内容当成正文
                    content_text = ''
                    if expected_title:
                        real_title = expected_title.strip()
    
                detail_data = {
                    'title': real_title.strip() if real_title else '',
                    'doc_number': doc_number.strip() if doc_number else '',
                    'pub_date': pub_date.strip() if pub_date else '',
                    'validity': validity.strip() if validity else '',
                    'issue_department': issue_department.strip() if issue_department else '',  # 发布机关（用于地区识别）
                    'content': content_text.strip(),
                    'raw_html': resp.text,
                    'access_blocked': access_blocked
                }
                last_detail_data = detail_data
    
                if access_blocked:
                    self.monitor.record_request(url, success=False, error_type="access_limited")
                    if attempt < max_detail_attempts:
                        if not request_info.get('access_blocked'):
                            self.force_refresh_proxy()
                            self._maybe_rotate_session(force=True)
                        self._sleep_between_requests(self.speed_mode, False)
                        continue
                    return detail_data
    
                if not content_text or len(content_text) <= 50:
                    logger.warning(f"详情内容为空或过短: {len(content_text) if content_text else 0}")
    
                self.monitor.record_request(url, success=True)
                return detail_data
    
            except requests.exceptions.Timeout as e:
                self.monitor.record_request(url, success=False, error_type="timeout")
                logger.warning(f"获取政策详情超时(尝试 {attempt}/{max_detail_attempts}): {e}", exc_info=True)
                if attempt < max_detail_attempts:
                    self._maybe_rotate_session(force=True)
                    self.force_refresh_proxy()
                    self._sleep_between_requests(self.speed_mode, False)
                    continue
                return {}
            except requests.exceptions.ConnectionError as e:
                self.monitor.record_request(url, success=False, error_type="connection_error")
                logger.error(f"获取政策详情连接错误: {e}", exc_info=True)
                if attempt < max_detail_attempts:
                    self._maybe_rotate_session(force=True)
                    self.force_refresh_proxy()
                    self._sleep_between_requests(self.speed_mode, False)
                    continue
                return {}
            except (ValueError, KeyError, AttributeError) as e:
                self.monitor.record_request(url, success=False, error_type="parse_error")
                logger.warning(f"获取政策详情解析错误: {e}", exc_info=True)
                if attempt < max_detail_attempts:
                    self._maybe_rotate_session(force=True)
                    self.force_refresh_proxy()
                    self._sleep_between_requests(self.speed_mode, False)
                    continue
                return {}
            except Exception as e:
                self.monitor.record_request(url, success=False, error_type="unknown")
                logger.error(f"获取政策详情失败: {e}", exc_info=True)
                if attempt < max_detail_attempts:
                    self._maybe_rotate_session(force=True)
                    self.force_refresh_proxy()
                    self._sleep_between_requests(self.speed_mode, False)
                    continue
                return {}
    
        return last_detail_data if last_detail_data else {}
    
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
            checksum = policy.get('checksum', '')
            if isinstance(policy, dict) and checksum:
                db.insert_policy(  # Assume DB supports checksum param
                    policy['level'],
                    policy['title'],
                    policy['pub_date'],
                    policy['source'],
                    policy['content'],
                    policy['crawl_time'],
                    policy.get('category'),
                    checksum=checksum  # Add checksum arg
                )
                logger.info(f"保存政策到 DB, checksum: {checksum[:8]}...")
            elif isinstance(policy, (list, tuple)) and len(policy) >= 6:
                db.insert_policy(
                    policy[1],  # level
                    policy[2],  # title
                    policy[3],  # pub_date
                    policy[4],  # source
                    policy[5],  # content
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # crawl_time
                    policy[6] if len(policy) > 6 else None,  # category
                    checksum=policy.get('checksum')  # Add checksum arg
                )
                logger.info(f"保存政策到 DB, checksum: {policy.get('checksum', '')[:8]}...")
    
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
                logger.warning("⚠️ 所有标题提取方法都失败了！")
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
                    detail_data = self.get_policy_detail(link, expected_title=title)
                    if isinstance(detail_data, dict):
                        content = detail_data.get('content', '')
                        detail_title = detail_data.get('title')
                        detail_doc = detail_data.get('doc_number')
                        detail_pub = detail_data.get('pub_date')
                        detail_validity = detail_data.get('validity')
                        if detail_title:
                            title = detail_title
                        if detail_doc:
                            document_number = detail_doc
                        if detail_pub:
                            publish_date = detail_pub
                        if detail_validity:
                            validity = detail_validity
                    else:
                        content = detail_data

                    if content:
                        logger.debug(f"成功获取正文，长度: {len(content)} 字符")
                    else:
                        logger.warning("未获取到正文内容")
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
        menu_name = api_config['menu']
        api_config.update({
            'search_url': f"{self.base_url}/{menu_name}/search/RecordSearch",
            'class_search_url': f"{self.base_url}/{menu_name}/search/ClassSearch",
            'init_page': f"{self.base_url}/{menu_name}/adv",
            'referer': f'{self.base_url}/{menu_name}/adv'
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

    def _crawl_category_with_year_split(self, category_name: str, category_code: str, callback=None, stop_callback=None, policy_callback=None, keywords=None, start_date=None, end_date=None, disable_speed_limit=False):
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
        years_info = self.category_year_counts.get(category_code, [])

        if not years_info:
            try:
                # 访问分类的搜索页面获取年份信息
                adv_url = api_config.get('init_page', f"{self.base_url}/{api_config['menu']}/adv")
                headers = self.headers.copy()
                if api_config.get('referer'):
                    headers['Referer'] = api_config['referer']

                resp, _ = self._session_get(adv_url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    years_info = self.extract_years_from_page(resp.text)
                    if years_info:
                        logger.info(f"分类 {category_name} 找到 {len(years_info)} 个年份: {', '.join([f'{y[0]}年({y[1]}条)' for y in years_info[:10]])}")
                        self.category_year_counts[category_code] = years_info
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
                if expected_count <= 0:
                    logger.debug(f"跳过 {category_name} - {year}年 (计数为0)")
                    continue

                logger.info(f"正在爬取 {category_name} - {year}年 (预计 {expected_count} 条)")

                if callback:
                    callback(f"正在爬取 {category_name} - {year}年")

                if expected_count and expected_count > MAX_RECORDS_PER_BATCH:
                    logger.info(
                        f"{category_name} - {year}年 预计 {expected_count} 条，超过 {MAX_RECORDS_PER_BATCH} 条阈值，将按默认分页抓取，如检测到分页受限将提示进一步拆分"
                    )

                # 爬取该年份的数据
                year_policies = self._crawl_category_year(
                    category_name,
                    category_code,
                    year,
                    expected_count,
                    callback,
                    stop_callback,
                    policy_callback,
                    keywords=keywords,
                    start_date=start_date,
                    end_date=end_date,
                    api_config=api_config,
                    disable_speed_limit=disable_speed_limit
                )

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

            year_policies = self._crawl_category_year(
                category_name,
                category_code,
                None,
                None,
                callback,
                stop_callback,
                policy_callback,
                keywords=keywords,
                start_date=start_date,
                end_date=end_date,
                api_config=api_config,
                disable_speed_limit=disable_speed_limit
            )

            if year_policies:
                all_policies.extend(year_policies)
                logger.info(f"{category_name} 全量爬取获取到 {len(year_policies)} 条政策")

        logger.info(f"分类 {category_name} 年份分割爬取完成，共获取 {len(all_policies)} 条政策")
        return all_policies
    
    def _get_department_name_by_lvalue(self, lvalue: str) -> str:
        """
        根据lvalue获取发布机关名称（用于日志显示）
        
        Args:
            lvalue: 发布机关lvalue值
        
        Returns:
            str: 发布机关名称
        """
        dept_map = {
            '81901': '广东省人大(含常委会)',
            '81902': '广东省人民政府',
            '81903': '广东省其他机构',
            '81937': '中山市人大(含常委会)',
            '81938': '中山市人民政府',
            '81939': '中山市其他机构',
        }
        return dept_map.get(lvalue, f'发布机关(lvalue={lvalue})')
    
    def _crawl_category_by_department(self, category_name: str, category_code: str, issue_department_lvalue: str,
                                     callback=None, stop_callback=None, policy_callback=None, keywords=None,
                                     start_date=None, end_date=None, disable_speed_limit=False):
        """
        直接按分类代码和发布机关获取政策（不使用年份分割）
        
        Args:
            category_name: 分类名称
            category_code: 分类代码
            issue_department_lvalue: 发布机关lvalue值
            callback: 进度回调函数
            stop_callback: 停止回调函数
            policy_callback: 政策数据回调函数
            keywords: 关键词列表
            start_date: 起始日期
            end_date: 结束日期
            disable_speed_limit: 是否禁用速度限制
        
        Returns:
            List[Dict]: 政策列表
        """
        logger.info(f"开始按发布机关获取: {category_name} (代码: {category_code}, lvalue: {issue_department_lvalue})")
        
        api_config = self._get_category_api_config(category_code)
        self.current_api_config = api_config
        
        # 初始化：先访问高级搜索页面来设置会话上下文
        try:
            init_url = api_config.get('init_page', f"{self.base_url}/{api_config['menu']}/adv")
            logger.debug(f"初始化会话: 访问 {init_url}")
            init_resp, _ = self._session_get(init_url, timeout=10)
            if init_resp and init_resp.status_code == 200:
                logger.debug("会话初始化成功")
            time.sleep(0.5)  # 短暂延迟
        except Exception as e:
            logger.warning(f"会话初始化失败（继续尝试）: {e}")
        
        # 注意：测试脚本显示，使用发布机关筛选时不需要ClassSearch初始化
        # 直接使用RecordSearch即可，ClassSearch可能导致冲突
        # 因此这里不发送ClassSearch，直接使用RecordSearch
        
        policies = []
        page_index = 1
        max_pages = MAX_RECORDS_PER_BATCH // 20  # 接口页数上限
        empty_page_count = 0
        max_empty_pages = 5  # 连续空页数限制
        prev_page_policies = None  # 保存上一页的政策数据，用于检测重复
        consecutive_duplicate_count = 0  # 连续重复页面计数
        max_consecutive_duplicates = 3  # 最大连续重复页面数（超过此数才停止）
        
        while page_index <= max_pages and empty_page_count < max_empty_pages:
            if stop_callback and stop_callback():
                logger.info("用户已停止爬取")
                break
            
            if callback:
                callback(f"正在获取 {category_name} - 第 {page_index} 页")
            
            # 获取搜索参数（直接传入发布机关lvalue，避免重复设置）
            # 如果issue_department_lvalue为空字符串，则传入None表示不使用发布机关筛选
            effective_lvalue = issue_department_lvalue if issue_department_lvalue else None
            search_params = self._get_search_parameters(
                keywords=keywords,
                category_code=category_code,
                page_index=page_index,
                page_size=20,
                start_date=start_date,
                end_date=end_date,
                filter_year=None,  # 不使用年份筛选
                api_config=api_config,
                issue_department_lvalue=effective_lvalue  # 空字符串转为None
            )
            
            # 使用带翻页校验的请求方法（处理验证码限制）
            # 注意：从第2页开始，网站可能需要翻页校验接口（GetRecordListTurningLimit）
            # 特别是第5-6页可能触发验证码限制
            try:
                prev_page_index = page_index - 1 if page_index > 1 else None
                resp = self._request_page_with_check(
                    page_index,
                    search_params,
                    prev_page_index,
                    api_config=api_config
                )
                
                if not resp or resp.status_code != 200:
                    if resp:
                        logger.warning(f"第 {page_index} 页搜索请求失败: HTTP {resp.status_code}")
                    else:
                        logger.warning(f"第 {page_index} 页搜索请求失败: 无响应")
                    
                    # 检查是否是验证码限制导致的失败
                    if resp and resp.status_code in [403, 429]:
                        logger.warning(f"第 {page_index} 页可能遇到验证码限制（HTTP {resp.status_code}），尝试轮换会话后重试")
                        if self._rotate_session():
                            logger.info("会话轮换成功，继续尝试")
                            # 重新初始化会话
                            try:
                                init_url = api_config.get('init_page', f"{self.base_url}/{api_config['menu']}/adv")
                                init_resp, _ = self._session_get(init_url, timeout=10)
                                if init_resp and init_resp.status_code == 200:
                                    logger.debug("会话重新初始化成功")
                                time.sleep(1)  # 短暂延迟
                            except Exception as e:
                                logger.warning(f"会话重新初始化失败: {e}")
                    
                    empty_page_count += 1
                    page_index += 1
                    continue
                
                # 检查响应内容是否包含访问限制
                # 注意：验证码检测已由_request_page_with_check处理，这里只检查访问限制
                # 如果响应状态码是200，先尝试解析，如果能解析出数据，说明不是验证码限制
                if resp.text:
                    # 先尝试解析，如果能解析出政策数据，说明响应正常
                    page_policies = self._parse_policy_list_html(
                        resp.text,
                        callback=callback,
                        stop_callback=stop_callback,
                        category_name=category_name,
                        policy_callback=policy_callback
                    )
                    
                    # 如果能解析出政策数据，说明响应正常，不需要检查验证码
                    if page_policies:
                        # 响应正常，继续处理
                        pass
                    else:
                        # 无法解析出数据，可能是验证码限制或其他问题
                        # 检查访问限制（仅在真正检测到限制时才处理）
                        if self._handle_access_limit(resp.text):
                            logger.warning(f"第 {page_index} 页检测到访问限制，已处理，继续下一页")
                            # 访问限制已处理（轮换会话等），继续尝试下一页
                            page_index += 1
                            time.sleep(2)  # 短暂延迟
                            continue
                        
                        # 检查是否真的遇到验证码限制（更严格的检测）
                        # 只有当响应明显是验证码页面时才处理
                        # 检查是否是验证码页面：包含验证码输入框或验证码图片
                        verifycode_strong_indicators = [
                            "请输入验证码",
                            "验证码错误",
                            "验证码已过期",
                            "需要输入验证码",
                            "验证码输入框"
                        ]
                        # 检查是否包含验证码输入框的常见HTML元素
                        has_verifycode_input = (
                            'id="verifycode"' in resp.text.lower() or
                            'name="verifycode"' in resp.text.lower() or
                            'class="verifycode"' in resp.text.lower() or
                            '验证码输入框' in resp.text
                        )
                        is_verifycode_page = any(indicator in resp.text for indicator in verifycode_strong_indicators)
                        
                        # 只有当明确是验证码页面时才处理（避免误判）
                        if is_verifycode_page and has_verifycode_input:
                            logger.warning(f"第 {page_index} 页明确检测到验证码限制，尝试轮换会话")
                            if self._rotate_session():
                                logger.info("会话轮换成功，继续尝试")
                                # 重新初始化会话
                                try:
                                    init_url = api_config.get('init_page', f"{self.base_url}/{api_config['menu']}/adv")
                                    init_resp, _ = self._session_get(init_url, timeout=10)
                                    if init_resp and init_resp.status_code == 200:
                                        logger.debug("会话重新初始化成功")
                                    time.sleep(2)  # 延迟后重试
                                except Exception as e:
                                    logger.warning(f"会话重新初始化失败: {e}")
                            # 重试当前页（但只重试一次，避免无限循环）
                            # 注意：这里不应该无限重试，应该继续处理响应
                            logger.info(f"第 {page_index} 页验证码限制已处理，继续解析响应")
                            # 重新解析响应（可能已经更新）
                            page_policies = self._parse_policy_list_html(
                                resp.text,
                                callback=callback,
                                stop_callback=stop_callback,
                                category_name=category_name,
                                policy_callback=policy_callback
                            )
                else:
                    # 响应为空，无法解析
                    page_policies = []
                
                if page_policies:
                    # 检查当前页与上一页是否完全一致
                    if prev_page_policies is not None and page_index > 1:
                        # 比较两页的政策数据
                        if self._are_pages_identical(prev_page_policies, page_policies):
                            logger.warning(f"第 {page_index} 页与第 {page_index - 1} 页完全一致")
                            logger.info(f"  上一页政策: {len(prev_page_policies)} 条")
                            logger.info(f"  当前页政策: {len(page_policies)} 条")
                            # 显示前几条政策的标题，便于调试
                            if prev_page_policies:
                                logger.info(f"  上一页前3条: {[p.get('title', '')[:50] for p in prev_page_policies[:3]]}")
                            if page_policies:
                                logger.info(f"  当前页前3条: {[p.get('title', '')[:50] for p in page_policies[:3]]}")
                            
                            # 检测到重复页面时，先尝试轮换会话（可能是验证码限制导致的）
                            logger.warning("检测到重复页面，尝试轮换会话后重试...")
                            if self._rotate_session():
                                logger.info("会话轮换成功，重新初始化会话")
                                # 重新初始化会话
                                try:
                                    init_url = api_config.get('init_page', f"{self.base_url}/{api_config['menu']}/adv")
                                    init_resp, _ = self._session_get(init_url, timeout=10)
                                    if init_resp and init_resp.status_code == 200:
                                        logger.debug("会话重新初始化成功")
                                    time.sleep(2)  # 延迟后重试
                                    
                                    # 重试当前页（使用新的会话）
                                    logger.info(f"使用新会话重试第 {page_index} 页...")
                                    prev_page_index = page_index - 1 if page_index > 1 else None
                                    retry_resp = self._request_page_with_check(
                                        page_index,
                                        search_params,
                                        prev_page_index,
                                        api_config=api_config
                                    )
                                    
                                    if retry_resp and retry_resp.status_code == 200:
                                        # 重新解析响应
                                        retry_policies = self._parse_policy_list_html(
                                            retry_resp.text,
                                            callback=callback,
                                            stop_callback=stop_callback,
                                            category_name=category_name,
                                            policy_callback=policy_callback
                                        )
                                        
                                        # 检查重试后的页面是否仍然与上一页相同
                                        if retry_policies and not self._are_pages_identical(prev_page_policies, retry_policies):
                                            logger.info(f"会话轮换后，第 {page_index} 页获取到新数据，继续爬取")
                                            page_policies = retry_policies
                                            # 继续处理，不break
                                        else:
                                            # 会话轮换后仍然重复，记录连续重复计数
                                            consecutive_duplicate_count += 1
                                            logger.warning(f"会话轮换后，第 {page_index} 页仍然与上一页相同（连续重复 {consecutive_duplicate_count} 次）")
                                            
                                            if consecutive_duplicate_count >= max_consecutive_duplicates:
                                                logger.warning(f"连续 {consecutive_duplicate_count} 页重复，停止查询")
                                                break
                                            
                                            # 尝试跳过当前页继续下一页
                                            logger.info(f"尝试跳过第 {page_index} 页，继续下一页...")
                                            # 不添加当前页数据，直接跳过
                                            page_policies = []  # 设置为空，不添加到policies中
                                            # 不更新prev_page_policies，保持上一页的数据
                                            # 继续循环，尝试下一页
                                            page_index += 1
                                            continue  # 跳过后续处理，直接进入下一轮循环
                                    else:
                                        # 重试失败，尝试跳过当前页继续下一页
                                        consecutive_duplicate_count += 1
                                        logger.warning(f"会话轮换后重试失败，尝试跳过当前页继续下一页（连续重复 {consecutive_duplicate_count} 次）")
                                        if consecutive_duplicate_count >= max_consecutive_duplicates:
                                            logger.warning(f"连续 {consecutive_duplicate_count} 页重复，停止查询")
                                            break
                                        page_policies = []
                                        page_index += 1
                                        continue
                                except Exception as e:
                                    logger.warning(f"会话重新初始化失败: {e}")
                                    consecutive_duplicate_count += 1
                                    logger.info(f"尝试跳过当前页继续下一页（连续重复 {consecutive_duplicate_count} 次）")
                                    if consecutive_duplicate_count >= max_consecutive_duplicates:
                                        logger.warning(f"连续 {consecutive_duplicate_count} 页重复，停止查询")
                                        break
                                    page_policies = []
                                    page_index += 1
                                    continue
                            else:
                                # 会话轮换失败，尝试跳过当前页继续下一页
                                consecutive_duplicate_count += 1
                                logger.warning(f"会话轮换失败，尝试跳过当前页继续下一页（连续重复 {consecutive_duplicate_count} 次）")
                                if consecutive_duplicate_count >= max_consecutive_duplicates:
                                    logger.warning(f"连续 {consecutive_duplicate_count} 页重复，停止查询")
                                    break
                                page_policies = []
                                page_index += 1
                                continue
                    
                    # 只有在获取到有效数据时才添加到结果中
                    if page_policies:
                        policies.extend(page_policies)
                        empty_page_count = 0
                        consecutive_duplicate_count = 0  # 重置连续重复计数
                        logger.info(f"第 {page_index} 页获取到 {len(page_policies)} 条政策，累计 {len(policies)} 条")
                        
                        # 保存当前页数据作为下一页的上一页
                        prev_page_policies = page_policies.copy()
                    else:
                        # 如果没有获取到数据（可能是跳过的重复页），不更新prev_page_policies
                        empty_page_count += 1
                        logger.debug(f"第 {page_index} 页未获取到政策（可能是跳过的重复页）")
                else:
                    empty_page_count += 1
                    logger.debug(f"第 {page_index} 页未获取到政策")
                    # 空页时也保存，以便检测连续空页
                    prev_page_policies = []
                
                # 递增页码（如果使用了continue跳过重复页，page_index已经在continue之前递增了）
                page_index += 1
                
                # 速度限制
                if not disable_speed_limit:
                    delay = random.uniform(2.0, 5.0)
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"获取第 {page_index} 页失败: {e}", exc_info=True)
                empty_page_count += 1
                page_index += 1
                continue
        
        logger.info(f"分类 {category_name} (发布机关lvalue={issue_department_lvalue}) 获取完成，共获取 {len(policies)} 条政策")
        return policies

    def _crawl_category_year(self, category_name: str, category_code: str, year: Optional[int], expected_count: Optional[int],
                           callback=None, stop_callback=None, policy_callback=None, keywords=None, start_date=None, end_date=None, api_config=None, disable_speed_limit=False):
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
        max_pages = MAX_RECORDS_PER_BATCH // 20  # 接口页数上限
        empty_page_count = 0
        max_empty_pages = 5  # 连续空页数限制
        retrieved_count = 0
        target_year_str = str(year) if year else None

        if api_config is None:
            api_config = self._get_category_api_config(category_code)

        menu = api_config.get('menu', '')
        if menu in DUAL_REQUEST_MENUS and year:
            dual_expected_count = expected_count if isinstance(expected_count, int) and expected_count > 0 else MAX_RECORDS_PER_BATCH
            logger.info(f"分类 {category_name} ({category_code}) 使用双请求模式爬取 {year} 年 (预期 {dual_expected_count} 条)")
            return self._crawl_year_with_dual_request(
                category_code,
                year,
                dual_expected_count,
                api_config,
                keywords=keywords,
                start_date=start_date,
                end_date=end_date,
                disable_speed_limit=disable_speed_limit,
                policy_callback=policy_callback
            )

        # 设置当前API配置，用于_parse_policy_list_html方法
        self.current_api_config = api_config

        while page_index <= max_pages and empty_page_count < max_empty_pages:
            if stop_callback and stop_callback():
                logger.info("用户已停止爬取")
                break

            try:
                prev_page_index = page_index - 1 if page_index > 1 else None

                # 构建搜索参数（使用年份筛选，但优先使用发布机关筛选）
                # 注意：此方法已废弃，仅用于兼容性
                issue_department_lvalue = None
                if category_code:
                    issue_department_lvalue = self._get_issue_department_lvalue(category_code)
                
                search_params = self._get_search_parameters(
                    keywords=keywords,
                    category_code=category_code,
                    page_index=page_index,
                    page_size=20,
                    start_date=start_date,
                    end_date=end_date,
                    old_page_index=prev_page_index,
                    filter_year=year,  # 使用年份筛选（此方法已废弃）
                    api_config=api_config,
                    issue_department_lvalue=issue_department_lvalue  # 如果可用，优先使用发布机关筛选
                )

                resp = self._request_page_with_check(
                    page_index,
                    search_params,
                    prev_page_index,
                    api_config=api_config
                )

                if resp and resp.status_code == 200:
                    self.monitor.record_request(self.search_url, success=True)

                    # 解析页面政策
                    page_policies = self._parse_policy_list_html(
                        resp.text,
                        callback,
                        stop_callback,
                        category_name,
                        policy_callback
                    )

                    cross_year_detected = False
                    if target_year_str:
                        filtered_policies = []
                        for policy in page_policies:
                            pub_date = (policy.get("pub_date") or "").strip()
                            if pub_date and not pub_date.startswith(target_year_str):
                                cross_year_detected = True
                                logger.debug(
                                    "%s%s 检测到越界年份记录: %s -> %s",
                                    category_name,
                                    year_info,
                                    policy.get("title", ""),
                                    pub_date,
                                )
                                continue
                            filtered_policies.append(policy)
                            self._register_policy_success()

                        page_policies = filtered_policies

                    if page_policies:
                        policies.extend(page_policies)
                        empty_page_count = 0
                        retrieved_count += len(page_policies)

                        if callback:
                            callback(f"{category_name}{year_info} 第 {page_index} 页获取 {len(page_policies)} 条政策")

                        if expected_count and retrieved_count >= expected_count:
                            logger.info(
                                "%s%s 已达到预计数量 %s 条，提前停止翻页",
                                category_name,
                                year_info,
                                expected_count,
                            )
                            break

                        if cross_year_detected:
                            logger.info(
                                "%s%s 页面包含下一年度数据，已停止翻页",
                                category_name,
                                year_info,
                            )
                            break
                    else:
                        empty_page_count += 1
                        if empty_page_count >= max_empty_pages:
                            logger.info(f"{category_name}{year_info} 连续 {max_empty_pages} 页无数据，停止翻页")
                            break
                else:
                    error_msg = f"HTTP {resp.status_code}" if resp else "请求失败"
                    logger.warning(f"{category_name}{year_info} 第 {page_index} 页请求失败: {error_msg}")
                    empty_page_count += 1

            except Exception as e:
                logger.error(f"{category_name}{year_info} 第 {page_index} 页处理失败: {e}", exc_info=True)
                empty_page_count += 1

            page_index += 1

            # 添加延时避免过快
            self._sleep_between_requests(self.speed_mode, disable_speed_limit)

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
        
        # 刷新最新年份统计
        self._refresh_category_year_counts()
        
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
                logger.warning("时间格式错误，禁用时间过滤")
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
                category_name, category_code, callback, stop_callback, policy_callback,
                keywords=keywords,
                start_date=start_date,
                end_date=end_date,
                disable_speed_limit=disable_speed_limit
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
                        self._register_policy_success()
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
                    self._register_policy_success()
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
        
        logger.info("爬取完成统计:")
        logger.info(f"  总爬取数量: {total_crawled} 条")
        if keywords:
            logger.info(f"  关键词过滤: {keywords}")
        if enable_time_filter:
            logger.info(f"  时间过滤: {start_date} 至 {end_date}")
            logger.info(f"  过滤后数量: {total_filtered} 条")
        logger.info(f"  去重后数量: {total_saved} 条")
        
        if callback:
            callback("爬取完成统计:")
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
                logger.warning("时间格式错误，禁用时间过滤")
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
        
        # 设置速度模式 - 后续延迟统一由 _sleep_between_requests 控制
        self.speed_mode = speed_mode
        
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
                    if (self.enable_session_rotation and self.max_requests_per_session and
                            session_rotation_counter >= self.max_requests_per_session):
                        logger.debug(f"已请求 {session_rotation_counter} 次，尝试强制轮换会话...")
                        if self._maybe_rotate_session(force=True):
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
                                self._register_policy_success()
                        else:
                            # 不启用时间过滤，直接包含所有政策
                            filtered_policies.append(policy)
                            self._register_policy_success()
                    
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
                    
                    # 添加延时（根据配置）
                    self._sleep_between_requests(self.speed_mode, disable_speed_limit)
                        
                except requests.exceptions.Timeout as e:
                    logger.warning(f"请求超时: {e}", exc_info=True)
                    self.monitor.record_request(self.search_url, success=False, error_type="timeout")
                    if callback:
                        callback("请求超时，等待3秒后重试...")
                    time.sleep(3)
                    continue
                    
                except requests.exceptions.ConnectionError as e:
                    logger.error(f"连接错误: {e}", exc_info=True)
                    self.monitor.record_request(self.search_url, success=False, error_type="connection_error")
                    if callback:
                        callback("连接错误，等待3秒后重试...")
                    time.sleep(3)
                    continue
                    
                except requests.exceptions.HTTPError as e:
                    error_code = getattr(e.response, 'status_code', None)
                    logger.error(f"HTTP错误 {error_code}: {e}", exc_info=True)
                    self.monitor.record_request(self.search_url, success=False, error_type=f"http_{error_code}")
                    
                    # 如果是反爬虫相关错误，增加延时
                    if error_code in [403, 429]:
                        logger.warning("检测到反爬虫限制，等待5秒后重试...")
                        if callback:
                            callback("检测到访问限制，等待重试...")
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
                    logger.warning("未知错误，跳过当前页面")
                    if callback:
                        callback("页面处理出错，跳过继续...")
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
        
        logger.info("快速爬取完成统计:")
        logger.info(f"  总爬取数量: {total_crawled} 条")
        logger.info(f"  过滤后数量: {total_filtered} 条")
        logger.info(f"  最终保存数量: {total_saved} 条")
        logger.info(f"  去重率: {(len(all_policies) - len(unique_policies)) / len(all_policies) * 100:.1f}%" if all_policies else "0%")
        
        if callback:
            callback(f"快速爬取完成！共获取 {total_saved} 条政策")
        
        return unique_policies

    def _fetch_category_year_counts(self, category_code: str, api_config: Dict[str, str]) -> List[Tuple[int, int]]:
        """获取指定分类的年份分布数据"""
        try:
            adv_url = api_config.get("init_page", f"{self.base_url}/{api_config['menu']}/adv")
            headers = self.headers.copy()
            headers["Referer"] = adv_url

            resp, _ = self._session_get(
                adv_url,
                headers=headers,
                timeout=20,
            )
            if resp.status_code != 200:
                logger.warning(
                    "获取分类 %s 年份信息失败，HTTP %s",
                    category_code,
                    resp.status_code,
                )
                return []

            years = self.extract_years_from_page(resp.text)
            return years
        except Exception as exc:  # noqa: BLE001 - 捕获全部异常确保流程继续
            logger.warning(
                "获取分类 %s 年份信息异常: %s",
                category_code,
                exc,
                exc_info=True,
            )
            return []

    def _refresh_category_year_counts(self) -> None:
        """刷新所有分类的年份统计"""
        logger.info("正在刷新分类年份统计...")
        updated_counts: Dict[str, List[Tuple[int, int]]] = {}
        categories = self._get_flat_categories()

        for category_name, category_code in categories:
            api_config = self._get_category_api_config(category_code)
            year_counts = self._fetch_category_year_counts(category_code, api_config)
            if year_counts:
                updated_counts[category_code] = year_counts
                preview = ", ".join(f"{year}年({count}条)" for year, count in year_counts[:5])
                if len(year_counts) > 5:
                    preview += f" … 共{len(year_counts)}个年份"
                logger.info("分类[%s] 年份区间: %s", category_name, preview)
            else:
                logger.info("分类[%s] 未获取到有效年份信息", category_name)

            time.sleep(0.3)

        self.category_year_counts = updated_counts
        logger.info("年份统计刷新完成，共缓存 %s 个分类", len(updated_counts))

    def _load_category_configs(self):
        """加载分类API配置"""
        configs = {}
        for category_code, api_key in CATEGORY_API_MAP.items():
            api_meta = API_PATH_MAP.get(api_key)
            if not api_meta:
                logger.warning(f"未找到 {api_key} 的API元数据，跳过 {category_code}")
                continue

            menu = api_meta['menu']
            configs[category_code] = {
                'menu': menu,
                'library': api_meta['library'],
                'class_flag': api_meta['class_flag'],
                'init_page': f"{self.base_url}/{menu}/adv",
                'search_url': f"{self.base_url}/{menu}/search/RecordSearch",
                'class_search_url': f"{self.base_url}/{menu}/search/ClassSearch",
            }
        logger.info(f"加载了 {len(configs)} 个分类API配置（支持菜单: {sorted(DUAL_REQUEST_MENUS)}）")
        return configs

    def _crawl_year_with_dual_request(self, category_code, target_year, expected_count, api_config, keywords=None, start_date=None, end_date=None, disable_speed_limit=False, policy_callback=None):
        """使用双请求链路爬取指定年份政策（适用于 dfxfg 等菜单）"""
        logger.info(f"使用双请求模式爬取 {category_code} {target_year} 年政策，预期 {expected_count} 条")
        
        menu = api_config['menu']
        library = api_config['library']
        class_flag = api_config['class_flag']
        base_url = self.base_url
        page_size = api_config.get('page_size', 20)
        max_pages = expected_count // page_size + 1
        
        headers = self.headers.copy()
        headers['Referer'] = f"{base_url}/{menu}/"
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        headers['X-Requested-With'] = 'XMLHttpRequest'
        
        # Common params
        common_params = {
            'Menu': menu,
            'Keywords': keywords or '',
            'SearchKeywordType': 'Title',
            'MatchType': 'Exact',
            'RangeType': 'Piece',
            'Library': library,
            'ClassFlag': class_flag,
            'GroupLibraries': '',
            'IsAdv': 'False',
            'GroupByIndex': '0',
            'OrderByIndex': '0',
            'ShowType': 'Default',  # As in dfxfg
            'TitleKeywords': '',
            'FullTextKeywords': '',
            'QueryBase64Request': '',
            'VerifyCodeResult': '',
            'isEng': 'chinese',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        class_search_url = f"{base_url}/{menu}/search/ClassSearch"
        record_search_url = f"{base_url}/{menu}/search/RecordSearch"
        
        retrieved_count = 0
        page_index = 0
        all_policies = []
        cross_year_detected = False
        cross_year_total = 0
        
        # Initial ClassSearch to update context
        class_params = common_params.copy()
        class_params.update({
            'IsAdv': 'False',
            'ClassCodeKey': f",,,{target_year}",
        })
        try:
            resp_class, _ = self._session_post(
                class_search_url,
                data=class_params,
                headers=headers,
                timeout=20
            )
            if not resp_class or resp_class.status_code != 200:
                raise requests.RequestException(f"ClassSearch HTTP {resp_class.status_code if resp_class else 'No response'}")
            logger.debug(f"ClassSearch for {target_year} 成功")
        except Exception as e:
            logger.error(f"ClassSearch 失败: {e}")
            return []
        
        while page_index < max_pages and retrieved_count < expected_count and not cross_year_detected:
            record_params = common_params.copy()
            record_params.update({
                'QueryOnClick': 'False',
                'AfterSearch': 'False',
                'pdfStr': '',
                'pdfTitle': '',
                'IsAdv': 'False',
                'ClassCodeKey': f",,,{target_year}",
                'ShowType': 'Default',
                'GroupValue': '',
                'Pager.PageIndex': str(page_index),
                'Pager.PageSize': str(page_size),
                'OldPageIndex': str(page_index - 1) if page_index > 0 else '',
                'newPageIndex': str(page_index),
            })
            
            try:
                self.current_api_config = api_config
                resp = self._request_page_with_check(record_search_url, record_params, headers, api_config)
                if not resp or not resp.text:
                    break
                
                policies = self._parse_policy_list_html(resp.text, category_name=f"{category_code}_{target_year}", policy_callback=None)
                if not policies:
                    logger.info(f"{target_year} 年第 {page_index + 1} 页解析为空，停止")
                    break

                list_year_map = self._extract_years_from_list(resp.text)
                valid_policies = []
                for policy in policies:
                    policy_id = policy.get('policy_id')
                    pub_year = self._extract_year_from_text(policy.get('pub_date', ''))
                    list_year = list_year_map.get(policy_id)
                    final_year = list_year or pub_year

                    if final_year and final_year != str(target_year):
                        cross_year_detected = True
                        cross_year_total += 1
                        logger.warning(
                            "跨年数据已过滤: year=%s, target=%s, title=%s",
                            final_year,
                            target_year,
                            policy.get('title', '')[:50]
                        )
                        continue
                    valid_policies.append(policy)
                    self._register_policy_success()
                
                if not valid_policies:
                    logger.info(f"{target_year} 年第 {page_index + 1} 页全部被跨年过滤，提前结束")
                    break
                
                all_policies.extend(valid_policies)
                retrieved_count += len(valid_policies)
                
                if policy_callback:
                    for policy in valid_policies:
                        policy_callback(policy)
                
                page_index += 1
                
                if not disable_speed_limit:
                    time.sleep(self._get_delay())
                    
            except Exception as e:
                logger.error(f"第 {page_index + 1} 页请求失败: {e}")
                break
        
        if cross_year_detected:
            logger.warning(f"{target_year} 年批次检测到 {cross_year_total} 条跨年数据，已跳过处理")
        
        logger.info(f"双请求模式完成: {target_year} 年获取 {retrieved_count} 条政策")
        return all_policies

    @staticmethod
    def _extract_year_from_text(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        match = re.search(r'(19|20)\d{2}', text)
        return match.group(0) if match else None

    def _extract_years_from_list(self, html_content: str) -> Dict[str, Optional[str]]:
        mapping: Dict[str, Optional[str]] = {}
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            checkboxes = soup.select('input.checkbox[name="recordList"]')
            for checkbox in checkboxes:
                policy_id = checkbox.get('value', '').strip()
                if not policy_id:
                    continue

                related_info_text = ''
                block_node = checkbox.find_parent('div', class_='block')
                if not block_node:
                    block_node = checkbox.find_parent('li')
                if block_node:
                    related_div = block_node.find('div', class_='related-info')
                    if related_div:
                        related_info_text = related_div.get_text(" ", strip=True)

                year = self._extract_year_from_text(related_info_text)
                mapping[policy_id] = year
        except Exception as exc:
            logger.debug(f"从列表提取年份失败: {exc}")
        return mapping

    def _get_delay(self) -> float:
        """统一处理抓取间隔，若父类未实现则使用默认值。"""
        delay_min, delay_max = self._get_delay_range_for_speed(self.speed_mode)
        return random.uniform(delay_min, delay_max)
    
    def _register_policy_success(self) -> None:
        if self.rotate_after_success_count <= 0:
            return
        self._policy_success_counter += 1
        if self._policy_success_counter >= self.rotate_after_success_count:
            self._policy_success_counter = 0
            logger.info(
                "已成功获取 %s 条政策，按配置强制轮换会话/代理",
                self.rotate_after_success_count
            )
            self._maybe_rotate_session(force=True)

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
        # 统一刷新年份统计
        self._refresh_category_year_counts()
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

        category_name = task_data['category_name']
        description = task_data['description']
        
        thread_name = threading.current_thread().name
        
        if callback:
            callback(f"线程 {thread_name} 开始爬取 {description}")
        
        # 创建临时的爬虫实例来使用原有的爬取逻辑
        temp_spider = GuangdongSpider()
        temp_spider.headers = self.headers
        temp_spider.enable_proxy = self.enable_proxy
        temp_spider.category_year_counts = getattr(self, "category_year_counts", {}).copy()
        
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

            task_keywords = task_data.get('keywords')
            task_start_date = task_data.get('start_date')
            task_end_date = task_data.get('end_date')
            task_disable_speed = task_data.get('disable_speed_limit', False)

            # 使用年份分割策略
            category_policies = temp_spider._crawl_category_with_year_split(
                category_name,
                task_data.get('category_code', ''),
                callback,
                lambda: self.check_stop() if hasattr(self, 'check_stop') else False,
                policy_callback=task_data.get('policy_callback'),
                keywords=task_keywords,
                start_date=task_start_date,
                end_date=task_end_date,
                disable_speed_limit=task_disable_speed
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