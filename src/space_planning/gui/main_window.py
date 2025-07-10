from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QTextEdit, QFileDialog, QMessageBox, QSpinBox, QDialog, QDialogButtonBox, QListWidget, QRadioButton, QProgressBar, QDateEdit, QGroupBox, QCheckBox, QHeaderView, QMenu)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate, QTimer
from PyQt5.QtGui import QColor
import sys
import os
import threading
from datetime import datetime, timedelta
import re
import urllib3
import warnings

# 启用SSL安全验证
# 移除SSL警告禁用，确保安全连接

from space_planning.core import database as db
from space_planning.spider.national import NationalSpider
from space_planning.utils.export import export_to_word
from space_planning.utils.compare import PolicyComparer
from space_planning.utils.compliance import ComplianceAnalyzer



class SearchThread(QThread):
    """搜索线程，避免界面卡死"""
    progress_signal = pyqtSignal(str)  # 进度信号
    result_signal = pyqtSignal(list)   # 初始数据库结果
    single_policy_signal = pyqtSignal(object)  # 新增单条政策
    finished_signal = pyqtSignal()     # 完成信号
    error_signal = pyqtSignal(str)     # 错误信号
    data_count_signal = pyqtSignal(int)  # 数据量信号
    
    def __init__(self, level, keywords, need_crawl=True, start_date=None, end_date=None, enable_anti_crawler=True, speed_mode="正常速度", spider=None, main_window=None):
        super().__init__()
        self.level = level
        self.keywords = keywords
        self.need_crawl = need_crawl
        self.start_date = start_date
        self.end_date = end_date
        self.enable_anti_crawler = enable_anti_crawler
        self.speed_mode = speed_mode
        self.spider = spider  # 使用传入的spider实例
        self.main_window = main_window  # 保存主窗口引用，用于访问持久爬虫实例
        self.stop_flag = False  # 停止标志
    
    def run(self):
        try:
            # 第一步：查询数据库现有数据
            self.progress_signal.emit("正在查询数据库...")
            db_results = db.search_policies(self.level, self.keywords, self.start_date, self.end_date)
            self.progress_signal.emit(f"数据库中找到 {len(db_results)} 条相关数据")
            
            # 实时显示数据库结果
            self.result_signal.emit(db_results)
            
            if self.need_crawl and not self.stop_flag:
                self.progress_signal.emit("正在爬取最新数据...")
                # 根据选择的机构使用对应的持久爬虫实例
                if self.main_window:
                    if self.level == "住房和城乡建设部":
                        spider = self.main_window.national_spider
                    elif self.level == "广东省人民政府":
                        spider = self.main_window.guangdong_spider
                    elif self.level == "自然资源部":
                        spider = self.main_window.mnr_spider
                    else:
                        # 其他机构暂时使用国家级爬虫
                        spider = self.main_window.national_spider
                    
                    # 更新当前使用的爬虫实例
                    self.spider = spider
                
                if spider:
                    # 根据速度模式和防反爬虫设置调整爬虫行为
                    if self.speed_mode == "快速模式":
                        # 快速模式：优先速度，禁用大部分限制
                        self.progress_signal.emit("🚀 快速模式：已禁用防反爬虫限制，优先速度")
                        disable_speed_limit = True
                    elif self.speed_mode == "慢速模式":
                        # 慢速模式：优先安全，启用所有防反爬虫措施
                        self.progress_signal.emit("🐌 慢速模式：已启用完整防反爬虫措施，优先安全")
                        disable_speed_limit = False
                    else:  # 正常速度
                        # 正常模式：根据用户设置决定
                        if not self.enable_anti_crawler:
                            self.progress_signal.emit("⚡ 正常速度：已禁用速度限制")
                            disable_speed_limit = True
                        else:
                            self.progress_signal.emit("🛡️ 正常速度：已启用防反爬虫措施")
                            disable_speed_limit = False
                    
                    # 自定义回调函数，实时更新进度和发送数据
                    def progress_callback(message):
                        if message.startswith("POLICY_DATA:"):
                            # 解析政策数据
                            data_parts = message[12:].split("|")
                            if len(data_parts) >= 4:
                                policy = {
                                    'level': self.level,  # 使用当前选择的机构级别
                                    'title': data_parts[0],
                                    'pub_date': data_parts[1],
                                    'source': data_parts[2],
                                    'content': data_parts[3],
                                    'category': data_parts[4] if len(data_parts) > 4 else None,  # 添加分类字段
                                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                # 立即发送到界面
                                self.single_policy_signal.emit(policy)
                        else:
                            self.progress_signal.emit(f"爬取进度: {message}")
                    
                    # 调用爬虫方法
                    if self.level == "广东省人民政府":
                        # 广东省爬虫使用快速方法（跳过分类遍历，大幅提升速度）
                        new_policies = getattr(spider, 'crawl_policies_fast', 
                                              getattr(spider, 'crawl_policies_optimized', spider.crawl_policies))(
                            keywords=self.keywords,
                            callback=progress_callback,
                            start_date=self.start_date,
                            end_date=self.end_date,
                            speed_mode=self.speed_mode,
                            disable_speed_limit=disable_speed_limit,
                            stop_callback=lambda: self.stop_flag
                        )
                    else:
                        # 其他爬虫使用标准方法
                        new_policies = spider.crawl_policies(
                            keywords=self.keywords,
                            callback=progress_callback,
                            start_date=self.start_date,
                            end_date=self.end_date,
                            speed_mode=self.speed_mode,
                            disable_speed_limit=disable_speed_limit,
                            stop_callback=lambda: self.stop_flag
                        )
                else:
                    new_policies = []
                
                # 注意：实时保存和显示数据已经在爬取过程中通过single_policy_signal完成
                # 这里不需要再次保存，避免重复保存
                if not self.stop_flag:
                    self.progress_signal.emit(f"爬取完成，共获取 {len(new_policies)} 条新数据")
                else:
                    self.progress_signal.emit("搜索已停止")
                    # 停止后也要显示已爬取的数据
                    if new_policies:
                        self.progress_signal.emit(f"已停止，共获取 {len(new_policies)} 条数据")
            else:
                self.progress_signal.emit("数据库数据充足，无需爬取新数据")
            
            # 最终查询结果 - 重新查询数据库以获取所有数据（包括新爬取的）
            final_results = db.search_policies(self.level, self.keywords, self.start_date, self.end_date)
            self.result_signal.emit(final_results)
            
            # 发送数据量信号
            self.data_count_signal.emit(len(final_results))
            
            self.finished_signal.emit()
            
        except Exception as e:
            self.error_signal.emit(str(e))
    
    def stop(self):
        """停止搜索"""
        self.stop_flag = True

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.max_display_rows = 100  # 最大显示100行
        self.page_size = 50  # 每页50行
        self.current_page = 0  # 当前页码
        self.setWindowTitle("空间规划政策合规性分析系统 v2.2.0 - ViVi141")
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), "../../../docs/icon.ico")
        if os.path.exists(icon_path):
            from PyQt5.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        
        self.resize(1400, 900)
        
        # 创建共享的爬虫实例
        from space_planning.spider.national import NationalSpider
        from space_planning.spider.guangdong import GuangdongSpider
        from space_planning.spider.mnr import MNRSpider
        
        # 为每个机构创建持久的爬虫实例，保持监控数据
        self.national_spider = NationalSpider()
        self.guangdong_spider = GuangdongSpider()
        self.mnr_spider = MNRSpider()
        
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
            print(f"动态加载的爬虫机构: {spider_levels}")
        except Exception as e:
            print(f"动态加载爬虫机构失败: {e}")
            # 降级方案：只显示已实现的爬虫
            self.level_combo.addItems(["住房和城乡建设部", "广东省人民政府", "自然资源部"])
        
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
        
        row3_layout.addStretch()
        row3_layout.addWidget(self.anti_crawler_checkbox)
        row3_layout.addWidget(QLabel("查询速度："))
        row3_layout.addWidget(self.speed_combo)
        
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
        
        # 自动调整列宽
        header = self.table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 机构
            header.setSectionResizeMode(1, QHeaderView.Stretch)  # 标题自适应
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 发布日期
            header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 来源
            header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 政策类型
            header.setSectionResizeMode(5, QHeaderView.Fixed)  # 操作列固定宽度
        self.table.setColumnWidth(5, 100)
        
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
            
            # 创建并启动搜索线程
            self.current_data = [] # 清空当前数据
            self.refresh_table([]) # 清空表格
            # 传递None给SearchThread，让它根据level动态创建爬虫
            self.search_thread = SearchThread(level, keywords, need_crawl, start_date, end_date, enable_anti_crawler, speed_mode, None, self)
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
        print(message)
        
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
            print(f"检测到实时爬取数据，当前数据量: {len(self.current_data)}, 查询结果: {len(results)}")
            print("保留实时爬取的数据，不覆盖")
            # 保留实时爬取的数据，不覆盖
            return
        
        # 如果是初始查询（没有实时数据），则正常更新
        if len(self.current_data) == 0:
            print(f"初始查询结果: {len(results)} 条")
        else:
            print(f"更新查询结果: 当前 {len(self.current_data)} 条 -> 新结果 {len(results)} 条")
        
        # 限制最大显示数量，避免内存占用过高
        max_display = 1000
        if len(results) > max_display:
            self.current_data = list(results[:max_display])
            QMessageBox.information(self, "提示", f"结果较多，仅显示前{max_display}条数据")
        else:
            self.current_data = list(results)
        
        self.refresh_table(self.current_data) # 刷新表格
        QApplication.processEvents()
    
    def on_new_policy(self, policy):
        """新增政策信号处理"""
        try:
            # 立即保存到数据库
            db.insert_policy(
                policy['level'], 
                policy['title'], 
                policy['pub_date'], 
                policy['source'], 
                policy['content'], 
                policy['crawl_time'],
                policy.get('category')  # 添加分类信息
            )
            
            # policy为dict，需转为tuple与表格结构一致
            # 注意：数据库返回的字段顺序是 (id, level, title, pub_date, source, content, category)
            row = (None, policy['level'], policy['title'], policy['pub_date'], policy['source'], policy['content'], policy.get('category', ''))
            self.current_data.append(row)
            
            # 实时显示：每一条都立即显示
            self._add_single_row(row)
            
            # 更新统计信息
            if self.stats_label is not None:
                self.stats_label.setText(f"共找到 {len(self.current_data)} 条政策")
            
            # 强制刷新界面
            QApplication.processEvents()
            
        except Exception as e:
            print(f"保存新政策失败: {e}")
            # 即使保存失败，也要显示在界面上
            try:
                row = (None, policy['level'], policy['title'], policy['pub_date'], policy['source'], policy['content'], policy.get('category', ''))
                self.current_data.append(row)
                self._add_single_row(row)
                
                if self.stats_label is not None:
                    self.stats_label.setText(f"共找到 {len(self.current_data)} 条政策")
                
                QApplication.processEvents()
            except Exception as e2:
                print(f"显示新政策失败: {e2}")

    def on_data_count_update(self, count):
        """接收数据量更新信号"""
        print(f"收到数据量更新信号: {count}")
        # 如果当前数据量小于接收到的数量，说明有新的数据
        if len(self.current_data) < count:
            print(f"数据量不匹配，当前: {len(self.current_data)}, 接收: {count}")
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
        self.page_info_label.setText(f"第 {self.current_page + 1}/{total_pages} 页 (显示第 {start_idx + 1}-{end_idx} 条，共 {len(data)} 条)")
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
        """添加单行数据（优化性能）"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._set_table_row(row, item)
        
        # 自动滚动到最新行
        if self.auto_scroll_checkbox.isChecked():
            self.table.scrollToBottom()
            # 选中最新行
            self.table.selectRow(row)
    
    def _set_table_row(self, row, item):
        """设置表格行数据"""
        # 设置各列数据 - 数据库字段顺序：(id, level, title, pub_date, source, content)
        
        # 检查item是元组还是字典
        if isinstance(item, (list, tuple)):
            # 元组/列表格式 (id, level, title, pub_date, source, content)
            level = str(item[1]) if len(item) > 1 else ""
            title = str(item[2]) if len(item) > 2 else ""
            pub_date = str(item[3]) if len(item) > 3 else ""
            source = str(item[4]) if len(item) > 4 else ""
            content = str(item[5]) if len(item) > 5 else ""
            category = str(item[6]) if len(item) > 6 else ""
        elif isinstance(item, dict):
            # 字典格式
            level = str(item.get('level', ''))
            title = str(item.get('title', ''))
            pub_date = str(item.get('pub_date', ''))
            source = str(item.get('source', ''))
            content = str(item.get('content', ''))
            category = str(item.get('category', ''))
        else:
            # 未知格式，使用默认值
            level = title = pub_date = source = content = category = ""
        
        # 机构列
        level_item = QTableWidgetItem(level)
        level_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 0, level_item)
        
        # 标题列 - 支持换行
        title_item = QTableWidgetItem(title)
        title_item.setToolTip(title)  # 鼠标悬停显示完整标题
        self.table.setItem(row, 1, title_item)
        
        # 发布日期列
        date_item = QTableWidgetItem(pub_date)
        date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 2, date_item)
        
        # 来源列 - 超链接样式
        source_item = QTableWidgetItem(source)
        source_item.setForeground(QColor(0, 102, 204))  # 蓝色链接样式
        source_item.setToolTip(f"点击查看来源：{source}")
        self.table.setItem(row, 3, source_item)
        
        # 政策类型列
        if level == '广东省人民政府':
            # 广东省政策显示分类信息
            if category and category.strip():
                type_item = QTableWidgetItem(category)
            else:
                # 如果分类为空，使用智能分类
                policy_types = self.compliance_analyzer.classify_policy(title, content)
                type_item = QTableWidgetItem(", ".join(policy_types))
        else:
            # 其他政策使用智能分类
            policy_types = self.compliance_analyzer.classify_policy(title, content)
            type_item = QTableWidgetItem(", ".join(policy_types))
        
        type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 4, type_item)
        
        # 操作列 - 按钮样式
        action_item = QTableWidgetItem("📄 查看全文")
        action_item.setForeground(QColor(0, 128, 0))  # 绿色按钮样式
        action_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        action_item.setToolTip("点击查看政策全文")
        self.table.setItem(row, 5, action_item)

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
            "Markdown文档 (*.md)"
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
        
        if dialog.exec_() == QDialog.Accepted:
            selected_format = format_combo.currentText()
            selected_indices = [policy_list.row(item) for item in policy_list.selectedItems()]
            
            if not selected_indices:
                QMessageBox.warning(self, "警告", "请至少选择一条政策")
                return
            
            # 获取选中的政策数据
            selected_policies = [self.current_data[i] for i in selected_indices]
            
            # 根据选择的格式设置文件过滤器
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
        
        dialog.exec_()
    
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
        project_keywords = self.keyword_edit.text().strip().split() if self.keyword_edit.text().strip() else []
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
        
        dialog.exec_()

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
        """显示爬虫状态实时监控"""
        try:
            from space_planning.gui.crawler_status_dialog import CrawlerStatusDialog
            # 传递所有爬虫实例到监控对话框
            dialog = CrawlerStatusDialog(self, {
                'national_spider': self.national_spider,
                'guangdong_spider': self.guangdong_spider,
                'mnr_spider': self.mnr_spider
            })
            dialog.show()  # 使用show()而不是exec_()，保持非模态
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打开爬虫状态监控失败: {str(e)}")
    
    def show_database_manager(self):
        """显示数据库管理对话框"""
        try:
            from .database_manager_dialog import DatabaseManagerDialog
            dialog = DatabaseManagerDialog(self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打开数据库管理失败: {str(e)}")
    
    # 清理数据库功能已迁移到数据库管理对话框中
    
    def show_crawler_settings(self):
        """显示爬虫设置对话框"""
        try:
            from .crawler_settings_dialog import CrawlerSettingsDialog
            dialog = CrawlerSettingsDialog(self)
            dialog.settings_changed.connect(self.on_settings_changed)
            dialog.exec_()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开爬虫设置对话框：{e}")
    
    def on_settings_changed(self):
        """设置改变事件"""
        QMessageBox.information(self, "设置已更新", "爬虫设置已保存，新的设置将在下次爬取时生效。")
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于", 
            "空间规划政策合规性分析系统\n\n"
            "版本: 2.2.0\n"
            "更新时间: 2025.7.10\n"
            "功能: 智能爬取、合规分析、数据导出\n"
            "技术: Python + PyQt5 + SQLite\n\n"
            "开发者: ViVi141\n"
            "联系邮箱: 747384120@qq.com\n\n"
            "本次更新:\n"
            "• 修复广东省爬虫分类显示问题\n"
            "• 优化政策类型字段显示逻辑\n"
            "• 完善数据传递机制\n"
            "• 移除授权限制，完全开放使用\n\n"
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


def main():
    """主程序入口函数"""
    try:
        print("正在初始化数据库...")
        db.init_db()  # 初始化数据库
        print("数据库初始化完成")
        
        print("正在启动应用程序...")
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        print("应用程序启动成功")
        
        sys.exit(app.exec_())
    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 