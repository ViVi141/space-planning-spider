#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
代理池模块 - 使用快代理官方SDK
提供代理IP的获取、验证、轮换和管理功能
"""

import os
import json
import time
import logging
import threading
from typing import Optional, Dict, List
from datetime import datetime
from kdl.auth import Auth
from kdl.client import Client
import random # Added for random.random()

logger = logging.getLogger(__name__)


class ProxyInfo:
    """代理信息类"""
    def __init__(self, proxy_data):
        logger.debug(f"正在解析代理数据: {proxy_data}, 类型: {type(proxy_data)}")
        
        if isinstance(proxy_data, str):
            # 隧道代理返回字符串格式：ip:port 或其他格式
            if ':' in proxy_data:
                self.ip, self.port = proxy_data.split(':')
            else:
                # 如果不是 ip:port 格式，可能是其他格式，直接使用
                self.ip = proxy_data
                self.port = '80'  # 使用默认端口
        elif isinstance(proxy_data, dict):
            # API代理返回字典格式
            self.ip = proxy_data.get('ip')
            self.port = proxy_data.get('port')
            if not self.ip or not self.port:
                raise ValueError(f"代理数据缺少必要字段: {proxy_data}")
        else:
            raise ValueError(f"不支持的代理数据格式: {type(proxy_data)}")
        
        # 构建代理字典
        proxy_str = f"{self.ip}:{self.port}"
        self.proxy_dict = {
            'http': f'http://{proxy_str}',
            'https': f'http://{proxy_str}'
        }
        
        # 添加代理状态跟踪
        self.created_at = datetime.now()  # 代理创建时间
        self.last_used_at = None  # 最后使用时间
        self.use_count = 0  # 使用次数
        self.success_count = 0  # 成功次数
        self.failure_count = 0  # 失败次数
        
        # 代理评分相关
        self.response_times = []  # 响应时间记录
        self.last_score = 100.0  # 初始评分100分
        self.consecutive_failures = 0  # 连续失败次数
        
        logger.debug(f"成功解析代理: {proxy_str}")
    
    def add_response_time(self, response_time: float):
        """记录响应时间"""
        self.response_times.append(response_time)
        if len(self.response_times) > 10:  # 只保留最近10次
            self.response_times.pop(0)
    
    def calculate_score(self) -> float:
        """计算代理质量评分"""
        score = 100.0
        
        # 1. 响应时间评分 (占比30分)
        if self.response_times:
            avg_response_time = sum(self.response_times) / len(self.response_times)
            if avg_response_time < 1:  # 1秒以内
                time_score = 30
            elif avg_response_time < 2:  # 1-2秒
                time_score = 25
            elif avg_response_time < 3:  # 2-3秒
                time_score = 20
            else:  # 3秒以上
                time_score = 15
            score -= (30 - time_score)
        
        # 2. 成功率评分 (占比40分)
        success_rate = self.success_rate
        score -= (1 - success_rate) * 40
        
        # 3. 连续失败惩罚 (每次失败-5分)
        score -= self.consecutive_failures * 5
        
        # 4. 使用频率评分 (占比30分)
        if self.use_count > 0:
            usage_score = 30 * (1 - (self.use_count / 100))  # 使用100次后分数为0
            score -= (30 - usage_score)
        
        self.last_score = max(0, min(100, score))  # 限制在0-100之间
        return self.last_score
    
    def mark_used(self, success: bool = True, response_time: float = None):
        """标记代理使用情况"""
        self.last_used_at = datetime.now()
        self.use_count += 1
        
        if success:
            self.success_count += 1
            self.consecutive_failures = 0
        else:
            self.failure_count += 1
            self.consecutive_failures += 1
        
        if response_time is not None:
            self.add_response_time(response_time)
    
    @property
    def success_rate(self) -> float:
        """获取成功率"""
        return self.success_count / self.use_count if self.use_count > 0 else 0.0
    
    @property
    def age_seconds(self) -> float:
        """获取代理年龄（秒）"""
        return (datetime.now() - self.created_at).total_seconds()
    
    @property
    def is_overused(self) -> bool:
        """检查代理是否过度使用"""
        return (self.use_count > 100 or 
                self.failure_count > 5 or 
                self.consecutive_failures >= 3 or  # 连续失败3次
                self.last_score < 30)  # 评分低于30分


class ProxyPool:
    """快代理代理池管理器"""
    
    def __init__(self, 
                 secret_id: str = "",
                 secret_key: str = "",
                 username: str = "",
                 password: str = "",
                 max_proxies: int = 5,
                 check_interval: int = 1800):  # 30分钟，减少刷新频率
        """
        初始化代理池
        
        Args:
            secret_id: 快代理订单号
            secret_key: 快代理密钥
            username: 代理隧道用户名（可选）
            password: 代理隧道密码（可选）
            max_proxies: 最大代理数量
            check_interval: 代理检查间隔(秒)
        """
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.username = username
        self.password = password
        self.max_proxies = max_proxies
        self.check_interval = check_interval
        
        # 初始化快代理客户端
        auth = Auth(self.secret_id, self.secret_key)
        self.client = Client(auth)
        
        self.proxies: List[ProxyInfo] = []
        self.lock = threading.Lock()
        self.running = False
        self.check_thread = None
        
        # 是否使用隧道代理
        self.use_tunnel = bool(self.username and self.password)
        
        # 代理轮换索引
        self.current_proxy_index = 0
        
        # 本地代理缓存文件
        self.cache_file = os.path.join(os.path.dirname(__file__), 'proxy_cache.json')
    
    def start(self):
        """启动代理池"""
        if not self.running:
            # 首先加载本地缓存
            cached_proxies = self._load_proxy_cache()
            if cached_proxies:
                with self.lock:
                    self.proxies = cached_proxies
                logger.info(f"从本地缓存加载了 {len(cached_proxies)} 个代理")
            
            self.running = True
            self.check_thread = threading.Thread(target=self._check_loop, daemon=True)
            self.check_thread.start()
            logger.info("代理池已启动")
    
    def stop(self):
        """停止代理池"""
        self.running = False
        if self.check_thread:
            self.check_thread.join()
        # 保存代理缓存
        self._save_proxy_cache()
        logger.info("代理池已停止")
    
    def _save_proxy_cache(self):
        """保存代理缓存到本地文件"""
        try:
            with self.lock:
                cache_data = []
                for proxy in self.proxies:
                    if not proxy.is_overused and proxy.last_score > 30:  # 只保存好代理
                        cache_data.append({
                            'ip': proxy.ip,
                            'port': proxy.port,
                            'created_at': proxy.created_at.isoformat(),
                            'last_used_at': proxy.last_used_at.isoformat() if proxy.last_used_at else None,
                            'use_count': proxy.use_count,
                            'success_count': proxy.success_count,
                            'failure_count': proxy.failure_count,
                            'response_times': proxy.response_times,
                            'last_score': proxy.last_score,
                            'consecutive_failures': proxy.consecutive_failures
                        })
                
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"已保存 {len(cache_data)} 个代理到本地缓存")
        except Exception as e:
            logger.error(f"保存代理缓存失败: {e}")
    
    def _load_proxy_cache(self):
        """从本地文件加载代理缓存"""
        try:
            if not os.path.exists(self.cache_file):
                return []
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            loaded_proxies = []
            for item in cache_data:
                try:
                    # 创建代理信息对象
                    proxy_data = f"{item['ip']}:{item['port']}"
                    proxy = ProxyInfo(proxy_data)
                    
                    # 恢复历史数据
                    proxy.created_at = datetime.fromisoformat(item['created_at'])
                    if item['last_used_at']:
                        proxy.last_used_at = datetime.fromisoformat(item['last_used_at'])
                    proxy.use_count = item['use_count']
                    proxy.success_count = item['success_count']
                    proxy.failure_count = item['failure_count']
                    proxy.response_times = item['response_times']
                    proxy.last_score = item['last_score']
                    proxy.consecutive_failures = item['consecutive_failures']
                    
                    # 检查代理是否仍然可用（年龄不超过1小时）
                    if proxy.age_seconds < 3600:  # 1小时
                        loaded_proxies.append(proxy)
                    
                except Exception as e:
                    logger.error(f"加载代理缓存项失败: {e}")
                    continue
            
            logger.info(f"从本地缓存加载了 {len(loaded_proxies)} 个代理")
            return loaded_proxies
            
        except Exception as e:
            logger.error(f"加载代理缓存失败: {e}")
            return []
    
    def _check_loop(self):
        """代理检查循环"""
        while self.running:
            try:
                self._refresh_proxies()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"代理检查循环出错: {e}")
                time.sleep(60)
    
    def _refresh_proxies(self):
        """刷新代理列表"""
        try:
            # 首先检查是否需要获取新代理
            with self.lock:
                # 如果当前代理数量足够且质量良好，不需要刷新
                good_proxies = [p for p in self.proxies if not p.is_overused and p.last_score > 50]
                if len(good_proxies) >= self.max_proxies // 2:  # 如果有一半以上的好代理，不刷新
                    logger.info(f"当前代理池状态良好，跳过刷新。好代理数量: {len(good_proxies)}")
                    return
            
            # 获取新代理
            if self.use_tunnel:
                # 使用隧道代理
                new_proxies_data = self.client.get_tps(
                    num=self.max_proxies // 2,  # 只获取一半数量的新代理
                    username=self.username,
                    password=self.password
                )
            else:
                # 使用API代理
                new_proxies_data = self.client.get_dps(num=self.max_proxies // 2)
            
            logger.debug(f"获取到的新代理数据: {new_proxies_data}")
            
            new_proxies = []
            for proxy_data in new_proxies_data:
                try:
                    if isinstance(proxy_data, (dict, str)):
                        proxy = ProxyInfo(proxy_data)
                        new_proxies.append(proxy)
                    else:
                        logger.error(f"不支持的代理数据类型: {type(proxy_data)}, 数据: {proxy_data}")
                except Exception as e:
                    logger.error(f"解析代理数据失败: {e}, 数据: {proxy_data}")
            
            with self.lock:
                # 保留现有的好代理
                existing_good_proxies = [p for p in self.proxies if not p.is_overused and p.last_score > 30]
                
                # 合并新旧代理，但限制总数
                all_proxies = existing_good_proxies + new_proxies
                if len(all_proxies) > self.max_proxies:
                    # 按评分排序，保留最好的代理
                    all_proxies.sort(key=lambda p: p.last_score, reverse=True)
                    self.proxies = all_proxies[:self.max_proxies]
                else:
                    self.proxies = all_proxies
                    
            logger.info(f"代理池更新完成，当前代理数量: {len(self.proxies)}，其中新代理: {len(new_proxies)}")
            
        except Exception as e:
            logger.error(f"刷新代理失败: {e}")
    
    def get_proxy(self) -> Optional[ProxyInfo]:
        """获取一个可用代理（智能选择策略）"""
        with self.lock:
            if not self.proxies:
                # 尝试从本地缓存加载
                cached_proxies = self._load_proxy_cache()
                if cached_proxies:
                    self.proxies = cached_proxies
                    logger.info(f"从本地缓存加载了 {len(cached_proxies)} 个代理")
                else:
                    # 如果本地缓存也没有，则获取新代理
                    self._refresh_proxies()
            
            if not self.proxies:
                return None
            
            # 移除过度使用的代理
            self.proxies = [p for p in self.proxies if not p.is_overused]
            
            if not self.proxies:
                # 如果所有代理都过度使用，尝试获取新代理
                self._refresh_proxies()
                if not self.proxies:
                    return None
            
            # 根据评分选择代理
            scored_proxies = [(p, p.calculate_score()) for p in self.proxies]
            scored_proxies.sort(key=lambda x: x[1], reverse=True)  # 按评分降序排序
            
            # 选择策略：优先使用本地保存的好代理
            if len(scored_proxies) > 0:
                # 80%概率选择最高分，20%概率随机选择其他代理
                if random.random() < 0.8:
                    proxy = scored_proxies[0][0]  # 选择最高分代理
                else:
                    # 随机选择其他代理（如果有的话）
                    other_proxies = scored_proxies[1:] if len(scored_proxies) > 1 else scored_proxies
                    proxy = random.choice(other_proxies)[0] if other_proxies else scored_proxies[0][0]
                
                # 更新使用时间
                proxy.mark_used()
                
                # 定期保存代理缓存（每10次使用保存一次）
                if proxy.use_count % 10 == 0:
                    self._save_proxy_cache()
                
                return proxy
            
            return None
    
    def report_proxy_result(self, proxy: ProxyInfo, success: bool, response_time: float = None):
        """报告代理使用结果"""
        if proxy:
            proxy.mark_used(success, response_time)
            
            # 如果代理评分过低或连续失败，触发刷新
            if proxy.last_score < 30 or proxy.consecutive_failures >= 3:
                self._refresh_proxies()
    
    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """获取代理字典格式"""
        proxy = self.get_proxy()
        return proxy.proxy_dict if proxy else None
    
    def get_proxy_stats(self) -> Dict:
        """获取代理统计信息"""
        with self.lock:
            active_proxies = [p for p in self.proxies if not p.is_overused]
            return {
                'total_proxies': len(self.proxies),
                'active_proxies': len(active_proxies),
                'running': self.running,
                'check_interval': self.check_interval,
                'last_refresh': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'proxy_details': [{
                    'ip': p.ip,
                    'port': p.port,
                    'age_seconds': p.age_seconds,
                    'use_count': p.use_count,
                    'success_rate': p.success_rate,
                    'score': p.last_score,
                    'avg_response_time': sum(p.response_times) / len(p.response_times) if p.response_times else None,
                    'consecutive_failures': p.consecutive_failures,
                    'last_used': p.last_used_at.strftime('%Y-%m-%d %H:%M:%S') if p.last_used_at else None
                } for p in self.proxies]
            }


class ProxyManager:
    """代理管理器 - 单例模式"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.proxy_pool = None
            self.initialized = True
    
    def initialize(self, config_file: str = None):
        """初始化代理池"""
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                if config.get('enabled', False):
                    self.proxy_pool = ProxyPool(
                        secret_id=config.get('secret_id', ''),
                        secret_key=config.get('secret_key', ''),
                        username=config.get('username', ''),
                        password=config.get('password', ''),
                        max_proxies=config.get('max_proxies', 5),
                        check_interval=config.get('check_interval', 300)
                    )
                    self.proxy_pool.start()
                    logger.info("代理池初始化成功")
            except Exception as e:
                logger.error(f"初始化代理池失败: {e}")
    
    def start(self):
        """启动代理池"""
        if self.proxy_pool:
            self.proxy_pool.start()
    
    def stop(self):
        """停止代理池"""
        if self.proxy_pool:
            self.proxy_pool.stop()
    
    def get_proxy(self) -> Optional[ProxyInfo]:
        """获取代理"""
        return self.proxy_pool.get_proxy() if self.proxy_pool else None
    
    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """获取代理字典"""
        return self.proxy_pool.get_proxy_dict() if self.proxy_pool else None
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.proxy_pool.get_proxy_stats() if self.proxy_pool else {
            'total_proxies': 0,
            'running': False,
            'check_interval': 0,
            'last_refresh': '-'
        }


# 全局代理管理器实例
_proxy_manager = ProxyManager()


def initialize_proxy_pool(config_file: str = None):
    """初始化全局代理池"""
    _proxy_manager.initialize(config_file)


def get_proxy() -> Optional[Dict[str, str]]:
    """获取代理字典"""
    return _proxy_manager.get_proxy_dict()


def get_proxy_stats() -> Dict:
    """获取代理统计信息"""
    return _proxy_manager.get_stats() 