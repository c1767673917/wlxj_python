#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成测试数据脚本
生成100条订单和对应的报价数据
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Supplier, Order, Quote
from datetime import datetime, timedelta
import random
from decimal import Decimal

# 测试数据配置
WAREHOUSES = [
    "上海港保税仓", "宁波港保税仓", "青岛港保税仓", "天津港保税仓", 
    "深圳港保税仓", "广州港保税仓", "大连港保税仓", "厦门港保税仓"
]

GOODS_LIST = [
    "大豆油 1000吨", "玉米油 800吨", "菜籽油 600吨", "花生油 500吨",
    "葵花籽油 400吨", "芝麻油 200吨", "橄榄油 100吨", "亚麻籽油 300吨",
    "椰子油 250吨", "棕榈油 1200吨", "豆粕 2000吨", "菜粕 1500吨",
    "花生粕 800吨", "棉粕 600吨", "胡麻粕 400吨"
]

DELIVERY_ADDRESSES = [
    "北京市朝阳区建国门外大街1号", "上海市浦东新区陆家嘴环路1000号",
    "广州市天河区天河北路233号", "深圳市福田区深南大道6008号",
    "杭州市西湖区文三路259号", "南京市鼓楼区中山路321号",
    "成都市高新区天府大道北段966号", "武汉市武昌区中南路99号",
    "西安市雁塔区科技路33号", "青岛市市南区香港中路76号",
    "大连市中山区人民路15号", "宁波市鄞州区首南街道"
]

DELIVERY_TIMES = ["1-3天", "3-5天", "5-7天", "7-10天", "10-15天", "15-20天"]

REMARKS_TEMPLATES = [
    "货物质量优良，包装完好",
    "支持第三方检验",
    "可提供质量检测报告",
    "含运输保险",
    "支持分批发货",
    "价格已含税费",
    "需要预付50%定金",
    "支持长期合作优惠",
    "24小时内确认订单",
    "提供售后服务保障"
]

def generate_orders_and_quotes():
    """生成100条订单和对应的报价"""
    
    with app.app_context():
        # 获取现有用户和供应商
        oil_users = User.query.filter_by(business_type='oil').all()
        oil_suppliers = Supplier.query.filter_by(business_type='oil').all()
        
        if not oil_users:
            print("错误：没有找到油脂业务类型的用户")
            return
        
        if not oil_suppliers:
            print("错误：没有找到油脂业务类型的供应商")
            return
        
        print(f"找到 {len(oil_users)} 个油脂用户，{len(oil_suppliers)} 个油脂供应商")
        
        orders_created = 0
        quotes_created = 0
        
        # 生成100条订单
        for i in range(100):
            try:
                # 随机选择用户
                user = random.choice(oil_users)
                
                # 随机选择仓库、货物、收货地址
                warehouse = random.choice(WAREHOUSES)
                goods = random.choice(GOODS_LIST)
                delivery_address = random.choice(DELIVERY_ADDRESSES)
                
                # 创建订单
                order = Order(
                    order_no=f"TEMP{datetime.now().strftime('%y%m%d')}{i+1:03d}",
                    warehouse=warehouse,
                    goods=goods,
                    delivery_address=delivery_address,
                    status='active',
                    user_id=user.id,
                    business_type='oil',
                    created_at=datetime.now() - timedelta(days=random.randint(0, 30))
                )
                
                db.session.add(order)
                db.session.flush()  # 获取订单ID
                
                # 生成正式订单号
                order.order_no = order.generate_order_no()
                
                orders_created += 1
                
                # 为每个订单生成2-5个报价
                num_quotes = random.randint(2, min(5, len(oil_suppliers)))
                selected_suppliers = random.sample(oil_suppliers, num_quotes)
                
                for supplier in selected_suppliers:
                    # 生成随机报价
                    base_price = random.randint(50000, 500000)  # 基础价格5万-50万
                    price_variation = random.uniform(0.8, 1.2)  # 价格浮动范围
                    final_price = Decimal(str(round(base_price * price_variation, 2)))
                    
                    delivery_time = random.choice(DELIVERY_TIMES)
                    remarks = random.choice(REMARKS_TEMPLATES)
                    
                    quote = Quote(
                        order_id=order.id,
                        supplier_id=supplier.id,
                        price=final_price,
                        delivery_time=delivery_time,
                        remarks=remarks,
                        created_at=order.created_at + timedelta(hours=random.randint(1, 48))
                    )
                    
                    db.session.add(quote)
                    quotes_created += 1
                
                # 随机选择一些订单设置为已完成状态
                if random.random() < 0.3:  # 30%的订单设为已完成
                    # 获取该订单的所有报价，选择最低价格的供应商
                    order_quotes = Quote.query.filter_by(order_id=order.id).all()
                    if order_quotes:
                        lowest_quote = min(order_quotes, key=lambda q: q.price)
                        order.status = 'completed'
                        order.selected_supplier_id = lowest_quote.supplier_id
                        order.selected_price = lowest_quote.price
                
                # 每20条订单提交一次
                if (i + 1) % 20 == 0:
                    db.session.commit()
                    print(f"已生成 {i + 1} 条订单...")
                    
            except Exception as e:
                db.session.rollback()
                print(f"生成第 {i + 1} 条订单时出错: {str(e)}")
                continue
        
        # 最终提交
        try:
            db.session.commit()
            print(f"\n数据生成完成！")
            print(f"成功创建 {orders_created} 条订单")
            print(f"成功创建 {quotes_created} 条报价")
            
            # 统计信息
            total_orders = Order.query.count()
            total_quotes = Quote.query.count()
            completed_orders = Order.query.filter_by(status='completed').count()
            active_orders = Order.query.filter_by(status='active').count()
            
            print(f"\n数据库统计:")
            print(f"订单总数: {total_orders}")
            print(f"报价总数: {total_quotes}")
            print(f"已完成订单: {completed_orders}")
            print(f"进行中订单: {active_orders}")
            
        except Exception as e:
            db.session.rollback()
            print(f"提交数据时出错: {str(e)}")

if __name__ == "__main__":
    print("开始生成测试数据...")
    generate_orders_and_quotes()
    print("测试数据生成完成！")