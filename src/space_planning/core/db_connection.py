#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库连接管理模块
提供上下文管理器，确保数据库连接正确关闭
"""

import sqlite3
import logging
from contextlib import contextmanager
from typing import Optional

from .exceptions import DatabaseConnectionError
from . import config

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection():
    """
    数据库连接上下文管理器
    
    使用示例:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM policy")
            results = cursor.fetchall()
        # 连接自动关闭
    
    Yields:
        sqlite3.Connection: 数据库连接对象
    
    Raises:
        DatabaseConnectionError: 连接失败时抛出
    """
    db_path = config.app_config.get_database_path()
    conn = None
    try:
        # 确保数据库目录存在
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # 返回字典式行对象
        
        logger.debug(f"数据库连接已建立: {db_path}")
        yield conn
        
        conn.commit()
        logger.debug("数据库连接已提交并关闭")
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"数据库操作失败: {e}", exc_info=True)
        raise DatabaseConnectionError(f"无法连接数据库 {db_path}: {e}") from e
    except OSError as e:
        if conn:
            try:
                conn.rollback()
            except (sqlite3.Error, OSError):
                pass
        logger.error(f"数据库文件操作失败: {e}", exc_info=True)
        raise DatabaseConnectionError(f"无法创建数据库目录: {e}") from e
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except (sqlite3.Error, OSError):
                pass
        logger.error(f"数据库操作出现未知错误: {e}", exc_info=True)
        raise DatabaseConnectionError(f"数据库操作失败: {e}") from e
    finally:
        if conn:
            try:
                conn.close()
            except Exception as close_error:
                logger.error(f"关闭数据库连接失败: {close_error}", exc_info=True)


@contextmanager
def get_db_cursor():
    """
    数据库游标上下文管理器（同时管理连接和游标）
    
    使用示例:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM policy")
            results = cursor.fetchall()
        # 连接和游标自动关闭
    
    Yields:
        sqlite3.Cursor: 数据库游标对象
    
    Raises:
        DatabaseConnectionError: 连接失败时抛出
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise

