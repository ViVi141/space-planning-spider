from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
import os

def export_to_word(data, file_path):
    """导出政策数据到Word文档"""
    doc = Document()
    
    # 设置中文字体
    doc.styles['Normal'].font.name = '宋体'
    doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    
    # 添加标题
    title = doc.add_heading('空间规划政策汇总', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 添加统计信息
    stats_para = doc.add_paragraph(f'共导出 {len(data)} 条政策文件')
    stats_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 为每个政策添加内容
    for i, policy in enumerate(data, 1):
        # 政策标题
        policy_title = doc.add_heading(f'{i}. {policy[2]}', level=1)
        
        # 基本信息
        info_para = doc.add_paragraph()
        info_para.add_run(f'层级：{policy[1]}\n')
        info_para.add_run(f'发布日期：{policy[3]}\n')
        info_para.add_run(f'来源：{policy[4]}\n')
        
        # 正文内容
        content_para = doc.add_paragraph()
        content_para.add_run('正文：\n')
        content_para.add_run(policy[5])
        
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
        try:
            import pandas as pd
            
            # 转换数据格式
            df_data = []
            for policy in data:
                df_data.append({
                    'ID': policy[0],
                    '层级': policy[1],
                    '标题': policy[2],
                    '发布日期': policy[3],
                    '来源': policy[4],
                    '内容': policy[5]
                })
            
            df = pd.DataFrame(df_data)
            df.to_excel(file_path, index=False, engine='openpyxl')
            return True
        except ImportError:
            print("需要安装pandas和openpyxl库才能导出Excel文件")
            return False
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
                    f.write(f'{i}. {policy[2]}\n')
                    f.write(f'层级：{policy[1]}\n')
                    f.write(f'发布日期：{policy[3]}\n')
                    f.write(f'来源：{policy[4]}\n')
                    f.write(f'正文：{policy[5]}\n')
                    f.write('=' * 50 + '\n\n')
            
            return True
        except Exception as e:
            print(f"导出文本文件失败: {e}")
            return False 