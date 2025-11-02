#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理验证工具模块
用于验证代理是否真正被使用
"""

import logging
import requests
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ProxyVerifier:
    """代理验证器"""
    
    # 用于验证代理IP的服务列表
    IP_CHECK_SERVICES = [
        'http://httpbin.org/ip',
        'https://api.ipify.org?format=json',
        'http://icanhazip.com',
        'https://ifconfig.me',
    ]
    
    @staticmethod
    def get_real_ip(proxies: Optional[Dict] = None, timeout: int = 10) -> Optional[str]:
        """
        获取真实IP地址（用于验证代理是否生效）
        
        Args:
            proxies: 代理字典，格式如 {'http': 'http://ip:port', 'https': 'https://ip:port'}
            timeout: 超时时间（秒）
            
        Returns:
            返回IP地址字符串，如果失败返回None
        """
        for service_url in ProxyVerifier.IP_CHECK_SERVICES:
            try:
                resp = requests.get(service_url, proxies=proxies, timeout=timeout)
                if resp.status_code == 200:
                    # 解析响应内容
                    if 'ipify.org' in service_url:
                        # JSON格式: {"ip":"xxx.xxx.xxx.xxx"}
                        data = resp.json()
                        return data.get('ip')
                    elif 'httpbin.org' in service_url:
                        # JSON格式: {"origin":"xxx.xxx.xxx.xxx"}
                        data = resp.json()
                        return data.get('origin', '').split(',')[0].strip()
                    else:
                        # 纯文本格式: xxx.xxx.xxx.xxx
                        return resp.text.strip()
            except Exception as e:
                logger.debug(f"获取IP失败（服务: {service_url}）: {e}")
                continue
        
        return None
    
    @staticmethod
    def extract_proxy_ip(proxy_dict: Dict[str, str]) -> Optional[str]:
        """
        从代理字典中提取代理IP地址
        
        Args:
            proxy_dict: 代理字典，格式如 {'http': 'http://ip:port', 'https': 'https://ip:port'}
            
        Returns:
            返回代理IP地址，如果失败返回None
        """
        try:
            # 优先使用http代理
            proxy_url = proxy_dict.get('http') or proxy_dict.get('https')
            if not proxy_url:
                return None
            
            # 移除协议前缀
            if proxy_url.startswith('http://'):
                proxy_url = proxy_url[7:]
            elif proxy_url.startswith('https://'):
                proxy_url = proxy_url[8:]
            
            # 提取IP:PORT
            if ':' in proxy_url:
                ip, port = proxy_url.split(':', 1)
                return ip.strip()
            else:
                return proxy_url.strip()
        except Exception as e:
            logger.debug(f"提取代理IP失败: {e}")
            return None
    
    @staticmethod
    def verify_proxy_usage(proxy_dict: Optional[Dict[str, str]], 
                          timeout: int = 10) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        验证代理是否真正被使用
        
        Args:
            proxy_dict: 代理字典
            timeout: 超时时间（秒）
            
        Returns:
            (是否使用代理, 检测到的IP, 代理IP)
        """
        if not proxy_dict:
            return False, None, None
        
        # 提取代理IP
        proxy_ip = ProxyVerifier.extract_proxy_ip(proxy_dict)
        if not proxy_ip:
            logger.warning("无法从代理字典中提取代理IP")
            return False, None, None
        
        # 获取使用代理后的IP
        detected_ip = ProxyVerifier.get_real_ip(proxies=proxy_dict, timeout=timeout)
        if not detected_ip:
            logger.warning("无法检测IP地址（可能网络问题或所有服务都不可用）")
            return False, None, proxy_ip
        
        # 比较检测到的IP和代理IP
        # 注意：某些代理服务可能返回不同的IP（如使用了负载均衡）
        # 所以只要检测到IP和本地IP不同，就认为使用了代理
        is_using_proxy = (detected_ip != proxy_ip)
        
        # 如果没有代理，获取本地IP作为参考
        local_ip = ProxyVerifier.get_real_ip(proxies=None, timeout=timeout)
        
        if is_using_proxy:
            logger.info(f"[代理验证] ✓ 代理已生效 - 检测到IP: {detected_ip}, 代理IP: {proxy_ip}")
            if local_ip:
                logger.info(f"[代理验证]   本地IP: {local_ip}（参考）")
        else:
            if detected_ip == proxy_ip:
                logger.warning(f"[代理验证] ⚠ 检测到IP与代理IP相同，可能代理未生效")
            else:
                logger.info(f"[代理验证]   检测到IP: {detected_ip}, 代理IP: {proxy_ip}")
        
        return is_using_proxy, detected_ip, proxy_ip
    
    @staticmethod
    def test_proxy_connection(proxy_dict: Optional[Dict[str, str]], 
                            test_url: str = "http://httpbin.org/get",
                            timeout: int = 10) -> Tuple[bool, Optional[str]]:
        """
        测试代理连接是否正常
        
        Args:
            proxy_dict: 代理字典
            test_url: 测试URL
            timeout: 超时时间（秒）
            
        Returns:
            (是否成功, 错误信息)
        """
        if not proxy_dict:
            return False, "代理字典为空"
        
        try:
            resp = requests.get(test_url, proxies=proxy_dict, timeout=timeout)
            if resp.status_code == 200:
                logger.info(f"[代理验证] ✓ 代理连接测试成功 - URL: {test_url}")
                return True, None
            else:
                error_msg = f"HTTP状态码: {resp.status_code}"
                logger.warning(f"[代理验证] ⚠ 代理连接测试失败 - {error_msg}")
                return False, error_msg
        except requests.exceptions.Timeout:
            error_msg = "连接超时"
            logger.warning(f"[代理验证] ⚠ 代理连接测试失败 - {error_msg}")
            return False, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"连接错误: {str(e)}"
            logger.warning(f"[代理验证] ⚠ 代理连接测试失败 - {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            logger.warning(f"[代理验证] ⚠ 代理连接测试失败 - {error_msg}")
            return False, error_msg

