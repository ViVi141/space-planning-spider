#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
表格显示配置模块
根据不同爬虫的数据结构配置表格显示策略
"""

from PyQt5.QtWidgets import QHeaderView
from typing import Dict, List, Tuple


class TableDisplayConfig:
    """表格显示配置管理器"""
    
    # 各爬虫的数据字段定义（基于实际代码分析）
    SPIDER_DATA_STRUCTURES = {
        '住房和城乡建设部': {
            'fields': ['level', 'title', 'pub_date', 'doc_number', 'source', 'content', 'crawl_time'],
            'has_category': False,  # NationalSpider 返回的数据中没有 category 字段
            'has_doc_number': True,
            'typical_title_length': 50,  # 住建部标题通常较短
            'typical_source_length': 70,  # URL格式: http://www.mohurd.gov.cn/...
            'title_max_length': 100,
            'source_max_length': 120,
        },
        '广东省人民政府': {
            'fields': ['level', 'title', 'url', 'pub_date', 'doc_number', 'source', 'content', 'category', 'crawl_time'],
            'has_category': True,  # GuangdongSpider 返回的数据中有 category 字段
            'has_doc_number': True,
            'typical_title_length': 70,  # 广东省标题通常较长，包含更多描述
            'typical_source_length': 110,  # URL通常包含更多路径
            'title_max_length': 120,
            'source_max_length': 150,
            'category_max_length': 25,  # 分类名称如"省级地方性法规"等
        },
        '自然资源部': {
            'fields': ['level', 'title', 'pub_date', 'doc_number', 'source', 'content', 'category', 'validity', 'effective_date', 'link', 'crawl_time'],
            'has_category': True,  # MNRSpider 返回的数据中有 category 字段
            'has_doc_number': True,
            'typical_title_length': 65,
            'typical_source_length': 95,  # URL格式: http://www.mnr.gov.cn/...
            'title_max_length': 110,
            'source_max_length': 130,
            'category_max_length': 20,  # 分类名称通常较短
        }
    }
    
    @classmethod
    def get_column_config(cls, spider_level: str) -> Dict[str, Dict]:
        """
        根据爬虫级别获取列宽配置
        
        Args:
            spider_level: 爬虫级别（'住房和城乡建设部', '广东省人民政府', '自然资源部'）
            
        Returns:
            列配置字典，包含列索引、宽度、调整模式等信息
        """
        config = {
            # 机构列（索引0）
            0: {
                'width': 150,
                'mode': QHeaderView.Fixed,
                'label': '机构'
            },
            # 标题列（索引1）
            1: {
                'width': None,  # 使用Stretch模式
                'mode': QHeaderView.Stretch,
                'label': '标题'
            },
            # 发布日期列（索引2）
            2: {
                'width': 120,
                'mode': QHeaderView.Fixed,
                'label': '发布日期'
            },
            # 来源列（索引3）
            3: {
                'width': 200,
                'mode': QHeaderView.Fixed,
                'label': '来源'
            },
            # 政策类型列（索引4）
            4: {
                'width': 150,
                'mode': QHeaderView.Fixed,
                'label': '政策类型'
            },
            # 操作列（索引5）
            5: {
                'width': 100,
                'mode': QHeaderView.Fixed,
                'label': '操作'
            }
        }
        
        # 根据爬虫类型调整配置（基于实际数据特征）
        if spider_level in cls.SPIDER_DATA_STRUCTURES:
            spider_info = cls.SPIDER_DATA_STRUCTURES[spider_level]
            
            # 根据实际URL长度调整来源列宽度
            source_max = spider_info.get('source_max_length', 100)
            if source_max > 120:
                config[3]['width'] = 260  # 非常长的URL（如广东省）
            elif source_max > 100:
                config[3]['width'] = 240  # 较长的URL
            elif source_max > 80:
                config[3]['width'] = 220  # 中等长度URL（如自然资源部）
            else:
                config[3]['width'] = 200  # 较短URL（如住建部）
            
            # 根据是否有分类信息调整政策类型列宽度
            if spider_info['has_category']:
                category_max = spider_info.get('category_max_length', 20)
                if category_max > 30:
                    config[4]['width'] = 200  # 非常长的分类名
                elif category_max > 20:
                    config[4]['width'] = 180  # 较长的分类名（如广东省）
                else:
                    config[4]['width'] = 160  # 中等分类名（如自然资源部）
            else:
                config[4]['width'] = 120  # 没有分类时使用智能分类，通常较短
        
        return config
    
    @classmethod
    def get_optimal_column_widths(cls, spider_level: str) -> List[Tuple[int, int]]:
        """
        获取最优列宽配置列表
        
        Args:
            spider_level: 爬虫级别
            
        Returns:
            [(列索引, 宽度), ...] 列表
        """
        config = cls.get_column_config(spider_level)
        widths = []
        for col_idx, col_info in sorted(config.items()):
            if col_info['width'] is not None:
                widths.append((col_idx, col_info['width']))
        return widths
    
    @classmethod
    def apply_table_config(cls, table, spider_level: str):
        """
        应用表格配置到指定的表格控件
        
        Args:
            table: QTableWidget实例
            spider_level: 爬虫级别
        """
        config = cls.get_column_config(spider_level)
        header = table.horizontalHeader()
        
        if header is not None:
            header.setStretchLastSection(False)
            
            # 应用每列的配置
            for col_idx, col_info in sorted(config.items()):
                if col_idx < table.columnCount():
                    header.setSectionResizeMode(col_idx, col_info['mode'])
                    if col_info['width'] is not None:
                        table.setColumnWidth(col_idx, col_info['width'])

