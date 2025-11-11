import os
import re
import sys
import time
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://gd.pkulaw.com"

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
}

API_PATH_MAP = {
    "dfxfg": {"menu": "dfxfg", "library": "gddifang"},
    "sfjs": {"menu": "sfjs", "library": "regularation"},
    "dfzfgz": {"menu": "dfzfgz", "library": "gddigui"},
    "fljs": {"menu": "fljs", "library": "gdnormativedoc"},
}

CATEGORY_API_MAP = {
    "XM07": "dfxfg",
    "XU13": "sfjs",
    "XO08": "dfzfgz",
    "XP08": "fljs",
}

CATEGORIES = [
    ("地方性法规", "省级地方性法规", "XM0701"),
    ("地方性法规", "设区的市地方性法规", "XM0702"),
    ("地方性法规", "经济特区法规", "XM0703"),
    ("地方性法规", "自治条例和单行条例", "XU13"),
    ("地方政府规章", "省级地方政府规章", "XO0802"),
    ("地方政府规章", "设区的市地方政府规章", "XO0803"),
    ("规范性文件", "地方规范性文件", "XP08"),
]

YEAR_PATTERN = re.compile(r"(\d{4})\s*\((\d+)\)")
TOTAL_PATTERN = re.compile(r"总共检索到\s*(\d+)\s*篇")


def get_api_type(category_code: str) -> str:
    for prefix, api_name in CATEGORY_API_MAP.items():
        if category_code.startswith(prefix):
            return api_name
    return "dfzfgz"


def extract_years_from_html(html: str) -> List[Tuple[int, int]]:
    soup = BeautifulSoup(html, "html.parser")
    years: List[Tuple[int, int]] = []

    year_block = soup.find("div", class_="block", attrs={"cluster_index": "3"})
    if year_block:
        links = year_block.find_all("a", attrs={"cluster_code": True})
        for link in links:
            text = link.get_text(strip=True)
            match = YEAR_PATTERN.search(text)
            if match:
                year = int(match.group(1))
                count = int(match.group(2))
                years.append((year, count))

    if not years:
        links = soup.find_all("a", attrs={"cluster_code": True})
        for link in links:
            code = link.get("cluster_code", "")
            if len(code) == 4 and code.isdigit():
                text = link.get_text(strip=True)
                match = YEAR_PATTERN.search(text)
                if match:
                    year = int(match.group(1))
                    count = int(match.group(2))
                    years.append((year, count))

    years.sort(reverse=True)
    return years


def extract_total_count(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    header = soup.find("h3")
    if header:
        match = TOTAL_PATTERN.search(header.get_text(strip=True))
        if match:
            return int(match.group(1))
    return sum(count for _, count in extract_years_from_html(html))


def fetch_category_years(session: requests.Session, parent: str, name: str, code: str) -> Tuple[List[Tuple[int, int]], int]:
    api_type = get_api_type(code)
    adv_url = f"{BASE_URL}/{api_type}/adv"
    segments = ["", "", "", ""]
    segments[0] = code
    params = {"ClassCodeKey": ",".join(segments)}
    headers = COMMON_HEADERS.copy()
    headers["Referer"] = adv_url

    try:
        resp = session.get(adv_url, params=params, headers=headers, timeout=30)
    except Exception:
        return [], -1

    if resp.status_code != 200:
        return [], -resp.status_code

    html = resp.text

    if os.environ.get("GD_SAVE_RESPONSES"):
        debug_path = f"debug_{code}.html"
        with open(debug_path, "w", encoding="utf-8") as debug_file:
            debug_file.write(html)

    years = extract_years_from_html(html)
    total = extract_total_count(html)
    return years, total


def main() -> int:
    session = requests.Session()
    session.headers.update(COMMON_HEADERS)
    session.cookies.set("JSESSIONID", os.urandom(16).hex().upper(), domain="gd.pkulaw.com")

    print("父级分类\t子分类\t年份\t数量")
    grand_total = 0

    for parent, name, code in CATEGORIES:
        years, total = fetch_category_years(session, parent, name, code)
        if total < 0:
            print(f"{parent}\t{name}\t获取失败\t{abs(total)}")
            time.sleep(0.5)
            continue

        grand_total += total
        if years:
            for year, count in years:
                print(f"{parent}\t{name}\t{year}\t{count}")
            print(f"{parent}\t{name}\t合计\t{total}")
        else:
            print(f"{parent}\t{name}\t无年份数据\t0")

        time.sleep(0.5)

    print(f"总体\t\t合计\t{grand_total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
