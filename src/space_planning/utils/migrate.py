#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移工具
"""

import os
import sys
import sqlite3
import shutil
from datetime import datetime

def find_old_database():
    """查找旧版本的数据库文件"""
    old_locations = []
    
    # 1. 检查当前目录
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    old_db_path = os.path.join(current_dir, 'src', 'space_planning', 'core', 'policy.db')
    if os.path.exists(old_db_path):
        old_locations.append(('开发环境数据库', old_db_path))
    
    # 2. 检查程序目录
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        old_db_path = os.path.join(exe_dir, 'policy.db')
        if os.path.exists(old_db_path):
            old_locations.append(('程序目录数据库', old_db_path))
    
    # 3. 检查用户文档目录（旧版本可能已经存在）
    user_docs = os.path.expanduser("~/Documents")
    old_app_dir = os.path.join(user_docs, "空间规划政策爬虫系统")
    if os.path.exists(old_app_dir):
        old_db_path = os.path.join(old_app_dir, "policy.db")
        if os.path.exists(old_db_path):
            old_locations.append(('用户文档数据库', old_db_path))
    
    return old_locations

def migrate_database(old_db_path, new_db_path):
    """迁移数据库"""
    try:
        # 备份旧数据库
        backup_path = old_db_path + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(old_db_path, backup_path)
        print(f"旧数据库已备份到: {backup_path}")
        
        # 连接旧数据库
        old_conn = sqlite3.connect(old_db_path)
        old_cursor = old_conn.cursor()
        
        # 连接新数据库
        new_conn = sqlite3.connect(new_db_path)
        new_cursor = new_conn.cursor()
        
        # 检查旧数据库表结构
        old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        old_tables = [row[0] for row in old_cursor.fetchall()]
        
        print(f"发现旧数据库表: {old_tables}")
        
        # 迁移政策数据
        if 'policy' in old_tables:
            old_cursor.execute("SELECT COUNT(*) FROM policy")
            policy_count = old_cursor.fetchone()[0]
            print(f"发现 {policy_count} 条政策数据")
            
            if policy_count > 0:
                # 获取所有政策数据
                old_cursor.execute("SELECT level, title, pub_date, source, content, crawl_time FROM policy")
                policies = old_cursor.fetchall()
                
                # 插入到新数据库
                migrated_count = 0
                for policy in policies:
                    try:
                        new_cursor.execute('''
                            INSERT OR IGNORE INTO policy (level, title, pub_date, source, content, crawl_time)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', policy)
                        if new_cursor.rowcount > 0:
                            migrated_count += 1
                    except Exception as e:
                        print(f"迁移政策失败: {policy[1]} - {e}")
                
                print(f"成功迁移 {migrated_count} 条政策数据")
        
        # 迁移全文检索数据
        if 'policy_fts' in old_tables:
            print("迁移全文检索数据...")
            try:
                # 重新构建全文检索索引
                new_cursor.execute("DELETE FROM policy_fts")
                new_cursor.execute("""
                    INSERT INTO policy_fts(rowid, title, content, level)
                    SELECT id, title, content, level FROM policy
                """)
                print("全文检索数据迁移完成")
            except Exception as e:
                print(f"全文检索数据迁移失败: {e}")
        
        # 提交更改
        new_conn.commit()
        
        # 关闭连接
        old_conn.close()
        new_conn.close()
        
        print(f"数据库迁移完成: {old_db_path} -> {new_db_path}")
        return True
        
    except Exception as e:
        print(f"数据库迁移失败: {e}")
        return False

def check_database_integrity(db_path):
    """检查数据库完整性"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        if 'policy' not in tables:
            print("错误: 缺少policy表")
            return False
        
        # 检查政策数量
        cursor.execute("SELECT COUNT(*) FROM policy")
        policy_count = cursor.fetchone()[0]
        print(f"政策数量: {policy_count}")
        
        # 检查全文检索
        if 'policy_fts' in tables:
            cursor.execute("SELECT COUNT(*) FROM policy_fts")
            fts_count = cursor.fetchone()[0]
            print(f"全文检索条目: {fts_count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"数据库完整性检查失败: {e}")
        return False

def main():
    """主函数"""
    print("=== 数据库迁移工具 ===")
    print()
    
    # 查找旧数据库
    old_locations = find_old_database()
    
    if not old_locations:
        print("未找到需要迁移的旧数据库")
        return
    
    print("发现以下旧数据库:")
    for i, (desc, path) in enumerate(old_locations, 1):
        print(f"{i}. {desc}: {path}")
    print()
    
    # 获取新数据库路径
    from space_planning.core import config
    new_db_path = config.app_config.get_database_path()
    print(f"新数据库路径: {new_db_path}")
    print()
    
    # 询问用户是否迁移
    while True:
        choice = input("是否要迁移数据库？(y/n): ").lower().strip()
        if choice in ['y', 'yes', '是']:
            break
        elif choice in ['n', 'no', '否']:
            print("取消迁移")
            return
        else:
            print("请输入 y 或 n")
    
    # 选择要迁移的数据库
    if len(old_locations) > 1:
        while True:
            try:
                choice = int(input(f"请选择要迁移的数据库 (1-{len(old_locations)}): "))
                if 1 <= choice <= len(old_locations):
                    selected_db = old_locations[choice - 1]
                    break
                else:
                    print(f"请输入 1-{len(old_locations)} 之间的数字")
            except ValueError:
                print("请输入有效的数字")
    else:
        selected_db = old_locations[0]
    
    desc, old_db_path = selected_db
    print(f"选择迁移: {desc}")
    print()
    
    # 检查新数据库是否已存在
    if os.path.exists(new_db_path):
        print("警告: 新数据库已存在")
        while True:
            choice = input("是否要覆盖现有数据库？(y/n): ").lower().strip()
            if choice in ['y', 'yes', '是']:
                break
            elif choice in ['n', 'no', '否']:
                print("取消迁移")
                return
            else:
                print("请输入 y 或 n")
    
    # 执行迁移
    print("开始迁移数据库...")
    success = migrate_database(old_db_path, new_db_path)
    
    if success:
        print()
        print("=== 迁移完成 ===")
        print("正在验证数据库完整性...")
        
        if check_database_integrity(new_db_path):
            print("数据库完整性检查通过")
            print()
            print("迁移成功！现在您可以:")
            print("1. 启动应用程序")
            print("2. 在'工具 -> 数据库管理'中查看数据状态")
            print("3. 旧数据库已备份，可以安全删除")
        else:
            print("警告: 数据库完整性检查失败")
    else:
        print("迁移失败，请检查错误信息")

if __name__ == "__main__":
    main() 