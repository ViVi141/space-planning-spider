import os
import sys
import logging
from typing import List, Dict, Any, Iterable, Sequence
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

# 调整路径，确保可以导入 src 包
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
sys.path.append(PROJECT_ROOT)

from src.space_planning.spider.guangdong import GuangdongSpider, DUAL_REQUEST_MENUS  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def crawl_category_year(
    spider: GuangdongSpider,
    category_code: str,
    category_name: str,
    year: int,
    expected_count: int,
    api_config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    针对单个分类单个年份执行抓取，返回政策列表。
    """
    menu = api_config.get('menu', '')
    if menu in DUAL_REQUEST_MENUS:
        policies = spider._crawl_year_with_dual_request(
            category_code=category_code,
            target_year=year,
            expected_count=expected_count,
            api_config=api_config,
            keywords=None,
            start_date=None,
            end_date=None,
            disable_speed_limit=True,
            policy_callback=None
        )
    else:
        policies = spider._crawl_category_year(
            category_code=category_code,
            target_year=year,
            expected_count=expected_count,
            api_config=api_config,
            keywords=None,
            start_date=None,
            end_date=None,
            disable_speed_limit=True,
            policy_callback=None
        )

    rows: List[Dict[str, Any]] = []
    for policy in policies:
        title = policy.get('title') or policy.get('real_title') or f"政策ID: {policy.get('policy_id', '')}"
        url = policy.get('url') or policy.get('source', '')
        rows.append({
            '分类名称': category_name,
            '年份': year,
            '政策标题': title,
            '政策链接': url
        })
    return rows


def main(output_path: str = "guangdong_policies.xlsx") -> None:
    spider = GuangdongSpider(disable_proxy=True)
    logger.info("测试模式：代理已关闭，准备全量抓取")

    # 先刷新年份统计
    logger.info("刷新分类年份统计...")
    spider._refresh_category_year_counts()

    all_rows: List[Dict[str, Any]] = []
    flat_categories = spider._get_flat_categories()
    logger.info("共发现 %s 个分类子项", len(flat_categories))

    for category_name, category_code in flat_categories:
        api_config = spider._get_category_api_config(category_code)
        year_counts = spider.category_year_counts.get(category_code, [])
        if not year_counts:
            logger.warning("分类 %s(%s) 未获取到年份统计，跳过", category_name, category_code)
            continue

        logger.info("开始分类 %s(%s)，年份区间：%s", category_name, category_code, year_counts[:5])
        for year, expected_count in year_counts:
            if expected_count <= 0:
                logger.info("年份 %s 无数据，跳过", year)
                continue

            logger.info("抓取 %s(%s) - %s 年，预估 %s 条", category_name, category_code, year, expected_count)
            try:
                rows = crawl_category_year(
                    spider=spider,
                    category_code=category_code,
                    category_name=category_name,
                    year=year,
                    expected_count=expected_count,
                    api_config=api_config
                )
                all_rows.extend(rows)
                logger.info("完成 %s 年，获取 %s 条政策", year, len(rows))
            except Exception as exc:
                logger.error("抓取 %s(%s) %s 年失败: %s", category_name, category_code, year, exc)

    spider.session.close()

    if not all_rows:
        logger.warning("未获取到任何政策数据，Excel 不会生成")
        return

    headers = ['分类名称', '年份', '政策标题', '政策链接']
    write_xlsx(sorted(all_rows, key=lambda r: (r['分类名称'], r['年份'], r['政策标题'])), headers, output_path)
    logger.info("已写入 Excel：%s，共 %s 条数据", output_path, len(all_rows))


def write_xlsx(rows: Iterable[Dict[str, Any]], headers: Sequence[str], output_path: str) -> None:
    """
    使用标准库构造最小化 XLSX 文件（避免第三方依赖）。
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    def column_letter(idx: int) -> str:
        result = ''
        while idx:
            idx, rem = divmod(idx - 1, 26)
            result = chr(65 + rem) + result
        return result or 'A'

    def build_sheet_xml() -> str:
        rows_xml = []
        row_index = 1

        def build_row(values: Sequence[Any], r_idx: int) -> str:
            cells = []
            for c_idx, value in enumerate(values, start=1):
                cell_ref = f"{column_letter(c_idx)}{r_idx}"
                text = '' if value is None else escape(str(value))
                cell_xml = (
                    f'<c r="{cell_ref}" t="inlineStr">'
                    f'<is><t>{text}</t></is>'
                    f'</c>'
                )
                cells.append(cell_xml)
            return f'<row r="{r_idx}">{"".join(cells)}</row>'

        rows_xml.append(build_row(headers, row_index))

        for row in rows:
            row_index += 1
            values = [row.get('分类名称', ''), row.get('年份', ''), row.get('政策标题', ''), row.get('政策链接', '')]
            rows_xml.append(build_row(values, row_index))

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            f'{"".join(rows_xml)}'
            '</sheetData>'
            '</worksheet>'
        )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets>'
        '<sheet name="广东政策" sheetId="1" r:id="rId1"/>'
        '</sheets>'
        '</workbook>'
    )

    rels_root_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )

    sheet_xml = build_sheet_xml()

    with ZipFile(output_path, 'w', ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types_xml)
        zf.writestr('_rels/.rels', rels_root_xml)
        zf.writestr('xl/workbook.xml', workbook_xml)
        zf.writestr('xl/_rels/workbook.xml.rels', workbook_rels_xml)
        zf.writestr('xl/worksheets/sheet1.xml', sheet_xml)


if __name__ == "__main__":
    main()
