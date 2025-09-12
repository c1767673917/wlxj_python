from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Order, Quote, Supplier
from utils.auth import business_type_filter
from sqlalchemy import func, and_
from decimal import Decimal, InvalidOperation
import logging

# 创建蓝图
quote_bp = Blueprint('quote', __name__, url_prefix='/quotes')

@quote_bp.route('/')
@login_required
def index():
    """报价对比首页"""
    # 获取同业务类型的所有进行中的订单及其报价
    query = db.session.query(Order).join(Quote, Order.id == Quote.order_id, isouter=True).filter(
        Order.status == 'active'  # 只显示进行中的订单
    ).group_by(
        Order.id
    ).having(func.count(Quote.id) > 0).order_by(Order.created_at.desc())
    orders_with_quotes = business_type_filter(query, Order).all()
    
    return render_template('quotes/index.html', orders=orders_with_quotes)

@quote_bp.route('/order/<int:order_id>')
@login_required
def compare(order_id):
    """订单报价对比页面"""
    query = Order.query.filter_by(id=order_id)
    order = business_type_filter(query, Order).first_or_404()
    
    # 获取所有报价，按价格排序
    quotes = Quote.query.filter_by(order_id=order.id).order_by(Quote.price.asc()).all()
    
    if not quotes:
        flash('该订单还没有收到任何报价', 'warning')
        return redirect(url_for('order.detail', order_id=order.id))
    
    # 计算统计数据（安全处理）
    try:
        # 获取有效价格
        valid_prices = []
        for quote in quotes:
            is_valid, _ = quote.validate_price()
            if is_valid:
                valid_prices.append(quote.get_price_decimal())
            else:
                logging.warning(f"Invalid price in quote {quote.id}: {quote.price}")
        
        if valid_prices:
            avg_price = sum(valid_prices) / len(valid_prices)
            # 计算方差：Var(X) = E[(X-μ)²] = E[X²] - μ²
            variance = Decimal('0')
            if len(valid_prices) > 1:
                sum_squares = sum(price * price for price in valid_prices)
                variance = (sum_squares / len(valid_prices)) - (avg_price * avg_price)
                # 确保方差非负（处理精度误差）
                if variance < 0:
                    variance = Decimal('0')
            
            stats = {
                'count': len(quotes),
                'valid_count': len(valid_prices),
                'min_price': min(valid_prices),
                'max_price': max(valid_prices),
                'avg_price': avg_price,
                'price_range': max(valid_prices) - min(valid_prices),
                'variance': variance,
                'std_deviation': variance.sqrt() if variance > 0 else Decimal('0')
            }
        else:
            stats = {
                'count': len(quotes),
                'valid_count': 0,
                'min_price': Decimal('0'),
                'max_price': Decimal('0'),
                'avg_price': Decimal('0'),
                'price_range': Decimal('0'),
                'variance': Decimal('0'),
                'std_deviation': Decimal('0')
            }
    except Exception as e:
        logging.error(f"Error calculating quote statistics: {e}")
        stats = {
            'count': len(quotes),
            'valid_count': 0,
            'min_price': Decimal('0'),
            'max_price': Decimal('0'),
            'avg_price': Decimal('0'),
            'price_range': Decimal('0'),
            'variance': Decimal('0'),
            'std_deviation': Decimal('0')
        }
    
    return render_template('quotes/compare.html', order=order, quotes=quotes, stats=stats)

@quote_bp.route('/analysis')
@login_required
def analysis():
    """报价分析页面"""
    # 获取统计数据
    query = Order.query
    total_orders = business_type_filter(query, Order).count()
    
    query = db.session.query(Order).join(Quote).group_by(Order.id)
    orders_with_quotes = business_type_filter(query, Order).count()
    
    query = Quote.query.join(Order)
    total_quotes = business_type_filter(query, Order).count()
    
    query = Order.query.filter_by(status='completed')
    completed_orders = business_type_filter(query, Order).count()
    
    # 获取供应商报价统计 - 优化查询和业务类型过滤
    try:
        base_query = db.session.query(
            Supplier.name,
            func.count(Quote.id).label('quote_count'),
            func.avg(Quote.price).label('avg_price'),
            func.min(Quote.price).label('min_price'),
            func.max(Quote.price).label('max_price'),
            func.sum(
                db.case([(Order.selected_supplier_id == Supplier.id, 1)], else_=0)
            ).label('win_count')
        ).select_from(Supplier).join(Quote).join(Order)
        
        # 应用业务类型过滤
        if not current_user.is_admin():
            base_query = base_query.filter(
                and_(
                    Supplier.business_type == current_user.business_type,
                    Order.business_type == current_user.business_type
                )
            )
        
        supplier_stats = base_query.group_by(Supplier.id, Supplier.name).all()
    except Exception as e:
        logging.error(f"查询供应商统计数据失败: {e}")
        supplier_stats = []
    
    # 最近的报价活动 - 优化查询
    try:
        query = Quote.query.join(Order).order_by(Quote.created_at.desc()).limit(10)
        recent_quotes = business_type_filter(query, Order).all()
    except Exception as e:
        logging.error(f"查询最近报价活动失败: {e}")
        recent_quotes = []
    
    return render_template('quotes/analysis.html', 
                         total_orders=total_orders,
                         orders_with_quotes=orders_with_quotes,
                         total_quotes=total_quotes,
                         completed_orders=completed_orders,
                         supplier_stats=supplier_stats,
                         recent_quotes=recent_quotes)

@quote_bp.route('/export/<int:order_id>')
@login_required
def export_quotes(order_id):
    """导出订单报价数据"""
    query = Order.query.filter_by(id=order_id)
    order = business_type_filter(query, Order).first_or_404()
    quotes = Quote.query.filter_by(order_id=order.id).order_by(Quote.price.asc()).all()
    
    if not quotes:
        flash('该订单没有报价数据可导出', 'warning')
        return redirect(url_for('quote.compare', order_id=order.id))
    
    # 这里可以实现CSV或Excel导出
    # 简化版本：返回JSON数据
    export_data = {
        'order': {
            'order_no': order.order_no,
            'goods': order.goods,
            'warehouse': order.warehouse,
            'delivery_address': order.delivery_address,
            'created_at': order.created_at.isoformat()
        },
        'quotes': [{
            'supplier_name': quote.supplier.name,
            'price': quote.get_price_float(),  # 使用安全转换方法
            'delivery_time': quote.delivery_time,
            'remarks': quote.remarks,
            'created_at': quote.created_at.isoformat()
        } for quote in quotes]
    }
    
    return jsonify(export_data)

@quote_bp.route('/supplier/<int:supplier_id>/history')
@login_required
def supplier_history(supplier_id):
    """供应商报价历史"""
    # 验证供应商存在性和业务类型权限
    try:
        query = Supplier.query.filter_by(id=supplier_id)
        supplier = business_type_filter(query, Supplier).first_or_404()
    except Exception as e:
        logging.error(f"查询供应商失败 (ID: {supplier_id}): {e}")
        flash('供应商不存在或无权限访问', 'error')
        return redirect(url_for('supplier.index'))
    
    # 获取该供应商的所有报价 - 优化查询逻辑
    try:
        query = Quote.query.join(Order).filter(
            and_(
                Quote.supplier_id == supplier.id,
                # 确保关联的订单符合业务类型权限
                Order.business_type == current_user.business_type if not current_user.is_admin() else True
            )
        ).order_by(Quote.created_at.desc())
        quotes = query.all()
    except Exception as e:
        logging.error(f"查询供应商报价历史失败 (供应商ID: {supplier_id}): {e}")
        quotes = []
    
    if not quotes:
        flash('该供应商还没有报价记录', 'info')
        return redirect(url_for('supplier.details', supplier_id=supplier.id))
    
    # 计算统计数据（强化错误处理和性能优化）
    stats = _calculate_supplier_stats(quotes, supplier.id)
    
    return render_template('quotes/supplier_history.html', 
                         supplier=supplier, 
                         quotes=quotes, 
                         stats=stats)

def _calculate_supplier_stats(quotes, supplier_id):
    """计算供应商统计数据的辅助函数"""
    try:
        # 批量验证价格，减少重复调用
        valid_prices = []
        win_count = 0
        
        for quote in quotes:
            try:
                is_valid, _ = quote.validate_price()
                if is_valid:
                    valid_prices.append(quote.get_price_decimal())
                
                # 检查是否为中标报价
                if quote.order and quote.order.selected_supplier_id == supplier_id:
                    win_count += 1
            except Exception as e:
                logging.warning(f"处理报价数据时出错 (Quote ID: {quote.id}): {e}")
                continue
        
        total_quotes = len(quotes)
        if valid_prices:
            avg_price = sum(valid_prices) / len(valid_prices)
            stats = {
                'total_quotes': total_quotes,
                'valid_quotes': len(valid_prices),
                'win_count': win_count,
                'win_rate': round((win_count / total_quotes * 100), 2) if total_quotes > 0 else 0,
                'avg_price': avg_price,
                'min_price': min(valid_prices),
                'max_price': max(valid_prices)
            }
        else:
            stats = {
                'total_quotes': total_quotes,
                'valid_quotes': 0,
                'win_count': win_count,
                'win_rate': round((win_count / total_quotes * 100), 2) if total_quotes > 0 else 0,
                'avg_price': Decimal('0'),
                'min_price': Decimal('0'),
                'max_price': Decimal('0')
            }
        
        logging.info(f"供应商 {supplier_id} 统计计算完成: {stats}")
        return stats
        
    except Exception as e:
        logging.error(f"计算供应商统计数据时发生错误 (供应商ID: {supplier_id}): {e}")
        return {
            'total_quotes': len(quotes) if quotes else 0,
            'valid_quotes': 0,
            'win_count': 0,
            'win_rate': 0,
            'avg_price': Decimal('0'),
            'min_price': Decimal('0'),
            'max_price': Decimal('0')
        }