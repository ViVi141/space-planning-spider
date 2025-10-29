#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
输入验证和清理工具
提供输入验证、清理和转义功能
"""

import re
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class InputValidator:
    """输入验证器"""
    
    # SQL注入危险字符模式
    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",  # UNION SELECT
        r"(\bDROP\s+TABLE\b)",  # DROP TABLE
        r"(\bDELETE\s+FROM\b)",  # DELETE FROM
        r"(\bINSERT\s+INTO\b)",  # INSERT INTO
        r"(\bUPDATE\s+.*\bSET\b)",  # UPDATE SET
        r"(\bEXEC\b|\bEXECUTE\b)",  # EXEC/EXECUTE
        r"(--|\#|\/\*)",  # SQL注释
        r"(\bor\b\s+\d+\s*=\s*\d+)",  # OR 1=1
        r"('|\"|;|\\x)",  # 危险字符
    ]
    
    @staticmethod
    def sanitize_keywords(keywords: str) -> List[str]:
        """
        清理和验证关键词
        
        Args:
            keywords: 原始关键词字符串
            
        Returns:
            清理后的关键词列表
        """
        if not keywords:
            return []
        
        # 检查SQL注入风险
        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, keywords, re.IGNORECASE):
                logger.warning(f"检测到潜在SQL注入攻击，已过滤: {keywords[:50]}")
                return []  # 发现注入攻击，返回空列表
        
        # 移除特殊字符，只保留字母、数字、中文和常用标点
        sanitized = re.sub(r'[^\w\s\u4e00-\u9fa5，。、；：！？（）【】《》]', '', keywords)
        
        # 分割关键词
        keywords_list = [k.strip() for k in sanitized.split() if k.strip()]
        
        # 限制关键词长度（防止DoS攻击）
        keywords_list = [k for k in keywords_list if len(k) <= 100]
        
        # 限制关键词数量（防止资源耗尽）
        keywords_list = keywords_list[:20]  # 最多20个关键词
        
        return keywords_list
    
    @staticmethod
    def validate_date(date_str: str) -> Optional[str]:
        """
        验证日期格式
        
        Args:
            date_str: 日期字符串（格式：YYYY-MM-DD）
            
        Returns:
            验证通过的日期字符串，否则返回None
        """
        if not date_str:
            return None
        
        # 移除危险字符
        date_str = re.sub(r'[^\d-]', '', date_str)
        
        try:
            # 验证日期格式
            parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
            
            # 检查日期范围（防止异常值）
            min_date = datetime(1900, 1, 1)
            max_date = datetime(2100, 12, 31)
            
            if min_date <= parsed_date <= max_date:
                return date_str
            else:
                logger.warning(f"日期超出有效范围: {date_str}")
                return None
        except ValueError:
            logger.warning(f"无效的日期格式: {date_str}")
            return None
    
    @staticmethod
    def sanitize_fts_query(query_str: str, max_length: int = 1000) -> str:
        """
        清理FTS查询字符串（防止注入）
        
        Args:
            query_str: 原始查询字符串
            max_length: 最大长度
            
        Returns:
            清理后的查询字符串
        """
        if not query_str:
            return ""
        
        # 检查SQL注入风险
        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, query_str, re.IGNORECASE):
                logger.warning(f"FTS查询检测到潜在SQL注入，已过滤")
                return ""
        
        # FTS5特殊字符：需要转义或移除
        # FTS5保留字：AND, OR, NOT
        # 移除或转义这些字符
        query_str = query_str.replace('"', '')
        query_str = query_str.replace("'", '')
        
        # 限制单个关键词长度
        words = query_str.split()
        words = [w[:50] for w in words if len(w) <= 50]  # 限制单词长度
        query_str = ' '.join(words)
        
        # 限制总长度
        if len(query_str) > max_length:
            query_str = query_str[:max_length]
            logger.warning(f"FTS查询字符串过长，已截断")
        
        return query_str
    
    @staticmethod
    def sanitize_sql_string(s: str, max_length: int = 10000) -> str:
        """
        清理SQL字符串（用于普通查询）
        
        Args:
            s: 原始字符串
            max_length: 最大长度
            
        Returns:
            清理后的字符串
        """
        if not s:
            return ""
        
        # 检查SQL注入
        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, s, re.IGNORECASE):
                logger.warning(f"检测到SQL注入风险，已清理")
                # 移除危险字符
                s = re.sub(pattern, '', s, flags=re.IGNORECASE)
        
        # 限制长度
        if len(s) > max_length:
            s = s[:max_length]
        
        return s
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """
        验证URL格式
        
        Args:
            url: URL字符串
            
        Returns:
            是否为有效的URL
        """
        if not url:
            return False
        
        # URL模式验证
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(url):
            return False
        
        # 额外的安全检查：不允许某些危险协议或本地文件访问
        dangerous_patterns = [
            r'^file://',
            r'^javascript:',
            r'^data:',
            r'localhost.*\.\.',  # 路径遍历
        ]
        
        for pattern in dangerous_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return False
        
        return True
    
    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 255) -> str:
        """
        清理文件名（防止路径遍历攻击）
        
        Args:
            filename: 原始文件名
            max_length: 最大长度
            
        Returns:
            清理后的文件名
        """
        if not filename:
            return "untitled"
        
        # 移除路径分隔符和危险字符
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
        
        # 移除路径遍历
        filename = filename.replace('..', '')
        
        # 移除前导/后导点和空格
        filename = filename.strip('. ')
        
        # 限制长度
        if len(filename) > max_length:
            filename = filename[:max_length]
        
        # 如果清理后为空，使用默认名称
        if not filename:
            filename = "untitled"
        
        return filename
    
    @staticmethod
    def validate_integer(value: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> Optional[int]:
        """
        验证整数
        
        Args:
            value: 字符串值
            min_val: 最小值
            max_val: 最大值
            
        Returns:
            验证通过的整数值，否则返回None
        """
        try:
            int_val = int(value)
            
            if min_val is not None and int_val < min_val:
                return None
            if max_val is not None and int_val > max_val:
                return None
            
            return int_val
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def sanitize_level(level: str) -> Optional[str]:
        """
        验证和清理机构级别
        
        Args:
            level: 机构级别字符串
            
        Returns:
            验证通过的级别，否则返回None
        """
        if not level:
            return None
        
        # 允许的机构列表（白名单）
        allowed_levels = [
            "住房和城乡建设部",
            "广东省人民政府",
            "自然资源部",
            "国家发展和改革委员会",
            "生态环境部",
            # 可以根据需要添加更多
        ]
        
        # 检查是否在允许列表中
        if level in allowed_levels:
            return level
        
        # 如果没有匹配，记录警告但允许（为了兼容性）
        logger.warning(f"未知的机构级别: {level}")
        return level  # 暂时允许，但记录警告

