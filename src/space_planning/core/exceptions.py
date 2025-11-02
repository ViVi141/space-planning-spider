#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义异常类
提供项目特定的异常类型，便于精确异常处理
"""


class SpacePlanningError(Exception):
    """空间规划爬虫系统基础异常类"""
    pass


class DatabaseError(SpacePlanningError):
    """数据库操作异常"""
    pass


class DatabaseConnectionError(DatabaseError):
    """数据库连接异常"""
    pass


class DatabaseQueryError(DatabaseError):
    """数据库查询异常"""
    pass


class DatabaseIntegrityError(DatabaseError):
    """数据库完整性异常（如重复数据）"""
    pass


class ConfigError(SpacePlanningError):
    """配置错误"""
    pass


class ConfigFileNotFoundError(ConfigError):
    """配置文件未找到"""
    pass


class ConfigParseError(ConfigError):
    """配置解析错误"""
    pass


class CrawlerError(SpacePlanningError):
    """爬虫基础异常"""
    pass


class NetworkError(CrawlerError):
    """网络请求异常"""
    pass


class ConnectionTimeoutError(NetworkError):
    """连接超时异常"""
    pass


class HTTPError(NetworkError):
    """HTTP错误（4xx, 5xx）"""
    
    def __init__(self, message, status_code=None, url=None):
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class ProxyError(NetworkError):
    """代理相关异常"""
    pass


class ParseError(CrawlerError):
    """解析异常（HTML/JSON解析失败）"""
    pass


class DataValidationError(SpacePlanningError):
    """数据验证异常"""
    pass


class ExportError(SpacePlanningError):
    """导出功能异常"""
    pass


class ValidationError(SpacePlanningError):
    """输入验证异常"""
    pass

