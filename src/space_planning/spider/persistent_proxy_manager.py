#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持久化代理管理器
实现单IP持续使用直到失效后再申请新IP的功能
"""

import os
import json
import time
import logging
import threading
import re
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
try:
    from kdl.auth import Auth
    from kdl.client import Client
    KDL_AVAILABLE = True
except ImportError:
    KDL_AVAILABLE = False
    Auth = None
    Client = None
import requests

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


class PersistentProxyInfo:
    """持久化代理信息类"""
    
    def __init__(self, proxy_data, proxy_type='api'):
        """
        初始化代理信息
        
        Args:
            proxy_data: 代理数据 (str或dict)
            proxy_type: 代理类型 ('api' 或 'tunnel')
        """
        self.proxy_type = proxy_type
        
        if isinstance(proxy_data, str):
            # 隧道代理格式：ip:port
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
                    self.port = '80'
                else:
                    raise ValueError(f"无效的代理数据格式: {proxy_data}")
        elif isinstance(proxy_data, dict):
            # API代理格式
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
        
        # 检查是否需要认证 - 从配置文件读取
        try:
            config_file = os.path.join(os.path.dirname(__file__), '..', 'gui', 'proxy_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                username = config.get('username', '')
                password = config.get('password', '')
            else:
                username = ''
                password = ''
        except Exception as e:
            logger.warning(f"读取代理配置文件失败: {e}")
            username = ''
            password = ''
        
        # 保存认证信息
        self.username = username
        self.password = password
        
        if username and password:
            # 带认证的代理格式
            self.proxy_dict = {
                'http': f'http://{username}:{password}@{proxy_str}',
                'https': f'http://{username}:{password}@{proxy_str}'
            }
            logger.info(f"使用带认证的代理: {username}@{proxy_str}")
        else:
            # 无认证的代理格式
            self.proxy_dict = {
                'http': f'http://{proxy_str}',
                'https': f'http://{proxy_str}'
            }
            logger.info(f"使用无认证的代理: {proxy_str}")
        
        # 代理状态跟踪
        self.created_at = datetime.now()
        self.first_used_at = None
        self.last_used_at = None
        self.last_success_at = None
        self.use_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.consecutive_failures = 0
        
        # 失效检测
        self.is_active = True
        self.failure_threshold = 3  # 连续失败3次认为失效
        self.max_age_hours = 24     # 最大使用时间24小时
        
        logger.info(f"创建持久化代理: {proxy_str}")
    
    def mark_used(self, success: bool = True, response_time: Optional[float] = None):
        """标记代理使用结果"""
        now = datetime.now()
        
        if self.first_used_at is None:
            self.first_used_at = now
        
        self.last_used_at = now
        self.use_count += 1
        
        if success:
            self.success_count += 1
            self.last_success_at = now
            self.consecutive_failures = 0
            logger.debug(f"代理 {self.ip}:{self.port} 使用成功 (总成功: {self.success_count})")
        else:
            self.failure_count += 1
            self.consecutive_failures += 1
            logger.warning(f"代理 {self.ip}:{self.port} 使用失败 (连续失败: {self.consecutive_failures})")
            
            # 检查是否需要标记为失效
            if self.consecutive_failures >= self.failure_threshold:
                self.is_active = False
                logger.error(f"代理 {self.ip}:{self.port} 连续失败{self.consecutive_failures}次，标记为失效")
    
    def is_expired(self) -> bool:
        """检查代理是否过期"""
        if not self.is_active:
            return True
        
        # 检查年龄
        age_hours = (datetime.now() - self.created_at).total_seconds() / 3600
        if age_hours > self.max_age_hours:
            logger.info(f"代理 {self.ip}:{self.port} 已使用{age_hours:.1f}小时，超过最大使用时间")
            return True
        
        return False
    
    @property
    def success_rate(self) -> float:
        """获取成功率"""
        return self.success_count / self.use_count if self.use_count > 0 else 0.0
    
    @property
    def age_hours(self) -> float:
        """获取代理年龄（小时）"""
        return (datetime.now() - self.created_at).total_seconds() / 3600
    
    def to_dict(self) -> Dict:
        """转换为字典格式（用于序列化）"""
        return {
            'ip': self.ip,
            'port': self.port,
            'proxy_type': self.proxy_type,
            'username': self.username,
            'password': self.password,
            'created_at': self.created_at.isoformat(),
            'first_used_at': self.first_used_at.isoformat() if self.first_used_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'last_success_at': self.last_success_at.isoformat() if self.last_success_at else None,
            'use_count': self.use_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'consecutive_failures': self.consecutive_failures,
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PersistentProxyInfo':
        """从字典创建代理信息对象"""
        proxy_data = f"{data['ip']}:{data['port']}"
        obj = cls(proxy_data, data.get('proxy_type', 'api'))
        
        # 恢复认证信息
        obj.username = data.get('username')
        obj.password = data.get('password')
        
        # 恢复状态
        obj.created_at = datetime.fromisoformat(data['created_at'])
        if data.get('first_used_at'):
            obj.first_used_at = datetime.fromisoformat(data['first_used_at'])
        if data.get('last_used_at'):
            obj.last_used_at = datetime.fromisoformat(data['last_used_at'])
        if data.get('last_success_at'):
            obj.last_success_at = datetime.fromisoformat(data['last_success_at'])
        
        obj.use_count = data['use_count']
        obj.success_count = data['success_count']
        obj.failure_count = data['failure_count']
        obj.consecutive_failures = data['consecutive_failures']
        obj.is_active = data['is_active']
        
        return obj

class PersistentProxyManager:
    """持久化代理管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化持久化代理管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config = self._load_config(config_file)
        self.current_proxy: Optional[PersistentProxyInfo] = None
        self.lock = threading.Lock()
        
        # 初始化快代理客户端
        if self.config.get('enabled', False) and KDL_AVAILABLE and Auth and Client:
            auth = Auth(self.config['secret_id'], self.config['secret_key'])
            self.client = Client(auth)
        else:
            self.client = None
        
        # 状态文件
        self.state_file = os.path.join(
            os.path.dirname(__file__), 
            'persistent_proxy_state.json'
        )
        
        # 加载上次的代理状态
        self._load_state()
        
        logger.info("持久化代理管理器初始化完成")
    
    def _load_config(self, config_file: Optional[str] = None) -> Dict:
        """加载配置文件"""
        if config_file is None:
            config_file = os.path.join(
                os.path.dirname(__file__), '..', 'gui', 'proxy_config.json'
            )
        
        default_config = {
            'enabled': False,
            'secret_id': '',
            'secret_key': '',
            'username': '',
            'password': '',
            'use_tunnel': False
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并配置
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                logger.error(f"加载代理配置失败: {e}")
        
        return default_config
    
    def _load_state(self):
        """加载上次的代理状态"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                
                if state_data.get('current_proxy'):
                    proxy_data = state_data['current_proxy']
                    self.current_proxy = PersistentProxyInfo.from_dict(proxy_data)
                    
                    # 检查代理是否仍然有效
                    if self.current_proxy.is_expired():
                        logger.info(f"上次保存的代理已过期: {self.current_proxy.ip}:{self.current_proxy.port}")
                        self.current_proxy = None
                    else:
                        logger.info(f"恢复上次使用的代理: {self.current_proxy.ip}:{self.current_proxy.port}")
        except Exception as e:
            logger.error(f"加载代理状态失败: {e}")
    
    def _save_state(self):
        """保存当前代理状态"""
        try:
            state_data = {
                'current_proxy': self.current_proxy.to_dict() if self.current_proxy else None,
                'last_update': datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存代理状态失败: {e}")
    
    def _get_new_proxy(self) -> Optional[PersistentProxyInfo]:
        """获取新的代理"""
        if not self.client:
            logger.error("代理客户端未初始化")
            return None
        
        try:
            if self.config.get('use_tunnel', False):
                # 使用隧道代理
                proxy_data = self.client.get_tps(
                    num=1,
                    username=self.config['username'],
                    password=self.config['password']
                )
                if proxy_data:
                    # 处理返回的数据格式
                    if isinstance(proxy_data, list) and len(proxy_data) > 0:
                        proxy_info = PersistentProxyInfo(proxy_data[0], 'tunnel')
                        # 设置认证信息
                        proxy_info.username = self.config.get('username', '')
                        proxy_info.password = self.config.get('password', '')
                        return proxy_info
                    elif isinstance(proxy_data, str):
                        proxy_info = PersistentProxyInfo(proxy_data, 'tunnel')
                        # 设置认证信息
                        proxy_info.username = self.config.get('username', '')
                        proxy_info.password = self.config.get('password', '')
                        return proxy_info
            else:
                # 使用API代理
                proxy_data = self.client.get_dps(num=1)
                if proxy_data:
                    # 处理返回的数据格式
                    if isinstance(proxy_data, list) and len(proxy_data) > 0:
                        proxy_info = PersistentProxyInfo(proxy_data[0], 'api')
                        # 设置认证信息
                        proxy_info.username = self.config.get('username', '')
                        proxy_info.password = self.config.get('password', '')
                        return proxy_info
                    elif isinstance(proxy_data, str):
                        proxy_info = PersistentProxyInfo(proxy_data, 'api')
                        # 设置认证信息
                        proxy_info.username = self.config.get('username', '')
                        proxy_info.password = self.config.get('password', '')
                        return proxy_info
            
            return None
            
        except Exception as e:
            logger.error(f"获取新代理失败: {e}")
            return None
    
    def get_proxy(self) -> Optional[Dict[str, str]]:
        """获取当前可用的代理"""
        with self.lock:
            # 如果没有启用代理，返回None
            if not self.config.get('enabled', False):
                return None
            
            # 检查当前代理是否有效
            if self.current_proxy and not self.current_proxy.is_expired():
                # 检查代理类型是否与配置匹配
                expected_type = 'tunnel' if self.config.get('use_tunnel', False) else 'api'
                if self.current_proxy.proxy_type != expected_type:
                    logger.info(f"代理类型不匹配，当前: {self.current_proxy.proxy_type}, 期望: {expected_type}，强制刷新")
                    self.current_proxy.is_active = False
                    self.current_proxy = None
                else:
                    return self.current_proxy.proxy_dict
            
            # 当前代理失效，获取新代理
            if self.current_proxy:
                logger.info(f"当前代理失效，获取新代理。失效原因: 连续失败{self.current_proxy.consecutive_failures}次")
            
            new_proxy = self._get_new_proxy()
            if new_proxy:
                self.current_proxy = new_proxy
                self._save_state()
                logger.info(f"获取到新代理: {new_proxy.ip}:{new_proxy.port} (类型: {new_proxy.proxy_type})")
                return new_proxy.proxy_dict
            else:
                logger.error("无法获取新代理")
                return None
    
    def report_result(self, success: bool, response_time: Optional[float] = None):
        """报告代理使用结果"""
        with self.lock:
            if self.current_proxy:
                self.current_proxy.mark_used(success, response_time)
                self._save_state()
                
                if not success:
                    logger.warning(f"代理使用失败: {self.current_proxy.ip}:{self.current_proxy.port} "
                                 f"(连续失败: {self.current_proxy.consecutive_failures}次)")
    
    def force_refresh(self):
        """强制刷新代理"""
        with self.lock:
            if self.current_proxy:
                logger.info(f"强制刷新代理: {self.current_proxy.ip}:{self.current_proxy.port}")
                self.current_proxy.is_active = False
            
            new_proxy = self._get_new_proxy()
            if new_proxy:
                self.current_proxy = new_proxy
                self._save_state()
                logger.info(f"强制刷新后获取新代理: {new_proxy.ip}:{new_proxy.port}")
    
    def clear_proxy(self):
        """清空当前代理"""
        try:
            # 使用超时机制获取锁
            if self.lock.acquire(timeout=2.0):  # 最多等待2秒
                try:
                    if self.current_proxy:
                        logger.info(f"清空当前代理: {self.current_proxy.ip}:{self.current_proxy.port}")
                        self.current_proxy = None
                        self._save_state()
                        logger.info("代理已清空")
                    else:
                        logger.info("当前没有活跃代理")
                finally:
                    self.lock.release()
            else:
                logger.warning("获取代理锁超时，跳过清空操作")
        except Exception as e:
            logger.error(f"清空代理时出错: {e}")
            # 确保锁被释放
            try:
                if self.lock.locked():
                    self.lock.release()
            except Exception as lock_error:
                logger.error(f"释放锁时出错: {lock_error}")
    
    def reset_proxy_state(self):
        """重置代理状态（清空代理并删除状态文件）"""
        with self.lock:
            # 清空当前代理
            if self.current_proxy:
                logger.info(f"清空当前代理: {self.current_proxy.ip}:{self.current_proxy.port}")
                self.current_proxy = None
            
            # 删除状态文件
            try:
                if os.path.exists(self.state_file):
                    os.remove(self.state_file)
                    logger.info(f"已删除代理状态文件: {self.state_file}")
                else:
                    logger.info("代理状态文件不存在")
            except Exception as e:
                logger.error(f"删除代理状态文件失败: {e}")
            
            logger.info("代理状态已重置")
    
    def get_status(self) -> Dict:
        """获取代理状态信息"""
        with self.lock:
            # 检查代理是否启用
            proxy_enabled = self.config.get('enabled', False)
            
            if not proxy_enabled:
                return {
                    'enabled': False,
                    'current_proxy': None,
                    'status': 'disabled'
                }
            
            if not self.current_proxy:
                return {
                    'enabled': True,
                    'current_proxy': None,
                    'status': 'no_proxy'
                }
            
            return {
                'enabled': True,
                'current_proxy': {
                    'ip': self.current_proxy.ip,
                    'port': self.current_proxy.port,
                    'type': self.current_proxy.proxy_type,
                    'age_hours': self.current_proxy.age_hours,
                    'use_count': self.current_proxy.use_count,
                    'success_count': self.current_proxy.success_count,
                    'failure_count': self.current_proxy.failure_count,
                    'success_rate': self.current_proxy.success_rate,
                    'consecutive_failures': self.current_proxy.consecutive_failures,
                    'is_active': self.current_proxy.is_active,
                    'last_used_at': self.current_proxy.last_used_at.strftime('%Y-%m-%d %H:%M:%S') if self.current_proxy.last_used_at else None
                },
                'status': 'active' if self.current_proxy.is_active else 'inactive'
            }

# 全局单例实例
persistent_proxy_manager = PersistentProxyManager() 