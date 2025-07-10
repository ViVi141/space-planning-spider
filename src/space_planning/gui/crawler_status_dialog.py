#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫状态实时监控对话框
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QTextEdit, QGroupBox, QProgressBar, QCheckBox, QSpinBox)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor
import os
from datetime import datetime

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

class CrawlerStatusDialog(QDialog):
    """爬虫状态实时监控对话框"""
    
    def __init__(self, parent=None, spiders_dict=None):
        super().__init__(parent)
        self.setWindowTitle("爬虫状态实时监控")
        self.setModal(False)  # 非模态对话框
        self.resize(800, 600)
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), "../../../docs/icon.ico")
        if os.path.exists(icon_path):
            from PyQt5.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        
        # 保存爬虫实例字典
        self.spiders_dict = spiders_dict or {}
        
        # 使用传入的spider实例或创建新的
        if parent and hasattr(parent, 'spider'):
            self.spider = parent.spider
        else:
            # 尝试从主窗口获取当前爬虫实例
            if parent and hasattr(parent, 'search_thread') and parent.search_thread.isRunning():
                # 如果正在搜索，尝试获取搜索线程中的爬虫
                try:
                    if hasattr(parent.search_thread, 'spider') and parent.search_thread.spider:
                        self.spider = parent.search_thread.spider
                    else:
                        self.spider = NationalSpider()
                except:
                    self.spider = NationalSpider()
            else:
                self.spider = NationalSpider()
        self.status_thread = None
        self.auto_refresh = True
        self.refresh_interval = 2  # 默认2秒刷新一次
        
        self.init_ui()
        self.start_status_update()
        
        # 定时刷新
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.update_status_display)
        self.refresh_timer.start(self.refresh_interval * 1000)
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 控制面板
        control_group = QGroupBox("控制面板")
        control_layout = QHBoxLayout()
        
        # 自动刷新控制
        self.auto_refresh_cb = QCheckBox("自动刷新")
        self.auto_refresh_cb.setChecked(self.auto_refresh)
        self.auto_refresh_cb.toggled.connect(self.on_auto_refresh_toggled)
        control_layout.addWidget(self.auto_refresh_cb)
        
        # 刷新间隔设置
        control_layout.addWidget(QLabel("刷新间隔:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(self.refresh_interval)
        self.interval_spin.valueChanged.connect(self.on_interval_changed)
        control_layout.addWidget(self.interval_spin)
        control_layout.addWidget(QLabel("秒"))
        
        # 手动刷新按钮
        self.refresh_btn = QPushButton("立即刷新")
        self.refresh_btn.clicked.connect(self.update_status_display)
        control_layout.addWidget(self.refresh_btn)
        
        control_layout.addStretch()
        
        # 重置统计按钮
        self.reset_btn = QPushButton("重置统计")
        self.reset_btn.clicked.connect(self.reset_stats)
        control_layout.addWidget(self.reset_btn)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # 状态显示区域
        status_group = QGroupBox("实时状态")
        status_layout = QVBoxLayout()
        
        # 状态文本显示
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setFont(QFont("Consolas", 10))
        status_layout.addWidget(self.status_text)
        
        # 进度条显示
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 初始状态显示
        self.update_status_display()
    
    def start_status_update(self):
        """启动状态更新线程"""
        if self.status_thread is None or not self.status_thread.isRunning():
            self.status_thread = StatusUpdateThread(self.spider, self)
            self.status_thread.status_signal.connect(self.on_status_updated)
            self.status_thread.error_signal.connect(self.on_status_error)
            self.status_thread.start()
    
    def stop_status_update(self):
        """停止状态更新线程"""
        if self.status_thread and self.status_thread.isRunning():
            self.status_thread.stop()
            self.status_thread.wait()
    
    def on_status_updated(self, status):
        """状态更新回调"""
        if self.auto_refresh:
            self.current_status = status
            self.update_status_display()
    
    def on_status_error(self, error_msg):
        """状态更新错误回调"""
        print(f"状态更新错误: {error_msg}")
    
    def update_status_display(self):
        """更新状态显示"""
        try:
            # 获取所有爬虫的状态
            all_status = self.get_all_spiders_status()
            
            # 格式化状态信息
            status_info = self.format_all_status_info(all_status)
            self.status_text.setPlainText(status_info)
            
        except Exception as e:
            self.status_text.setPlainText(f"获取状态失败: {str(e)}")
    
    def get_current_spider(self):
        """获取当前爬虫实例"""
        try:
            # 首先尝试从主窗口获取当前搜索线程中的爬虫
            parent = self.parent()
            if parent and hasattr(parent, 'search_thread'):
                search_thread = getattr(parent, 'search_thread', None)
                if search_thread and hasattr(search_thread, 'isRunning') and search_thread.isRunning():
                    if hasattr(search_thread, 'spider'):
                        return search_thread.spider
            
            # 如果搜索线程中没有，使用默认爬虫
            return self.spider
        except:
            return self.spider
    
    def get_all_spiders_status(self):
        """获取所有爬虫的状态"""
        status_dict = {}
        
        # 获取各个爬虫的状态
        if hasattr(self, 'spiders_dict') and self.spiders_dict:
            for name, spider in self.spiders_dict.items():
                try:
                    status = spider.get_crawler_status()
                    status_dict[name] = status
                except Exception as e:
                    status_dict[name] = {'error': str(e)}
        
        # 添加当前爬虫状态
        try:
            current_spider = self.get_current_spider()
            status = current_spider.get_crawler_status()
            status_dict['current'] = status
        except Exception as e:
            status_dict['current'] = {'error': str(e)}
        
        return status_dict
    
    def format_status_info(self, status):
        """格式化状态信息"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        status_info = f"=== 爬虫状态实时监控 ===\n"
        status_info += f"更新时间: {current_time}\n\n"
        
        # 基本状态
        status_info += "【基本状态】\n"
        status_info += f"速度模式: {status.get('speed_mode', '未知')}\n"
        
        # 监控统计
        monitor_stats = status.get('monitor_stats', {})
        if monitor_stats:
            runtime_stats = monitor_stats.get('runtime_stats', {})
            status_info += "\n【运行统计】\n"
            status_info += f"运行时间: {runtime_stats.get('runtime_hours', 0):.2f} 小时\n"
            status_info += f"总请求数: {runtime_stats.get('total_requests', 0)}\n"
            status_info += f"成功请求: {runtime_stats.get('total_success', 0)}\n"
            status_info += f"失败请求: {runtime_stats.get('total_errors', 0)}\n"
            status_info += f"成功率: {runtime_stats.get('success_rate', 0):.2%}\n"
            status_info += f"平均每小时请求数: {runtime_stats.get('requests_per_hour', 0):.1f}\n"
            status_info += f"最近1小时请求数: {runtime_stats.get('recent_requests_1h', 0)}\n"
            status_info += f"活跃域名数: {runtime_stats.get('active_domains', 0)}\n"
            
            # 错误摘要
            error_summary = monitor_stats.get('error_summary', {})
            if error_summary:
                status_info += "\n【错误摘要】\n"
                for error_type, count in error_summary.items():
                    status_info += f"{error_type}: {count} 次\n"
            
            # 建议
            recommendations = monitor_stats.get('recommendations', [])
            if recommendations:
                status_info += "\n【优化建议】\n"
                for rec in recommendations:
                    status_info += f"• {rec}\n"
            
            # 域名统计
            domain_stats = monitor_stats.get('domain_stats', {})
            if domain_stats:
                status_info += "\n【域名统计】\n"
                for domain, stats in domain_stats.items():
                    status_info += f"{domain}:\n"
                    status_info += f"  成功率: {stats.get('success_rate', 0):.2%}\n"
                    status_info += f"  请求频率: {stats.get('request_frequency', 0):.1f}/分钟\n"
                    status_info += f"  总请求数: {stats.get('total_requests', 0)}\n"
        else:
            # 兼容旧结构
            status_info += "\n【运行统计】\n"
            status_info += f"总请求数: {status.get('total_requests', 0)}\n"
            status_info += f"成功率: {status.get('success_rate', 0):.2%}\n"
            status_info += f"每小时请求数: {status.get('requests_per_hour', 0):.1f}\n"
            status_info += f"运行时间: {status.get('runtime_hours', 0):.2f} 小时\n"
        
        # 速率限制器状态
        rate_limiter_stats = status.get('rate_limiter_stats', {})
        if rate_limiter_stats:
            status_info += "\n【速率限制】\n"
            status_info += f"最大请求数: {rate_limiter_stats.get('max_requests', 0)}\n"
            status_info += f"时间窗口: {rate_limiter_stats.get('time_window', 0)} 秒\n"
        
        return status_info
    
    def format_all_status_info(self, all_status):
        """格式化所有爬虫的状态信息"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        status_info = f"=== 爬虫状态实时监控 ===\n"
        status_info += f"更新时间: {current_time}\n\n"
        
        # 显示各个爬虫的状态
        for spider_name, status in all_status.items():
            if spider_name == 'current':
                continue  # 跳过current，避免重复
                
            status_info += f"【{spider_name.upper()}】\n"
            
            if 'error' in status:
                status_info += f"错误: {status['error']}\n\n"
                continue
            
            # 基本状态
            status_info += f"速度模式: {status.get('speed_mode', '未知')}\n"
            
            # 监控统计
            monitor_stats = status.get('monitor_stats', {})
            if monitor_stats:
                runtime_stats = monitor_stats.get('runtime_stats', {})
                status_info += f"运行时间: {runtime_stats.get('runtime_hours', 0):.2f} 小时\n"
                status_info += f"总请求数: {runtime_stats.get('total_requests', 0)}\n"
                status_info += f"成功请求: {runtime_stats.get('total_success', 0)}\n"
                status_info += f"失败请求: {runtime_stats.get('total_errors', 0)}\n"
                status_info += f"成功率: {runtime_stats.get('success_rate', 0):.2%}\n"
                status_info += f"平均每小时请求数: {runtime_stats.get('requests_per_hour', 0):.1f}\n"
                status_info += f"最近1小时请求数: {runtime_stats.get('recent_requests_1h', 0)}\n"
                status_info += f"活跃域名数: {runtime_stats.get('active_domains', 0)}\n"
                
                # 错误摘要
                error_summary = monitor_stats.get('error_summary', {})
                if error_summary:
                    status_info += "错误摘要:\n"
                    for error_type, count in error_summary.items():
                        status_info += f"  {error_type}: {count} 次\n"
                
                # 建议
                recommendations = monitor_stats.get('recommendations', [])
                if recommendations:
                    status_info += "优化建议:\n"
                    for rec in recommendations:
                        status_info += f"  • {rec}\n"
                
                # 域名统计
                domain_stats = monitor_stats.get('domain_stats', {})
                if domain_stats:
                    status_info += "域名统计:\n"
                    for domain, stats in domain_stats.items():
                        status_info += f"  {domain}:\n"
                        status_info += f"    成功率: {stats.get('success_rate', 0):.2%}\n"
                        status_info += f"    请求频率: {stats.get('request_frequency', 0):.1f}/分钟\n"
                        status_info += f"    总请求数: {stats.get('total_requests', 0)}\n"
            else:
                status_info += "无监控数据\n"
            
            status_info += "\n"
        
        return status_info
    
    def on_auto_refresh_toggled(self, checked):
        """自动刷新开关"""
        self.auto_refresh = checked
        if checked:
            self.refresh_timer.start(self.refresh_interval * 1000)
        else:
            self.refresh_timer.stop()
    
    def on_interval_changed(self, value):
        """刷新间隔改变"""
        self.refresh_interval = value
        if self.auto_refresh:
            self.refresh_timer.stop()
            self.refresh_timer.start(self.refresh_interval * 1000)
    
    def reset_stats(self):
        """重置统计"""
        try:
            # 重置所有爬虫的统计
            if hasattr(self.spider, 'monitor'):
                self.spider.monitor.reset_stats()
            
            # 重置其他爬虫的统计
            if self.spiders_dict:
                for name, spider in self.spiders_dict.items():
                    if hasattr(spider, 'monitor'):
                        spider.monitor.reset_stats()
            
            self.update_status_display()
        except Exception as e:
            print(f"重置统计失败: {e}")
    
    def closeEvent(self, event):
        """关闭事件"""
        self.stop_status_update()
        if self.refresh_timer:
            self.refresh_timer.stop()
        event.accept() 