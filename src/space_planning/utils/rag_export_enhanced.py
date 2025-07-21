#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG知识库增强导出模块
支持分片导出，符合系统限制（最大100MB，最多50个文件）
"""

import re
import os
import json
import logging
import math
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from pathlib import Path

# 设置日志
logger = logging.getLogger(__name__)

class RAGChunkExporter:
    """RAG分片导出器"""
    
    def __init__(self, 
                 max_file_size_mb: int = 100,
                 max_files_per_chunk: int = 50,
                 max_chunk_size: int = 4096):
        self.max_file_size_mb = max_file_size_mb
        self.max_files_per_chunk = max_files_per_chunk
        self.max_chunk_size = max_chunk_size
        
        # 系统限制
        self.max_total_size_bytes = max_file_size_mb * 1024 * 1024  # 转换为字节
        
        # 分段器
        self.segmenter = RAGSegmenter(max_chunk_size)
    
    def export_with_chunking(self, data: List, output_dir: str, format_type: str = 'markdown') -> Dict:
        """
        分片导出RAG知识库
        自动分割为符合系统限制的多个文件包
        """
        try:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 处理政策数据
            processed_data = self._process_policy_data(data)
            
            # 生成分段
            segments = self._generate_segments(processed_data, format_type)
            
            # 分片导出
            chunks = self._create_chunks(segments)
            
            # 导出分片
            export_results = self._export_chunks(chunks, output_dir, format_type)
            
            return {
                'success': True,
                'total_policies': len(data),
                'total_segments': len(segments),
                'total_chunks': len(chunks),
                'chunks': export_results,
                'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logger.error(f"RAG分片导出失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def _process_policy_data(self, data: List) -> List[Dict]:
        """处理政策数据"""
        processed_data = []
        
        for i, policy in enumerate(data):
            try:
                # 解析政策数据
                if isinstance(policy, tuple):
                    # 数据库返回的元组格式
                    policy_info = {
                        'id': policy[0],
                        'level': policy[1],
                        'title': policy[2],
                        'pub_date': policy[3],
                        'source': policy[4],
                        'content': policy[5],
                        'category': policy[6] if len(policy) > 6 else ''
                    }
                else:
                    # 字典格式
                    policy_info = policy
                
                # 清理和格式化内容
                content = self._clean_policy_content(policy_info.get('content', ''))
                if not content.strip():
                    continue
                
                processed_data.append({
                    'policy_num': i + 1,
                    'level': policy_info.get('level', ''),
                    'title': policy_info.get('title', ''),
                    'pub_date': policy_info.get('pub_date', ''),
                    'source': policy_info.get('source', ''),
                    'content': content,
                    'category': policy_info.get('category', ''),
                    'crawl_time': policy_info.get('crawl_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                })
                
            except Exception as e:
                logger.warning(f"处理政策数据失败: {e}")
                continue
        
        return processed_data
    
    def _generate_segments(self, processed_data: List[Dict], format_type: str = 'markdown') -> List[Dict]:
        """生成分段"""
        segments = []
        
        for policy in processed_data:
            # 生成政策内容
            content = self._generate_policy_content(policy)
            
            # 分段处理
            if format_type == 'markdown':
                policy_segments = self.segmenter.segment_markdown(content)
            else:
                policy_segments = self.segmenter.segment_txt_pdf(content)
            
            # 添加政策信息到分段
            for segment in policy_segments:
                segment['policy_info'] = {
                    'level': policy['level'],
                    'title': policy['title'],
                    'pub_date': policy['pub_date'],
                    'source': policy['source'],
                    'category': policy['category']
                }
                segments.append(segment)
        
        return segments
    
    def _create_chunks(self, segments: List[Dict]) -> List[List[Dict]]:
        """创建分片"""
        chunks = []
        current_chunk = []
        current_size = 0
        
        for segment in segments:
            segment_size = len(segment['content'])
            
            # 检查是否需要创建新分片
            if (len(current_chunk) >= self.max_files_per_chunk or 
                current_size + segment_size > self.max_total_size_bytes):
                
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_size = 0
            
            # 添加段落到当前分片
            current_chunk.append(segment)
            current_size += segment_size
        
        # 添加最后一个分片
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _export_chunks(self, chunks: List[List[Dict]], output_dir: str, format_type: str) -> List[Dict]:
        """导出分片"""
        export_results = []
        
        for i, chunk in enumerate(chunks):
            chunk_dir = os.path.join(output_dir, f"chunk_{i+1:03d}")
            os.makedirs(chunk_dir, exist_ok=True)
            
            # 导出分片
            if format_type == 'markdown':
                result = self._export_markdown_chunk(chunk, chunk_dir, i+1)
            elif format_type == 'json':
                result = self._export_json_chunk(chunk, chunk_dir, i+1)
            else:  # txt
                result = self._export_txt_chunk(chunk, chunk_dir, i+1)
            
            export_results.append(result)
        
        return export_results
    
    def _export_markdown_chunk(self, chunk: List[Dict], chunk_dir: str, chunk_num: int) -> Dict:
        """导出Markdown分片"""
        files_created = []
        total_size = 0
        
        for i, segment in enumerate(chunk):
            # 生成文件名
            policy_title = segment['policy_info']['title'][:50]  # 限制标题长度
            safe_title = re.sub(r'[^\w\s-]', '', policy_title).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            
            filename = f"{chunk_num:03d}_{i+1:03d}_{safe_title}.md"
            filepath = os.path.join(chunk_dir, filename)
            
            # 生成Markdown内容
            content = self._generate_markdown_content(segment)
            
            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            file_size = os.path.getsize(filepath)
            files_created.append({
                'filename': filename,
                'size_bytes': file_size,
                'title': segment['title'],
                'policy_title': segment['policy_info']['title']
            })
            total_size += file_size
        
        return {
            'chunk_num': chunk_num,
            'chunk_dir': chunk_dir,
            'files_created': files_created,
            'total_files': len(files_created),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2)
        }
    
    def _export_json_chunk(self, chunk: List[Dict], chunk_dir: str, chunk_num: int) -> Dict:
        """导出JSON分片"""
        files_created = []
        total_size = 0
        
        for i, segment in enumerate(chunk):
            # 生成文件名
            policy_title = segment['policy_info']['title'][:50]
            safe_title = re.sub(r'[^\w\s-]', '', policy_title).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            
            filename = f"{chunk_num:03d}_{i+1:03d}_{safe_title}.json"
            filepath = os.path.join(chunk_dir, filename)
            
            # 生成JSON内容
            json_data = {
                'title': segment['title'],
                'content': segment['content'],
                'level': segment['level'],
                'policy_info': segment['policy_info'],
                'metadata': {
                    'chunk_size': len(segment['content']),
                    'export_time': datetime.now().isoformat(),
                    'chunk_num': chunk_num,
                    'segment_num': i+1
                }
            }
            
            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            file_size = os.path.getsize(filepath)
            files_created.append({
                'filename': filename,
                'size_bytes': file_size,
                'title': segment['title'],
                'policy_title': segment['policy_info']['title']
            })
            total_size += file_size
        
        return {
            'chunk_num': chunk_num,
            'chunk_dir': chunk_dir,
            'files_created': files_created,
            'total_files': len(files_created),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2)
        }
    
    def _export_txt_chunk(self, chunk: List[Dict], chunk_dir: str, chunk_num: int) -> Dict:
        """导出TXT分片"""
        files_created = []
        total_size = 0
        
        for i, segment in enumerate(chunk):
            # 生成文件名
            policy_title = segment['policy_info']['title'][:50]
            safe_title = re.sub(r'[^\w\s-]', '', policy_title).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            
            filename = f"{chunk_num:03d}_{i+1:03d}_{safe_title}.txt"
            filepath = os.path.join(chunk_dir, filename)
            
            # 生成TXT内容
            content = self._generate_txt_content(segment)
            
            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            file_size = os.path.getsize(filepath)
            files_created.append({
                'filename': filename,
                'size_bytes': file_size,
                'title': segment['title'],
                'policy_title': segment['policy_info']['title']
            })
            total_size += file_size
        
        return {
            'chunk_num': chunk_num,
            'chunk_dir': chunk_dir,
            'files_created': files_created,
            'total_files': len(files_created),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2)
        }
    
    def _generate_policy_content(self, policy: Dict) -> str:
        """生成政策内容"""
        content_parts = []
        
        # 标题
        content_parts.append(f"# {policy['title']}")
        content_parts.append("")
        
        # 基本信息
        content_parts.append("## 基本信息")
        content_parts.append(f"- **发布机构**: {policy['level']}")
        content_parts.append(f"- **发布日期**: {policy['pub_date']}")
        content_parts.append(f"- **来源**: {policy['source']}")
        if policy['category']:
            content_parts.append(f"- **分类**: {policy['category']}")
        content_parts.append("")
        
        # 政策内容
        content_parts.append("## 政策内容")
        content_parts.append(policy['content'])
        content_parts.append("")
        
        return "\n".join(content_parts)
    
    def _generate_markdown_content(self, segment: Dict) -> str:
        """生成Markdown内容"""
        content_parts = []
        
        # 标题
        content_parts.append(f"# {segment['title']}")
        content_parts.append("")
        
        # 政策信息
        policy_info = segment['policy_info']
        content_parts.append("## 政策信息")
        content_parts.append(f"- **发布机构**: {policy_info['level']}")
        content_parts.append(f"- **政策标题**: {policy_info['title']}")
        content_parts.append(f"- **发布日期**: {policy_info['pub_date']}")
        content_parts.append(f"- **来源**: {policy_info['source']}")
        if policy_info['category']:
            content_parts.append(f"- **分类**: {policy_info['category']}")
        content_parts.append("")
        
        # 内容
        content_parts.append("## 内容")
        content_parts.append(segment['content'])
        content_parts.append("")
        
        return "\n".join(content_parts)
    
    def _generate_txt_content(self, segment: Dict) -> str:
        """生成TXT内容"""
        content_parts = []
        
        # 标题
        content_parts.append(f"标题: {segment['title']}")
        content_parts.append("=" * 50)
        content_parts.append("")
        
        # 政策信息
        policy_info = segment['policy_info']
        content_parts.append("政策信息:")
        content_parts.append(f"  发布机构: {policy_info['level']}")
        content_parts.append(f"  政策标题: {policy_info['title']}")
        content_parts.append(f"  发布日期: {policy_info['pub_date']}")
        content_parts.append(f"  来源: {policy_info['source']}")
        if policy_info['category']:
            content_parts.append(f"  分类: {policy_info['category']}")
        content_parts.append("")
        
        # 内容
        content_parts.append("内容:")
        content_parts.append("-" * 30)
        content_parts.append(segment['content'])
        content_parts.append("")
        
        return "\n".join(content_parts)
    
    def _clean_policy_content(self, content: str) -> str:
        """清理政策内容"""
        if not content:
            return ""
        
        # 移除多余的空白字符
        content = re.sub(r'\s+', ' ', content.strip())
        
        # 移除HTML标签
        content = re.sub(r'<[^>]+>', '', content)
        
        # 移除特殊字符
        content = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s\.,，。！？；：""''（）()【】\[\]]', '', content)
        
        return content

class RAGSegmenter:
    """RAG智能分段器"""
    
    def __init__(self, max_chunk_size: int = 4096):
        self.max_chunk_size = max_chunk_size
        
        # 定义分段标识的正则表达式
        self.segment_patterns = {
            'chapter': r'[第][一二三四五六七八九十]+[章]',
            'section': r'[第][一二三四五六七八九十]+[节]',
            'numbered': r'[一二三四五六七八九十|1-9]+[、|\.][1-9]*[\.]*[1-9]*',
            'article': r'[第][一二三四五六七八九十]+[条]',
            'markdown_h1': r'^#\s+',
            'markdown_h2': r'^##\s+',
            'markdown_h3': r'^###\s+',
            'markdown_h4': r'^####\s+',
            'markdown_h5': r'^#####\s+',
            'markdown_h6': r'^######\s+',
            'policy_chapter': r'第[一二三四五六七八九十]+章',
            'policy_section': r'第[一二三四五六七八九十]+节',
            'policy_article': r'第[一二三四五六七八九十]+条',
            'policy_item': r'[一二三四五六七八九十]+[、\.]',
        }
        
        self.all_patterns = '|'.join([
            f'({pattern})' for pattern in self.segment_patterns.values()
        ])
    
    def segment_markdown(self, content: str) -> List[Dict]:
        """MarkDown类型文件智能分段"""
        segments = []
        lines = content.split('\n')
        current_segment = []
        current_title = ""
        current_level = 0
        
        for line in lines:
            title_level = self._detect_title_level(line)
            
            if title_level > 0:
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
                
                current_segment = [line]
                current_title = line.strip()
                current_level = title_level
            else:
                current_segment.append(line)
        
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
    
    def segment_txt_pdf(self, content: str) -> List[Dict]:
        """TXT/PDF类型文件智能分段"""
        # 按段落分割
        paragraphs = re.split(r'\n\s*\n', content)
        segments = []
        
        current_segment = []
        current_size = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            paragraph_size = len(paragraph)
            
            if current_size + paragraph_size > self.max_chunk_size and current_segment:
                # 保存当前分段
                segments.append({
                    'title': f"段落 {len(segments) + 1}",
                    'level': 1,
                    'content': '\n\n'.join(current_segment),
                    'size': current_size
                })
                current_segment = []
                current_size = 0
            
            current_segment.append(paragraph)
            current_size += paragraph_size
        
        if current_segment:
            segments.append({
                'title': f"段落 {len(segments) + 1}",
                'level': 1,
                'content': '\n\n'.join(current_segment),
                'size': current_size
            })
        
        return segments
    
    def _detect_title_level(self, line: str) -> int:
        """检测标题级别"""
        line = line.strip()
        
        # Markdown标题
        match = re.match(r'^#{1,6}\s+', line)
        if match:
            return len(match.group())
        
        # 其他标题模式
        if re.search(self.all_patterns, line):
            return 1
        
        return 0
    
    def _split_by_size(self, content: str, title: str, level: int) -> List[Dict]:
        """按大小分割内容"""
        segments = []
        words = content.split()
        current_segment = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1  # +1 for space
            
            if current_size + word_size > self.max_chunk_size and current_segment:
                segments.append({
                    'title': f"{title} (分段 {len(segments) + 1})",
                    'level': level,
                    'content': ' '.join(current_segment),
                    'size': current_size
                })
                current_segment = []
                current_size = 0
            
            current_segment.append(word)
            current_size += word_size
        
        if current_segment:
            segments.append({
                'title': f"{title} (分段 {len(segments) + 1})",
                'level': level,
                'content': ' '.join(current_segment),
                'size': current_size
            })
        
        return segments

def export_rag_with_chunking(data, output_dir, format_type='markdown', 
                            max_file_size_mb=100, max_files_per_chunk=50, max_chunk_size=4096):
    """分片导出RAG知识库的主函数"""
    exporter = RAGChunkExporter(
        max_file_size_mb=max_file_size_mb,
        max_files_per_chunk=max_files_per_chunk,
        max_chunk_size=max_chunk_size
    )
    
    return exporter.export_with_chunking(data, output_dir, format_type) 