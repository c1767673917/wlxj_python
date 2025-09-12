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
    try:
        # 检查用户是否已认证
        if not current_user or not current_user.is_authenticated:
            # 未登录用户返回空查询
            return query.filter(model_class.id == None)
        
        if current_user.is_admin():
            return query  # 管理员可以看到所有数据
        else:
            # 确保用户有business_type属性
            if not hasattr(current_user, 'business_type') or not current_user.business_type:
                return query.filter(model_class.id == None)
            
            return query.filter(model_class.business_type == current_user.business_type)
    except Exception as e:
        # 发生异常时返回空查询，确保安全
        import logging
        logging.warning(f"business_type_filter异常: {e}")
        return query.filter(model_class.id == None)