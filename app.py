from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
import os
import logging

# Flask应用初始化
app = Flask(__name__)
app.config.from_object(Config)

# 数据库初始化
from models import db
db.init_app(app)

# SQLite外键约束配置
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """启用SQLite外键约束"""
    if 'sqlite' in app.config.get('SQLALCHEMY_DATABASE_URI', ''):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# 登录管理器初始化
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# 首页路由
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        from models import User
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误')
    
    return render_template('login.html')

# 注册路由已移除，仅管理员可添加用户

# 登出路由
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# 仪表板
@app.route('/dashboard')
@login_required
def dashboard():
    from models import Order, Supplier
    
    if current_user.is_admin():
        # 管理员看到所有数据的分类统计
        stats_by_type = {}
        for btype in ['oil', 'fast_moving']:
            total_orders = Order.query.filter_by(business_type=btype).count()
            active_orders = Order.query.filter_by(business_type=btype, status='active').count()
            total_suppliers = Supplier.query.filter_by(business_type=btype).count()
            stats_by_type[btype] = {
                'total_orders': total_orders,
                'active_orders': active_orders, 
                'total_suppliers': total_suppliers
            }
        return render_template('dashboard.html', admin_stats=stats_by_type)
    else:
        # 普通用户按业务类型查看数据
        total_orders = Order.query.filter_by(business_type=current_user.business_type).count()
        active_orders = Order.query.filter_by(business_type=current_user.business_type, status='active').count()
        total_suppliers = Supplier.query.filter_by(business_type=current_user.business_type).count()
        
        return render_template('dashboard.html',
                             total_orders=total_orders,
                             active_orders=active_orders,
                             total_suppliers=total_suppliers)

# 注册蓝图
from routes.supplier import supplier_bp
from routes.order import order_bp
from routes.supplier_portal import portal_bp
from routes.quote import quote_bp
from routes.admin import admin_bp
app.register_blueprint(supplier_bp)
app.register_blueprint(order_bp)
app.register_blueprint(portal_bp)
app.register_blueprint(quote_bp)
app.register_blueprint(admin_bp)

# 自定义模板过滤器
@app.template_filter('nl2br')
def nl2br(s):
    """将换行符转换为HTML的<br>标签"""
    if not s:
        return s
    return s.replace('\n', '<br>')

@app.template_filter('safe_number')
def safe_number(value, default=0):
    """安全的数值转换过滤器，用于确保模板中的数学运算安全
    
    Args:
        value: 需要转换的值
        default: 默认值（转换失败时返回）
        
    Returns:
        数值类型或默认值
    """
    import logging
    from decimal import Decimal
    
    try:
        if value is None:
            return default
            
        if isinstance(value, (int, float, Decimal)):
            return value
            
        # 尝试转换字符串
        if isinstance(value, str) and value.strip():
            try:
                return float(value)
            except ValueError:
                pass
                
        return default
    except Exception as e:
        logging.error(f"Error in safe_number filter: {e}")
        return default

@app.template_filter('truncate')
def truncate_filter(s, length=50):
    """截断字符串"""
    if not s:
        return s
    if len(s) <= length:
        return s
    return s[:length] + '...'

@app.template_filter('format_price')
def format_price(value, currency='¥'):
    """格式化价格显示，防止Decimal类型错误
    
    Args:
        value: 价格值
        currency: 货币符号
        
    Returns:
        格式化后的价格字符串
    """
    try:
        if value is None:
            return f"{currency}0.00"
            
        # 使用安全转换
        float_value = decimal_to_float(value)
        return f"{currency}{float_value:,.2f}"
        
    except Exception:
        return f"{currency}0.00"

@app.template_filter('decimal_to_float')
def decimal_to_float(value):
    """将Decimal类型安全转换为float类型，用于模板中的数值计算
    
    Args:
        value: 需要转换的值（可能是Decimal、float、int、str或None）
        
    Returns:
        float: 转换后的浮点数，转换失败时返回0.0
    """
    import logging
    from decimal import Decimal, InvalidOperation
    
    try:
        # 处理None值
        if value is None:
            return 0.0
            
        # 处理Decimal类型
        if isinstance(value, Decimal):
            # 检查是否为无穷大或NaN
            if not value.is_finite():
                logging.warning(f"Decimal value is not finite: {value}")
                return 0.0
            return float(value)
            
        # 处理字符串类型
        if isinstance(value, str):
            if not value.strip():  # 空字符串
                return 0.0
            try:
                decimal_val = Decimal(value)
                if not decimal_val.is_finite():
                    logging.warning(f"String converted Decimal is not finite: {value}")
                    return 0.0
                return float(decimal_val)
            except (InvalidOperation, ValueError) as e:
                logging.warning(f"Failed to convert string to Decimal: {value}, error: {e}")
                return 0.0
                
        # 处理数值类型（int, float）
        if isinstance(value, (int, float)):
            # 检查是否为有效数值
            if str(value).lower() in ['inf', '-inf', 'nan']:
                logging.warning(f"Invalid numeric value: {value}")
                return 0.0
            return float(value)
            
        # 处理其他类型
        logging.warning(f"Unsupported type for decimal_to_float: {type(value)}, value: {value}")
        return 0.0
        
    except Exception as e:
        # 记录所有未预期的异常
        logging.error(f"Unexpected error in decimal_to_float: {e}, value: {value}, type: {type(value)}")
        return 0.0

@app.template_filter('pow')
def pow_filter(value, exponent=2):
    """计算数值的幂运算，用于模板中的数学计算
    
    Args:
        value: 需要计算的基数
        exponent: 指数，默认为2（平方）
        
    Returns:
        计算结果，如果计算失败返回0
    """
    try:
        if value is None:
            return 0
            
        # 使用安全转换确保数值类型正确
        safe_value = safe_number(value, 0)
        return pow(safe_value, exponent)
        
    except Exception as e:
        logging.error(f"Error in pow filter: {e}, value: {value}, exponent: {exponent}")
        return 0

# 添加日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 供应商专属入口路由（直接访问，不使用蓝图前缀）
@app.route('/supplier/<access_code>')
def supplier_portal(access_code):
    """供应商专属门户入口"""
    from models import Supplier, Order, Quote
    
    supplier = Supplier.query.filter_by(access_code=access_code).first_or_404()
    
    # 将供应商信息存储到session中
    session['supplier_id'] = supplier.id
    session['supplier_name'] = supplier.name
    session['access_code'] = access_code
    
    # 获取该供应商需要报价的订单
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

# 创建数据库表
def create_tables():
    from models import User, Supplier, Order, Quote
    
    with app.app_context():
        db.create_all()
        
        # 创建默认管理员账户
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                password=generate_password_hash('admin123'),
                business_type='admin'
            )
            db.session.add(admin_user)
            db.session.commit()

if __name__ == '__main__':
    create_tables()  # 启动时创建表
    app.run(debug=True, host='0.0.0.0', port=5001)