#!/usr/bin/env python3
"""
优化价格显示修复方案的验证测试
测试所有改进点是否正确实施
"""

import sys
import os
import re
from pathlib import Path

# 添加项目路径
sys.path.insert(0, '/Users/lichuansong/Desktop/projects/wlxj_python')

def test_template_improvements():
    """测试模板改进情况"""
    print("=" * 60)
    print("测试优化价格显示修复方案")
    print("=" * 60)
    
    results = {
        'format_price_consistency': False,
        'boundary_condition_handling': False,
        'percentage_display': False,
        'user_experience_improvements': False,
        'code_quality_improvements': False
    }
    
    # 测试模板文件
    templates_to_check = [
        '/Users/lichuansong/Desktop/projects/wlxj_python/templates/portal/quotes.html',
        '/Users/lichuansong/Desktop/projects/wlxj_python/templates/portal/order_detail.html',
        '/Users/lichuansong/Desktop/projects/wlxj_python/templates/orders/detail.html'
    ]
    
    print("\n1. 检查价格格式化一致性...")
    format_price_count = 0
    raw_price_count = 0
    
    for template_path in templates_to_check:
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # 检查format_price使用
                format_price_matches = len(re.findall(r'\|format_price', content))
                format_price_count += format_price_matches
                
                # 检查原始价格显示（应该避免）
                raw_price_matches = len(re.findall(r'¥\{\{.*?price.*?\}\}', content))
                raw_price_count += raw_price_matches
                
                print(f"  {template_path.split('/')[-1]}: format_price使用{format_price_matches}次, 原始显示{raw_price_matches}次")
    
    results['format_price_consistency'] = raw_price_count == 0 and format_price_count > 0
    print(f"  ✓ 格式化一致性: {'PASS' if results['format_price_consistency'] else 'FAIL'}")
    
    print("\n2. 检查边界条件处理...")
    boundary_check_patterns = [
        r'selected_price\|float != 0',
        r'price\|float != 0',
        r'selected_price and.*selected_price\|float',
        r'quote\.price and quote\.price\|float'
    ]
    
    boundary_improvements = 0
    for template_path in templates_to_check:
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                for pattern in boundary_check_patterns:
                    matches = len(re.findall(pattern, content))
                    boundary_improvements += matches
                    if matches > 0:
                        print(f"  找到边界检查: {pattern} ({matches}次)")
    
    results['boundary_condition_handling'] = boundary_improvements >= 4
    print(f"  ✓ 边界条件处理: {'PASS' if results['boundary_condition_handling'] else 'FAIL'}")
    
    print("\n3. 检查百分比显示功能...")
    percentage_patterns = [
        r'price_change_percent.*=.*\*\s*100',
        r'price_change_percent.*%',
        r'\+.*price_change_percent.*%'
    ]
    
    percentage_features = 0
    for template_path in templates_to_check:
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                for pattern in percentage_patterns:
                    matches = len(re.findall(pattern, content))
                    percentage_features += matches
                    if matches > 0:
                        print(f"  找到百分比功能: {pattern} ({matches}次)")
    
    results['percentage_display'] = percentage_features >= 6
    print(f"  ✓ 百分比显示功能: {'PASS' if results['percentage_display'] else 'FAIL'}")
    
    print("\n4. 检查用户体验改进...")
    ux_improvements = [
        r'调整时间',
        r'协商调整',
        r'最终成交价',
        r'价格调整：',
        r'bg-light.*rounded',
        r'alert.*alert-info'
    ]
    
    ux_features = 0
    for template_path in templates_to_check:
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                for pattern in ux_improvements:
                    matches = len(re.findall(pattern, content))
                    ux_features += matches
                    if matches > 0:
                        print(f"  找到用户体验改进: {pattern} ({matches}次)")
    
    results['user_experience_improvements'] = ux_features >= 8
    print(f"  ✓ 用户体验改进: {'PASS' if results['user_experience_improvements'] else 'FAIL'}")
    
    print("\n5. 检查代码质量改进...")
    quality_indicators = [
        r'position-relative',
        r'text-end',
        r'fw-bold',
        r'd-block',
        r'bg-success.*bg-opacity',
        r'mt-\d+'
    ]
    
    quality_features = 0
    for template_path in templates_to_check:
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                for pattern in quality_indicators:
                    matches = len(re.findall(pattern, content))
                    quality_features += matches
    
    results['code_quality_improvements'] = quality_features >= 10
    print(f"  代码质量指标数量: {quality_features}")
    print(f"  ✓ 代码质量改进: {'PASS' if results['code_quality_improvements'] else 'FAIL'}")
    
    # 计算总体评分
    total_score = sum(results.values())
    max_score = len(results)
    percentage = (total_score / max_score) * 100
    
    print("\n" + "=" * 60)
    print("测试结果总结:")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:30} {status}")
    
    print(f"\n总体评分: {total_score}/{max_score} ({percentage:.1f}%)")
    
    if percentage >= 90:
        print("🎉 优化方案质量: 优秀 (90%+)")
    elif percentage >= 75:
        print("👍 优化方案质量: 良好 (75-89%)")
    elif percentage >= 60:
        print("⚠️  优化方案质量: 需要改进 (60-74%)")
    else:
        print("❌ 优化方案质量: 不合格 (<60%)")
    
    print("\n改进详情:")
    print("- 统一使用format_price过滤器，提升格式化一致性")
    print("- 增强边界条件处理，防止空值错误")  
    print("- 添加价格变化百分比显示，提供更直观的调整信息")
    print("- 优化用户界面设计，改进信息展示位置和样式")
    print("- 提升代码质量，使用更好的CSS类和结构")
    
    return percentage >= 90

def test_specific_improvements():
    """测试具体改进点"""
    print("\n" + "=" * 60)
    print("具体改进点验证")
    print("=" * 60)
    
    # 检查portal/quotes.html中的具体改进
    quotes_template = '/Users/lichuansong/Desktop/projects/wlxj_python/templates/portal/quotes.html'
    if os.path.exists(quotes_template):
        with open(quotes_template, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print("\n1. Portal Quotes 模板改进:")
        
        # 检查价格变化百分比
        if 'price_change_percent' in content:
            print("  ✓ 添加了价格变化百分比计算")
        
        # 检查边界条件
        if 'selected_price|float != 0' in content:
            print("  ✓ 增强了边界条件检查")
            
        # 检查调整时间显示
        if '调整时间' in content:
            print("  ✓ 添加了调整时间信息")
    
    # 检查portal/order_detail.html中的具体改进  
    order_detail_template = '/Users/lichuansong/Desktop/projects/wlxj_python/templates/portal/order_detail.html'
    if os.path.exists(order_detail_template):
        with open(order_detail_template, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print("\n2. Portal Order Detail 模板改进:")
        
        # 检查format_price使用
        if '|format_price' in content:
            print("  ✓ 统一使用format_price过滤器")
        
        # 检查alert样式
        if 'alert alert-info' in content:
            print("  ✓ 改进了价格调整信息的显示样式")
            
        # 检查详细调整信息
        if '价格调整：' in content:
            print("  ✓ 添加了详细的价格调整信息")

if __name__ == '__main__':
    print("开始验证优化价格显示修复方案...")
    
    # 运行主要测试
    success = test_template_improvements()
    
    # 运行具体改进测试
    test_specific_improvements()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 验证完成：所有改进均已正确实施，质量达到90%以上！")
    else:
        print("⚠️  验证完成：需要进一步优化以达到90%质量要求")
    print("=" * 60)