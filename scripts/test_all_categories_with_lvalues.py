"""
系统测试所有大类和小类的发布机关lvalue有效性
检查不同大类下同名小类的数据量差异
"""
import os
import sys
import requests
import time
from bs4 import BeautifulSoup
import re
import json

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

def test_category_with_lvalue(menu, library, class_flag, category_code, category_name, lvalue, lvalue_name):
    """测试特定分类和发布机关的组合"""
    session = get_session()
    
    # 初始化会话
    init_url = f"{BASE_URL}/{menu}/adv"
    try:
        init_resp = session.get(init_url, timeout=10)
        if init_resp.status_code != 200:
            return None
    except:
        return None
    
    # 发送搜索请求
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
        'ClassCodeKey': f',,,{category_code},,,' if category_code else ',,,,,,',
        'GroupByIndex': '0',
        'OrderByIndex': '0',
        'ShowType': 'Default',
        'GroupValue': '',
        'AdvSearchDic.Title': '',
        'AdvSearchDic.CheckFullText': '',
        'AdvSearchDic.IssueDepartment': lvalue if lvalue else '',
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
                return 0
            
            # 获取总数
            total_span = soup.find('h3', string=lambda s: s and '总共检索到' in s if s else False)
            if total_span:
                total_text = total_span.get_text()
                match = re.search(r'(\d+)', total_text)
                if match:
                    return int(match.group(1))
            
            # 检查checkbox数量（第1页）
            checkboxes = soup.select('input.checkbox[name="recordList"]')
            return len(checkboxes) if checkboxes else 0
        else:
            return None
    except Exception as e:
        return None

def main():
    """主函数"""
    print("=" * 100)
    print("系统测试所有大类和小类的发布机关lvalue有效性")
    print("=" * 100)
    
    # 定义所有需要测试的分类
    test_categories = [
        # (菜单, 库, class_flag, 分类代码, 分类名称, 大类名称)
        ('dfxfg', 'gddifang', 'gddifang', 'XM0701', '省级地方性法规', '地方性法规'),
        ('dfxfg', 'gddifang', 'gddifang', 'XM0702', '设区的市地方性法规', '地方性法规'),
        
        ('dfzfgz', 'gddigui', 'gddigui', 'XO0802', '省级地方政府规章', '地方政府规章'),
        ('dfzfgz', 'gddigui', 'gddigui', 'XO0803', '设区的市地方政府规章', '地方政府规章'),
        
        ('fljs', 'gdnormativedoc', 'gdnormativedoc', 'XP08', '地方规范性文件', '规范性文件'),
    ]
    
    # 定义需要测试的lvalue
    test_lvalues = [
        ('81901', '广东省人大(含常委会)'),
        ('81902', '广东省人民政府'),
        ('81903', '广东省其他机构'),
        ('81937', '中山市人大(含常委会)'),
        ('81938', '中山市人民政府'),
        ('81939', '中山市其他机构'),
        (None, '不使用发布机关筛选'),  # 测试不使用发布机关筛选
    ]
    
    all_results = []
    
    # 遍历所有分类
    for menu, library, class_flag, category_code, category_name, main_category in test_categories:
        print(f"\n{'='*100}")
        print(f"大类: {main_category} | 小类: {category_name} ({category_code})")
        print(f"菜单: {menu}, 库: {library}")
        print(f"{'='*100}")
        
        category_results = []
        
        # 测试每个lvalue
        for lvalue, lvalue_name in test_lvalues:
            print(f"\n  测试: {lvalue_name} (lvalue={lvalue})")
            
            count = test_category_with_lvalue(
                menu, library, class_flag,
                category_code, category_name,
                lvalue, lvalue_name
            )
            
            status = "[OK]" if count and count > 0 else "[FAIL]"
            count_str = str(count) if count is not None else "N/A"
            print(f"    结果: {status} {count_str}条")
            
            category_results.append({
                'main_category': main_category,
                'category_code': category_code,
                'category_name': category_name,
                'menu': menu,
                'library': library,
                'lvalue': lvalue,
                'lvalue_name': lvalue_name,
                'count': count,
                'status': 'valid' if count and count > 0 else 'invalid'
            })
            
            time.sleep(0.5)  # 延迟避免请求过快
        
        all_results.extend(category_results)
        
        # 显示该分类的有效lvalue
        valid_lvalues = [r for r in category_results if r['status'] == 'valid']
        if valid_lvalues:
            print(f"\n  [有效lvalue]:")
            for r in valid_lvalues:
                print(f"    - {r['lvalue_name']} (lvalue={r['lvalue']}): {r['count']}条")
        else:
            print(f"\n  [WARN] 该分类下没有有效的lvalue")
        
        time.sleep(1)  # 分类间延迟
    
    # 保存结果到JSON
    output_file = os.path.join(PROJECT_ROOT, 'analysis_pages', 'guangdong', 'all_categories_lvalues_test.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n{'='*100}")
    print(f"结果已保存到: {output_file}")
    
    # 生成汇总报告
    print(f"\n{'='*100}")
    print("汇总报告")
    print(f"{'='*100}")
    
    # 按大类分组
    by_main_category = {}
    for r in all_results:
        main_cat = r['main_category']
        if main_cat not in by_main_category:
            by_main_category[main_cat] = []
        by_main_category[main_cat].append(r)
    
    for main_cat, results in by_main_category.items():
        print(f"\n【{main_cat}】")
        print("-" * 100)
        
        # 按小类分组
        by_category = {}
        for r in results:
            cat_code = r['category_code']
            if cat_code not in by_category:
                by_category[cat_code] = []
            by_category[cat_code].append(r)
        
        for cat_code, cat_results in by_category.items():
            cat_name = cat_results[0]['category_name']
            print(f"\n  {cat_name} ({cat_code}):")
            
            valid_results = [r for r in cat_results if r['status'] == 'valid']
            if valid_results:
                for r in valid_results:
                    lvalue_str = r['lvalue'] if r['lvalue'] else '无'
                    print(f"    [OK] {r['lvalue_name']} (lvalue={lvalue_str}): {r['count']}条")
            else:
                print(f"    [FAIL] 没有有效的lvalue")
    
    # 检查同名小类在不同大类中的数据量差异
    print(f"\n{'='*100}")
    print("同名小类在不同大类中的数据量对比")
    print(f"{'='*100}")
    
    # 找出同名但不同大类的分类
    category_groups = {}
    for r in all_results:
        key = r['category_name']
        if key not in category_groups:
            category_groups[key] = []
        category_groups[key].append(r)
    
    for cat_name, results in category_groups.items():
        # 如果同一个名称出现在不同大类中
        main_cats = set(r['main_category'] for r in results)
        if len(main_cats) > 1:
            print(f"\n【{cat_name}】出现在多个大类中:")
            for main_cat in main_cats:
                main_cat_results = [r for r in results if r['main_category'] == main_cat]
                print(f"\n  {main_cat}:")
                for r in main_cat_results:
                    if r['status'] == 'valid':
                        lvalue_str = r['lvalue'] if r['lvalue'] else '无'
                        print(f"    {r['lvalue_name']} (lvalue={lvalue_str}): {r['count']}条")
    
    print(f"\n{'='*100}")
    print("测试完成")
    print(f"{'='*100}")

if __name__ == '__main__':
    main()

