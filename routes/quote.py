from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Order, Quote, Supplier
from sqlalchemy import func
from decimal import Decimal, InvalidOperation
import logging

# 创建蓝图
quote_bp = Blueprint('quote', __name__, url_prefix='/quotes')

@quote_bp.route('/')
@login_required
def index():
    """报价对比首页"""
    # 获取用户的所有订单及其报价
    orders_with_quotes = db.session.query(Order).filter_by(
        user_id=current_user.id
    ).join(Quote, Order.id == Quote.order_id, isouter=True).group_by(
        Order.id
    ).having(func.count(Quote.id) > 0).order_by(Order.created_at.desc()).all()
    
    return render_template('quotes/index.html', orders=orders_with_quotes)

@quote_bp.route('/order/<int:order_id>')
@login_required
def compare(order_id):
    """订单报价对比页面"""
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    
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
    total_orders = Order.query.filter_by(user_id=current_user.id).count()
    orders_with_quotes = db.session.query(Order).filter_by(
        user_id=current_user.id
    ).join(Quote).group_by(Order.id).count()
    
    total_quotes = Quote.query.join(Order).filter(Order.user_id == current_user.id).count()
    completed_orders = Order.query.filter_by(user_id=current_user.id, status='completed').count()
    
    # 获取供应商报价统计
    supplier_stats = db.session.query(
        Supplier.name,
        func.count(Quote.id).label('quote_count'),
        func.avg(Quote.price).label('avg_price'),
        func.min(Quote.price).label('min_price'),
        func.max(Quote.price).label('max_price'),
        func.count(
            db.case([(Order.selected_supplier_id == Supplier.id, 1)], else_=0)
        ).label('win_count')
    ).join(Quote).join(Order).filter(
        Order.user_id == current_user.id
    ).group_by(Supplier.id, Supplier.name).all()
    
    # 最近的报价活动
    recent_quotes = Quote.query.join(Order).filter(
        Order.user_id == current_user.id
    ).order_by(Quote.created_at.desc()).limit(10).all()
    
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
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
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
    supplier = Supplier.query.filter_by(id=supplier_id, user_id=current_user.id).first_or_404()
    
    # 获取该供应商的所有报价
    quotes = Quote.query.join(Order).filter(
        Quote.supplier_id == supplier.id,
        Order.user_id == current_user.id
    ).order_by(Quote.created_at.desc()).all()
    
    if not quotes:
        flash('该供应商还没有报价记录', 'info')
        return redirect(url_for('supplier.details', supplier_id=supplier.id))
    
    # 计算统计数据（安全处理）
    try:
        valid_prices = []
        for quote in quotes:
            is_valid, _ = quote.validate_price()
            if is_valid:
                valid_prices.append(quote.get_price_decimal())
                
        win_count = sum(1 for quote in quotes if quote.order.selected_supplier_id == supplier.id)
        
        if valid_prices:
            stats = {
                'total_quotes': len(quotes),
                'valid_quotes': len(valid_prices),
                'win_count': win_count,
                'win_rate': (win_count / len(quotes) * 100) if quotes else 0,
                'avg_price': sum(valid_prices) / len(valid_prices),
                'min_price': min(valid_prices),
                'max_price': max(valid_prices)
            }
        else:
            stats = {
                'total_quotes': len(quotes),
                'valid_quotes': 0,
                'win_count': win_count,
                'win_rate': (win_count / len(quotes) * 100) if quotes else 0,
                'avg_price': Decimal('0'),
                'min_price': Decimal('0'),
                'max_price': Decimal('0')
            }
    except Exception as e:
        logging.error(f"Error calculating supplier statistics: {e}")
        stats = {
            'total_quotes': len(quotes),
            'valid_quotes': 0,
            'win_count': 0,
            'win_rate': 0,
            'avg_price': Decimal('0'),
            'min_price': Decimal('0'),
            'max_price': Decimal('0')
        }
    
    return render_template('quotes/supplier_history.html', 
                         supplier=supplier, 
                         quotes=quotes, 
                         stats=stats)