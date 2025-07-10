import sqlite3
import os
import sys
import shutil
from datetime import datetime, timedelta
import json

# 导入配置模块
from . import config

def get_database_path():
    """获取数据库文件路径，使用新的配置系统"""
    return config.app_config.get_database_path()

def get_backup_dir():
    """获取备份目录"""
    return config.app_config.get_backup_dir()

def get_conn():
    """获取数据库连接"""
    db_path = get_database_path()
    # 确保数据库目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return sqlite3.connect(db_path)

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
        print("正在添加category字段到现有数据库...")
        c.execute('ALTER TABLE policy ADD COLUMN category TEXT')
        print("category字段添加完成")
    
    # 创建全文检索表
    c.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS policy_fts USING fts5(
            title, content, level, content='policy', content_rowid='id'
        )
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
    
    print(f"数据库初始化完成: {get_database_path()}")

def backup_database():
    """备份数据库"""
    try:
        db_path = get_database_path()
        if not os.path.exists(db_path):
            print("数据库文件不存在，无需备份")
            return False
        
        backup_dir = get_backup_dir()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"policy_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # 复制数据库文件
        shutil.copy2(db_path, backup_path)
        
        # 更新最后备份时间
        config.app_config.update_config('last_backup_time', datetime.now().isoformat())
        
        print(f"数据库备份完成: {backup_path}")
        
        # 清理旧备份文件
        cleanup_old_backups()
        
        return True
    except Exception as e:
        print(f"数据库备份失败: {e}")
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
                print(f"删除旧备份文件: {file_path}")
    except Exception as e:
        print(f"清理旧备份文件失败: {e}")

def clear_database():
    """清理数据库 - 删除所有政策数据"""
    try:
        conn = get_conn()
        c = conn.cursor()
        
        # 获取清理前的数据统计
        c.execute('SELECT COUNT(*) FROM policy')
        policy_count = c.fetchone()[0]
        
        # 备份当前数据库（可选）
        if policy_count > 0:
            backup_database()
        
        # 删除所有政策数据
        c.execute('DELETE FROM policy')
        
        # 清理FTS表
        c.execute('DELETE FROM policy_fts')
        
        # 重置自增ID
        c.execute('DELETE FROM sqlite_sequence WHERE name="policy"')
        
        # 提交更改
        conn.commit()
        conn.close()
        
        print(f"数据库清理完成，删除了 {policy_count} 条政策数据")
        return True, policy_count
    except Exception as e:
        print(f"数据库清理失败: {e}")
        if conn:
            conn.rollback()
            conn.close()
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
        print(f"检查备份状态失败: {e}")
        return False

def insert_policy(level, title, pub_date, source, content, crawl_time, category=None):
    """插入政策数据"""
    conn = None
    try:
        conn = get_conn()
        c = conn.cursor()
        
        # 去重：同title和pub_date不重复插入
        c.execute('SELECT id FROM policy WHERE title=? AND pub_date=?', (title, pub_date))
        if c.fetchone():
            return None
        
        c.execute('''INSERT INTO policy (level, title, pub_date, source, content, category, crawl_time)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (level, title, pub_date, source, content, category, crawl_time))
        rowid = c.lastrowid
        
        # 同步到FTS表
        c.execute('INSERT INTO policy_fts(rowid, title, content, level) VALUES (?, ?, ?, ?)',
                  (rowid, title, content, level))
        
        conn.commit()
        
        # 检查是否需要备份
        if should_backup_database():
            backup_database()
        
        return rowid
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"插入政策失败: {e}")
        return None
    finally:
        if conn:
            conn.close()

def search_policies(level=None, keywords=None, start_date=None, end_date=None):
    """搜索政策，支持时间区间"""
    conn = get_conn()
    c = conn.cursor()
    params = []
    date_sql = ''
    
    if start_date and end_date:
        date_sql = ' AND p.pub_date BETWEEN ? AND ?'
        params.extend([start_date, end_date])
    
    if keywords:
        # 使用全文检索
        if level:
            query = f"level:{level} AND ({' OR '.join(keywords)})"
        else:
            query = ' OR '.join(keywords)
        sql = f'''SELECT p.id, p.level, p.title, p.pub_date, p.source, p.content, p.category 
                  FROM policy p JOIN policy_fts fts ON p.id = fts.rowid 
                  WHERE policy_fts MATCH ?{date_sql} ORDER BY p.pub_date DESC'''
        c.execute(sql, (query, *params))
    else:
        # 普通查询
        if level:
            sql = f'''SELECT id, level, title, pub_date, source, content, category 
                      FROM policy p WHERE level = ?{date_sql} ORDER BY pub_date DESC'''
            c.execute(sql, (level, *params))
        else:
            sql = f'''SELECT id, level, title, pub_date, source, content, category 
                      FROM policy p WHERE 1=1{date_sql} ORDER BY pub_date DESC'''
            c.execute(sql, (*params,))
    
    results = c.fetchall()
    conn.close()
    return results

def get_policy_by_id(policy_id):
    """根据ID获取政策详情"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM policy WHERE id = ?', (policy_id,))
    result = c.fetchone()
    conn.close()
    return result

def get_database_info():
    """获取数据库信息"""
    try:
        conn = get_conn()
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
        
        conn.close()
        
        return {
            'policy_count': policy_count,
            'latest_date': latest_date,
            'file_size': file_size,
            'file_size_mb': round(float(file_size) / (1024 * 1024), 2),
            'last_backup_time': last_backup_time,
            'database_path': db_path,
            'backup_dir': get_backup_dir()
        }
    except Exception as e:
        print(f"获取数据库信息失败: {e}")
        return {}

def restore_database(backup_file):
    """从备份文件恢复数据库"""
    try:
        db_path = get_database_path()
        backup_path = os.path.join(get_backup_dir(), backup_file)
        
        if not os.path.exists(backup_path):
            print(f"备份文件不存在: {backup_path}")
            return False
        
        # 备份当前数据库
        if os.path.exists(db_path):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            current_backup = os.path.join(get_backup_dir(), f"before_restore_{timestamp}.db")
            shutil.copy2(db_path, current_backup)
            print(f"当前数据库已备份到: {current_backup}")
        
        # 恢复数据库
        shutil.copy2(backup_path, db_path)
        print(f"数据库恢复完成: {backup_path}")
        return True
    except Exception as e:
        print(f"数据库恢复失败: {e}")
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
                    print(f"处理文件 {filename} 时出错: {e}")
                    # 跳过有问题的文件
                    continue
        
        # 按时间倒序排序
        backup_files.sort(key=lambda x: x['file_time'], reverse=True)
        return backup_files
    except Exception as e:
        print(f"获取备份文件列表失败: {e}")
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