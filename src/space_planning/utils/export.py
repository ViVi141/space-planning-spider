from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
import os

def export_to_word(data, file_path):
    """导出政策数据到Word文档"""
    doc = Document()
    
    # 设置中文字体 - 使用更安全的方式
    try:
        # 直接设置段落字体，避免样式设置问题
        pass
    except Exception:
        # 如果字体设置失败，继续执行，不影响文档生成
        pass
    
    # 添加标题
    title = doc.add_heading('空间规划政策汇总', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 添加统计信息
    stats_para = doc.add_paragraph(f'共导出 {len(data)} 条政策文件')
    stats_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 为每个政策添加内容
    for i, policy in enumerate(data, 1):
        # 解析政策数据格式
        if isinstance(policy, (list, tuple)):
            title = str(policy[2]) if len(policy) > 2 else "未知标题"
            level = str(policy[1]) if len(policy) > 1 else "未知层级"
            pub_date = str(policy[3]) if len(policy) > 3 else "未知日期"
            source = str(policy[4]) if len(policy) > 4 else "未知来源"
            content = str(policy[5]) if len(policy) > 5 else "无内容"
        elif isinstance(policy, dict):
            title = str(policy.get('title', '未知标题'))
            level = str(policy.get('level', '未知层级'))
            pub_date = str(policy.get('pub_date', '未知日期'))
            source = str(policy.get('source', '未知来源'))
            content = str(policy.get('content', '无内容'))
        else:
            title = level = pub_date = source = content = "未知"
        
        # 政策标题
        policy_title = doc.add_heading(f'{i}. {title}', level=1)
        
        # 基本信息
        info_para = doc.add_paragraph()
        info_para.add_run(f'层级：{level}\n')
        info_para.add_run(f'发布日期：{pub_date}\n')
        info_para.add_run(f'来源：{source}\n')
        
        # 正文内容
        content_para = doc.add_paragraph()
        content_para.add_run('正文：\n')
        content_para.add_run(content)
        
        # 添加分隔线
        if i < len(data):
            doc.add_paragraph('=' * 50)
    
    # 保存文档
    doc.save(file_path)
    return True

class DataExporter:
    """数据导出器"""
    
    def __init__(self):
        pass
    
    def export_to_word(self, data, file_path):
        """导出政策数据到Word文档"""
        return export_to_word(data, file_path)
    
    def export_to_excel(self, data, file_path):
        """导出政策数据到Excel文档"""
        # 检查pandas是否可用
        try:
            import pandas as pd  # type: ignore
        except ImportError:
            print("需要安装pandas和openpyxl库才能导出Excel文件")
            return False
        
        try:
            # 转换数据格式
            df_data = []
            for policy in data:
                # 解析政策数据格式
                if isinstance(policy, (list, tuple)):
                    policy_id = str(policy[0]) if len(policy) > 0 else ""
                    level = str(policy[1]) if len(policy) > 1 else "未知层级"
                    title = str(policy[2]) if len(policy) > 2 else "未知标题"
                    pub_date = str(policy[3]) if len(policy) > 3 else "未知日期"
                    source = str(policy[4]) if len(policy) > 4 else "未知来源"
                    content = str(policy[5]) if len(policy) > 5 else "无内容"
                elif isinstance(policy, dict):
                    policy_id = str(policy.get('id', ''))
                    level = str(policy.get('level', '未知层级'))
                    title = str(policy.get('title', '未知标题'))
                    pub_date = str(policy.get('pub_date', '未知日期'))
                    source = str(policy.get('source', '未知来源'))
                    content = str(policy.get('content', '无内容'))
                else:
                    policy_id = level = title = pub_date = source = content = "未知"
                
                df_data.append({
                    'ID': policy_id,
                    '层级': level,
                    '标题': title,
                    '发布日期': pub_date,
                    '来源': source,
                    '内容': content
                })
            
            df = pd.DataFrame(df_data)
            df.to_excel(file_path, index=False, engine='openpyxl')
            return True
        except Exception as e:
            print(f"导出Excel文件失败: {e}")
            return False
    
    def export_to_txt(self, data, file_path):
        """导出政策数据到文本文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('空间规划政策汇总\n')
                f.write('=' * 50 + '\n')
                f.write(f'共导出 {len(data)} 条政策文件\n\n')
                
                for i, policy in enumerate(data, 1):
                    # 解析政策数据格式
                    if isinstance(policy, (list, tuple)):
                        title = str(policy[2]) if len(policy) > 2 else "未知标题"
                        level = str(policy[1]) if len(policy) > 1 else "未知层级"
                        pub_date = str(policy[3]) if len(policy) > 3 else "未知日期"
                        source = str(policy[4]) if len(policy) > 4 else "未知来源"
                        content = str(policy[5]) if len(policy) > 5 else "无内容"
                    elif isinstance(policy, dict):
                        title = str(policy.get('title', '未知标题'))
                        level = str(policy.get('level', '未知层级'))
                        pub_date = str(policy.get('pub_date', '未知日期'))
                        source = str(policy.get('source', '未知来源'))
                        content = str(policy.get('content', '无内容'))
                    else:
                        title = level = pub_date = source = content = "未知"
                    
                    f.write(f'{i}. {title}\n')
                    f.write(f'层级：{level}\n')
                    f.write(f'发布日期：{pub_date}\n')
                    f.write(f'来源：{source}\n')
                    f.write(f'正文：{content}\n')
                    f.write('=' * 50 + '\n\n')
            
            return True
        except Exception as e:
            print(f"导出文本文件失败: {e}")
            return False 