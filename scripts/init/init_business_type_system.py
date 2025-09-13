#!/usr/bin/env python3
"""
业务类型系统初始化脚本
创建默认管理员和示例业务用户
"""

from app import app, db
from models import User
from werkzeug.security import generate_password_hash

def init_business_type_system():
    """初始化业务类型系统"""
    with app.app_context():
        # 创建默认管理员
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password=generate_password_hash('admin123'),
                business_type='admin'
            )
            db.session.add(admin)
            print("创建默认管理员账户: admin / admin123")
        else:
            print("管理员账户已存在")
        
        # 创建示例用户（可选）
        test_users = [
            {'username': 'oil_user1', 'password': 'password123', 'business_type': 'oil'},
            {'username': 'oil_user2', 'password': 'password123', 'business_type': 'oil'},
            {'username': 'fast_user1', 'password': 'password123', 'business_type': 'fast_moving'},
        ]
        
        for user_data in test_users:
            if not User.query.filter_by(username=user_data['username']).first():
                user = User(
                    username=user_data['username'],
                    password=generate_password_hash(user_data['password']),
                    business_type=user_data['business_type']
                )
                db.session.add(user)
                print(f"创建测试用户: {user_data['username']} / {user_data['password']} ({user_data['business_type']})")
            else:
                print(f"用户 {user_data['username']} 已存在")
        
        db.session.commit()
        print("业务类型系统初始化完成")
        
        # 显示用户统计
        admin_count = User.query.filter_by(business_type='admin').count()
        oil_count = User.query.filter_by(business_type='oil').count()
        fast_count = User.query.filter_by(business_type='fast_moving').count()
        
        print(f"\n用户统计:")
        print(f"- 管理员: {admin_count}")
        print(f"- 油脂: {oil_count}")
        print(f"- 快消: {fast_count}")

if __name__ == '__main__':
    init_business_type_system()