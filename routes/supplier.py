from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Supplier
import secrets

# 创建蓝图
supplier_bp = Blueprint('supplier', __name__, url_prefix='/suppliers')

@supplier_bp.route('/')
@login_required
def index():
    """供应商列表页面"""
    suppliers = Supplier.query.filter_by(user_id=current_user.id).all()
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
        
        # 检查名称是否已存在
        existing = Supplier.query.filter_by(name=name, user_id=current_user.id).first()
        if existing:
            flash('供应商名称已存在', 'error')
            return render_template('suppliers/add.html')
        
        # 创建新供应商
        supplier = Supplier(
            name=name,
            webhook_url=webhook_url if webhook_url else None,
            user_id=current_user.id,
            access_code=secrets.token_urlsafe(32)
        )
        
        db.session.add(supplier)
        db.session.commit()
        
        flash(f'供应商 "{name}" 添加成功', 'success')
        return redirect(url_for('supplier.index'))
    
    return render_template('suppliers/add.html')

@supplier_bp.route('/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def edit(supplier_id):
    """编辑供应商"""
    supplier = Supplier.query.filter_by(id=supplier_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        name = request.form.get('name')
        webhook_url = request.form.get('webhook_url', '').strip()
        
        if not name:
            flash('供应商名称不能为空', 'error')
            return render_template('suppliers/edit.html', supplier=supplier)
        
        # 检查名称是否已存在（排除当前供应商）
        existing = Supplier.query.filter_by(name=name, user_id=current_user.id).filter(Supplier.id != supplier_id).first()
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
    supplier = Supplier.query.filter_by(id=supplier_id, user_id=current_user.id).first_or_404()
    
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
    supplier = Supplier.query.filter_by(id=supplier_id, user_id=current_user.id).first_or_404()
    
    # 生成新的访问码
    supplier.access_code = secrets.token_urlsafe(32)
    db.session.commit()
    
    flash(f'供应商 "{supplier.name}" 的访问码已重新生成', 'success')
    return redirect(url_for('supplier.index'))

@supplier_bp.route('/<int:supplier_id>/details')
@login_required
def details(supplier_id):
    """供应商详情页面"""
    supplier = Supplier.query.filter_by(id=supplier_id, user_id=current_user.id).first_or_404()
    
    # 生成专属访问链接
    access_url = url_for('supplier_portal', access_code=supplier.access_code, _external=True)
    
    return render_template('suppliers/details.html', supplier=supplier, access_url=access_url)