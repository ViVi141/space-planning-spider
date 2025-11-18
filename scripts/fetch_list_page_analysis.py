"""
直接获取列表页进行分析
"""
import os
import sys
import requests
import time
from bs4 import BeautifulSoup

# 调整路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
sys.path.append(PROJECT_ROOT)

from src.space_planning.spider.guangdong import GuangdongSpider

def fetch_list_page(category_code='XM0701', issue_department_lvalue='81903', page_index=1):
    """获取列表页HTML"""
    spider = GuangdongSpider(disable_proxy=True)
    
    # 获取API配置
    api_config = spider._get_category_api_config(category_code)
    print(f"API配置: {api_config}")
    
    # 初始化会话（模拟_crawl_category_by_department的流程）
    try:
        init_url = api_config.get('init_page', f"{spider.base_url}/{api_config['menu']}/adv")
        print(f"\n步骤1: 初始化会话 - 访问 {init_url}")
        init_resp, _ = spider._session_get(init_url, timeout=10)
        if init_resp and init_resp.status_code == 200:
            print(f"  会话初始化成功 (状态码: {init_resp.status_code})")
        time.sleep(0.5)
    except Exception as e:
        print(f"  会话初始化失败: {e}")
    
    # 发送ClassSearch（模拟_crawl_category_by_department的流程）
    try:
        class_search_url = api_config.get('class_search_url', f"{spider.base_url}/{api_config['menu']}/search/ClassSearch")
        class_params = {
            'Menu': api_config['menu'],
            'Library': api_config['library'],
            'ClassFlag': api_config['class_flag'],
            'IsAdv': 'False',
            'ClassCodeKey': f',,,{category_code},,,',
        }
        headers = spider.headers.copy()
        headers['Referer'] = api_config.get('referer', f"{spider.base_url}/{api_config['menu']}/adv")
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        headers['X-Requested-With'] = 'XMLHttpRequest'
        
        print(f"\n步骤2: 发送ClassSearch - {class_search_url}")
        print(f"  ClassSearch参数: {class_params}")
        class_resp, _ = spider._session_post(class_search_url, data=class_params, headers=headers, timeout=10)
        if class_resp and class_resp.status_code == 200:
            print(f"  ClassSearch成功 (状态码: {class_resp.status_code}, 内容长度: {len(class_resp.text)})")
        time.sleep(0.3)
    except Exception as e:
        print(f"  ClassSearch失败: {e}")
    
    # 获取搜索参数
    search_params = spider._get_search_parameters(
        keywords=None,
        category_code=category_code,
        page_index=page_index,
        page_size=20,
        start_date=None,
        end_date=None,
        filter_year=None,
        api_config=api_config,
        issue_department_lvalue=issue_department_lvalue
    )
    
    print(f"\n搜索参数:")
    for key, value in search_params.items():
        if value:  # 只显示非空参数
            print(f"  {key}: {value}")
    
    # 发送请求
    search_url = api_config.get('search_url', f"{spider.base_url}/{api_config['menu']}/search/RecordSearch")
    headers = spider.headers.copy()
    if api_config.get('referer'):
        headers['Referer'] = api_config['referer']
    headers.update({
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
    })
    
    print(f"\n请求URL: {search_url}")
    print(f"请求Headers: {dict(headers)}")
    
    try:
        resp, _ = spider._session_post(search_url, data=search_params, headers=headers, timeout=20)
        print(f"\n响应状态码: {resp.status_code}")
        print(f"响应内容长度: {len(resp.text)} 字符")
        
        # 保存HTML
        output_dir = os.path.join(PROJECT_ROOT, 'analysis_pages', 'guangdong', 'list_pages')
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"list_page_{category_code}_{issue_department_lvalue}_page{page_index}.html"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(resp.text)
        
        print(f"\nHTML已保存到: {filepath}")
        
        # 分析HTML结构
        analyze_html_structure(resp.text, filepath)
        
        return resp.text
        
    except Exception as e:
        print(f"请求失败: {e}", exc_info=True)
        return None

def analyze_html_structure(html_content, filepath):
    """分析HTML结构"""
    print("\n" + "="*80)
    print("HTML结构分析")
    print("="*80)
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. 检查checkbox
    checkboxes = soup.select('input.checkbox[name="recordList"]')
    print(f"\n1. Checkbox元素:")
    print(f"   找到 {len(checkboxes)} 个 checkbox")
    if checkboxes:
        for i, cb in enumerate(checkboxes[:3]):  # 只显示前3个
            print(f"   [{i+1}] value={cb.get('value', '')[:50]}")
    
    # 2. 检查list-title
    list_titles = soup.find_all('div', class_='list-title')
    print(f"\n2. list-title元素:")
    print(f"   找到 {len(list_titles)} 个 list-title")
    if list_titles:
        for i, lt in enumerate(list_titles[:3]):  # 只显示前3个
            title_text = lt.get_text(strip=True)[:50]
            print(f"   [{i+1}] {title_text}")
    
    # 3. 检查checkbox容器
    checkbox_containers = soup.find_all('div', class_='checkbox')
    print(f"\n3. checkbox容器:")
    print(f"   找到 {len(checkbox_containers)} 个 checkbox容器")
    
    # 4. 检查所有input元素
    all_inputs = soup.find_all('input')
    print(f"\n4. 所有input元素:")
    print(f"   找到 {len(all_inputs)} 个 input")
    checkbox_inputs = [inp for inp in all_inputs if 'checkbox' in inp.get('class', [])]
    print(f"   其中 checkbox 类型: {len(checkbox_inputs)} 个")
    
    # 5. 检查是否有错误信息
    error_messages = soup.find_all(text=lambda t: t and ('错误' in t or '失败' in t or '未找到' in t))
    if error_messages:
        print(f"\n5. 可能的错误信息:")
        for msg in error_messages[:5]:
            print(f"   - {msg.strip()[:100]}")
    
    # 6. 检查是否有数据表格或列表
    tables = soup.find_all('table')
    print(f"\n6. 表格元素:")
    print(f"   找到 {len(tables)} 个 table")
    
    lists = soup.find_all(['ul', 'ol'])
    print(f"   找到 {len(lists)} 个列表 (ul/ol)")
    
    # 7. 检查是否有分页信息
    pagers = soup.find_all(class_=lambda x: x and ('page' in str(x).lower() or 'pager' in str(x).lower()))
    print(f"\n7. 分页元素:")
    print(f"   找到 {len(pagers)} 个分页相关元素")
    
    # 8. 检查是否有政策链接
    policy_links = soup.find_all('a', href=lambda x: x and ('.html' in x or 'policy' in x.lower() or 'record' in x.lower()))
    print(f"\n8. 政策链接:")
    print(f"   找到 {len(policy_links)} 个可能的政策链接")
    if policy_links:
        for i, link in enumerate(policy_links[:5]):  # 只显示前5个
            href = link.get('href', '')[:80]
            text = link.get_text(strip=True)[:50]
            print(f"   [{i+1}] {text} -> {href}")
    
    # 9. 保存HTML片段用于调试
    debug_file = filepath.replace('.html', '_debug.txt')
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("HTML结构摘要\n")
        f.write("="*80 + "\n\n")
        f.write(f"总字符数: {len(html_content)}\n")
        f.write(f"Checkbox数量: {len(checkboxes)}\n")
        f.write(f"list-title数量: {len(list_titles)}\n")
        f.write(f"政策链接数量: {len(policy_links)}\n\n")
        
        # 保存前5000字符用于查看
        f.write("HTML前5000字符:\n")
        f.write("-"*80 + "\n")
        f.write(html_content[:5000])
        f.write("\n\n")
        
        # 如果有list-title，保存第一个的完整HTML
        if list_titles:
            f.write("第一个list-title的完整HTML:\n")
            f.write("-"*80 + "\n")
            f.write(str(list_titles[0]))
            f.write("\n\n")
        
        # 如果有checkbox，保存第一个的父元素HTML
        if checkboxes:
            parent = checkboxes[0].find_parent()
            if parent:
                f.write("第一个checkbox的父元素HTML:\n")
                f.write("-"*80 + "\n")
                f.write(str(parent)[:2000])
                f.write("\n\n")
    
    print(f"\n调试信息已保存到: {debug_file}")

def main():
    """主函数"""
    print("="*80)
    print("获取列表页进行分析")
    print("="*80)
    
    # 测试省级地方性法规
    print("\n测试1: 省级地方性法规 (XM0701, lvalue=81903)")
    html1 = fetch_list_page('XM0701', '81903', 1)
    
    time.sleep(2)
    
    # 测试设区的市地方性法规
    print("\n\n测试2: 设区的市地方性法规 (XM0702, lvalue=81937)")
    html2 = fetch_list_page('XM0702', '81937', 1)
    
    time.sleep(2)
    
    # 测试规范性文件
    print("\n\n测试3: 地方规范性文件 (XP08, lvalue=81937)")
    html3 = fetch_list_page('XP08', '81937', 1)
    
    print("\n" + "="*80)
    print("分析完成！")
    print("="*80)

if __name__ == '__main__':
    main()

