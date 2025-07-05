import sqlite3
import os

def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), 'policy.db')
    return sqlite3.connect(db_path)

def init_db():
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
            crawl_time TEXT
        )
    ''')
    # 创建全文检索表
    c.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS policy_fts USING fts5(
            title, content, level, content='policy', content_rowid='id'
        )
    ''')
    conn.commit()
    conn.close()

def insert_policy(level, title, pub_date, source, content, crawl_time):
    conn = None
    try:
        conn = get_conn()
        c = conn.cursor()
        # 去重：同title和pub_date不重复插入
        c.execute('SELECT id FROM policy WHERE title=? AND pub_date=?', (title, pub_date))
        if c.fetchone():
            return None
        c.execute('''INSERT INTO policy (level, title, pub_date, source, content, crawl_time)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (level, title, pub_date, source, content, crawl_time))
        rowid = c.lastrowid
        # 同步到FTS表
        c.execute('INSERT INTO policy_fts(rowid, title, content, level) VALUES (?, ?, ?, ?)',
                  (rowid, title, content, level))
        conn.commit()
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
        if level and level != "全部机构":
            query = f"level:{level} AND ({' OR '.join(keywords)})"
        else:
            query = ' OR '.join(keywords)
        sql = f'''SELECT p.id, p.level, p.title, p.pub_date, p.source, p.content 
                  FROM policy p JOIN policy_fts fts ON p.id = fts.rowid 
                  WHERE policy_fts MATCH ?{date_sql} ORDER BY p.pub_date DESC'''
        c.execute(sql, (query, *params))
    else:
        # 普通查询
        if level and level != "全部机构":
            sql = f'''SELECT id, level, title, pub_date, source, content 
                      FROM policy p WHERE level = ?{date_sql} ORDER BY pub_date DESC'''
            c.execute(sql, (level, *params))
        else:
            sql = f'''SELECT id, level, title, pub_date, source, content 
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

class DatabaseManager:
    """数据库管理类"""
    
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), 'policy.db')
    
    def get_conn(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        """初始化数据库"""
        conn = self.get_conn()
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
                crawl_time TEXT
            )
        ''')
        # 创建全文检索表
        c.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS policy_fts USING fts5(
                title, content, level, content='policy', content_rowid='id'
            )
        ''')
        conn.commit()
        conn.close()
    
    def insert_policy(self, level, title, pub_date, source, content, crawl_time):
        """插入政策数据"""
        conn = None
        try:
            conn = self.get_conn()
            c = conn.cursor()
            # 去重：同title和pub_date不重复插入
            c.execute('SELECT id FROM policy WHERE title=? AND pub_date=?', (title, pub_date))
            if c.fetchone():
                return None
            c.execute('''INSERT INTO policy (level, title, pub_date, source, content, crawl_time)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (level, title, pub_date, source, content, crawl_time))
            rowid = c.lastrowid
            # 同步到FTS表
            c.execute('INSERT INTO policy_fts(rowid, title, content, level) VALUES (?, ?, ?, ?)',
                      (rowid, title, content, level))
            conn.commit()
            return rowid
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"插入政策失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def search_policies(self, level=None, keywords=None, start_date=None, end_date=None):
        """搜索政策，支持时间区间"""
        conn = self.get_conn()
        c = conn.cursor()
        params = []
        date_sql = ''
        if start_date and end_date:
            date_sql = ' AND p.pub_date BETWEEN ? AND ?'
            params.extend([start_date, end_date])
        if keywords:
            # 使用全文检索
            if level and level != "全部机构":
                query = f"level:{level} AND ({' OR '.join(keywords)})"
            else:
                query = ' OR '.join(keywords)
            sql = f'''SELECT p.id, p.level, p.title, p.pub_date, p.source, p.content 
                      FROM policy p JOIN policy_fts fts ON p.id = fts.rowid 
                      WHERE policy_fts MATCH ?{date_sql} ORDER BY p.pub_date DESC'''
            c.execute(sql, (query, *params))
        else:
            # 普通查询
            if level and level != "全部机构":
                sql = f'''SELECT id, level, title, pub_date, source, content 
                          FROM policy p WHERE level = ?{date_sql} ORDER BY pub_date DESC'''
                c.execute(sql, (level, *params))
            else:
                sql = f'''SELECT id, level, title, pub_date, source, content 
                          FROM policy p WHERE 1=1{date_sql} ORDER BY pub_date DESC'''
                c.execute(sql, (*params,))
        results = c.fetchall()
        conn.close()
        return results
    
    def get_policy_by_id(self, policy_id):
        """根据ID获取政策详情"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('SELECT * FROM policy WHERE id = ?', (policy_id,))
        result = c.fetchone()
        conn.close()
        return result 