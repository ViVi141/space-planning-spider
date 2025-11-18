#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试发布机关搜索参数
"""

import os
import sys
import requests
from bs4 import BeautifulSoup

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_dir = os.path.join(project_root, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

BASE_URL = 'https://gd.pkulaw.com'

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
        'Referer': 'https://gd.pkulaw.com/fljs/adv',
    })
    return session

def test_issue_department_dialog(library='gdnormativedoc'):
    """测试获取发布机关可选值"""
    url = f"{BASE_URL}/foreigndialog?library={library}&property=IssueDepartment"
    print(f"测试发布机关对话框: {url}")
    
    session = get_session()
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            print(f"响应长度: {len(resp.text)}")
            # 保存响应用于分析
            output_path = os.path.join(project_root, 'analysis_pages', 'guangdong', f'issue_department_{library}.html')
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            print(f"已保存到: {output_path}")
            
            # 尝试解析
            soup = BeautifulSoup(resp.text, 'html.parser')
            # 查找可能的选项
            options = soup.find_all(['option', 'li', 'a'])
            print(f"找到 {len(options)} 个可能的选项")
            for opt in options[:20]:  # 只显示前20个
                text = opt.get_text(strip=True)
                value = opt.get('value', '')
                if text and ('广东省' in text or '中山市' in text):
                    print(f"  选项: {text} (value: {value})")
            return resp.text
        else:
            print(f"失败: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"错误: {e}")
        return None

def test_search_with_issue_department(issue_department_lvalue='81902'):
    """测试使用发布机关参数搜索（使用lvalue）"""
    print(f"\n测试使用发布机关搜索: lvalue={issue_department_lvalue}")
    
    search_params = {
        'Menu': 'fljs',
        'Keywords': '',
        'SearchKeywordType': 'Title',
        'MatchType': 'Fuzzy',
        'RangeType': 'Piece',
        'Library': 'gdnormativedoc',
        'ClassFlag': 'gdnormativedoc',
        'GroupLibraries': '',
        'QueryOnClick': 'False',
        'AfterSearch': 'False',
        'pdfStr': '',
        'pdfTitle': '',
        'IsAdv': 'True',
        'ClassCodeKey': ',,,,,,',
        'GroupByIndex': '0',
        'OrderByIndex': '0',
        'ShowType': 'Default',
        'GroupValue': '',
        'AdvSearchDic.Title': '',
        'AdvSearchDic.CheckFullText': '',
        'AdvSearchDic.IssueDepartment': issue_department_lvalue,  # 使用lvalue值
        'AdvSearchDic.DocumentNO': '',
        'AdvSearchDic.IssueDate': '',
        'AdvSearchDic.ImplementDate': '',
        'AdvSearchDic.TimelinessDic': '',
        'AdvSearchDic.EffectivenessDic': '',
        'TitleKeywords': '',
        'FullTextKeywords': '',
        'Pager.PageIndex': '1',
        'Pager.PageSize': '20',
        'QueryBase64Request': '',
        'VerifyCodeResult': '',
        'isEng': 'chinese',
        'OldPageIndex': '',
        'newPageIndex': '1',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    search_url = f"{BASE_URL}/fljs/search/RecordSearch"
    print(f"搜索URL: {search_url}")
    
    session = get_session()
    session.headers.update({
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': f"{BASE_URL}/fljs/adv",
    })
    
    try:
        resp = session.post(search_url, data=search_params, timeout=20)
        if resp.status_code == 200:
            # 保存响应
            output_path = os.path.join(project_root, 'analysis_pages', 'guangdong', f'search_with_issue_department_lvalue_{issue_department_lvalue}.html')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            print(f"已保存搜索结果到: {output_path}")
            
            # 解析结果
            soup = BeautifulSoup(resp.text, 'html.parser')
            checkboxes = soup.select('input.checkbox[name="recordList"]')
            print(f"找到 {len(checkboxes)} 个政策")
            
            # 显示前几个政策的标题
            titles = soup.select('div.list-title h4 a, h4 a')
            for i, title in enumerate(titles[:5], 1):
                print(f"  {i}. {title.get_text(strip=True)[:60]}...")
            
            return resp.text
        else:
            print(f"失败: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"错误: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("测试发布机关搜索参数")
    print("=" * 60)
    
    # 测试1: 获取发布机关可选值
    print("\n【测试1】获取发布机关可选值")
    print("-" * 60)
    test_issue_department_dialog('gdnormativedoc')
    test_issue_department_dialog('gddigui')
    test_issue_department_dialog('gddifang')
    
    # 测试2: 使用发布机关搜索（使用lvalue）
    print("\n【测试2】使用发布机关参数搜索（使用lvalue）")
    print("-" * 60)
    # 从HTML中看到的lvalue: 81902=广东省人民政府, 81901=广东省人大(含常委会)
    test_search_with_issue_department('81902')  # 广东省人民政府
    test_search_with_issue_department('81901')  # 广东省人大(含常委会)
    
    # 查找中山市的lvalue
    print("\n【测试3】查找中山市的发布机关lvalue")
    print("-" * 60)
    soup = BeautifulSoup(open(os.path.join(project_root, 'analysis_pages', 'guangdong', 'issue_department_gdnormativedoc.html'), encoding='utf-8').read(), 'html.parser')
    zhongshan_options = soup.find_all('option', string=lambda s: s and '中山' in s)
    for opt in zhongshan_options:
        lvalue = opt.get('lvalue', '')
        title = opt.get('title', '')
        print(f"  中山市选项: {title} (lvalue: {lvalue})")
        if lvalue:
            test_search_with_issue_department(lvalue)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
