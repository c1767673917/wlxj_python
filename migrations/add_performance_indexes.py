#!/usr/bin/env python3
"""
性能优化索引迁移脚本
为高频查询字段添加单字段索引，提升系统查询性能
"""

import sqlite3
import os
import logging
import shutil
from datetime import datetime

def add_performance_indexes():
    """添加性能优化索引"""
    db_path = 'database.db'
    backup_path = f'database_backup_indexes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    
    # 备份数据库
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)
        logging.info(f"数据库已备份到: {backup_path}")
    else:
        logging.warning(f"数据库文件不存在: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 为orders表添加索引
        logging.info("为orders表添加性能索引...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_business_type ON orders(business_type)")
        
        # 为quotes表添加索引
        logging.info("为quotes表添加性能索引...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_order_id ON quotes(order_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_supplier_id ON quotes(supplier_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_price ON quotes(price)")
        
        # 为suppliers表添加索引
        logging.info("为suppliers表添加性能索引...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_user_id ON suppliers(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_business_type ON suppliers(business_type)")
        
        # 为order_suppliers关联表添加索引
        logging.info("为order_suppliers表添加性能索引...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_suppliers_order_id ON order_suppliers(order_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_suppliers_supplier_id ON order_suppliers(supplier_id)")
        
        conn.commit()
        logging.info("性能索引添加完成")
        
        # 验证索引
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = cursor.fetchall()
        logging.info(f"当前索引数量: {len(indexes)}")
        for idx in indexes:
            logging.info(f"索引: {idx[0]}")
            
        return True
        
    except Exception as e:
        conn.rollback()
        logging.error(f"添加索引失败: {str(e)}")
        raise
    finally:
        conn.close()

def validate_index_performance():
    """验证索引性能提升"""
    db_path = 'database.db'
    if not os.path.exists(db_path):
        logging.error("数据库文件不存在，无法验证性能")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 测试常见查询的执行计划
        test_queries = [
            "EXPLAIN QUERY PLAN SELECT * FROM orders WHERE status = 'active'",
            "EXPLAIN QUERY PLAN SELECT * FROM orders WHERE business_type = 'oil'",
            "EXPLAIN QUERY PLAN SELECT * FROM orders ORDER BY created_at DESC LIMIT 10",
            "EXPLAIN QUERY PLAN SELECT * FROM quotes WHERE order_id = 1",
            "EXPLAIN QUERY PLAN SELECT * FROM quotes ORDER BY price ASC LIMIT 1",
            "EXPLAIN QUERY PLAN SELECT * FROM suppliers WHERE business_type = 'oil'",
        ]
        
        logging.info("执行查询计划分析...")
        for query in test_queries:
            cursor.execute(query)
            plan = cursor.fetchall()
            logging.info(f"查询: {query.replace('EXPLAIN QUERY PLAN ', '')}")
            for step in plan:
                logging.info(f"  执行计划: {step}")
        
        return True
        
    except Exception as e:
        logging.error(f"性能验证失败: {str(e)}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/migration.log'),
            logging.StreamHandler()
        ]
    )
    
    try:
        logging.info("开始数据库索引优化迁移...")
        success = add_performance_indexes()
        
        if success:
            logging.info("索引添加成功，开始性能验证...")
            validate_index_performance()
            logging.info("数据库索引优化迁移完成")
        else:
            logging.error("索引添加失败")
            
    except Exception as e:
        logging.error(f"迁移过程发生错误: {str(e)}")
        raise