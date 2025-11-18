"""
手动获取省级地方性法规（XM0701）的第4页和第5页进行分析
"""
import os
import sys
import requests
import time
from bs4 import BeautifulSoup
import json

# 调整路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
sys.path.append(PROJECT_ROOT)

from src.space_planning.spider.guangdong import GuangdongSpider

BASE_URL = 'https://gd.pkulaw.com'

def fetch_page(category_code='XM0701', issue_department_lvalue='81901', page_index=1):
    """获取指定页面 - 按照guangdong.py的策略"""
    print(f"\n{'='*80}")
    print(f"获取第 {page_index} 页")
    print(f"{'='*80}")
    
    spider = GuangdongSpider(disable_proxy=True)
    
    # 获取API配置
    api_config = spider._get_category_api_config(category_code)
    spider.current_api_config = api_config
    print(f"API配置: {api_config}")
    
    # 按照_crawl_category_by_department的策略：
    # 1. 初始化会话
    try:
        init_url = api_config.get('init_page', f"{BASE_URL}/{api_config['menu']}/adv")
        print(f"初始化会话: 访问 {init_url}")
        init_resp, _ = spider._session_get(init_url, timeout=10)
        if init_resp and init_resp.status_code == 200:
            print(f"[OK] 会话初始化成功")
        time.sleep(0.5)
    except Exception as e:
        print(f"[WARN] 会话初始化失败（继续尝试）: {e}")
    
    # 2. 获取搜索参数（按照_crawl_category_by_department的方式）
    effective_lvalue = issue_department_lvalue if issue_department_lvalue else None
    search_params = spider._get_search_parameters(
        keywords=None,
        category_code=category_code,
        page_index=page_index,
        page_size=20,
        start_date=None,
        end_date=None,
        filter_year=None,  # 不使用年份筛选
        api_config=api_config,
        issue_department_lvalue=effective_lvalue
    )
    
    print(f"\n搜索参数:")
    for key, value in search_params.items():
        if value:  # 只显示非空参数
            print(f"  {key}: {value}")
    
    # 3. 使用带翻页校验的请求方法（按照_crawl_category_by_department的方式）
    prev_page_index = page_index - 1 if page_index > 1 else None
    print(f"\n使用带翻页校验的请求方法...")
    print(f"  当前页: {page_index}")
    print(f"  上一页: {prev_page_index}")
    
    resp = spider._request_page_with_check(
        page_index,
        search_params,
        prev_page_index,
        api_config=api_config
    )
    
    if not resp:
        print(f"[FAIL] 请求失败，无响应")
        return None
    
    if resp.status_code != 200:
        print(f"[FAIL] HTTP {resp.status_code}")
        print(f"响应内容前500字符: {resp.text[:500]}")
        return None
    
    print(f"[OK] HTTP {resp.status_code}")
    print(f"响应长度: {len(resp.text)} 字符")
    
    # 保存响应
    output_dir = os.path.join(PROJECT_ROOT, 'analysis_pages', 'guangdong', 'page_analysis')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'xm0701_page_{page_index}.html')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(resp.text)
    print(f"已保存到: {output_file}")
    
    # 解析响应
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # 检查是否有数据
    no_content = soup.find('div', class_='search-no-content')
    if no_content:
        print(f"[WARN] 发现search-no-content")
        print(f"  内容: {no_content.get_text(strip=True)[:200]}")
    
    # 获取总数
    total_span = soup.find('h3', string=lambda s: s and '总共检索到' in s if s else False)
    total = None
    if total_span:
        total_text = total_span.get_text()
        import re
        match = re.search(r'(\d+)', total_text)
        if match:
            total = int(match.group(1))
            print(f"[OK] 总共检索到 {total} 篇")
    
    # 4. 使用_parse_policy_list_html解析（按照_crawl_category_by_department的方式）
    # 注意：这里只解析列表，不获取详情，所以传入policy_callback=None
    # 但实际上_parse_policy_list_html会尝试获取详情，我们需要修改策略
    # 为了只解析列表，我们直接使用_parse_policy_list_record_search
    print(f"\n解析政策列表...")
    page_policies = spider._parse_policy_list_record_search(
        soup,
        callback=None,
        stop_callback=None,
        category_name='省级地方性法规'
    )
    
    # 如果备用方法也失败，尝试checkbox方法（但不获取详情）
    if not page_policies:
        print("[WARN] 备用解析方法失败，尝试checkbox方法...")
        checkboxes = soup.select('input.checkbox[name="recordList"]')
        print(f"找到 {len(checkboxes)} 个checkbox元素")
        
        for checkbox in checkboxes:
            policy_id = checkbox.get('value', '').strip()
            if policy_id:
                # 只提取基本信息，不获取详情
                row = checkbox.find_parent('tr')
                if row:
                    title_elem = row.select_one('div.list-title h4 a, h4 a, a.title')
                    if title_elem:
                        policy = {
                            'title': title_elem.get_text(strip=True),
                            'url': title_elem.get('href', ''),
                            'policy_id': policy_id,
                            'doc_number': '',  # 列表页可能没有文档号
                            'pub_date': ''
                        }
                        page_policies.append(policy)
    
    print(f"[OK] 解析到 {len(page_policies)} 条政策")
    
    # 显示前5条政策的标题和文档号
    print(f"\n前5条政策:")
    for i, policy in enumerate(page_policies[:5], 1):
        title = policy.get('title', '').strip()
        doc_number = policy.get('doc_number', '').strip()
        pub_date = policy.get('pub_date', '').strip()
        print(f"  {i}. {title[:60]}...")
        print(f"     文档号: {doc_number}, 发布日期: {pub_date}")
    
    # 生成政策标识列表（用于比较）
    policy_identifiers = []
    for policy in page_policies:
        title = policy.get('title', '').strip()
        doc_number = policy.get('doc_number', '').strip()
        identifier = f"{title}|{doc_number}"
        policy_identifiers.append(identifier)
    
    return {
        'page_index': page_index,
        'html_file': output_file,
        'total_count': total,
        'policy_count': len(page_policies),
        'policies': page_policies,
        'identifiers': policy_identifiers,
        'response_length': len(resp.text)
    }

def compare_pages(page4_data, page5_data):
    """比较两页数据"""
    print(f"\n{'='*80}")
    print("页面比较分析")
    print(f"{'='*80}")
    
    print(f"\n第4页:")
    print(f"  政策数量: {page4_data['policy_count']}")
    print(f"  响应长度: {page4_data['response_length']} 字符")
    
    print(f"\n第5页:")
    print(f"  政策数量: {page5_data['policy_count']}")
    print(f"  响应长度: {page5_data['response_length']} 字符")
    
    # 比较政策标识
    page4_ids = set(page4_data['identifiers'])
    page5_ids = set(page5_data['identifiers'])
    
    print(f"\n政策标识比较:")
    print(f"  第4页唯一标识数: {len(page4_ids)}")
    print(f"  第5页唯一标识数: {len(page5_ids)}")
    print(f"  相同标识数: {len(page4_ids & page5_ids)}")
    print(f"  第4页独有: {len(page4_ids - page5_ids)}")
    print(f"  第5页独有: {len(page5_ids - page4_ids)}")
    
    if page4_ids == page5_ids:
        print(f"\n[WARN] 第4页和第5页的政策标识完全相同！")
        print(f"  这可能是验证码限制导致的，或者网站返回了相同的页面")
    else:
        print(f"\n[OK] 第4页和第5页的政策不同")
        if len(page4_ids & page5_ids) > 0:
            print(f"  但有 {len(page4_ids & page5_ids)} 条相同的政策")
            print(f"\n相同的政策:")
            for identifier in list(page4_ids & page5_ids)[:5]:
                print(f"    - {identifier[:80]}...")
    
    # 检查响应内容相似度
    print(f"\n响应内容分析:")
    if page4_data['response_length'] == page5_data['response_length']:
        print(f"  [WARN] 响应长度完全相同: {page4_data['response_length']} 字符")
        print(f"  这强烈暗示两页内容可能完全相同")
    else:
        diff = abs(page4_data['response_length'] - page5_data['response_length'])
        print(f"  响应长度差异: {diff} 字符")
    
    # 检查是否有验证码相关提示
    print(f"\n验证码检测:")
    with open(page4_data['html_file'], 'r', encoding='utf-8') as f:
        page4_html = f.read()
    with open(page5_data['html_file'], 'r', encoding='utf-8') as f:
        page5_html = f.read()
    
    verifycode_tokens = ["验证码", "verification", "captcha", "请输入验证码"]
    page4_has_verifycode = any(token in page4_html for token in verifycode_tokens)
    page5_has_verifycode = any(token in page5_html for token in verifycode_tokens)
    
    print(f"  第4页包含验证码关键词: {page4_has_verifycode}")
    print(f"  第5页包含验证码关键词: {page5_has_verifycode}")
    
    if page5_has_verifycode:
        print(f"  [WARN] 第5页可能包含验证码限制提示")

def main():
    """主函数"""
    print("=" * 80)
    print("手动获取省级地方性法规（XM0701）的第4页和第5页进行分析")
    print("=" * 80)
    
    # 获取第4页
    page4_data = fetch_page(category_code='XM0701', issue_department_lvalue='81901', page_index=4)
    if not page4_data:
        print("[FAIL] 无法获取第4页")
        return
    
    time.sleep(3)  # 延迟避免请求过快
    
    # 获取第5页
    page5_data = fetch_page(category_code='XM0701', issue_department_lvalue='81901', page_index=5)
    if not page5_data:
        print("[FAIL] 无法获取第5页")
        return
    
    # 比较两页
    compare_pages(page4_data, page5_data)
    
    # 保存比较结果
    comparison_result = {
        'page4': {
            'page_index': page4_data['page_index'],
            'policy_count': page4_data['policy_count'],
            'response_length': page4_data['response_length'],
            'identifiers': page4_data['identifiers']
        },
        'page5': {
            'page_index': page5_data['page_index'],
            'policy_count': page5_data['policy_count'],
            'response_length': page5_data['response_length'],
            'identifiers': page5_data['identifiers']
        },
        'comparison': {
            'identical': page4_data['identifiers'] == page5_data['identifiers'],
            'common_count': len(set(page4_data['identifiers']) & set(page5_data['identifiers'])),
            'page4_unique': len(set(page4_data['identifiers']) - set(page5_data['identifiers'])),
            'page5_unique': len(set(page5_data['identifiers']) - set(page4_data['identifiers']))
        }
    }
    
    output_file = os.path.join(PROJECT_ROOT, 'analysis_pages', 'guangdong', 'page_analysis', 'comparison_result.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(comparison_result, f, ensure_ascii=False, indent=2)
    print(f"\n比较结果已保存到: {output_file}")
    
    print(f"\n{'='*80}")
    print("分析完成")
    print(f"{'='*80}")

if __name__ == '__main__':
    main()

