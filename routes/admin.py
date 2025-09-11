from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from backup_manager import BackupManager
from datetime import datetime
import os

# 创建蓝图
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """管理员权限装饰器"""
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('需要管理员权限才能访问此页面', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

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