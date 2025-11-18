"""
测试81937（中山市人大）在fljs菜单（规范性文件）中的使用方式
"""
import os
import sys
import requests
import time
from bs4 import BeautifulSoup
import re

# 调整路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
sys.path.append(PROJECT_ROOT)

BASE_URL = 'https://gd.pkulaw.com'

def get_session():
    """获取会话"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    })
    return session

def test_81937_with_params(class_code_key, description):
    """测试81937在不同参数下的效果"""
    print(f"\n{'='*80}")
    print(f"测试: {description}")
    print(f"ClassCodeKey: {class_code_key}")
    print(f"{'='*80}")
    
    session = get_session()
    
    # 初始化会话
    init_url = f"{BASE_URL}/fljs/adv"
    init_resp = session.get(init_url, timeout=10)
    if init_resp.status_code != 200:
        print(f"  [FAIL] 会话初始化失败")
        return None
    
    # 发送搜索请求
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
        'ClassCodeKey': class_code_key,
        'GroupByIndex': '0',
        'OrderByIndex': '0',
        'ShowType': 'Default',
        'GroupValue': '',
        'AdvSearchDic.Title': '',
        'AdvSearchDic.CheckFullText': '',
        'AdvSearchDic.IssueDepartment': '81937',  # 中山市人大
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
    session.headers.update({
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': f"{BASE_URL}/fljs/adv",
        'X-Requested-With': 'XMLHttpRequest',
    })
    
    try:
        resp = session.post(search_url, data=search_params, timeout=20)
        if resp.status_code == 200:
            # 保存响应
            safe_desc = description.replace(' ', '_').replace('=', '_')
            output_path = os.path.join(PROJECT_ROOT, 'analysis_pages', 'guangdong', f'fljs_81937_{safe_desc}.html')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            print(f"  已保存到: {output_path}")
            
            # 解析结果
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 检查是否有数据
            no_content = soup.find('div', class_='search-no-content')
            if no_content:
                print(f"  [FAIL] 发现search-no-content，无数据")
                return 0
            
            # 获取总数
            total_span = soup.find('h3', string=lambda s: s and '总共检索到' in s if s else False)
            if total_span:
                total_text = total_span.get_text()
                match = re.search(r'(\d+)', total_text)
                if match:
                    total = int(match.group(1))
                    print(f"  [OK] 总共检索到 {total} 篇")
                    
                    # 检查前几个政策的标题
                    titles = soup.select('div.list-title h4 a, h4 a')
                    zhongshan_count = 0
                    print(f"  前10条政策标题:")
                    for i, title in enumerate(titles[:10], 1):
                        title_text = title.get_text(strip=True)
                        if '中山' in title_text:
                            zhongshan_count += 1
                            print(f"    {i}. [中山] {title_text[:60]}...")
                        else:
                            print(f"    {i}. {title_text[:60]}...")
                    
                    print(f"  前10条中，包含'中山'的有 {zhongshan_count} 条")
                    return total
            
            # 检查checkbox数量
            checkboxes = soup.select('input.checkbox[name="recordList"]')
            if checkboxes:
                print(f"  [OK] 找到 {len(checkboxes)} 个checkbox（第1页）")
                return len(checkboxes)
            else:
                print(f"  [FAIL] 未找到checkbox")
                return 0
        else:
            print(f"  [FAIL] HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [FAIL] 错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """主函数"""
    print("=" * 80)
    print("测试81937（中山市人大）在fljs菜单（规范性文件）中的使用方式")
    print("=" * 80)
    
    # 测试不同的ClassCodeKey配置
    test_cases = [
        (',,,,,,', '不使用ClassCodeKey（全空）'),
        (',,,XP08,,,', '使用ClassCodeKey=XP08（地方规范性文件）'),
        ('', 'ClassCodeKey为空字符串'),
    ]
    
    results = []
    for class_code_key, description in test_cases:
        count = test_81937_with_params(class_code_key, description)
        results.append({
            'description': description,
            'class_code_key': class_code_key,
            'count': count
        })
        time.sleep(1)  # 延迟避免请求过快
    
    # 汇总结果
    print(f"\n{'='*80}")
    print("测试结果汇总")
    print(f"{'='*80}")
    print(f"{'配置':<40} {'ClassCodeKey':<20} {'数据量':<10} {'状态':<10}")
    print("-" * 80)
    for r in results:
        count_str = str(r['count']) if r['count'] is not None else "N/A"
        status = "[OK]" if r['count'] and r['count'] > 0 else "[FAIL]"
        print(f"{r['description']:<40} {r['class_code_key']:<20} {count_str:<10} {status:<10}")
    
    # 分析
    print(f"\n{'='*80}")
    print("分析")
    print(f"{'='*80}")
    
    valid_configs = [r for r in results if r['count'] and r['count'] > 0]
    if valid_configs:
        print("有效的配置:")
        for r in valid_configs:
            print(f"  - {r['description']}: {r['count']}条")
        
        # 推荐配置
        best = max(valid_configs, key=lambda x: x['count'])
        print(f"\n推荐配置: {best['description']} (ClassCodeKey={best['class_code_key']})")
        print(f"  数据量: {best['count']}条")
    else:
        print("[WARN] 所有配置都无效，81937在fljs菜单中可能不适用")
    
    print(f"\n{'='*80}")
    print("测试完成")
    print(f"{'='*80}")

if __name__ == '__main__':
    main()

