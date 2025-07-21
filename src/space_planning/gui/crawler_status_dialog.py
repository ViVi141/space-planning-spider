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
        # 安全获取爬虫名称
        crawler_name = getattr(self.crawler, 'name', 'Unknown')
        self.setWindowTitle(f"爬虫状态 - {crawler_name}")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # 添加代理状态显示组件
        self.proxy_status = ProxyStatusWidget()
        layout.addWidget(self.proxy_status)
        
        # 添加爬虫基本信息
        info_group = QGroupBox("爬虫信息")
        info_layout = QVBoxLayout()
        self.level_label = QLabel("爬虫级别: 未知")
        self.mode_label = QLabel("速度模式: 未知")
        info_layout.addWidget(self.level_label)
        info_layout.addWidget(self.mode_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
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
        
        # 添加多线程信息显示
        multithread_group = QGroupBox("多线程信息")
        multithread_layout = QVBoxLayout()
        self.multithread_label = QLabel("活跃线程: 0")
        self.crawled_label = QLabel("已爬取: 0")
        self.saved_label = QLabel("已保存: 0")
        self.elapsed_label = QLabel("耗时: 0.0秒")
        multithread_layout.addWidget(self.multithread_label)
        multithread_layout.addWidget(self.crawled_label)
        multithread_layout.addWidget(self.saved_label)
        multithread_layout.addWidget(self.elapsed_label)
        multithread_group.setLayout(multithread_layout)
        layout.addWidget(multithread_group)
        
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
            # 尝试获取爬虫统计信息
            stats = self._get_crawler_stats()
            session = self._get_session_info()
            
            # 更新代理状态
            proxy_info = self._extract_proxy_info(stats, session)
            self.proxy_status.update_status(proxy_info)
            
            # 更新重试配置
            self._update_retry_config(stats)
            
            # 更新进度和统计信息
            self._update_progress_and_stats(stats)
            
        except Exception as e:
            print(f"更新状态失败: {e}")
            # 显示错误信息
            self.total_label.setText(f"状态更新失败: {str(e)}")
            self.success_label.setText("")
            self.failed_label.setText("")
            self.success_rate_label.setText("")
    
    def _get_crawler_stats(self):
        """安全获取爬虫统计信息"""
        try:
            # 首先尝试获取多线程爬虫的状态
            if hasattr(self.crawler, 'get_crawler_status'):
                status = self.crawler.get_crawler_status()
                
                # 如果是多线程爬虫，提取统计信息
                if 'multithread_stats' in status:
                    multithread_stats = status['multithread_stats']
                    proxy_stats = status.get('proxy_stats', {})
                    
                    # 转换为标准格式
                    return {
                        'total_pages': multithread_stats.get('total_tasks', 0),
                        'successful_pages': multithread_stats.get('completed_tasks', 0),
                        'failed_pages': multithread_stats.get('failed_tasks', 0),
                        'proxy_enabled': status.get('enable_proxy', False),
                        'proxy_status': {
                            'enabled': status.get('enable_proxy', False),
                            'current_proxy': proxy_stats.get('current_proxy'),
                            'proxy_details': proxy_stats.get('proxy_details', [])
                        },
                        'multithread_info': {
                            'active_threads': multithread_stats.get('active_threads', 0),
                            'total_crawled': multithread_stats.get('total_crawled', 0),
                            'total_saved': multithread_stats.get('total_saved', 0),
                            'elapsed_time': multithread_stats.get('elapsed_time', 0)
                        },
                        'level': status.get('level', '未知'),
                        'speed_mode': status.get('speed_mode', '正常速度'),
                        'categories': status.get('categories', [])
                    }
                else:
                    # 普通爬虫状态
                    return status
            
            # 尝试不同的方法名
            elif hasattr(self.crawler, 'get_crawling_stats'):
                return self.crawler.get_crawling_stats()
            elif hasattr(self.crawler, 'get_stats'):
                return self.crawler.get_stats()
            else:
                # 返回默认统计信息
                return {
                    'total_pages': 0,
                    'successful_pages': 0,
                    'failed_pages': 0,
                    'proxy_enabled': False
                }
        except Exception as e:
            print(f"获取爬虫统计失败: {e}")
            return {
                'total_pages': 0,
                'successful_pages': 0,
                'failed_pages': 0,
                'proxy_enabled': False
            }
    
    def _get_session_info(self):
        """安全获取会话信息"""
        try:
            if hasattr(self.crawler, 'get_session_info'):
                return self.crawler.get_session_info()
            else:
                return {}
        except Exception as e:
            print(f"获取会话信息失败: {e}")
            return {}
    
    def _extract_proxy_info(self, stats, session):
        """提取代理信息"""
        try:
            # 首先检查stats中是否有proxy_status
            if 'proxy_status' in stats:
                proxy_status = stats['proxy_status']
                proxy_enabled = proxy_status.get('enabled', False)
                
                if proxy_enabled and proxy_status.get('current_proxy'):
                    current_proxy_info = proxy_status['current_proxy']
                    return {
                        'enabled': True,
                        'current_proxy': f"{current_proxy_info['ip']}:{current_proxy_info['port']}",
                        'score': current_proxy_info.get('success_rate', 0) * 100,  # 转换为百分比
                        'response_time': None,  # 持久化代理管理器不提供响应时间
                        'usage_count': current_proxy_info.get('use_count', 0),
                        'retry_count': current_proxy_info.get('consecutive_failures', 0)
                    }
                elif proxy_enabled:
                    # 代理已启用但没有当前代理
                    return {
                        'enabled': True,
                        'current_proxy': "等待获取",
                        'score': 0,
                        'response_time': None,
                        'usage_count': 0,
                        'retry_count': 0
                    }
                else:
                    # 代理未启用
                    return None
            
            # 兼容旧格式 - 检查proxy_enabled字段
            proxy_enabled = stats.get('proxy_enabled', False)
            
            if not proxy_enabled:
                return None
            
            # 获取当前代理信息
            current_proxy = session.get('current_proxy')
            proxy_stats = stats.get('proxy_stats', {})
            proxy_details = proxy_stats.get('proxy_details', [])
            
            # 查找当前代理的详细信息
            current_proxy_detail = None
            if current_proxy and proxy_details:
                current_proxy_ip = current_proxy.split(':')[0]
                for detail in proxy_details:
                    if detail.get('ip') == current_proxy_ip:
                        current_proxy_detail = detail
                        break
            
            return {
                'enabled': True,
                'current_proxy': current_proxy or "等待获取",
                'score': current_proxy_detail.get('score', 0) if current_proxy_detail else 0,
                'response_time': current_proxy_detail.get('avg_response_time') if current_proxy_detail else None,
                'usage_count': session.get('proxy_usage_count', 0),
                'retry_count': session.get('retry_count', 0)
            }
        except Exception as e:
            print(f"提取代理信息失败: {e}")
            return None
    
    def _update_retry_config(self, stats):
        """更新重试配置显示"""
        try:
            retry_stats = stats.get('retry_stats', {})
            self.max_retries_label.setText(f"最大重试次数: {retry_stats.get('max_retries', 3)}")
            self.retry_delay_label.setText(
                f"重试延迟: {retry_stats.get('retry_delay', 5)}秒 - "
                f"{retry_stats.get('max_retry_delay', 60)}秒"
            )
            retry_codes = retry_stats.get('retry_codes', [])
            self.retry_codes_label.setText(f"重试状态码: {', '.join(map(str, retry_codes))}")
        except Exception as e:
            print(f"更新重试配置失败: {e}")
            self.max_retries_label.setText("最大重试次数: 未知")
            self.retry_delay_label.setText("重试延迟: 未知")
            self.retry_codes_label.setText("重试状态码: 未知")
    
    def _update_progress_and_stats(self, stats):
        """更新进度和统计信息"""
        try:
            # 获取基础统计信息
            total = stats.get('total_pages', 0)
            successful = stats.get('successful_pages', 0)
            failed = stats.get('failed_pages', 0)
            
            # 计算成功率
            if total > 0:
                success_rate = (successful / total) * 100
            else:
                success_rate = 0
            
            # 更新基础统计显示
            self.total_label.setText(f"总任务数: {total}")
            self.success_label.setText(f"成功任务数: {successful}")
            self.failed_label.setText(f"失败任务数: {failed}")
            self.success_rate_label.setText(f"成功率: {success_rate:.1f}%")
            
            # 更新进度条
            if total > 0:
                progress = (successful + failed) / total * 100
                self.progress_bar.setValue(int(progress))
            else:
                self.progress_bar.setValue(0)
            
            # 显示多线程特定信息
            if 'multithread_info' in stats:
                multithread_info = stats['multithread_info']
                active_threads = multithread_info.get('active_threads', 0)
                total_crawled = multithread_info.get('total_crawled', 0)
                total_saved = multithread_info.get('total_saved', 0)
                elapsed_time = multithread_info.get('elapsed_time', 0)
                
                # 更新多线程信息显示
                if hasattr(self, 'multithread_label'):
                    self.multithread_label.setText(f"活跃线程: {active_threads}")
                if hasattr(self, 'crawled_label'):
                    self.crawled_label.setText(f"已爬取: {total_crawled}")
                if hasattr(self, 'saved_label'):
                    self.saved_label.setText(f"已保存: {total_saved}")
                if hasattr(self, 'elapsed_label'):
                    self.elapsed_label.setText(f"耗时: {elapsed_time:.1f}秒")
            
            # 显示爬虫级别和模式信息
            if 'level' in stats:
                level = stats['level']
                speed_mode = stats.get('speed_mode', '正常速度')
                if hasattr(self, 'level_label'):
                    self.level_label.setText(f"爬虫级别: {level}")
                if hasattr(self, 'mode_label'):
                    self.mode_label.setText(f"速度模式: {speed_mode}")
            
        except Exception as e:
            print(f"更新进度和统计信息失败: {e}")
            self.total_label.setText("统计信息更新失败")
            self.success_label.setText("")
            self.failed_label.setText("")
            self.success_rate_label.setText("")
    
    def stop_crawler(self):
        """停止爬虫"""
        if self.crawler:
            try:
                if hasattr(self.crawler, 'stop_crawling'):
                    self.crawler.stop_crawling()
            except Exception as e:
                print(f"停止爬虫失败: {e}")
            self.close()
    
    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'timer'):
            self.timer.stop()
        super().closeEvent(event) 