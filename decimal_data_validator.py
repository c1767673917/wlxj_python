#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Decimal数据验证和监控工具

用于检查数据库中的Decimal数据完整性，识别潜在问题，
并提供修复建议。
"""

import sys
import os
from decimal import Decimal, InvalidOperation
import logging
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'decimal_validation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

class DecimalDataValidator:
    """Decimal数据验证器"""
    
    def __init__(self, app_context=None):
        """初始化验证器"""
        self.app_context = app_context
        self.issues = []
        
    def validate_quote_prices(self, db, Quote):
        """验证Quote表中的价格数据"""
        logger.info("开始验证Quote表价格数据...")
        
        issues = []
        total_quotes = 0
        invalid_quotes = 0
        
        try:
            quotes = Quote.query.all()
            total_quotes = len(quotes)
            
            for quote in quotes:
                total_quotes += 1
                quote_issues = []
                
                # 检查价格是否为None
                if quote.price is None:
                    quote_issues.append("价格为None")
                    invalid_quotes += 1
                
                # 检查价格类型
                elif not isinstance(quote.price, Decimal):
                    quote_issues.append(f"价格类型错误: {type(quote.price)}")
                    invalid_quotes += 1
                
                # 检查价格是否为有限数值
                elif isinstance(quote.price, Decimal) and not quote.price.is_finite():
                    quote_issues.append(f"价格为非有限数值: {quote.price}")
                    invalid_quotes += 1
                
                # 检查价格是否为负数
                elif quote.price < 0:
                    quote_issues.append(f"价格为负数: {quote.price}")
                    invalid_quotes += 1
                
                # 检查价格是否超出范围
                elif quote.price > Decimal('9999999999.99'):
                    quote_issues.append(f"价格超出范围: {quote.price}")
                    invalid_quotes += 1
                
                if quote_issues:
                    issues.append({
                        'quote_id': quote.id,
                        'order_id': quote.order_id,
                        'supplier_id': quote.supplier_id,
                        'price': quote.price,
                        'issues': quote_issues
                    })
            
            logger.info(f"Quote价格验证完成: 总数 {total_quotes}, 无效 {invalid_quotes}")
            return {
                'total': total_quotes,
                'invalid': invalid_quotes,
                'valid_rate': ((total_quotes - invalid_quotes) / total_quotes * 100) if total_quotes > 0 else 100,
                'issues': issues
            }
            
        except Exception as e:
            logger.error(f"验证Quote价格时出错: {e}")
            return {
                'total': 0,
                'invalid': 0,
                'valid_rate': 0,
                'issues': [],
                'error': str(e)
            }
    
    def check_template_compatibility(self, templates_dir):
        """检查模板文件的兼容性"""
        logger.info("检查模板文件兼容性...")
        
        issues = []
        deprecated_filters = ['decimal_to_float']
        recommended_filters = ['safe_number', 'format_price']
        
        try:
            # 遍历模板目录
            for root, dirs, files in os.walk(templates_dir):
                for file in files:
                    if file.endswith('.html'):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, templates_dir)
                        
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        file_issues = []
                        
                        # 检查是否使用了deprecated过滤器
                        for filter_name in deprecated_filters:
                            if filter_name in content:
                                file_issues.append(f"使用了deprecated过滤器: {filter_name}")
                        
                        # 检查是否存在unsafe的数学运算
                        unsafe_patterns = [
                            '|sum /',
                            '|length )',
                            '|min|max',
                            'prices|map(attribute=\'price\')'
                        ]
                        
                        for pattern in unsafe_patterns:
                            if pattern in content:
                                file_issues.append(f"可能存在unsafe的数学运算: {pattern}")
                        
                        if file_issues:
                            issues.append({
                                'file': rel_path,
                                'issues': file_issues
                            })
            
            logger.info(f"模板兼容性检查完成: 发现 {len(issues)} 个文件有问题")
            return issues
            
        except Exception as e:
            logger.error(f"检查模板兼容性时出错: {e}")
            return []
    
    def generate_fix_recommendations(self, quote_issues, template_issues):
        """生成修复建议"""
        recommendations = []
        
        # Quote数据修复建议
        if quote_issues['invalid'] > 0:
            recommendations.append({
                'type': 'data',
                'priority': 'high',
                'title': 'Quote价格数据修复',
                'description': f'发现 {quote_issues["invalid"]} 个无效价格记录',
                'actions': [
                    '1. 备份数据库',
                    '2. 运行数据清理脚本修复无效价格',
                    '3. 为Quote模型添加数据验证约束',
                    '4. 实施价格输入验证'
                ]
            })
        
        # 模板修复建议
        if template_issues:
            recommendations.append({
                'type': 'template',
                'priority': 'medium',
                'title': '模板安全性改进',
                'description': f'发现 {len(template_issues)} 个模板文件需要改进',
                'actions': [
                    '1. 将decimal_to_float替换为safe_number或format_price',
                    '2. 添加数据验证和边界检查',
                    '3. 使用安全的数学运算方法',
                    '4. 添加错误处理和默认值'
                ]
            })
        
        # 监控建议
        recommendations.append({
            'type': 'monitoring',
            'priority': 'low',
            'title': '持续监控',
            'description': '建立数据质量监控机制',
            'actions': [
                '1. 定期运行数据验证脚本',
                '2. 设置数据质量告警',
                '3. 记录和分析错误日志',
                '4. 建立数据质量仪表板'
            ]
        })
        
        return recommendations
    
    def generate_report(self, quote_results, template_issues):
        """生成验证报告"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        report = f"""
===================================================================
Decimal数据验证报告
===================================================================
生成时间: {timestamp}

1. Quote价格数据验证结果
-------------------------------------------------------------------
总Quote数量: {quote_results.get('total', 0)}
无效Quote数量: {quote_results.get('invalid', 0)}
数据有效率: {quote_results.get('valid_rate', 0):.1f}%

"""
        
        # 详细问题列表
        if quote_results.get('issues'):
            report += "发现的问题:\n"
            for i, issue in enumerate(quote_results['issues'][:10], 1):  # 只显示前10个
                report += f"  {i}. Quote ID {issue['quote_id']}: {', '.join(issue['issues'])}\n"
            
            if len(quote_results['issues']) > 10:
                report += f"  ... 还有 {len(quote_results['issues']) - 10} 个问题\n"
        
        report += f"""
2. 模板兼容性检查结果
-------------------------------------------------------------------
有问题的模板文件数: {len(template_issues)}

"""
        
        # 模板问题详情
        if template_issues:
            report += "模板文件问题:\n"
            for issue in template_issues[:5]:  # 只显示前5个
                report += f"  - {issue['file']}: {', '.join(issue['issues'])}\n"
            
            if len(template_issues) > 5:
                report += f"  ... 还有 {len(template_issues) - 5} 个文件有问题\n"
        
        # 修复建议
        recommendations = self.generate_fix_recommendations(quote_results, template_issues)
        
        report += f"""
3. 修复建议
-------------------------------------------------------------------
"""
        
        for rec in recommendations:
            report += f"""
{rec['title']} (优先级: {rec['priority']})
{rec['description']}
执行步骤:
"""
            for action in rec['actions']:
                report += f"  {action}\n"
        
        # 总体评估
        overall_score = self.calculate_overall_score(quote_results, template_issues)
        
        report += f"""
4. 总体评估
-------------------------------------------------------------------
数据质量评分: {overall_score['score']:.1f}/100
评估等级: {overall_score['grade']}
建议行动: {overall_score['action']}

===================================================================
"""
        
        return report
    
    def calculate_overall_score(self, quote_results, template_issues):
        """计算总体质量评分"""
        # 数据质量分数 (70%)
        data_score = quote_results.get('valid_rate', 0) * 0.7
        
        # 模板安全分数 (30%)
        template_score = max(0, 100 - len(template_issues) * 10) * 0.3
        
        total_score = data_score + template_score
        
        if total_score >= 90:
            grade = "优秀 (A)"
            action = "质量优秀，保持当前标准"
        elif total_score >= 80:
            grade = "良好 (B)"
            action = "质量良好，可考虑小幅改进"
        elif total_score >= 70:
            grade = "中等 (C)"
            action = "质量中等，建议及时改进"
        else:
            grade = "差 (D)"
            action = "质量较差，需要立即改进"
        
        return {
            'score': total_score,
            'grade': grade,
            'action': action
        }


def main():
    """主函数"""
    print("启动Decimal数据验证工具...")
    
    try:
        # 检查是否在Flask应用上下文中
        try:
            from app import app
            from models import db, Quote
            
            with app.app_context():
                validator = DecimalDataValidator()
                
                # 验证Quote价格数据
                quote_results = validator.validate_quote_prices(db, Quote)
                
                # 检查模板兼容性
                templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
                template_issues = validator.check_template_compatibility(templates_dir)
                
                # 生成报告
                report = validator.generate_report(quote_results, template_issues)
                
                # 输出报告
                print(report)
                
                # 保存报告到文件
                report_file = f'decimal_validation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
                with open(report_file, 'w', encoding='utf-8') as f:
                    f.write(report)
                
                print(f"\n详细报告已保存到: {report_file}")
                
        except ImportError as e:
            logger.error(f"无法导入应用模块: {e}")
            print("请确保在正确的目录中运行此脚本")
            
    except Exception as e:
        logger.error(f"验证过程中出错: {e}")
        print(f"验证失败: {e}")


if __name__ == '__main__':
    main()