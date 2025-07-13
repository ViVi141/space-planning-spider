#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫状态实时监控对话框
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QTextEdit, QGroupBox, QProgressBar, QCheckBox, QSpinBox, QFrame)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor
import os
from datetime import datetime
from typing import Dict, Optional

from ..spider.national import NationalSpider

class StatusUpdateThread(QThread):
    """状态更新线程"""
    status_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, spider, dialog=None):
        super().__init__()
        self.spider = spider
        self.dialog = dialog
        self.running = True
    
    def run(self):
        """运行状态更新"""
        while self.running:
            try:
                # 动态获取当前爬虫实例
                current_spider = self.get_current_spider()
                status = current_spider.get_crawler_status()
                self.status_signal.emit(status)
            except Exception as e:
                self.error_signal.emit(str(e))
            
            # 等待1秒后再次更新
            self.msleep(1000)
    
    def get_current_spider(self):
        """获取当前爬虫实例"""
        try:
            # 尝试从对话框获取当前爬虫
            if hasattr(self, 'dialog') and self.dialog:
                return self.dialog.get_current_spider()
            return self.spider
        except:
            return self.spider
    
    def get_all_spiders_status(self):
        """获取所有爬虫的状态"""
        status_dict = {}
        
        # 获取各个爬虫的状态
        if self.dialog and hasattr(self.dialog, 'spiders_dict') and self.dialog.spiders_dict:
            for name, spider in self.dialog.spiders_dict.items():
                try:
                    status = spider.get_crawler_status()
                    status_dict[name] = status
                except Exception as e:
                    status_dict[name] = {'error': str(e)}
        
        # 添加当前爬虫状态
        try:
            current_status = self.spider.get_crawler_status()
            status_dict['current'] = current_status
        except Exception as e:
            status_dict['current'] = {'error': str(e)}
        
        return status_dict
    
    def stop(self):
        """停止线程"""
        self.running = False

class ProxyStatusWidget(QFrame):
    """代理状态显示组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.setup_ui()
        
    def setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 代理状态标题
        title_layout = QHBoxLayout()
        title_label = QLabel("代理状态")
        title_label.setStyleSheet("font-weight: bold;")
        self.proxy_enabled_label = QLabel()
        title_layout.addWidget(title_label)
        title_layout.addWidget(self.proxy_enabled_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # 当前代理信息
        proxy_info_layout = QHBoxLayout()
        proxy_info_layout.addWidget(QLabel("当前代理:"))
        self.current_proxy_label = QLabel()
        proxy_info_layout.addWidget(self.current_proxy_label)
        proxy_info_layout.addStretch()
        layout.addLayout(proxy_info_layout)
        
        # 代理评分
        score_layout = QHBoxLayout()
        score_layout.addWidget(QLabel("代理评分:"))
        self.proxy_score_label = QLabel()
        score_layout.addWidget(self.proxy_score_label)
        score_layout.addStretch()
        layout.addLayout(score_layout)
        
        # 响应时间
        response_layout = QHBoxLayout()
        response_layout.addWidget(QLabel("响应时间:"))
        self.response_time_label = QLabel()
        response_layout.addWidget(self.response_time_label)
        response_layout.addStretch()
        layout.addLayout(response_layout)
        
        # 使用统计
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("使用次数:"))
        self.usage_count_label = QLabel()
        stats_layout.addWidget(self.usage_count_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        # 添加重试信息
        retry_layout = QHBoxLayout()
        retry_layout.addWidget(QLabel("重试次数:"))
        self.retry_count_label = QLabel()
        retry_layout.addWidget(self.retry_count_label)
        retry_layout.addStretch()
        layout.addLayout(retry_layout)
        
        self.setLayout(layout)
    
    def update_status(self, proxy_info: Optional[Dict] = None):
        """更新代理状态显示"""
        if not proxy_info:
            self.proxy_enabled_label.setText("已禁用")
            self.proxy_enabled_label.setStyleSheet("color: gray;")
            self.current_proxy_label.setText("无")
            self.proxy_score_label.setText("-")
            self.response_time_label.setText("-")
            self.usage_count_label.setText("-")
            self.retry_count_label.setText("-")
            return
        
        # 更新代理状态
        self.proxy_enabled_label.setText("已启用")
        self.proxy_enabled_label.setStyleSheet("color: green;")
        
        # 更新代理IP
        if proxy_info.get('current_proxy'):
            self.current_proxy_label.setText(proxy_info['current_proxy'])
            self.current_proxy_label.setStyleSheet("color: blue;")
        else:
            self.current_proxy_label.setText("等待获取")
            self.current_proxy_label.setStyleSheet("color: orange;")
        
        # 更新评分
        score = proxy_info.get('score', 0)
        self.proxy_score_label.setText(f"{score:.1f}")
        if score >= 80:
            self.proxy_score_label.setStyleSheet("color: green;")
        elif score >= 60:
            self.proxy_score_label.setStyleSheet("color: orange;")
        else:
            self.proxy_score_label.setStyleSheet("color: red;")
        
        # 更新响应时间
        response_time = proxy_info.get('response_time')
        if response_time is not None:
            self.response_time_label.setText(f"{response_time:.2f}s")
        else:
            self.response_time_label.setText("-")
        
        # 更新使用次数
        self.usage_count_label.setText(str(proxy_info.get('usage_count', 0)))

        # 更新重试次数
        retry_count = proxy_info.get('retry_count', 0)
        if retry_count > 0:
            self.retry_count_label.setText(f"{retry_count} (重试中)")
            self.retry_count_label.setStyleSheet("color: orange;")
        else:
            self.retry_count_label.setText("0")
            self.retry_count_label.setStyleSheet("")

class CrawlerStatusDialog(QDialog):
    """爬虫状态对话框"""
    
    def __init__(self, crawler, parent=None):
        super().__init__(parent)
        self.crawler = crawler
        self.setup_ui()
        self.start_monitoring()
    
    def setup_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"爬虫状态 - {self.crawler.name}")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # 添加代理状态显示组件
        self.proxy_status = ProxyStatusWidget()
        layout.addWidget(self.proxy_status)
        
        # 添加重试配置显示
        retry_group = QGroupBox("重试配置")
        retry_layout = QVBoxLayout()
        self.max_retries_label = QLabel()
        self.retry_delay_label = QLabel()
        self.retry_codes_label = QLabel()
        retry_layout.addWidget(self.max_retries_label)
        retry_layout.addWidget(self.retry_delay_label)
        retry_layout.addWidget(self.retry_codes_label)
        retry_group.setLayout(retry_layout)
        layout.addWidget(retry_group)
        
        # 添加进度显示
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("进度:"))
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)
        
        # 添加统计信息
        stats_layout = QVBoxLayout()
        self.total_label = QLabel()
        self.success_label = QLabel()
        self.failed_label = QLabel()
        self.success_rate_label = QLabel()
        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.success_label)
        stats_layout.addWidget(self.failed_label)
        stats_layout.addWidget(self.success_rate_label)
        layout.addLayout(stats_layout)
        
        # 添加按钮
        button_layout = QHBoxLayout()
        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.stop_crawler)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def start_monitoring(self):
        """开始监控"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)  # 每秒更新一次
    
    def update_status(self):
        """更新状态显示"""
        if not self.crawler:
            return
        
        try:
            stats = self.crawler.get_crawling_stats()
            session = self.crawler.get_session_info()
            
            # 更新代理状态
            if stats['proxy_enabled']:
                current_proxy = session.get('current_proxy')
                proxy_stats = stats.get('proxy_stats', {})
                proxy_details = proxy_stats.get('proxy_details', [])
                
                # 查找当前代理的详细信息
                current_proxy_detail = None
                if current_proxy and proxy_details:
                    current_proxy_ip = current_proxy.split(':')[0]
                    for detail in proxy_details:
                        if detail['ip'] == current_proxy_ip:
                            current_proxy_detail = detail
                            break
                
                proxy_info = {
                    'enabled': True,
                    'current_proxy': current_proxy,
                    'score': current_proxy_detail['score'] if current_proxy_detail else 0,
                    'response_time': current_proxy_detail['avg_response_time'] if current_proxy_detail else None,
                    'usage_count': session['proxy_usage_count'],
                    'retry_count': session.get('retry_count', 0)
                }
            else:
                proxy_info = None
            
            self.proxy_status.update_status(proxy_info)
            
            # 更新重试配置
            retry_stats = stats.get('retry_stats', {})
            self.max_retries_label.setText(f"最大重试次数: {retry_stats.get('max_retries', 3)}")
            self.retry_delay_label.setText(
                f"重试延迟: {retry_stats.get('retry_delay', 5)}秒 - "
                f"{retry_stats.get('max_retry_delay', 60)}秒"
            )
            retry_codes = retry_stats.get('retry_codes', [])
            self.retry_codes_label.setText(f"重试状态码: {', '.join(map(str, retry_codes))}")
            
            # 更新进度和统计信息
            total = stats['total_pages']
            success = stats['successful_pages']
            failed = stats['failed_pages']
            
            if total > 0:
                success_rate = (success / total) * 100
                self.progress_bar.setValue(int(success_rate))
            
            self.total_label.setText(f"总页面数: {total}")
            self.success_label.setText(f"成功页面: {success}")
            self.failed_label.setText(f"失败页面: {failed}")
            self.success_rate_label.setText(f"成功率: {success_rate:.1f}%" if total > 0 else "成功率: -")
            
        except Exception as e:
            print(f"更新状态失败: {e}")
    
    def stop_crawler(self):
        """停止爬虫"""
        if self.crawler:
            self.crawler.stop_crawling()
            self.close()
    
    def closeEvent(self, event):
        """关闭事件"""
        self.timer.stop()
        super().closeEvent(event) 