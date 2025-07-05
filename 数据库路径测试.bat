@echo off
chcp 65001 >nul
echo ========================================
echo 数据库路径测试工具
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

echo 正在测试数据库路径配置...
echo.

:: 创建临时Python脚本
echo import sys > temp_db_test.py
echo import os >> temp_db_test.py
echo. >> temp_db_test.py
echo def get_database_path(): >> temp_db_test.py
echo     if getattr(sys, 'frozen', False): >> temp_db_test.py
echo         user_docs = os.path.expanduser("~/Documents") >> temp_db_test.py
echo         app_data_dir = os.path.join(user_docs, "空间规划政策爬虫系统") >> temp_db_test.py
echo         if not os.path.exists(app_data_dir): >> temp_db_test.py
echo             os.makedirs(app_data_dir) >> temp_db_test.py
echo         return os.path.join(app_data_dir, "policy.db") >> temp_db_test.py
echo     else: >> temp_db_test.py
echo         return os.path.join("src", "space_planning", "core", "policy.db") >> temp_db_test.py
echo. >> temp_db_test.py
echo def test_database_access(): >> temp_db_test.py
echo     print("=== 数据库路径测试 ===") >> temp_db_test.py
echo     print() >> temp_db_test.py
echo     # 测试路径获取 >> temp_db_test.py
echo     db_path = get_database_path() >> temp_db_test.py
echo     print(f"数据库路径: {db_path}") >> temp_db_test.py
echo     print(f"路径存在: {os.path.exists(db_path)}") >> temp_db_test.py
echo     print(f"目录存在: {os.path.exists(os.path.dirname(db_path))}") >> temp_db_test.py
echo     print() >> temp_db_test.py
echo     # 测试数据库连接 >> temp_db_test.py
echo     try: >> temp_db_test.py
echo         import sqlite3 >> temp_db_test.py
echo         conn = sqlite3.connect(db_path) >> temp_db_test.py
echo         cursor = conn.cursor() >> temp_db_test.py
echo         cursor.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)") >> temp_db_test.py
echo         cursor.execute("INSERT INTO test_table (id) VALUES (1)") >> temp_db_test.py
echo         cursor.execute("SELECT * FROM test_table") >> temp_db_test.py
echo         result = cursor.fetchone() >> temp_db_test.py
echo         cursor.execute("DROP TABLE test_table") >> temp_db_test.py
echo         conn.commit() >> temp_db_test.py
echo         conn.close() >> temp_db_test.py
echo         print("✓ 数据库连接测试成功") >> temp_db_test.py
echo         print("✓ 数据库读写测试成功") >> temp_db_test.py
echo     except Exception as e: >> temp_db_test.py
echo         print(f"✗ 数据库测试失败: {e}") >> temp_db_test.py
echo     print() >> temp_db_test.py
echo     # 显示环境信息 >> temp_db_test.py
echo     print("=== 环境信息 ===") >> temp_db_test.py
echo     print(f"Python版本: {sys.version}") >> temp_db_test.py
echo     print(f"是否打包环境: {getattr(sys, 'frozen', False)}") >> temp_db_test.py
echo     print(f"当前工作目录: {os.getcwd()}") >> temp_db_test.py
echo     print(f"用户文档目录: {os.path.expanduser('~/Documents')}") >> temp_db_test.py
echo. >> temp_db_test.py
echo if __name__ == "__main__": >> temp_db_test.py
echo     test_database_access() >> temp_db_test.py

:: 运行测试脚本
python temp_db_test.py

:: 清理临时文件
del temp_db_test.py

echo.
echo ========================================
echo 测试完成！
echo ========================================
echo.
echo 如果数据库测试失败，可能的原因：
echo 1. 目录权限不足
echo 2. 磁盘空间不足
echo 3. 防病毒软件阻止
echo 4. 路径包含特殊字符
echo.

pause 