"""
数据库工具函数
提供数据库维护和修复功能
"""

from models import db, User, Supplier, Order, Quote
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

# 删除操作锁，防止并发删除
_deletion_locks = {}
_deletion_lock = threading.Lock()

def safe_delete_user(user_id):
    """
    安全删除用户及其关联数据
    使用优化的事务管理和并发保护机制
    
    Args:
        user_id: 用户ID
        
    Returns:
        tuple: (success: bool, message: str, data: dict)
    """
    # 并发删除保护
    with _deletion_lock:
        if user_id in _deletion_locks:
            return False, "该用户正在被删除中，请稍后再试", {}
        _deletion_locks[user_id] = datetime.now()
    
    try:
        # 验证用户存在性
        user = User.query.get(user_id)
        if not user:
            return False, "用户不存在", {}
            
        username = user.username
        deletion_start_time = datetime.now()
        
        logger.info(f"开始删除用户: {username} (ID: {user_id}) - 开始时间: {deletion_start_time}")
        
        # 预统计关联数据（使用子查询优化性能）
        user_order_ids = db.session.query(Order.id).filter_by(user_id=user_id).subquery()
        
        supplier_count = Supplier.query.filter_by(user_id=user_id).count()
        order_count = Order.query.filter_by(user_id=user_id).count()
        quote_count = Quote.query.filter(Quote.order_id.in_(user_order_ids)).count()
        
        logger.info(f"关联数据统计: 供应商 {supplier_count}个, 订单 {order_count}个, 报价 {quote_count}个")
        
        # 执行原子化删除操作
        try:
            # 使用批量删除提升性能
            deletion_stats = _perform_batch_deletion(user_id, user_order_ids)
            
            # 删除用户本身
            db.session.delete(user)
            
            # 提交所有更改
            db.session.commit()
            
            deletion_end_time = datetime.now()
            deletion_duration = (deletion_end_time - deletion_start_time).total_seconds()
            
            # 构建删除结果数据
            result_data = {
                'username': username,
                'supplier_count': supplier_count,
                'order_count': order_count,
                'quote_count': quote_count,
                'deletion_duration': deletion_duration,
                'deletion_stats': deletion_stats
            }
            
            # 执行删除后的完整性验证
            is_valid, validation_result = validate_user_deletion_integrity(user_id, result_data)
            result_data['validation_result'] = validation_result
            
            if is_valid:
                logger.info(f"用户 {username} 删除成功且完整性验证通过 - 耗时: {deletion_duration:.3f}秒")
                logger.info(f"删除统计: {deletion_stats}")
                return True, "用户删除成功", result_data
            else:
                # 删除完成但存在完整性问题
                integrity_issues = validation_result.get('integrity_issues', [])
                logger.warning(f"用户 {username} 删除完成但存在完整性问题: {integrity_issues}")
                
                warning_msg = "用户删除完成，但检测到数据完整性问题"
                if len(integrity_issues) > 0:
                    warning_msg += f": {'; '.join(integrity_issues[:3])}"  # 只显示前3个问题
                
                return True, warning_msg, result_data
            
        except (SQLAlchemyError, StaleDataError) as e:
            db.session.rollback()
            error_msg = f"数据库事务失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, {}
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"删除操作异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, {}
        
    except Exception as e:
        error_msg = f"用户删除预处理失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg, {}
        
    finally:
        # 清理并发锁
        with _deletion_lock:
            _deletion_locks.pop(user_id, None)


def _perform_batch_deletion(user_id, user_order_ids):
    """
    执行批量删除操作
    
    Args:
        user_id: 用户ID
        user_order_ids: 用户订单ID子查询
        
    Returns:
        dict: 删除统计信息
    """
    deletion_stats = {
        'quotes_deleted': 0,
        'order_supplier_relations_cleared': 0,
        'orders_deleted': 0,
        'suppliers_deleted': 0
    }
    
    # Step 1: 批量删除所有相关报价
    quotes_deleted = Quote.query.filter(Quote.order_id.in_(user_order_ids)).delete(synchronize_session=False)
    deletion_stats['quotes_deleted'] = quotes_deleted
    logger.debug(f"批量删除报价: {quotes_deleted} 条")
    
    # Step 2: 清除订单与供应商的多对多关系
    user_orders = Order.query.filter_by(user_id=user_id).all()
    for order in user_orders:
        if order.suppliers:
            order.suppliers.clear()
            deletion_stats['order_supplier_relations_cleared'] += 1
    logger.debug(f"清除订单供应商关联关系: {deletion_stats['order_supplier_relations_cleared']} 个订单")
    
    # Step 3: 批量删除用户订单
    orders_deleted = Order.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    deletion_stats['orders_deleted'] = orders_deleted
    logger.debug(f"批量删除订单: {orders_deleted} 条")
    
    # Step 4: 批量删除用户供应商
    suppliers_deleted = Supplier.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    deletion_stats['suppliers_deleted'] = suppliers_deleted
    logger.debug(f"批量删除供应商: {suppliers_deleted} 条")
    
    return deletion_stats


def get_user_deletion_status(user_id):
    """
    获取用户删除状态
    
    Args:
        user_id: 用户ID
        
    Returns:
        dict: 用户状态信息
    """
    try:
        with _deletion_lock:
            is_being_deleted = user_id in _deletion_locks
            deletion_start_time = _deletion_locks.get(user_id)
        
        user_exists = User.query.get(user_id) is not None
        
        status_info = {
            'user_exists': user_exists,
            'is_being_deleted': is_being_deleted,
            'deletion_start_time': deletion_start_time,
            'can_delete': user_exists and not is_being_deleted
        }
        
        return status_info
        
    except Exception as e:
        logger.error(f"检查用户删除状态失败: {str(e)}")
        return {
            'user_exists': False,
            'is_being_deleted': False,
            'deletion_start_time': None,
            'can_delete': False,
            'error': str(e)
        }


def cleanup_stale_deletion_locks(max_age_minutes=5):
    """
    清理陈旧的删除锁
    
    Args:
        max_age_minutes: 锁的最大存在时间（分钟）
        
    Returns:
        int: 清理的锁数量
    """
    try:
        current_time = datetime.now()
        cleaned_count = 0
        
        with _deletion_lock:
            stale_locks = []
            for user_id, lock_time in _deletion_locks.items():
                age_minutes = (current_time - lock_time).total_seconds() / 60
                if age_minutes > max_age_minutes:
                    stale_locks.append(user_id)
            
            for user_id in stale_locks:
                _deletion_locks.pop(user_id)
                cleaned_count += 1
                logger.warning(f"清理陈旧的删除锁: 用户ID {user_id}")
        
        if cleaned_count > 0:
            logger.info(f"清理了 {cleaned_count} 个陈旧的删除锁")
            
        return cleaned_count
        
    except Exception as e:
        logger.error(f"清理删除锁失败: {str(e)}")
        return 0


def validate_user_deletion_integrity(user_id, data):
    """
    验证用户删除操作的完整性
    
    Args:
        user_id: 删除的用户ID
        data: 删除操作的统计数据
        
    Returns:
        tuple: (is_valid: bool, validation_result: dict)
    """
    try:
        validation_result = {
            'user_deleted': False,
            'orphaned_suppliers': 0,
            'orphaned_orders': 0,
            'orphaned_quotes': 0,
            'integrity_issues': []
        }
        
        # 检查用户是否已被删除
        user_still_exists = User.query.get(user_id) is not None
        validation_result['user_deleted'] = not user_still_exists
        
        if user_still_exists:
            validation_result['integrity_issues'].append("用户未被成功删除")
        
        # 检查是否存在孤立数据
        orphaned_suppliers = Supplier.query.filter_by(user_id=user_id).count()
        orphaned_orders = Order.query.filter_by(user_id=user_id).count()
        
        # 通过子查询检查孤立报价
        if orphaned_orders > 0:
            order_ids = [order.id for order in Order.query.filter_by(user_id=user_id).all()]
            orphaned_quotes = Quote.query.filter(Quote.order_id.in_(order_ids)).count()
        else:
            orphaned_quotes = 0
        
        validation_result.update({
            'orphaned_suppliers': orphaned_suppliers,
            'orphaned_orders': orphaned_orders,
            'orphaned_quotes': orphaned_quotes
        })
        
        # 检查完整性问题
        if orphaned_suppliers > 0:
            validation_result['integrity_issues'].append(f"发现 {orphaned_suppliers} 个孤立供应商")
        
        if orphaned_orders > 0:
            validation_result['integrity_issues'].append(f"发现 {orphaned_orders} 个孤立订单")
            
        if orphaned_quotes > 0:
            validation_result['integrity_issues'].append(f"发现 {orphaned_quotes} 个孤立报价")
        
        # 验证统计数据一致性
        if 'deletion_stats' in data:
            stats = data['deletion_stats']
            expected_suppliers = data.get('supplier_count', 0)
            expected_orders = data.get('order_count', 0)
            expected_quotes = data.get('quote_count', 0)
            
            if stats.get('suppliers_deleted', 0) != expected_suppliers:
                validation_result['integrity_issues'].append(
                    f"供应商删除数量不匹配: 期望 {expected_suppliers}, 实际 {stats.get('suppliers_deleted', 0)}"
                )
                
            if stats.get('orders_deleted', 0) != expected_orders:
                validation_result['integrity_issues'].append(
                    f"订单删除数量不匹配: 期望 {expected_orders}, 实际 {stats.get('orders_deleted', 0)}"
                )
                
            if stats.get('quotes_deleted', 0) != expected_quotes:
                validation_result['integrity_issues'].append(
                    f"报价删除数量不匹配: 期望 {expected_quotes}, 实际 {stats.get('quotes_deleted', 0)}"
                )
        
        is_valid = len(validation_result['integrity_issues']) == 0 and validation_result['user_deleted']
        
        if is_valid:
            logger.info(f"用户 {user_id} 删除完整性验证通过")
        else:
            logger.warning(f"用户 {user_id} 删除完整性验证失败: {validation_result['integrity_issues']}")
        
        return is_valid, validation_result
        
    except Exception as e:
        logger.error(f"删除完整性验证失败: {str(e)}")
        return False, {
            'user_deleted': False,
            'orphaned_suppliers': 0,
            'orphaned_orders': 0,
            'orphaned_quotes': 0,
            'integrity_issues': [f"验证过程异常: {str(e)}"],
            'validation_error': str(e)
        }

def check_data_integrity():
    """
    检查数据完整性
    
    Returns:
        dict: 完整性检查结果
    """
    try:
        results = {}
        
        # 检查孤立的供应商（user_id不存在）
        orphaned_suppliers = db.session.query(Supplier).outerjoin(User).filter(User.id.is_(None)).all()
        results['orphaned_suppliers'] = len(orphaned_suppliers)
        
        # 检查孤立的订单（user_id不存在）
        orphaned_orders = db.session.query(Order).outerjoin(User).filter(User.id.is_(None)).all()
        results['orphaned_orders'] = len(orphaned_orders)
        
        # 检查孤立的报价（order_id或supplier_id不存在）
        orphaned_quotes_order = db.session.query(Quote).outerjoin(Order).filter(Order.id.is_(None)).all()
        orphaned_quotes_supplier = db.session.query(Quote).outerjoin(Supplier).filter(Supplier.id.is_(None)).all()
        results['orphaned_quotes_order'] = len(orphaned_quotes_order)
        results['orphaned_quotes_supplier'] = len(orphaned_quotes_supplier)
        
        logger.info(f"数据完整性检查完成: {results}")
        return results
        
    except Exception as e:
        logger.error(f"数据完整性检查失败: {str(e)}", exc_info=True)
        return {'error': str(e)}

def cleanup_orphaned_data():
    """
    清理孤立数据
    
    Returns:
        dict: 清理结果统计
    """
    try:
        results = {}
        
        # 清理孤立的报价（订单不存在）
        orphaned_quotes_order = Quote.query.filter(~Quote.order_id.in_(
            db.session.query(Order.id)
        )).all()
        if orphaned_quotes_order:
            for quote in orphaned_quotes_order:
                db.session.delete(quote)
            results['deleted_quotes_order'] = len(orphaned_quotes_order)
            logger.info(f"删除了 {len(orphaned_quotes_order)} 个孤立报价（订单不存在）")
        
        # 清理孤立的报价（供应商不存在）
        orphaned_quotes_supplier = Quote.query.filter(~Quote.supplier_id.in_(
            db.session.query(Supplier.id)
        )).all()
        if orphaned_quotes_supplier:
            for quote in orphaned_quotes_supplier:
                db.session.delete(quote)
            results['deleted_quotes_supplier'] = len(orphaned_quotes_supplier)
            logger.info(f"删除了 {len(orphaned_quotes_supplier)} 个孤立报价（供应商不存在）")
        
        # 清理孤立的供应商（用户不存在）
        orphaned_suppliers = Supplier.query.filter(~Supplier.user_id.in_(
            db.session.query(User.id)
        )).all()
        if orphaned_suppliers:
            for supplier in orphaned_suppliers:
                db.session.delete(supplier)
            results['deleted_suppliers'] = len(orphaned_suppliers)
            logger.info(f"删除了 {len(orphaned_suppliers)} 个孤立供应商")
        
        # 清理孤立的订单（用户不存在）
        orphaned_orders = Order.query.filter(~Order.user_id.in_(
            db.session.query(User.id)
        )).all()
        if orphaned_orders:
            for order in orphaned_orders:
                db.session.delete(order)
            results['deleted_orders'] = len(orphaned_orders)
            logger.info(f"删除了 {len(orphaned_orders)} 个孤立订单")
        
        # 提交所有更改
        db.session.commit()
        
        logger.info(f"孤立数据清理完成: {results}")
        return results
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"清理孤立数据失败: {str(e)}", exc_info=True)
        return {'error': str(e)}