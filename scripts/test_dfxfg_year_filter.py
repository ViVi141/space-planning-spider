import os
import sys
import re
import logging
from typing import Dict, Any, List, Tuple

from bs4 import BeautifulSoup

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.space_planning.spider.guangdong import GuangdongSpider

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DUAL_MENUS = {'dfxfg', 'fljs', 'dfzfgz', 'sfjs'}
MAX_PAGES_TO_TEST = 5


def choose_target_year(year_counts: List[Tuple[int, int]]) -> int:
    for year, count in year_counts:
        if count > 0 and year <= 2020:
            return year
    for year, count in year_counts:
        if count > 0:
            return year
    return year_counts[0][0] if year_counts else 2020


def extract_years_from_html(html: str) -> Tuple[int, List[str]]:
    soup = BeautifulSoup(html, 'html.parser')
    checkboxes = soup.select('input.checkbox[name="recordList"]')
    infos = soup.select('div.related-info')

    years = []
    for info in infos:
        text = info.get_text(" ", strip=True)
        match = re.search(r'(19|20)\d{2}', text)
        if match:
            years.append(match.group(0))

    return len(checkboxes), years


def perform_dual_request_test(spider: GuangdongSpider, category_code: str, api_config: Dict[str, Any], target_year: int):
    menu = api_config['menu']
    library = api_config['library']
    class_flag = api_config['class_flag']
    base_url = spider.base_url
    page_size = 20

    headers = spider.headers.copy()
    headers['Referer'] = f"{base_url}/{menu}/"
    headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
    headers['X-Requested-With'] = 'XMLHttpRequest'

    common_params = {
        'Menu': menu,
        'Keywords': '',
        'SearchKeywordType': 'Title',
        'MatchType': 'Exact',
        'RangeType': 'Piece',
        'Library': library,
        'ClassFlag': class_flag,
        'GroupLibraries': '',
        'IsAdv': 'False',
        'GroupByIndex': '0',
        'OrderByIndex': '0',
        'ShowType': 'Default',
        'TitleKeywords': '',
        'FullTextKeywords': '',
        'QueryBase64Request': '',
        'VerifyCodeResult': '',
        'isEng': 'chinese',
        'X-Requested-With': 'XMLHttpRequest'
    }

    class_search_url = f"{base_url}/{menu}/search/ClassSearch"
    record_search_url = f"{base_url}/{menu}/search/RecordSearch"

    logger.info(f"=== 分类 {category_code} ({menu}) 测试 {target_year} 年 ===")

    class_params = common_params.copy()
    class_params.update({'ClassCodeKey': f",,,{target_year}"})

    try:
        resp_class = spider.session.post(class_search_url, data=class_params, headers=headers, timeout=20)
        resp_class.raise_for_status()
        logger.info(f"ClassSearch 成功: {resp_class.status_code}, 响应长度: {len(resp_class.text)}")
    except Exception as e:
        logger.error(f"ClassSearch 失败: {e}")
        return

    retrieved = 0
    cross_year = 0
    years_collected: List[str] = []

    for page_idx in range(MAX_PAGES_TO_TEST):
        record_params = common_params.copy()
        record_params.update({
            'QueryOnClick': 'False',
            'AfterSearch': 'False',
            'pdfStr': '',
            'pdfTitle': '',
            'ClassCodeKey': f",,,{target_year}",
            'GroupValue': '',
            'Pager.PageIndex': str(page_idx),
            'Pager.PageSize': str(page_size),
            'OldPageIndex': str(page_idx - 1) if page_idx > 0 else '',
            'newPageIndex': str(page_idx)
        })

        try:
            resp_record = spider.session.post(record_search_url, data=record_params, headers=headers, timeout=20)
            resp_record.raise_for_status()
            logger.info(f"RecordSearch 第 {page_idx + 1} 页成功: {resp_record.status_code}")
        except Exception as e:
            logger.error(f"RecordSearch 第 {page_idx + 1} 页失败: {e}")
            break

        count, years = extract_years_from_html(resp_record.text)
        if count == 0:
            logger.info(f"第 {page_idx + 1} 页为空或结构变化，停止")
            break

        retrieved += count
        years_collected.extend(years)

        page_cross_year = sum(1 for y in years if y and y != str(target_year))
        cross_year += page_cross_year

        logger.info(f"第 {page_idx + 1} 页：记录 {count} 条，解析年份 {len(years)} 条，跨年 {page_cross_year} 条")
        if page_cross_year > 0:
            logger.warning(f"跨年年份样本: {[y for y in years if y and y != str(target_year)]}")

    logger.info(f"分类 {category_code} 测试总结: 抓取 {retrieved} 条，跨年 {cross_year} 条")
    if years_collected:
        logger.info(f"年份样本（前 10 条）: {years_collected[:10]}")


def main():
    spider = GuangdongSpider(disable_proxy=True)
    logger.info("测试模式：代理已全面禁用")

    categories = []
    for code, api_config in spider._category_api_configs.items():
        if api_config['menu'] in DUAL_MENUS:
            categories.append((code, api_config))

    if not categories:
        logger.error("未找到支持双请求的分类配置")
        return

    logger.info(f"共找到 {len(categories)} 个分类待测试: {[code for code, _ in categories]}")

    for category_code, api_config in categories:
        try:
            year_counts = spider._fetch_category_year_counts(category_code, api_config) or []
        except Exception as e:
            logger.error(f"获取年份统计失败 {category_code}: {e}")
            year_counts = []

        if not year_counts:
            logger.warning(f"分类 {category_code} 未获取到年份统计，跳过")
            continue

        target_year = choose_target_year(year_counts)
        logger.info(f"分类 {category_code} 选定年份 {target_year} (统计样本: {year_counts[:5]})")
        perform_dual_request_test(spider, category_code, api_config, target_year)

    spider.session.close()


if __name__ == "__main__":
    main()
