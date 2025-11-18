"""
精确复制之前成功的81937测试
"""
import os
import sys
import requests
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

def test_81937_exact():
    """精确复制之前成功的测试"""
    print("=" * 80)
    print("精确复制之前成功的81937测试")
    print("=" * 80)
    
    session = get_session()
    
    # 初始化会话
    init_url = f"{BASE_URL}/fljs/adv"
    init_resp = session.get(init_url, timeout=10)
    if init_resp.status_code != 200:
        print(f"[FAIL] 会话初始化失败")
        return
    
    print(f"[OK] 会话初始化成功")
    
    # 精确复制之前成功的参数
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
        'ClassCodeKey': ',,,,,,',  # 全空，和之前一样
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
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': f"{BASE_URL}/fljs/adv",
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    print(f"\n发送搜索请求...")
    print(f"  URL: {search_url}")
    print(f"  IssueDepartment: 81937")
    print(f"  ClassCodeKey: ',,,,,,' (全空)")
    
    try:
        resp = session.post(search_url, data=search_params, headers=headers, timeout=20)
        print(f"  响应状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            # 保存响应
            output_path = os.path.join(PROJECT_ROOT, 'analysis_pages', 'guangdong', 'fljs_81937_exact_test.html')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            print(f"  已保存到: {output_path}")
            print(f"  响应长度: {len(resp.text)} 字符")
            
            # 解析结果
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 检查是否有search-no-content
            no_content = soup.find('div', class_='search-no-content')
            if no_content:
                print(f"\n[FAIL] 发现search-no-content")
                print(f"  内容: {no_content.get_text(strip=True)[:100]}")
            else:
                print(f"\n[OK] 未发现search-no-content")
            
            # 获取总数
            total_span = soup.find('h3', string=lambda s: s and '总共检索到' in s if s else False)
            if total_span:
                total_text = total_span.get_text()
                match = re.search(r'(\d+)', total_text)
                if match:
                    total = int(match.group(1))
                    print(f"[OK] 总共检索到 {total} 篇")
                    
                    # 显示前几个政策标题
                    titles = soup.select('div.list-title h4 a, h4 a')
                    print(f"\n前{min(10, len(titles))}条政策标题:")
                    for i, title in enumerate(titles[:10], 1):
                        title_text = title.get_text(strip=True)
                        print(f"  {i}. {title_text[:70]}")
                    
                    return total
                else:
                    print(f"[WARN] 未找到总数，文本: {total_text}")
            else:
                print(f"[WARN] 未找到总数span")
            
            # 检查checkbox
            checkboxes = soup.select('input.checkbox[name="recordList"]')
            if checkboxes:
                print(f"[OK] 找到 {len(checkboxes)} 个checkbox")
                return len(checkboxes)
            else:
                print(f"[WARN] 未找到checkbox")
                
                # 检查是否有其他内容
                list_titles = soup.find_all('div', class_='list-title')
                print(f"  找到 {len(list_titles)} 个list-title")
                
                if list_titles:
                    print(f"\n前5个list-title:")
                    for i, lt in enumerate(list_titles[:5], 1):
                        text = lt.get_text(strip=True)
                        print(f"  {i}. {text[:70]}")
            
            return 0
        else:
            print(f"[FAIL] HTTP {resp.status_code}")
            print(f"  响应内容: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"[FAIL] 错误: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    test_81937_exact()

