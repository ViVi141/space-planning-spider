import sqlite3
import os
import sys
import shutil
from datetime import datetime, timedelta
import json
import logging

# 导入配置模块
from . import config
from .exceptions import (
    DatabaseConnectionError,
    DatabaseQueryError,
    DatabaseIntegrityError,
    DatabaseError
)
from .db_connection import get_db_connection

logger = logging.getLogger(__name__)

def get_database_path():
    """获取数据库文件路径，使用新的配置系统"""
    return config.app_config.get_database_path()

def get_backup_dir():
    """获取备份目录"""
    return config.app_config.get_backup_dir()

def get_conn():
    """
    获取数据库连接（向后兼容函数）
    
    注意：推荐使用 get_db_connection() 上下文管理器
    这样可以确保连接正确关闭
    """
    db_path = get_database_path()
    # 确保数据库目录存在
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return sqlite3.connect(db_path)
    except sqlite3.Error as e:
        raise DatabaseConnectionError(f"无法连接数据库 {db_path}: {e}") from e
    except OSError as e:
        raise DatabaseConnectionError(f"无法创建数据库目录: {e}") from e

def init_db():
    """初始化数据库"""
    conn = get_conn()
    c = conn.cursor()
    
    # 创建主表
    c.execute('''
        CREATE TABLE IF NOT EXISTS policy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            title TEXT,
            pub_date TEXT,
            source TEXT,
            content TEXT,
            category TEXT,
            crawl_time TEXT
        )
    ''')
    
    # 检查是否需要添加category字段（数据库迁移）
    try:
        c.execute('SELECT category FROM policy LIMIT 1')
    except sqlite3.OperationalError:
        # category字段不存在，需要添加
        logger.info("正在添加category字段到现有数据库...")
        c.execute('ALTER TABLE policy ADD COLUMN category TEXT')
        logger.info("category字段添加完成")
    
    # 创建全文检索表
    c.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS policy_fts USING fts5(
            title, content, level, content='policy', content_rowid='id'
        )
    ''')
    
    # 创建索引以提高查询性能
    # 1. level字段索引（用于按机构筛选）
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_policy_level ON policy(level)
    ''')
    
    # 2. pub_date字段索引（用于时间范围查询和排序）
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_policy_pub_date ON policy(pub_date)
    ''')
    
    # 3. 组合索引（level + pub_date，用于常见查询模式）
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_policy_level_date ON policy(level, pub_date DESC)
    ''')
    
    # 4. title索引（用于标题搜索）
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_policy_title ON policy(title)
    ''')
    
    # 5. source索引（用于来源筛选）
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_policy_source ON policy(source)
    ''')
    
    # 6. category索引（用于分类筛选）
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_policy_category ON policy(category)
    ''')
    
    # 7. crawl_time索引（用于按爬取时间查询）
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_policy_crawl_time ON policy(crawl_time)
    ''')
    
    # 创建系统信息表
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_info (
            key TEXT PRIMARY KEY,
            value TEXT,
            update_time TEXT
        )
    ''')
    
    # 初始化系统信息
    c.execute('''
        INSERT OR IGNORE INTO system_info (key, value, update_time) 
        VALUES (?, ?, ?)
    ''', ('db_version', '2.0', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    conn.commit()
    conn.close()
    
    logger.info(f"数据库初始化完成: {get_database_path()}")

def backup_database():
    """备份数据库"""
    try:
        db_path = get_database_path()
        if not os.path.exists(db_path):
            logger.warning("数据库文件不存在，无需备份")
            return False
        
        backup_dir = get_backup_dir()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"policy_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # 复制数据库文件
        shutil.copy2(db_path, backup_path)
        
        # 更新最后备份时间
        config.app_config.update_config('last_backup_time', datetime.now().isoformat())
        
        logger.info(f"数据库备份完成: {backup_path}")
        
        # 清理旧备份文件
        cleanup_old_backups()
        
        return True
    except OSError as e:
        logger.error(f"数据库备份失败（文件操作错误）: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"数据库备份失败（未知错误）: {e}", exc_info=True)
        return False

def cleanup_old_backups():
    """清理旧的备份文件"""
    try:
        backup_dir = get_backup_dir()
        max_backup_count = config.app_config.get_database_config().get('max_backup_count', 10)
        
        # 获取所有备份文件
        backup_files = []
        for filename in os.listdir(backup_dir):
            if filename.startswith('policy_backup_') and filename.endswith('.db'):
                file_path = os.path.join(backup_dir, filename)
                backup_files.append((file_path, os.path.getmtime(file_path)))
        
        # 按修改时间排序
        backup_files.sort(key=lambda x: x[1], reverse=True)
        
        # 删除多余的备份文件
        if len(backup_files) > max_backup_count:
            for file_path, _ in backup_files[max_backup_count:]:
                os.remove(file_path)
                logger.debug(f"删除旧备份文件: {file_path}")
    except OSError as e:
        logger.error(f"清理旧备份文件失败（文件操作错误）: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"清理旧备份文件失败（未知错误）: {e}", exc_info=True)

def clear_database():
    """清理数据库 - 删除所有政策数据（使用上下文管理器）"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 获取清理前的数据统计
            c.execute('SELECT COUNT(*) FROM policy')
            policy_count = c.fetchone()[0]
            
            # 删除所有政策数据
            c.execute('DELETE FROM policy')
            
            # 清理FTS表
            c.execute('DELETE FROM policy_fts')
            
            # 重置自增ID
            c.execute('DELETE FROM sqlite_sequence WHERE name="policy"')
            
            # 上下文管理器会自动commit
        
        # 在连接关闭后执行备份（避免死锁）
        if policy_count > 0:
            backup_database()
        
        logger.info(f"数据库清理完成，删除了 {policy_count} 条政策数据")
        return True, policy_count
    except DatabaseError as e:
        logger.error(f"数据库清理失败（数据库错误）: {e}", exc_info=True)
        return False, 0
    except Exception as e:
        logger.error(f"数据库清理失败（未知错误）: {e}", exc_info=True)
        return False, 0

def should_backup_database():
    """检查是否需要备份数据库"""
    try:
        backup_enabled = config.app_config.get_database_config().get('backup_enabled', True)
        if not backup_enabled:
            return False
        
        last_backup_time = config.app_config.get_config('last_backup_time')
        if not last_backup_time:
            return True
        
        backup_interval = config.app_config.get_database_config().get('backup_interval', 7)
        last_backup = datetime.fromisoformat(last_backup_time)
        days_since_backup = (datetime.now() - last_backup).days
        
        return days_since_backup >= backup_interval
    except Exception as e:
        logger.error(f"检查备份状态失败: {e}", exc_info=True)
        return False

def insert_policy(level, title, pub_date, source, content, crawl_time, category=None):
    """插入政策数据 - 增强去重逻辑（使用上下文管理器）"""
    from .db_connection import get_db_connection
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 增强去重逻辑：检查多种组合
            # 1. 标题+日期组合
            c.execute('SELECT id FROM policy WHERE title=? AND pub_date=?', (title, pub_date))
            if c.fetchone():
                logger.debug(f"跳过重复政策: {title} ({pub_date})")
                return None
            
            # 2. 标题+来源组合（如果来源相同）
            if source:
                c.execute('SELECT id FROM policy WHERE title=? AND source=?', (title, source))
                if c.fetchone():
                    logger.debug(f"跳过重复政策: {title} (来源: {source})")
                    return None
            
            # 3. 内容相似度检查（如果内容完全相同）
            c.execute('SELECT id FROM policy WHERE content=?', (content,))
            if c.fetchone():
                logger.debug(f"跳过重复内容政策: {title}")
                return None
            
            c.execute('''INSERT INTO policy (level, title, pub_date, source, content, category, crawl_time)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (level, title, pub_date, source, content, category, crawl_time))
            rowid = c.lastrowid
            
            # 同步到FTS表
            c.execute('INSERT INTO policy_fts(rowid, title, content, level) VALUES (?, ?, ?, ?)',
                      (rowid, title, content, level))
            
            # 上下文管理器会自动commit
        
        # 检查是否需要备份（在连接关闭后）
        if should_backup_database():
            backup_database()
        
        return rowid
    except DatabaseIntegrityError as e:
        logger.warning(f"插入政策失败（数据完整性约束）: {e}")
        return None
    except DatabaseQueryError as e:
        logger.error(f"插入政策失败（数据库操作错误）: {e}", exc_info=True)
        raise
    except DatabaseError as e:
        logger.error(f"插入政策失败（数据库错误）: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"插入政策失败（未知错误）: {e}", exc_info=True)
        return None

def deduplicate_database():
    """清理数据库中的重复记录（使用上下文管理器）"""
    from .db_connection import get_db_connection
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            logger.info("🔍 开始清理数据库重复记录...")
            
            # 获取所有政策
            c.execute('SELECT id, title, pub_date, source, content FROM policy ORDER BY id')
            all_policies = c.fetchall()
            
            if not all_policies:
                logger.info("数据库中没有政策数据")
                return {'success': True, 'removed': 0, 'total': 0}
            
            logger.info(f"总政策数量: {len(all_policies)}")
            
            # 按标题+日期分组，保留最新的记录
            policy_groups = {}
            for policy in all_policies:
                policy_id, title, pub_date, source, content = policy
                key = (title, pub_date)
                if key not in policy_groups:
                    policy_groups[key] = []
                policy_groups[key].append(policy)
            
            # 找出重复的记录
            duplicates_to_remove = []
            for key, policies in policy_groups.items():
                if len(policies) > 1:
                    # 保留ID最大的记录（最新的），删除其他的
                    policies.sort(key=lambda x: x[0])  # 按ID排序
                    duplicates_to_remove.extend(policies[:-1])  # 除了最后一个都删除
            
            if not duplicates_to_remove:
                logger.info("✅ 没有发现重复记录")
                return {'success': True, 'removed': 0, 'total': len(all_policies)}
            
            logger.info(f"发现 {len(duplicates_to_remove)} 条重复记录需要删除")
            
            # 删除重复记录
            removed_count = 0
            for policy in duplicates_to_remove:
                policy_id, title, pub_date, source, content = policy
                try:
                    # 删除主表记录
                    c.execute('DELETE FROM policy WHERE id = ?', (policy_id,))
                    # 删除FTS表记录
                    c.execute('DELETE FROM policy_fts WHERE rowid = ?', (policy_id,))
                    removed_count += 1
                    logger.debug(f"删除重复记录: {title} ({pub_date})")
                except sqlite3.Error as e:
                    logger.error(f"删除记录失败 ID {policy_id}（数据库错误）: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"删除记录失败 ID {policy_id}（未知错误）: {e}", exc_info=True)
            
            # 上下文管理器会自动commit
            
            # 重新统计
            c.execute('SELECT COUNT(*) FROM policy')
            new_count = c.fetchone()[0]
            
            logger.info(f"✅ 清理完成！删除了 {removed_count} 条重复记录，剩余 {new_count} 条记录")
            
            return {
                'success': True,
                'removed': removed_count,
                'total': new_count,
                'original': len(all_policies)
            }
        
    except DatabaseError as e:
        logger.error(f"清理数据库失败（数据库错误）: {e}", exc_info=True)
        return {'success': False, 'error': f'数据库错误: {str(e)}'}
    except Exception as e:
        logger.error(f"清理数据库失败（未知错误）: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def search_policies(level=None, keywords=None, start_date=None, end_date=None, limit=None, offset=0):
    """
    搜索政策，支持时间区间（改进：添加输入验证和分页，使用上下文管理器）
    
    Args:
        level: 机构级别
        keywords: 关键词列表
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回结果数量限制（用于分页）
        offset: 结果偏移量（用于分页）
    
    Returns:
        政策数据列表
    """
    # 导入验证器和连接管理器
    from ..utils.validator import InputValidator
    from .db_connection import get_db_connection
    
    try:
        # 验证limit和offset参数（防止注入和DoS攻击）
        validated_limit = InputValidator.validate_integer(limit, min_val=1, max_val=10000, default=None)
        validated_offset = InputValidator.validate_integer(offset, min_val=0, max_val=1000000, default=0)
        
        # 验证level参数（白名单机制）
        validated_level = None
        if level:
            validated_level = InputValidator.sanitize_level(level)
            if not validated_level:
                logger.warning(f"无效的机构级别参数，已忽略: {level}")
        
        with get_db_connection() as conn:
            c = conn.cursor()
            params = []
            # 使用列表构建SQL片段，避免字符串拼接
            where_conditions = []
            
            # 验证和添加日期条件
            if start_date and end_date:
                validated_start = InputValidator.validate_date(start_date)
                validated_end = InputValidator.validate_date(end_date)
                if validated_start and validated_end:
                    where_conditions.append('p.pub_date BETWEEN ? AND ?')
                    params.extend([validated_start, validated_end])
                else:
                    logger.warning(f"无效的日期参数: {start_date} - {end_date}")
            
            # 构建WHERE子句（安全的方式）
            where_clause = ''
            if where_conditions:
                where_clause = ' AND ' + ' AND '.join(where_conditions)
            
            # 验证和清理关键词
            if keywords:
                # 清理关键词（防止注入攻击）
                sanitized_keywords = []
                for kw in keywords:
                    if isinstance(kw, str):
                        sanitized = InputValidator.sanitize_fts_query(kw)
                        if sanitized:
                            sanitized_keywords.append(sanitized)
                
                if sanitized_keywords:
                    # 构建FTS查询（使用参数化方式）
                    if validated_level:
                        # 使用参数化方式构建FTS查询
                        fts_query_parts = [f"level:{validated_level}"]
                        fts_query_parts.append(f"({' OR '.join(sanitized_keywords)})")
                        fts_query = ' AND '.join(fts_query_parts)
                    else:
                        fts_query = ' OR '.join(sanitized_keywords)
                    
                    # 再次清理完整查询（双重保护）
                    fts_query = InputValidator.sanitize_fts_query(fts_query, max_length=500)
                    
                    if fts_query:
                        # 使用参数化查询（避免SQL注入）
                        sql = '''SELECT p.id, p.level, p.title, p.pub_date, p.source, p.content, p.category 
                                 FROM policy p JOIN policy_fts fts ON p.id = fts.rowid 
                                 WHERE policy_fts MATCH ?'''
                        sql += where_clause
                        sql += ' ORDER BY p.pub_date DESC'
                        
                        query_params = [fts_query] + params
                        
                        if validated_limit:
                            sql += ' LIMIT ? OFFSET ?'
                            query_params.extend([validated_limit, validated_offset])
                        
                        c.execute(sql, query_params)
                    else:
                        # 查询被过滤，返回空结果（使用参数化查询）
                        sql = '''SELECT id, level, title, pub_date, source, content, category 
                                 FROM policy p WHERE 1=0'''
                        sql += where_clause
                        c.execute(sql, params)
                else:
                    # 所有关键词都被过滤，使用普通查询
                    keywords = None
            
            if not keywords:
                # 普通查询（不使用FTS）
                sql = '''SELECT id, level, title, pub_date, source, content, category 
                         FROM policy p'''
                
                if validated_level:
                    sql += ' WHERE level = ?'
                    sql += where_clause
                    params = [validated_level] + params
                elif where_clause:
                    sql += ' WHERE 1=1' + where_clause
                
                sql += ' ORDER BY pub_date DESC'
                
                if validated_limit:
                    sql += ' LIMIT ? OFFSET ?'
                    params.extend([validated_limit, validated_offset])
                
                c.execute(sql, params)
            
            results = c.fetchall()
            return results
    except Exception as e:
        logger.error(f"搜索政策失败: {e}", exc_info=True)
        return []

def get_policy_by_id(policy_id):
    """
    根据ID获取政策详情（改进：使用上下文管理器）
    
    Args:
        policy_id: 政策ID
    
    Returns:
        政策数据元组或None
    """
    from .db_connection import get_db_connection
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM policy WHERE id = ?', (policy_id,))
            result = c.fetchone()
            return result
    except Exception as e:
        logger.error(f"获取政策详情失败 ID {policy_id}: {e}", exc_info=True)
        return None

def get_database_info():
    """获取数据库信息（改进：使用上下文管理器）"""
    from .db_connection import get_db_connection
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 获取政策数量
            c.execute('SELECT COUNT(*) FROM policy')
            policy_count = c.fetchone()[0]
            
            # 获取最新政策时间
            c.execute('SELECT MAX(pub_date) FROM policy')
            latest_date = c.fetchone()[0]
            
            # 获取数据库文件大小
            db_path = get_database_path()
            try:
                if os.path.exists(db_path):
                    stat_info = os.stat(db_path)
                    file_size = stat_info.st_size
                else:
                    file_size = 0
            except (OSError, OverflowError):
                file_size = 0
            
            # 获取最后备份时间
            last_backup_time = config.app_config.get_config('last_backup_time')
            
            return {
                'policy_count': policy_count,
                'latest_date': latest_date,
                'file_size': file_size,
                'file_size_mb': round(float(file_size) / (1024 * 1024), 2),
                'last_backup_time': last_backup_time,
                'database_path': db_path,
                'backup_dir': get_backup_dir()
            }
    except sqlite3.Error as e:
        logger.error(f"获取数据库信息失败（数据库错误）: {e}", exc_info=True)
        return {}
    except Exception as e:
        logger.error(f"获取数据库信息失败（未知错误）: {e}", exc_info=True)
        return {}

def restore_database(backup_file):
    """从备份文件恢复数据库"""
    try:
        db_path = get_database_path()
        backup_path = os.path.join(get_backup_dir(), backup_file)
        
        if not os.path.exists(backup_path):
            logger.warning(f"备份文件不存在: {backup_path}")
            return False
        
        # 备份当前数据库
        if os.path.exists(db_path):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            current_backup = os.path.join(get_backup_dir(), f"before_restore_{timestamp}.db")
            shutil.copy2(db_path, current_backup)
            logger.info(f"当前数据库已备份到: {current_backup}")
        
        # 恢复数据库
        shutil.copy2(backup_path, db_path)
        logger.info(f"数据库恢复完成: {backup_path}")
        return True
    except (OSError, IOError) as e:
        logger.error(f"数据库恢复失败（文件操作错误）: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"数据库恢复失败（未知错误）: {e}", exc_info=True)
        return False

def get_backup_files():
    """获取所有备份文件"""
    try:
        backup_dir = get_backup_dir()
        backup_files = []
        
        for filename in os.listdir(backup_dir):
            if filename.startswith('policy_backup_') and filename.endswith('.db'):
                file_path = os.path.join(backup_dir, filename)
                try:
                    # 使用os.stat避免大文件大小溢出
                    stat_info = os.stat(file_path)
                    file_size = stat_info.st_size
                    file_time = datetime.fromtimestamp(stat_info.st_mtime)
                    
                    # 安全计算文件大小MB，避免溢出
                    file_size_mb = round(float(file_size) / (1024 * 1024), 2)
                    
                    backup_files.append({
                        'filename': filename,
                        'file_path': file_path,
                        'file_size': file_size,
                        'file_size_mb': file_size_mb,
                        'file_time': file_time.strftime('%Y-%m-%d %H:%M:%S')
                    })
                except (OSError, OverflowError) as e:
                    logger.warning(f"处理文件 {filename} 时出错: {e}")
                    # 跳过有问题的文件
                    continue
        
        # 按时间倒序排序
        backup_files.sort(key=lambda x: x['file_time'], reverse=True)
        return backup_files
    except OSError as e:
        logger.error(f"获取备份文件列表失败（文件操作错误）: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"获取备份文件列表失败（未知错误）: {e}", exc_info=True)
        return []

class DatabaseManager:
    """数据库管理类"""
    
    def __init__(self):
        self.db_path = get_database_path()
        self.backup_dir = get_backup_dir()
    
    def get_conn(self):
        """获取数据库连接"""
        return get_conn()
    
    def init_db(self):
        """初始化数据库"""
        init_db()
    
    def insert_policy(self, level, title, pub_date, source, content, crawl_time):
        """插入政策数据"""
        return insert_policy(level, title, pub_date, source, content, crawl_time)
    
    def search_policies(self, level=None, keywords=None, start_date=None, end_date=None):
        """搜索政策，支持时间区间"""
        return search_policies(level, keywords, start_date, end_date)
    
    def get_policy_by_id(self, policy_id):
        """根据ID获取政策详情"""
        return get_policy_by_id(policy_id)
    
    def backup_database(self):
        """备份数据库"""
        return backup_database()
    
    def restore_database(self, backup_file):
        """从备份文件恢复数据库"""
        return restore_database(backup_file)
    
    def get_database_info(self):
        """获取数据库信息"""
        return get_database_info()
    
    def get_backup_files(self):
        """获取所有备份文件"""
        return get_backup_files()
    
    def cleanup_old_backups(self):
        """清理旧的备份文件"""
        return cleanup_old_backups()
    
    def clear_database(self):
        """清理数据库 - 删除所有政策数据"""
        return clear_database() 