import re
from datetime import datetime

class ComplianceAnalyzer:
    """合规性分析器"""
    def __init__(self):
        # 政策类型关键词
        self.policy_types = {
            '总体规划': ['总体规划', '国土空间规划', '城市总体规划', '县域规划'],
            '控制性详细规划': ['控制性详细规划', '控规', '详细规划'],
            '专项规划': ['专项规划', '专项', '交通规划', '绿地规划', '基础设施规划'],
            '土地利用': ['土地利用', '用地', '土地管理', '建设用地'],
            '环境保护': ['环境保护', '生态', '污染', '环境'],
            '历史文化': ['历史文化', '文物', '古迹', '保护'],
            '交通规划': ['交通', '道路', '轨道交通', '公交'],
            '市政设施': ['市政', '给排水', '电力', '通信', '燃气']
        }
        
        # 合规性关键词
        self.compliance_keywords = {
            '强制性': ['必须', '应当', '禁止', '不得', '严禁'],
            '指导性': ['建议', '鼓励', '推荐', '引导'],
            '程序性': ['程序', '流程', '审批', '备案', '公示'],
            '标准性': ['标准', '规范', '要求', '指标', '参数']
        }
    
    def classify_policy(self, title, content):
        """政策分类"""
        text = title + ' ' + content
        classifications = []
        
        for policy_type, keywords in self.policy_types.items():
            for keyword in keywords:
                if keyword in text:
                    classifications.append(policy_type)
                    break
        
        return list(set(classifications)) if classifications else ['其他']
    
    def analyze_compliance(self, policy_content, project_keywords):
        """分析政策对项目的合规性影响"""
        if not project_keywords:
            return {'score': 0, 'impact': '无', 'risks': [], 'suggestions': []}
        
        score = 0
        risks = []
        suggestions = []
        
        # 关键词匹配度
        matched_keywords = []
        for keyword in project_keywords:
            if keyword in policy_content:
                matched_keywords.append(keyword)
                score += 20
        
        # 政策类型影响
        policy_types = self.classify_policy('', policy_content)
        if any(t in ['控制性详细规划', '土地利用'] for t in policy_types):
            score += 30
        elif any(t in ['总体规划', '专项规划'] for t in policy_types):
            score += 20
        
        # 强制性要求检测
        for keyword in self.compliance_keywords['强制性']:
            if keyword in policy_content:
                risks.append(f"发现强制性要求：{keyword}")
                score += 10
        
        # 时间敏感性
        if '最新' in policy_content or '修订' in policy_content:
            risks.append("政策可能已更新，需要核实最新版本")
        
        # 生成建议
        if score > 50:
            suggestions.append("该政策对项目有重要影响，建议重点关注")
        if matched_keywords:
            suggestions.append(f"政策涉及项目关键词：{', '.join(matched_keywords)}")
        
        # 影响等级
        if score >= 80:
            impact = '高'
        elif score >= 50:
            impact = '中'
        else:
            impact = '低'
        
        return {
            'score': min(score, 100),
            'impact': impact,
            'risks': risks,
            'suggestions': suggestions,
            'matched_keywords': matched_keywords
        }
    
    def generate_compliance_report(self, policies, project_keywords):
        """生成合规性分析报告"""
        result = "=== 空间规划政策合规性分析报告 ===\n\n"
        result += f"分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        result += f"项目关键词：{', '.join(project_keywords)}\n"
        result += f"分析政策数量：{len(policies)} 条\n\n"
        
        # 政策分类统计
        type_stats = {}
        high_impact_policies = []
        risks = []
        suggestions = []
        
        for policy in policies:
            # 获取政策内容
            content = policy[5] if len(policy) > 5 else ""
            title = policy[2]
            
            # 政策分类
            policy_types = self.classify_policy(title, content)
            for policy_type in policy_types:
                type_stats[policy_type] = type_stats.get(policy_type, 0) + 1
            
            # 合规性分析
            compliance = self.analyze_compliance(content, project_keywords)
            
            if compliance['score'] > 50:
                high_impact_policies.append({
                    'title': title,
                    'pub_date': policy[3],
                    'score': compliance['score'],
                    'impact': compliance['impact'],
                    'risks': compliance['risks'],
                    'suggestions': compliance['suggestions']
                })
            
            risks.extend(compliance['risks'])
            suggestions.extend(compliance['suggestions'])
        
        # 1. 政策类型分布
        result += "1. 政策类型分布：\n"
        for policy_type, count in sorted(type_stats.items(), key=lambda x: x[1], reverse=True):
            result += f"   {policy_type}：{count} 条\n"
        
        # 2. 高影响政策
        result += f"\n2. 高影响政策（{len(high_impact_policies)} 条）：\n"
        for policy in high_impact_policies:
            result += f"   📋 {policy['title']}\n"
            result += f"      发布日期：{policy['pub_date']}\n"
            result += f"      影响度：{policy['impact']}（评分：{policy['score']}）\n"
            if policy['risks']:
                result += f"      风险提示：{', '.join(policy['risks'])}\n"
            if policy['suggestions']:
                result += f"      建议：{', '.join(policy['suggestions'])}\n"
            result += "\n"
        
        # 3. 总体风险提示
        if risks:
            result += "3. 总体风险提示：\n"
            unique_risks = list(set(risks))
            for risk in unique_risks:
                result += f"   ⚠️ {risk}\n"
        
        # 4. 合规建议
        if suggestions:
            result += "\n4. 合规建议：\n"
            unique_suggestions = list(set(suggestions))
            for suggestion in unique_suggestions:
                result += f"   💡 {suggestion}\n"
        
        # 5. 合规性评分
        if high_impact_policies:
            avg_score = sum(p['score'] for p in high_impact_policies) / len(high_impact_policies)
            result += f"\n5. 项目合规性评分：{avg_score:.1f}/100\n"
            if avg_score >= 80:
                result += "   合规性评级：优秀 ✅\n"
            elif avg_score >= 60:
                result += "   合规性评级：良好 ⚠️\n"
            else:
                result += "   合规性评级：需要关注 ❌\n"
        
        return result 