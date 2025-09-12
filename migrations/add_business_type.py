#!/usr/bin/env python3
"""
业务类型系统数据迁移脚本
将用户隔离模式改为业务类型共享模式
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    """执行数据库迁移"""
    db_path = 'database.db'
    backup_path = f'database_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    
    # 1. 备份现有数据库
    if os.path.exists(db_path):
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"数据库已备份到: {backup_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 2. 修改users表结构
        print("正在修改users表结构...")
        cursor.execute("ALTER TABLE users RENAME COLUMN role TO business_type")
        cursor.execute("UPDATE users SET business_type = 'admin' WHERE business_type = 'admin'")
        cursor.execute("UPDATE users SET business_type = 'oil' WHERE business_type = 'user'")
        
        # 3. 为suppliers表添加business_type字段
        print("正在修改suppliers表结构...")
        cursor.execute("ALTER TABLE suppliers ADD COLUMN business_type VARCHAR(20) NOT NULL DEFAULT 'oil'")
        cursor.execute("""
            UPDATE suppliers SET business_type = (
                SELECT CASE 
                    WHEN u.business_type = 'admin' THEN 'oil'  
                    ELSE u.business_type 
                END
                FROM users u 
                WHERE u.id = suppliers.user_id
            )
        """)
        
        # 4. 为orders表添加business_type字段
        print("正在修改orders表结构...")
        cursor.execute("ALTER TABLE orders ADD COLUMN business_type VARCHAR(20) NOT NULL DEFAULT 'oil'")
        cursor.execute("""
            UPDATE orders SET business_type = (
                SELECT CASE 
                    WHEN u.business_type = 'admin' THEN 'oil'  
                    ELSE u.business_type 
                END
                FROM users u 
                WHERE u.id = orders.user_id
            )
        """)
        
        # 5. 添加索引
        print("正在添加索引...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_business_type ON suppliers(business_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_business_type ON orders(business_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_business_type ON users(business_type)")
        
        # 6. 清理测试数据（可选，根据需要执行）
        print("正在清理测试数据...")
        cursor.execute("DELETE FROM quotes")
        cursor.execute("DELETE FROM order_suppliers") 
        cursor.execute("DELETE FROM suppliers WHERE user_id != 1")  # 保留管理员创建的供应商
        cursor.execute("DELETE FROM orders WHERE user_id != 1")     # 保留管理员创建的订单
        cursor.execute("DELETE FROM users WHERE business_type != 'admin'")  # 保留管理员账户
        
        conn.commit()
        print("数据库迁移成功完成")
        
        # 7. 验证迁移结果
        cursor.execute("SELECT COUNT(*) FROM users WHERE business_type = 'admin'")
        admin_count = cursor.fetchone()[0]
        print(f"管理员账户数量: {admin_count}")
        
        cursor.execute("SELECT COUNT(*) FROM suppliers")
        supplier_count = cursor.fetchone()[0]
        print(f"供应商数量: {supplier_count}")
        
        cursor.execute("SELECT COUNT(*) FROM orders")
        order_count = cursor.fetchone()[0]
        print(f"订单数量: {order_count}")
        
    except Exception as e:
        conn.rollback()
        print(f"迁移失败: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()