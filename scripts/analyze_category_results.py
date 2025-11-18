"""
分析分类测试结果，找出同名小类在不同大类中的数据量差异
"""
import os
import sys
import json

# 调整路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
sys.path.append(PROJECT_ROOT)

def main():
    """主函数"""
    # 读取测试结果
    json_file = os.path.join(PROJECT_ROOT, 'analysis_pages', 'guangdong', 'all_categories_lvalues_test.json')
    
    with open(json_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    print("=" * 100)
    print("分类测试结果分析")
    print("=" * 100)
    
    # 按大类分组
    by_main_category = {}
    for r in results:
        main_cat = r['main_category']
        if main_cat not in by_main_category:
            by_main_category[main_cat] = []
        by_main_category[main_cat].append(r)
    
    # 显示每个大类的有效配置
    for main_cat, cat_results in by_main_category.items():
        print(f"\n【{main_cat}】")
        print("-" * 100)
        
        # 按小类分组
        by_category = {}
        for r in cat_results:
            cat_code = r['category_code']
            if cat_code not in by_category:
                by_category[cat_code] = []
            by_category[cat_code].append(r)
        
        for cat_code, results_list in by_category.items():
            cat_name = results_list[0]['category_name']
            print(f"\n  {cat_name} ({cat_code}):")
            
            valid_results = [r for r in results_list if r['status'] == 'valid' and r['count'] and r['count'] > 0]
            if valid_results:
                for r in valid_results:
                    lvalue_str = r['lvalue'] if r['lvalue'] else '无'
                    print(f"    [OK] {r['lvalue_name']} (lvalue={lvalue_str}): {r['count']}条")
            else:
                print(f"    [FAIL] 没有有效的lvalue")
    
    # 检查同名小类在不同大类中的数据量差异
    print(f"\n{'='*100}")
    print("同名小类在不同大类中的数据量对比")
    print(f"{'='*100}")
    
    # 找出同名但不同大类的分类
    category_groups = {}
    for r in results:
        key = r['category_name']
        if key not in category_groups:
            category_groups[key] = []
        category_groups[key].append(r)
    
    found_differences = False
    for cat_name, results_list in category_groups.items():
        # 如果同一个名称出现在不同大类中
        main_cats = set(r['main_category'] for r in results_list)
        if len(main_cats) > 1:
            found_differences = True
            print(f"\n【{cat_name}】出现在多个大类中:")
            for main_cat in sorted(main_cats):
                main_cat_results = [r for r in results_list if r['main_category'] == main_cat]
                cat_code = main_cat_results[0]['category_code']
                print(f"\n  {main_cat} ({cat_code}):")
                valid_results = [r for r in main_cat_results if r['status'] == 'valid' and r['count'] and r['count'] > 0]
                if valid_results:
                    for r in valid_results:
                        lvalue_str = r['lvalue'] if r['lvalue'] else '无'
                        print(f"    [OK] {r['lvalue_name']} (lvalue={lvalue_str}): {r['count']}条")
                else:
                    print(f"    [FAIL] 没有有效的lvalue")
    
    if not found_differences:
        print("\n未发现同名小类出现在不同大类中的情况")
    
    # 生成配置建议
    print(f"\n{'='*100}")
    print("配置建议")
    print(f"{'='*100}")
    
    recommended_config = {}
    for main_cat, cat_results in by_main_category.items():
        recommended_config[main_cat] = {}
        for r in cat_results:
            cat_code = r['category_code']
            if cat_code not in recommended_config[main_cat]:
                recommended_config[main_cat][cat_code] = {
                    'category_name': r['category_name'],
                    'menu': r['menu'],
                    'library': r['library'],
                    'valid_lvalues': []
                }
            
            if r['status'] == 'valid' and r['count'] and r['count'] > 0 and r['lvalue']:
                recommended_config[main_cat][cat_code]['valid_lvalues'].append({
                    'lvalue': r['lvalue'],
                    'lvalue_name': r['lvalue_name'],
                    'count': r['count']
                })
    
    for main_cat, categories in recommended_config.items():
        print(f"\n【{main_cat}】")
        for cat_code, config in categories.items():
            print(f"  {config['category_name']} ({cat_code}):")
            if config['valid_lvalues']:
                for lv in config['valid_lvalues']:
                    print(f"    - lvalue={lv['lvalue']} ({lv['lvalue_name']}): {lv['count']}条")
            else:
                print(f"    - 无有效lvalue，建议不使用发布机关筛选")
    
    print(f"\n{'='*100}")
    print("分析完成")
    print(f"{'='*100}")

if __name__ == '__main__':
    main()

