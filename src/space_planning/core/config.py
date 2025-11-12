#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件
"""

import os
import sys
import json
import logging

# 初始化日志（延迟导入避免循环依赖）
logger = logging.getLogger(__name__)

# 导入异常类
from .exceptions import ConfigError, ConfigFileNotFoundError, ConfigParseError

# 应用配置
APP_CONFIG = {
    'app_name': '空间规划政策爬虫系统',
    'app_version': '3.1.2',
    'install_mode': True,  # 是否使用安装模式
    'data_dir_name': '空间规划政策爬虫系统',  # 数据目录名称
}

# 数据库配置
DATABASE_CONFIG = {
    'max_display_count': 100000,  # 最大显示数量（取消限制）
    'max_crawl_pages': 999999,  # 最大爬取页数（无上限）
    'timeout': 10,              # 网络请求超时时间
    'backup_enabled': True,     # 是否启用数据库备份
    'backup_interval': 7,       # 备份间隔（天）
    'max_backup_count': 10,     # 最大备份文件数量
}

# 爬虫配置
SPIDER_CONFIG = {
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    'request_timeout': 15,
    'max_retries': 3,
    'min_delay': 1.0,
    'max_delay': 3.0,
    'max_requests_per_minute': 999999,  # 无限制
}

# 防反爬虫配置
ANTI_CRAWLER_CONFIG = {
    'enable_rotation': True,  # 是否启用会话轮换
    'enable_frequency_limit': True,  # 是否启用频率限制
    'max_concurrent_requests': 999,  # 最大并发请求数（无限制）
    'session_rotation_interval': 300,  # 会话轮换间隔（秒）
}

# 界面配置
UI_CONFIG = {
    'window_width': 1400,
    'window_height': 900,
    'table_row_height': 60,
    'text_area_height': 250,
    'max_display_rows': 100,  # 最大显示行数
    'page_size': 50,  # 每页显示行数
    'default_thread_count': 4,  # 默认多线程数量
}

# 政策类型关键词
POLICY_TYPES = {
    '总体规划': ['总体规划', '国土空间规划', '城市总体规划', '县域规划'],
    '控制性详细规划': ['控制性详细规划', '控规', '详细规划'],
    '专项规划': ['专项规划', '专项', '交通规划', '绿地规划', '基础设施规划'],
    '土地利用': ['土地利用', '用地', '土地管理', '建设用地'],
    '环境保护': ['环境保护', '生态', '污染', '环境'],
    '历史文化': ['历史文化', '文物', '古迹', '保护'],
    '交通规划': ['交通', '道路', '轨道交通', '公交'],
    '市政设施': ['市政', '给排水', '电力', '通信', '燃气']
}

# 合规性关键词
COMPLIANCE_KEYWORDS = {
    '强制性': ['必须', '应当', '禁止', '不得', '严禁'],
    '指导性': ['建议', '鼓励', '推荐', '引导'],
    '程序性': ['程序', '流程', '审批', '备案', '公示'],
    '标准性': ['标准', '规范', '要求', '指标', '参数']
}

class AppConfig:
    """应用配置管理类"""
    
    def __init__(self):
        self.app_name = APP_CONFIG['app_name']
        self.app_version = APP_CONFIG['app_version']
        self.install_mode = APP_CONFIG['install_mode']
        self.data_dir_name = APP_CONFIG['data_dir_name']
        
        # 获取应用数据目录
        self.app_data_dir = self._get_app_data_dir()
        self.config_file = os.path.join(self.app_data_dir, 'app_config.json')
        
        # 加载或创建配置文件
        self._load_or_create_config()
    
    def _get_app_data_dir(self):
        """获取应用数据目录"""
        if self.install_mode:
            # 安装模式：使用用户文档目录
            if sys.platform == 'win32':
                # Windows: 用户文档目录
                user_docs = os.path.expanduser("~/Documents")
                app_data_dir = os.path.join(user_docs, self.data_dir_name)
            elif sys.platform == 'darwin':
                # macOS: 应用支持目录
                app_data_dir = os.path.expanduser(f"~/Library/Application Support/{self.data_dir_name}")
            else:
                # Linux: 用户配置目录
                app_data_dir = os.path.expanduser(f"~/.config/{self.data_dir_name}")
        else:
            # 便携模式：使用程序目录
            if getattr(sys, 'frozen', False):
                # 打包后的环境
                app_data_dir = os.path.join(os.path.dirname(sys.executable), 'data')
            else:
                # 开发环境 - 使用更安全的方式获取项目根目录
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(current_dir))
                app_data_dir = os.path.join(project_root, 'data')
        
        # 确保目录存在
        os.makedirs(app_data_dir, exist_ok=True)
        return app_data_dir
    
    def _load_or_create_config(self):
        """加载或创建配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except FileNotFoundError:
                logger.warning("配置文件不存在，使用默认配置")
                self.config = self._get_default_config()
            except json.JSONDecodeError as e:
                logger.error(f"配置文件格式错误: {e}", exc_info=True)
                raise ConfigParseError(f"配置文件解析失败: {e}") from e
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}", exc_info=True)
                raise ConfigError(f"配置加载失败: {e}") from e
        else:
            self.config = self._get_default_config()
            self._save_config()
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            'install_mode': self.install_mode,
            'database': DATABASE_CONFIG,
            'spider': SPIDER_CONFIG,
            'anti_crawler': ANTI_CRAWLER_CONFIG,
            'ui': UI_CONFIG,
            'policy_types': POLICY_TYPES,
            'compliance_keywords': COMPLIANCE_KEYWORDS,
            'last_backup_time': None,
            'database_path': os.path.join(self.app_data_dir, 'policy.db'),
            'backup_dir': os.path.join(self.app_data_dir, 'backups'),
        }
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except (OSError, IOError) as e:
            logger.error(f"保存配置文件失败（文件操作错误）: {e}", exc_info=True)
            raise ConfigError(f"配置保存失败: {e}") from e
        except Exception as e:
            logger.error(f"保存配置文件失败（未知错误）: {e}", exc_info=True)
            raise ConfigError(f"配置保存失败: {e}") from e
    
    def get_database_path(self):
        """获取数据库路径"""
        return self.config.get('database_path', os.path.join(self.app_data_dir, 'policy.db'))
    
    def get_backup_dir(self):
        """获取备份目录"""
        backup_dir = self.config.get('backup_dir', os.path.join(self.app_data_dir, 'backups'))
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir
    
    def update_config(self, key, value):
        """更新配置"""
        self.config[key] = value
        self._save_config()
    
    def get_config(self, key, default=None):
        """获取配置值"""
        return self.config.get(key, default)
    
    def get_database_config(self):
        """获取数据库配置"""
        return self.config.get('database', DATABASE_CONFIG)
    
    def get_spider_config(self):
        """获取爬虫配置"""
        return self.config.get('spider', SPIDER_CONFIG)
    
    def get_anti_crawler_config(self):
        """获取防反爬虫配置"""
        return self.config.get('anti_crawler', ANTI_CRAWLER_CONFIG)
    
    def get_ui_config(self):
        """获取界面配置"""
        return self.config.get('ui', UI_CONFIG)
    
    def get_policy_types(self):
        """获取政策类型关键词"""
        return self.config.get('policy_types', POLICY_TYPES)
    
    def get_compliance_keywords(self):
        """获取合规性关键词"""
        return self.config.get('compliance_keywords', COMPLIANCE_KEYWORDS)

# 全局配置实例
app_config = AppConfig()

class Config:
    """配置管理类（向后兼容）"""
    
    def __init__(self):
        self.database = app_config.get_database_config()
        self.spider = app_config.get_spider_config()
        self.anti_crawler = app_config.get_anti_crawler_config()
        self.ui = app_config.get_ui_config()
        self.policy_types = app_config.get_policy_types()
        self.compliance_keywords = app_config.get_compliance_keywords()
    
    @classmethod
    def get_database_config(cls):
        """获取数据库配置"""
        return app_config.get_database_config()
    
    @classmethod
    def get_spider_config(cls):
        """获取爬虫配置"""
        return app_config.get_spider_config()
    
    @classmethod
    def get_anti_crawler_config(cls):
        """获取防反爬虫配置"""
        return app_config.get_anti_crawler_config()
    
    @classmethod
    def get_ui_config(cls):
        """获取界面配置"""
        return app_config.get_ui_config()
    
    @classmethod
    def get_policy_types(cls):
        """获取政策类型关键词"""
        return app_config.get_policy_types()
    
    @classmethod
    def get_compliance_keywords(cls):
        """获取合规性关键词"""
        return app_config.get_compliance_keywords() 