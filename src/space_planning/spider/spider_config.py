#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫配置模块
集中管理所有爬虫的配置信息，避免硬编码
"""

from typing import Dict, Any


class SpiderConfig:
    """爬虫配置管理器"""
    
    # ========== 国家住建部爬虫配置 ==========
    NATIONAL_SPIDER = {
        'name': '住房和城乡建设部',
        'level': '住房和城乡建设部',
        'api_url': 'https://www.mohurd.gov.cn/api-gateway/jpaas-publish-server/front/page/build/unit',
        'base_url': 'https://www.mohurd.gov.cn',
        'base_params': {
            'webId': '86ca573ec4df405db627fdc2493677f3',
            'pageId': 'vhiC3JxmPC8o7Lqg4Jw0E',
            'parseType': 'bulidstatic',
            'pageType': 'column',
            'tagId': '内容1',
            'tplSetId': 'fc259c381af3496d85e61997ea7771cb',
            'unitUrl': '/api-gateway/jpaas-publish-server/front/page/build/unit'
        },
        'headers': {
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Referer': 'https://www.mohurd.gov.cn/gongkai/zc/wjk/index.html',
            'Origin': 'https://www.mohurd.gov.cn',
        },
        'default_speed_mode': '正常速度',
    }
    
    # ========== 自然资源部爬虫配置 ==========
    MNR_SPIDER = {
        'name': '自然资源部',
        'level': '自然资源部',
        'base_url': 'https://gi.mnr.gov.cn/',
        'search_api': 'https://search.mnr.gov.cn/was5/web/search',
        'ajax_api': 'https://search.mnr.gov.cn/was/ajaxdata_jsonp.jsp',
        'channel_id': '216640',  # 政府信息公开平台的频道ID
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://gi.mnr.gov.cn/',
            'X-Requested-With': 'XMLHttpRequest'
        },
        'default_speed_mode': '正常速度',
        'max_pages': 999999,  # 最大翻页数（无上限）
    }
    
    # ========== 广东省爬虫配置 ==========
    GUANGDONG_SPIDER = {
        'name': '广东省人民政府',
        'level': '广东省人民政府',
        'base_url': 'https://gd.pkulaw.com',
        'search_url': 'https://gd.pkulaw.com/china/search/RecordSearch',
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://gd.pkulaw.com',
            'Referer': 'https://gd.pkulaw.com/china/adv'
        },
        'default_speed_mode': '正常速度',
        'category_config': {
            "省级地方性法规": {"code": "XM0701", "expected_count": 859},
            "设区的市地方性法规": {"code": "XM0702", "expected_count": 816},
            "经济特区法规": {"code": "XM0703", "expected_count": 951},
            "自治条例和单行条例": {"code": "XU13", "expected_count": 37},
            "省级地方政府规章": {"code": "XO0802", "expected_count": 764},
            "设区的市地方政府规章": {"code": "XO0803", "expected_count": 2077},
            "地方规范性文件": {"code": "XP08", "expected_count": 40231},
        }
    }
    
    # ========== 通用爬虫配置 ==========
    COMMON_CONFIG = {
        'max_retries': 3,  # 最大重试次数
        'retry_delay': 2,  # 重试延迟（秒）
        'request_timeout': 30,  # 请求超时时间（秒）
        'min_delay': 0.5,  # 最小延迟（秒）
        'max_delay': 2.0,  # 最大延迟（秒）
        'max_empty_pages': 3,  # 最大连续空页数
        'max_consecutive_out_of_range': 5,  # 最大连续超出范围页数
        'page_size': 20,  # 默认每页数量
    }
    
    @classmethod
    def get_national_config(cls) -> Dict[str, Any]:
        """获取国家住建部爬虫配置"""
        return cls.NATIONAL_SPIDER.copy()
    
    @classmethod
    def get_mnr_config(cls) -> Dict[str, Any]:
        """获取自然资源部爬虫配置"""
        return cls.MNR_SPIDER.copy()
    
    @classmethod
    def get_guangdong_config(cls) -> Dict[str, Any]:
        """获取广东省爬虫配置"""
        return cls.GUANGDONG_SPIDER.copy()
    
    @classmethod
    def get_common_config(cls) -> Dict[str, Any]:
        """获取通用爬虫配置"""
        return cls.COMMON_CONFIG.copy()
    
    @classmethod
    def get_config_by_level(cls, level: str) -> Dict[str, Any]:
        """根据机构级别获取配置"""
        configs = {
            '住房和城乡建设部': cls.NATIONAL_SPIDER,
            '自然资源部': cls.MNR_SPIDER,
            '广东省人民政府': cls.GUANGDONG_SPIDER,
        }
        return configs.get(level, cls.COMMON_CONFIG).copy()

