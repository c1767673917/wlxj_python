from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('需要管理员权限才能访问此页面', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def business_type_filter(query, model_class):
    """根据用户业务类型过滤查询结果"""
    if current_user.is_admin():
        return query  # 管理员可以看到所有数据
    else:
        return query.filter(model_class.business_type == current_user.business_type)