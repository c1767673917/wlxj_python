#!/usr/bin/env python3
"""
创建新的数据库结构（业务类型系统）
"""

from app import app, db
from models import User, Supplier, Order, Quote
from werkzeug.security import generate_password_hash

def create_new_database():
    """创建新的数据库结构"""
    with app.app_context():
        # 删除所有表（如果存在）
        db.drop_all()
        
        # 创建所有表
        db.create_all()
        print("数据库表创建成功")
        
        # 创建默认管理员
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            business_type='admin'
        )
        db.session.add(admin)
        
        # 创建示例用户
        test_users = [
            {'username': 'oil_user1', 'password': 'password123', 'business_type': 'oil'},
            {'username': 'oil_user2', 'password': 'password123', 'business_type': 'oil'},
            {'username': 'fast_user1', 'password': 'password123', 'business_type': 'fast_moving'},
        ]
        
        for user_data in test_users:
            user = User(
                username=user_data['username'],
                password=generate_password_hash(user_data['password']),
                business_type=user_data['business_type']
            )
            db.session.add(user)
        
        db.session.commit()
        print("默认用户创建成功")
        
        # 显示统计信息
        admin_count = User.query.filter_by(business_type='admin').count()
        oil_count = User.query.filter_by(business_type='oil').count()
        fast_count = User.query.filter_by(business_type='fast_moving').count()
        
        print(f"\n用户统计:")
        print(f"- 管理员: {admin_count}")
        print(f"- 油脂: {oil_count}")
        print(f"- 快消: {fast_count}")
        print(f"\n默认管理员账户: admin / admin123")
        print(f"测试账户密码统一为: password123")

if __name__ == '__main__':
    create_new_database()