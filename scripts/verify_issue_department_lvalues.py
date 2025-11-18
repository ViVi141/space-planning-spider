"""
验证发布机关lvalue配置是否正确
"""
import os
import sys
import requests
from bs4 import BeautifulSoup

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

def test_issue_department(menu, library, class_flag, issue_department_lvalue, category_name, category_code=None):
    """测试发布机关筛选"""
    print(f"\n测试: {category_name}")
    print(f"  菜单: {menu}, 库: {library}, 发布机关lvalue: {issue_department_lvalue}")
    if category_code:
        print(f"  分类代码: {category_code}")
    
    session = get_session()
    
    # 初始化会话
    init_url = f"{BASE_URL}/{menu}/adv"
    init_resp = session.get(init_url, timeout=10)
    if init_resp.status_code != 200:
        print(f"  [FAIL] 会话初始化失败")
        return None
    
    # 发送搜索请求
    # 注意：如果提供了category_code，需要同时设置ClassCodeKey来限制分类
    class_code_key = f',,,{category_code},,,' if category_code else ',,,,,,'
    search_params = {
        'Menu': menu,
        'Keywords': '',
        'SearchKeywordType': 'Title',
        'MatchType': 'Fuzzy',
        'RangeType': 'Piece',
        'Library': library,
        'ClassFlag': class_flag,
        'GroupLibraries': '',
        'QueryOnClick': 'False',
        'AfterSearch': 'False',
        'pdfStr': '',
        'pdfTitle': '',
        'IsAdv': 'True',
        'ClassCodeKey': class_code_key,  # 如果提供category_code，使用分类代码
        'GroupByIndex': '0',
        'OrderByIndex': '0',
        'ShowType': 'Default',
        'GroupValue': '',
        'AdvSearchDic.Title': '',
        'AdvSearchDic.CheckFullText': '',
        'AdvSearchDic.IssueDepartment': issue_department_lvalue,
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
    
    search_url = f"{BASE_URL}/{menu}/search/RecordSearch"
    session.headers.update({
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': f"{BASE_URL}/{menu}/adv",
        'X-Requested-With': 'XMLHttpRequest',
    })
    
    try:
        resp = session.post(search_url, data=search_params, timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 检查是否有数据
            no_content = soup.find('div', class_='search-no-content')
            if no_content:
                print(f"  [FAIL] 无数据 (search-no-content)")
                return 0
            
            # 获取总数
            total_span = soup.find('h3', string=lambda s: s and '总共检索到' in s if s else False)
            if total_span:
                total_text = total_span.get_text()
                import re
                match = re.search(r'(\d+)', total_text)
                if match:
                    total = int(match.group(1))
                    print(f"  [OK] 找到 {total} 条数据")
                    return total
            
            # 检查checkbox数量
            checkboxes = soup.select('input.checkbox[name="recordList"]')
            if checkboxes:
                print(f"  [OK] 找到 {len(checkboxes)} 个checkbox (第1页)")
                return len(checkboxes)
            else:
                print(f"  [FAIL] 未找到checkbox")
                return 0
        else:
            print(f"  [FAIL] HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [FAIL] 错误: {e}")
        return None

def main():
    """主函数"""
    print("=" * 80)
    print("验证发布机关lvalue配置")
    print("=" * 80)
    
    # 测试配置
    # (菜单, 库, class_flag, lvalue, 分类名称, 分类代码, 预期数量)
    test_cases = [
        # 省级地方性法规 (XM0701) - 需要同时使用ClassCodeKey
        ('dfxfg', 'gddifang', 'gddifang', '81901', '省级地方性法规 - 广东省人大', 'XM0701', 859),
        ('dfxfg', 'gddifang', 'gddifang', '81902', '省级地方性法规 - 广东省人民政府', 'XM0701', None),
        ('dfxfg', 'gddifang', 'gddifang', '81903', '省级地方性法规 - 广东省其他机构', 'XM0701', 859),
        
        # 设区的市地方性法规 (XM0702) - 需要同时使用ClassCodeKey
        ('dfxfg', 'gddifang', 'gddifang', '81937', '设区的市地方性法规 - 中山市人大', 'XM0702', 8),
        
        # 省级地方政府规章 (XO0802) - 需要同时使用ClassCodeKey
        ('dfzfgz', 'gddigui', 'gddigui', '81902', '省级地方政府规章 - 广东省人民政府', 'XO0802', 764),
        
        # 设区的市地方政府规章 (XO0803) - 需要同时使用ClassCodeKey
        ('dfzfgz', 'gddigui', 'gddigui', '81938', '设区的市地方政府规章 - 中山市人民政府', 'XO0803', 21),
        
        # 地方规范性文件 (XP08) - 需要同时使用ClassCodeKey
        ('fljs', 'gdnormativedoc', 'gdnormativedoc', '81937', '地方规范性文件 - 中山市人大', 'XP08', 9),
        ('fljs', 'gdnormativedoc', 'gdnormativedoc', '81938', '地方规范性文件 - 中山市人民政府', 'XP08', 640),
        ('fljs', 'gdnormativedoc', 'gdnormativedoc', '81939', '地方规范性文件 - 中山市其他机构', 'XP08', 292),
    ]
    
    results = []
    for menu, library, class_flag, lvalue, category_name, category_code, expected in test_cases:
        count = test_issue_department(menu, library, class_flag, lvalue, category_name, category_code)
        results.append({
            'category': category_name,
            'lvalue': lvalue,
            'actual': count,
            'expected': expected,
            'status': 'OK' if count and (expected is None or count >= expected * 0.9) else 'FAIL'
        })
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("验证结果汇总")
    print("=" * 80)
    print(f"{'分类':<40} {'lvalue':<10} {'实际':<10} {'预期':<10} {'状态':<10}")
    print("-" * 80)
    for r in results:
        expected_str = str(r['expected']) if r['expected'] else 'N/A'
        actual_str = str(r['actual']) if r['actual'] is not None else 'N/A'
        print(f"{r['category']:<40} {r['lvalue']:<10} {actual_str:<10} {expected_str:<10} {r['status']:<10}")
    
    # 检查配置问题
    print("\n" + "=" * 80)
    print("配置问题检查")
    print("=" * 80)
    
    issues = []
    for r in results:
        if r['status'] == 'FAIL':
            if r['actual'] == 0:
                issues.append(f"❌ {r['category']} (lvalue={r['lvalue']}): 无数据")
            elif r['expected'] and r['actual'] < r['expected'] * 0.9:
                issues.append(f"⚠️ {r['category']} (lvalue={r['lvalue']}): 数据量不足 (实际={r['actual']}, 预期={r['expected']})")
    
    if issues:
        print("发现以下问题：")
        for issue in issues:
            print(f"  {issue.replace('❌', '[FAIL]').replace('⚠️', '[WARN]').replace('✅', '[OK]')}")
    else:
        print("[OK] 所有配置正确！")

if __name__ == '__main__':
    main()

