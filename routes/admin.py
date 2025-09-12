from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from scripts.backup.backup_manager import BackupManager
from utils.auth import admin_required
from werkzeug.security import generate_password_hash
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

# 创建蓝图
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@login_required
@admin_required
def index():
    """管理员首页"""
    from models import User, Supplier, Order, Quote
    
    # 系统统计
    stats = {
        'total_users': User.query.count(),
        'total_suppliers': Supplier.query.count(),
        'total_orders': Order.query.count(),
        'total_quotes': Quote.query.count(),
        'active_orders': Order.query.filter_by(status='active').count(),
        'completed_orders': Order.query.filter_by(status='completed').count()
    }
    
    # 备份统计
    backup_manager = BackupManager()
    backup_stats = backup_manager.get_backup_stats()
    
    return render_template('admin/index.html', stats=stats, backup_stats=backup_stats)

@admin_bp.route('/backup')
@login_required
@admin_required
def backup_management():
    """备份管理页面"""
    backup_manager = BackupManager()
    
    # 获取备份列表
    backups = backup_manager.list_backups()
    
    # 获取备份统计
    stats = backup_manager.get_backup_stats()
    
    return render_template('admin/backup.html', backups=backups, stats=stats)

@admin_bp.route('/backup/create', methods=['POST'])
@login_required
@admin_required
def create_backup():
    """创建备份"""
    backup_manager = BackupManager()
    
    compress = request.form.get('compress', 'true') == 'true'
    backup_path = backup_manager.create_backup(compress=compress)
    
    if backup_path:
        flash(f'备份创建成功: {backup_path.name}', 'success')
    else:
        flash('备份创建失败', 'error')
    
    return redirect(url_for('admin.backup_management'))

@admin_bp.route('/backup/cleanup', methods=['POST'])
@login_required
@admin_required
def cleanup_backups():
    """清理旧备份"""
    backup_manager = BackupManager()
    
    keep_days = request.form.get('keep_days', 7, type=int)
    deleted_count = backup_manager.cleanup_old_backups(keep_days=keep_days)
    
    flash(f'清理完成，删除了 {deleted_count} 个旧备份文件', 'success')
    return redirect(url_for('admin.backup_management'))

@admin_bp.route('/backup/download/<filename>')
@login_required
@admin_required
def download_backup(filename):
    """下载备份文件"""
    backup_manager = BackupManager()
    backup_path = backup_manager.backup_dir / filename
    
    if not backup_path.exists():
        flash('备份文件不存在', 'error')
        return redirect(url_for('admin.backup_management'))
    
    return send_file(backup_path, as_attachment=True)

@admin_bp.route('/backup/verify/<filename>')
@login_required
@admin_required
def verify_backup(filename):
    """验证备份文件"""
    backup_manager = BackupManager()
    
    is_valid, message = backup_manager.verify_backup(filename)
    
    return jsonify({
        'success': is_valid,
        'message': message
    })

@admin_bp.route('/backup/restore/<filename>', methods=['POST'])
@login_required
@admin_required
def restore_backup(filename):
    """恢复备份"""
    backup_manager = BackupManager()
    
    # 这是一个危险操作，需要额外确认
    confirm = request.form.get('confirm') == 'true'
    
    if not confirm:
        flash('请确认要执行恢复操作', 'warning')
        return redirect(url_for('admin.backup_management'))
    
    success = backup_manager.restore_backup(filename)
    
    if success:
        flash(f'备份恢复成功: {filename}', 'success')
    else:
        flash(f'备份恢复失败: {filename}', 'error')
    
    return redirect(url_for('admin.backup_management'))

@admin_bp.route('/system')
@login_required
@admin_required
def system_info():
    """系统信息页面"""
    import platform
    import psutil
    
    # 系统信息
    system_info = {
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'cpu_count': psutil.cpu_count(),
        'memory_total': psutil.virtual_memory().total / 1024 / 1024 / 1024,  # GB
        'memory_available': psutil.virtual_memory().available / 1024 / 1024 / 1024,  # GB
        'disk_usage': psutil.disk_usage('.').percent
    }
    
    # 数据库信息
    db_path = 'database.db'
    db_info = {}
    if os.path.exists(db_path):
        stat = os.stat(db_path)
        db_info = {
            'size': stat.st_size / 1024 / 1024,  # MB
            'created': datetime.fromtimestamp(stat.st_ctime),
            'modified': datetime.fromtimestamp(stat.st_mtime)
        }
    
    return render_template('admin/system.html', system_info=system_info, db_info=db_info)

@admin_bp.route('/users')
@login_required
@admin_required
def user_management():
    """用户管理页面"""
    from models import User
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/logs')
@login_required
@admin_required
def view_logs():
    """查看系统日志"""
    log_files = ['backup.log', 'app.log']  # 可以根据需要添加更多日志文件
    
    logs = {}
    for log_file in log_files:
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    # 读取最后100行
                    lines = f.readlines()
                    logs[log_file] = lines[-100:] if len(lines) > 100 else lines
            except Exception as e:
                logs[log_file] = [f'读取日志文件失败: {str(e)}']
        else:
            logs[log_file] = ['日志文件不存在']
    
    return render_template('admin/logs.html', logs=logs)

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """添加新用户"""
    if request.method == 'POST':
        from models import User, db
        
        username = request.form.get('username')
        password = request.form.get('password')
        business_type = request.form.get('business_type')
        
        # 数据验证
        if not username or not password or not business_type:
            flash('请填写所有字段', 'error')
            return render_template('admin/add_user.html')
        
        if business_type not in ['admin', 'oil', 'fast_moving']:
            flash('无效的业务类型', 'error')
            return render_template('admin/add_user.html')
        
        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return render_template('admin/add_user.html')
        
        try:
            user = User(
                username=username,
                password=generate_password_hash(password),
                business_type=business_type
            )
            db.session.add(user)
            db.session.commit()
            flash(f'用户 "{username}" 添加成功', 'success')
            return redirect(url_for('admin.user_management'))
        except Exception as e:
            db.session.rollback()
            flash(f'添加用户失败: {str(e)}', 'error')
    
    return render_template('admin/add_user.html')

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """编辑用户"""
    from models import User, db
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        username = request.form.get('username')
        business_type = request.form.get('business_type')
        password = request.form.get('password')
        
        # 数据验证
        if not username or not business_type:
            flash('用户名和业务类型不能为空', 'error')
            return render_template('admin/edit_user.html', user=user)
        
        if business_type not in ['admin', 'oil', 'fast_moving']:
            flash('无效的业务类型', 'error')
            return render_template('admin/edit_user.html', user=user)
        
        # 检查用户名是否被其他用户使用
        existing = User.query.filter_by(username=username).filter(User.id != user_id).first()
        if existing:
            flash('用户名已被其他用户使用', 'error')
            return render_template('admin/edit_user.html', user=user)
        
        try:
            user.username = username
            user.business_type = business_type
            
            # 如果提供了新密码则更新
            if password:
                user.password = generate_password_hash(password)
            
            db.session.commit()
            flash(f'用户 "{username}" 更新成功', 'success')
            return redirect(url_for('admin.user_management'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新用户失败: {str(e)}', 'error')
    
    return render_template('admin/edit_user.html', user=user)

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户 - 增强版本包含并发保护和详细的状态检查"""
    from models import User
    from utils.database_utils import safe_delete_user, get_user_deletion_status, cleanup_stale_deletion_locks
    
    # 清理陈旧的删除锁
    cleanup_stale_deletion_locks()
    
    # 检查用户删除状态
    status_info = get_user_deletion_status(user_id)
    
    if not status_info['user_exists']:
        flash('用户不存在或已被删除', 'warning')
        return redirect(url_for('admin.user_management'))
    
    if status_info['is_being_deleted']:
        flash('该用户正在被其他管理员删除，请稍后刷新页面查看结果', 'warning')
        return redirect(url_for('admin.user_management'))
    
    if not status_info['can_delete']:
        flash('当前无法删除该用户，请稍后再试', 'error')
        return redirect(url_for('admin.user_management'))
    
    # 获取用户信息进行额外验证
    user = User.query.get(user_id)
    if not user:
        flash('用户不存在', 'error')
        return redirect(url_for('admin.user_management'))
    
    # 不能删除管理员账户的业务逻辑检查
    if user.business_type == 'admin':
        # 不能删除自己
        if user.id == current_user.id:
            flash('不能删除当前登录的账户', 'error')
            return redirect(url_for('admin.user_management'))
        
        # 检查是否是唯一的管理员
        admin_count = User.query.filter_by(business_type='admin').count()
        if admin_count <= 1:
            flash('不能删除唯一的管理员账户', 'error')
            return redirect(url_for('admin.user_management'))
    
    # 执行安全删除
    success, message, data = safe_delete_user(user_id)
    
    if success:
        # 构建详细的删除成功消息
        detail_msg = f'用户 "{data["username"]}" 删除成功'
        
        # 添加关联数据统计
        if data.get('supplier_count', 0) > 0 or data.get('order_count', 0) > 0:
            detail_msg += f' (供应商: {data["supplier_count"]}个, 订单: {data["order_count"]}个, 报价: {data["quote_count"]}个)'
        
        # 添加性能信息
        if 'deletion_duration' in data:
            detail_msg += f' - 耗时: {data["deletion_duration"]:.2f}秒'
        
        flash(detail_msg, 'success')
        logger.info(f"管理员 {current_user.username} 成功删除用户 {data['username']} (ID: {user_id})")
        
    else:
        flash(f'删除用户失败: {message}', 'error')
        logger.error(f"管理员 {current_user.username} 删除用户失败 (ID: {user_id}): {message}")
    
    return redirect(url_for('admin.user_management'))

@admin_bp.route('/database/integrity')
@login_required
@admin_required
def database_integrity():
    """数据库完整性检查页面"""
    from utils.database_utils import check_data_integrity
    
    integrity_results = check_data_integrity()
    return render_template('admin/database_integrity.html', results=integrity_results)

@admin_bp.route('/database/cleanup', methods=['POST'])
@login_required
@admin_required
def database_cleanup():
    """清理孤立数据"""
    from utils.database_utils import cleanup_orphaned_data
    
    try:
        results = cleanup_orphaned_data()
        if 'error' in results:
            flash(f'数据清理失败: {results["error"]}', 'error')
        else:
            total_cleaned = sum(results.values())
            if total_cleaned > 0:
                flash(f'数据清理完成，共清理了 {total_cleaned} 条孤立数据', 'success')
            else:
                flash('数据完整性良好，无需清理', 'info')
    except Exception as e:
        flash(f'数据清理失败: {str(e)}', 'error')
    
    return redirect(url_for('admin.database_integrity'))