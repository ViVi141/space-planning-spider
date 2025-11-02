from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QTextEdit, QFileDialog, QMessageBox, QSpinBox, QDialog, QDialogButtonBox, QListWidget, QRadioButton, QProgressBar, QDateEdit, QGroupBox, QCheckBox, QHeaderView, QMenu)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate, QTimer
from PyQt5.QtGui import QColor
import sys
import os
import threading
from datetime import datetime, timedelta
import re

# 启用SSL安全验证
# 移除SSL警告禁用，确保安全连接

from space_planning.core import database as db
from space_planning.spider.national import NationalSpider
from space_planning.utils.export import export_to_word
from space_planning.utils.compare import PolicyComparer
from space_planning.utils.compliance import ComplianceAnalyzer
from space_planning.gui.crawler_status_dialog import CrawlerStatusDialog
from space_planning.gui.search_thread import SearchThread
from space_planning.gui.table_manager import TableManager
from space_planning.gui.table_display_config import TableDisplayConfig
from space_planning.core.logger_config import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 从配置获取UI参数
        from space_planning.core.config import app_config
        ui_config = app_config.get_ui_config()
        
        self.max_display_rows = ui_config.get('max_display_rows', 100)  # 最大显示行数
        self.page_size = ui_config.get('page_size', 50)  # 每页行数
        self.current_page = 0  # 当前页码
        
        # 从配置获取应用信息
        from space_planning.core.config import APP_CONFIG
        app_name = APP_CONFIG['app_name']
        app_version = APP_CONFIG['app_version']
        self.setWindowTitle(f"{app_name} v{app_version} - ViVi141")
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), "../../../docs/icon.ico")
        if os.path.exists(icon_path):
            from PyQt5.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        
        # 从配置获取窗口大小
        window_width = ui_config.get('window_width', 1400)
        window_height = ui_config.get('window_height', 900)
        self.resize(window_width, window_height)
        
        # 设置窗口最小和最大尺寸，防止窗口被拉宽
        self.setMinimumSize(window_width, window_height)
        self.setMaximumSize(window_width, window_height)  # 固定窗口大小，不允许自动扩展
        
        # 默认禁用代理 - 不在这里初始化代理系统
        from space_planning.spider.proxy_pool import set_global_proxy_enabled
        from space_planning.core.logger_config import get_logger
        logger = get_logger(__name__)
        
        set_global_proxy_enabled(False)
        logger.info("程序默认不使用代理，可在代理设置中启用")
        
        # 创建共享的爬虫实例
        from space_planning.spider.national import NationalSpider
        from space_planning.spider.national_multithread import NationalMultiThreadSpider
        from space_planning.spider.guangdong import GuangdongSpider, GuangdongMultiThreadSpider
        from space_planning.spider.mnr import MNRSpider
        from space_planning.spider.mnr_multithread import MNRMultiThreadSpider
        
        # 从配置获取线程数
        default_thread_count = ui_config.get('default_thread_count', 4)
        
        # 为每个机构创建持久的爬虫实例，保持监控数据
        self.national_spider = NationalSpider()
        self.national_multithread_spider = NationalMultiThreadSpider(max_workers=default_thread_count)
        self.guangdong_spider = GuangdongSpider()
        self.guangdong_multithread_spider = GuangdongMultiThreadSpider(max_workers=default_thread_count)
        self.mnr_spider = MNRSpider()
        self.mnr_multithread_spider = MNRMultiThreadSpider(max_workers=default_thread_count)
        
        # 默认使用国家级爬虫
        self.spider = self.national_spider
        
        self.init_ui()
    

    
    def create_menu_bar(self):
        """创建菜单栏"""
        from PyQt5.QtWidgets import QAction, QMenuBar, QMenu
        
        menubar: QMenuBar = self.menuBar()
        if menubar is None:
            return
            
        file_menu: QMenu = menubar.addMenu('文件')
        tools_menu: QMenu = menubar.addMenu('工具')
        settings_menu: QMenu = menubar.addMenu('设置')
        help_menu: QMenu = menubar.addMenu('帮助')
        
        if file_menu is not None:
            # 文件菜单
            export_action = QAction('导出数据 (Word/Excel/文本)', self)
            export_action.triggered.connect(self.export_data)
            file_menu.addAction(export_action)
        
        if tools_menu is not None:
            # 工具菜单
            status_action = QAction('爬虫状态实时监控', self)
            status_action.triggered.connect(self.show_crawler_status)
            tools_menu.addAction(status_action)
            
            # 代理诊断菜单
            proxy_diagnostic_action = QAction('代理诊断', self)
            proxy_diagnostic_action.triggered.connect(self.show_proxy_diagnostic)
            tools_menu.addAction(proxy_diagnostic_action)
            
            # 清空代理菜单
            clear_proxy_action = QAction('清空代理', self)
            clear_proxy_action.triggered.connect(self.clear_proxy_manually)
            tools_menu.addAction(clear_proxy_action)
            
            # 数据库管理菜单
            db_action = QAction('数据库管理', self)
            db_action.triggered.connect(self.show_database_manager)
            tools_menu.addAction(db_action)
            
            # 清理数据库功能已迁移到数据库管理对话框中
        
        if settings_menu is not None:
            # 设置菜单
            crawler_settings_action = QAction('爬虫设置', self)
            crawler_settings_action.triggered.connect(self.show_crawler_settings)
            settings_menu.addAction(crawler_settings_action)
            
            # 代理设置菜单项
            proxy_settings_action = QAction('代理设置', self)
            proxy_settings_action.triggered.connect(self.show_proxy_settings)
            settings_menu.addAction(proxy_settings_action)
        
        if help_menu is not None:
            # 帮助菜单
            about_action = QAction('关于', self)
            about_action.triggered.connect(self.show_about)
            help_menu.addAction(about_action)

    def init_ui(self):
        # 创建菜单栏
        self.create_menu_bar()
        
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # 预设模式区域
        mode_group = QGroupBox("预设模式")
        mode_layout = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "日常监控模式 - 最近30天",
            "项目分析模式 - 最近6个月", 
            "历史补全模式 - 最近2年",
            "快速预览模式 - 最近7天",
            "自定义模式 - 手动设置时间"
        ])
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(QLabel("选择模式："))
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        mode_group.setLayout(mode_layout)

        # 查询参数区域
        query_group = QGroupBox("查询参数")
        query_layout = QVBoxLayout()
        
        # 第一行：机构、关键词
        row1_layout = QHBoxLayout()
        self.level_combo = QComboBox()
        
        # 动态加载已实现的爬虫机构列表
        try:
            from space_planning.spider import get_all_spider_levels
            spider_levels = get_all_spider_levels()
            self.level_combo.addItems(spider_levels)
            logger.debug(f"动态加载的爬虫机构: {spider_levels}")
        except Exception as e:
            logger.error(f"动态加载爬虫机构失败: {e}", exc_info=True)
            # 降级方案：只显示已实现的爬虫
            self.level_combo.addItems(["住房和城乡建设部", "广东省人民政府", "自然资源部"])
        
        # 连接机构选择变化事件
        self.level_combo.currentTextChanged.connect(self.on_level_changed)
        
        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText("请输入项目关键词，如'控制性详细规划'、'建设用地'...")
        self.keyword_edit.setMinimumWidth(300)
        row1_layout.addWidget(QLabel("机构："))
        row1_layout.addWidget(self.level_combo)
        row1_layout.addWidget(QLabel("项目关键词："))
        row1_layout.addWidget(self.keyword_edit)
        row1_layout.addStretch()
        
        # 时间范围区域
        date_group = QGroupBox("时间范围")
        date_layout = QHBoxLayout()
        
        # 添加时间过滤开关
        self.time_filter_checkbox = QCheckBox("启用时间过滤")
        self.time_filter_checkbox.setChecked(True)  # 默认启用
        self.time_filter_checkbox.stateChanged.connect(self.on_time_filter_changed)
        date_layout.addWidget(self.time_filter_checkbox)
        
        date_layout.addWidget(QLabel("开始日期："))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))  # 默认30天前
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.dateChanged.connect(self.on_date_changed)
        date_layout.addWidget(self.start_date_edit)
        
        date_layout.addWidget(QLabel("结束日期："))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate())  # 默认今天
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.dateChanged.connect(self.on_date_changed)
        date_layout.addWidget(self.end_date_edit)
        
        date_group.setLayout(date_layout)
        
        # 第三行：检索说明和防反爬虫选项
        row3_layout = QHBoxLayout()
        info_label = QLabel("💡 系统将基于时间区间自动检索，无需设置页数限制")
        info_label.setStyleSheet("color: #666; font-size: 12px; font-style: italic;")
        row3_layout.addWidget(info_label)
        
        # 防反爬虫选项
        self.anti_crawler_checkbox = QCheckBox("启用速度限制")
        self.anti_crawler_checkbox.setChecked(True)
        self.anti_crawler_checkbox.setToolTip("禁用后将使用最快速度，但保留UA轮换等其他防反爬虫措施")
        self.anti_crawler_checkbox.setStyleSheet("color: #666; font-size: 12px;")
        
        # 速度选择
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["正常速度", "快速模式", "慢速模式"])
        self.speed_combo.setCurrentText("正常速度")
        self.speed_combo.setToolTip("选择查询速度，快速模式可能被反爬虫检测")
        self.speed_combo.setStyleSheet("color: #666; font-size: 12px;")
        self.speed_combo.setMaximumWidth(100)
        
        # 多线程选项
        self.multithread_checkbox = QCheckBox("启用多线程")
        self.multithread_checkbox.setChecked(False)  # 默认关闭
        self.multithread_checkbox.setToolTip("启用多线程爬取，可大幅提升爬取速度（所有机构都支持）")
        self.multithread_checkbox.setStyleSheet("color: #666; font-size: 12px;")
        
        # 线程数选择
        self.thread_count_combo = QComboBox()
        self.thread_count_combo.addItems(["2", "4", "6", "8", "10"])
        self.thread_count_combo.setCurrentText("4")
        self.thread_count_combo.setToolTip("选择线程数量，建议4-8个线程")
        self.thread_count_combo.setStyleSheet("color: #666; font-size: 12px;")
        self.thread_count_combo.setMaximumWidth(60)
        self.thread_count_combo.setEnabled(False)  # 默认禁用
        
        # 连接多线程选项变化
        self.multithread_checkbox.stateChanged.connect(self.on_multithread_changed)
        
        row3_layout.addStretch()
        row3_layout.addWidget(self.anti_crawler_checkbox)
        row3_layout.addWidget(QLabel("查询速度："))
        row3_layout.addWidget(self.speed_combo)
        row3_layout.addWidget(self.multithread_checkbox)
        row3_layout.addWidget(QLabel("线程数："))
        row3_layout.addWidget(self.thread_count_combo)
        
        # 表格自动滚动选项
        self.auto_scroll_checkbox = QCheckBox("表格自动滚动")
        self.auto_scroll_checkbox.setChecked(True)
        self.auto_scroll_checkbox.setToolTip("启用后表格会自动滚动到最新数据")
        self.auto_scroll_checkbox.setStyleSheet("color: #666; font-size: 12px;")
        row3_layout.addWidget(self.auto_scroll_checkbox)
        
        query_layout.addLayout(row1_layout)
        query_layout.addWidget(date_group) # 添加时间范围组
        query_layout.addLayout(row3_layout)
        query_group.setLayout(query_layout)

        # 操作按钮区域
        button_layout = QHBoxLayout()
        self.search_btn = QPushButton("🔍 智能查询")
        self.search_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        self.search_btn.setMinimumHeight(35)
        
        self.compliance_btn = QPushButton("📋 合规性分析")
        self.compliance_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px; }")
        self.compliance_btn.setMinimumHeight(35)
        
        self.export_btn = QPushButton("📄 导出报告")
        self.batch_update_btn = QPushButton("📥 批量爬取")
        self.compare_btn = QPushButton("🔍 智能对比")
        
        button_layout.addWidget(self.search_btn)
        button_layout.addWidget(self.compliance_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.batch_update_btn)
        button_layout.addWidget(self.compare_btn)
        button_layout.addStretch()

        # 进度显示区域
        progress_layout = QHBoxLayout()
        self.progress_label = QLabel("就绪")
        self.progress_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addStretch()

        # 中部：结果表格和统计信息
        table_group = QGroupBox("查询结果")
        table_layout = QVBoxLayout()
        
        # 统计信息栏
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("共找到 0 条政策")
        self.stats_label.setStyleSheet("color: #666; font-size: 12px; font-weight: bold;")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        
        # 分页控制（当数据量大时显示）
        self.page_info_label = QLabel("")
        self.page_info_label.setStyleSheet("color: #666; font-size: 12px;")
        self.page_info_label.setVisible(False)
        stats_layout.addWidget(self.page_info_label)
        
        # 分页导航按钮
        self.prev_page_btn = QPushButton("◀ 上一页")
        self.prev_page_btn.setMaximumWidth(80)
        self.prev_page_btn.clicked.connect(self.prev_page)
        self.prev_page_btn.setVisible(False)
        stats_layout.addWidget(self.prev_page_btn)
        
        self.next_page_btn = QPushButton("下一页 ▶")
        self.next_page_btn.setMaximumWidth(80)
        self.next_page_btn.clicked.connect(self.next_page)
        self.next_page_btn.setVisible(False)
        stats_layout.addWidget(self.next_page_btn)
        
        table_layout.addLayout(stats_layout)
        
        # 表格
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["机构", "标题", "发布日期", "来源", "政策类型", "操作"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # 初始化表格配置（默认使用第一个机构的配置）
        initial_level = self.level_combo.currentText() if hasattr(self, 'level_combo') else "住房和城乡建设部"
        TableDisplayConfig.apply_table_config(self.table, initial_level)
        
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)  # 允许文字换行
        
        # 设置表格右键菜单
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        # 设置行高
        vheader = self.table.verticalHeader()
        if vheader is not None:
            vheader.setDefaultSectionSize(60)  # 设置行高
        
        table_layout.addWidget(self.table)
        table_group.setLayout(table_layout)

        # 底部：全文展示区
        full_text_group = QGroupBox("政策全文")
        full_text_layout = QVBoxLayout()
        
        # 全文标题栏
        title_bar = QHBoxLayout()
        self.full_text_title = QLabel("请点击表格中的'查看全文'查看政策内容")
        self.full_text_title.setStyleSheet("color: #666; font-size: 12px;")
        title_bar.addWidget(self.full_text_title)
        title_bar.addStretch()
        
        # 复制按钮
        self.copy_btn = QPushButton("📋 复制全文")
        self.copy_btn.clicked.connect(self.copy_full_text)
        self.copy_btn.setMaximumWidth(100)
        title_bar.addWidget(self.copy_btn)
        
        full_text_layout.addLayout(title_bar)
        
        # 全文内容
        self.full_text = QTextEdit()
        self.full_text.setReadOnly(True)
        self.full_text.setPlaceholderText("在此处显示政策全文...\n\n💡 提示：点击表格中的'📄 查看全文'按钮查看具体政策内容")
        self.full_text.setMinimumHeight(300)  # 增加最小高度
        self.full_text.setMaximumHeight(1000)  # 增加最大高度
        self.full_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.full_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.full_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)  # 设置自动换行
        self.full_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 12px;
                background-color: #fafafa;
                font-family: "Microsoft YaHei", Arial, sans-serif;
                font-size: 13px;
                line-height: 1.6;
                selection-background-color: #0078d4;
                selection-color: white;
            }
            QTextEdit QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QTextEdit QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 6px;
                min-height: 20px;
            }
            QTextEdit QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
        """)
        
        full_text_layout.addWidget(self.full_text)
        full_text_group.setLayout(full_text_layout)

        # 组装布局
        main_layout.addWidget(mode_group)
        main_layout.addWidget(query_group)
        main_layout.addLayout(button_layout)
        main_layout.addLayout(progress_layout)
        main_layout.addWidget(table_group)
        main_layout.addWidget(full_text_group)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 信号槽绑定
        self.search_btn.clicked.connect(self.on_smart_search)
        self.compliance_btn.clicked.connect(self.on_compliance_analysis)
        self.export_btn.clicked.connect(self.on_export)
        self.batch_update_btn.clicked.connect(self.on_batch_update)
        self.compare_btn.clicked.connect(self.on_compare)
        self.table.cellClicked.connect(self.on_table_click)
        
        # 存储当前数据
        self.current_data = []
        
        # 初始化 TableManager
        self.table_manager = TableManager(
            table_widget=self.table,
            stats_label=self.stats_label,
            page_info_label=self.page_info_label,
            prev_page_btn=self.prev_page_btn,
            next_page_btn=self.next_page_btn,
            auto_scroll_checkbox=self.auto_scroll_checkbox,
            max_display_rows=self.max_display_rows,
            page_size=self.page_size
        )
        # 初始化对比器
        self.comparer = PolicyComparer()
        # 初始化合规性分析器
        self.compliance_analyzer = ComplianceAnalyzer()
    


    def on_mode_changed(self, mode_text):
        """预设模式改变时的处理"""
        # 临时断开日期变化信号，避免触发模式切换
        self.start_date_edit.dateChanged.disconnect(self.on_date_changed)
        self.end_date_edit.dateChanged.disconnect(self.on_date_changed)
        
        try:
            if "日常监控模式" in mode_text:
                # 最近30天
                self.start_date_edit.setDate(QDate.currentDate().addDays(-30))
                self.end_date_edit.setDate(QDate.currentDate())
            elif "项目分析模式" in mode_text:
                # 自定义时间，默认最近6个月
                self.start_date_edit.setDate(QDate.currentDate().addMonths(-6))
                self.end_date_edit.setDate(QDate.currentDate())
            elif "历史补全模式" in mode_text:
                # 完整时间段，默认最近2年
                self.start_date_edit.setDate(QDate.currentDate().addYears(-2))
                self.end_date_edit.setDate(QDate.currentDate())
            elif "快速预览模式" in mode_text:
                # 最近7天
                self.start_date_edit.setDate(QDate.currentDate().addDays(-7))
                self.end_date_edit.setDate(QDate.currentDate())
            elif "自定义模式" in mode_text:
                # 切换到自定义模式时，确保日期是当前日期
                self.start_date_edit.setDate(QDate.currentDate())
                self.end_date_edit.setDate(QDate.currentDate())
        finally:
            # 重新连接日期变化信号
            self.start_date_edit.dateChanged.connect(self.on_date_changed)
            self.end_date_edit.dateChanged.connect(self.on_date_changed)

    def on_date_changed(self):
        """日期变化时自动切换到自定义模式"""
        self.mode_combo.setCurrentText("自定义模式 - 手动设置时间")

    def on_time_filter_changed(self, state):
        """时间过滤开关变化时的处理"""
        if state == Qt.CheckState.Checked:
            self.time_filter_checkbox.setText("启用时间过滤")
            self.start_date_edit.setEnabled(True)
            self.end_date_edit.setEnabled(True)
        else:
            self.time_filter_checkbox.setText("禁用时间过滤")
            self.start_date_edit.setEnabled(False)
            self.end_date_edit.setEnabled(False)
            # 如果禁用时间过滤，则使用当前日期作为时间范围
            self.start_date_edit.setDate(QDate.currentDate())
            self.end_date_edit.setDate(QDate.currentDate())

    def on_multithread_changed(self, state):
        """多线程选项变化事件"""
        is_enabled = state == Qt.CheckState.Checked
        self.thread_count_combo.setEnabled(is_enabled)
        
        # 检查当前选择的机构是否支持多线程
        current_level = self.level_combo.currentText()
        if is_enabled and current_level not in ["住房和城乡建设部", "广东省人民政府", "自然资源部"]:
            QMessageBox.warning(self, "提示", "多线程功能目前仅支持住建部、广东省和自然资源部爬虫")
            self.multithread_checkbox.setChecked(False)
            self.thread_count_combo.setEnabled(False)
            return
        
        if is_enabled:
            self.progress_label.setText("已启用多线程爬取")
        else:
            self.progress_label.setText("已禁用多线程爬取")
    
    def on_level_changed(self, level):
        """机构选择变化事件"""
        # 根据选择的机构应用相应的表格显示配置
        try:
            TableDisplayConfig.apply_table_config(self.table, level)
            logger.debug(f"已为机构 '{level}' 应用表格显示配置")
        except Exception as e:
            logger.warning(f"应用表格配置失败: {e}", exc_info=True)
        
        # 如果当前启用了多线程，但选择的不是支持的机构，则禁用多线程
        supported_levels = ["住房和城乡建设部", "广东省人民政府", "自然资源部"]
        if self.multithread_checkbox.isChecked() and level not in supported_levels:
            self.multithread_checkbox.setChecked(False)
            self.thread_count_combo.setEnabled(False)
            QMessageBox.information(self, "提示", f"已自动禁用多线程功能，因为{level}暂不支持多线程爬取")

    def on_smart_search(self):
        """智能查询：自动判断数据来源，一键获取最新结果"""
        # 如果正在搜索，则停止搜索
        if hasattr(self, 'search_thread') and self.search_thread.isRunning():
            self.search_thread.stop()
            self.progress_label.setText("正在停止...")
            return
            
        try:
            # 防止重复点击
            if hasattr(self, 'search_thread') and self.search_thread.isRunning():
                return
            
            # 显示进度提示
            self.search_btn.setText("⏹️ 停止查询")
            self.search_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 8px; }")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # 不确定进度
            self.progress_label.setText("正在查询数据库...")
            QApplication.processEvents()
            
            level = self.level_combo.currentText()
            keywords = self.keyword_edit.text().strip()
            
            if keywords:
                keywords = keywords.split()
            
            # 获取时间区间参数
            if self.time_filter_checkbox.isChecked():
                start_date = self.start_date_edit.date().toString('yyyy-MM-dd')
                end_date = self.end_date_edit.date().toString('yyyy-MM-dd')
            else:
                # 如果禁用时间过滤，则不传递时间参数
                start_date = None
                end_date = None
            
            # 检查是否需要爬取新数据
            db_results = db.search_policies(level, keywords, start_date, end_date)
            need_crawl = self._need_crawl_new_data(db_results, keywords)
            
            # 优先级处理：查询速度设置 > 爬虫设置
            # 1. 获取查询速度设置（优先级最高）
            speed_mode = self.speed_combo.currentText()
            enable_anti_crawler = self.anti_crawler_checkbox.isChecked()
            
            # 2. 根据速度模式动态调整防反爬虫设置
            if speed_mode == "快速模式":
                # 快速模式：禁用大部分防反爬虫措施，优先速度
                enable_anti_crawler = False
                self.progress_label.setText("使用快速模式：已禁用防反爬虫限制")
            elif speed_mode == "慢速模式":
                # 慢速模式：启用所有防反爬虫措施，优先安全
                enable_anti_crawler = True
                self.progress_label.setText("使用慢速模式：已启用完整防反爬虫措施")
            else:  # 正常速度
                # 正常模式：使用用户设置的防反爬虫开关
                self.progress_label.setText(f"使用正常速度：防反爬虫{'已启用' if enable_anti_crawler else '已禁用'}")
            
            # 3. 显示设置优先级提示
            if need_crawl:
                priority_msg = f"设置优先级：查询速度({speed_mode}) > 爬虫设置"
                self.progress_label.setText(f"{priority_msg} - 正在准备爬取...")
                QApplication.processEvents()
            
            # 获取多线程设置
            use_multithread = self.multithread_checkbox.isChecked()
            thread_count_text = self.thread_count_combo.currentText()
            thread_count = int(thread_count_text) if thread_count_text else 4
            
            # 创建并启动搜索线程
            self.current_data = [] # 清空当前数据
            self.refresh_table([]) # 清空表格
            # 传递None给SearchThread，让它根据level动态创建爬虫
            self.search_thread = SearchThread(level, keywords, need_crawl, start_date, end_date, enable_anti_crawler, speed_mode, None, self, use_multithread, thread_count)
            self.search_thread.progress_signal.connect(self.update_progress)
            self.search_thread.result_signal.connect(self.update_results)
            self.search_thread.single_policy_signal.connect(self.on_new_policy) # 新增信号连接
            self.search_thread.finished_signal.connect(self.search_finished)
            self.search_thread.error_signal.connect(self.search_error)
            self.search_thread.data_count_signal.connect(self.on_data_count_update) # 连接数据量信号
            self.search_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"智能查询失败: {str(e)}")
            self.reset_search_ui()
    
    def update_progress(self, message):
        """更新进度显示"""
        self.progress_label.setText(message)
        logger.debug(message)
        
        # 如果消息包含"已保存"，更新统计信息
        if "已保存" in message and hasattr(self, 'current_data'):
            if self.stats_label is not None:
                self.stats_label.setText(f"共找到 {len(self.current_data)} 条政策")
        
        # 处理爬取统计信息
        if "爬取完成统计:" in message:
            # 这是一个统计信息的开始，可以特殊处理
            pass
        elif "总爬取数量:" in message or "过滤后数量:" in message or "最终保存数量:" in message:
            # 这些是统计信息，可以高亮显示
            pass
        
        QApplication.processEvents()
    
    def update_results(self, results):
        """实时更新结果表格"""
        # 检查是否是最终查询结果（爬取完成后的查询）
        # 如果是最终查询，且当前数据量大于查询结果，说明有实时爬取的数据
        if len(self.current_data) > len(results) and len(self.current_data) > 0:
            logger.debug(f"检测到实时爬取数据，当前数据量: {len(self.current_data)}, 查询结果: {len(results)}")
            logger.debug("保留实时爬取的数据，不覆盖")
            # 保留实时爬取的数据，不覆盖
            return
        
        # 如果是初始查询（没有实时数据），则正常更新
        if len(self.current_data) == 0:
            logger.debug(f"初始查询结果: {len(results)} 条")
        else:
            logger.debug(f"更新查询结果: 当前 {len(self.current_data)} 条 -> 新结果 {len(results)} 条")
        
        # 取消数据限制，显示所有结果
        self.current_data = list(results)
        
        self.refresh_table(self.current_data) # 刷新表格
        QApplication.processEvents()
    
    def on_new_policy(self, policy):
        """新增政策信号处理"""
        try:
            logger.info(f"收到新政策信号: {type(policy)}, 键={list(policy.keys()) if isinstance(policy, dict) else 'N/A'}")
            
            # 检查policy格式
            if not isinstance(policy, dict):
                logger.error(f"政策格式错误: 期望dict，实际{type(policy)}")
                return
            
            # 检查必需的字段（content是可选的，如果缺失会自动添加空字符串）
            required_fields = ['level', 'title', 'pub_date', 'source', 'crawl_time']
            missing_fields = [field for field in required_fields if field not in policy]
            if missing_fields:
                logger.warning(f"政策缺少必需字段: {missing_fields}, 可用字段: {list(policy.keys())}")
            
            # 确保 content 字段存在（如果缺失，添加空字符串）
            if 'content' not in policy:
                policy['content'] = ""
                logger.debug(f"政策缺少 content 字段，已添加空字符串: {policy.get('title', 'N/A')[:50]}")
            
            # 立即保存到数据库
            try:
                db.insert_policy(
                    policy.get('level', ''), 
                    policy.get('title', ''), 
                    policy.get('pub_date', ''), 
                    policy.get('source', ''), 
                    policy.get('content', ''), 
                    policy.get('crawl_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    policy.get('category')  # 添加分类信息
                )
                logger.debug(f"政策已保存到数据库: {policy.get('title', 'N/A')[:50]}")
            except Exception as db_error:
                logger.error(f"保存政策到数据库失败: {db_error}", exc_info=True)
            
            # policy为dict，需转为tuple与表格结构一致
            # 注意：数据库返回的字段顺序是 (id, level, title, pub_date, source, content, category)
            row = (
                None, 
                policy.get('level', ''), 
                policy.get('title', ''), 
                policy.get('pub_date', ''), 
                policy.get('source', ''), 
                policy.get('content', ''), 
                policy.get('category', '')
            )
            self.current_data.append(row)
            logger.debug(f"政策已添加到current_data，当前总数: {len(self.current_data)}")
            
            # 实时显示：每一条都立即显示
            try:
                self._add_single_row(row)
                logger.debug(f"政策已添加到表格: {policy.get('title', 'N/A')[:50]}")
            except Exception as add_error:
                logger.error(f"添加行到表格失败: {add_error}", exc_info=True)
                raise
            
            # 更新统计信息
            if self.stats_label is not None:
                self.stats_label.setText(f"共找到 {len(self.current_data)} 条政策")
            
            # 对于广东省，立即更新界面，实现流动显示效果
            if policy.get('level', '') == '广东省人民政府':
                QApplication.processEvents()  # 立即处理界面事件，确保实时显示
            else:
                # 其他机构批量更新界面，减少频繁刷新
                self._update_ui_periodically()
            
        except Exception as e:
            logger.error(f"处理新政策失败: {e}", exc_info=True)
            import traceback
            logger.error(f"详细错误:\n{traceback.format_exc()}")
            # 即使保存失败，也要尝试显示在界面上
            try:
                row = (
                    None, 
                    policy.get('level', '') if isinstance(policy, dict) else '', 
                    policy.get('title', '') if isinstance(policy, dict) else str(policy), 
                    policy.get('pub_date', '') if isinstance(policy, dict) else '', 
                    policy.get('source', '') if isinstance(policy, dict) else '', 
                    policy.get('content', '') if isinstance(policy, dict) else '', 
                    policy.get('category', '') if isinstance(policy, dict) else ''
                )
                self.current_data.append(row)
                self._add_single_row(row)
                
                if self.stats_label is not None:
                    self.stats_label.setText(f"共找到 {len(self.current_data)} 条政策")
                
                # 减少界面刷新频率
                self._update_ui_periodically()
            except Exception as e2:
                logger.error(f"显示新政策失败: {e2}", exc_info=True)

    def on_data_count_update(self, count):
        """接收数据量更新信号"""
        logger.debug(f"收到数据量更新信号: {count}")
        # 如果当前数据量小于接收到的数量，说明有新的数据
        if len(self.current_data) < count:
            logger.debug(f"数据量不匹配，当前: {len(self.current_data)}, 接收: {count}")
            # 可以选择重新查询数据库或保持当前状态

    def search_finished(self):
        """搜索完成"""
        self.progress_label.setText("查询完成")
        self.progress_bar.setVisible(False)
        self.search_btn.setText("🔍 智能查询")
        self.search_btn.setEnabled(True)
        
        # 显示结果统计 - 使用实际的数据量
        actual_count = len(self.current_data)
        QMessageBox.information(self, "查询完成", 
            f"🎉 智能查询完成！\n\n"
            f"📊 共找到 {actual_count} 条政策")
    
    def search_error(self, error_msg):
        """搜索出错"""
        QMessageBox.critical(self, "错误", f"智能查询失败: {error_msg}")
        self.reset_search_ui()
    
    def reset_search_ui(self):
        """重置搜索UI状态"""
        self.progress_label.setText("就绪")
        self.progress_bar.setVisible(False)
        self.search_btn.setText("🔍 智能查询")
        self.search_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
    
    def _need_crawl_new_data(self, db_results, keywords):
        """判断是否需要爬取新数据"""
        # 如果没有关键词，默认爬取一些最新数据
        if not keywords:
            return True
        
        # 如果数据库结果太少，爬取更多
        if len(db_results) < 5:
            return True
        
        # 检查数据库中最新的数据时间
        if db_results:
            # 兼容不同的数据格式
            latest_dates = []
            for result in db_results:
                if isinstance(result, (list, tuple)) and len(result) > 3:
                    latest_dates.append(result[3])
                elif isinstance(result, dict):
                    latest_dates.append(result.get('pub_date', ''))
            
            if latest_dates:
                latest_date = max(date for date in latest_dates if date)
                # 如果最新数据超过7天，爬取新数据
                try:
                    latest_datetime = datetime.strptime(latest_date, '%Y-%m-%d')
                    if datetime.now() - latest_datetime > timedelta(days=7):
                        return True
                except:
                    pass
        
        return False

    def refresh_table(self, data, only_last=False):
        """刷新表格数据（支持分页显示）- 委托给TableManager"""
        self.current_data = data
        self.table_manager.current_data = data
        self.table_manager.refresh_table(data, only_last)
    
    def prev_page(self):
        """上一页 - 委托给TableManager"""
        self.table_manager.prev_page()
    
    def next_page(self):
        """下一页 - 委托给TableManager"""
        self.table_manager.next_page()
    
    def _add_single_row(self, item):
        """添加单行数据（优化性能）- 委托给TableManager"""
        self.table_manager._add_single_row(item)
    
    def _set_table_row(self, row, item):
        """设置表格行数据 - 委托给TableManager处理"""
        self.table_manager._set_table_row(row, item, self.compliance_analyzer)

    def on_export(self):
        """导出数据 - 支持政策选择和多种格式"""
        if not self.current_data:
            QMessageBox.warning(self, "警告", "没有数据可导出")
            return
        
        # 创建政策选择和格式选择对话框
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QDialogButtonBox, QListWidget, QCheckBox, QGroupBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("选择政策和导出格式")
        dialog.setModal(True)
        dialog.resize(600, 500)
        
        layout = QVBoxLayout()
        
        # 政策选择区域
        policy_group = QGroupBox("选择要导出的政策")
        policy_layout = QVBoxLayout()
        
        # 全选复选框
        select_all_checkbox = QCheckBox("全选")
        policy_layout.addWidget(select_all_checkbox)
        
        # 政策列表
        policy_list = QListWidget()
        policy_list.setSelectionMode(QListWidget.MultiSelection)
        
        # 添加政策到列表
        for i, policy in enumerate(self.current_data):
            if isinstance(policy, (list, tuple)):
                title = str(policy[2]) if len(policy) > 2 else "未知标题"
                level = str(policy[1]) if len(policy) > 1 else "未知机构"
            elif isinstance(policy, dict):
                title = str(policy.get('title', '未知标题'))
                level = str(policy.get('level', '未知机构'))
            else:
                title = "未知标题"
                level = "未知机构"
            
            policy_list.addItem(f"{i+1}. {title} ({level})")
        
        policy_layout.addWidget(policy_list)
        policy_group.setLayout(policy_layout)
        layout.addWidget(policy_group)
        
        # 格式选择区域
        format_group = QGroupBox("选择导出格式")
        format_layout = QVBoxLayout()
        
        format_layout.addWidget(QLabel("请选择导出格式："))
        format_combo = QComboBox()
        format_combo.addItems([
            "Word文档 (*.docx)",
            "Excel表格 (*.xlsx)", 
            "文本文件 (*.txt)",
            "Markdown文档 (*.md)",
            "RAG知识库 (*.md/*.json/*.txt)",
            "--- 分条导出 ---",
            "分条导出Word文档 (每个政策一个文件)",
            "分条导出文本文件 (每个政策一个文件)",
            "分条导出Markdown (每个政策一个文件)"
        ])
        format_layout.addWidget(format_combo)
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        # 全选功能
        def on_select_all_changed(state):
            if state:
                for i in range(policy_list.count()):
                    item = policy_list.item(i)
                    if item:
                        item.setSelected(True)
            else:
                policy_list.clearSelection()
        
        select_all_checkbox.stateChanged.connect(on_select_all_changed)
        
        if dialog.exec() == QDialog.Accepted:
            selected_format = format_combo.currentText()
            selected_indices = [policy_list.row(item) for item in policy_list.selectedItems()]
            
            if not selected_indices:
                QMessageBox.warning(self, "警告", "请至少选择一条政策")
                return
            
            # 获取选中的政策数据
            selected_policies = [self.current_data[i] for i in selected_indices]
            
            # 根据选择的格式设置文件过滤器
            if "分条导出" in selected_format:
                # 分条导出需要选择目录
                from PyQt5.QtWidgets import QFileDialog
                output_dir = QFileDialog.getExistingDirectory(self, "选择输出目录", "")
                if not output_dir:
                    return
                
                # 确定分条导出格式
                if "Word" in selected_format:
                    export_format = 'word'
                elif "文本" in selected_format:
                    export_format = 'txt'
                elif "Markdown" in selected_format:
                    export_format = 'markdown'
                else:
                    export_format = 'word'
                
                # 执行分条导出
                try:
                    from space_planning.utils.export import DataExporter
                    exporter = DataExporter()
                    result = exporter.export_individual_files(selected_policies, output_dir, export_format)
                    
                    if result.get('success'):
                        QMessageBox.information(self, "成功", 
                            f"分条导出成功！\n共导出{result['total_files']}个文件\n输出目录：{output_dir}")
                    else:
                        QMessageBox.critical(self, "错误", f"分条导出失败：{result.get('error', '未知错误')}")
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"分条导出失败：{str(e)}")
                return
            elif "RAG知识库" in selected_format:
                # RAG导出需要选择目录，不是单个文件
                self.export_rag_knowledge_base(selected_policies)
                return
            
            # 常规导出需要选择文件
            if "Word" in selected_format:
                file_filter = "Word文档 (*.docx)"
                default_ext = ".docx"
            elif "Excel" in selected_format:
                file_filter = "Excel表格 (*.xlsx)"
                default_ext = ".xlsx"
            elif "文本" in selected_format:
                file_filter = "文本文件 (*.txt)"
                default_ext = ".txt"
            elif "Markdown" in selected_format:
                file_filter = "Markdown文档 (*.md)"
                default_ext = ".md"
            else:
                file_filter = "所有文件 (*.*)"
                default_ext = ""
            
            file_path, _ = QFileDialog.getSaveFileName(self, "保存文件", f"政策数据{default_ext}", file_filter)
            
            if file_path:
                try:
                    from space_planning.utils.export import DataExporter
                    exporter = DataExporter()
                    
                    if "Word" in selected_format:
                        success = exporter.export_to_word(selected_policies, file_path)
                        if success:
                            QMessageBox.information(self, "成功", f"Word文档导出成功！共导出{len(selected_policies)}条政策")
                        else:
                            QMessageBox.critical(self, "错误", "Word文档导出失败")
                    elif "Excel" in selected_format:
                        success = exporter.export_to_excel(selected_policies, file_path)
                        if success:
                            QMessageBox.information(self, "成功", f"Excel表格导出成功！共导出{len(selected_policies)}条政策")
                        else:
                            QMessageBox.critical(self, "错误", "Excel表格导出失败，请确保已安装pandas和openpyxl库")
                    elif "文本" in selected_format:
                        success = exporter.export_to_txt(selected_policies, file_path)
                        if success:
                            QMessageBox.information(self, "成功", f"文本文件导出成功！共导出{len(selected_policies)}条政策")
                        else:
                            QMessageBox.critical(self, "错误", "文本文件导出失败")
                    elif "Markdown" in selected_format:
                        success = exporter.export_to_markdown(selected_policies, file_path)
                        if success:
                            QMessageBox.information(self, "成功", f"Markdown文档导出成功！共导出{len(selected_policies)}条政策")
                        else:
                            QMessageBox.critical(self, "错误", "Markdown文档导出失败")
                    else:
                        QMessageBox.warning(self, "警告", "不支持的导出格式")
                        
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def export_rag_knowledge_base(self, selected_policies):
        """导出RAG知识库格式"""
        try:
            from .rag_export_dialog import show_rag_export_dialog
            result = show_rag_export_dialog(self, selected_policies)
            
            if result == QDialog.Accepted:
                QMessageBox.information(
                    self, 
                    "RAG导出成功", 
                    f"✅ RAG知识库导出完成！\n\n"
                    f"📊 共处理 {len(selected_policies)} 条政策\n"
                    f"📁 请查看输出目录中的分段文件"
                )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"RAG导出失败: {str(e)}")

    def on_batch_update(self):
        """批量爬取数据（不依赖关键词）"""
        try:
            # 防止重复点击
            if hasattr(self, 'batch_thread') and self.batch_thread.isRunning():
                return
            
            self.batch_update_btn.setText("📥 爬取中...")
            self.batch_update_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.progress_label.setText("正在批量爬取数据...")
            QApplication.processEvents()
            
            # 获取时间区间参数
            start_date = self.start_date_edit.date().toString('yyyy-MM-dd')
            end_date = self.end_date_edit.date().toString('yyyy-MM-dd')
            
            # 创建并启动批量爬取线程
            self.current_data = [] # 清空当前数据
            self.refresh_table([]) # 清空表格
            # 使用第一个可用的机构进行批量爬取
            self.batch_thread = SearchThread("住房和城乡建设部", None, True, start_date, end_date, True, "正常速度", None, self)
            self.batch_thread.progress_signal.connect(self.update_progress)
            self.batch_thread.result_signal.connect(self.update_results)
            self.batch_thread.single_policy_signal.connect(self.on_new_policy) # 新增信号连接
            self.batch_thread.finished_signal.connect(self.batch_finished)
            self.batch_thread.error_signal.connect(self.batch_error)
            self.batch_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"批量爬取失败: {str(e)}")
            self.reset_batch_ui()
    
    def batch_finished(self):
        """批量爬取完成"""
        self.progress_label.setText("批量爬取完成")
        self.progress_bar.setVisible(False)
        self.batch_update_btn.setText("📥 批量爬取")
        self.batch_update_btn.setEnabled(True)
        
        QMessageBox.information(self, "批量爬取完成", 
            f"✅ 批量爬取完成！\n\n"
            f"📊 共获取 {len(self.current_data)} 条政策")
    
    def batch_error(self, error_msg):
        """批量爬取出错"""
        QMessageBox.critical(self, "错误", f"批量爬取失败: {error_msg}")
        self.reset_batch_ui()
    
    def reset_batch_ui(self):
        """重置批量爬取UI状态"""
        self.progress_label.setText("就绪")
        self.progress_bar.setVisible(False)
        self.batch_update_btn.setText("📥 批量爬取")
        self.batch_update_btn.setEnabled(True)



    def on_compare(self):
        """智能对比功能"""
        if not self.current_data:
            QMessageBox.warning(self, "警告", "没有数据可对比")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("智能对比分析")
        dialog.resize(800, 600)
        dialog.setModal(True)
        
        layout = QVBoxLayout()
        
        # 选择要对比的政策
        layout.addWidget(QLabel("选择要对比的政策："))
        
        # 创建政策选择列表
        policy_list = QListWidget()
        for i, policy in enumerate(self.current_data):
            # 解析政策数据格式
            if isinstance(policy, (list, tuple)):
                title = str(policy[2]) if len(policy) > 2 else "未知标题"
                level = str(policy[1]) if len(policy) > 1 else "未知机构"
            elif isinstance(policy, dict):
                title = str(policy.get('title', '未知标题'))
                level = str(policy.get('level', '未知机构'))
            else:
                title = "未知标题"
                level = "未知机构"
            policy_list.addItem(f"{i+1}. {title} ({level})")
        layout.addWidget(policy_list)
        
        # 对比结果显示
        result_text = QTextEdit()
        result_text.setReadOnly(True)
        layout.addWidget(QLabel("对比结果："))
        layout.addWidget(result_text)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        # 当选择政策时进行分析
        def analyze_selected():
            selected_items = policy_list.selectedItems()
            if len(selected_items) >= 2:
                # 获取选中的政策
                selected_policies = []
                for item in selected_items:
                    index = policy_list.row(item)
                    if index < len(self.current_data):
                        selected_policies.append(self.current_data[index])
                
                # 进行对比分析
                if selected_policies:
                    analysis_result = self.analyze_policies(selected_policies)
                    result_text.setText(analysis_result)
        
        policy_list.itemSelectionChanged.connect(analyze_selected)
        
        dialog.exec()
    
    def analyze_policies(self, policies):
        """分析政策对比结果"""
        if len(policies) < 2:
            return "请至少选择两个政策进行对比"
        
        result = "=== 政策对比分析结果 ===\n\n"
        
        # 关键词分析
        result += "1. 关键词分析：\n"
        for i, policy in enumerate(policies):
            # 解析政策数据格式
            if isinstance(policy, (list, tuple)):
                content = str(policy[5]) if len(policy) > 5 else ""
                level = str(policy[1]) if len(policy) > 1 else ""
            elif isinstance(policy, dict):
                content = str(policy.get('content', ''))
                level = str(policy.get('level', ''))
            else:
                content = level = ""
            
            keywords = self.comparer.find_keywords(content)
            result += f"   政策{i+1}（{level}）：{', '.join(keywords) if keywords else '无关键词'}\n"
        
        result += "\n2. 相似度分析：\n"
        # 两两对比
        for i in range(len(policies)):
            for j in range(i+1, len(policies)):
                similarity = self.comparer.compare_texts(policies[i][5], policies[j][5])
                result += f"   政策{i+1} vs 政策{j+1}：\n"
                result += f"      - 整体相似度：{similarity['average']:.2f}%\n"
                result += f"      - 部分相似度：{similarity['partial_ratio']:.2f}%\n"
                result += f"      - 词汇排序相似度：{similarity['token_sort_ratio']:.2f}%\n"
                result += f"      - 词汇集合相似度：{similarity['token_set_ratio']:.2f}%\n\n"
        
        result += "3. 建议：\n"
        # 根据相似度给出建议
        for i in range(len(policies)):
            for j in range(i+1, len(policies)):
                similarity = self.comparer.compare_texts(policies[i][5], policies[j][5])
                if similarity['average'] > 80:
                    result += f"   - 政策{i+1}与政策{j+1}高度相似，建议重点关注差异部分\n"
                elif similarity['average'] > 50:
                    result += f"   - 政策{i+1}与政策{j+1}有一定相似性，可参考借鉴\n"
                else:
                    result += f"   - 政策{i+1}与政策{j+1}差异较大，需要分别分析\n"
        
        return result

    def on_compliance_analysis(self):
        """合规性分析"""
        if not self.current_data:
            QMessageBox.warning(self, "警告", "没有数据可分析")
            return
        
        # 获取项目关键词
        text = self.keyword_edit.text().strip()
        project_keywords = text.split() if text else []
        if not project_keywords:
            QMessageBox.information(self, "提示", "请先输入项目关键词，然后进行合规性分析")
            return
        
        # 创建分析结果对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("合规性分析报告")
        dialog.resize(1000, 700)
        dialog.setModal(True)
        
        layout = QVBoxLayout()
        
        # 分析结果文本
        result_text = QTextEdit()
        result_text.setReadOnly(True)
        layout.addWidget(result_text)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        # 执行分析
        analysis_result = self.perform_compliance_analysis(project_keywords)
        result_text.setText(analysis_result)
        
        dialog.exec()

    def perform_compliance_analysis(self, project_keywords):
        """执行合规性分析"""
        result = "=== 空间规划政策合规性分析报告 ===\n\n"
        result += f"分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        result += f"项目关键词：{', '.join(project_keywords)}\n"
        result += f"分析政策数量：{len(self.current_data)} 条\n\n"
        
        # 政策分类统计
        type_stats = {}
        high_impact_policies = []
        risks = []
        suggestions = []
        
        for i, policy in enumerate(self.current_data):
            # 解析政策数据格式
            if isinstance(policy, (list, tuple)):
                content = str(policy[5]) if len(policy) > 5 else ""
                title = str(policy[2]) if len(policy) > 2 else ""
                pub_date = str(policy[3]) if len(policy) > 3 else ""
            elif isinstance(policy, dict):
                content = str(policy.get('content', ''))
                title = str(policy.get('title', ''))
                pub_date = str(policy.get('pub_date', ''))
            else:
                content = title = pub_date = ""
            
            # 政策分类
            policy_types = self.compliance_analyzer.classify_policy(title, content)
            for policy_type in policy_types:
                type_stats[policy_type] = type_stats.get(policy_type, 0) + 1
            
            # 合规性分析
            compliance = self.compliance_analyzer.analyze_compliance(content, project_keywords)
            
            if compliance['score'] > 50:
                high_impact_policies.append({
                    'title': title,
                    'pub_date': pub_date,
                    'score': compliance['score'],
                    'impact': compliance['impact'],
                    'risks': compliance['risks'],
                    'suggestions': compliance['suggestions']
                })
            
            risks.extend(compliance['risks'])
            suggestions.extend(compliance['suggestions'])
        
        # 1. 政策类型分布
        result += "1. 政策类型分布：\n"
        for policy_type, count in sorted(type_stats.items(), key=lambda x: x[1], reverse=True):
            result += f"   {policy_type}：{count} 条\n"
        
        # 2. 高影响政策
        result += f"\n2. 高影响政策（{len(high_impact_policies)} 条）：\n"
        for policy in high_impact_policies:
            result += f"   📋 {policy['title']}\n"
            result += f"      发布日期：{policy['pub_date']}\n"
            result += f"      影响度：{policy['impact']}（评分：{policy['score']}）\n"
            if policy['risks']:
                result += f"      风险提示：{', '.join(policy['risks'])}\n"
            if policy['suggestions']:
                result += f"      建议：{', '.join(policy['suggestions'])}\n"
            result += "\n"
        
        # 3. 总体风险提示
        if risks:
            result += "3. 总体风险提示：\n"
            unique_risks = list(set(risks))
            for risk in unique_risks:
                result += f"   ⚠️ {risk}\n"
        
        # 4. 合规建议
        if suggestions:
            result += "\n4. 合规建议：\n"
            unique_suggestions = list(set(suggestions))
            for suggestion in unique_suggestions:
                result += f"   💡 {suggestion}\n"
        
        # 5. 合规性评分
        if high_impact_policies:
            avg_score = sum(p['score'] for p in high_impact_policies) / len(high_impact_policies)
            result += f"\n5. 项目合规性评分：{avg_score:.1f}/100\n"
            if avg_score >= 80:
                result += "   合规性评级：优秀 ✅\n"
            elif avg_score >= 60:
                result += "   合规性评级：良好 ⚠️\n"
            else:
                result += "   合规性评级：需要关注 ❌\n"
        
        return result

    def copy_full_text(self):
        """复制全文内容到剪贴板"""
        text = self.full_text.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(text)
                QMessageBox.information(self, "复制成功", f"政策全文已复制到剪贴板：\n{text}")
            else:
                QMessageBox.warning(self, "错误", "无法访问系统剪贴板")
        else:
            QMessageBox.warning(self, "提示", "没有可复制的内容")
    
    def show_context_menu(self, position):
        """显示表格右键菜单"""
        try:
            # 获取点击的行
            row = self.table.rowAt(position.y())
            if row < 0 or row >= len(self.current_data):
                return
            
            # 创建右键菜单
            menu = QMenu(self)
            
            # 获取当前行数据
            item = self.current_data[row]
            if isinstance(item, (list, tuple)):
                title = str(item[2]) if len(item) > 2 else ""
                source = str(item[4]) if len(item) > 4 else ""
                content = str(item[5]) if len(item) > 5 else ""
            elif isinstance(item, dict):
                title = str(item.get('title', ''))
                source = str(item.get('source', ''))
                content = str(item.get('content', ''))
            else:
                title = source = content = ""
            
            # 添加菜单项
            copy_title_action = menu.addAction("📋 复制标题")
            copy_source_action = menu.addAction("🔗 复制来源")
            copy_content_action = menu.addAction("📄 复制全文")
            menu.addSeparator()
            view_full_text_action = menu.addAction("👁️ 查看全文")
            
            # 显示菜单并获取用户选择
            action = menu.exec_(self.table.mapToGlobal(position))
            
            if action == copy_title_action:
                clipboard = QApplication.clipboard()
                if clipboard is not None:
                    clipboard.setText(title)
                    QMessageBox.information(self, "复制成功", f"政策标题已复制到剪贴板")
            
            elif action == copy_source_action:
                clipboard = QApplication.clipboard()
                if clipboard is not None:
                    clipboard.setText(source)
                    QMessageBox.information(self, "复制成功", f"政策来源已复制到剪贴板")
            
            elif action == copy_content_action:
                clipboard = QApplication.clipboard()
                if clipboard is not None:
                    clipboard.setText(content)
                    QMessageBox.information(self, "复制成功", f"政策全文已复制到剪贴板")
            
            elif action == view_full_text_action:
                self._show_full_text(title, content)
                
        except Exception as e:
            QMessageBox.warning(self, "错误", f"显示右键菜单失败: {str(e)}")
    
    def on_table_click(self, row, col):
        """处理表格点击事件"""
        if row >= len(self.current_data):
            return
            
        # 获取当前行的数据
        item = self.current_data[row]
        
        # 解析数据格式
        if isinstance(item, (list, tuple)):
            source = str(item[4]) if len(item) > 4 else ""
            content = str(item[5]) if len(item) > 5 else ""
            title = str(item[2]) if len(item) > 2 else ""
        elif isinstance(item, dict):
            source = str(item.get('source', ''))
            content = str(item.get('content', ''))
            title = str(item.get('title', ''))
        else:
            source = content = title = ""
            
        if col == 3:  # 点击来源列
            # 实际复制到剪贴板
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(source)
                QMessageBox.information(self, "复制成功", f"政策来源已复制到剪贴板：\n{source}")
            else:
                QMessageBox.warning(self, "错误", "无法访问系统剪贴板")
        elif col == 5:  # 点击"查看全文"列
            if content and content.strip() and content.strip() != "点击查看":
                self._show_full_text(title, content)
            else:
                # 动态抓取正文
                self._show_full_text(title, "正在获取政策正文，请稍候...")
                def fetch_content(item=item, row=row):
                    try:
                        # 根据政策来源判断使用哪个爬虫
                        if 'mnr.gov.cn' in source:
                            from space_planning.spider.mnr import MNRSpider
                            spider = MNRSpider()
                        elif 'gd.gov.cn' in source:
                            from space_planning.spider.guangdong import GuangdongSpider
                            spider = GuangdongSpider()
                        else:
                            from space_planning.spider.national import NationalSpider
                            spider = NationalSpider()
                        
                        detail = spider.get_policy_detail(source)
                        if not detail:
                            detail = "未获取到政策正文"
                    except Exception as e:
                        detail = f"获取政策正文失败: {e}"
                    def update():
                        self._show_full_text(title, detail)
                        # 更新内存中的数据，避免重复抓取
                        if isinstance(item, dict):
                            item['content'] = detail
                        elif isinstance(item, (list, tuple)) and len(item) > 5:
                            item2 = list(item)
                            item2[5] = detail
                            self.current_data[row] = tuple(item2)
                    QTimer.singleShot(0, update)
                threading.Thread(target=fetch_content, daemon=True).start()

    def _show_full_text(self, title, content):
        """显示政策全文到右侧全文区"""
        if self.full_text is not None:
            cleaned_content = content.strip()
            import re
            cleaned_content = re.sub(r'\n\s*\n', '\n\n', cleaned_content)
            if '\n' not in cleaned_content:
                cleaned_content = re.sub(r'([。！？；])', r'\1\n', cleaned_content)
            self.full_text.setPlainText(cleaned_content)
            self.full_text.updateGeometry()
            cursor = self.full_text.textCursor()
            cursor.movePosition(cursor.Start)
            self.full_text.setTextCursor(cursor)
            self.full_text.ensureCursorVisible()
            self.full_text.repaint()
            QApplication.processEvents()
        if self.full_text_title is not None:
            self.full_text_title.setText(f"正在查看：{title}")
        if self.full_text is not None:
            self.full_text.setFocus()
    
    def show_crawler_status(self):
        """显示爬虫状态"""
        if hasattr(self, 'crawler_status_dialog'):
            self.crawler_status_dialog.close()
        
        # 智能获取当前爬虫实例
        crawler = None
        try:
            # 首先检查搜索线程中的爬虫
            if hasattr(self, 'search_thread') and self.search_thread.isRunning():
                crawler = getattr(self.search_thread, 'spider', None)
                logger.debug(f"从搜索线程获取爬虫: {type(crawler).__name__ if crawler else 'None'}")
            
            # 如果没有找到爬虫，根据当前选择的机构和模式确定爬虫
            if crawler is None:
                current_level = self.level_combo.currentText()
                use_multithread = self.multithread_checkbox.isChecked()
                
                logger.debug(f"当前机构: {current_level}, 多线程模式: {use_multithread}")
                
                if current_level == "自然资源部":
                    if use_multithread:
                        crawler = self.mnr_multithread_spider
                        logger.debug("使用自然资源部多线程爬虫")
                    else:
                        crawler = self.mnr_spider
                        logger.debug("使用自然资源部单线程爬虫")
                elif current_level == "广东省人民政府":
                    if use_multithread:
                        crawler = self.guangdong_multithread_spider
                        logger.debug("使用广东省多线程爬虫")
                    else:
                        crawler = self.guangdong_spider
                        logger.debug("使用广东省单线程爬虫")
                elif current_level == "住房和城乡建设部":
                    if use_multithread:
                        crawler = self.national_multithread_spider
                        logger.debug("使用国家级多线程爬虫")
                    else:
                        crawler = self.national_spider
                        logger.debug("使用国家级单线程爬虫")
                else:
                    # 默认使用国家级爬虫
                    crawler = self.national_spider
                    logger.debug("使用默认国家级爬虫")
            
            # 如果还是没有爬虫，创建一个默认的
            if crawler is None:
                from space_planning.spider.national import NationalSpider
                crawler = NationalSpider()
                logger.debug("创建默认爬虫实例")
                
        except Exception as e:
            logger.error(f"获取爬虫实例失败: {e}", exc_info=True)
            # 创建一个默认爬虫
            from space_planning.spider.national import NationalSpider
            crawler = NationalSpider()
        
        logger.debug(f"最终使用的爬虫类型: {type(crawler).__name__}")
        
        try:
            self.crawler_status_dialog = CrawlerStatusDialog(crawler, self)
            self.crawler_status_dialog.show()
        except Exception as e:
            logger.error(f"创建爬虫状态对话框失败: {e}", exc_info=True)
            QMessageBox.warning(self, "错误", f"无法打开爬虫状态对话框：{str(e)[:100]}")
    
    def show_database_manager(self):
        """显示数据库管理对话框"""
        try:
            from .database_manager_dialog import DatabaseManagerDialog
            dialog = DatabaseManagerDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打开数据库管理失败: {str(e)}")
    
    # 清理数据库功能已迁移到数据库管理对话框中
    
    def show_crawler_settings(self):
        """显示爬虫设置对话框"""
        try:
            from .crawler_settings_dialog import CrawlerSettingsDialog
            dialog = CrawlerSettingsDialog(self)
            dialog.settings_changed.connect(self.on_settings_changed)
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开爬虫设置对话框：{e}")
    
    def show_proxy_settings(self):
        """显示代理设置对话框"""
        try:
            from .proxy_settings_dialog import ProxySettingsDialog
            dialog = ProxySettingsDialog(self)
            if dialog.exec() == QDialog.Accepted:
                # 代理设置已在对话框中更新并初始化
                QMessageBox.information(self, "成功", "代理设置已更新")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打开代理设置对话框失败: {e}")
    
    def on_settings_changed(self):
        """设置改变事件"""
        QMessageBox.information(self, "设置已更新", "爬虫设置已保存，新的设置将在下次爬取时生效。")
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于", 
            "空间规划政策合规性分析系统\n\n"
            "版本: 3.0.1\n"
            "更新时间: 2025.10.29\n"
            "功能: 智能爬取、合规分析、数据导出\n"
            "技术: Python + PyQt5 + SQLite\n\n"
            "开发者: ViVi141\n"
            "联系邮箱: 747384120@qq.com\n\n"
            "本次更新:\n"
            "• 修复模块导入路径问题，确保程序能正确启动\n"
            "• 修复数据库连接泄漏问题，提升稳定性\n"
            "• 修复线程锁泄漏问题，改进异常处理\n"
            "• 修复全局变量线程安全问题\n"
            "• 优化代码质量和性能\n"
            "• 清理临时文件，保持项目整洁\n\n"
            "防反爬虫功能已启用，包含:\n"
            "• 随机User-Agent轮换\n"
            "• 请求频率限制\n"
            "• 智能延迟控制\n"
            "• 错误监控与重试\n"
            "• 会话轮换机制\n"
            "• SSL证书安全验证")
    

    
    def export_data(self):
        """导出数据（菜单项）"""
        self.on_export()
    
    def show_proxy_diagnostic(self):
        """显示代理诊断"""
        try:
            import sys
            import os
            # 添加utils目录到路径
            utils_path = os.path.join(os.path.dirname(__file__), '..', 'utils')
            if utils_path not in sys.path:
                sys.path.insert(0, utils_path)
            
            # 动态导入代理诊断模块
            import importlib.util
            diagnostic_path = os.path.join(utils_path, "proxy_diagnostic.py")
            spec = importlib.util.spec_from_file_location("proxy_diagnostic", diagnostic_path)
            if spec and spec.loader:
                proxy_diagnostic = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(proxy_diagnostic)
                run_diagnostic = proxy_diagnostic.run_diagnostic
            else:
                raise ImportError(f"无法加载代理诊断模块: {diagnostic_path}")
            
            # 创建诊断结果对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("代理诊断结果")
            dialog.setModal(True)
            dialog.resize(500, 400)
            
            layout = QVBoxLayout()
            
            # 添加文本显示
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            
            # 捕获诊断输出
            import io
            import sys
            old_stdout = sys.stdout
            new_stdout = io.StringIO()
            sys.stdout = new_stdout
            
            try:
                run_diagnostic()
                output = new_stdout.getvalue()
            finally:
                sys.stdout = old_stdout
            
            text_edit.setPlainText(output)
            layout.addWidget(text_edit)
            
            # 添加关闭按钮
            close_btn = QPushButton("关闭")
            def close_dialog():
                dialog.close()
            close_btn.clicked.connect(close_dialog)
            layout.addWidget(close_btn)
            
            dialog.setLayout(layout)
            dialog.show()
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"代理诊断失败: {str(e)}")
    
    def _update_ui_periodically(self):
        """定期更新UI，减少频繁刷新"""
        # 使用定时器来批量更新UI，而不是每次都立即刷新
        if not hasattr(self, '_ui_update_timer'):
            self._ui_update_timer = QTimer()
            self._ui_update_timer.timeout.connect(self._force_ui_update)
            self._ui_update_timer.setSingleShot(True)
        
        # 如果定时器还没开始，启动它
        if not self._ui_update_timer.isActive():
            self._ui_update_timer.start(100)  # 100ms后更新UI
    
    def _force_ui_update(self):
        """强制更新UI"""
        QApplication.processEvents()
    
    def clear_proxy_manually(self):
        """手动清空代理"""
        try:
            from space_planning.spider.persistent_proxy_manager import persistent_proxy_manager
            
            # 确认对话框
            reply = QMessageBox.question(
                self, 
                "确认清空代理", 
                "确定要清空当前代理吗？\n\n这将清除当前使用的代理，下次爬取时会重新获取新代理。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 清空代理
                persistent_proxy_manager.clear_proxy()
                
                # 显示成功消息
                QMessageBox.information(
                    self, 
                    "清空成功", 
                    "代理已清空！\n\n下次爬取时会自动获取新的代理。"
                )
                
                logger.info("用户手动清空代理")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"清空代理失败: {str(e)}")
            logger.error(f"手动清空代理失败: {e}", exc_info=True)

def main():
    """主程序入口函数"""
    from space_planning.core.logger_config import get_logger
    logger = get_logger(__name__)
    
    try:
        logger.info("正在初始化数据库...")
        db.init_db()  # 初始化数据库
        logger.info("数据库初始化完成")
        
        logger.info("正在启动应用程序...")
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        logger.info("应用程序启动成功")
        
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"程序启动失败: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 