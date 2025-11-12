#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫状态实时监控对话框
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QGroupBox, QProgressBar, QFrame, QMessageBox)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from typing import Dict, Optional

import logging

logger = logging.getLogger(__name__)

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
                status = {}
                session_info = {}
                if current_spider:
                    if hasattr(current_spider, 'get_crawler_status'):
                        status = current_spider.get_crawler_status() or {}
                    if hasattr(current_spider, 'get_session_info'):
                        try:
                            session_info = current_spider.get_session_info() or {}
                        except Exception:
                            session_info = {}
                self.status_signal.emit({
                    'status': status,
                    'session': session_info
                })
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
        except Exception:
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
    
    @staticmethod
    def _to_float(value, default=0.0):
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                value = value.strip()
                if not value:
                    return default
                return float(value)
            except ValueError:
                return default
        return default
    
    @staticmethod
    def _to_int(value, default=0):
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                value = value.strip()
                if not value:
                    return default
                return int(float(value))
            except ValueError:
                return default
        return default
        
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
        score = self._to_float(proxy_info.get('score'), 0.0)
        self.proxy_score_label.setText(f"{score:.1f}")
        if score >= 80:
            self.proxy_score_label.setStyleSheet("color: green;")
        elif score >= 60:
            self.proxy_score_label.setStyleSheet("color: orange;")
        else:
            self.proxy_score_label.setStyleSheet("color: red;")
        
        # 更新响应时间
        response_time = self._to_float(proxy_info.get('response_time'), None)
        if response_time is not None:
            self.response_time_label.setText(f"{response_time:.2f}s")
        else:
            self.response_time_label.setText("-")
        
        # 更新使用次数
        usage_count = self._to_int(proxy_info.get('usage_count'), 0)
        self.usage_count_label.setText(str(usage_count))

        # 更新重试次数
        retry_count = self._to_int(proxy_info.get('retry_count'), 0)
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
        self.is_closing = False  # 标记对话框是否正在关闭
        self.status_thread: Optional[StatusUpdateThread] = None
        try:
            self.setup_ui()
            # 延迟启动监控，确保UI已完全初始化
            QTimer.singleShot(500, self.start_monitoring)  # 增加到500ms，确保UI完全初始化
        except Exception as e:
            logger.error(f"初始化爬虫状态对话框失败: {e}", exc_info=True)
            # 即使初始化失败，也要显示对话框，但提示错误
            QMessageBox.warning(self, "错误", f"初始化失败: {str(e)[:100]}")
    
    @staticmethod
    def _to_float(value, default=0.0):
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                value = value.strip()
                if not value:
                    return default
                return float(value)
            except ValueError:
                return default
        return default
    
    @classmethod
    def _to_int(cls, value, default=0):
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                value = value.strip()
                if not value:
                    return default
                return int(float(value))
            except ValueError:
                return default
        return default
    
    @classmethod
    def _sanitize_basic_stats(cls, status: Dict) -> Dict:
        """确保统计数据为合法数值"""
        if not isinstance(status, dict):
            return {
                'total_pages': 0,
                'successful_pages': 0,
                'failed_pages': 0
            }
        
        total_pages = cls._to_int(status.get('total_pages'), 0)
        successful_pages = cls._to_int(status.get('successful_pages'), 0)
        failed_pages = cls._to_int(status.get('failed_pages'), 0)
        
        if total_pages <= 0 and (successful_pages > 0 or failed_pages > 0):
            total_pages = successful_pages + failed_pages
        
        status['total_pages'] = max(total_pages, 0)
        status['successful_pages'] = max(successful_pages, 0)
        status['failed_pages'] = max(failed_pages, 0)
        
        progress = status.get('progress')
        if isinstance(progress, dict):
            progress_total = cls._to_int(progress.get('total_pages'), 0)
            progress_completed = cls._to_int(progress.get('completed_urls_count'), 0)
            progress_failed = cls._to_int(progress.get('failed_urls_count'), 0)
            progress['total_pages'] = max(progress_total, 0)
            progress['completed_urls_count'] = max(progress_completed, 0)
            progress['failed_urls_count'] = max(progress_failed, 0)
            status['progress'] = progress
        
        return status
    
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
        try:
            if self.is_closing:
                return
            if not self.crawler:
                logger.warning("爬虫实例为空，无法启动监控")
                return
            if self.status_thread and self.status_thread.isRunning():
                return
            self.status_thread = StatusUpdateThread(self.crawler, self)
            self.status_thread.status_signal.connect(self.on_status_update)
            self.status_thread.error_signal.connect(self.on_status_error)
            self.status_thread.start()
        except Exception as e:
            logger.error(f"启动监控失败: {e}", exc_info=True)
            # 即使启动失败也不抛出异常，避免崩溃
    
    def on_status_update(self, payload):
        """处理状态更新信号"""
        if self.is_closing:
            return
        
        try:
            if not self.isVisible():
                logger.debug("对话框已关闭，停止状态更新")
                self.is_closing = True
                return
        except (RuntimeError, AttributeError):
            self.is_closing = True
            return
        
        if not hasattr(self, 'total_label') or not hasattr(self, 'proxy_status'):
            logger.warning("UI组件未完全初始化，跳过状态更新")
            return
        
        if not isinstance(payload, dict):
            stats = payload if isinstance(payload, dict) else {}
            session = {}
        else:
            stats = payload.get('status') or {}
            session = payload.get('session') or {}
        
        sanitized_stats = self._sanitize_basic_stats(stats)
        if not isinstance(session, dict):
            session = {}
        
        try:
            self._apply_status_update(sanitized_stats, session)
        except Exception as e:
            logger.error(f"应用状态更新失败: {e}", exc_info=True)
            if hasattr(self, 'total_label'):
                error_msg = str(e)[:50]
                self.total_label.setText(f"状态更新失败: {error_msg}")
    
    def on_status_error(self, message: str):
        """处理状态更新错误"""
        if self.is_closing:
            return
        logger.error(f"爬虫状态监控线程错误: {message}")
        if hasattr(self, 'total_label'):
            self.total_label.setText(f"状态获取失败: {str(message)[:50]}")
    
    def get_current_spider(self):
        """供状态线程动态获取当前爬虫"""
        return self.crawler

    def _apply_status_update(self, stats: Dict, session: Optional[Dict] = None):
        """根据状态数据更新界面"""
        if not isinstance(stats, dict):
            logger.warning("状态数据格式无效，跳过更新")
            return
        
        session = session or {}
        if not isinstance(session, dict):
            session = {}
        
        # 更新代理状态
        try:
            proxy_info = self._extract_proxy_info(stats, session)
            if hasattr(self, 'proxy_status'):
                self.proxy_status.update_status(proxy_info)
        except Exception as proxy_error:
            logger.error(f"更新代理状态失败: {proxy_error}", exc_info=True)
        
        # 更新重试配置
        try:
            self._update_retry_config(stats)
        except Exception as retry_error:
            logger.error(f"更新重试配置失败: {retry_error}", exc_info=True)
        
        # 更新进度与统计
        try:
            self._update_progress_and_stats(stats)
        except Exception as progress_error:
            logger.error(f"更新进度和统计信息失败: {progress_error}", exc_info=True)
    
    def _extract_proxy_info(self, stats, session):
        """提取代理信息"""
        if not isinstance(stats, dict):
            logger.warning(f"stats不是字典类型: {type(stats)}")
            return None
        
        if not isinstance(session, dict):
            session = {}
        
        try:
            # 首先检查stats中是否有proxy_status
            if 'proxy_status' in stats:
                proxy_status = stats.get('proxy_status', {})
                if not isinstance(proxy_status, dict):
                    proxy_status = {}
                
                proxy_enabled = proxy_status.get('enabled', False)
                proxy_enabled = bool(proxy_enabled)

                if proxy_enabled:
                    current_proxy_info = proxy_status.get('current_proxy')
                    if current_proxy_info:
                        # 处理不同的current_proxy格式
                        if isinstance(current_proxy_info, dict):
                            ip = current_proxy_info.get('ip', '')
                            port = current_proxy_info.get('port', '')
                            if ip and port:
                                return {
                                    'enabled': True,
                                    'current_proxy': f"{ip}:{port}",
                                    'score': self._to_float(current_proxy_info.get('success_rate'), 0.0) * 100,  # 转换为百分比
                                    'response_time': self._to_float(current_proxy_info.get('response_time'), None),
                                    'usage_count': self._to_int(current_proxy_info.get('use_count'), 0),
                                    'retry_count': self._to_int(current_proxy_info.get('consecutive_failures'), 0)
                                }
                        elif isinstance(current_proxy_info, str):
                            # 如果是字符串格式 ip:port
                            return {
                                'enabled': True,
                                'current_proxy': current_proxy_info,
                                'score': 0,
                                'response_time': None,
                                'usage_count': 0,
                                'retry_count': 0
                            }
                    
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
            proxy_enabled = bool(stats.get('proxy_enabled', False))
            
            if not proxy_enabled:
                return None
            
            # 获取当前代理信息
            current_proxy = session.get('current_proxy') if isinstance(session, dict) else None
            proxy_stats = stats.get('proxy_stats', {})
            if not isinstance(proxy_stats, dict):
                proxy_stats = {}
            
            proxy_details = proxy_stats.get('proxy_details', [])
            if not isinstance(proxy_details, list):
                proxy_details = []
            
            # 查找当前代理的详细信息
            current_proxy_detail = None
            if current_proxy and proxy_details:
                try:
                    current_proxy_ip = str(current_proxy).split(':')[0]
                    for detail in proxy_details:
                        if isinstance(detail, dict) and detail.get('ip') == current_proxy_ip:
                            current_proxy_detail = detail
                            break
                except Exception:
                    pass
            
            return {
                'enabled': True,
                'current_proxy': current_proxy or "等待获取",
                'score': self._to_float(current_proxy_detail.get('score')) if current_proxy_detail else 0.0,
                'response_time': self._to_float(current_proxy_detail.get('avg_response_time')) if current_proxy_detail else None,
                'usage_count': self._to_int(session.get('proxy_usage_count')) if isinstance(session, dict) else 0,
                'retry_count': self._to_int(session.get('retry_count')) if isinstance(session, dict) else 0
            }
        except Exception as e:
            logger.error(f"提取代理信息失败: {e}", exc_info=True)
            return None
    
    def _update_retry_config(self, stats):
        """更新重试配置显示"""
        try:
            if not isinstance(stats, dict):
                stats = {}
            
            retry_stats = stats.get('retry_stats', {})
            if not isinstance(retry_stats, dict):
                retry_stats = {}
            
            # 安全设置文本
            if hasattr(self, 'max_retries_label'):
                try:
                    self.max_retries_label.setText(f"最大重试次数: {retry_stats.get('max_retries', 3)}")
                except Exception:
                    pass
            
            if hasattr(self, 'retry_delay_label'):
                try:
                    retry_delay = retry_stats.get('retry_delay', 5)
                    max_retry_delay = retry_stats.get('max_retry_delay', 60)
                    self.retry_delay_label.setText(
                        f"重试延迟: {retry_delay}秒 - {max_retry_delay}秒"
                    )
                except Exception:
                    pass
            
            if hasattr(self, 'retry_codes_label'):
                try:
                    retry_codes = retry_stats.get('retry_codes', [])
                    if isinstance(retry_codes, (list, tuple)):
                        codes_str = ', '.join(map(str, retry_codes))
                    else:
                        codes_str = str(retry_codes) if retry_codes else "未知"
                    self.retry_codes_label.setText(f"重试状态码: {codes_str}")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"更新重试配置失败: {e}", exc_info=True)
            try:
                if hasattr(self, 'max_retries_label'):
                    self.max_retries_label.setText("最大重试次数: 未知")
                if hasattr(self, 'retry_delay_label'):
                    self.retry_delay_label.setText("重试延迟: 未知")
                if hasattr(self, 'retry_codes_label'):
                    self.retry_codes_label.setText("重试状态码: 未知")
            except Exception:
                pass
    
    def _update_progress_and_stats(self, stats):
        """更新进度和统计信息"""
        try:
            # 获取基础统计信息
            total = self._to_int(stats.get('total_pages'), 0)
            successful = self._to_int(stats.get('successful_pages'), 0)
            failed = self._to_int(stats.get('failed_pages'), 0)
            
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
                progress = min(max((successful + failed) / total * 100, 0), 100)
                self.progress_bar.setValue(int(progress))
            else:
                self.progress_bar.setValue(0)
            
            # 显示多线程特定信息
            if 'multithread_info' in stats:
                try:
                    multithread_info = stats.get('multithread_info', {})
                    if not isinstance(multithread_info, dict):
                        multithread_info = {}
                    
                    active_threads = self._to_int(multithread_info.get('active_threads'), 0)
                    total_crawled = self._to_int(multithread_info.get('total_crawled'), 0)
                    total_saved = self._to_int(multithread_info.get('total_saved'), 0)
                    elapsed_time = self._to_float(multithread_info.get('elapsed_time'), 0.0)
                    
                    # 更新多线程信息显示（安全地）
                    if hasattr(self, 'multithread_label'):
                        try:
                            self.multithread_label.setText(f"活跃线程: {active_threads}")
                        except Exception:
                            pass
                    if hasattr(self, 'crawled_label'):
                        try:
                            self.crawled_label.setText(f"已爬取: {total_crawled}")
                        except Exception:
                            pass
                    if hasattr(self, 'saved_label'):
                        try:
                            self.saved_label.setText(f"已保存: {total_saved}")
                        except Exception:
                            pass
                    if hasattr(self, 'elapsed_label'):
                        try:
                            self.elapsed_label.setText(f"耗时: {elapsed_time:.1f}秒")
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"更新多线程信息失败: {e}", exc_info=True)
            
            # 显示爬虫级别和模式信息
            try:
                if 'level' in stats:
                    level = stats.get('level', '未知')
                    speed_mode = stats.get('speed_mode', '正常速度')
                    if hasattr(self, 'level_label'):
                        try:
                            self.level_label.setText(f"爬虫级别: {level}")
                        except Exception:
                            pass
                    if hasattr(self, 'mode_label'):
                        try:
                            self.mode_label.setText(f"速度模式: {speed_mode}")
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"更新爬虫级别和模式信息失败: {e}", exc_info=True)
            
        except Exception as e:
            logger.error(f"更新进度和统计信息失败: {e}", exc_info=True)
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
                logger.error(f"停止爬虫失败: {e}", exc_info=True)
            self.close()
    
    def closeEvent(self, event):
        """关闭事件"""
        # 标记正在关闭，停止所有更新
        self.is_closing = True
        
        try:
            if self.status_thread:
                self.status_thread.stop()
                self.status_thread.wait(1500)
                self.status_thread = None
        except Exception as e:
            logger.debug(f"停止状态线程失败: {e}")
        
        try:
            # 清空爬虫引用，避免后续访问
            self.crawler = None
        except Exception:
            pass
        
        try:
            super().closeEvent(event)
        except Exception as e:
            logger.debug(f"关闭对话框时出现异常: {e}") 