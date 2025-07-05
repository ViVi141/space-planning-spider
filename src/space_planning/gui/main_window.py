from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QTextEdit, QFileDialog, QMessageBox, QSpinBox, QDialog, QDialogButtonBox, QListWidget, QRadioButton, QProgressBar, QDateEdit, QGroupBox, QCheckBox, QHeaderView)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate, QTimer
from PyQt5.QtGui import QColor
import sys
import os
import threading
from datetime import datetime, timedelta
import re
import urllib3
import warnings

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

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
    
    def __init__(self, level, keywords, need_crawl=True, start_date=None, end_date=None, enable_anti_crawler=True, speed_mode="正常速度"):
        super().__init__()
        self.level = level
        self.keywords = keywords
        self.need_crawl = need_crawl
        self.start_date = start_date
        self.end_date = end_date
        self.enable_anti_crawler = enable_anti_crawler
        self.speed_mode = speed_mode
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
                # 爬取新数据
                spider = None
                if self.level == "国家住建部":
                    from space_planning.spider.national import NationalSpider
                    spider = NationalSpider()
                elif self.level == "全部机构":
                    # 对于全部机构，默认使用国家级爬虫
                    from space_planning.spider.national import NationalSpider
                    spider = NationalSpider()
                else:
                    # 其他机构暂时使用国家级爬虫
                    from space_planning.spider.national import NationalSpider
                    spider = NationalSpider()
                
                if spider:
                    # 根据速度模式调整防反爬虫设置
                    if not self.enable_anti_crawler:
                        self.progress_signal.emit("已禁用速度限制，使用最快速度（其他防反爬虫措施仍有效）")
                    else:
                        if self.speed_mode == "快速模式":
                            self.progress_signal.emit("使用快速模式，可能被反爬虫检测")
                        elif self.speed_mode == "慢速模式":
                            self.progress_signal.emit("使用慢速模式，更安全但速度较慢")
                        else:
                            self.progress_signal.emit("使用正常速度模式")
                    
                    # 自定义回调函数，实时更新进度和发送数据
                    def progress_callback(message):
                        if message.startswith("POLICY_DATA:"):
                            # 解析政策数据
                            data_parts = message[12:].split("|")
                            if len(data_parts) >= 4:
                                policy = {
                                    'level': '国家住建部',
                                    'title': data_parts[0],
                                    'pub_date': data_parts[1],
                                    'source': data_parts[2],
                                    'content': data_parts[3],
                                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                # 立即发送到界面
                                self.single_policy_signal.emit(policy)
                        else:
                            self.progress_signal.emit(f"爬取进度: {message}")
                    
                    new_policies = spider.crawl_policies(
                        keywords=self.keywords,
                        callback=progress_callback,
                        start_date=self.start_date,
                        end_date=self.end_date,
                        speed_mode=self.speed_mode,
                        disable_speed_limit=not self.enable_anti_crawler,
                        stop_callback=lambda: self.stop_flag
                    )
                else:
                    new_policies = []
                
                # 实时保存和显示数据（在爬取过程中已经完成）
                # 这里只需要处理停止后的数据保存
                if new_policies and not self.stop_flag:
                    for i, policy in enumerate(new_policies):
                        db.insert_policy(
                            policy['level'], 
                            policy['title'], 
                            policy['pub_date'], 
                            policy['source'], 
                            policy['content'], 
                            policy['crawl_time']
                        )
                
                if not self.stop_flag:
                    self.progress_signal.emit(f"爬取完成，共获取 {len(new_policies)} 条新数据")
                else:
                    self.progress_signal.emit("搜索已停止")
                    # 停止后也要显示已爬取的数据
                    if new_policies:
                        self.progress_signal.emit(f"已停止，共获取 {len(new_policies)} 条数据")
            else:
                self.progress_signal.emit("数据库数据充足，无需爬取新数据")
            
            # 最终查询结果
            final_results = db.search_policies(self.level, self.keywords, self.start_date, self.end_date)
            self.result_signal.emit(final_results)
            self.finished_signal.emit()
            
        except Exception as e:
            self.error_signal.emit(str(e))
    
    def stop(self):
        """停止搜索"""
        self.stop_flag = True

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("空间规划政策合规性分析系统")
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), "../../../docs/icon.ico")
        if os.path.exists(icon_path):
            from PyQt5.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        
        self.resize(1400, 900)
        
        self.init_ui()
    
    def create_menu_bar(self):
        """创建菜单栏"""
        from PyQt5.QtWidgets import QAction
        
        menubar = self.menuBar()
        file_menu = menubar.addMenu('文件')
        tools_menu = menubar.addMenu('工具')
        help_menu = menubar.addMenu('帮助')
        
        # 文件菜单
        export_action = QAction('导出数据', self)
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)
        
        # 工具菜单
        status_action = QAction('爬虫状态', self)
        status_action.triggered.connect(self.show_crawler_status)
        tools_menu.addAction(status_action)
        
        # 帮助菜单
        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def init_ui(self):
        # 创建菜单栏
        self.create_menu_bar()
        
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # 顶部：预设模式选择
        mode_group = QGroupBox("预设模式")
        mode_layout = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "日常监控模式 - 最近30天",
            "项目分析模式 - 最近6个月",
            "历史补全模式 - 最近2年",
            "快速预览模式 - 最近7天"
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
        self.level_combo.addItems(["全部机构", "国家住建部", "广东省", "中山市", "火炬高技术产业开发区"])
        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText("请输入项目关键词，如'控制性详细规划'、'建设用地'...")
        self.keyword_edit.setMinimumWidth(300)
        row1_layout.addWidget(QLabel("机构："))
        row1_layout.addWidget(self.level_combo)
        row1_layout.addWidget(QLabel("项目关键词："))
        row1_layout.addWidget(self.keyword_edit)
        row1_layout.addStretch()
        
        # 第二行：时间区间
        row2_layout = QHBoxLayout()
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.end_date_edit.setDate(QDate.currentDate())
        row2_layout.addWidget(QLabel("起始日期："))
        row2_layout.addWidget(self.start_date_edit)
        row2_layout.addWidget(QLabel("结束日期："))
        row2_layout.addWidget(self.end_date_edit)
        row2_layout.addStretch()
        
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
        
        query_layout.addLayout(row1_layout)
        query_layout.addLayout(row2_layout)
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
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 机构
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # 标题自适应
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 发布日期
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 来源
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 政策类型
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)  # 操作列固定宽度
        self.table.setColumnWidth(5, 100)
        
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)  # 允许文字换行
        self.table.verticalHeader().setDefaultSectionSize(60)  # 设置行高
        
        # 性能优化：设置最大显示行数
        self.max_display_rows = 100  # 最大显示100行
        self.current_page = 0
        self.page_size = 50  # 每页50行
        
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
        self.full_text.setMaximumHeight(250)
        self.full_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px;
                background-color: #fafafa;
                font-family: "Microsoft YaHei", Arial, sans-serif;
                font-size: 13px;
                line-height: 1.5;
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
            start_date = self.start_date_edit.date().toString('yyyy-MM-dd')
            end_date = self.end_date_edit.date().toString('yyyy-MM-dd')
            
            # 检查是否需要爬取新数据
            db_results = db.search_policies(level, keywords, start_date, end_date)
            need_crawl = self._need_crawl_new_data(db_results, keywords)
            
            # 获取防反爬虫设置
            enable_anti_crawler = self.anti_crawler_checkbox.isChecked()
            speed_mode = self.speed_combo.currentText()
            
            # 创建并启动搜索线程
            self.current_data = [] # 清空当前数据
            self.refresh_table([]) # 清空表格
            self.search_thread = SearchThread(level, keywords, need_crawl, start_date, end_date, enable_anti_crawler, speed_mode)
            self.search_thread.progress_signal.connect(self.update_progress)
            self.search_thread.result_signal.connect(self.update_results)
            self.search_thread.single_policy_signal.connect(self.on_new_policy) # 新增信号连接
            self.search_thread.finished_signal.connect(self.search_finished)
            self.search_thread.error_signal.connect(self.search_error)
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
            self.stats_label.setText(f"共找到 {len(self.current_data)} 条政策")
        
        QApplication.processEvents()
    
    def update_results(self, results):
        """实时更新结果表格"""
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
        # 立即保存到数据库
        db.insert_policy(
            policy['level'], 
            policy['title'], 
            policy['pub_date'], 
            policy['source'], 
            policy['content'], 
            policy['crawl_time']
        )
        
        # policy为dict，需转为tuple与表格结构一致
        # 注意：数据库返回的字段顺序是 (id, level, title, pub_date, source, content)
        row = (None, policy['level'], policy['title'], policy['pub_date'], policy['source'], policy['content'])
        self.current_data.append(row)
        
        # 实时显示：每一条都立即显示
        self._add_single_row(row)
        
        # 更新统计信息
        self.stats_label.setText(f"共找到 {len(self.current_data)} 条政策")
        
        # 强制刷新界面
        QApplication.processEvents()

    def search_finished(self):
        """搜索完成"""
        self.progress_label.setText("查询完成")
        self.progress_bar.setVisible(False)
        self.search_btn.setText("🔍 智能查询")
        self.search_btn.setEnabled(True)
        
        # 显示结果统计
        QMessageBox.information(self, "查询完成", 
            f"🎉 智能查询完成！\n\n"
            f"📊 共找到 {len(self.current_data)} 条政策")
    
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
            latest_date = max(result[3] for result in db_results if result[3])
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
    
    def _set_table_row(self, row, item):
        """设置表格行数据"""
        # 设置各列数据 - 数据库字段顺序：(id, level, title, pub_date, source, content)
        
        # 机构列
        level_item = QTableWidgetItem(str(item[1]))
        level_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 0, level_item)
        
        # 标题列 - 支持换行
        title_item = QTableWidgetItem(str(item[2]))
        title_item.setToolTip(str(item[2]))  # 鼠标悬停显示完整标题
        self.table.setItem(row, 1, title_item)
        
        # 发布日期列
        date_item = QTableWidgetItem(str(item[3]))
        date_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 2, date_item)
        
        # 来源列 - 超链接样式
        source_item = QTableWidgetItem(str(item[4]))
        source_item.setForeground(QColor(0, 102, 204))  # 蓝色链接样式
        source_item.setToolTip(f"点击查看来源：{item[4]}")
        self.table.setItem(row, 3, source_item)
        
        # 政策类型列
        content = item[5] if len(item) > 5 else ""
        policy_types = self.compliance_analyzer.classify_policy(str(item[2]), content)
        type_item = QTableWidgetItem(", ".join(policy_types))
        type_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 4, type_item)
        
        # 操作列 - 按钮样式
        action_item = QTableWidgetItem("📄 查看全文")
        action_item.setForeground(QColor(0, 128, 0))  # 绿色按钮样式
        action_item.setTextAlignment(Qt.AlignCenter)
        action_item.setToolTip("点击查看政策全文")
        self.table.setItem(row, 5, action_item)

    def on_export(self):
        """导出为Word"""
        if not self.current_data:
            QMessageBox.warning(self, "警告", "没有数据可导出")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "保存Word文件", "", "Word文档 (*.docx)")
        if file_path:
            try:
                export_to_word(self.current_data, file_path)
                QMessageBox.information(self, "成功", "Word文档导出成功！")
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
            self.batch_thread = SearchThread("全部机构", None, True, start_date, end_date)
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
            policy_list.addItem(f"{i+1}. {policy[2]} ({policy[1]})")
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
                    selected_policies.append(self.current_data[index])
                
                # 进行对比分析
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
            keywords = self.comparer.find_keywords(policy[5])
            result += f"   政策{i+1}（{policy[1]}）：{', '.join(keywords) if keywords else '无关键词'}\n"
        
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
            # 获取政策内容
            content = policy[5] if len(policy) > 5 else ""
            title = policy[2]
            
            # 政策分类
            policy_types = self.compliance_analyzer.classify_policy(title, content)
            for policy_type in policy_types:
                type_stats[policy_type] = type_stats.get(policy_type, 0) + 1
            
            # 合规性分析
            compliance = self.compliance_analyzer.analyze_compliance(content, project_keywords)
            
            if compliance['score'] > 50:
                high_impact_policies.append({
                    'title': title,
                    'pub_date': policy[3],
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
            clipboard.setText(text)
            QMessageBox.information(self, "复制成功", "政策全文已复制到剪贴板")
        else:
            QMessageBox.warning(self, "提示", "没有可复制的内容")
    
    def on_table_click(self, row, col):
        """处理表格点击事件"""
        if row >= len(self.current_data):
            return
            
        if col == 3:  # 点击来源列
            source = self.current_data[row][4]
            # 实际复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setText(source)
            QMessageBox.information(self, "复制成功", f"政策来源已复制到剪贴板：\n{source}")
        elif col == 5:  # 点击"查看全文"列
            # 兼容tuple和dict
            content = self.current_data[row][5] if len(self.current_data[row]) > 5 else ""
            if content:
                # 保留原始格式，使用setHtml而不是setText
                self.full_text.setPlainText(content)
                # 更新标题
                title = self.current_data[row][2]
                self.full_text_title.setText(f"正在查看：{title}")
                # 滚动到全文区域
                self.full_text.setFocus()
                # 不显示弹窗提示，静默显示
                
                # 重新设置该行的样式，确保来源列保持超链接样式
                self._set_table_row(row, self.current_data[row])
            else:
                # 静默处理，不显示弹窗
                self.full_text.setPlainText("该政策暂无全文内容")
                self.full_text_title.setText("暂无内容")
    
    def show_crawler_status(self):
        """显示爬虫状态"""
        try:
            spider = NationalSpider()
            status = spider.get_crawler_status()
            
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
            
            dialog = QDialog(self)
            dialog.setWindowTitle("爬虫状态监控")
            dialog.resize(600, 500)
            
            layout = QVBoxLayout()
            
            # 状态显示区域
            status_text = QTextEdit()
            status_text.setReadOnly(True)
            
            # 格式化状态信息
            status_info = "=== 爬虫状态监控 ===\n\n"
            
            # 防反爬虫信息
            anti_info = status['anti_crawler_info']
            status_info += "【防反爬虫状态】\n"
            status_info += f"总请求数: {anti_info['total_requests']}\n"
            status_info += f"被屏蔽IP数: {anti_info['blocked_ips']}\n"
            status_info += f"代理池数量: {anti_info['proxy_count']}\n"
            status_info += f"当前代理: {anti_info['current_proxy'] or '无'}\n\n"
            
            # 监控统计
            monitor_stats = status['monitor_stats']
            runtime_stats = monitor_stats['runtime_stats']
            status_info += "【运行统计】\n"
            status_info += f"运行时间: {runtime_stats['runtime_hours']:.2f} 小时\n"
            status_info += f"总请求数: {runtime_stats['total_requests']}\n"
            status_info += f"成功请求: {runtime_stats['total_success']}\n"
            status_info += f"失败请求: {runtime_stats['total_errors']}\n"
            status_info += f"成功率: {runtime_stats['success_rate']:.2%}\n"
            status_info += f"每小时请求数: {runtime_stats['requests_per_hour']:.1f}\n\n"
            
            # 错误摘要
            error_summary = monitor_stats['error_summary']
            if error_summary:
                status_info += "【错误摘要】\n"
                for error_type, count in error_summary.items():
                    status_info += f"{error_type}: {count} 次\n"
                status_info += "\n"
            
            # 建议
            recommendations = monitor_stats['recommendations']
            if recommendations:
                status_info += "【优化建议】\n"
                for rec in recommendations:
                    status_info += f"• {rec}\n"
                status_info += "\n"
            
            # 域名统计
            domain_stats = monitor_stats['domain_stats']
            if domain_stats:
                status_info += "【域名统计】\n"
                for domain, stats in domain_stats.items():
                    status_info += f"{domain}:\n"
                    status_info += f"  成功率: {stats['success_rate']:.2%}\n"
                    status_info += f"  请求频率: {stats['request_frequency']:.1f}/分钟\n"
                    status_info += f"  总请求数: {stats['total_requests']}\n"
            
            status_text.setPlainText(status_info)
            layout.addWidget(status_text)
            
            # 按钮区域
            button_layout = QHBoxLayout()
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.accept)
            button_layout.addStretch()
            button_layout.addWidget(close_btn)
            layout.addLayout(button_layout)
            
            dialog.setLayout(layout)
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"获取爬虫状态失败: {str(e)}")
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于", 
            "空间规划政策合规性分析系统\n\n"
            "版本: 2.0\n"
            "功能: 智能爬取、合规分析、数据导出\n"
            "技术: Python + PyQt5 + SQLite\n\n"
            "防反爬虫功能已启用，包含:\n"
            "• 随机User-Agent轮换\n"
            "• 请求频率限制\n"
            "• 智能延迟控制\n"
            "• 错误监控与重试\n"
            "• 会话轮换机制\n"
            "• SSL证书验证禁用")
    

    
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