import os
import sys
import time
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://gd.pkulaw.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

CATEGORY_NAME = "省级地方性法规"
CATEGORY_CODE = "XM0701"
TARGET_YEAR = "2018"
MENU = "dfxfg"
LIBRARY = "gddifang"
GROUP_INDEX_YEAR = "3"


def build_payload(page_index: int, prev_page: int | None = None) -> str:
    parts = [
        f"Menu={MENU}",
        "Keywords=",
        "SearchKeywordType=Title",
        "MatchType=Exact",
        "RangeType=Piece",
        f"Library={LIBRARY}",
        f"ClassFlag={LIBRARY}",
        "GroupLibraries=",
        "QueryOnClick=False",
        "AfterSearch=False",
        "pdfStr=",
        "pdfTitle=",
        "IsAdv=True",
        f"ClassCodeKey=,,,{CATEGORY_CODE},,,{TARGET_YEAR}",
        f"GroupByIndex={GROUP_INDEX_YEAR}",
        f"GroupValue={TARGET_YEAR}",
        "OrderByIndex=0",
        "ShowType=Group",
        "AdvSearchDic.Title=",
        "AdvSearchDic.CheckFullText=",
        "AdvSearchDic.IssueDepartment=",
        "AdvSearchDic.DocumentNO=",
        "AdvSearchDic.IssueDate=",
        "AdvSearchDic.ImplementDate=",
        "AdvSearchDic.TimelinessDic=",
        "AdvSearchDic.EffectivenessDic=",
        "TitleKeywords=",
        "FullTextKeywords=",
        f"Pager.PageIndex={page_index}",
        "Pager.PageSize=20",
        "QueryBase64Request=",
        "VerifyCodeResult=",
        "isEng=chinese",
        f"OldPageIndex={prev_page if prev_page is not None else ''}",
        f"newPageIndex={page_index if prev_page is not None else ''}",
    ]
    return "&".join(parts)


def parse_records(html: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    records: List[Tuple[str, str]] = []
    for item in soup.select("input.checkbox[name='recordList']"):
        block = item.find_parent("div", class_="block")
        if not block:
            continue
        title_tag = block.select_one("div.list-title a")
        info_div = block.select_one("div.related-info")
        title = title_tag.get_text(strip=True) if title_tag else ""
        info = info_div.get_text(strip=True) if info_div else ""
        records.append((title, info))
    return records


def main() -> int:
    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.set("JSESSIONID", os.urandom(16).hex().upper(), domain="gd.pkulaw.com")

    url = f"{BASE_URL}/{MENU}/search/RecordSearch"
    aggregated: List[Tuple[str, str]] = []

    for page_index in range(1, 9):
        prev_index = page_index - 1 if page_index > 1 else None
        payload = build_payload(page_index, prev_index)
        resp = session.post(url, data=payload, timeout=30)
        resp.raise_for_status()
        records = parse_records(resp.text)
        aggregated.extend(records)
        cross_year = [(title, info) for title, info in records if TARGET_YEAR not in info]
        print(f"第 {page_index} 页返回 {len(records)} 条, 跨年条数: {len(cross_year)}")
        for title, info in cross_year[:3]:
            print(f"  跨年样例: {info} -> {title}")
        if cross_year:
            break
        if not records:
            break
        time.sleep(0.5)

    print(f"共采集 {len(aggregated)} 条样本")
    year_counts = {}
    for _, info in aggregated:
        if "公布" in info:
            year = info.split("公布")[0][-4:]
        else:
            year = "未知"
        year_counts[year] = year_counts.get(year, 0) + 1
    print("年份分布:")
    for year, count in sorted(year_counts.items(), reverse=True):
        print(f"  {year}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
