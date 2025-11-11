# 广东省爬虫双请求年份筛选方案

## 1. 方案概览
- **目标**：精准获取广东政策库指定年份的数据，避免跨年与 500 页限制。
- **覆盖范围**：`dfxfg`（地方性法规）、`dfzfgz`（地方政府规章）、`sfjs`（自治条例和单行条例）、`fljs`（地方规范性文件）。
- **核心思路**：完全复刻前端的“`ClassSearch` → `RecordSearch`”双阶段提交，并在列表与详情层面双重校验年份。

## 2. 请求流程
1. **ClassSearch**
   - URL：`/{menu}/search/ClassSearch`
   - 关键参数：`ClassCodeKey=,,,{year}`、`ShowType=Default`
   - 作用：刷新服务端聚类上下文，确保后续列表仅关联目标年份。
2. **RecordSearch**
   - URL：`/{menu}/search/RecordSearch`
   - 关键参数：`ClassCodeKey=,,,{year}`、分页字段 `Pager.PageIndex` / `Pager.PageSize`
   - 作用：分页获取列表 HTML，解析 `input.checkbox[name="recordList"]`。

## 3. 年份校验
- **列表层**：从 `div.related-info` 提取年份，构建 `policy_id → year` 映射。
- **详情层**：`get_policy_detail` 解析正文内 `pub_date`。
- **过滤规则**：若任一层判断与目标年份不符，则跳过并记录日志（`跨年数据已过滤`）。

## 4. 运行步骤
1. 在根目录执行：
   ```powershell
   python scripts/export_guangdong_policies_excel.py
   ```
2. 脚本流程：
   - 调用 `GuangdongSpider._refresh_category_year_counts()` 读取全部可用年份。
   - 遍历每个分类、每个年份，执行 `_crawl_year_with_dual_request`。
   - 将通过年份校验的数据写入 Excel（默认 `guangdong_policies.xlsx`）。

## 5. 日志要点
- `分类[...] 年份区间`: 会输出“前 5 个年份 + 总数量”，便于核对是否包含 20 世纪数据。
- `跨年数据已过滤`: 表明该条记录被自动剔除，通常出现在 `fljs` 分类。
- `双请求模式完成`: 展示目标年份实际抓取条数，便于与聚合数量对照。

## 6. 常见问题
| 问题 | 处理方式 |
| ---- | -------- |
| 日志仅显示近 5 年 | 实际仍遍历全部年份，日志尾部会显示“共 X 个年份”提示。 |
| `fljs` 出现跨年 | 属于站点返回顺序问题，脚本会自动过滤，对最终 Excel 无影响。 |
| 20 世纪年份缺失 | 检查对应分类的聚合页面是否存在 `<a cluster_code="19xx">`，若无则需手动筛选确认。 |
| 网络被限流 | 脚本内置自动重试与延迟，可适当调小 `page_size` 或增加时间间隔。 |

## 7. 相关子系统
- 详情解析 `get_policy_detail`：负责标题、文号、发布日期与正文。
- 去重 `_deduplicate_policies`：使用内容 / checksum 双重判断。
- 导出脚本 `export_guangdong_policies_excel.py`：统一从上述接口消费数据并导出。

> 建议在正式跑全量前，先使用 `scripts/test_dfxfg_year_filter.py` 对关键年份做抽样验证，确保站点结构未变化。***

