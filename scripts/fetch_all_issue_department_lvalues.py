"""
获取所有大类的发布机关代码（lvalue）
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

def fetch_issue_department_dialog(library):
    """获取发布机关对话框HTML"""
    url = f"{BASE_URL}/foreigndialog?library={library}&property=IssueDepartment"
    print(f"\n获取发布机关选项: {url}")
    
    session = get_session()
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code == 200:
            return resp.text
        else:
            print(f"  [FAIL] HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [FAIL] 错误: {e}")
        return None

def parse_issue_department_options(html_content, library):
    """解析发布机关选项"""
    soup = BeautifulSoup(html_content, 'html.parser')
    options = soup.find_all('option')
    
    departments = []
    for opt in options:
        lvalue = opt.get('lvalue', '').strip()
        title = opt.get('title', '').strip()
        value = opt.get('value', '').strip()
        text = opt.get_text(strip=True)
        
        if lvalue or title or text:
            departments.append({
                'lvalue': lvalue,
                'title': title,
                'value': value,
                'text': text,
                'library': library
            })
    
    return departments

def test_lvalue_with_category(menu, library, class_flag, lvalue, category_code, category_name):
    """测试lvalue在特定分类中是否有效"""
    session = get_session()
    
    # 初始化会话
    init_url = f"{BASE_URL}/{menu}/adv"
    init_resp = session.get(init_url, timeout=10)
    if init_resp.status_code != 200:
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
        'AdvSearchDic.IssueDepartment': lvalue,
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
                import re
                match = re.search(r'(\d+)', total_text)
                if match:
                    return int(match.group(1))
            
            # 检查checkbox数量
            checkboxes = soup.select('input.checkbox[name="recordList"]')
            return len(checkboxes) if checkboxes else 0
        else:
            return None
    except Exception as e:
        return None

def main():
    """主函数"""
    print("=" * 80)
    print("获取所有大类的发布机关代码（lvalue）")
    print("=" * 80)
    
    # 定义所有需要检查的库
    libraries = {
        'gddifang': {'menu': 'dfxfg', 'class_flag': 'gddifang', 'name': '地方性法规'},
        'gddigui': {'menu': 'dfzfgz', 'class_flag': 'gddigui', 'name': '地方政府规章'},
        'gdnormativedoc': {'menu': 'fljs', 'class_flag': 'gdnormativedoc', 'name': '规范性文件'},
    }
    
    # 定义分类配置
    categories = {
        'gddifang': [
            ('XM0701', '省级地方性法规'),
            ('XM0702', '设区的市地方性法规'),
        ],
        'gddigui': [
            ('XO0802', '省级地方政府规章'),
            ('XO0803', '设区的市地方政府规章'),
        ],
        'gdnormativedoc': [
            ('XP08', '地方规范性文件'),
        ],
    }
    
    all_results = {}
    
    # 获取每个库的发布机关选项
    for library, config in libraries.items():
        print(f"\n{'='*80}")
        print(f"库: {config['name']} ({library})")
        print(f"{'='*80}")
        
        # 获取发布机关对话框
        html = fetch_issue_department_dialog(library)
        if not html:
            continue
        
        # 保存HTML
        output_dir = os.path.join(PROJECT_ROOT, 'analysis_pages', 'guangdong', 'issue_departments')
        os.makedirs(output_dir, exist_ok=True)
        html_path = os.path.join(output_dir, f'issue_department_{library}.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  已保存到: {html_path}")
        
        # 解析选项
        departments = parse_issue_department_options(html, library)
        print(f"  找到 {len(departments)} 个发布机关选项")
        
        # 过滤出有效的lvalue（有lvalue属性的）
        valid_departments = [d for d in departments if d['lvalue']]
        print(f"  其中 {len(valid_departments)} 个有lvalue")
        
        # 显示前20个
        print(f"\n  前20个发布机关选项:")
        for i, dept in enumerate(valid_departments[:20], 1):
            print(f"    {i}. {dept['text'][:50]} (lvalue={dept['lvalue']}, title={dept['title']})")
        
        # 测试每个分类中的有效性
        if library in categories:
            print(f"\n  测试在分类中的有效性:")
            for category_code, category_name in categories[library]:
                print(f"\n    分类: {category_name} ({category_code})")
                
                # 测试关键lvalue
                key_lvalues = ['81901', '81902', '81903', '81937', '81938', '81939']
                for lvalue in key_lvalues:
                    dept_info = next((d for d in valid_departments if d['lvalue'] == lvalue), None)
                    if dept_info:
                        count = test_lvalue_with_category(
                            config['menu'], library, config['class_flag'],
                            lvalue, category_code, category_name
                        )
                        status = "[OK]" if count and count > 0 else "[FAIL]"
                        count_str = str(count) if count is not None else "N/A"
                        print(f"      {status} lvalue={lvalue} ({dept_info['text'][:30]}): {count_str}条")
                        time.sleep(0.5)  # 延迟避免请求过快
        
        all_results[library] = {
            'config': config,
            'departments': valid_departments,
            'total_count': len(valid_departments)
        }
        
        time.sleep(1)  # 延迟避免请求过快
    
    # 保存结果到JSON
    output_file = os.path.join(PROJECT_ROOT, 'analysis_pages', 'guangdong', 'issue_departments', 'all_lvalues.json')
    
    # 转换为可序列化的格式
    json_results = {}
    for library, data in all_results.items():
        json_results[library] = {
            'menu': data['config']['menu'],
            'class_flag': data['config']['class_flag'],
            'name': data['config']['name'],
            'total_count': data['total_count'],
            'departments': data['departments']
        }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*80}")
    print("结果汇总")
    print(f"{'='*80}")
    print(f"已保存所有lvalue到: {output_file}")
    
    # 汇总关键lvalue
    print(f"\n关键lvalue汇总:")
    key_lvalues = {
        '81901': '广东省人大(含常委会)',
        '81902': '广东省人民政府',
        '81903': '广东省其他机构',
        '81937': '中山市人大(含常委会)',
        '81938': '中山市人民政府',
        '81939': '中山市其他机构',
    }
    
    for lvalue, name in key_lvalues.items():
        found_in = []
        for library, data in all_results.items():
            dept = next((d for d in data['departments'] if d['lvalue'] == lvalue), None)
            if dept:
                found_in.append(f"{data['config']['name']}({library})")
        
        if found_in:
            print(f"  {lvalue} ({name}): 存在于 {', '.join(found_in)}")
        else:
            print(f"  {lvalue} ({name}): [未找到]")
    
    print(f"\n{'='*80}")
    print("完成")
    print(f"{'='*80}")

if __name__ == '__main__':
    main()

