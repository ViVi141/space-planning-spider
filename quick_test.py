#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://gd.pkulaw.com'
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Referer': 'https://gd.pkulaw.com/fljs/adv',
    'Origin': 'https://gd.pkulaw.com',
})
session.cookies.set('JSESSIONID', '1234567890ABCDEF', domain='gd.pkulaw.com')
session.get(f"{BASE_URL}/fljs/adv", timeout=10)

search_url = f"{BASE_URL}/fljs/search/RecordSearch"

# 测试年份筛选
search_data = {
    'Menu': 'fljs',
    'Library': 'gdnormativedoc',
    'ClassFlag': 'gdnormativedoc',
    'ClassCodeKey': ',,,2020',  # 年份筛选
    'IsAdv': 'True',
    'Pager.PageIndex': '1',
    'Pager.PageSize': '20',
    'QueryOnClick': 'False',
    'AfterSearch': 'False',
    'GroupByIndex': '0',
    'OrderByIndex': '0',
    'ShowType': 'Default',
    'isEng': 'chinese',
    'OldPageIndex': '',
    'newPageIndex': '',
    'X-Requested-With': 'XMLHttpRequest',
}

resp = session.post(search_url, data=search_data, timeout=30)
soup = BeautifulSoup(resp.text, 'html.parser')
total = soup.find('span', string=lambda x: x and x.isdigit())
print(f"结果: {total.get_text() if total else '未找到'} 篇")
print("✓✓✓ 年份筛选成功！" if total and int(total.get_text()) < 40231 else "✗✗✗ 失败")

