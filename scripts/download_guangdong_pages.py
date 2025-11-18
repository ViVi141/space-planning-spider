#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载广东省政策库各分类页面用于分析
"""

import os
import sys
import time
import requests
from pathlib import Path
from bs4 import BeautifulSoup

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_dir = os.path.join(project_root, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from space_planning.spider.spider_config import SpiderConfig

# 配置
BASE_URL = 'https://gd.pkulaw.com'
OUTPUT_DIR = os.path.join(project_root, 'analysis_pages', 'guangdong')

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 分类配置
CATEGORIES = {
    '地方性法规': {
        'code': 'XM07',
        'api': 'dfxfg',
        'sub_categories': [
            ('省级地方性法规', 'XM0701'),
            ('设区的市地方性法规', 'XM0702'),
            ('经济特区法规', 'XM0703'),
            ('自治条例和单行条例', 'XU13'),
        ]
    },
    '地方政府规章': {
        'code': 'XO08',
        'api': 'dfzfgz',
        'sub_categories': [
            ('省级地方政府规章', 'XO0802'),
            ('设区的市地方政府规章', 'XO0803'),
        ]
    },
    '规范性文件': {
        'code': 'XP08',
        'api': 'fljs',
        'sub_categories': [
            ('地方规范性文件', 'XP08'),
        ]
    }
}

# API路径映射
API_PATH_MAP = {
    'dfxfg': {'menu': 'dfxfg', 'library': 'gddifang', 'class_flag': 'gddifang'},
    'sfjs': {'menu': 'sfjs', 'library': 'regularation', 'class_flag': 'regularation'},
    'dfzfgz': {'menu': 'dfzfgz', 'library': 'gddigui', 'class_flag': 'gddigui'},
    'fljs': {'menu': 'fljs', 'library': 'gdnormativedoc', 'class_flag': 'gdnormativedoc'},
}

def get_session():
    """创建会话"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Origin': 'https://gd.pkulaw.com',
        'Referer': 'https://gd.pkulaw.com/dfxfg/adv',
    })
    return session

def download_adv_page(category_name, api_type, output_path):
    """下载高级搜索页面"""
    url = f"{BASE_URL}/{api_type}/adv"
    print(f"  下载高级搜索页: {url}")
    
    session = get_session()
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            print(f"  [OK] 已保存: {output_path}")
            return resp.text
        else:
            print(f"  [FAIL] 失败: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [FAIL] 错误: {e}")
        return None

def download_search_result(category_name, sub_category_name, category_code, api_type, page=1, output_path=None):
    """下载搜索结果页面"""
    api_config = API_PATH_MAP.get(api_type, API_PATH_MAP['dfxfg'])
    
    # 构建搜索参数
    search_params = {
        'Menu': api_config['menu'],
        'Keywords': '',
        'SearchKeywordType': 'Title',
        'MatchType': 'Exact',
        'RangeType': 'Piece',
        'Library': api_config['library'],
        'ClassFlag': api_config['class_flag'],
        'GroupLibraries': '',
        'QueryOnClick': 'False',
        'AfterSearch': 'False',
        'pdfStr': '',
        'pdfTitle': '',
        'IsAdv': 'True',
        'ClassCodeKey': f',,,{category_code},,,' if category_code else ',,,,,,',
        'GroupByIndex': '0',
        'OrderByIndex': '0',
        'ShowType': 'Default',
        'GroupValue': '',
        'AdvSearchDic.Title': '',
        'AdvSearchDic.CheckFullText': '',
        'AdvSearchDic.IssueDepartment': '',
        'AdvSearchDic.DocumentNO': '',
        'AdvSearchDic.IssueDate': '',
        'AdvSearchDic.ImplementDate': '',
        'AdvSearchDic.TimelinessDic': '',
        'AdvSearchDic.EffectivenessDic': '',
        'TitleKeywords': '',
        'FullTextKeywords': '',
        'Pager.PageIndex': str(page),
        'Pager.PageSize': '20',
        'QueryBase64Request': '',
        'VerifyCodeResult': '',
        'isEng': 'chinese',
        'OldPageIndex': '',
        'newPageIndex': str(page),
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    search_url = f"{BASE_URL}/{api_type}/search/RecordSearch"
    print(f"  下载搜索结果页: {search_url} (第{page}页)")
    
    session = get_session()
    session.headers.update({
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': f"{BASE_URL}/{api_type}/adv",
    })
    
    try:
        resp = session.post(search_url, data=search_params, timeout=20)
        if resp.status_code == 200:
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(resp.text)
                print(f"  [OK] 已保存: {output_path}")
            return resp.text
        else:
            print(f"  [FAIL] 失败: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [ERROR] 错误: {e}")
        return None

def download_policy_detail(policy_id, api_type, output_path):
    """下载政策详情页"""
    api_config = API_PATH_MAP.get(api_type, API_PATH_MAP['dfxfg'])
    library = api_config['library']
    url = f"{BASE_URL}/{library}/{policy_id}.html"
    
    print(f"  下载详情页: {url}")
    
    session = get_session()
    session.headers.update({
        'Referer': f"{BASE_URL}/{api_type}/adv",
    })
    
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            print(f"  [OK] 已保存: {output_path}")
            return resp.text
        else:
            print(f"  [FAIL] 失败: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [FAIL] 错误: {e}")
        return None

def extract_policy_ids_from_html(html_content):
    """从HTML中提取政策ID"""
    soup = BeautifulSoup(html_content, 'html.parser')
    policy_ids = []
    
    # 方法1: 从checkbox提取
    checkboxes = soup.select('input.checkbox[name="recordList"]')
    for checkbox in checkboxes:
        policy_id = checkbox.get('value', '').strip()
        if policy_id and len(policy_id) > 10:
            policy_ids.append(policy_id)
    
    # 方法2: 从链接提取
    if not policy_ids:
        links = soup.find_all('a', href=True)
        for link in links:
            href = link.get('href', '')
            # 匹配 /gddigui/xxx.html 或 /gddifang/xxx.html 等格式
            import re
            match = re.search(r'/(gddigui|gddifang|regularation|gdnormativedoc)/([^/]+)\.html', href)
            if match:
                policy_id = match.group(2)
                if policy_id not in policy_ids:
                    policy_ids.append(policy_id)
    
    return policy_ids[:10]  # 只返回前10个，用于分析

def main():
    """主函数"""
    print("=" * 60)
    print("广东省政策库页面下载工具")
    print("=" * 60)
    print()
    
    session = get_session()
    
    # 下载各个分类的页面
    for category_name, category_info in CATEGORIES.items():
        print(f"\n【{category_name}】")
        print("-" * 60)
        
        api_type = category_info['api']
        category_dir = os.path.join(OUTPUT_DIR, category_name)
        os.makedirs(category_dir, exist_ok=True)
        
        # 1. 下载高级搜索页
        adv_path = os.path.join(category_dir, 'adv_page.html')
        adv_html = download_adv_page(category_name, api_type, adv_path)
        time.sleep(2)
        
        # 2. 下载各个子分类的搜索结果
        for sub_category_name, sub_category_code in category_info['sub_categories']:
            print(f"\n  【{sub_category_name}】({sub_category_code})")
            
            sub_dir = os.path.join(category_dir, sub_category_name.replace('/', '_'))
            os.makedirs(sub_dir, exist_ok=True)
            
            # 下载第1页搜索结果
            search_path = os.path.join(sub_dir, 'search_page_1.html')
            search_html = download_search_result(
                category_name, sub_category_name, sub_category_code, 
                api_type, page=1, output_path=search_path
            )
            time.sleep(3)
            
            if search_html:
                # 提取政策ID
                policy_ids = extract_policy_ids_from_html(search_html)
                print(f"  提取到 {len(policy_ids)} 个政策ID")
                
                # 下载前3个政策的详情页（用于分析）
                for i, policy_id in enumerate(policy_ids[:3], 1):
                    detail_path = os.path.join(sub_dir, f'detail_{i}_{policy_id}.html')
                    download_policy_detail(policy_id, api_type, detail_path)
                    time.sleep(2)
        
        print()
    
    print("\n" + "=" * 60)
    print("下载完成！")
    print(f"所有页面已保存到: {OUTPUT_DIR}")
    print("=" * 60)

if __name__ == '__main__':
    main()
