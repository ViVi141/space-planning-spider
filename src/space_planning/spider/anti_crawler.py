"""
防反爬虫工具模块
"""

import logging
import random
import time
from collections import deque
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urlparse

import certifi
import requests
import threading

from .advanced_anti_detection import advanced_anti_detection, cookie_manager
from .config import crawler_config


logger = logging.getLogger(__name__)


class AntiCrawlerManager:
    """防反爬虫统一管理器，所有爬虫共享相同的运行时配置"""

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = certifi.where()
        self.lock = threading.Lock()

        # 运行时状态
        self.speed_mode = "正常速度"
        self.disable_speed_limit = False
        self.request_history = []
        self.ip_blacklist = set()

        # 统计
        self._request_timestamps = deque()
        self._session_started_at = time.time()
        self._requests_since_rotation = 0

        # 初始化配置/代理/头部
        self._load_runtime_settings()
        self._init_proxy()
        self._apply_dynamic_headers()

    # ------------------------------------------------------------------ #
    # 配置加载与刷新
    # ------------------------------------------------------------------ #
    def _load_runtime_settings(self) -> None:
        """从全局配置加载防反爬参数"""
        cfg = crawler_config

        delay_cfg = cfg.get_config('request_delay') or {}
        try:
            self.min_delay = max(0.0, float(delay_cfg.get('min', 1.0) or 0.0))
        except (TypeError, ValueError):
            self.min_delay = 1.0
        try:
            self.max_delay = float(delay_cfg.get('max', 3.0) or 3.0)
        except (TypeError, ValueError):
            self.max_delay = max(self.min_delay, 3.0)
        if self.max_delay < self.min_delay:
            self.max_delay = self.min_delay

        retry_cfg = cfg.get_config('retry_settings') or {}
        try:
            self.max_retries = max(0, int(retry_cfg.get('max_retries', 3) or 0))
        except (TypeError, ValueError):
            self.max_retries = 3
        try:
            self.retry_delay = max(0.1, float(retry_cfg.get('retry_delay', 2) or 1))
        except (TypeError, ValueError):
            self.retry_delay = 2.0

        session_cfg = cfg.get_config('session_settings') or {}
        self.enable_session_rotation = bool(session_cfg.get('enable_rotation', True))
        self.enable_cookie_management = bool(session_cfg.get('enable_cookie_management', True))
        try:
            self.session_rotation_interval = max(0, int(session_cfg.get('rotation_interval', 300) or 0))
        except (TypeError, ValueError):
            self.session_rotation_interval = 300
        try:
            self.max_requests_per_session = max(0, int(session_cfg.get('max_requests_per_session', 50) or 0))
        except (TypeError, ValueError):
            self.max_requests_per_session = 50

        header_cfg = cfg.get_config('headers_settings') or {}
        self.randomize_user_agent = bool(header_cfg.get('randomize_user_agent', True))
        self.add_referer_header = bool(header_cfg.get('add_referer', True))
        self.add_fingerprint_header = bool(header_cfg.get('add_fingerprint', False))

        behavior_cfg = cfg.get_config('behavior_settings') or {}
        self.simulate_human_behavior = bool(behavior_cfg.get('simulate_human_behavior', True))
        self.random_delay_enabled = bool(behavior_cfg.get('random_delay', True))
        try:
            intensity = int(behavior_cfg.get('intensity', 5))
        except (TypeError, ValueError):
            intensity = 5
        self.behavior_intensity = max(1, min(intensity, 10))

        rate_cfg = cfg.get_config('rate_limit_settings') or {}
        self.rate_limit_enabled = bool(rate_cfg.get('enabled', False))
        try:
            rpm = int(rate_cfg.get('max_requests_per_minute', 60))
        except (TypeError, ValueError):
            rpm = 60
        self.requests_per_minute = max(1, rpm)

        try:
            self.request_timeout = int(cfg.get_config('request_timeout') or 30)
        except (TypeError, ValueError):
            self.request_timeout = 30

    def refresh_settings(self) -> None:
        """刷新配置（供外部调用）"""
        self._load_runtime_settings()

    def configure_speed_mode(self, speed_mode: str = "正常速度", disable_speed_limit: bool = False) -> None:
        """设置速度模式（快速/正常/慢速）"""
        self.speed_mode = speed_mode or "正常速度"
        self.disable_speed_limit = bool(disable_speed_limit)
        self._load_runtime_settings()

    # ------------------------------------------------------------------ #
    # 代理与会话管理
    # ------------------------------------------------------------------ #
    def _init_proxy(self) -> None:
        """初始化代理信息"""
        try:
            from .proxy_pool import get_shared_proxy, is_global_proxy_enabled
            if is_global_proxy_enabled():
                proxy_dict = get_shared_proxy()
                if proxy_dict:
                    self.session.proxies.update(proxy_dict)
                    logger.info("AntiCrawlerManager: 已应用代理 %s", proxy_dict)
        except Exception as exc:  # noqa: BLE001
            logger.warning("AntiCrawlerManager: 初始化代理失败: %s", exc, exc_info=True)

    def refresh_proxy(self) -> None:
        """外部调用以手动刷新代理"""
        self._init_proxy()

    def _reset_session_counters(self) -> None:
        self._session_started_at = time.time()
        self._requests_since_rotation = 0

    def _apply_dynamic_headers(self) -> None:
        base_headers = self._prepare_headers({}, None)
        self.session.headers.clear()
        self.session.headers.update(base_headers)

    def _rotate_session(self) -> None:
        """创建新的 Session 并保留必要的上下文"""
        previous_proxies = self.session.proxies.copy()
        new_session = requests.Session()
        new_session.verify = certifi.where()
        if previous_proxies:
            new_session.proxies.update(previous_proxies)
        self.session = new_session
        self._reset_session_counters()
        if self.enable_cookie_management:
            cookie_manager.clear_cookies()
            self.session.cookies.clear()
        self._apply_dynamic_headers()
        self._init_proxy()

    def _maybe_rotate_session(self, force: bool = False) -> bool:
        if not self.enable_session_rotation:
            return False
        need_rotate = force
        now = time.time()
        if self.session_rotation_interval and now - self._session_started_at >= self.session_rotation_interval:
            need_rotate = True
        if self.max_requests_per_session and self._requests_since_rotation >= self.max_requests_per_session:
            need_rotate = True
        if not need_rotate:
            return False
        self._rotate_session()
        return True

    # ------------------------------------------------------------------ #
    # 请求节奏控制
    # ------------------------------------------------------------------ #
    def _get_delay_range_for_speed(self) -> Dict[str, float]:
        factor = 1.0
        if self.speed_mode == "快速模式":
            factor = 0.5
        elif self.speed_mode == "慢速模式":
            factor = 2.0
        delay_min = max(0.0, self.min_delay * factor)
        delay_max = max(delay_min, self.max_delay * factor)
        return {'min': delay_min, 'max': delay_max}

    def _sleep_between_requests(self) -> None:
        if self.disable_speed_limit or not self.random_delay_enabled:
            return
        delay_range = self._get_delay_range_for_speed()
        delay = random.uniform(delay_range['min'], delay_range['max'])
        jitter = random.uniform(-0.1, 0.1) * (self.behavior_intensity / 10)
        delay *= (1 + jitter)
        if delay > 0:
            time.sleep(delay)

    def sleep_between_requests(self, disable_speed_limit: bool = False) -> None:
        """外部调用延迟控制（例如多线程任务中）"""
        if disable_speed_limit:
            return
        self._sleep_between_requests()

    def _apply_rate_limit(self) -> None:
        if self.disable_speed_limit or not self.rate_limit_enabled:
            return
        now = time.time()
        window = 60.0
        while self._request_timestamps and now - self._request_timestamps[0] > window:
            self._request_timestamps.popleft()
        if len(self._request_timestamps) >= self.requests_per_minute:
            sleep_time = window - (now - self._request_timestamps[0]) + 0.01
            if sleep_time > 0:
                time.sleep(min(sleep_time, self.max_delay))

    # ------------------------------------------------------------------ #
    # 请求头与行为模拟
    # ------------------------------------------------------------------ #
    def _prepare_headers(self, headers: Optional[Dict], url: Optional[str]) -> Dict:
        prepared: Dict[str, str] = {}
        if headers:
            prepared.update(headers)

        referer = prepared.get('Referer')
        if not referer and url:
            parsed = urlparse(url)
            if parsed.scheme and parsed.netloc:
                referer = f"{parsed.scheme}://{parsed.netloc}/"

        random_headers = None
        if self.randomize_user_agent or self.add_fingerprint_header:
            try:
                random_headers = advanced_anti_detection.get_random_headers(referer=referer)
            except Exception:  # noqa: BLE001
                random_headers = None

        if self.randomize_user_agent:
            if random_headers and random_headers.get('User-Agent'):
                prepared['User-Agent'] = random_headers['User-Agent']
            else:
                prepared.setdefault(
                    'User-Agent',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )

        if self.add_referer_header and referer:
            prepared['Referer'] = referer

        if self.add_fingerprint_header and random_headers and random_headers.get('X-Client-Data'):
            prepared['X-Client-Data'] = random_headers['X-Client-Data']

        if random_headers:
            for key, value in random_headers.items():
                prepared.setdefault(key, value)

        return prepared

    def _simulate_behavior(self) -> None:
        if not self.simulate_human_behavior:
            return
        rounds = max(1, self.behavior_intensity // 4)
        for _ in range(rounds):
            try:
                advanced_anti_detection.simulate_human_behavior()
            except Exception:  # noqa: BLE001
                break

    # ------------------------------------------------------------------ #
    # 请求执行
    # ------------------------------------------------------------------ #
    def make_request(self, url: str, method: str = 'GET', **kwargs) -> requests.Response:
        """发送请求，应用统一的防反爬策略"""
        self._load_runtime_settings()

        original_headers = kwargs.pop('headers', None)
        timeout = kwargs.pop('timeout', self.request_timeout)
        request_kwargs = kwargs.copy()
        request_kwargs['headers'] = self._prepare_headers(original_headers, url)
        request_kwargs['timeout'] = timeout
        request_kwargs.setdefault('allow_redirects', True)
        request_kwargs.setdefault('stream', False)

        self._apply_rate_limit()
        self._sleep_between_requests()
        self._simulate_behavior()
        self._maybe_rotate_session()

        last_exception: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            start_time = time.time()
            try:
                response = self.session.request(method, url, **request_kwargs)
                elapsed = time.time() - start_time
                self._record_request_history(url, method, response.status_code, elapsed)
                self._requests_since_rotation += 1
                self._request_timestamps.append(time.time())
                self._report_proxy_result(True)

                if response.status_code >= 400:
                    if response.status_code in {403, 429, 500, 502, 503, 504}:
                        raise requests.exceptions.HTTPError(response=response)
                    response.raise_for_status()
                return response

            except Exception as exc:  # noqa: BLE001
                elapsed = time.time() - start_time
                self._record_request_history(url, method, None, elapsed, error=str(exc))
                self._requests_since_rotation += 1
                self._request_timestamps.append(time.time())
                self._report_proxy_result(False)
                last_exception = exc

                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise last_exception

        raise RuntimeError(f"请求失败: {url}")  # 理论不可达

    # ------------------------------------------------------------------ #
    # 工具方法
    # ------------------------------------------------------------------ #
    def _record_request_history(
        self,
        url: str,
        method: str,
        status_code: Optional[int],
        response_time: float,
        error: Optional[str] = None
    ) -> None:
        record = {
            'url': url,
            'method': method,
            'status_code': status_code,
            'response_time': round(response_time, 3),
            'error': error,
            'timestamp': datetime.utcnow().isoformat()
        }
        with self.lock:
            self.request_history.append(record)
            if len(self.request_history) > 10000:
                self.request_history = self.request_history[-5000:]

    def _report_proxy_result(self, success: bool) -> None:
        try:
            from .proxy_pool import report_shared_proxy_result
            report_shared_proxy_result(success)
        except Exception:  # noqa: BLE001
            pass

    def get_random_headers(self, url: Optional[str] = None) -> Dict:
        """向后兼容的 API，返回配置驱动的伪装请求头"""
        return self._prepare_headers({}, url)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-