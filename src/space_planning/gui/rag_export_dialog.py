#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG知识库导出对话框
提供用户友好的界面来配置RAG导出选项
"""

import os
import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QComboBox, QSpinBox, QPushButton, QTextEdit, QFileDialog,
    QGroupBox, QCheckBox, QProgressBar, QMessageBox, QTabWidget, QWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon

from ..utils.rag_export import RAGExporter

class RAGExportWorker(QThread):
    """RAG导出工作线程"""
    
    progress_updated = pyqtSignal(str)
    export_finished = pyqtSignal(dict)
    export_error = pyqtSignal(str)
    
    def __init__(self, data, output_dir, format_type, max_chunk_size):
        super().__init__()
        self.data = data
        self.output_dir = output_dir
        self.format_type = format_type
        self.max_chunk_size = max_chunk_size
    
    def run(self):
        try:
            self.progress_updated.emit("正在初始化RAG导出器...")
            exporter = RAGExporter(self.max_chunk_size)
            
            self.progress_updated.emit("正在处理政策数据...")
            result = exporter.export_for_rag(
                self.data, 
                self.output_dir, 
                self.format_type
            )
            
            self.progress_updated.emit("导出完成！")
            self.export_finished.emit(result)
            
        except Exception as e:
            self.export_error.emit(str(e))

class RAGExportDialog(QDialog):
    """RAG知识库导出对话框"""
    
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.data = data or []
        self.worker = None
        self.init_ui()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("RAG知识库导出")
        self.setMinimumSize(600, 500)
        
        # 设置窗口图标（如果有的话）
        try:
            self.setWindowIcon(QIcon("docs/icon.ico"))
        except:
            pass
        
        layout = QVBoxLayout()
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 基本设置选项卡
        basic_tab = self.create_basic_settings_tab()
        tab_widget.addTab(basic_tab, "基本设置")
        
        # 高级设置选项卡
        advanced_tab = self.create_advanced_settings_tab()
        tab_widget.addTab(advanced_tab, "高级设置")
        
        # 预览选项卡
        preview_tab = self.create_preview_tab()
        tab_widget.addTab(preview_tab, "导出预览")
        
        layout.addWidget(tab_widget)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态文本
        self.status_label = QLabel("准备就绪")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        self.export_button = QPushButton("开始导出")
        self.export_button.clicked.connect(self.start_export)
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def create_basic_settings_tab(self):
        """创建基本设置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 输出目录设置
        dir_group = QGroupBox("输出目录")
        dir_layout = QHBoxLayout()
        
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("选择输出目录...")
        dir_layout.addWidget(self.output_dir_edit)
        
        browse_button = QPushButton("浏览...")
        browse_button.clicked.connect(self.browse_output_dir)
        dir_layout.addWidget(browse_button)
        
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)
        
        # 导出格式设置
        format_group = QGroupBox("导出格式")
        format_layout = QVBoxLayout()
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Markdown (.md)", "JSON (.json)", "Text (.txt)"])
        format_layout.addWidget(self.format_combo)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # 段落大小设置
        chunk_group = QGroupBox("段落设置")
        chunk_layout = QHBoxLayout()
        
        chunk_layout.addWidget(QLabel("最大段落大小:"))
        
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(1000, 10000)
        self.chunk_size_spin.setValue(4096)
        self.chunk_size_spin.setSuffix(" 字符")
        chunk_layout.addWidget(self.chunk_size_spin)
        
        chunk_layout.addStretch()
        chunk_group.setLayout(chunk_layout)
        layout.addWidget(chunk_group)
        
        # 统计信息
        stats_group = QGroupBox("统计信息")
        stats_layout = QVBoxLayout()
        
        self.stats_label = QLabel(f"待导出政策数量: {len(self.data)}")
        stats_layout.addWidget(self.stats_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_advanced_settings_tab(self):
        """创建高级设置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 分段模式设置
        segment_group = QGroupBox("分段模式")
        segment_layout = QVBoxLayout()
        
        self.markdown_mode_check = QCheckBox("Markdown智能分段（按标题层级）")
        self.markdown_mode_check.setChecked(True)
        segment_layout.addWidget(self.markdown_mode_check)
        
        self.html_mode_check = QCheckBox("HTML/DOCX智能分段（转换后按标题）")
        segment_layout.addWidget(self.html_mode_check)
        
        self.txt_mode_check = QCheckBox("TXT/PDF智能分段（按标题或字符数）")
        segment_layout.addWidget(self.txt_mode_check)
        
        segment_group.setLayout(segment_layout)
        layout.addWidget(segment_group)
        
        # 元数据设置
        metadata_group = QGroupBox("元数据设置")
        metadata_layout = QVBoxLayout()
        
        self.include_metadata_check = QCheckBox("包含政策元数据（标题、日期、来源等）")
        self.include_metadata_check.setChecked(True)
        metadata_layout.addWidget(self.include_metadata_check)
        
        self.include_segment_info_check = QCheckBox("包含段落信息（ID、大小等）")
        self.include_segment_info_check.setChecked(True)
        metadata_layout.addWidget(self.include_segment_info_check)
        
        metadata_group.setLayout(metadata_layout)
        layout.addWidget(metadata_group)
        
        # 文件命名设置
        naming_group = QGroupBox("文件命名")
        naming_layout = QVBoxLayout()
        
        self.auto_naming_check = QCheckBox("自动生成文件名（推荐）")
        self.auto_naming_check.setChecked(True)
        naming_layout.addWidget(self.auto_naming_check)
        
        naming_group.setLayout(naming_layout)
        layout.addWidget(naming_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_preview_tab(self):
        """创建预览选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 预览文本区域
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("预览将在这里显示...")
        layout.addWidget(self.preview_text)
        
        # 更新预览按钮
        update_preview_button = QPushButton("更新预览")
        update_preview_button.clicked.connect(self.update_preview)
        layout.addWidget(update_preview_button)
        
        widget.setLayout(layout)
        return widget
    
    def browse_output_dir(self):
        """浏览输出目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "选择输出目录",
            os.path.expanduser("~/Documents")
        )
        if dir_path:
            self.output_dir_edit.setText(dir_path)
    
    def update_preview(self):
        """更新预览"""
        try:
            # 获取当前设置
            format_type = self.get_format_type()
            max_chunk_size = self.chunk_size_spin.value()
            
            # 生成预览内容
            preview_content = f"""# RAG知识库导出预览

## 导出设置
- 输出格式: {format_type}
- 最大段落大小: {max_chunk_size} 字符
- 政策数量: {len(self.data)}

## 分段规则
- Markdown文件: 按标题层级分段（最多6级）
- HTML/DOCX文件: 转换后按标题分段
- TXT/PDF文件: 按标题或字符数分段

## 输出文件结构（优化后）
```
output_directory/
├── rag_metadata.json              # 导出元数据
├── rag_knowledge_base.md          # 合并的Markdown文件
├── rag_knowledge_base.json        # 合并的JSON文件
└── rag_knowledge_base.txt         # 合并的TXT文件
```

## 文件内容结构
每个政策将包含：
- 政策标题和基本信息
- 完整的政策正文内容
- 按段落组织的结构化内容

## 优化特性
- ✅ 所有政策合并到单个文件
- ✅ 减少文件数量，便于管理
- ✅ 保持内容完整性和结构性
- ✅ 兼容MaxKB向量模型自动分段
- ✅ 符合RAG最佳实践
"""
            
            self.preview_text.setPlainText(preview_content)
            
        except Exception as e:
            self.preview_text.setPlainText(f"预览生成失败: {str(e)}")
    
    def get_format_type(self):
        """获取选择的格式类型"""
        format_text = self.format_combo.currentText()
        if "Markdown" in format_text:
            return "markdown"
        elif "JSON" in format_text:
            return "json"
        else:
            return "txt"
    
    def validate_settings(self):
        """验证设置"""
        if not self.output_dir_edit.text().strip():
            QMessageBox.warning(self, "警告", "请选择输出目录")
            return False
        
        if not os.path.exists(self.output_dir_edit.text()):
            try:
                os.makedirs(self.output_dir_edit.text(), exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建输出目录: {str(e)}")
                return False
        
        if not self.data:
            QMessageBox.warning(self, "警告", "没有可导出的数据")
            return False
        
        return True
    
    def start_export(self):
        """开始导出"""
        if not self.validate_settings():
            return
        
        # 禁用导出按钮
        self.export_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        
        # 获取导出参数
        output_dir = self.output_dir_edit.text()
        format_type = self.get_format_type()
        max_chunk_size = self.chunk_size_spin.value()
        
        # 创建工作线程
        self.worker = RAGExportWorker(
            self.data, 
            output_dir, 
            format_type, 
            max_chunk_size
        )
        
        # 连接信号
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.export_finished.connect(self.export_completed)
        self.worker.export_error.connect(self.export_failed)
        
        # 启动线程
        self.worker.start()
    
    def update_progress(self, message):
        """更新进度信息"""
        self.status_label.setText(message)
    
    def export_completed(self, result):
        """导出完成"""
        self.progress_bar.setVisible(False)
        self.export_button.setEnabled(True)
        
        if result.get('success'):
            QMessageBox.information(
                self, 
                "导出成功", 
                f"RAG知识库导出完成！\n\n"
                f"输出目录: {result['output_dir']}\n"
                f"政策数量: {result['total_policies']}\n"
                f"段落数量: {result['total_segments']}\n"
                f"元数据文件: {result['metadata_file']}"
            )
            self.accept()
        else:
            QMessageBox.critical(
                self, 
                "导出失败", 
                f"RAG知识库导出失败: {result.get('error', '未知错误')}"
            )
    
    def export_failed(self, error_message):
        """导出失败"""
        self.progress_bar.setVisible(False)
        self.export_button.setEnabled(True)
        QMessageBox.critical(self, "导出失败", f"导出过程中发生错误: {error_message}")
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, 
                "确认退出", 
                "导出正在进行中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.terminate()
                self.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

# 便捷函数
def show_rag_export_dialog(parent, data):
    """
    显示RAG导出对话框
    
    Args:
        parent: 父窗口
        data: 政策数据列表
    
    Returns:
        对话框结果
    """
    dialog = RAGExportDialog(parent, data)
    return dialog.exec_() 