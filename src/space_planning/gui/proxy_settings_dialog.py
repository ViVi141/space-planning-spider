#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理设置对话框
允许用户配置快代理私密代理参数
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                           QPushButton, QCheckBox, QSpinBox, QGroupBox, QTextEdit,
                           QMessageBox, QTabWidget, QWidget, QFormLayout, QComboBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import json
import os
from datetime import datetime
from kdl.auth import Auth
from kdl.client import Client

from space_planning.spider.proxy_pool import ProxyPool, initialize_proxy_pool, get_proxy_stats


class ProxyTestThread(QThread):
    """代理测试线程"""
    test_result = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    
    def __init__(self, proxy_config):
        super().__init__()
        self.proxy_config = proxy_config
    
    def run(self):
        try:
            self.progress.emit("正在测试代理连接...")
            
            # 创建临时客户端进行测试
            auth = Auth(
                self.proxy_config.get('secret_id', ''),
                self.proxy_config.get('secret_key', '')
            )
            client = Client(auth)
            
            # 尝试获取代理
            try:
                # 如果配置了隧道用户名和密码，使用隧道代理
                username = self.proxy_config.get('username', '').strip()
                password = self.proxy_config.get('password', '').strip()
                
                self.progress.emit("正在获取代理...")
                if username and password:
                    # 使用隧道代理
                    proxies = client.get_tps(num=1, username=username, password=password)
                    self.progress.emit(f"获取到隧道代理数据: {proxies}")
                else:
                    # 使用API代理
                    proxies = client.get_dps(num=1)
                    self.progress.emit(f"获取到API代理数据: {proxies}")
                
                # 确保proxies是列表或可迭代对象
                if not proxies:
                    self.test_result.emit(False, "无法获取代理，请检查配置是否正确")
                    return
                
                # 如果proxies是字符串，说明API返回了单个代理字符串
                if isinstance(proxies, str):
                    proxy = proxies
                    self.progress.emit(f"解析代理数据: {proxy} (类型: {type(proxy)})")
                    
                    if ':' in proxy:
                        ip, port = proxy.split(':', 1)
                        self.test_result.emit(True, f"代理测试成功！获取到代理: {ip}:{port}")
                    else:
                        self.test_result.emit(True, f"代理测试成功！获取到代理: {proxy}")
                    return
                
                # 如果proxies是列表，取第一个元素
                if isinstance(proxies, (list, tuple)) and len(proxies) > 0:
                    proxy = proxies[0]
                    self.progress.emit(f"解析代理数据: {proxy} (类型: {type(proxy)})")
                    
                    if isinstance(proxy, dict):
                        # API代理返回字典格式
                        if 'ip' in proxy and 'port' in proxy:
                            self.test_result.emit(True, f"代理测试成功！获取到代理: {proxy['ip']}:{proxy['port']}")
                        else:
                            self.test_result.emit(False, f"代理数据格式错误: {proxy}")
                    elif isinstance(proxy, str):
                        # 隧道代理返回字符串格式
                        if ':' in proxy:
                            ip, port = proxy.split(':', 1)
                            self.test_result.emit(True, f"代理测试成功！获取到代理: {ip}:{port}")
                        else:
                            # 如果不是 ip:port 格式，直接显示
                            self.test_result.emit(True, f"代理测试成功！获取到代理: {proxy}")
                    else:
                        self.test_result.emit(False, f"不支持的代理数据类型: {type(proxy)}")
                else:
                    self.test_result.emit(False, "无法获取代理，请检查配置是否正确")
            except Exception as e:
                self.test_result.emit(False, f"获取代理失败: {str(e)}")
                
        except Exception as e:
            self.test_result.emit(False, f"测试过程中出错: {str(e)}")


class ProxySettingsDialog(QDialog):
    """代理设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("快代理设置")
        self.setModal(True)
        self.resize(600, 500)
        
        # 加载配置
        self.config_file = os.path.join(
            os.path.dirname(__file__), 'proxy_config.json'
        )
        self.proxy_config = self.load_config()
        
        self.init_ui()
    
    def load_config(self):
        """加载代理配置"""
        default_config = {
            'enabled': False,
            'secret_id': '',  # 快代理订单号
            'secret_key': '', # 快代理密钥
            'username': '',   # 代理隧道用户名（可选）
            'password': '',   # 代理隧道密码（可选）
            'max_proxies': 5,
            'check_interval': 1800  # 30分钟，减少刷新频率
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并配置，保留默认值
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                print(f"加载代理配置失败: {e}")
        
        return default_config
    
    def save_config(self):
        """保存代理配置"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.proxy_config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存配置失败: {e}")
            return False
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 基本设置选项卡
        basic_tab = self.create_basic_tab()
        tab_widget.addTab(basic_tab, "基本设置")
        
        # 高级设置选项卡
        advanced_tab = self.create_advanced_tab()
        tab_widget.addTab(advanced_tab, "高级设置")
        
        # 测试选项卡
        test_tab = self.create_test_tab()
        tab_widget.addTab(test_tab, "代理测试")
        
        # 统计信息选项卡
        stats_tab = self.create_stats_tab()
        tab_widget.addTab(stats_tab, "统计信息")
        
        layout.addWidget(tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.test_button = QPushButton("测试代理")
        self.test_button.clicked.connect(self.test_proxy)
        
        self.save_button = QPushButton("保存设置")
        self.save_button.clicked.connect(self.save_settings)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.test_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def create_basic_tab(self):
        """创建基本设置选项卡"""
        widget = QWidget()
        layout = QFormLayout()
        
        # 启用代理
        self.enable_proxy = QCheckBox("启用快代理")
        self.enable_proxy.setChecked(self.proxy_config.get('enabled', False))
        layout.addRow("代理状态:", self.enable_proxy)
        
        # 创建分组框：API配置
        api_group = QGroupBox("API配置")
        api_layout = QFormLayout()
        
        self.secret_id_edit = QLineEdit()
        self.secret_id_edit.setText(self.proxy_config.get('secret_id', ''))
        self.secret_id_edit.setPlaceholderText("请输入快代理订单号")
        api_layout.addRow("订单号:", self.secret_id_edit)
        
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setText(self.proxy_config.get('secret_key', ''))
        self.secret_key_edit.setPlaceholderText("请输入快代理密钥")
        api_layout.addRow("密钥:", self.secret_key_edit)
        
        api_group.setLayout(api_layout)
        layout.addRow(api_group)
        
        # 创建分组框：隧道配置（可选）
        tunnel_group = QGroupBox("隧道配置（可选）")
        tunnel_layout = QFormLayout()
        
        self.username_edit = QLineEdit()
        self.username_edit.setText(self.proxy_config.get('username', ''))
        self.username_edit.setPlaceholderText("代理隧道用户名")
        tunnel_layout.addRow("用户名:", self.username_edit)
        
        self.password_edit = QLineEdit()
        self.password_edit.setText(self.proxy_config.get('password', ''))
        self.password_edit.setPlaceholderText("代理隧道密码")
        self.password_edit.setEchoMode(QLineEdit.Password)
        tunnel_layout.addRow("密码:", self.password_edit)
        
        tunnel_group.setLayout(tunnel_layout)
        layout.addRow(tunnel_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_advanced_tab(self):
        """创建高级设置选项卡"""
        widget = QWidget()
        layout = QFormLayout()
        
        # 创建分组框：代理池设置
        pool_group = QGroupBox("代理池设置")
        pool_layout = QFormLayout()
        
        self.max_proxies_spin = QSpinBox()
        self.max_proxies_spin.setRange(1, 100)
        self.max_proxies_spin.setValue(self.proxy_config.get('max_proxies', 5))
        pool_layout.addRow("最大代理数量:", self.max_proxies_spin)
        
        self.check_interval_spin = QSpinBox()
        self.check_interval_spin.setRange(60, 3600)
        self.check_interval_spin.setValue(self.proxy_config.get('check_interval', 300))
        self.check_interval_spin.setSuffix(" 秒")
        pool_layout.addRow("检查间隔:", self.check_interval_spin)
        
        pool_group.setLayout(pool_layout)
        layout.addRow(pool_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_test_tab(self):
        """创建测试选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 测试说明
        info_label = QLabel(
            "点击下方按钮测试代理连接。测试将使用当前配置尝试获取一个代理。\n"
            "请确保已正确填写订单号和密钥。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 测试按钮
        self.test_proxy_button = QPushButton("开始测试")
        self.test_proxy_button.clicked.connect(self.test_proxy)
        layout.addWidget(self.test_proxy_button)
        
        # 测试结果显示
        self.test_result_text = QTextEdit()
        self.test_result_text.setReadOnly(True)
        self.test_result_text.setMaximumHeight(200)
        layout.addWidget(QLabel("测试结果:"))
        layout.addWidget(self.test_result_text)
        
        widget.setLayout(layout)
        return widget
    
    def create_stats_tab(self):
        """创建统计信息选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 统计信息显示
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        
        # 刷新按钮
        refresh_button = QPushButton("刷新统计信息")
        refresh_button.clicked.connect(self.refresh_stats)
        
        layout.addWidget(refresh_button)
        layout.addWidget(self.stats_text)
        
        # 初始刷新
        self.refresh_stats()
        
        widget.setLayout(layout)
        return widget
    
    def test_proxy(self):
        """测试代理连接"""
        config = self.get_config()
        
        if not config['secret_id'] or not config['secret_key']:
            QMessageBox.warning(self, "配置错误", "订单号和密钥为必填项")
            return
        
        # 禁用测试按钮
        self.test_button.setEnabled(False)
        self.test_proxy_button.setEnabled(False)
        self.test_result_text.clear()
        
        # 创建并启动测试线程
        self.test_thread = ProxyTestThread(config)
        self.test_thread.progress.connect(self.on_test_progress)
        self.test_thread.test_result.connect(self.on_test_result)
        self.test_thread.finished.connect(self.on_test_finished)
        self.test_thread.start()
    
    def on_test_progress(self, message):
        """测试进度更新"""
        self.test_result_text.append(message)
    
    def on_test_result(self, success, message):
        """测试结果处理"""
        if success:
            self.test_result_text.append(f"✅ {message}")
        else:
            self.test_result_text.append(f"❌ {message}")
    
    def on_test_finished(self):
        """测试完成处理"""
        self.test_button.setEnabled(True)
        self.test_proxy_button.setEnabled(True)
    
    def refresh_stats(self):
        """刷新统计信息"""
        stats = get_proxy_stats()
        
        # 格式化统计信息
        stats_text = f"""代理池状态:
- 运行状态: {'运行中' if stats['running'] else '已停止'}
- 当前代理数量: {stats['total_proxies']}
- 检查间隔: {stats['check_interval']}秒
- 最后刷新时间: {stats['last_refresh']}
"""
        
        self.stats_text.setText(stats_text)
    
    def save_settings(self):
        """保存设置"""
        config = self.get_config()
        
        # 验证必填字段
        if not config['secret_id'] or not config['secret_key']:
            QMessageBox.warning(self, "配置错误", "订单号和密钥为必填项")
            return
        
        # 保存配置
        self.proxy_config = config
        if self.save_config():
            # 初始化代理池
            initialize_proxy_pool(self.config_file)
            QMessageBox.information(self, "保存成功", "代理设置已保存并生效")
            self.accept()
    
    def get_config(self):
        """获取当前配置"""
        return {
            'enabled': self.enable_proxy.isChecked(),
            'secret_id': self.secret_id_edit.text().strip(),
            'secret_key': self.secret_key_edit.text().strip(),
            'username': self.username_edit.text().strip(),
            'password': self.password_edit.text().strip(),
            'max_proxies': self.max_proxies_spin.value(),
            'check_interval': self.check_interval_spin.value()
        } 