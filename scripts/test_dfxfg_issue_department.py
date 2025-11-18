"""
测试dfxfg菜单（地方性法规）的发布机关筛选
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

def test_dfxfg_with_issue_department(issue_department_lvalue='81903'):
    """测试dfxfg菜单使用发布机关筛选"""
    print(f"\n测试dfxfg菜单使用发布机关筛选: lvalue={issue_department_lvalue}")
    
    # 先访问高级搜索页面初始化会话
    session = get_session()
    init_url = f"{BASE_URL}/dfxfg/adv"
    print(f"步骤1: 初始化会话 - 访问 {init_url}")
    init_resp = session.get(init_url, timeout=10)
    if init_resp.status_code == 200:
        print(f"  会话初始化成功 (状态码: {init_resp.status_code})")
    
    # 发送RecordSearch（不使用ClassSearch）
    search_params = {
        'Menu': 'dfxfg',
        'Keywords': '',
        'SearchKeywordType': 'Title',
        'MatchType': 'Fuzzy',
        'RangeType': 'Piece',
        'Library': 'gddifang',
        'ClassFlag': 'gddifang',
        'GroupLibraries': '',
        'QueryOnClick': 'False',
        'AfterSearch': 'False',
        'pdfStr': '',
        'pdfTitle': '',
        'IsAdv': 'True',
        'ClassCodeKey': ',,,,,,',  # 全空，不使用分类代码
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
    
    search_url = f"{BASE_URL}/dfxfg/search/RecordSearch"
    print(f"\n步骤2: 发送RecordSearch - {search_url}")
    print(f"  发布机关lvalue: {issue_department_lvalue}")
    print(f"  ClassCodeKey: {search_params['ClassCodeKey']}")
    
    session.headers.update({
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': f"{BASE_URL}/dfxfg/adv",
        'X-Requested-With': 'XMLHttpRequest',
    })
    
    try:
        resp = session.post(search_url, data=search_params, timeout=20)
        if resp.status_code == 200:
            # 保存响应
            output_path = os.path.join(PROJECT_ROOT, 'analysis_pages', 'guangdong', f'dfxfg_issue_department_{issue_department_lvalue}.html')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            print(f"  已保存搜索结果到: {output_path}")
            print(f"  响应内容长度: {len(resp.text)} 字符")
            
            # 解析结果
            soup = BeautifulSoup(resp.text, 'html.parser')
            checkboxes = soup.select('input.checkbox[name="recordList"]')
            print(f"  找到 {len(checkboxes)} 个checkbox")
            
            list_titles = soup.find_all('div', class_='list-title')
            print(f"  找到 {len(list_titles)} 个list-title")
            
            # 检查是否有search-no-content
            no_content = soup.find('div', class_='search-no-content')
            if no_content:
                print(f"  ⚠️ 发现search-no-content，可能没有数据")
            else:
                print(f"  ✓ 未发现search-no-content，可能有数据")
            
            # 显示前几个政策的标题
            titles = soup.select('div.list-title h4 a, h4 a')
            for i, title in enumerate(titles[:5], 1):
                print(f"  {i}. {title.get_text(strip=True)[:60]}...")
            
            return resp.text
        else:
            print(f"  失败: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  错误: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("测试dfxfg菜单（地方性法规）的发布机关筛选")
    print("=" * 60)
    
    # 测试1: 广东省其他机构 (81903)
    test_dfxfg_with_issue_department('81903')
    
    # 测试2: 广东省人大 (81901)
    test_dfxfg_with_issue_department('81901')
    
    # 测试3: 广东省人民政府 (81902)
    test_dfxfg_with_issue_department('81902')
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

