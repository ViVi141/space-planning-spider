#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫设置对话框
允许用户选择防检测模式和配置参数（无代理池）
"""

import sys
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
                             QLineEdit, QPushButton, QGroupBox, QTextEdit, QTabWidget,
                             QFormLayout, QSlider, QFrame, QWidget)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor

from ..spider.config import crawler_config, AntiDetectionMode

class CrawlerSettingsDialog(QDialog):
    """爬虫设置对话框（无代理池）"""
    
    settings_changed = pyqtSignal()  # 设置改变信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("爬虫设置")
        self.setModal(True)
        self.resize(600, 500)
        
        # 初始化UI
        self.init_ui()
        self.load_current_settings()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 基本设置标签页
        basic_tab = self.create_basic_tab()
        tab_widget.addTab(basic_tab, "基本设置")
        
        # 高级设置标签页
        advanced_tab = self.create_advanced_tab()
        tab_widget.addTab(advanced_tab, "高级设置")
        
        # 行为设置标签页
        behavior_tab = self.create_behavior_tab()
        tab_widget.addTab(behavior_tab, "行为设置")
        
        layout.addWidget(tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("保存设置")
        self.save_button.clicked.connect(self.save_settings)
        
        self.reset_button = QPushButton("重置默认")
        self.reset_button.clicked.connect(self.reset_to_default)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def create_basic_tab(self):
        """创建基本设置标签页"""
        widget = QWidget()
        layout = QFormLayout()
        
        # 防检测模式选择
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("正常模式", AntiDetectionMode.NORMAL)
        self.mode_combo.addItem("增强模式", AntiDetectionMode.ENHANCED)
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        
        mode_label = QLabel("防检测模式:")
        mode_label.setToolTip("正常模式：基础防检测，性能较好\n增强模式：高级防检测，适合严格反爬虫网站")
        layout.addRow(mode_label, self.mode_combo)
        
        # 请求延迟设置
        delay_layout = QHBoxLayout()
        self.min_delay_spin = QDoubleSpinBox()
        self.min_delay_spin.setRange(0.1, 10.0)
        self.min_delay_spin.setSuffix(" 秒")
        self.min_delay_spin.setDecimals(1)
        
        self.max_delay_spin = QDoubleSpinBox()
        self.max_delay_spin.setRange(0.1, 20.0)
        self.max_delay_spin.setSuffix(" 秒")
        self.max_delay_spin.setDecimals(1)
        
        delay_layout.addWidget(QLabel("最小:"))
        delay_layout.addWidget(self.min_delay_spin)
        delay_layout.addWidget(QLabel("最大:"))
        delay_layout.addWidget(self.max_delay_spin)
        
        layout.addRow("请求延迟:", delay_layout)
        
        # 重试设置
        retry_layout = QHBoxLayout()
        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(0, 10)
        self.max_retries_spin.setSuffix(" 次")
        
        self.retry_delay_spin = QSpinBox()
        self.retry_delay_spin.setRange(1, 30)
        self.retry_delay_spin.setSuffix(" 秒")
        
        retry_layout.addWidget(QLabel("最大重试:"))
        retry_layout.addWidget(self.max_retries_spin)
        retry_layout.addWidget(QLabel("重试延迟:"))
        retry_layout.addWidget(self.retry_delay_spin)
        
        layout.addRow("重试设置:", retry_layout)
        
        # 会话设置
        session_layout = QHBoxLayout()
        self.session_rotation_spin = QSpinBox()
        self.session_rotation_spin.setRange(60, 1800)
        self.session_rotation_spin.setSuffix(" 秒")
        
        self.max_requests_spin = QSpinBox()
        self.max_requests_spin.setRange(10, 200)
        self.max_requests_spin.setSuffix(" 次")
        
        session_layout.addWidget(QLabel("轮换间隔:"))
        session_layout.addWidget(self.session_rotation_spin)
        session_layout.addWidget(QLabel("最大请求:"))
        session_layout.addWidget(self.max_requests_spin)
        
        layout.addRow("会话设置:", session_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_advanced_tab(self):
        """创建高级设置标签页"""
        widget = QWidget()
        layout = QFormLayout()
        
        # 请求头设置
        header_group = QGroupBox("请求头设置")
        header_layout = QFormLayout()
        
        self.random_ua_check = QCheckBox("随机User-Agent")
        self.add_referer_check = QCheckBox("添加Referer")
        self.add_fingerprint_check = QCheckBox("添加浏览器指纹")
        
        header_layout.addRow(self.random_ua_check)
        header_layout.addRow(self.add_referer_check)
        header_layout.addRow(self.add_fingerprint_check)
        
        header_group.setLayout(header_layout)
        layout.addRow(header_group)
        
        # 会话管理设置
        session_group = QGroupBox("会话管理")
        session_layout = QFormLayout()
        
        self.enable_session_rotation = QCheckBox("启用会话轮换")
        self.enable_cookie_management = QCheckBox("启用Cookie管理")
        
        session_layout.addRow(self.enable_session_rotation)
        session_layout.addRow(self.enable_cookie_management)
        
        session_group.setLayout(session_layout)
        layout.addRow(session_group)
        
        # 频率限制设置
        rate_group = QGroupBox("频率限制")
        rate_layout = QFormLayout()
        
        self.enable_rate_limiting = QCheckBox("启用频率限制")
        self.requests_per_minute = QSpinBox()
        self.requests_per_minute.setRange(1, 200)
        self.requests_per_minute.setSuffix(" 次/分钟")
        
        rate_layout.addRow(self.enable_rate_limiting)
        rate_layout.addRow("每分钟请求数:", self.requests_per_minute)
        
        rate_group.setLayout(rate_layout)
        layout.addRow(rate_group)

        # 代理策略
        proxy_group = QGroupBox("代理策略")
        proxy_layout = QFormLayout()

        self.rotate_after_success_spin = QSpinBox()
        self.rotate_after_success_spin.setRange(0, 500)
        self.rotate_after_success_spin.setSuffix(" 条")
        self.rotate_after_success_spin.setToolTip("成功获取指定条数政策后强制轮换会话/代理，设置为 0 表示不启用。")

        proxy_layout.addRow("成功轮换阈值:", self.rotate_after_success_spin)

        proxy_group.setLayout(proxy_layout)
        layout.addRow(proxy_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_behavior_tab(self):
        """创建行为设置标签页"""
        widget = QWidget()
        layout = QFormLayout()
        
        # 行为模拟设置
        behavior_group = QGroupBox("行为模拟")
        behavior_layout = QFormLayout()
        
        self.simulate_human_check = QCheckBox("模拟人类行为")
        self.random_delay_check = QCheckBox("随机延迟")
        self.mouse_movement_check = QCheckBox("鼠标移动模拟")
        self.scroll_simulation_check = QCheckBox("滚动模拟")
        
        behavior_layout.addRow(self.simulate_human_check)
        behavior_layout.addRow(self.random_delay_check)
        behavior_layout.addRow(self.mouse_movement_check)
        behavior_layout.addRow(self.scroll_simulation_check)
        
        behavior_group.setLayout(behavior_layout)
        layout.addRow(behavior_group)
        
        # 行为强度设置
        intensity_group = QGroupBox("行为强度")
        intensity_layout = QFormLayout()
        
        self.behavior_intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.behavior_intensity_slider.setRange(1, 10)
        self.behavior_intensity_slider.setTickPosition(QSlider.TicksBelow)
        self.behavior_intensity_slider.setTickInterval(1)
        
        self.intensity_label = QLabel("5")
        self.behavior_intensity_slider.valueChanged.connect(
            lambda v: self.intensity_label.setText(str(v))
        )
        
        intensity_layout.addRow("强度:", self.behavior_intensity_slider)
        intensity_layout.addRow("", self.intensity_label)
        
        intensity_group.setLayout(intensity_layout)
        layout.addRow(intensity_group)
        
        # 模式说明
        mode_info = QTextEdit()
        mode_info.setMaximumHeight(100)
        mode_info.setPlainText("""
正常模式特点：
- 基础请求头伪装
- 简单延迟控制
- 基本重试机制
- 适合大多数政策网站
- 性能较好，资源消耗低

增强模式特点：
- 高级指纹伪装
- 复杂行为模拟
- 增强重试机制
- 适合严格反爬虫网站
- 性能较低，资源消耗高
        """)
        mode_info.setReadOnly(True)
        
        layout.addRow("模式说明:", mode_info)
        
        widget.setLayout(layout)
        return widget
    
    def on_mode_changed(self):
        """模式改变事件"""
        mode = self.mode_combo.currentData()
        crawler_config.set_mode(mode)
        self.load_current_settings()
    
    def load_current_settings(self):
        """加载当前设置"""
        # 设置模式
        current_mode = crawler_config.get_mode()
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == current_mode:
                self.mode_combo.setCurrentIndex(i)
                break
        
        # 设置延迟
        self.min_delay_spin.setValue(crawler_config.get_config('request_delay.min'))
        self.max_delay_spin.setValue(crawler_config.get_config('request_delay.max'))
        
        # 设置重试
        self.max_retries_spin.setValue(crawler_config.get_config('retry_settings.max_retries'))
        self.retry_delay_spin.setValue(crawler_config.get_config('retry_settings.retry_delay'))
        
        # 设置会话
        self.session_rotation_spin.setValue(crawler_config.get_config('session_settings.rotation_interval'))
        self.max_requests_spin.setValue(crawler_config.get_config('session_settings.max_requests_per_session'))
        enable_rotation = crawler_config.get_config('session_settings.enable_rotation')
        if enable_rotation is None:
            enable_rotation = True
        self.enable_session_rotation.setChecked(bool(enable_rotation))
        enable_cookie = crawler_config.get_config('session_settings.enable_cookie_management')
        if enable_cookie is None:
            enable_cookie = True
        self.enable_cookie_management.setChecked(bool(enable_cookie))
        
        # 设置请求头
        self.random_ua_check.setChecked(crawler_config.get_config('headers_settings.randomize_user_agent'))
        self.add_referer_check.setChecked(crawler_config.get_config('headers_settings.add_referer'))
        self.add_fingerprint_check.setChecked(crawler_config.get_config('headers_settings.add_fingerprint'))
        
        # 设置行为
        self.simulate_human_check.setChecked(crawler_config.get_config('behavior_settings.simulate_human_behavior'))
        self.random_delay_check.setChecked(crawler_config.get_config('behavior_settings.random_delay'))
        self.mouse_movement_check.setChecked(crawler_config.get_config('behavior_settings.mouse_movement'))
        self.scroll_simulation_check.setChecked(crawler_config.get_config('behavior_settings.scroll_simulation'))
        intensity_value = crawler_config.get_config('behavior_settings.intensity')
        if not isinstance(intensity_value, (int, float)):
            intensity_value = 5
        intensity_value = max(1, min(int(intensity_value), self.behavior_intensity_slider.maximum()))
        self.behavior_intensity_slider.setValue(intensity_value)
        self.intensity_label.setText(str(intensity_value))

        # 设置频率限制
        enable_rate_limit = crawler_config.get_config('rate_limit_settings.enabled')
        if enable_rate_limit is None:
            enable_rate_limit = False
        self.enable_rate_limiting.setChecked(bool(enable_rate_limit))
        rpm_value = crawler_config.get_config('rate_limit_settings.max_requests_per_minute')
        if not isinstance(rpm_value, int):
            rpm_value = 60
        rpm_value = max(self.requests_per_minute.minimum(), min(rpm_value, self.requests_per_minute.maximum()))
        self.requests_per_minute.setValue(rpm_value)

        rotate_value = crawler_config.get_config('proxy_settings.rotate_after_success_count')
        if rotate_value is None:
            rotate_value = 0
        try:
            rotate_value = int(rotate_value)
        except (TypeError, ValueError):
            rotate_value = 0
        rotate_value = max(self.rotate_after_success_spin.minimum(), min(rotate_value, self.rotate_after_success_spin.maximum()))
        self.rotate_after_success_spin.setValue(rotate_value)
    
    def save_settings(self):
        """保存设置"""
        try:
            # 保存延迟设置
            crawler_config.set_request_delay(
                self.min_delay_spin.value(),
                self.max_delay_spin.value()
            )
            
            # 保存重试设置
            crawler_config.set_retry_settings(
                self.max_retries_spin.value(),
                self.retry_delay_spin.value()
            )
            
            # 保存会话设置
            crawler_config.set_config('session_settings.rotation_interval', self.session_rotation_spin.value())
            crawler_config.set_config('session_settings.max_requests_per_session', self.max_requests_spin.value())
            crawler_config.set_config('session_settings.enable_rotation', self.enable_session_rotation.isChecked())
            crawler_config.set_config('session_settings.enable_cookie_management', self.enable_cookie_management.isChecked())
            
            # 保存请求头设置
            crawler_config.set_config('headers_settings.randomize_user_agent', self.random_ua_check.isChecked())
            crawler_config.set_config('headers_settings.add_referer', self.add_referer_check.isChecked())
            crawler_config.set_config('headers_settings.add_fingerprint', self.add_fingerprint_check.isChecked())
            
            # 保存行为设置
            crawler_config.set_config('behavior_settings.simulate_human_behavior', self.simulate_human_check.isChecked())
            crawler_config.set_config('behavior_settings.random_delay', self.random_delay_check.isChecked())
            crawler_config.set_config('behavior_settings.mouse_movement', self.mouse_movement_check.isChecked())
            crawler_config.set_config('behavior_settings.scroll_simulation', self.scroll_simulation_check.isChecked())
            crawler_config.set_config('behavior_settings.intensity', self.behavior_intensity_slider.value())

            # 保存频率限制设置
            crawler_config.set_config('rate_limit_settings.enabled', self.enable_rate_limiting.isChecked())
            crawler_config.set_config('rate_limit_settings.max_requests_per_minute', self.requests_per_minute.value())

            # 保存代理策略
            crawler_config.set_config('proxy_settings.rotate_after_success_count', self.rotate_after_success_spin.value())
            
            # 保存到文件
            crawler_config.save_config()
            
            # 发送信号
            self.settings_changed.emit()
            
            self.accept()
            
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "保存失败", f"保存设置时发生错误：{e}")
    
    def reset_to_default(self):
        """重置为默认设置"""
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "确认重置", 
            "确定要重置所有设置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 重置为正常模式
            crawler_config.set_mode(AntiDetectionMode.NORMAL)
            self.load_current_settings()
            
            QMessageBox.information(self, "重置完成", "设置已重置为默认值") 