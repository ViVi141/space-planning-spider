"""
测试XM0702（设区的市地方性法规）不使用发布机关筛选
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

def test_xm0702_with_classcode_only():
    """测试XM0702只使用ClassCodeKey，不使用发布机关筛选"""
    print("\n测试: 设区的市地方性法规 (XM0702) - 只使用ClassCodeKey")
    
    session = get_session()
    
    # 初始化会话
    init_url = f"{BASE_URL}/dfxfg/adv"
    init_resp = session.get(init_url, timeout=10)
    if init_resp.status_code != 200:
        print(f"  [FAIL] 会话初始化失败")
        return None
    
    # 发送搜索请求（只使用ClassCodeKey，不使用发布机关筛选）
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
        'ClassCodeKey': ',,,XM0702,,,',  # 只使用分类代码
        'GroupByIndex': '0',
        'OrderByIndex': '0',
        'ShowType': 'Default',
        'GroupValue': '',
        'AdvSearchDic.Title': '',
        'AdvSearchDic.CheckFullText': '',
        'AdvSearchDic.IssueDepartment': '',  # 不使用发布机关筛选
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
    session.headers.update({
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': f"{BASE_URL}/dfxfg/adv",
        'X-Requested-With': 'XMLHttpRequest',
    })
    
    try:
        resp = session.post(search_url, data=search_params, timeout=20)
        if resp.status_code == 200:
            # 保存响应
            output_path = os.path.join(PROJECT_ROOT, 'analysis_pages', 'guangdong', 'xm0702_classcode_only.html')
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
                print(f"  [FAIL] 发现search-no-content，可能没有数据")
            else:
                print(f"  [OK] 未发现search-no-content，可能有数据")
            
            # 获取总数
            total_span = soup.find('h3', string=lambda s: s and '总共检索到' in s if s else False)
            if total_span:
                total_text = total_span.get_text()
                import re
                match = re.search(r'(\d+)', total_text)
                if match:
                    total = int(match.group(1))
                    print(f"  [OK] 总共检索到 {total} 篇")
                    
                    # 检查前几个政策是否包含中山市
                    titles = soup.select('div.list-title h4 a, h4 a')
                    zhongshan_count = 0
                    for title in titles[:10]:
                        title_text = title.get_text(strip=True)
                        if '中山' in title_text:
                            zhongshan_count += 1
                            print(f"    包含中山: {title_text[:60]}...")
                    
                    print(f"  前10条中，包含'中山'的有 {zhongshan_count} 条")
                    return total
            
            # 显示前几个政策的标题
            titles = soup.select('div.list-title h4 a, h4 a')
            for i, title in enumerate(titles[:5], 1):
                print(f"  {i}. {title.get_text(strip=True)[:60]}...")
            
            return len(checkboxes) if checkboxes else 0
        else:
            print(f"  [FAIL] HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [FAIL] 错误: {e}")
        return None

if __name__ == '__main__':
    print("=" * 80)
    print("测试XM0702（设区的市地方性法规）不使用发布机关筛选")
    print("=" * 80)
    
    test_xm0702_with_classcode_only()
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

