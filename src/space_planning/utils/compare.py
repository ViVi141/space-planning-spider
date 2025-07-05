from fuzzywuzzy import fuzz
import re
from PyQt5.QtGui import QTextCharFormat, QColor, QSyntaxHighlighter

class PolicyComparer:
    def __init__(self):
        self.keywords = ['规划', '空间', '用地', '控制性详细规划', '总体规划', '专项规划', '土地利用', '建设用地', '容积率', '建筑密度', '绿地率']
    
    def compare_texts(self, text1, text2):
        """比较两个文本的相似度"""
        # 使用fuzzywuzzy计算相似度
        ratio = fuzz.ratio(text1, text2)
        partial_ratio = fuzz.partial_ratio(text1, text2)
        token_sort_ratio = fuzz.token_sort_ratio(text1, text2)
        token_set_ratio = fuzz.token_set_ratio(text1, text2)
        
        return {
            'ratio': ratio,
            'partial_ratio': partial_ratio,
            'token_sort_ratio': token_sort_ratio,
            'token_set_ratio': token_set_ratio,
            'average': (ratio + partial_ratio + token_sort_ratio + token_set_ratio) / 4
        }
    
    def find_keywords(self, text):
        """在文本中查找关键词"""
        found_keywords = []
        for keyword in self.keywords:
            if keyword in text:
                found_keywords.append(keyword)
        return found_keywords
    
    def highlight_keywords(self, text):
        """高亮关键词"""
        highlighted_text = text
        for keyword in self.keywords:
            if keyword in text:
                highlighted_text = highlighted_text.replace(keyword, f'<span style="background-color: yellow; font-weight: bold;">{keyword}</span>')
        return highlighted_text

class KeywordHighlighter(QSyntaxHighlighter):
    """关键词高亮器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keywords = ['规划', '空间', '用地', '控制性详细规划', '总体规划', '专项规划', '土地利用', '建设用地', '容积率', '建筑密度', '绿地率']
        self.highlight_format = QTextCharFormat()
        self.highlight_format.setBackground(QColor(255, 255, 0))  # 黄色背景
        self.highlight_format.setFontWeight(700)  # 粗体
    
    def set_keywords(self, keywords):
        """设置关键词列表"""
        if keywords:
            self.keywords = keywords
        else:
            self.keywords = ['规划', '空间', '用地', '控制性详细规划', '总体规划', '专项规划', '土地利用', '建设用地', '容积率', '建筑密度', '绿地率']
        self.rehighlight()  # 重新高亮
    
    def highlightBlock(self, text):
        """高亮文本块中的关键词"""
        for keyword in self.keywords:
            pattern = re.compile(keyword, re.IGNORECASE)
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), self.highlight_format) 