#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫配置模块
支持不同防检测模式的选择
"""

from enum import Enum
from typing import Dict, Any, Optional
import json
import os
import logging

logger = logging.getLogger(__name__)

class AntiDetectionMode(Enum):
    """防检测模式"""
    NORMAL = "normal"      # 正常模式：基础防检测
    ENHANCED = "enhanced"  # 增强模式：高级防检测

class CrawlerConfig:
    """爬虫配置管理器"""
    
    def __init__(self):
        # 默认配置
        self.default_config = {
            'anti_detection_mode': AntiDetectionMode.NORMAL.value,
            'use_proxy': False,  # 默认不使用代理
            'request_delay': {
                'min': 1.0,
                'max': 3.0
            },
            'retry_settings': {
                'max_retries': 3,
                'retry_delay': 2
            },
            'session_settings': {
                'rotation_interval': 300,  # 5分钟
                'max_requests_per_session': 50
            },
            'headers_settings': {
                'randomize_user_agent': True,
                'add_referer': True,
                'add_fingerprint': False  # 正常模式默认关闭
            },
            'behavior_settings': {
                'simulate_human_behavior': True,
                'random_delay': True,
                'mouse_movement': False,  # 正常模式默认关闭
                'scroll_simulation': False  # 正常模式默认关闭
            },
            'proxy_settings': {
                'enabled': False,
                'api_url': None,
                'rotation_strategy': 'quality'
            }
        }
        
        # 增强模式配置
        self.enhanced_config = {
            'anti_detection_mode': AntiDetectionMode.ENHANCED.value,
            'use_proxy': False,  # 增强模式也不默认使用代理
            'request_delay': {
                'min': 2.0,
                'max': 5.0
            },
            'retry_settings': {
                'max_retries': 5,
                'retry_delay': 3
            },
            'session_settings': {
                'rotation_interval': 180,  # 3分钟
                'max_requests_per_session': 30
            },
            'headers_settings': {
                'randomize_user_agent': True,
                'add_referer': True,
                'add_fingerprint': True  # 增强模式启用指纹
            },
            'behavior_settings': {
                'simulate_human_behavior': True,
                'random_delay': True,
                'mouse_movement': True,  # 增强模式启用鼠标模拟
                'scroll_simulation': True  # 增强模式启用滚动模拟
            },
            'proxy_settings': {
                'enabled': False,
                'api_url': None,
                'rotation_strategy': 'quality'
            }
        }
        
        # 当前配置
        self.current_config = self.default_config.copy()
        self.current_mode = AntiDetectionMode.NORMAL
    
    def set_mode(self, mode: AntiDetectionMode) -> None:
        """设置防检测模式"""
        self.current_mode = mode
        
        if mode == AntiDetectionMode.NORMAL:
            self.current_config = self.default_config.copy()
        else:
            self.current_config = self.enhanced_config.copy()
        
        logger.info(f"已切换到{mode.value}模式")
    
    def get_mode(self) -> AntiDetectionMode:
        """获取当前模式"""
        return self.current_mode
    
    def is_enhanced_mode(self) -> bool:
        """是否为增强模式"""
        return self.current_mode == AntiDetectionMode.ENHANCED
    
    def get_config(self, key: Optional[str] = None) -> Any:
        """获取配置值"""
        if key is None:
            return self.current_config
        
        keys = key.split('.')
        value = self.current_config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
    
    def set_config(self, key: str, value: Any) -> None:
        """设置配置值"""
        keys = key.split('.')
        config = self.current_config
        
        # 导航到父级
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置值
        config[keys[-1]] = value
    
    def enable_proxy(self, api_url: Optional[str] = None) -> None:
        """启用代理"""
        self.set_config('proxy_settings.enabled', True)
        if api_url:
            self.set_config('proxy_settings.api_url', api_url)
        logger.info("代理功能已启用")
    
    def disable_proxy(self) -> None:
        """禁用代理"""
        self.set_config('proxy_settings.enabled', False)
        self.set_config('proxy_settings.api_url', None)
        logger.info("代理功能已禁用")
    
    def set_request_delay(self, min_delay: float, max_delay: float) -> None:
        """设置请求延迟"""
        self.set_config('request_delay.min', min_delay)
        self.set_config('request_delay.max', max_delay)
        logger.info(f"请求延迟已设置为 {min_delay}-{max_delay} 秒")
    
    def set_retry_settings(self, max_retries: int, retry_delay: int) -> None:
        """设置重试参数"""
        self.set_config('retry_settings.max_retries', max_retries)
        self.set_config('retry_settings.retry_delay', retry_delay)
        print(f"重试设置已更新：最大重试 {max_retries} 次，重试延迟 {retry_delay} 秒")
    
    def enable_behavior_simulation(self, mouse: bool = True, scroll: bool = True) -> None:
        """启用行为模拟"""
        self.set_config('behavior_settings.mouse_movement', mouse)
        self.set_config('behavior_settings.scroll_simulation', scroll)
        print(f"行为模拟已启用：鼠标移动={mouse}, 滚动模拟={scroll}")
    
    def disable_behavior_simulation(self) -> None:
        """禁用行为模拟"""
        self.set_config('behavior_settings.mouse_movement', False)
        self.set_config('behavior_settings.scroll_simulation', False)
        print("行为模拟已禁用")
    
    def get_mode_description(self) -> str:
        """获取模式描述"""
        if self.current_mode == AntiDetectionMode.NORMAL:
            return """
正常模式特点：
- 基础请求头伪装
- 简单延迟控制
- 基本重试机制
- 适合大多数政策网站
- 性能较好，资源消耗低
            """
        else:
            return """
增强模式特点：
- 高级指纹伪装
- 复杂行为模拟
- 增强重试机制
- 适合严格反爬虫网站
- 性能较低，资源消耗高
            """
    
    def save_config(self, file_path: str = "crawler_config.json") -> None:
        """保存配置到文件"""
        config_data = {
            'mode': self.current_mode.value,
            'config': self.current_config
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        print(f"配置已保存到: {file_path}")
    
    def load_config(self, file_path: str = "crawler_config.json") -> bool:
        """从文件加载配置"""
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            mode_value = config_data.get('mode', 'normal')
            self.current_mode = AntiDetectionMode(mode_value)
            self.current_config = config_data.get('config', self.default_config)
            
            print(f"配置已从 {file_path} 加载")
            return True
        except Exception as e:
            print(f"加载配置失败: {e}")
            return False
    
    def print_current_config(self) -> None:
        """打印当前配置"""
        print(f"\n当前模式: {self.current_mode.value}")
        print(f"代理状态: {'启用' if self.get_config('proxy_settings.enabled') else '禁用'}")
        print(f"请求延迟: {self.get_config('request_delay.min')}-{self.get_config('request_delay.max')} 秒")
        print(f"最大重试: {self.get_config('retry_settings.max_retries')} 次")
        print(f"行为模拟: {'启用' if self.get_config('behavior_settings.simulate_human_behavior') else '禁用'}")
        print(f"指纹伪装: {'启用' if self.get_config('headers_settings.add_fingerprint') else '禁用'}")
        print(self.get_mode_description())

# 全局配置实例
crawler_config = CrawlerConfig() 