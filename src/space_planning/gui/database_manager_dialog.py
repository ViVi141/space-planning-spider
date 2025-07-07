#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库管理对话框
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QTableWidget, QTableWidgetItem, QTextEdit, QGroupBox, 
                             QMessageBox, QProgressBar, QComboBox, QFileDialog, QHeaderView, QApplication)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
import os
from datetime import datetime

from ..core import database as db
from ..core import config

class BackupThread(QThread):
    """备份线程"""
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, operation, backup_file=None):
        super().__init__()
        self.operation = operation  # 'backup' or 'restore'
        self.backup_file = backup_file
    
    def run(self):
        try:
            if self.operation == 'backup':
                self.progress_signal.emit("正在备份数据库...")
                success = db.backup_database()
                if success:
                    self.finished_signal.emit(True, "数据库备份完成")
                else:
                    self.finished_signal.emit(False, "数据库备份失败")
            elif self.operation == 'restore':
                self.progress_signal.emit("正在恢复数据库...")
                success = db.restore_database(self.backup_file)
                if success:
                    self.finished_signal.emit(True, "数据库恢复完成")
                else:
                    self.finished_signal.emit(False, "数据库恢复失败")
        except Exception as e:
            self.finished_signal.emit(False, f"操作失败: {str(e)}")

class DatabaseManagerDialog(QDialog):
    """数据库管理对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据库管理")
        self.setModal(True)
        self.resize(800, 600)
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), "../../../docs/icon.ico")
        if os.path.exists(icon_path):
            from PyQt5.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        
        self.backup_thread = None
        self.init_ui()
        self.load_database_info()
        self.load_backup_files()
        
        # 定时刷新数据库信息
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_database_info)
        self.refresh_timer.start(5000)  # 每5秒刷新一次
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 数据库信息组
        info_group = QGroupBox("数据库信息")
        info_layout = QVBoxLayout()
        
        # 数据库状态信息
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(150)
        self.info_text.setReadOnly(True)
        info_layout.addWidget(self.info_text)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新信息")
        refresh_btn.clicked.connect(self.load_database_info)
        info_layout.addWidget(refresh_btn)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 备份管理组
        backup_group = QGroupBox("备份管理")
        backup_layout = QVBoxLayout()
        
        # 备份操作按钮
        backup_btn_layout = QHBoxLayout()
        self.backup_btn = QPushButton("立即备份")
        self.backup_btn.clicked.connect(self.backup_database)
        backup_btn_layout.addWidget(self.backup_btn)
        
        self.restore_btn = QPushButton("恢复数据库")
        self.restore_btn.clicked.connect(self.restore_database)
        backup_btn_layout.addWidget(self.restore_btn)
        
        self.cleanup_btn = QPushButton("清理旧备份")
        self.cleanup_btn.clicked.connect(self.cleanup_backups)
        backup_btn_layout.addWidget(self.cleanup_btn)
        
        # 添加分隔线
        backup_btn_layout.addStretch()
        
        # 清理数据库按钮
        self.clear_db_btn = QPushButton("🗑️ 清理数据库")
        self.clear_db_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; }")
        self.clear_db_btn.clicked.connect(self.clear_database)
        backup_btn_layout.addWidget(self.clear_db_btn)
        
        backup_layout.addLayout(backup_btn_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        backup_layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: green;")
        backup_layout.addWidget(self.status_label)
        
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # 备份文件列表组
        files_group = QGroupBox("备份文件列表")
        files_layout = QVBoxLayout()
        
        # 备份文件表格
        self.backup_table = QTableWidget()
        self.backup_table.setColumnCount(4)
        self.backup_table.setHorizontalHeaderLabels(["文件名", "大小(MB)", "创建时间", "操作"])
        header = self.backup_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents) 
            header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        files_layout.addWidget(self.backup_table)
        
        files_group.setLayout(files_layout)
        layout.addWidget(files_group)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
    
    def load_database_info(self):
        """加载数据库信息"""
        try:
            info = db.get_database_info()
            
            info_text = f"""数据库路径: {info.get('database_path', '未知')}
备份目录: {info.get('backup_dir', '未知')}
政策数量: {info.get('policy_count', 0)} 条
数据库大小: {info.get('file_size_mb', 0)} MB
最新政策日期: {info.get('latest_date', '无')}
最后备份时间: {info.get('last_backup_time', '从未备份')}

配置信息:
- 安装模式: {'是' if config.app_config.install_mode else '否'}
- 自动备份: {'启用' if config.app_config.get_database_config().get('backup_enabled', True) else '禁用'}
- 备份间隔: {config.app_config.get_database_config().get('backup_interval', 7)} 天
- 最大备份数: {config.app_config.get_database_config().get('max_backup_count', 10)} 个"""
            
            self.info_text.setText(info_text)
        except Exception as e:
            self.info_text.setText(f"加载数据库信息失败: {str(e)}")
    
    def load_backup_files(self):
        """加载备份文件列表"""
        try:
            backup_files = db.get_backup_files()
            print(f"获取到 {len(backup_files)} 个备份文件")
            
            # 安全设置行数
            row_count = len(backup_files)
            if row_count > 1000:  # 限制最大行数避免溢出
                row_count = 1000
                print(f"备份文件数量过多，限制显示前 {row_count} 个")
            
            self.backup_table.setRowCount(row_count)
            
            for row, backup_file in enumerate(backup_files[:row_count]):
                # 文件名
                filename_item = QTableWidgetItem(backup_file['filename'])
                self.backup_table.setItem(row, 0, filename_item)
                
                # 文件大小
                size_item = QTableWidgetItem(f"{backup_file['file_size_mb']} MB")
                self.backup_table.setItem(row, 1, size_item)
                
                # 创建时间
                time_item = QTableWidgetItem(backup_file['file_time'])
                self.backup_table.setItem(row, 2, time_item)
                
                # 操作按钮
                restore_btn = QPushButton("恢复")
                restore_btn.clicked.connect(lambda checked, filename=backup_file['filename']: self.restore_from_file(filename))
                self.backup_table.setCellWidget(row, 3, restore_btn)
            
            if not backup_files:
                self.backup_table.setRowCount(1)
                no_data_item = QTableWidgetItem("暂无备份文件")
                self.backup_table.setItem(0, 0, no_data_item)
                
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载备份文件列表失败: {str(e)}")
    
    def backup_database(self):
        """备份数据库"""
        reply = QMessageBox.question(self, "确认备份", 
                                   "确定要备份当前数据库吗？\n备份文件将保存在备份目录中。",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.start_backup_operation('backup')
    
    def restore_database(self):
        """恢复数据库"""
        reply = QMessageBox.warning(self, "警告", 
                                  "恢复数据库将覆盖当前数据库！\n当前数据库将被备份后覆盖。\n确定要继续吗？",
                                  QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 选择备份文件
            backup_dir = db.get_backup_dir()
            backup_file, _ = QFileDialog.getOpenFileName(
                self, "选择备份文件", backup_dir, "数据库文件 (*.db)")
            
            if backup_file:
                filename = os.path.basename(backup_file)
                self.start_backup_operation('restore', filename)
    
    def restore_from_file(self, filename):
        """从指定文件恢复数据库"""
        reply = QMessageBox.warning(self, "警告", 
                                  f"确定要从备份文件 '{filename}' 恢复数据库吗？\n当前数据库将被覆盖！",
                                  QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.start_backup_operation('restore', filename)
    
    def cleanup_backups(self):
        """清理旧备份"""
        reply = QMessageBox.question(self, "确认清理", 
                                   "确定要清理旧的备份文件吗？\n只保留最新的备份文件。",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                db.cleanup_old_backups()
                self.load_backup_files()
                QMessageBox.information(self, "成功", "旧备份文件清理完成")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"清理备份文件失败: {str(e)}")
    
    def clear_database(self):
        """清理数据库 - 删除所有政策数据"""
        try:
            # 获取数据库信息
            info = db.get_database_info()
            policy_count = info.get('policy_count', 0)
            
            if policy_count == 0:
                QMessageBox.information(self, "提示", "数据库中没有政策数据，无需清理")
                return
            
            # 确认对话框
            reply = QMessageBox.question(
                self, 
                "⚠️ 确认清理数据库", 
                f"确定要清理数据库吗？\n\n"
                f"当前数据库包含 {policy_count} 条政策数据\n"
                f"清理后将删除所有数据并自动重启程序\n\n"
                f"⚠️ 此操作不可撤销！\n"
                f"建议先备份数据库。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 再次确认
                reply2 = QMessageBox.question(
                    self, 
                    "最终确认", 
                    f"这是最后一次确认！\n\n"
                    f"确定要删除所有 {policy_count} 条政策数据吗？\n"
                    f"此操作将立即执行并重启程序。",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply2 == QMessageBox.Yes:
                    # 执行清理
                    self.status_label.setText("正在清理数据库...")
                    self.status_label.setStyleSheet("color: red;")
                    self.clear_db_btn.setEnabled(False)
                    QApplication.processEvents()
                    
                    success, deleted_count = db.clear_database()
                    
                    if success:
                        self.status_label.setText(f"清理完成，删除了 {deleted_count} 条数据")
                        QMessageBox.information(
                            self, 
                            "清理完成", 
                            f"数据库清理成功！\n\n"
                            f"删除了 {deleted_count} 条政策数据\n"
                            f"程序将在3秒后自动重启..."
                        )
                        
                        # 延迟重启程序
                        QTimer.singleShot(3000, self.restart_application)
                    else:
                        self.status_label.setText("清理失败")
                        self.status_label.setStyleSheet("color: red;")
                        self.clear_db_btn.setEnabled(True)
                        QMessageBox.critical(self, "错误", "数据库清理失败，请检查错误日志")
                        
        except Exception as e:
            self.status_label.setText("清理失败")
            self.status_label.setStyleSheet("color: red;")
            self.clear_db_btn.setEnabled(True)
            QMessageBox.critical(self, "错误", f"清理数据库时出错: {str(e)}")
    
    def restart_application(self):
        """重启应用程序"""
        try:
            # 获取当前程序路径
            import sys
            import subprocess
            
            # 获取当前脚本路径
            current_script = sys.argv[0]
            
            # 启动新进程
            subprocess.Popen([sys.executable, current_script])
            
            # 关闭当前程序
            QApplication.quit()
            
        except Exception as e:
            print(f"重启程序失败: {e}")
            QMessageBox.warning(self, "警告", f"自动重启失败，请手动重启程序: {str(e)}")
    
    def start_backup_operation(self, operation, backup_file=None):
        """开始备份或恢复操作"""
        # 禁用按钮
        self.backup_btn.setEnabled(False)
        self.restore_btn.setEnabled(False)
        self.cleanup_btn.setEnabled(False)
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        
        # 更新状态
        self.status_label.setText("操作进行中...")
        self.status_label.setStyleSheet("color: blue;")
        
        # 启动线程
        self.backup_thread = BackupThread(operation, backup_file)
        self.backup_thread.progress_signal.connect(self.update_progress)
        self.backup_thread.finished_signal.connect(self.operation_finished)
        self.backup_thread.start()
    
    def update_progress(self, message):
        """更新进度信息"""
        self.status_label.setText(message)
    
    def operation_finished(self, success, message):
        """操作完成"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        
        # 恢复按钮状态
        self.backup_btn.setEnabled(True)
        self.restore_btn.setEnabled(True)
        self.cleanup_btn.setEnabled(True)
        
        # 更新状态
        if success:
            self.status_label.setText("操作完成")
            self.status_label.setStyleSheet("color: green;")
            QMessageBox.information(self, "成功", message)
            
            # 刷新数据
            self.load_database_info()
            self.load_backup_files()
        else:
            self.status_label.setText("操作失败")
            self.status_label.setStyleSheet("color: red;")
            QMessageBox.warning(self, "错误", message)
        
        # 清理线程
        if self.backup_thread:
            self.backup_thread.deleteLater()
            self.backup_thread = None
    
    def closeEvent(self, event):
        """关闭事件"""
        # 停止定时器
        if self.refresh_timer:
            self.refresh_timer.stop()
        
        # 停止线程
        if self.backup_thread and self.backup_thread.isRunning():
            self.backup_thread.terminate()
            self.backup_thread.wait()
        
        event.accept() 