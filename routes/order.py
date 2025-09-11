from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Order, Supplier, order_suppliers
from datetime import datetime
import requests
import json
import logging
import traceback
import time
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from requests.exceptions import RequestException, Timeout, ConnectionError

# 创建蓝图
order_bp = Blueprint('order', __name__, url_prefix='/orders')

@order_bp.route('/')
@login_required
def index():
    """订单列表页面"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    
    query = Order.query.filter_by(user_id=current_user.id)
    
    if status:
        query = query.filter_by(status=status)
    
    orders = query.order_by(Order.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False)
    
    return render_template('orders/index.html', orders=orders, status=status)

@order_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    """创建新订单 - 带完整异常处理和事务回滚"""
    if request.method == 'POST':
        # 开始事务
        try:
            warehouse = request.form.get('warehouse', '').strip()
            goods = request.form.get('goods', '').strip()
            delivery_address = request.form.get('delivery_address', '').strip()
            supplier_ids = request.form.getlist('supplier_ids')
            
            # 数据验证
            if not all([warehouse, goods, delivery_address]):
                flash('请填写所有必填字段', 'error')
                suppliers = Supplier.query.filter_by(user_id=current_user.id).all()
                return render_template('orders/create.html', suppliers=suppliers)
            
            if not supplier_ids:
                flash('请至少选择一个供应商', 'error')
                suppliers = Supplier.query.filter_by(user_id=current_user.id).all()
                return render_template('orders/create.html', suppliers=suppliers)
            
            # 验证供应商ID是否有效
            supplier_ids = [int(sid) for sid in supplier_ids if sid.isdigit()]
            if not supplier_ids:
                flash('选择的供应商无效', 'error')
                suppliers = Supplier.query.filter_by(user_id=current_user.id).all()
                return render_template('orders/create.html', suppliers=suppliers)
            
            # 创建订单对象
            order = Order(
                order_no=Order.generate_temp_order_no(),
                warehouse=warehouse,
                goods=goods,
                delivery_address=delivery_address,
                user_id=current_user.id
            )
            
            # 数据验证
            validation_errors = order.validate_order_data()
            if validation_errors:
                for error in validation_errors:
                    flash(error, 'error')
                suppliers = Supplier.query.filter_by(user_id=current_user.id).all()
                return render_template('orders/create.html', suppliers=suppliers)
            
            # 验证用户是否拥有这些供应商
            selected_suppliers = Supplier.query.filter(
                Supplier.id.in_(supplier_ids),
                Supplier.user_id == current_user.id
            ).all()
            
            if len(selected_suppliers) != len(supplier_ids):
                flash('选择的供应商中包含无效项目', 'error')
                suppliers = Supplier.query.filter_by(user_id=current_user.id).all()
                return render_template('orders/create.html', suppliers=suppliers)
            
            # 开始数据库事务
            db.session.add(order)
            db.session.flush()  # 获取订单ID但不提交
            
            # 生成正式订单号（基于ID确保唯一性）
            order.order_no = order.generate_order_no()
            
            # 关联选中的供应商
            for supplier in selected_suppliers:
                order.suppliers.append(supplier)
            
            # 提交事务
            db.session.commit()
            
            logging.info(f"订单创建成功: {order.order_no}, 用户: {current_user.id}, 供应商数量: {len(selected_suppliers)}")
            
            # 异步发送通知给供应商（不影响主流程）
            try:
                success_count, failed_suppliers = notify_suppliers(order, selected_suppliers)
                if failed_suppliers:
                    notification_status = f"已通知 {success_count} 个供应商，{len(failed_suppliers)} 个通知失败"
                else:
                    notification_status = f"已成功通知 {success_count} 个供应商"
            except Exception as notify_error:
                logging.error(f"发送供应商通知失败: {str(notify_error)}")
                notification_status = "订单创建成功，但通知发送失败"
            
            flash(f'订单 {order.order_no} 创建成功，{notification_status}', 'success')
            return redirect(url_for('order.detail', order_id=order.id))
            
        except IntegrityError as e:
            db.session.rollback()
            logging.error(f"订单创建失败 - 数据完整性错误: {str(e)}")
            flash('订单创建失败：数据冲突，请重试', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"订单创建失败 - 数据库错误: {str(e)}")
            flash('订单创建失败：数据库错误，请稍后重试', 'error')
        except ValueError as e:
            db.session.rollback()
            logging.error(f"订单创建失败 - 数据验证错误: {str(e)}")
            flash(f'订单创建失败：{str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            logging.error(f"订单创建失败 - 未知错误: {str(e)}")
            logging.error(f"错误详情: {traceback.format_exc()}")
            flash('订单创建失败：系统错误，请联系管理员', 'error')
        
        # 出错时返回表单
        try:
            suppliers = Supplier.query.filter_by(user_id=current_user.id).all()
        except Exception:
            suppliers = []
        return render_template('orders/create.html', suppliers=suppliers)
    
    # GET请求 - 显示创建表单
    try:
        suppliers = Supplier.query.filter_by(user_id=current_user.id).all()
    except SQLAlchemyError as e:
        logging.error(f"获取供应商列表失败: {str(e)}")
        flash('获取供应商列表失败，请稍后重试', 'error')
        suppliers = []
    
    return render_template('orders/create.html', suppliers=suppliers)

@order_bp.route('/<int:order_id>')
@login_required
def detail(order_id):
    """订单详情页面 - 使用缓存机制优化性能"""
    try:
        order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
        
        # 使用缓存机制获取Quote模型，提升性能
        Quote = Order._get_quote_model()
        quotes = Quote.query.filter_by(order_id=order.id).order_by(Quote.price.asc()).all()
        
        # 记录性能统计信息
        cache_stats = Order.get_cache_stats()
        logging.debug(f"订单详情页面加载完成，缓存命中率: {cache_stats['hit_rate_percent']}%")
        
        return render_template('orders/detail.html', order=order, quotes=quotes)
        
    except Exception as e:
        logging.error(f"加载订单详情失败 (订单ID: {order_id}): {str(e)}")
        flash('加载订单详情失败，请稍后重试', 'error')
        return redirect(url_for('order.index'))

@order_bp.route('/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(order_id):
    """编辑订单 - 带异常处理"""
    try:
        order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
        
        if order.status != 'active':
            flash('只能编辑活跃状态的订单', 'error')
            return redirect(url_for('order.detail', order_id=order.id))
        
        if request.method == 'POST':
            try:
                warehouse = request.form.get('warehouse', '').strip()
                goods = request.form.get('goods', '').strip()
                delivery_address = request.form.get('delivery_address', '').strip()
                
                # 数据验证
                if not all([warehouse, goods, delivery_address]):
                    flash('请填写所有必填字段', 'error')
                    return render_template('orders/edit.html', order=order)
                
                # 长度验证
                if len(warehouse) > 200:
                    flash('仓库信息长度不能超过200字符', 'error')
                    return render_template('orders/edit.html', order=order)
                
                if len(delivery_address) > 300:
                    flash('收货地址长度不能超过300字符', 'error')
                    return render_template('orders/edit.html', order=order)
                
                # 保存原始数据用于回滚
                original_warehouse = order.warehouse
                original_goods = order.goods
                original_delivery_address = order.delivery_address
                
                # 更新订单数据
                order.warehouse = warehouse
                order.goods = goods
                order.delivery_address = delivery_address
                
                # 提交事务
                db.session.commit()
                
                logging.info(f"订单编辑成功: {order.order_no}, 用户: {current_user.id}")
                flash('订单信息更新成功', 'success')
                return redirect(url_for('order.detail', order_id=order.id))
                
            except SQLAlchemyError as e:
                db.session.rollback()
                logging.error(f"订单编辑失败 - 数据库错误: {str(e)}")
                flash('订单更新失败：数据库错误，请稍后重试', 'error')
                return render_template('orders/edit.html', order=order)
            except Exception as e:
                db.session.rollback()
                logging.error(f"订单编辑失败 - 未知错误: {str(e)}")
                flash('订单更新失败：系统错误，请联系管理员', 'error')
                return render_template('orders/edit.html', order=order)
        
        return render_template('orders/edit.html', order=order)
        
    except Exception as e:
        logging.error(f"获取订单详情失败: {str(e)}")
        flash('获取订单信息失败', 'error')
        return redirect(url_for('order.index'))

@order_bp.route('/<int:order_id>/select-supplier', methods=['POST'])
@login_required
def select_supplier(order_id):
    """选择中标供应商 - 使用缓存机制优化性能"""
    try:
        order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
        
        supplier_id = request.form.get('supplier_id', type=int)
        price = request.form.get('price', type=float)
        
        if not supplier_id or not price:
            flash('请选择供应商和确认价格', 'error')
            return redirect(url_for('order.detail', order_id=order.id))
        
        # 验证供应商是否有该订单的报价
        # 使用缓存机制获取Quote模型，提升性能
        Quote = Order._get_quote_model()
        quote = Quote.query.filter_by(order_id=order.id, supplier_id=supplier_id).first()
        if not quote:
            flash('所选供应商没有该订单的报价', 'error')
            return redirect(url_for('order.detail', order_id=order.id))
        
        # 验证价格是否匹配
        if abs(float(quote.price) - price) > 0.01:  # 允许小数精度误差
            flash('价格不匹配，请确认后重试', 'error')
            return redirect(url_for('order.detail', order_id=order.id))
        
        # 更新订单状态
        order.selected_supplier_id = supplier_id
        order.selected_price = price
        order.status = 'completed'
        
        db.session.commit()
        
        # 记录性能统计
        cache_stats = Order.get_cache_stats()
        logging.info(f"订单 {order.order_no} 已完成，选择供应商ID: {supplier_id}，缓存命中率: {cache_stats['hit_rate_percent']}%")
        
        flash('已选择中标供应商，订单已完成', 'success')
        return redirect(url_for('order.detail', order_id=order.id))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"选择中标供应商失败 (订单ID: {order_id}): {str(e)}")
        flash('操作失败，请稍后重试', 'error')
        return redirect(url_for('order.detail', order_id=order_id))

@order_bp.route('/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel(order_id):
    """取消订单"""
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    
    if order.status != 'active':
        flash('只能取消活跃状态的订单', 'error')
        return redirect(url_for('order.detail', order_id=order.id))
    
    order.status = 'cancelled'
    db.session.commit()
    
    flash('订单已取消', 'success')
    return redirect(url_for('order.index'))

@order_bp.route('/<int:order_id>/add-suppliers', methods=['GET', 'POST'])
@login_required
def add_suppliers(order_id):
    """为订单添加更多供应商"""
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    
    if order.status != 'active':
        flash('只能为活跃状态的订单添加供应商', 'error')
        return redirect(url_for('order.detail', order_id=order.id))
    
    if request.method == 'POST':
        supplier_ids = request.form.getlist('supplier_ids')
        
        if not supplier_ids:
            flash('请至少选择一个供应商', 'error')
            return redirect(url_for('order.add_suppliers', order_id=order.id))
        
        # 获取新的供应商（排除已关联的）
        current_supplier_ids = [s.id for s in order.suppliers]
        new_supplier_ids = [int(sid) for sid in supplier_ids if int(sid) not in current_supplier_ids]
        
        if not new_supplier_ids:
            flash('所选供应商已经关联到此订单', 'warning')
            return redirect(url_for('order.detail', order_id=order.id))
        
        # 添加新供应商
        new_suppliers = Supplier.query.filter(Supplier.id.in_(new_supplier_ids)).all()
        for supplier in new_suppliers:
            order.suppliers.append(supplier)
        
        db.session.commit()
        
        # 通知新供应商
        try:
            success_count, failed_suppliers = notify_suppliers(order, new_suppliers)
            if failed_suppliers:
                flash(f'已添加 {len(new_suppliers)} 个供应商，通知发送成功 {success_count} 个，失败 {len(failed_suppliers)} 个', 'warning')
            else:
                flash(f'已添加 {len(new_suppliers)} 个供应商，并成功发送通知', 'success')
        except Exception as e:
            logging.error(f"发送供应商通知异常: {str(e)}")
            flash(f'已添加 {len(new_suppliers)} 个供应商，但通知发送失败', 'warning')
        return redirect(url_for('order.detail', order_id=order.id))
    
    # 获取可添加的供应商（排除已关联的）
    current_supplier_ids = [s.id for s in order.suppliers]
    available_suppliers = Supplier.query.filter_by(user_id=current_user.id).filter(
        ~Supplier.id.in_(current_supplier_ids)).all()
    
    return render_template('orders/add_suppliers.html', order=order, suppliers=available_suppliers)

def notify_suppliers(order, suppliers):
    """通知供应商新订单 - 增强错误处理和重试机制"""
    success_count = 0
    failed_suppliers = []
    
    for supplier in suppliers:
        if not supplier.webhook_url:
            logging.info(f"供应商 {supplier.name} 未配置webhook，跳过通知")
            continue
            
        # 重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                access_url = url_for('supplier_portal', access_code=supplier.access_code, _external=True)
                
                # 验证访问码是否存在
                if not supplier.access_code:
                    logging.error(f"供应商 {supplier.name} 缺少访问码，无法生成链接")
                    failed_suppliers.append(supplier.name)
                    break
                
                message = {
                    "msgtype": "text",
                    "text": {
                        "content": f"🔔 新的询价订单通知\n\n"
                                   f"订单号：{order.order_no}\n"
                                   f"货物：{order.goods[:100]}...\n"  # 限制长度
                                   f"仓库：{order.warehouse}\n"
                                   f"收货地址：{order.delivery_address[:50]}...\n\n"
                                   f"请点击链接提交报价：{access_url}"
                    }
                }
                
                # 发送请求，设置超时
                response = requests.post(
                    supplier.webhook_url, 
                    json=message, 
                    timeout=5,  # 缩短超时时间
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 200:
                    logging.info(f"通知发送成功: {supplier.name} (尝试 {attempt + 1}/{max_retries})")
                    success_count += 1
                    break
                else:
                    logging.warning(f"通知发送失败: {supplier.name}, 状态码: {response.status_code}, 响应: {response.text[:200]}")
                    if attempt == max_retries - 1:
                        failed_suppliers.append(supplier.name)
                        
            except Timeout:
                logging.error(f"通知发送超时: {supplier.name} (尝试 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    failed_suppliers.append(supplier.name)
            except ConnectionError:
                logging.error(f"连接错误: {supplier.name} (尝试 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    failed_suppliers.append(supplier.name)
            except RequestException as e:
                logging.error(f"请求异常: {supplier.name}, 错误: {str(e)} (尝试 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    failed_suppliers.append(supplier.name)
            except Exception as e:
                logging.error(f"未知错误: {supplier.name}, 错误: {str(e)} (尝试 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    failed_suppliers.append(supplier.name)
            
            # 重试前等待
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))  # 递增等待时间
    
    # 记录最终结果
    logging.info(f"供应商通知完成 - 成功: {success_count}, 失败: {len(failed_suppliers)}")
    if failed_suppliers:
        logging.error(f"通知失败的供应商: {', '.join(failed_suppliers)}")
    
    return success_count, failed_suppliers