#!/usr/bin/env python3
"""
业务类型系统功能验证测试
"""

from app import app, db
from models import User, Supplier, Order
from utils.auth import business_type_filter

def test_business_type_system():
    """测试业务类型系统"""
    with app.app_context():
        print("=== 业务类型系统功能验证测试 ===\n")
        
        # 1. 测试用户模型
        print("1. 用户模型测试:")
        users = User.query.all()
        for user in users:
            print(f"   - {user.username}: {user.get_business_type_display()} (is_admin: {user.is_admin()})")
        
        # 2. 创建测试供应商
        print("\n2. 创建测试供应商:")
        
        # 获取测试用户
        oil_user1 = User.query.filter_by(username='oil_user1').first()
        oil_user2 = User.query.filter_by(username='oil_user2').first()
        fast_user1 = User.query.filter_by(username='fast_user1').first()
        admin_user = User.query.filter_by(username='admin').first()
        
        # 创建不同业务类型的供应商
        test_suppliers = [
            {'name': '石油供应商A', 'user': oil_user1, 'business_type': 'oil'},
            {'name': '石油供应商B', 'user': oil_user2, 'business_type': 'oil'},
            {'name': '快消品供应商A', 'user': fast_user1, 'business_type': 'fast_moving'},
            {'name': '管理员供应商', 'user': admin_user, 'business_type': 'oil'},
        ]
        
        for supplier_data in test_suppliers:
            supplier = Supplier(
                name=supplier_data['name'],
                user_id=supplier_data['user'].id,
                business_type=supplier_data['business_type']
            )
            db.session.add(supplier)
            print(f"   - 创建供应商: {supplier_data['name']} ({supplier_data['business_type']})")
        
        # 创建测试订单
        print("\n3. 创建测试订单:")
        test_orders = [
            {'order_no': 'ORD001', 'warehouse': '食用油仓库A', 'goods': '大豆油', 'user': oil_user1, 'business_type': 'oil'},
            {'order_no': 'ORD002', 'warehouse': '食用油仓库B', 'goods': '花生油', 'user': oil_user2, 'business_type': 'oil'},
            {'order_no': 'ORD003', 'warehouse': '快消仓库', 'goods': '洗发水', 'user': fast_user1, 'business_type': 'fast_moving'},
        ]
        
        for order_data in test_orders:
            order = Order(
                order_no=order_data['order_no'],
                warehouse=order_data['warehouse'],
                goods=order_data['goods'],
                delivery_address='测试地址',
                user_id=order_data['user'].id,
                business_type=order_data['business_type']
            )
            db.session.add(order)
            print(f"   - 创建订单: {order_data['order_no']} ({order_data['business_type']})")
        
        db.session.commit()
        
        # 4. 测试权限过滤
        print("\n4. 权限过滤测试:")
        
        # 模拟不同用户查看数据
        print("   油脂用户oil_user1可见的供应商:")
        with app.test_request_context():
            # 模拟当前用户为oil_user1
            from flask_login import login_user
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = str(oil_user1.id)
                    sess['_fresh'] = True
                
                # 直接测试business_type过滤
                oil_suppliers = Supplier.query.filter_by(business_type='oil').all()
                for supplier in oil_suppliers:
                    print(f"     - {supplier.name}")
        
        print("   快消品用户fast_user1可见的供应商:")
        fast_suppliers = Supplier.query.filter_by(business_type='fast_moving').all()
        for supplier in fast_suppliers:
            print(f"     - {supplier.name}")
        
        print("   管理员可见的所有供应商:")
        all_suppliers = Supplier.query.all()
        for supplier in all_suppliers:
            print(f"     - {supplier.name} ({supplier.business_type})")
        
        # 5. 数据隔离验证
        print("\n5. 数据隔离验证:")
        oil_orders = Order.query.filter_by(business_type='oil').all()
        fast_orders = Order.query.filter_by(business_type='fast_moving').all()
        
        print(f"   油脂订单数量: {len(oil_orders)}")
        for order in oil_orders:
            print(f"     - {order.order_no}: {order.goods}")
        
        print(f"   快消品订单数量: {len(fast_orders)}")
        for order in fast_orders:
            print(f"     - {order.order_no}: {order.goods}")
        
        # 6. 统计信息
        print("\n6. 系统统计:")
        total_users = User.query.count()
        total_suppliers = Supplier.query.count()
        total_orders = Order.query.count()
        
        print(f"   总用户数: {total_users}")
        print(f"   总供应商数: {total_suppliers}")
        print(f"   总订单数: {total_orders}")
        
        by_type_stats = {}
        for btype in ['oil', 'fast_moving']:
            supplier_count = Supplier.query.filter_by(business_type=btype).count()
            order_count = Order.query.filter_by(business_type=btype).count()
            by_type_stats[btype] = {'suppliers': supplier_count, 'orders': order_count}
        
        for btype, stats in by_type_stats.items():
            type_name = '油脂' if btype == 'oil' else '快消'
            print(f"   {type_name}: 供应商{stats['suppliers']}个, 订单{stats['orders']}个")
        
        print("\n=== 测试完成 ===")

if __name__ == '__main__':
    test_business_type_system()