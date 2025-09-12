from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Supplier
from utils.auth import business_type_filter
import secrets

# 创建蓝图
supplier_bp = Blueprint('supplier', __name__, url_prefix='/suppliers')

@supplier_bp.route('/')
@login_required
def index():
    """供应商列表页面"""
    query = Supplier.query
    suppliers = business_type_filter(query, Supplier).all()
    return render_template('suppliers/index.html', suppliers=suppliers)

@supplier_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """添加供应商"""
    if request.method == 'POST':
        name = request.form.get('name')
        webhook_url = request.form.get('webhook_url', '').strip()
        
        if not name:
            flash('供应商名称不能为空', 'error')
            return render_template('suppliers/add.html')
        
        # 管理员可以选择业务类型，普通用户使用自己的业务类型
        if current_user.is_admin():
            business_type = request.form.get('business_type', 'oil')
            if business_type not in ['oil', 'fast_moving']:
                flash('无效的业务类型', 'error')
                return render_template('suppliers/add.html')
        else:
            business_type = current_user.business_type
        
        # 检查名称是否在指定业务类型中已存在
        existing = Supplier.query.filter_by(name=name, business_type=business_type).first()
        if existing:
            flash('供应商名称在该业务类型中已存在', 'error')
            return render_template('suppliers/add.html')
        
        try:
            # 创建新供应商
            supplier = Supplier(
                name=name,
                webhook_url=webhook_url if webhook_url else None,
                user_id=current_user.id,
                business_type=business_type,
                access_code=secrets.token_urlsafe(32)
            )
            
            db.session.add(supplier)
            db.session.commit()
            
            flash(f'供应商 "{name}" 添加成功', 'success')
            return redirect(url_for('supplier.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'添加供应商失败: {str(e)}', 'error')
            return render_template('suppliers/add.html')
    
    return render_template('suppliers/add.html')

@supplier_bp.route('/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def edit(supplier_id):
    """编辑供应商"""
    query = Supplier.query.filter_by(id=supplier_id)
    supplier = business_type_filter(query, Supplier).first_or_404()
    
    if request.method == 'POST':
        name = request.form.get('name')
        webhook_url = request.form.get('webhook_url', '').strip()
        
        if not name:
            flash('供应商名称不能为空', 'error')
            return render_template('suppliers/edit.html', supplier=supplier)
        
        # 检查名称是否在同业务类型中已存在（排除当前供应商）
        query = Supplier.query.filter_by(name=name).filter(Supplier.id != supplier_id)
        existing = business_type_filter(query, Supplier).first()
        if existing:
            flash('供应商名称已存在', 'error')
            return render_template('suppliers/edit.html', supplier=supplier)
        
        # 更新供应商信息
        supplier.name = name
        supplier.webhook_url = webhook_url if webhook_url else None
        
        db.session.commit()
        
        flash(f'供应商 "{name}" 更新成功', 'success')
        return redirect(url_for('supplier.index'))
    
    return render_template('suppliers/edit.html', supplier=supplier)

@supplier_bp.route('/delete/<int:supplier_id>', methods=['POST'])
@login_required
def delete(supplier_id):
    """删除供应商"""
    query = Supplier.query.filter_by(id=supplier_id)
    supplier = business_type_filter(query, Supplier).first_or_404()
    
    # 检查是否有关联的报价
    if supplier.quotes:
        flash('该供应商有关联的报价，无法删除', 'error')
        return redirect(url_for('supplier.index'))
    
    name = supplier.name
    db.session.delete(supplier)
    db.session.commit()
    
    flash(f'供应商 "{name}" 删除成功', 'success')
    return redirect(url_for('supplier.index'))

@supplier_bp.route('/<int:supplier_id>/regenerate-code', methods=['POST'])
@login_required
def regenerate_access_code(supplier_id):
    """重新生成访问码"""
    query = Supplier.query.filter_by(id=supplier_id)
    supplier = business_type_filter(query, Supplier).first_or_404()
    
    # 生成新的访问码
    supplier.access_code = secrets.token_urlsafe(32)
    db.session.commit()
    
    flash(f'供应商 "{supplier.name}" 的访问码已重新生成', 'success')
    return redirect(url_for('supplier.index'))

@supplier_bp.route('/<int:supplier_id>/details')
@login_required
def details(supplier_id):
    """供应商详情页面"""
    query = Supplier.query.filter_by(id=supplier_id)
    supplier = business_type_filter(query, Supplier).first_or_404()
    
    # 生成专属访问链接
    access_url = url_for('supplier_portal', access_code=supplier.access_code, _external=True)
    
    return render_template('suppliers/details.html', supplier=supplier, access_url=access_url)