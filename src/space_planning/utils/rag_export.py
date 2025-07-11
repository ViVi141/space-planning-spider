#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG知识库优化导出模块
专门针对MaxKB知识库的智能分段功能
"""

import re
import os
import json
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime

# 设置日志
logger = logging.getLogger(__name__)

class RAGSegmenter:
    """RAG智能分段器"""
    
    def __init__(self, max_chunk_size: int = 4096):
        self.max_chunk_size = max_chunk_size
        
        # 定义分段标识的正则表达式
        self.segment_patterns = {
            # 章标题：第一章 RAG与大模型应用
            'chapter': r'[第][一二三四五六七八九十]+[章]',
            # 节标题：第一节 大模型应用的方向：RAG
            'section': r'[第][一二三四五六七八九十]+[节]',
            # 数字标题：一、 RAG与大模型应用 或 1.1 大模型应用的方向：RAG
            'numbered': r'[一二三四五六七八九十|1-9]+[、|\.][1-9]*[\.]*[1-9]*',
            # 条目：第一条：本公司员工均应遵守以下规定
            'article': r'[第][一二三四五六七八九十]+[条]',
            # Markdown标题：## 标题
            'markdown_h1': r'^#\s+',
            'markdown_h2': r'^##\s+',
            'markdown_h3': r'^###\s+',
            'markdown_h4': r'^####\s+',
            'markdown_h5': r'^#####\s+',
            'markdown_h6': r'^######\s+',
            # 政策文件常见标题模式
            'policy_chapter': r'第[一二三四五六七八九十]+章',
            'policy_section': r'第[一二三四五六七八九十]+节',
            'policy_article': r'第[一二三四五六七八九十]+条',
            'policy_item': r'[一二三四五六七八九十]+[、\.]',
        }
        
        # 合并所有分段标识的正则表达式
        self.all_patterns = '|'.join([
            f'({pattern})' for pattern in self.segment_patterns.values()
        ])
    
    def segment_markdown(self, content: str) -> List[Dict]:
        """
        MarkDown类型文件智能分段
        根据标题逐级下钻式分段（最多支持6级标题），每个段落最多4096个字符
        """
        segments = []
        lines = content.split('\n')
        current_segment = []
        current_title = ""
        current_level = 0
        
        for line in lines:
            # 检测标题级别
            title_level = self._detect_title_level(line)
            
            if title_level > 0:
                # 保存当前段落
                if current_segment:
                    segment_text = '\n'.join(current_segment)
                    if len(segment_text) > self.max_chunk_size:
                        # 分段过长，按字符数分段
                        sub_segments = self._split_by_size(segment_text, current_title, current_level)
                        segments.extend(sub_segments)
                    else:
                        segments.append({
                            'title': current_title,
                            'level': current_level,
                            'content': segment_text,
                            'size': len(segment_text)
                        })
                
                # 开始新段落
                current_segment = [line]
                current_title = line.strip()
                current_level = title_level
            else:
                current_segment.append(line)
        
        # 处理最后一个段落
        if current_segment:
            segment_text = '\n'.join(current_segment)
            if len(segment_text) > self.max_chunk_size:
                sub_segments = self._split_by_size(segment_text, current_title, current_level)
                segments.extend(sub_segments)
            else:
                segments.append({
                    'title': current_title,
                    'level': current_level,
                    'content': segment_text,
                    'size': len(segment_text)
                })
        
        return segments
    
    def segment_html_docx(self, content: str) -> List[Dict]:
        """
        HTML、DOCX类型智能分段
        识别标题格式转换成markdown的标题样式，逐级下钻进行分段
        """
        # 将HTML/DOCX内容转换为Markdown格式
        markdown_content = self._convert_to_markdown(content)
        return self.segment_markdown(markdown_content)
    
    def segment_txt_pdf(self, content: str) -> List[Dict]:
        """
        TXT和PDF类型文件智能分段
        按照标题#进行分段，若没有#标题的则按照字符数4096个字符进行分段
        """
        # 检查是否有标题标识
        if re.search(r'#\s+', content):
            return self.segment_markdown(content)
        else:
            # 没有标题，按字符数分段
            return self._split_by_size(content, "无标题", 0)
    
    def _detect_title_level(self, line: str) -> int:
        """检测标题级别"""
        line = line.strip()
        
        # Markdown标题检测
        match = re.match(r'^#{1,6}\s+', line)
        if match:
            title_match = re.match(r'^(#+)\s+', line)
            if title_match:
                return len(title_match.group(1))
        
        # 其他标题模式检测
        for pattern_name, pattern in self.segment_patterns.items():
            if re.search(pattern, line):
                # 根据模式类型返回不同级别
                if 'chapter' in pattern_name or 'h1' in pattern_name:
                    return 1
                elif 'section' in pattern_name or 'h2' in pattern_name:
                    return 2
                elif 'article' in pattern_name or 'h3' in pattern_name:
                    return 3
                elif 'h4' in pattern_name:
                    return 4
                elif 'h5' in pattern_name:
                    return 5
                elif 'h6' in pattern_name:
                    return 6
                else:
                    return 1
        
        return 0
    
    def _split_by_size(self, content: str, title: str, level: int) -> List[Dict]:
        """按字符数分段"""
        segments = []
        remaining_content = content
        
        while len(remaining_content) > self.max_chunk_size:
            # 在max_chunk_size范围内查找最后一个换行符
            chunk = remaining_content[:self.max_chunk_size]
            last_newline = chunk.rfind('\n')
            
            if last_newline > 0:
                # 在换行符处分割
                segment_content = remaining_content[:last_newline]
                remaining_content = remaining_content[last_newline + 1:]
            else:
                # 没有找到换行符，强制分割
                segment_content = remaining_content[:self.max_chunk_size]
                remaining_content = remaining_content[self.max_chunk_size:]
            
            segments.append({
                'title': title,
                'level': level,
                'content': segment_content,
                'size': len(segment_content)
            })
        
        # 添加剩余内容
        if remaining_content:
            segments.append({
                'title': title,
                'level': level,
                'content': remaining_content,
                'size': len(remaining_content)
            })
        
        return segments
    
    def _convert_to_markdown(self, content: str) -> str:
        """将HTML/DOCX内容转换为Markdown格式"""
        # 这里可以添加HTML/DOCX到Markdown的转换逻辑
        # 简化实现，实际项目中可能需要更复杂的转换
        return content

class RAGExporter:
    """RAG知识库优化导出器"""
    
    def __init__(self, max_chunk_size: int = 4096):
        self.segmenter = RAGSegmenter(max_chunk_size)
    
    def export_for_rag(self, data: List, output_dir: str, format_type: str = 'markdown') -> Dict:
        """
        为RAG知识库导出优化格式
        
        Args:
            data: 政策数据列表
            output_dir: 输出目录
            format_type: 输出格式 ('markdown', 'json', 'txt')
        
        Returns:
            导出结果信息
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建元数据文件
        metadata = {
            'export_time': datetime.now().isoformat(),
            'total_policies': len(data),
            'format_type': format_type,
            'max_chunk_size': self.segmenter.max_chunk_size,
            'segments': []
        }
        
        all_segments = []
        
        for i, policy in enumerate(data, 1):
            # 解析政策数据
            policy_info = self._parse_policy_data(policy)
            
            # 生成政策内容
            content = self._generate_policy_content(policy_info, i)
            
            # 根据格式类型进行分段
            if format_type == 'markdown':
                segments = self.segmenter.segment_markdown(content)
            elif format_type == 'html':
                segments = self.segmenter.segment_html_docx(content)
            else:
                segments = self.segmenter.segment_txt_pdf(content)
            
            # 为每个段落添加政策元数据
            for j, segment in enumerate(segments):
                segment['policy_id'] = i
                segment['policy_title'] = policy_info['title']
                segment['policy_date'] = policy_info['pub_date']
                segment['policy_level'] = policy_info['level']
                segment['policy_source'] = policy_info['source']
                segment['segment_id'] = f"policy_{i}_segment_{j+1}"
                all_segments.append(segment)
        
        # 导出文件
        if format_type == 'markdown':
            result = self._export_markdown_segments(all_segments, output_dir)
        elif format_type == 'json':
            result = self._export_json_segments(all_segments, output_dir)
        else:
            result = self._export_txt_segments(all_segments, output_dir)
        
        # 更新元数据
        metadata['segments'] = all_segments
        metadata['total_segments'] = len(all_segments)
        metadata['output_files'] = result['files']
        
        # 保存元数据
        metadata_file = os.path.join(output_dir, 'rag_metadata.json')
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return {
            'success': True,
            'output_dir': output_dir,
            'total_policies': len(data),
            'total_segments': len(all_segments),
            'metadata_file': metadata_file,
            'output_files': result['files']
        }
    
    def _parse_policy_data(self, policy) -> Dict:
        """解析政策数据格式"""
        if isinstance(policy, (list, tuple)):
            return {
                'id': str(policy[0]) if len(policy) > 0 else "",
                'level': str(policy[1]) if len(policy) > 1 else "未知层级",
                'title': str(policy[2]) if len(policy) > 2 else "未知标题",
                'pub_date': str(policy[3]) if len(policy) > 3 else "未知日期",
                'source': str(policy[4]) if len(policy) > 4 else "未知来源",
                'content': str(policy[5]) if len(policy) > 5 else "无内容"
            }
        elif isinstance(policy, dict):
            return {
                'id': str(policy.get('id', '')),
                'level': str(policy.get('level', '未知层级')),
                'title': str(policy.get('title', '未知标题')),
                'pub_date': str(policy.get('pub_date', '未知日期')),
                'source': str(policy.get('source', '未知来源')),
                'content': str(policy.get('content', '无内容'))
            }
        else:
            return {
                'id': '',
                'level': '未知层级',
                'title': '未知标题',
                'pub_date': '未知日期',
                'source': '未知来源',
                'content': '无内容'
            }
    
    def _generate_policy_content(self, policy_info: Dict, policy_num: int) -> str:
        """生成政策内容 - 只返回正文，不包含元数据"""
        # 只返回正文内容，元数据在导出时统一添加
        return policy_info['content']
    
    @staticmethod
    def clean_policy_content(content: str) -> str:
        """清洗正文内容，去除常见网页冗余内容"""
        # 过滤常见无关关键词
        patterns = [
            r'【字号.*?】',
            r'【打印.*?】',
            r'【仅内容打印.*?】',
            r'【关闭.*?】',
            r'【下载.*?】',
            r'分享到.*',
            r'高级检索',
            r'全部',
            r'名称',
            r'文号',
            r'发布机构',
            r'业务类型',
            r'废止记录',
            r'成文时间',
            r'效力级别',
            r'时效状态',
            r'部门规范性文件',
            r'现行有效',
            r'来一一源',
            r'\s{2,}',
        ]
        for pat in patterns:
            content = re.sub(pat, '', content, flags=re.IGNORECASE)
        # 去除多余空行
        content = re.sub(r'\n{2,}', '\n', content)
        return content.strip()

    def _export_markdown_segments(self, segments: List[Dict], output_dir: str) -> Dict:
        """导出Markdown格式的段落 - 合并到单个文件"""
        files = []
        
        # 创建单个Markdown文件
        filename = "rag_knowledge_base.md"
        filepath = os.path.join(output_dir, filename)
        
        # 生成合并的内容
        content = "# 空间规划政策知识库\n\n"
        content += f"**导出时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        content += f"**政策数量：** {len(set(seg['policy_id'] for seg in segments))}\n\n"
        content += f"**段落数量：** {len(segments)}\n\n"
        content += "---\n\n"
        
        # 按政策分组，然后按段落顺序添加内容
        policy_groups = {}
        for segment in segments:
            policy_id = segment['policy_id']
            if policy_id not in policy_groups:
                policy_groups[policy_id] = []
            policy_groups[policy_id].append(segment)
        
        # 为每个政策添加内容
        for policy_id in sorted(policy_groups.keys()):
            policy_segments = policy_groups[policy_id]
            if not policy_segments:
                continue
                
            # 获取政策基本信息（从第一个段落获取）
            first_segment = policy_segments[0]
            policy_title = first_segment['policy_title']
            policy_date = first_segment['policy_date']
            policy_level = first_segment['policy_level']
            policy_source = first_segment['policy_source']
            
            # 合并所有正文内容并清洗
            full_content = '\n'.join([seg['content'] for seg in policy_segments])
            clean_content = self.clean_policy_content(full_content)

            # 添加政策标题和基本信息
            content += f"## {policy_id}. {policy_title}\n\n"
            content += f"**层级：** {policy_level}\n\n"
            content += f"**发布日期：** {policy_date}\n\n"
            content += f"**来源：** {policy_source}\n\n"
            content += f"**正文：**\n\n"
            content += f"{clean_content}\n\n"
            content += "---\n\n"
        
        # 保存合并的文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        files.append({
            'filename': filename,
            'filepath': filepath,
            'segment_count': len(segments),
            'policy_count': len(policy_groups)
        })
        
        return {'files': files}
    
    def _export_json_segments(self, segments: List[Dict], output_dir: str) -> Dict:
        """导出JSON格式的段落 - 合并到单个文件"""
        files = []
        
        # 按政策分组
        policy_groups = {}
        for segment in segments:
            policy_id = segment['policy_id']
            if policy_id not in policy_groups:
                policy_groups[policy_id] = []
            policy_groups[policy_id].append(segment)
        
        # 创建合并的JSON结构
        merged_data = {
            'export_time': datetime.now().isoformat(),
            'total_policies': len(policy_groups),
            'total_segments': len(segments),
            'format_type': 'json',
            'max_chunk_size': self.segmenter.max_chunk_size,
            'policies': []
        }
        
        # 为每个政策创建结构化数据
        for policy_id in sorted(policy_groups.keys()):
            policy_segments = policy_groups[policy_id]
            if not policy_segments:
                continue
                
            first_segment = policy_segments[0]
            policy_data = {
                'policy_id': policy_id,
                'title': first_segment['policy_title'],
                'date': first_segment['policy_date'],
                'level': first_segment['policy_level'],
                'source': first_segment['policy_source'],
                'segments': []
            }
            
            # 添加该政策的所有段落
            for segment in policy_segments:
                segment_data = {
                    'segment_id': segment['segment_id'],
                    'title': segment['title'],
                    'level': segment['level'],
                    'content': segment['content'],
                    'size': segment['size']
                }
                policy_data['segments'].append(segment_data)
            
            # 合并所有正文内容并清洗
            full_content = '\n'.join([seg['content'] for seg in policy_segments])
            clean_content = self.clean_policy_content(full_content)
            policy_data['content'] = clean_content

            merged_data['policies'].append(policy_data)
        
        # 导出合并的JSON文件
        main_file = os.path.join(output_dir, 'rag_knowledge_base.json')
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        
        files.append({
            'filename': 'rag_knowledge_base.json',
            'filepath': main_file,
            'policy_count': len(policy_groups),
            'segment_count': len(segments)
        })
        
        return {'files': files}
    
    def _export_txt_segments(self, segments: List[Dict], output_dir: str) -> Dict:
        """导出TXT格式的段落 - 合并到单个文件"""
        files = []
        
        # 创建单个TXT文件
        filename = "rag_knowledge_base.txt"
        filepath = os.path.join(output_dir, filename)
        
        # 生成合并的内容
        content = "空间规划政策知识库\n"
        content += "=" * 50 + "\n\n"
        content += f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        content += f"政策数量：{len(set(seg['policy_id'] for seg in segments))}\n\n"
        content += f"段落数量：{len(segments)}\n\n"
        content += "=" * 50 + "\n\n"
        
        # 按政策分组，然后按段落顺序添加内容
        policy_groups = {}
        for segment in segments:
            policy_id = segment['policy_id']
            if policy_id not in policy_groups:
                policy_groups[policy_id] = []
            policy_groups[policy_id].append(segment)
        
        # 为每个政策添加内容
        for policy_id in sorted(policy_groups.keys()):
            policy_segments = policy_groups[policy_id]
            if not policy_segments:
                continue
                
            # 获取政策基本信息（从第一个段落获取）
            first_segment = policy_segments[0]
            policy_title = first_segment['policy_title']
            policy_date = first_segment['policy_date']
            policy_level = first_segment['policy_level']
            policy_source = first_segment['policy_source']
            
            # 合并所有正文内容并清洗
            full_content = '\n'.join([seg['content'] for seg in policy_segments])
            clean_content = self.clean_policy_content(full_content)

            # 添加政策标题和基本信息
            content += f"{policy_id}. {policy_title}\n"
            content += f"层级：{policy_level}\n"
            content += f"发布日期：{policy_date}\n"
            content += f"来源：{policy_source}\n"
            content += f"正文：\n"
            content += "-" * 30 + "\n"
            content += f"{clean_content}\n\n"
            content += "=" * 50 + "\n\n"
        
        # 保存合并的文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        files.append({
            'filename': filename,
            'filepath': filepath,
            'segment_count': len(segments),
            'policy_count': len(policy_groups)
        })
        
        return {'files': files}

def export_for_rag_knowledge_base(data, output_dir, format_type='markdown', max_chunk_size=4096):
    """
    为RAG知识库导出优化格式的便捷函数
    
    Args:
        data: 政策数据列表
        output_dir: 输出目录
        format_type: 输出格式 ('markdown', 'json', 'txt')
        max_chunk_size: 最大段落大小
    
    Returns:
        导出结果信息
    """
    exporter = RAGExporter(max_chunk_size)
    return exporter.export_for_rag(data, output_dir, format_type) 