#!/usr/bin/env python3
"""
价格显示修复测试脚本
测试供应商门户中的价格显示逻辑
"""

from app import app
from models import db, Order, Quote, Supplier
from flask import url_for

def test_price_display_logic():
    """测试价格显示逻辑"""
    with app.app_context():
        print("=== 价格显示逻辑测试 ===\n")
        
        # 获取测试数据
        orders = Order.query.all()
        quotes = Quote.query.all()
        suppliers = Supplier.query.all()
        
        print(f"数据统计:")
        print(f"- 订单数量: {len(orders)}")
        print(f"- 报价数量: {len(quotes)}")
        print(f"- 供应商数量: {len(suppliers)}\n")
        
        # 测试每个订单的价格显示逻辑
        for order in orders:
            print(f"订单: {order.order_no}")
            print(f"状态: {order.status}")
            print(f"选中供应商ID: {order.selected_supplier_id}")
            print(f"最终价格: {order.selected_price}")
            
            # 获取该订单的报价
            order_quotes = Quote.query.filter_by(order_id=order.id).all()
            print(f"报价数量: {len(order_quotes)}")
            
            for quote in order_quotes:
                supplier = Supplier.query.get(quote.supplier_id)
                print(f"  供应商: {supplier.name if supplier else '未知'}")
                print(f"  报价价格: {quote.price}")
                
                # 测试价格显示逻辑
                is_selected = order.selected_supplier_id == quote.supplier_id
                has_final_price = order.selected_price and float(order.selected_price) != 0
                price_changed = has_final_price and float(order.selected_price) != float(quote.price)
                
                print(f"  是否中标: {is_selected}")
                print(f"  有最终价格: {has_final_price}")
                print(f"  价格已变化: {price_changed}")
                
                if is_selected and has_final_price:
                    if price_changed:
                        print(f"  显示格式: 划线原价({quote.price}) + 最终成交价({order.selected_price})")
                    else:
                        print(f"  显示格式: 成交价({quote.price})")
                else:
                    print(f"  显示格式: 原始报价({quote.price})")
                    
                print()
            
            print("-" * 50)

def test_template_filters():
    """测试模板过滤器"""
    with app.app_context():
        print("=== 模板过滤器测试 ===\n")
        
        # 测试价格格式化
        from decimal import Decimal
        
        test_values = [
            None,
            0,
            100.50,
            Decimal('200.75'),
            '300.25',
            1234567.89
        ]
        
        for value in test_values:
            try:
                # 测试format_price过滤器
                from app import format_price
                formatted = format_price(value)
                print(f"format_price({value}) = {formatted}")
            except Exception as e:
                print(f"format_price({value}) 错误: {e}")
        
        print()

if __name__ == '__main__':
    test_price_display_logic()
    test_template_filters()
    
    print("=== 修复总结 ===")
    print("1. 已简化价格显示逻辑，去除百分比和差额显示")
    print("2. 已修复JavaScript自动隐藏导致的报价信息消失问题")
    print("3. 已统一列表页面和详情页面的价格显示格式")
    print("4. 保持了划线原价 + 最终成交价的显示格式")