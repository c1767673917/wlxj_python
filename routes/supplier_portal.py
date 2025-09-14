from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from models import db, Supplier, Order, Quote
from datetime import datetime, date
from sqlalchemy import or_, func
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO
import logging
import traceback
from functools import wraps

# 创建蓝图
portal_bp = Blueprint('portal', __name__, url_prefix='/portal')

# 供应商登录验证装饰器
def require_supplier_login(f):
    """供应商登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'supplier_id' not in session:
            flash('访问已过期，请重新访问', 'error')
            return redirect(url_for('index'))
        
        supplier_id = session['supplier_id']
        supplier = Supplier.query.get(supplier_id)
        
        if not supplier:
            flash('供应商信息不存在', 'error')
            return redirect(url_for('index'))
            
        return f(*args, **kwargs)
    return decorated_function

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
@require_supplier_login
def order_detail(order_id):
    """订单详情页面（供应商视图）"""
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
@require_supplier_login
def submit_quote(order_id):
    """提交或更新报价"""
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
@require_supplier_login
def my_quotes():
    """我的报价列表 - 支持筛选、搜索和分页"""
    try:
        supplier_id = session['supplier_id']
        supplier = Supplier.query.get(supplier_id)
        
        # 安全地获取筛选参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status = request.args.get('status', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        keyword = request.args.get('keyword', '').strip()
        date_quick = request.args.get('date_quick', '').strip()
        
        # 参数验证
        if page < 1:
            page = 1
        elif page > 1000:
            page = 1000
            
        if per_page not in [10, 20, 50]:
            per_page = 10
            
        # 验证状态参数
        valid_statuses = ['', 'active', 'completed', 'cancelled']
        if status not in valid_statuses:
            logging.warning(f"供应商提供了无效的状态参数: {status}")
            status = ''
        
        # 限制关键词长度
        if keyword and len(keyword) > 100:
            logging.warning(f"供应商提供了过长的关键词: {len(keyword)}字符")
            keyword = keyword[:100]
            flash('搜索关键词过长，已自动截取前100个字符', 'warning')
        
        # 处理快捷日期选项
        if date_quick:
            quick_start, quick_end = process_quote_quick_date(date_quick)
            if quick_start and quick_end:
                start_date, end_date = quick_start, quick_end
                logging.debug(f"应用快捷日期选项: {date_quick} -> {start_date} to {end_date}")
            else:
                logging.warning(f"快捷日期选项处理失败: {date_quick}")
                flash('快捷日期设置失败，请手动选择日期', 'warning')
        
        # 构建查询
        try:
            query = build_quotes_query(supplier_id, status, start_date, end_date, keyword)
        except Exception as e:
            logging.error(f"构建报价查询失败: {str(e)}")
            flash('查询条件处理失败，显示所有报价', 'error')
            query = Quote.query.filter_by(supplier_id=supplier_id)
        
        # 执行分页查询
        try:
            quotes = query.paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            # 检查分页结果
            if quotes.total == 0 and (status or start_date or end_date or keyword):
                logging.info(f"供应商{supplier_id}筛选条件未找到结果 - 状态:{status}, 日期:{start_date}-{end_date}, 关键词:{keyword}")
            elif quotes.total > 0:
                logging.debug(f"供应商{supplier_id}查询完成，找到{quotes.total}条记录，显示第{page}页")
                
        except Exception as e:
            logging.error(f"分页查询执行失败: {str(e)}")
            flash('查询失败，请稍后重试', 'error')
            # 回退到简单查询
            try:
                quotes = Quote.query.filter_by(supplier_id=supplier_id).order_by(
                    Quote.created_at.desc()).paginate(
                    page=1, per_page=per_page, error_out=False)
            except Exception as fallback_error:
                logging.error(f"回退查询也失败: {str(fallback_error)}")
                # 创建空的分页对象
                quotes = type('MockPagination', (), {
                    'items': [], 'total': 0, 'pages': 0, 
                    'has_prev': False, 'has_next': False,
                    'prev_num': None, 'next_num': None,
                    'page': 1, 'per_page': per_page,
                    'iter_pages': lambda: []
                })()
        
        return render_template('portal/quotes.html', 
                             supplier=supplier, 
                             quotes=quotes,
                             status=status,
                             start_date=start_date,
                             end_date=end_date,
                             keyword=keyword,
                             date_quick=date_quick,
                             per_page=per_page)
    
    except Exception as e:
        logging.error(f"供应商报价列表页面发生未知错误: {str(e)}")
        logging.error(f"错误详情: {traceback.format_exc()}")
        flash('页面加载失败，请刷新页面重试', 'error')
        return redirect(url_for('index'))

@portal_bp.route('/logout')
def logout():
    """供应商登出"""
    session.pop('supplier_id', None)
    session.pop('supplier_name', None)
    session.pop('access_code', None)
    flash('您已安全退出', 'info')
    return redirect(url_for('index'))

@portal_bp.route('/quotes/export')
@require_supplier_login
def export_quotes():
    """导出筛选后的报价Excel"""
    try:
        supplier_id = session['supplier_id']
        supplier = Supplier.query.get(supplier_id)
        
        # 获取筛选参数
        status = request.args.get('status', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        keyword = request.args.get('keyword', '').strip()
        
        # 构建查询 - 复用筛选逻辑
        try:
            query = build_quotes_query(supplier_id, status, start_date, end_date, keyword)
        except Exception as e:
            logging.error(f"构建导出查询失败: {str(e)}")
            flash('导出查询构建失败', 'error')
            return redirect(url_for('portal.my_quotes'))
        
        # 获取所有符合条件的报价
        quotes = query.all()
        
        if not quotes:
            flash('没有符合条件的报价可以导出', 'warning')
            return redirect(url_for('portal.my_quotes', 
                                  status=status, start_date=start_date, 
                                  end_date=end_date, keyword=keyword))
        
        # 创建Excel工作簿
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"{supplier.name}报价列表"
        
        # 设置标题样式
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        # 设置表头
        headers = ['订单号', '货物信息', '收货地址', '仓库', '报价金额', '交期', '订单状态', '报价状态', '创建时间']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
        
        # 填充数据
        for row, quote in enumerate(quotes, 2):
            ws.cell(row=row, column=1, value=quote.order.order_no)
            ws.cell(row=row, column=2, value=quote.order.goods)
            ws.cell(row=row, column=3, value=quote.order.delivery_address)
            ws.cell(row=row, column=4, value=quote.order.warehouse)
            ws.cell(row=row, column=5, value=f"¥{quote.price:.2f}")
            ws.cell(row=row, column=6, value=quote.delivery_time or '-')
            
            # 订单状态
            status_map = {
                'active': '进行中',
                'completed': '已完成', 
                'cancelled': '已取消'
            }
            ws.cell(row=row, column=7, value=status_map.get(quote.order.status, quote.order.status))
            
            # 报价状态
            if quote.order.selected_supplier_id == supplier_id:
                quote_status = '已中标'
            elif quote.order.status == 'completed':
                quote_status = '未中标'
            elif quote.order.status == 'cancelled':
                quote_status = '订单取消'
            else:
                quote_status = '待定'
            ws.cell(row=row, column=8, value=quote_status)
            
            ws.cell(row=row, column=9, value=quote.created_at.strftime('%Y-%m-%d %H:%M'))
        
        # 自动调整列宽
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # 生成文件名
        current_date = datetime.now().strftime('%Y%m%d')
        filename = f"{supplier.name}报价列表_{current_date}.xlsx"
        
        # 保存到内存
        excel_buffer = BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)
        
        # 记录导出信息
        logging.info(f"供应商{supplier_id}Excel导出成功: 导出{len(quotes)}条记录, 文件名:{filename}")
        
        # 返回文件
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logging.error(f"供应商报价Excel导出失败: {str(e)}")
        logging.error(f"错误详情: {traceback.format_exc()}")
        flash('Excel导出失败，请稍后重试', 'error')
        return redirect(url_for('portal.my_quotes'))

def build_quotes_query(supplier_id, status=None, start_date=None, end_date=None, keyword=None):
    """构建报价查询条件"""
    # 基础查询 - 连接Order表进行筛选
    query = Quote.query.join(Order).filter(Quote.supplier_id == supplier_id)
    
    # 应用筛选条件
    query = apply_quote_filters(query, status, start_date, end_date, keyword)
    
    return query.order_by(Quote.created_at.desc())

def apply_quote_filters(query, status, start_date, end_date, keyword):
    """应用报价筛选条件"""
    # 状态筛选
    if status:
        query = query.filter(Order.status == status)
        logging.debug(f"应用状态筛选: {status}")
    
    # 日期范围筛选
    try:
        query = apply_quote_date_filter(query, start_date, end_date)
    except Exception as e:
        logging.error(f"日期筛选处理失败: {str(e)}")
        raise e
    
    # 关键词搜索
    try:
        query = apply_quote_keyword_search(query, keyword)
    except Exception as e:
        logging.error(f"关键词搜索处理失败: {str(e)}")
        raise e
    
    return query

def apply_quote_date_filter(query, start_date, end_date):
    """应用报价日期范围筛选"""
    import re
    from datetime import timedelta
    
    start_dt = None
    end_dt = None
    
    # 日期格式验证
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    
    # 处理开始日期
    if start_date and start_date.strip():
        start_date = start_date.strip()
        if not date_pattern.match(start_date):
            raise ValueError(f'开始日期格式无效: {start_date}')
        
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Order.created_at >= start_dt)
            logging.debug(f"应用开始日期筛选: {start_date}")
        except ValueError as e:
            raise ValueError(f'解析开始日期失败: {start_date}')
    
    # 处理结束日期
    if end_date and end_date.strip():
        end_date = end_date.strip()
        if not date_pattern.match(end_date):
            raise ValueError(f'结束日期格式无效: {end_date}')
        
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            # 设置为当天的最后一刻
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            query = query.filter(Order.created_at <= end_dt)
            logging.debug(f"应用结束日期筛选: {end_date}")
        except ValueError as e:
            raise ValueError(f'解析结束日期失败: {end_date}')
    
    # 验证日期范围
    if start_dt and end_dt:
        if start_dt.date() > end_dt.date():
            raise ValueError('开始日期不能大于结束日期')
        
        date_diff = end_dt.date() - start_dt.date()
        if date_diff.days > 365:  # 1年
            logging.warning(f"供应商选择了过大的日期范围: {date_diff.days}天")
            flash('选择的日期范围较大（超过1年），查询可能较慢，建议缩小范围', 'warning')
    
    return query

def apply_quote_keyword_search(query, keyword):
    """应用关键词搜索 - 搜索订单号、仓库、收货地址、货物信息"""
    if not keyword or not keyword.strip():
        return query
    
    keyword = keyword.strip()
    search_pattern = f"%{keyword}%"
    
    # 多字段模糊匹配
    conditions = [
        Order.order_no.ilike(search_pattern),
        Order.goods.ilike(search_pattern),
        Order.delivery_address.ilike(search_pattern),
        Order.warehouse.ilike(search_pattern)
    ]
    
    return query.filter(or_(*conditions))

def process_quote_quick_date(date_quick):
    """处理供应商报价快捷日期选项"""
    try:
        today = date.today()
        
        if date_quick == 'today':
            date_str = today.strftime('%Y-%m-%d')
            return date_str, date_str
        elif date_quick == 'this_month':
            start = today.replace(day=1)
            start_str = start.strftime('%Y-%m-%d')
            end_str = today.strftime('%Y-%m-%d')
            return start_str, end_str
        else:
            logging.warning(f"不支持的快捷日期选项: {date_quick}")
            return '', ''
            
    except Exception as e:
        logging.error(f"处理快捷日期选项时发生错误: {str(e)}")
        return '', ''

def notify_buyer_new_quote(order, supplier, price):
    """通知采购方有新报价（可扩展实现）"""
    # 这里可以实现通知采购方的逻辑
    # 例如：发送邮件、系统内通知等
    pass