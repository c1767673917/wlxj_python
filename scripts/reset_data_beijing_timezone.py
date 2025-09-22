#!/usr/bin/env python3
"""
数据重置脚本 - 北京时区转换
清空现有测试数据并确保系统使用北京时间
"""

import sqlite3
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))

from utils.beijing_time_helper import BeijingTimeHelper

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/data_reset_{BeijingTimeHelper.get_backup_timestamp()}.log'),
        logging.StreamHandler()
    ]
)

def create_backup(db_path):
    """创建数据库备份"""
    try:
        backup_dir = Path(__file__).parent.parent / 'backup'
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = BeijingTimeHelper.get_backup_timestamp()
        backup_path = backup_dir / f'database_backup_before_reset_{timestamp}.db'
        
        import shutil
        shutil.copy2(db_path, backup_path)
        logging.info(f"数据库备份已创建: {backup_path}")
        return backup_path
    except Exception as e:
        logging.error(f"创建备份失败: {e}")
        raise

def reset_database(db_path):
    """重置数据库数据"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logging.info("开始清理数据库数据...")
        
        # 禁用外键约束
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # 删除数据（按依赖关系顺序）
        tables_to_clear = [
            ('quotes', '报价记录'),
            ('order_suppliers', '订单供应商关联'),
            ('orders', '订单'),
            ('suppliers', '供应商'),
        ]
        
        for table, description in tables_to_clear:
            cursor.execute(f"DELETE FROM {table}")
            deleted_count = cursor.rowcount
            logging.info(f"清理 {description} ({table}): {deleted_count} 条记录")
        
        # 清理非管理员用户
        cursor.execute("DELETE FROM users WHERE business_type != 'admin'")
        deleted_users = cursor.rowcount
        logging.info(f"清理非管理员用户: {deleted_users} 条记录")
        
        # 重置自增ID（如果sqlite_sequence表存在）
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
        if cursor.fetchone():
            reset_tables = ['quotes', 'orders', 'suppliers', 'users']
            for table in reset_tables:
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name = '{table}'")
                logging.info(f"重置表 {table} 的自增ID")
        else:
            logging.info("sqlite_sequence表不存在，跳过自增ID重置")
        
        # 重新启用外键约束
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # 提交更改
        conn.commit()
        logging.info("数据库重置完成")
        
        # 验证清理结果
        verify_cleanup(cursor)
        
    except Exception as e:
        logging.error(f"数据库重置失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def verify_cleanup(cursor):
    """验证清理结果"""
    logging.info("验证数据清理结果...")
    
    # 检查各表的记录数
    tables_to_check = [
        ('quotes', '报价'),
        ('orders', '订单'),
        ('suppliers', '供应商'),
        ('order_suppliers', '订单供应商关联')
    ]
    
    for table, description in tables_to_check:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        if count > 0:
            logging.warning(f"{description}表仍有 {count} 条记录")
        else:
            logging.info(f"{description}表已清空 ✓")
    
    # 检查用户表（应只保留管理员）
    cursor.execute("SELECT COUNT(*) FROM users WHERE business_type = 'admin'")
    admin_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE business_type != 'admin'")
    non_admin_count = cursor.fetchone()[0]
    
    logging.info(f"管理员用户: {admin_count} 个")
    logging.info(f"非管理员用户: {non_admin_count} 个")
    
    if non_admin_count > 0:
        logging.warning("仍有非管理员用户存在")

def create_test_admin_if_needed(db_path):
    """如果没有管理员用户，创建一个测试管理员"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查是否有管理员用户
        cursor.execute("SELECT COUNT(*) FROM users WHERE business_type = 'admin'")
        admin_count = cursor.fetchone()[0]
        
        if admin_count == 0:
            logging.info("未找到管理员用户，创建测试管理员...")
            
            from werkzeug.security import generate_password_hash
            
            # 创建测试管理员
            now = BeijingTimeHelper.now()
            password_hash = generate_password_hash('admin123')
            
            cursor.execute("""
                INSERT INTO users (username, password, business_type, created_at)
                VALUES (?, ?, ?, ?)
            """, ('admin', password_hash, 'admin', now))
            
            conn.commit()
            logging.info("测试管理员已创建 (用户名: admin, 密码: admin123)")
        else:
            logging.info(f"已存在 {admin_count} 个管理员用户")
            
    except Exception as e:
        logging.error(f"创建测试管理员失败: {e}")
        raise
    finally:
        conn.close()

def main():
    """主函数"""
    try:
        # 记录开始时间
        start_time = BeijingTimeHelper.now()
        logging.info(f"开始数据重置 - 北京时间: {BeijingTimeHelper.format_datetime(start_time)}")
        
        # 数据库路径
        db_path = Path(__file__).parent.parent / 'instance' / 'database.db'
        
        if not db_path.exists():
            logging.error(f"数据库文件不存在: {db_path}")
            return False
        
        # 创建备份
        backup_path = create_backup(db_path)
        
        # 重置数据库
        reset_database(db_path)
        
        # 创建测试管理员
        create_test_admin_if_needed(db_path)
        
        # 记录完成时间
        end_time = BeijingTimeHelper.now()
        duration = end_time - start_time
        
        logging.info(f"数据重置完成 - 北京时间: {BeijingTimeHelper.format_datetime(end_time)}")
        logging.info(f"耗时: {duration.total_seconds():.2f} 秒")
        logging.info(f"备份文件: {backup_path}")
        
        print("\n" + "="*60)
        print("数据重置完成！")
        print(f"开始时间: {BeijingTimeHelper.format_datetime(start_time)}")
        print(f"完成时间: {BeijingTimeHelper.format_datetime(end_time)}")
        print(f"备份文件: {backup_path}")
        print("="*60)
        
        return True
        
    except Exception as e:
        logging.error(f"数据重置失败: {e}")
        print(f"\n数据重置失败: {e}")
        return False

if __name__ == '__main__':
    print("北京时区转换 - 数据重置脚本")
    print("此脚本将清空所有测试数据并确保系统使用北京时间")
    
    confirm = input("确认执行数据重置？(输入 'YES' 继续): ")
    if confirm.upper() == 'YES':
        success = main()
        sys.exit(0 if success else 1)
    else:
        print("操作已取消")
        sys.exit(0)