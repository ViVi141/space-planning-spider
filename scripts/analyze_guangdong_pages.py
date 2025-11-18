#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析广东省政策库页面结构，识别地区信息
"""

import os
import sys
import re
from pathlib import Path
from bs4 import BeautifulSoup
from collections import defaultdict

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
ANALYSIS_DIR = os.path.join(project_root, 'analysis_pages', 'guangdong')

# 地区关键词
PROVINCIAL_KEYWORDS = ['广东省', '粤府', '粤府办', '粤']
ZHONGSHAN_KEYWORDS = ['中山市', '中府', '中府办', '中']
EXCLUDE_CITY_KEYWORDS = [
    '广州市', '穗府', '穗府办',
    '深圳市', '深府', '深府办',
    '珠海市', '珠府', '珠府办',
    '汕头市', '汕府', '汕府办',
    '佛山市', '佛府', '佛府办',
    '韶关市', '韶府', '韶府办',
    '湛江市', '湛府', '湛府办',
    '肇庆市', '肇府', '肇府办',
    '江门市', '江府', '江府办',
    '茂名市', '茂府', '茂府办',
    '惠州市', '惠府', '惠府办',
    '梅州市', '梅府', '梅府办',
    '汕尾市', '汕府', '汕府办',
    '河源市', '河府', '河府办',
    '阳江市', '阳府', '阳府办',
    '清远市', '清府', '清府办',
    '东莞市', '东府', '东府办',
    '潮州市', '潮府', '潮府办',
    '揭阳市', '揭府', '揭府办',
    '云浮市', '云府', '云府办'
]

def analyze_search_page(html_path):
    """分析搜索结果页面"""
    print(f"\n分析搜索结果页: {html_path}")
    print("-" * 60)
    
    if not os.path.exists(html_path):
        print(f"文件不存在: {html_path}")
        return None
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 提取政策信息
    policies = []
    
    # 方法1: 从checkbox提取
    checkboxes = soup.select('input.checkbox[name="recordList"]')
    print(f"找到 {len(checkboxes)} 个checkbox")
    
    for checkbox in checkboxes[:5]:  # 只分析前5个
        policy_id = checkbox.get('value', '').strip()
        if policy_id:
            # 查找对应的政策项
            parent = checkbox.find_parent()
            if parent:
                policy_info = extract_policy_info_from_item(parent, policy_id)
                if policy_info:
                    policies.append(policy_info)
    
    # 方法2: 从列表项提取
    if not policies:
        items = soup.select('div.list-item, li.list-item, tr.list-item')
        print(f"找到 {len(items)} 个列表项")
        for item in items[:5]:
            policy_info = extract_policy_info_from_item(item, None)
            if policy_info:
                policies.append(policy_info)
    
    return policies

def extract_policy_info_from_item(item, policy_id=None):
    """从列表项中提取政策信息"""
    if not item:
        return None
    
    info = {
        'policy_id': policy_id,
        'title': '',
        'doc_number': '',
        'pub_date': '',
        'related_info': '',
        'url': ''
    }
    
    # 提取标题
    title_elem = item.find('a') or item.find('h4') or item.find('h3')
    if title_elem:
        info['title'] = title_elem.get_text(strip=True)
        info['url'] = title_elem.get('href', '')
    
    # 提取相关信息（related-info）
    related_info = item.find('div', class_='related-info')
    if related_info:
        info['related_info'] = related_info.get_text(strip=True)
        # 尝试从related-info中提取文号和日期
        parts = info['related_info'].split(' / ')
        if len(parts) >= 2:
            info['doc_number'] = parts[1].strip()
        if len(parts) >= 3:
            info['pub_date'] = parts[2].strip()
    
    # 如果没有找到，尝试从整个item文本中提取
    if not info['title']:
        text = item.get_text(strip=True)
        # 尝试提取标题（通常是第一行）
        lines = text.split('\n')
        if lines:
            info['title'] = lines[0].strip()
    
    return info if info['title'] else None

def analyze_detail_page(html_path):
    """分析政策详情页面"""
    print(f"\n分析详情页: {html_path}")
    print("-" * 60)
    
    if not os.path.exists(html_path):
        print(f"文件不存在: {html_path}")
        return None
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    info = {
        'title': '',
        'doc_number': '',
        'pub_date': '',
        'issue_department': '',
        'content_preview': '',
        'region_indicators': []
    }
    
    # 提取标题
    title_elem = soup.select_one('h2.title, h1.title, title')
    if title_elem:
        info['title'] = title_elem.get_text(strip=True)
    
    # 提取元数据
    for li in soup.select('li'):
        strong = li.find('strong')
        if strong:
            label = strong.get_text(strip=True)
            value = li.get_text(strip=True).replace(label, '').replace('：', '').strip()
            if '发文字号' in label:
                info['doc_number'] = value
            elif '公布日期' in label or '发布日期' in label:
                info['pub_date'] = value
            elif '发布机关' in label or '制定机关' in label:
                info['issue_department'] = value
    
    # 提取内容预览
    content_elem = soup.select_one('div.content, div.article-content, div.text')
    if content_elem:
        info['content_preview'] = content_elem.get_text(strip=True)[:500]
    
    # 识别地区标识
    all_text = soup.get_text()
    info['region_indicators'] = identify_region(all_text, info)
    
    return info

def identify_region(text, policy_info):
    """识别政策所属地区"""
    indicators = []
    
    # 检查标题
    title = policy_info.get('title', '')
    doc_number = policy_info.get('doc_number', '')
    issue_department = policy_info.get('issue_department', '')
    content_preview = policy_info.get('content_preview', '')
    
    # 省级识别
    for keyword in PROVINCIAL_KEYWORDS:
        if keyword in title:
            indicators.append(f"标题包含省级关键词: {keyword}")
        if keyword in doc_number:
            indicators.append(f"文号包含省级关键词: {keyword}")
        if keyword in issue_department:
            indicators.append(f"发布机关包含省级关键词: {keyword}")
    
    # 中山市识别
    for keyword in ZHONGSHAN_KEYWORDS:
        if keyword in title:
            indicators.append(f"标题包含中山市关键词: {keyword}")
        if keyword in doc_number:
            indicators.append(f"文号包含中山市关键词: {keyword}")
        if keyword in issue_department:
            indicators.append(f"发布机关包含中山市关键词: {keyword}")
    
    # 其他城市识别
    for keyword in EXCLUDE_CITY_KEYWORDS:
        if keyword in title:
            indicators.append(f"标题包含其他城市关键词: {keyword} (需排除)")
        if keyword in doc_number:
            indicators.append(f"文号包含其他城市关键词: {keyword} (需排除)")
        if keyword in issue_department:
            indicators.append(f"发布机关包含其他城市关键词: {keyword} (需排除)")
    
    # 从内容中识别
    if content_preview:
        if '广东省人民政府' in content_preview:
            indicators.append("内容包含: 广东省人民政府")
        elif '中山市人民政府' in content_preview:
            indicators.append("内容包含: 中山市人民政府")
        else:
            for city in ['广州市', '深圳市', '珠海市', '汕头市', '佛山市']:
                if f'{city}人民政府' in content_preview:
                    indicators.append(f"内容包含: {city}人民政府 (需排除)")
    
    return indicators

def analyze_all_pages():
    """分析所有下载的页面"""
    print("=" * 60)
    print("广东省政策库页面结构分析")
    print("=" * 60)
    
    results = defaultdict(list)
    
    # 遍历所有分类目录
    for category_dir in os.listdir(ANALYSIS_DIR):
        category_path = os.path.join(ANALYSIS_DIR, category_dir)
        if not os.path.isdir(category_path):
            continue
        
        print(f"\n\n{'='*60}")
        print(f"分类: {category_dir}")
        print(f"{'='*60}")
        
        # 分析高级搜索页
        adv_path = os.path.join(category_path, 'adv_page.html')
        if os.path.exists(adv_path):
            print(f"\n[高级搜索页]")
            # 可以在这里分析高级搜索页的结构
        
        # 遍历子分类
        for sub_dir in os.listdir(category_path):
            sub_path = os.path.join(category_path, sub_dir)
            if not os.path.isdir(sub_path):
                continue
            
            print(f"\n\n子分类: {sub_dir}")
            
            # 分析搜索结果页
            search_path = os.path.join(sub_path, 'search_page_1.html')
            if os.path.exists(search_path):
                policies = analyze_search_page(search_path)
                if policies:
                    results[sub_dir].extend(policies)
            
            # 分析详情页
            for file in os.listdir(sub_path):
                if file.startswith('detail_') and file.endswith('.html'):
                    detail_path = os.path.join(sub_path, file)
                    detail_info = analyze_detail_page(detail_path)
                    if detail_info:
                        print(f"\n政策信息:")
                        print(f"  标题: {detail_info['title'][:60]}...")
                        print(f"  文号: {detail_info['doc_number']}")
                        print(f"  发布日期: {detail_info['pub_date']}")
                        print(f"  发布机关: {detail_info['issue_department']}")
                        print(f"  地区标识:")
                        for indicator in detail_info['region_indicators']:
                            print(f"    - {indicator}")
                        
                        # 判断地区
                        region = determine_region(detail_info)
                        print(f"  判断结果: {region}")
                        results[sub_dir].append({
                            'type': 'detail',
                            'info': detail_info,
                            'region': region
                        })
    
    # 生成分析报告
    print("\n\n" + "=" * 60)
    print("分析报告")
    print("=" * 60)
    
    for sub_dir, items in results.items():
        print(f"\n{sub_dir}:")
        provincial_count = sum(1 for item in items if item.get('region') == 'provincial')
        zhongshan_count = sum(1 for item in items if item.get('region') == 'zhongshan')
        other_count = sum(1 for item in items if item.get('region') == 'other')
        unknown_count = sum(1 for item in items if item.get('region') == 'unknown')
        
        print(f"  省级: {provincial_count}")
        print(f"  中山市: {zhongshan_count}")
        print(f"  其他城市: {other_count}")
        print(f"  无法识别: {unknown_count}")

def determine_region(policy_info):
    """判断政策所属地区"""
    indicators = policy_info.get('region_indicators', [])
    
    # 检查是否有省级标识
    provincial_indicators = [i for i in indicators if '省级' in i or '广东省' in i or '粤府' in i]
    if provincial_indicators:
        return 'provincial'
    
    # 检查是否有中山市标识
    zhongshan_indicators = [i for i in indicators if '中山市' in i or '中府' in i]
    if zhongshan_indicators:
        return 'zhongshan'
    
    # 检查是否有其他城市标识
    other_indicators = [i for i in indicators if '需排除' in i]
    if other_indicators:
        return 'other'
    
    return 'unknown'

if __name__ == '__main__':
    analyze_all_pages()
