#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
表格管理模块
负责表格数据的显示、分页、更新等操作
"""

from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from space_planning.core.logger_config import get_logger

logger = get_logger(__name__)


class TableManager:
    """表格管理器"""
    
    def __init__(self, table_widget, stats_label, page_info_label, 
                 prev_page_btn, next_page_btn, auto_scroll_checkbox,
                 max_display_rows=100, page_size=50):
        self.table = table_widget
        self.stats_label = stats_label
        self.page_info_label = page_info_label
        self.prev_page_btn = prev_page_btn
        self.next_page_btn = next_page_btn
        self.auto_scroll_checkbox = auto_scroll_checkbox
        self.max_display_rows = max_display_rows
        self.page_size = page_size
        self.current_page = 0
        self.current_data = []
    
    def refresh_table(self, data, only_last=False):
        """刷新表格数据（支持分页显示）"""
        self.current_data = data
        
        # 更新统计信息
        if self.stats_label is not None:
            self.stats_label.setText(f"共找到 {len(data)} 条政策")
        
        # 如果数据量很大，启用分页显示
        if len(data) > self.max_display_rows:
            self._show_paginated_data(data)
        else:
            # 数据量不大，直接显示全部
            self.page_info_label.setVisible(False)
            if only_last and data:
                row = len(data) - 1
                self.table.insertRow(row)
                item = data[row]
                self._set_table_row(row, item)
            else:
                self.table.setRowCount(len(data))
                for row, item in enumerate(data):
                    self._set_table_row(row, item)
    
    def _show_paginated_data(self, data):
        """分页显示数据"""
        total_pages = (len(data) + self.page_size - 1) // self.page_size
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(data))
        
        # 显示当前页数据
        page_data = data[start_idx:end_idx]
        self.table.setRowCount(len(page_data))
        for row, item in enumerate(page_data):
            self._set_table_row(row, item)
        
        # 更新分页信息
        self.page_info_label.setText(
            f"第 {self.current_page + 1}/{total_pages} 页 "
            f"(显示第 {start_idx + 1}-{end_idx} 条，共 {len(data)} 条)"
        )
        self.page_info_label.setVisible(True)
        
        # 更新导航按钮状态
        self.prev_page_btn.setVisible(self.current_page > 0)
        self.next_page_btn.setVisible(self.current_page < total_pages - 1)
    
    def prev_page(self):
        """上一页"""
        if self.current_page > 0:
            self.current_page -= 1
            self._show_paginated_data(self.current_data)
    
    def next_page(self):
        """下一页"""
        total_pages = (len(self.current_data) + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._show_paginated_data(self.current_data)
    
    def _add_single_row(self, item):
        """添加单行数据（优化性能，支持流动显示）"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._set_table_row(row, item)
        
        # 自动滚动到最新行（实现流动显示效果）
        if self.auto_scroll_checkbox.isChecked():
            self.table.scrollToBottom()
            # 选中最新行（可选，可能影响性能）
            # self.table.selectRow(row)
        
        # 立即刷新表格视图（确保实时显示）
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()  # 处理界面事件，确保立即显示
    
    def _set_table_row(self, row, item, compliance_analyzer=None):
        """设置表格行数据 - 增强字段识别"""
        # 检查item是元组还是字典
        if isinstance(item, (list, tuple)):
            # 元组/列表格式 (id, level, title, pub_date, source, content, category)
            # 数据库查询返回的顺序: (id, level, title, pub_date, source, content, category)
            level = str(item[1]) if len(item) > 1 and item[1] is not None else ""
            title = str(item[2]) if len(item) > 2 and item[2] is not None else ""
            pub_date = str(item[3]) if len(item) > 3 and item[3] is not None else ""
            source = str(item[4]) if len(item) > 4 and item[4] is not None else ""
            content = str(item[5]) if len(item) > 5 and item[5] is not None else ""
            category = str(item[6]) if len(item) > 6 and item[6] is not None else ""
        elif isinstance(item, dict):
            # 字典格式 - 支持多种字段名变体
            # level字段
            level = str(item.get('level', '')) or str(item.get('机构', '')) or ""
            
            # title字段 - 支持多种变体
            title = str(item.get('title', '')) or str(item.get('标题', '')) or str(item.get('name', '')) or ""
            
            # pub_date字段 - 支持多种日期字段名
            pub_date = (str(item.get('pub_date', '')) or 
                       str(item.get('publish_date', '')) or 
                       str(item.get('publishdate', '')) or
                       str(item.get('发布日期', '')) or
                       str(item.get('date', '')) or "")
            
            # source字段 - 支持多种来源字段名
            source = (str(item.get('source', '')) or 
                     str(item.get('url', '')) or 
                     str(item.get('link', '')) or
                     str(item.get('来源', '')) or
                     str(item.get('url_link', '')) or "")
            
            # content字段
            content = str(item.get('content', '')) or str(item.get('正文', '')) or str(item.get('text', '')) or ""
            
            # category字段 - 支持多种分类字段名
            category = (str(item.get('category', '')) or 
                       str(item.get('分类', '')) or
                       str(item.get('type', '')) or
                       str(item.get('policy_type', '')) or "")
        else:
            # 未知格式，尝试转换
            level = title = pub_date = source = content = category = ""
            try:
                item_str = str(item)
                # 如果是单个字符串，可能作为标题
                if item_str and len(item_str) > 10:
                    title = item_str
                    logger.warning(f"未知数据格式，尝试作为标题: {item_str[:50]}")
            except Exception:
                pass
        
        # 机构列
        level_item = QTableWidgetItem(level)
        level_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 0, level_item)
        
        # 标题列 - 支持换行，增强识别
        # 清理标题（移除可能的None、null等）
        title = str(title).strip() if title else ""
        if title.lower() in ['none', 'null']:
            title = ""
        
        if not title:
            title = "（无标题）"  # 如果标题为空，显示占位符
        
        title_item = QTableWidgetItem(title)
        title_item.setToolTip(title)  # 鼠标悬停显示完整标题
        self.table.setItem(row, 1, title_item)
        
        # 发布日期列 - 增强识别和格式化
        # 如果 pub_date 为空，尝试从其他字段获取或使用备用值
        if not pub_date or not pub_date.strip() or pub_date.strip() in ['None', 'null', 'NULL']:
            # 尝试从 item 中获取其他可能的日期字段
            if isinstance(item, dict):
                # 尝试从 effective_date 或其他日期字段获取
                pub_date = (item.get('effective_date', '') or 
                           item.get('validity', '') or
                           item.get('生效日期', '') or
                           item.get('effectivedate', ''))
            
            # 如果还是没有，尝试从 crawl_time 提取日期部分
            if not pub_date or not pub_date.strip():
                if isinstance(item, dict) and item.get('crawl_time'):
                    crawl_time = item.get('crawl_time', '')
                    # 提取日期部分（格式：YYYY-MM-DD HH:MM:SS）
                    if isinstance(crawl_time, str):
                        if ' ' in crawl_time:
                            pub_date = crawl_time.split(' ')[0]
                        else:
                            pub_date = crawl_time[:10] if len(crawl_time) >= 10 else crawl_time
                elif isinstance(item, (list, tuple)) and len(item) > 7:
                    # 尝试从元组的第7个位置获取crawl_time
                    crawl_time = item[7] if len(item) > 7 else ''
                    if crawl_time and isinstance(crawl_time, str):
                        if ' ' in crawl_time:
                            pub_date = crawl_time.split(' ')[0]
                        else:
                            pub_date = crawl_time[:10] if len(crawl_time) >= 10 else crawl_time
            
            # 如果还是为空，显示未知
            if not pub_date or not pub_date.strip() or pub_date.strip() in ['None', 'null', 'NULL']:
                pub_date = "未知"
        
        # 清理和标准化日期格式
        pub_date = str(pub_date).strip()
        if pub_date and pub_date != "未知":
            # 移除可能的None字符串
            if pub_date.lower() in ['none', 'null', '']:
                pub_date = "未知"
        
        date_item = QTableWidgetItem(pub_date)
        date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 2, date_item)
        
        # 来源列 - 超链接样式，增强识别
        # 清理来源（移除可能的None、null等）
        source = str(source).strip() if source else ""
        if source.lower() in ['none', 'null']:
            source = ""
        
        # 如果来源为空但有url或link字段，尝试使用
        if not source and isinstance(item, dict):
            source = item.get('url', '') or item.get('link', '')
            source = str(source).strip() if source else ""
        
        if not source:
            source = "（无来源）"  # 如果来源为空，显示占位符
        
        source_item = QTableWidgetItem(source)
        source_item.setForeground(QColor(0, 102, 204))  # 蓝色链接样式
        source_item.setToolTip(f"点击查看来源：{source}")
        self.table.setItem(row, 3, source_item)
        
        # 政策类型列 - 优先显示实际分类
        if category and category.strip():
            # 使用实际的分类信息
            type_item = QTableWidgetItem(category)
        else:
            # 如果分类为空，使用智能分类作为备选
            if compliance_analyzer:
                try:
                    policy_types = compliance_analyzer.classify_policy(title, content)
                    type_item = QTableWidgetItem(", ".join(policy_types) if policy_types else "未分类")
                except Exception as e:
                    logger.warning(f"分类政策失败: {e}")
                    type_item = QTableWidgetItem("未分类")
            else:
                type_item = QTableWidgetItem("未分类")
        
        type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 4, type_item)
        
        # 操作列 - 按钮样式
        action_item = QTableWidgetItem("📄 查看全文")
        action_item.setForeground(QColor(0, 128, 0))  # 绿色按钮样式
        action_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        action_item.setToolTip("点击查看政策全文")
        self.table.setItem(row, 5, action_item)

