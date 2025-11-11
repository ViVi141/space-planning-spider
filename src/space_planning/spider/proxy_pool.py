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
import re
from typing import Optional, Dict, List
from datetime import datetime

# Conditional import for kdl
try:
    from kdl.auth import Auth
    from kdl.client import Client
    KDL_AVAILABLE = True
except ImportError:
    Auth = None
    Client = None
    KDL_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("KDL 模块未安装，代理池功能禁用")

logger = logging.getLogger(__name__)


def is_valid_ip(ip: str) -> bool:
    """验证IP地址格式是否正确"""
    try:
        # 检查IP格式
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        
        for part in parts:
            if not part.isdigit():
                return False
            num = int(part)
            if num < 0 or num > 255:
                return False
        
        return True
    except:
        return False


def is_valid_port(port: str) -> bool:
    """验证端口格式是否正确"""
    try:
        port_num = int(port)
        return 1 <= port_num <= 65535
    except:
        return False


def is_valid_proxy_format(proxy_str: str) -> bool:
    """验证代理格式是否正确 (ip:port)"""
    try:
        if ':' not in proxy_str:
            return False
        
        ip, port = proxy_str.split(':', 1)
        return is_valid_ip(ip) and is_valid_port(port)
    except:
        return False


class ProxyInfo:
    """代理信息类"""
    def __init__(self, proxy_data):
        logger.debug(f"正在解析代理数据: {proxy_data}, 类型: {type(proxy_data)}")
        
        if isinstance(proxy_data, str):
            # 隧道代理返回字符串格式：ip:port 或其他格式
            if ':' in proxy_data:
                self.ip, self.port = proxy_data.split(':', 1)
                # 验证IP和端口格式
                if not is_valid_ip(self.ip):
                    raise ValueError(f"无效的IP地址格式: {self.ip}")
                if not is_valid_port(self.port):
                    raise ValueError(f"无效的端口格式: {self.port}")
            else:
                # 如果不是 ip:port 格式，检查是否为有效IP
                if is_valid_ip(proxy_data):
                    self.ip = proxy_data
                    self.port = '80'  # 使用默认端口
                else:
                    raise ValueError(f"无效的代理数据格式: {proxy_data}")
        elif isinstance(proxy_data, dict):
            # API代理返回字典格式
            self.ip = proxy_data.get('ip')
            self.port = proxy_data.get('port')
            
            # 验证IP和端口
            if not self.ip or not self.port:
                raise ValueError(f"代理数据缺少必要字段: {proxy_data}")
            
            if not is_valid_ip(self.ip):
                raise ValueError(f"无效的IP地址格式: {self.ip}")
            if not is_valid_port(self.port):
                raise ValueError(f"无效的端口格式: {self.port}")
        else:
            raise ValueError(f"不支持的代理数据格式: {type(proxy_data)}")
        
        # 构建代理字典
        proxy_str = f"{self.ip}:{self.port}"
        
        # 检查是否需要认证（从配置中读取）
        username = ''
        password = ''
        try:
            config_file = os.path.join(os.path.dirname(__file__), '..', 'gui', 'proxy_config.json')
            if os.path.exists(config_file):
                # 使用SecureConfig读取配置（自动解密）
                try:
                    from ..utils.crypto import SecureConfig
                    secure_config = SecureConfig(config_file)
                    config = secure_config.get_all_config()
                    username = config.get('username', '')
                    password = config.get('password', '')
                except Exception:
                    # 降级到直接读取
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    username = config.get('username', '')
                    password = config.get('password', '')
        except Exception as e:
            logger.debug(f"读取代理认证配置失败: {e}")
        
        if username and password:
            # 带认证的代理格式
            self.proxy_dict = {
                'http': f'http://{username}:{password}@{proxy_str}',
                'https': f'http://{username}:{password}@{proxy_str}'
            }
            logger.debug(f"ProxyInfo使用带认证的代理: {username}@{proxy_str}")
        else:
            # 无认证的代理格式
            self.proxy_dict = {
                'http': f'http://{proxy_str}',
                'https': f'http://{proxy_str}'
            }
            logger.debug(f"ProxyInfo使用无认证的代理: {proxy_str}")
        
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
    
    def mark_used(self, success: bool = True, response_time: float | None = None):
        """标记代理使用情况
        
        Args:
            success: 是否成功使用代理
            response_time: 响应时间(秒)
        """
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
        try:
            if not secret_id or not secret_key:
                logger.warning("代理配置缺少订单号或密钥，将禁用代理功能")
                self.client = None
            else:
                auth = Auth(self.secret_id, self.secret_key)
                self.client = Client(auth)
                logger.info("代理客户端初始化成功")
        except Exception as e:
            logger.error(f"代理客户端初始化失败: {e}")
            logger.error(f"请检查订单号: {secret_id[:8]}... 和密钥配置是否正确")
            self.client = None
        
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
        
        # 添加刷新时间控制
        self._last_refresh_time = 0
        self._refresh_failure_count = 0
        self._max_refresh_failures = 3
    
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
            
            # 检查上次刷新时间，避免过于频繁的请求
            current_time = time.time()
            if hasattr(self, '_last_refresh_time') and current_time - self._last_refresh_time < 300:  # 5分钟内不重复刷新
                logger.info("距离上次刷新时间过短，跳过刷新")
                return
            
            # 获取新代理
            try:
                if not self.client:
                    logger.error("代理客户端未初始化，无法获取代理")
                    logger.error("请检查代理配置中的订单号和密钥是否正确")
                    return
                
                if self.use_tunnel:
                    # 使用隧道代理
                    logger.info("正在获取隧道代理...")
                    new_proxies_data = self.client.get_tps(
                        num=self.max_proxies // 2,  # 只获取一半数量的新代理
                        username=self.username,
                        password=self.password
                    )
                else:
                    # 使用API代理
                    logger.info("正在获取API代理...")
                    new_proxies_data = self.client.get_dps(num=self.max_proxies // 2)
                
                # 记录刷新时间
                self._last_refresh_time = current_time
                
                logger.info(f"从代理API获取到 {len(new_proxies_data) if new_proxies_data else 0} 个代理数据")
                logger.debug(f"获取到的新代理数据: {new_proxies_data}")
                
            except Exception as api_error:
                # 处理API错误
                error_msg = str(api_error)
                error_type = type(api_error).__name__
                logger.error(f"代理API请求失败: {api_error}")
                logger.error(f"错误类型: {error_type}")
                
                # 检查是否是KdlStatusError并获取状态码
                status_code = None
                if hasattr(api_error, 'status_code'):
                    status_code = api_error.status_code
                    logger.debug(f"代理API返回状态码: {status_code}")
                elif hasattr(api_error, 'code'):
                    status_code = api_error.code
                    logger.debug(f"代理API返回错误码: {status_code}")
                
                # 处理400错误（请求格式错误）
                if status_code == 400 or "400" in error_msg or "Bad Request" in error_msg:
                    logger.warning("代理API返回400错误（请求格式错误）")
                    logger.info("可能原因：订单号或密钥格式不正确、API参数错误")
                    logger.info("解决方案：请检查代理设置中的订单API密钥（SecretId和SecretKey）是否正确")
                    
                    # 尝试使用内存中的缓存代理
                    cache_count = 0
                    if hasattr(self, 'proxies') and len(self.proxies) > 0:
                        cache_count = len(self.proxies)
                        logger.info(f"将使用内存中缓存的 {cache_count} 个代理继续工作")
                        return  # 使用缓存代理，不获取新代理
                    
                    # 尝试从本地缓存文件加载
                    try:
                        cached_proxies = self._load_proxy_cache()
                        if cached_proxies:
                            with self.lock:
                                self.proxies = cached_proxies
                            logger.info(f"从本地缓存文件加载了 {len(cached_proxies)} 个代理，将继续工作")
                            return
                    except Exception as cache_error:
                        logger.debug(f"尝试加载本地缓存失败: {cache_error}")
                    
                    # 如果都没有，提示用户
                    logger.warning("无可用缓存代理（内存和本地文件均无）")
                    logger.info("提示：GUI中的代理测试使用独立客户端，可能仍然可以成功获取代理")
                    logger.info("建议：检查代理配置中的SecretId和SecretKey是否正确，或等待代理池自动重试")
                    return
                # 处理请求频率限制
                elif "req over limit" in error_msg or "503" in error_msg or status_code == 503:
                    logger.warning("代理API请求频率限制，等待后重试...")
                    # 增加等待时间
                    if hasattr(self, '_last_refresh_time'):
                        self._last_refresh_time = current_time - 240  # 强制等待4分钟
                    time.sleep(60)  # 等待1分钟
                    return
                # 处理认证错误
                elif "401" in error_msg or "403" in error_msg or status_code in (401, 403):
                    logger.error("代理API认证失败，请检查订单号和密钥配置")
                    logger.info("请确认代理设置中的订单API密钥（SecretId和SecretKey）是否正确")
                    return
                # 处理超时错误
                elif "timeout" in error_msg.lower():
                    logger.error("代理API请求超时，请检查网络连接")
                    # 尝试使用内存中的缓存代理
                    if hasattr(self, 'proxies') and len(self.proxies) > 0:
                        logger.info(f"将使用内存中缓存的 {len(self.proxies)} 个代理继续工作")
                        return
                    # 尝试从本地缓存文件加载
                    try:
                        cached_proxies = self._load_proxy_cache()
                        if cached_proxies:
                            with self.lock:
                                self.proxies = cached_proxies
                            logger.info(f"从本地缓存文件加载了 {len(cached_proxies)} 个代理，将继续工作")
                            return
                    except Exception:
                        pass
                    return
                # 其他错误
                else:
                    logger.error(f"代理API请求失败: {api_error}")
                    # 尝试使用内存中的缓存代理
                    if hasattr(self, 'proxies') and len(self.proxies) > 0:
                        logger.info(f"将使用内存中缓存的 {len(self.proxies)} 个代理继续工作")
                        return
                    # 尝试从本地缓存文件加载
                    try:
                        cached_proxies = self._load_proxy_cache()
                        if cached_proxies:
                            with self.lock:
                                self.proxies = cached_proxies
                            logger.info(f"从本地缓存文件加载了 {len(cached_proxies)} 个代理，将继续工作")
                            return
                    except Exception:
                        pass
                    return
            
            # 确保new_proxies_data是列表格式
            if isinstance(new_proxies_data, str):
                # 如果API返回单个字符串，转换为列表
                new_proxies_data = [new_proxies_data]
            elif not isinstance(new_proxies_data, (list, tuple)):
                # 如果不是列表或元组，转换为列表
                new_proxies_data = [new_proxies_data] if new_proxies_data else []
            
            new_proxies = []
            invalid_count = 0
            
            for i, proxy_data in enumerate(new_proxies_data):
                try:
                    logger.debug(f"正在解析第 {i+1} 个代理数据: {proxy_data} (类型: {type(proxy_data)})")
                    
                    if isinstance(proxy_data, str):
                        # 处理多行字符串
                        for line in proxy_data.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            if not is_valid_proxy_format(line):
                                logger.warning(f"跳过无效代理格式: {line}")
                                invalid_count += 1
                                continue
                            proxy = ProxyInfo(line)
                            new_proxies.append(proxy)
                            logger.debug(f"成功解析代理: {proxy.ip}:{proxy.port}")
                        continue  # 跳过后续逻辑
                    elif isinstance(proxy_data, dict):
                        ip = proxy_data.get('ip')
                        port = proxy_data.get('port')
                        if not ip or not port or not is_valid_ip(ip) or not is_valid_port(port):
                            logger.warning(f"跳过无效代理数据: {proxy_data}")
                            invalid_count += 1
                            continue
                        proxy = ProxyInfo(proxy_data)
                        new_proxies.append(proxy)
                        logger.debug(f"成功解析代理: {proxy.ip}:{proxy.port}")
                    else:
                        logger.error(f"不支持的代理数据类型: {type(proxy_data)}, 数据: {proxy_data}")
                        invalid_count += 1
                except Exception as e:
                    logger.error(f"解析代理数据失败: {e}, 数据: {proxy_data}")
                    invalid_count += 1
            
            logger.info(f"代理解析完成: 成功 {len(new_proxies)} 个, 无效 {invalid_count} 个")
            
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
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
    
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
    
    def report_proxy_result(self, proxy: ProxyInfo, success: bool, response_time: Optional[float] = None):
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
        try:
            with self.lock:
                active_proxies = [p for p in self.proxies if not p.is_overused]
                proxy_details = []
                
                for p in self.proxies:
                    try:
                        # 安全计算平均响应时间
                        avg_response_time = None
                        if p.response_times and len(p.response_times) > 0:
                            avg_response_time = sum(p.response_times) / len(p.response_times)
                        
                        # 安全格式化最后使用时间
                        last_used = None
                        if p.last_used_at:
                            try:
                                last_used = p.last_used_at.strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                last_used = '未知'
                        
                        proxy_details.append({
                            'ip': p.ip,
                            'port': p.port,
                            'age_seconds': p.age_seconds,
                            'use_count': p.use_count,
                            'success_rate': p.success_rate,
                            'score': p.last_score,
                            'avg_response_time': avg_response_time,
                            'consecutive_failures': p.consecutive_failures,
                            'last_used': last_used
                        })
                    except Exception as e:
                        # 如果单个代理信息获取失败，跳过它
                        logger.warning(f"获取代理 {p.ip}:{p.port} 统计信息失败: {e}")
                        continue
                
                return {
                    'total_proxies': len(self.proxies),
                    'active_proxies': len(active_proxies),
                    'pool_size': len(self.proxies),  # 兼容性字段
                    'available_proxies': len(active_proxies),  # 兼容性字段
                    'running': self.running,
                    'check_interval': self.check_interval,
                    'last_refresh': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'proxy_details': proxy_details
                }
        except Exception as e:
            logger.error(f"获取代理统计信息失败: {e}")
            return {
                'total_proxies': 0,
                'active_proxies': 0,
                'pool_size': 0,
                'available_proxies': 0,
                'running': False,
                'check_interval': 0,
                'last_refresh': '获取失败',
                'proxy_details': []
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
    
    def is_initialized(self) -> bool:
        """检查代理池是否已初始化"""
        return self.proxy_pool is not None and self.proxy_pool.running
    
    def initialize(self, config_file: str) -> bool:
        """初始化代理池（支持加密配置）"""
        if config_file and os.path.exists(config_file):
            try:
                # 尝试使用SecureConfig读取（自动解密敏感信息）
                try:
                    from ..utils.crypto import SecureConfig
                    secure_config = SecureConfig(config_file)
                    config = secure_config.get_all_config()
                    logger.debug("ProxyManager: 使用SecureConfig读取配置（已自动解密敏感信息）")
                except Exception as secure_error:
                    # 如果SecureConfig不可用，降级到直接读取JSON
                    logger.debug(f"ProxyManager: SecureConfig不可用，使用直接读取: {secure_error}")
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    # 验证并解密敏感信息（如果看起来像加密值）
                    secret_id = config.get('secret_id', '')
                    secret_key = config.get('secret_key', '')
                    password = config.get('password', '')
                    
                    # 如果值看起来像加密的base64字符串，尝试解密
                    if secret_id and len(secret_id) > 30 and ('=' in secret_id or '/' in secret_id or '+' in secret_id):
                        try:
                            from ..utils.crypto import SecureConfig
                            secure_config = SecureConfig(config_file)
                            config['secret_id'] = secure_config.get_sensitive('secret_id', secret_id)
                            logger.debug("ProxyManager: 手动解密secret_id")
                        except Exception:
                            logger.warning("ProxyManager: 无法解密secret_id，可能导致API错误")
                    
                    if secret_key and len(secret_key) > 30 and ('=' in secret_key or '/' in secret_key or '+' in secret_key):
                        try:
                            if 'secure_config' not in locals():
                                from ..utils.crypto import SecureConfig
                                secure_config = SecureConfig(config_file)
                            config['secret_key'] = secure_config.get_sensitive('secret_key', secret_key)
                            logger.debug("ProxyManager: 手动解密secret_key")
                        except Exception:
                            logger.warning("ProxyManager: 无法解密secret_key，可能导致API错误")
                    
                    if password and len(password) > 30 and ('=' in password or '/' in password or '+' in password):
                        try:
                            if 'secure_config' not in locals():
                                from ..utils.crypto import SecureConfig
                                secure_config = SecureConfig(config_file)
                            config['password'] = secure_config.get_sensitive('password', password)
                            logger.debug("ProxyManager: 手动解密password")
                        except Exception:
                            pass  # password可能不是加密的
                    
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
                    return True
                else:
                    logger.info("代理功能已禁用")
                    return False
            except Exception as e:
                logger.error(f"初始化代理池失败: {e}", exc_info=True)
                return False
        else:
            logger.warning(f"代理配置文件不存在: {config_file}")
            return False
    
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
    
    def get_status(self) -> Dict:
        """获取代理状态（兼容EnhancedBaseCrawler）"""
        if self.proxy_pool:
            stats = self.proxy_pool.get_proxy_stats()
            current_proxy = self.proxy_pool.get_proxy()
            return {
                'enabled': True,
                'current_proxy': {
                    'ip': current_proxy.ip,
                    'port': current_proxy.port,
                    'use_count': current_proxy.use_count,
                    'success_rate': current_proxy.success_rate
                } if current_proxy else None,
                'pool_size': stats.get('pool_size', 0),
                'available_proxies': stats.get('available_proxies', 0)
            }
        else:
            return {
                'enabled': False,
                'current_proxy': None,
                'pool_size': 0,
                'available_proxies': 0
            }
    
    def report_result(self, proxy_info, success: bool, response_time: Optional[float] = None):
        """报告代理使用结果（兼容EnhancedBaseCrawler）"""
        if self.proxy_pool and proxy_info:
            self.proxy_pool.report_proxy_result(proxy_info, success, response_time)


# 全局代理管理器实例
_proxy_manager = ProxyManager()

# 全局代理状态管理
_global_proxy_enabled = True
_global_proxy_lock = threading.Lock()
_global_current_proxy = None
_global_proxy_fail_count = 0
_global_max_fail_count = 3  # 最大失败次数后切换代理


def initialize_proxy_pool(config_file: str):
    """初始化全局代理池"""
    if not KDL_AVAILABLE:
        logger.info("跳过代理池初始化（KDL 不可用）")
        return None
    _proxy_manager.initialize(config_file)


def get_proxy() -> Optional[Dict[str, str]]:
    """获取代理字典"""
    return _proxy_manager.get_proxy_dict()


def get_proxy_stats() -> Dict:
    """获取代理统计信息"""
    return _proxy_manager.get_stats()


def set_global_proxy_enabled(enabled: bool):
    """设置全局代理启用状态"""
    global _global_proxy_enabled
    with _global_proxy_lock:
        _global_proxy_enabled = enabled
        if not enabled:
            _global_current_proxy = None
            _global_proxy_fail_count = 0


def is_global_proxy_enabled() -> bool:
    """检查全局代理是否启用"""
    return _global_proxy_enabled


def get_shared_proxy() -> Optional[Dict[str, str]]:
    """获取共享代理 - 所有爬虫使用同一个代理直到失效（自动包含认证信息）"""
    global _global_current_proxy, _global_proxy_fail_count
    
    with _global_proxy_lock:
        if not _global_proxy_enabled:
            return None
        
        # 如果当前代理失败次数过多，切换新代理
        if _global_proxy_fail_count >= _global_max_fail_count:
            _global_current_proxy = None
            _global_proxy_fail_count = 0
        
        # 如果没有当前代理，获取新代理
        if _global_current_proxy is None:
            try:
                # 优先使用get_proxy_dict()，它已经包含了认证信息（如果配置了username和password）
                proxy_dict = _proxy_manager.get_proxy_dict()
                if proxy_dict and isinstance(proxy_dict, dict):
                    _global_current_proxy = proxy_dict.copy()
                    logger.debug(f"从get_proxy_dict获取代理（已包含认证）: {_global_current_proxy}")
                else:
                    # 降级：尝试get_proxy()获取ProxyInfo对象
                    proxy_info = _proxy_manager.get_proxy()
                    if proxy_info:
                        if hasattr(proxy_info, 'proxy_dict'):
                            # 如果ProxyInfo对象有proxy_dict属性（已包含认证），直接使用
                            _global_current_proxy = proxy_info.proxy_dict.copy() if isinstance(proxy_info.proxy_dict, dict) else None
                            logger.debug(f"从ProxyInfo.proxy_dict获取代理: {_global_current_proxy}")
                        elif hasattr(proxy_info, 'ip') and hasattr(proxy_info, 'port'):
                            # 手动构建代理字典（如果需要认证，从配置读取）
                            username = getattr(proxy_info, 'username', '')
                            password = getattr(proxy_info, 'password', '')
                            
                            if username and password:
                                # 带认证的代理格式
                                _global_current_proxy = {
                                    'http': f'http://{username}:{password}@{proxy_info.ip}:{proxy_info.port}',
                                    'https': f'http://{username}:{password}@{proxy_info.ip}:{proxy_info.port}'
                                }
                                logger.debug(f"使用带认证的共享代理: {username}@{proxy_info.ip}:{proxy_info.port}")
                            else:
                                # 无认证的代理格式
                                _global_current_proxy = {
                                    'http': f'http://{proxy_info.ip}:{proxy_info.port}',
                                    'https': f'http://{proxy_info.ip}:{proxy_info.port}'
                                }
                                logger.debug(f"使用无认证的共享代理: {proxy_info.ip}:{proxy_info.port}")
                        elif isinstance(proxy_info, dict):
                            # 已经是字典格式
                            if 'http' in proxy_info or 'https' in proxy_info:
                                # 已经是标准的requests代理格式，直接使用
                                _global_current_proxy = proxy_info.copy()
                            elif 'ip' in proxy_info and 'port' in proxy_info:
                                username = proxy_info.get('username', '')
                                password = proxy_info.get('password', '')
                                if username and password:
                                    _global_current_proxy = {
                                        'http': f'http://{username}:{password}@{proxy_info["ip"]}:{proxy_info["port"]}',
                                        'https': f'http://{username}:{password}@{proxy_info["ip"]}:{proxy_info["port"]}'
                                    }
                                else:
                                    _global_current_proxy = {
                                        'http': f'http://{proxy_info["ip"]}:{proxy_info["port"]}',
                                        'https': f'http://{proxy_info["ip"]}:{proxy_info["port"]}'
                                    }
                            else:
                                _global_current_proxy = None
                        else:
                            _global_current_proxy = None
                    else:
                        _global_current_proxy = None
            except Exception as e:
                logger.error(f"获取共享代理失败: {e}", exc_info=True)
                _global_current_proxy = None
        
        return _global_current_proxy


def report_shared_proxy_result(success: bool):
    """报告共享代理使用结果"""
    global _global_proxy_fail_count
    
    if not _global_proxy_enabled:
        return
    
    with _global_proxy_lock:
        if success:
            _global_proxy_fail_count = 0  # 成功时重置失败计数
        else:
            _global_proxy_fail_count += 1
            logger.warning(f"共享代理失败，失败次数: {_global_proxy_fail_count}/{_global_max_fail_count}")


def get_shared_proxy_status() -> Dict:
    """获取共享代理状态"""
    return {
        'enabled': _global_proxy_enabled,
        'current_proxy': _global_current_proxy,
        'fail_count': _global_proxy_fail_count,
        'max_fail_count': _global_max_fail_count
    } 