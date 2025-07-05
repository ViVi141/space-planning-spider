@echo off
chcp 65001 >nul
echo ========================================
echo 网络诊断工具
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

echo 正在创建网络诊断脚本...
echo.

:: 创建临时Python脚本
echo import requests > temp_network_test.py
echo import urllib3 >> temp_network_test.py
echo import ssl >> temp_network_test.py
echo import certifi >> temp_network_test.py
echo import sys >> temp_network_test.py
echo import os >> temp_network_test.py
echo. >> temp_network_test.py
echo # 禁用SSL警告 >> temp_network_test.py
echo urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) >> temp_network_test.py
echo. >> temp_network_test.py
echo def test_network_connection(): >> temp_network_test.py
echo     print("=== 网络连接诊断 ===") >> temp_network_test.py
echo     print() >> temp_network_test.py
echo     # 测试目标URL >> temp_network_test.py
echo     test_urls = [ >> temp_network_test.py
echo         "https://www.baidu.com", >> temp_network_test.py
echo         "https://www.mohurd.gov.cn", >> temp_network_test.py
echo         "https://www.google.com" >> temp_network_test.py
echo     ] >> temp_network_test.py
echo     # 测试不同的SSL配置 >> temp_network_test.py
echo     ssl_configs = [ >> temp_network_test.py
echo         ("certifi证书", {"verify": certifi.where()}), >> temp_network_test.py
echo         ("系统证书", {"verify": True}), >> temp_network_test.py
echo         ("禁用验证", {"verify": False}) >> temp_network_test.py
echo     ] >> temp_network_test.py
echo     # 测试不同的代理配置 >> temp_network_test.py
echo     proxy_configs = [ >> temp_network_test.py
echo         ("无代理", {}), >> temp_network_test.py
echo         ("明确无代理", {"proxies": {"http": None, "https": None}}) >> temp_network_test.py
echo     ] >> temp_network_test.py
echo     for url in test_urls: >> temp_network_test.py
echo         print(f"测试URL: {url}") >> temp_network_test.py
echo         success = False >> temp_network_test.py
echo         for ssl_name, ssl_config in ssl_configs: >> temp_network_test.py
echo             for proxy_name, proxy_config in proxy_configs: >> temp_network_test.py
echo                 try: >> temp_network_test.py
echo                     config = {**ssl_config, **proxy_config} >> temp_network_test.py
echo                     response = requests.get(url, timeout=10, **config) >> temp_network_test.py
echo                     if response.status_code == 200: >> temp_network_test.py
echo                         print(f"  ✓ 成功 - {ssl_name} + {proxy_name}") >> temp_network_test.py
echo                         success = True >> temp_network_test.py
echo                         break >> temp_network_test.py
echo                     else: >> temp_network_test.py
echo                         print(f"  ✗ 状态码 {response.status_code} - {ssl_name} + {proxy_name}") >> temp_network_test.py
echo                 except Exception as e: >> temp_network_test.py
echo                     print(f"  ✗ 失败 - {ssl_name} + {proxy_name}: {str(e)[:50]}...") >> temp_network_test.py
echo             if success: >> temp_network_test.py
echo                 break >> temp_network_test.py
echo         if not success: >> temp_network_test.py
echo             print(f"  ❌ 所有配置都失败") >> temp_network_test.py
echo         print() >> temp_network_test.py
echo     # 测试系统环境 >> temp_network_test.py
echo     print("=== 系统环境信息 ===") >> temp_network_test.py
echo     print(f"Python版本: {sys.version}") >> temp_network_test.py
echo     print(f"操作系统: {os.name}") >> temp_network_test.py
echo     print(f"certifi版本: {certifi.__version__}") >> temp_network_test.py
echo     print(f"requests版本: {requests.__version__}") >> temp_network_test.py
echo     print(f"urllib3版本: {urllib3.__version__}") >> temp_network_test.py
echo     # 检查环境变量 >> temp_network_test.py
echo     print("\n=== 网络环境变量 ===") >> temp_network_test.py
echo     proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'] >> temp_network_test.py
echo     for var in proxy_vars: >> temp_network_test.py
echo         value = os.environ.get(var) >> temp_network_test.py
echo         if value: >> temp_network_test.py
echo             print(f"{var}: {value}") >> temp_network_test.py
echo         else: >> temp_network_test.py
echo             print(f"{var}: 未设置") >> temp_network_test.py
echo     # 提供建议 >> temp_network_test.py
echo     print("\n=== 建议 ===") >> temp_network_test.py
echo     print("1. 如果所有测试都失败，请检查网络连接") >> temp_network_test.py
echo     print("2. 如果只有某些配置成功，程序会自动选择最佳配置") >> temp_network_test.py
echo     print("3. 如果遇到SSL错误，程序会自动尝试禁用SSL验证") >> temp_network_test.py
echo     print("4. 如果遇到代理问题，程序会自动尝试不使用代理") >> temp_network_test.py
echo. >> temp_network_test.py
echo if __name__ == "__main__": >> temp_network_test.py
echo     test_network_connection() >> temp_network_test.py

:: 运行诊断脚本
python temp_network_test.py

:: 清理临时文件
del temp_network_test.py

echo.
echo ========================================
echo 诊断完成！
echo ========================================
echo.
echo 如果网络测试失败，请尝试以下解决方案：
echo 1. 检查网络连接是否正常
echo 2. 检查防火墙设置
echo 3. 检查代理设置
echo 4. 尝试使用VPN或更换网络环境
echo 5. 联系网络管理员
echo.

pause 