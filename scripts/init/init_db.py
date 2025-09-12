#!/usr/bin/env python3
"""
数据库初始化脚本
用于创建数据库表结构和初始数据
"""

from app import app, db
from models import User, Supplier, Order, Quote
from werkzeug.security import generate_password_hash

def init_database():
    """初始化数据库"""
    with app.app_context():
        print("正在创建数据库表...")
        
        # 删除所有表（如果存在）
        db.drop_all()
        
        # 创建所有表
        db.create_all()
        
        print("数据库表创建完成！")
        
        # 创建默认管理员账户
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                password=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin_user)
            print("创建默认管理员账户: admin / admin123")
        
        # 创建测试用户
        test_user = User.query.filter_by(username='test').first()
        if not test_user:
            test_user = User(
                username='test',
                password=generate_password_hash('test123'),
                role='user'
            )
            db.session.add(test_user)
            print("创建测试用户账户: test / test123")
        
        # 提交更改
        db.session.commit()
        print("初始数据创建完成！")
        
        print("\n数据库初始化成功！")
        print("=" * 50)
        print("管理员账户: admin / admin123")
        print("测试账户: test / test123")
        print("=" * 50)

if __name__ == '__main__':
    init_database()