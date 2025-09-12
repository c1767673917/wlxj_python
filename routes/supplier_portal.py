from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from models import db, Supplier, Order, Quote
from datetime import datetime

# 创建蓝图
portal_bp = Blueprint('portal', __name__, url_prefix='/portal')

@portal_bp.route('/supplier/<access_code>')
def supplier_portal(access_code):
    """供应商专属门户入口"""
    supplier = Supplier.query.filter_by(access_code=access_code).first_or_404()
    
    # 将供应商信息存储到session中，用于后续验证
    session['supplier_id'] = supplier.id
    session['supplier_name'] = supplier.name
    session['access_code'] = access_code
    
    # 获取该供应商需要报价的订单（活跃状态且已关联的订单）
    orders = Order.query.join(Order.suppliers).filter(
        Supplier.id == supplier.id,
        Order.status == 'active'
    ).order_by(Order.created_at.desc()).all()
    
    # 获取该供应商已提交的报价
    quotes = Quote.query.filter_by(supplier_id=supplier.id).all()
    quoted_order_ids = [quote.order_id for quote in quotes]
    
    return render_template('portal/dashboard.html', 
                         supplier=supplier, 
                         orders=orders,
                         quoted_order_ids=quoted_order_ids,
                         quotes=quotes)

@portal_bp.route('/order/<int:order_id>')
def order_detail(order_id):
    """订单详情页面（供应商视图）"""
    # 验证供应商权限
    if 'supplier_id' not in session:
        flash('访问已过期，请重新访问', 'error')
        return redirect(url_for('index'))
    
    supplier_id = session['supplier_id']
    supplier = Supplier.query.get(supplier_id)
    
    # 获取订单并验证供应商是否有权限访问
    order = Order.query.join(Order.suppliers).filter(
        Order.id == order_id,
        Supplier.id == supplier_id
    ).first_or_404()
    
    # 获取该供应商对此订单的报价
    quote = Quote.query.filter_by(order_id=order.id, supplier_id=supplier_id).first()
    
    # 获取所有报价数量（不显示具体报价内容）
    total_quotes = Quote.query.filter_by(order_id=order.id).count()
    
    return render_template('portal/order_detail.html', 
                         supplier=supplier,
                         order=order, 
                         quote=quote,
                         total_quotes=total_quotes)

@portal_bp.route('/order/<int:order_id>/quote', methods=['GET', 'POST'])
def submit_quote(order_id):
    """提交或更新报价"""
    # 验证供应商权限
    if 'supplier_id' not in session:
        flash('访问已过期，请重新访问', 'error')
        return redirect(url_for('index'))
    
    supplier_id = session['supplier_id']
    supplier = Supplier.query.get(supplier_id)
    
    # 获取订单并验证权限
    order = Order.query.join(Order.suppliers).filter(
        Order.id == order_id,
        Supplier.id == supplier_id,
        Order.status == 'active'  # 只能对活跃订单报价
    ).first_or_404()
    
    # 获取现有报价
    existing_quote = Quote.query.filter_by(order_id=order.id, supplier_id=supplier_id).first()
    
    if request.method == 'POST':
        price = request.form.get('price', type=float)
        delivery_time = request.form.get('delivery_time', '').strip()
        remarks = request.form.get('remarks', '').strip()
        
        # 基础价格验证
        if not price or price <= 0:
            flash('请输入有效的报价金额', 'error')
            return render_template('portal/quote_form.html', 
                                 supplier=supplier, 
                                 order=order, 
                                 quote=existing_quote)
        
        # 价格上限验证
        if price > 9999999999.99:
            flash('报价金额超出系统允许的最大值', 'error')
            return render_template('portal/quote_form.html', 
                                 supplier=supplier, 
                                 order=order, 
                                 quote=existing_quote)
        
        # 价格变动合理性检查（仅在更新报价时）
        price_warnings = []
        if existing_quote:
            try:
                original_price = existing_quote.get_price_decimal()
                price_warnings = Quote.validate_price_change(original_price, price)
            except Exception as e:
                import logging
                logging.warning(f'价格对比计算失败: {e}')
        
        if existing_quote:
            # 更新现有报价
            existing_quote.price = price
            existing_quote.delivery_time = delivery_time if delivery_time else None
            existing_quote.remarks = remarks if remarks else None
            existing_quote.created_at = datetime.utcnow()  # 更新时间
            
            # 显示价格警告和成功消息
            if price_warnings:
                for warning in price_warnings:
                    flash(warning, 'warning')
            flash('报价更新成功', 'success')
        else:
            # 创建新报价
            new_quote = Quote(
                order_id=order.id,
                supplier_id=supplier_id,
                price=price,
                delivery_time=delivery_time if delivery_time else None,
                remarks=remarks if remarks else None
            )
            db.session.add(new_quote)
            flash('报价提交成功', 'success')
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            import logging
            logging.error(f'报价保存失败: {e}')
            flash('报价保存失败，请重试', 'error')
            return render_template('portal/quote_form.html', 
                                 supplier=supplier, 
                                 order=order, 
                                 quote=existing_quote)
        
        # 可以在这里添加通知采购方的逻辑
        notify_buyer_new_quote(order, supplier, price)
        
        return redirect(url_for('portal.order_detail', order_id=order.id))
    
    return render_template('portal/quote_form.html', 
                         supplier=supplier, 
                         order=order, 
                         quote=existing_quote)

@portal_bp.route('/quotes')
def my_quotes():
    """我的报价列表"""
    # 验证供应商权限
    if 'supplier_id' not in session:
        flash('访问已过期，请重新访问', 'error')
        return redirect(url_for('index'))
    
    supplier_id = session['supplier_id']
    supplier = Supplier.query.get(supplier_id)
    
    # 获取所有报价
    quotes = Quote.query.filter_by(supplier_id=supplier_id).order_by(Quote.created_at.desc()).all()
    
    return render_template('portal/quotes.html', supplier=supplier, quotes=quotes)

@portal_bp.route('/logout')
def logout():
    """供应商登出"""
    session.pop('supplier_id', None)
    session.pop('supplier_name', None)
    session.pop('access_code', None)
    flash('您已安全退出', 'info')
    return redirect(url_for('index'))

def notify_buyer_new_quote(order, supplier, price):
    """通知采购方有新报价（可扩展实现）"""
    # 这里可以实现通知采购方的逻辑
    # 例如：发送邮件、系统内通知等
    pass