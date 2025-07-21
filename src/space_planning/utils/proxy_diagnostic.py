#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理诊断工具
用于检查和诊断代理配置和状态
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, Any


def check_proxy_config() -> Dict[str, Any]:
    """检查代理配置"""
    config_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'gui', 'proxy_config.json'
    )
    
    result = {
        'config_file_exists': os.path.exists(config_file),
        'config_file_path': config_file,
        'config_content': None,
        'config_valid': False
    }
    
    if result['config_file_exists']:
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                result['config_content'] = config
                result['config_valid'] = bool(
                    config.get('enabled', False) and 
                    config.get('secret_id') and 
                    config.get('secret_key')
                )
        except Exception as e:
            result['error'] = str(e)
    
    return result


def check_proxy_state() -> Dict[str, Any]:
    """检查代理状态"""
    state_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'spider', 'persistent_proxy_state.json'
    )
    
    result = {
        'state_file_exists': os.path.exists(state_file),
        'state_file_path': state_file,
        'state_content': None,
        'state_valid': False
    }
    
    if result['state_file_exists']:
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                result['state_content'] = state
                result['state_valid'] = bool(
                    state.get('current_proxy') and 
                    state['current_proxy'].get('is_active', False)
                )
        except Exception as e:
            result['error'] = str(e)
    else:
        result['error'] = "状态文件不存在，可能是代理管理器尚未初始化或未成功获取过代理"
    
    return result


def run_diagnostic() -> Dict[str, Any]:
    """运行完整诊断"""
    print("=== 代理诊断报告 ===")
    print(f"诊断时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 检查配置
    config_result = check_proxy_config()
    print("1. 代理配置检查:")
    print(f"   配置文件存在: {config_result['config_file_exists']}")
    if config_result['config_file_exists']:
        print(f"   配置有效: {config_result['config_valid']}")
        if config_result['config_content']:
            config = config_result['config_content']
            print(f"   代理启用: {config.get('enabled', False)}")
            print(f"   订单号: {config.get('secret_id', '未设置')}")
            print(f"   密钥: {'已设置' if config.get('secret_key') else '未设置'}")
    else:
        print("   错误: 配置文件不存在")
    print()
    
    # 检查状态
    state_result = check_proxy_state()
    print("2. 代理状态检查:")
    print(f"   状态文件存在: {state_result['state_file_exists']}")
    if state_result['state_file_exists']:
        print(f"   状态有效: {state_result['state_valid']}")
        if state_result['state_content']:
            state = state_result['state_content']
            current_proxy = state.get('current_proxy', {})
            if current_proxy:
                print(f"   当前代理: {current_proxy.get('ip', 'N/A')}:{current_proxy.get('port', 'N/A')}")
                print(f"   代理类型: {current_proxy.get('proxy_type', 'N/A')}")
                print(f"   是否活跃: {current_proxy.get('is_active', False)}")
                print(f"   使用次数: {current_proxy.get('use_count', 0)}")
                print(f"   成功率: {current_proxy.get('success_rate', 0):.2%}")
                print(f"   连续失败: {current_proxy.get('consecutive_failures', 0)}")
    else:
        print("   错误: 状态文件不存在")
    print()
    
    # 总结
    print("3. 诊断总结:")
    if config_result['config_valid'] and state_result['state_valid']:
        print("   ✅ 代理配置正常，状态良好")
        return {'status': 'healthy', 'issues': []}
    else:
        issues = []
        if not config_result['config_valid']:
            issues.append("代理配置无效或未启用")
        if not state_result['state_valid']:
            issues.append("代理状态文件无效或代理不活跃")
        
        print("   ❌ 发现以下问题:")
        for issue in issues:
            print(f"      - {issue}")
        
        return {'status': 'unhealthy', 'issues': issues}


if __name__ == "__main__":
    run_diagnostic() 