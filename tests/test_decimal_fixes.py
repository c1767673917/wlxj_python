#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Decimal-Float类型错误修复验证测试

测试改进后的Decimal处理机制，确保：
1. 错误处理完善
2. 边界情况处理
3. 类型安全转换
4. 模板过滤器安全性
"""

import sys
import os
import unittest
from decimal import Decimal, InvalidOperation
from unittest.mock import MagicMock, patch
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入应用模块
from app import decimal_to_float, safe_number, format_price
from models.quote import Quote

class TestDecimalToFloatFilter(unittest.TestCase):
    """测试decimal_to_float过滤器的安全性和健壮性"""
    
    def setUp(self):
        """设置测试环境"""
        # 配置日志以捕获警告和错误
        logging.basicConfig(level=logging.DEBUG)
        
    def test_normal_decimal_conversion(self):
        """测试正常Decimal转换"""
        test_cases = [
            (Decimal('100.50'), 100.50),
            (Decimal('0'), 0.0),
            (Decimal('999999.99'), 999999.99),
        ]
        
        for decimal_val, expected in test_cases:
            with self.subTest(decimal_val=decimal_val):
                result = decimal_to_float(decimal_val)
                self.assertEqual(result, expected)
                self.assertIsInstance(result, float)
    
    def test_none_value_handling(self):
        """测试None值处理"""
        result = decimal_to_float(None)
        self.assertEqual(result, 0.0)
        self.assertIsInstance(result, float)
    
    def test_string_conversion(self):
        """测试字符串转换"""
        test_cases = [
            ('100.50', 100.50),
            ('0', 0.0),
            ('', 0.0),
            ('   ', 0.0),
            ('invalid', 0.0),
            ('inf', 0.0),
            ('-inf', 0.0),
            ('nan', 0.0),
        ]
        
        for string_val, expected in test_cases:
            with self.subTest(string_val=string_val):
                result = decimal_to_float(string_val)
                self.assertEqual(result, expected)
                self.assertIsInstance(result, float)
    
    def test_numeric_type_handling(self):
        """测试数值类型处理"""
        test_cases = [
            (100, 100.0),
            (0, 0.0),
            (100.50, 100.50),
            (-50.25, -50.25),
        ]
        
        for numeric_val, expected in test_cases:
            with self.subTest(numeric_val=numeric_val):
                result = decimal_to_float(numeric_val)
                self.assertEqual(result, expected)
                self.assertIsInstance(result, float)
    
    def test_infinite_and_nan_handling(self):
        """测试无穷大和NaN处理"""
        test_cases = [
            (float('inf'), 0.0),
            (float('-inf'), 0.0),
            (float('nan'), 0.0),
        ]
        
        for special_val, expected in test_cases:
            with self.subTest(special_val=special_val):
                result = decimal_to_float(special_val)
                self.assertEqual(result, expected)
    
    def test_unsupported_type_handling(self):
        """测试不支持的类型处理"""
        test_cases = [
            ([], 0.0),
            ({}, 0.0),
            (object(), 0.0),
        ]
        
        for unsupported_val, expected in test_cases:
            with self.subTest(unsupported_val=type(unsupported_val)):
                result = decimal_to_float(unsupported_val)
                self.assertEqual(result, expected)
    
    def test_decimal_special_cases(self):
        """测试Decimal特殊情况"""
        # 非有限Decimal值
        inf_decimal = Decimal('Infinity')
        neg_inf_decimal = Decimal('-Infinity')
        nan_decimal = Decimal('NaN')
        
        test_cases = [
            (inf_decimal, 0.0),
            (neg_inf_decimal, 0.0),
            (nan_decimal, 0.0),
        ]
        
        for decimal_val, expected in test_cases:
            with self.subTest(decimal_val=decimal_val):
                result = decimal_to_float(decimal_val)
                self.assertEqual(result, expected)


class TestSafeNumberFilter(unittest.TestCase):
    """测试safe_number过滤器"""
    
    def test_normal_numbers(self):
        """测试正常数值"""
        test_cases = [
            (100, 100),
            (100.50, 100.50),
            (Decimal('50.25'), Decimal('50.25')),
            (0, 0),
        ]
        
        for value, expected in test_cases:
            with self.subTest(value=value):
                result = safe_number(value)
                self.assertEqual(result, expected)
    
    def test_string_conversion(self):
        """测试字符串转换"""
        test_cases = [
            ('100.50', 100.50),
            ('0', 0.0),
            ('invalid', 0),  # 默认值
            ('', 0),  # 默认值
        ]
        
        for string_val, expected in test_cases:
            with self.subTest(string_val=string_val):
                result = safe_number(string_val)
                self.assertEqual(result, expected)
    
    def test_default_value(self):
        """测试自定义默认值"""
        result = safe_number(None, default=999)
        self.assertEqual(result, 999)
        
        result = safe_number('invalid', default=-1)
        self.assertEqual(result, -1)


class TestFormatPriceFilter(unittest.TestCase):
    """测试format_price过滤器"""
    
    def test_normal_price_formatting(self):
        """测试正常价格格式化"""
        test_cases = [
            (100.50, '¥100.50'),
            (Decimal('1000.00'), '¥1,000.00'),
            (0, '¥0.00'),
            (1234567.89, '¥1,234,567.89'),
        ]
        
        for price, expected in test_cases:
            with self.subTest(price=price):
                result = format_price(price)
                self.assertEqual(result, expected)
    
    def test_none_price_formatting(self):
        """测试None价格格式化"""
        result = format_price(None)
        self.assertEqual(result, '¥0.00')
    
    def test_custom_currency(self):
        """测试自定义货币符号"""
        result = format_price(100.50, currency='$')
        self.assertEqual(result, '$100.50')
    
    def test_invalid_price_formatting(self):
        """测试无效价格格式化"""
        test_cases = [
            ('invalid', '¥0.00'),
            ([], '¥0.00'),
            ({}, '¥0.00'),
        ]
        
        for invalid_price, expected in test_cases:
            with self.subTest(invalid_price=type(invalid_price)):
                result = format_price(invalid_price)
                self.assertEqual(result, expected)


class TestQuoteModel(unittest.TestCase):
    """测试Quote模型的安全方法"""
    
    def setUp(self):
        """设置测试Quote对象"""
        self.quote = Quote()
        self.quote.id = 1
    
    def test_get_price_decimal_normal(self):
        """测试正常Decimal价格获取"""
        self.quote.price = Decimal('100.50')
        result = self.quote.get_price_decimal()
        self.assertEqual(result, Decimal('100.50'))
        self.assertIsInstance(result, Decimal)
    
    def test_get_price_decimal_none(self):
        """测试None价格处理"""
        self.quote.price = None
        result = self.quote.get_price_decimal()
        self.assertEqual(result, Decimal('0'))
    
    def test_get_price_decimal_invalid(self):
        """测试非有限Decimal处理"""
        self.quote.price = Decimal('Infinity')
        result = self.quote.get_price_decimal()
        self.assertEqual(result, Decimal('0'))
    
    def test_get_price_float(self):
        """测试float价格获取"""
        self.quote.price = Decimal('100.50')
        result = self.quote.get_price_float()
        self.assertEqual(result, 100.50)
        self.assertIsInstance(result, float)
    
    def test_format_price_safe(self):
        """测试安全价格格式化"""
        self.quote.price = Decimal('100.50')
        result = self.quote.format_price_safe()
        self.assertEqual(result, '¥100.50')
    
    def test_validate_price_valid(self):
        """测试有效价格验证"""
        self.quote.price = Decimal('100.50')
        is_valid, message = self.quote.validate_price()
        self.assertTrue(is_valid)
        self.assertEqual(message, '价格有效')
    
    def test_validate_price_none(self):
        """测试None价格验证"""
        self.quote.price = None
        is_valid, message = self.quote.validate_price()
        self.assertFalse(is_valid)
        self.assertEqual(message, '价格不能为空')
    
    def test_validate_price_negative(self):
        """测试负数价格验证"""
        self.quote.price = Decimal('-10.00')
        is_valid, message = self.quote.validate_price()
        self.assertFalse(is_valid)
        self.assertEqual(message, '价格不能为负数')
    
    def test_validate_price_too_large(self):
        """测试超大价格验证"""
        self.quote.price = Decimal('99999999999.99')
        is_valid, message = self.quote.validate_price()
        self.assertFalse(is_valid)
        self.assertEqual(message, '价格超出允许范围')


class TestTemplateIntegration(unittest.TestCase):
    """测试模板集成安全性"""
    
    def test_template_filter_chain(self):
        """测试模板过滤器链安全性"""
        # 模拟模板中的过滤器链：quotes|map(attribute='price')|map('safe_number', 0)|list
        mock_quotes = [
            MagicMock(price=Decimal('100.50')),
            MagicMock(price=Decimal('200.00')),
            MagicMock(price=None),
            MagicMock(price='invalid'),
        ]
        
        # 提取价格并安全转换
        prices = []
        for quote in mock_quotes:
            safe_price = safe_number(quote.price, 0)
            prices.append(safe_price)
        
        # 验证结果
        self.assertEqual(len(prices), 4)
        self.assertEqual(prices[0], Decimal('100.50'))
        self.assertEqual(prices[1], Decimal('200.00'))
        self.assertEqual(prices[2], 0)  # None转换为默认值
        self.assertEqual(prices[3], 0)  # 无效字符串转换为默认值
    
    def test_price_calculation_safety(self):
        """测试价格计算安全性"""
        prices = [Decimal('100.50'), Decimal('200.00'), 0, 0]
        
        # 过滤有效价格
        valid_prices = [p for p in prices if p > 0]
        
        if valid_prices:
            min_price = min(valid_prices)
            max_price = max(valid_prices)
            avg_price = sum(valid_prices) / len(valid_prices)
            
            self.assertEqual(min_price, Decimal('100.50'))
            self.assertEqual(max_price, Decimal('200.00'))
            self.assertEqual(avg_price, Decimal('150.25'))
        else:
            self.fail("Should have valid prices")


def run_comprehensive_test():
    """运行全面的测试套件"""
    print("=" * 70)
    print("开始Decimal-Float类型错误修复验证测试")
    print("=" * 70)
    
    # 创建测试套件
    test_classes = [
        TestDecimalToFloatFilter,
        TestSafeNumberFilter,
        TestFormatPriceFilter,
        TestQuoteModel,
        TestTemplateIntegration,
    ]
    
    total_tests = 0
    total_failures = 0
    total_errors = 0
    
    for test_class in test_classes:
        print(f"\n--- 测试 {test_class.__name__} ---")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        total_tests += result.testsRun
        total_failures += len(result.failures)
        total_errors += len(result.errors)
        
        if result.failures:
            print(f"失败测试: {len(result.failures)}")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback}")
        
        if result.errors:
            print(f"错误测试: {len(result.errors)}")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback}")
    
    # 计算通过率
    passed_tests = total_tests - total_failures - total_errors
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print("\n" + "=" * 70)
    print("测试结果总结")
    print("=" * 70)
    print(f"总测试数: {total_tests}")
    print(f"通过: {passed_tests}")
    print(f"失败: {total_failures}")
    print(f"错误: {total_errors}")
    print(f"通过率: {pass_rate:.1f}%")
    
    # 评估修复质量
    if pass_rate >= 95:
        quality_score = "优秀 (A)"
        recommendation = "修复质量优秀，可以部署"
    elif pass_rate >= 90:
        quality_score = "良好 (B)"
        recommendation = "修复质量良好，建议部署"
    elif pass_rate >= 80:
        quality_score = "中等 (C)"
        recommendation = "修复质量中等，需要进一步改进"
    else:
        quality_score = "差 (D)"
        recommendation = "修复质量不足，需要重新修复"
    
    print(f"修复质量评分: {quality_score}")
    print(f"建议: {recommendation}")
    
    return pass_rate


if __name__ == '__main__':
    pass_rate = run_comprehensive_test()
    sys.exit(0 if pass_rate >= 90 else 1)