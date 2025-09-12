# 业务类型数据共享系统技术规格说明

## 问题陈述

### 业务问题
- **当前问题**: 系统采用用户数据隔离模式，每个用户只能看到自己创建的供应商、订单和报价数据，导致同类型业务用户无法共享供应商资源，降低了报价效率
- **现有状态**: 
  - 用户角色只有`user`和`admin`两种
  - 所有数据表通过`user_id`进行隔离
  - 供应商和订单完全按用户隔离
- **期望结果**: 改为业务类型数据共享模式，同类型业务用户共享供应商和订单数据，提高报价效率和供应商利用率

## 解决方案概述

### 方法
将用户角色从用户隔离模式改为业务类型共享模式，通过business_type字段替代user_id进行数据分组，同时保持管理员的全局访问权限。

### 核心变更
1. 用户模型role字段改为business_type，支持`admin`/`oil`/`fast_moving`三种类型
2. 供应商和订单模型的user_id字段改为business_type字段
3. 移除注册路由，仅管理员可添加用户
4. 修改所有数据查询逻辑，按业务类型过滤而非用户ID
5. 添加管理员用户管理功能

### 成功标准
- 同业务类型用户可以看到彼此的供应商和订单
- 管理员可以查看和操作所有业务类型的数据
- 移除注册功能，仅管理员可添加用户
- 清理现有测试数据

## 技术实现

### 数据库变更

#### 表结构修改
```sql
-- 修改users表
ALTER TABLE users RENAME COLUMN role TO business_type;
UPDATE users SET business_type = 'admin' WHERE business_type = 'admin';
UPDATE users SET business_type = 'oil' WHERE business_type = 'user';

-- 修改suppliers表
ALTER TABLE suppliers ADD COLUMN business_type VARCHAR(20) NOT NULL DEFAULT 'oil';
UPDATE suppliers SET business_type = (
    SELECT u.business_type 
    FROM users u 
    WHERE u.id = suppliers.user_id 
    AND u.business_type != 'admin'
);
-- 保留user_id作为创建者标识，但不再用于数据过滤

-- 修改orders表  
ALTER TABLE orders ADD COLUMN business_type VARCHAR(20) NOT NULL DEFAULT 'oil';
UPDATE orders SET business_type = (
    SELECT u.business_type 
    FROM users u 
    WHERE u.id = orders.user_id 
    AND u.business_type != 'admin'
);
-- 保留user_id作为创建者标识，但不再用于数据过滤
```

#### 新增索引
```sql
CREATE INDEX idx_suppliers_business_type ON suppliers(business_type);
CREATE INDEX idx_orders_business_type ON orders(business_type);
CREATE INDEX idx_users_business_type ON users(business_type);
```

### 代码变更

#### 模型文件修改

**文件**: `/Users/lichuansong/Desktop/projects/wlxj_python/models/user.py`
```python
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    business_type = db.Column(db.String(20), default='oil')  # admin, oil, fast_moving
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系保持不变，但查询逻辑改变
    suppliers = db.relationship('Supplier', backref='creator', lazy=True)
    orders = db.relationship('Order', backref='creator', lazy=True)
    
    def is_admin(self):
        return self.business_type == 'admin'
        
    def get_business_type_display(self):
        type_map = {
            'admin': '系统管理员',
            'oil': '石油化工',
            'fast_moving': '快消品'
        }
        return type_map.get(self.business_type, self.business_type)
```

**文件**: `/Users/lichuansong/Desktop/projects/wlxj_python/models/supplier.py`
```python
class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    access_code = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    webhook_url = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 创建者
    business_type = db.Column(db.String(20), nullable=False, default='oil')  # 业务类型
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    quotes = db.relationship('Quote', backref='supplier', lazy=True)
```

**文件**: `/Users/lichuansong/Desktop/projects/wlxj_python/models/order.py`
```python
class Order(db.Model):
    __tablename__ = 'orders'
    
    # ... 保留现有缓存机制代码 ...
    
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False)
    warehouse = db.Column(db.String(200), nullable=False)
    goods = db.Column(db.Text, nullable=False)
    delivery_address = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), default='active')
    selected_supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    selected_price = db.Column(db.Numeric(10, 2), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 创建者
    business_type = db.Column(db.String(20), nullable=False, default='oil')  # 业务类型
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系保持不变
    quotes = db.relationship('Quote', backref='order', lazy=True)
    selected_supplier = db.relationship('Supplier', foreign_keys=[selected_supplier_id])
    suppliers = db.relationship('Supplier', secondary=order_suppliers, backref='orders')
```

#### 权限控制装饰器

**新增文件**: `/Users/lichuansong/Desktop/projects/wlxj_python/utils/auth.py`
```python
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
```

#### 业务逻辑查询修改

**文件**: `/Users/lichuansong/Desktop/projects/wlxj_python/app.py`
- 移除register路由（第52-68行）
- 修改dashboard路由查询逻辑：
```python
@app.route('/dashboard')
@login_required
def dashboard():
    from models import Order, Supplier
    from utils.auth import business_type_filter
    
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
```

**文件**: `/Users/lichuansong/Desktop/projects/wlxj_python/routes/supplier.py`
- 修改所有查询逻辑，将`filter_by(user_id=current_user.id)`改为按业务类型过滤
- 创建供应商时设置business_type

**文件**: `/Users/lichuansong/Desktop/projects/wlxj_python/routes/order.py`
- 修改所有查询逻辑，将`filter_by(user_id=current_user.id)`改为按业务类型过滤
- 创建订单时设置business_type

### API变更

#### 新增用户管理接口

**文件**: `/Users/lichuansong/Desktop/projects/wlxj_python/routes/admin.py`

新增路由：
```python
@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """添加新用户"""
    if request.method == 'POST':
        from models import User
        from werkzeug.security import generate_password_hash
        
        username = request.form.get('username')
        password = request.form.get('password')
        business_type = request.form.get('business_type')
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
        else:
            user = User(
                username=username,
                password=generate_password_hash(password),
                business_type=business_type
            )
            db.session.add(user)
            db.session.commit()
            flash('用户添加成功', 'success')
            return redirect(url_for('admin.user_management'))
    
    return render_template('admin/add_user.html')

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """编辑用户"""
    from models import User
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.business_type = request.form.get('business_type')
        
        password = request.form.get('password')
        if password:
            user.password = generate_password_hash(password)
        
        db.session.commit()
        flash('用户修改成功', 'success')
        return redirect(url_for('admin.user_management'))
    
    return render_template('admin/edit_user.html', user=user)

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户"""
    from models import User
    user = User.query.get_or_404(user_id)
    
    if user.business_type == 'admin':
        flash('不能删除管理员账户', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('用户删除成功', 'success')
    
    return redirect(url_for('admin.user_management'))
```

### 配置变更

#### 业务类型配置
**文件**: `/Users/lichuansong/Desktop/projects/wlxj_python/config.py`
```python
# 业务类型配置
BUSINESS_TYPES = {
    'admin': '系统管理员',
    'oil': '石油化工',
    'fast_moving': '快消品'
}
```

## 实施序列

### 阶段1: 数据库结构修改
1. 创建数据库迁移脚本 `/Users/lichuansong/Desktop/projects/wlxj_python/migrations/add_business_type.py`
2. 执行迁移添加business_type字段
3. 更新现有数据的business_type值
4. 添加必要的数据库索引

### 阶段2: 模型层修改
1. 修改User模型 `/Users/lichuansong/Desktop/projects/wlxj_python/models/user.py`
2. 修改Supplier模型 `/Users/lichuansong/Desktop/projects/wlxj_python/models/supplier.py`
3. 修改Order模型 `/Users/lichuansong/Desktop/projects/wlxj_python/models/order.py`
4. 创建权限控制工具 `/Users/lichuansong/Desktop/projects/wlxj_python/utils/auth.py`

### 阶段3: 业务逻辑修改
1. 修改主应用 `/Users/lichuansong/Desktop/projects/wlxj_python/app.py`
   - 移除register路由
   - 修改dashboard逻辑
2. 修改供应商路由 `/Users/lichuansong/Desktop/projects/wlxj_python/routes/supplier.py`
3. 修改订单路由 `/Users/lichuansong/Desktop/projects/wlxj_python/routes/order.py`
4. 扩展管理员路由 `/Users/lichuansong/Desktop/projects/wlxj_python/routes/admin.py`

### 阶段4: 前端界面调整
1. 修改仪表板模板以支持管理员多业务类型统计
2. 创建用户管理界面模板
3. 更新导航菜单，移除注册链接

### 阶段5: 数据清理和初始化
1. 清理现有测试数据
2. 创建默认管理员账户
3. 初始化示例数据（可选）

## 验证计划

### 单元测试
- **用户模型测试**: 验证business_type字段和is_admin()方法
- **权限装饰器测试**: 验证admin_required和业务类型过滤功能
- **查询过滤测试**: 验证按业务类型的数据过滤逻辑

### 集成测试
- **数据隔离测试**: 验证不同业务类型用户只能看到对应数据
- **管理员权限测试**: 验证管理员可以查看所有业务类型数据
- **用户管理功能测试**: 验证管理员添加、编辑、删除用户功能

### 业务逻辑验证
1. **数据共享验证**: 
   - 创建两个oil类型用户，验证可以看到彼此的供应商和订单
   - 创建fast_moving类型用户，验证与oil类型数据隔离
2. **管理员权限验证**:
   - 管理员登录查看所有业务类型的统计数据
   - 管理员添加不同业务类型的用户
3. **注册功能移除验证**:
   - 访问/register路由返回404
   - 登录页面无注册链接

### 数据迁移验证脚本

**文件**: `/Users/lichuansong/Desktop/projects/wlxj_python/migrations/add_business_type.py`
```python
#!/usr/bin/env python3
"""
业务类型系统数据迁移脚本
将用户隔离模式改为业务类型共享模式
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    """执行数据库迁移"""
    db_path = 'database.db'
    backup_path = f'database_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    
    # 1. 备份现有数据库
    if os.path.exists(db_path):
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"数据库已备份到: {backup_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 2. 修改users表结构
        cursor.execute("ALTER TABLE users RENAME COLUMN role TO business_type")
        cursor.execute("UPDATE users SET business_type = 'admin' WHERE business_type = 'admin'")
        cursor.execute("UPDATE users SET business_type = 'oil' WHERE business_type = 'user'")
        
        # 3. 为suppliers表添加business_type字段
        cursor.execute("ALTER TABLE suppliers ADD COLUMN business_type VARCHAR(20) NOT NULL DEFAULT 'oil'")
        cursor.execute("""
            UPDATE suppliers SET business_type = (
                SELECT CASE 
                    WHEN u.business_type = 'admin' THEN 'oil'  
                    ELSE u.business_type 
                END
                FROM users u 
                WHERE u.id = suppliers.user_id
            )
        """)
        
        # 4. 为orders表添加business_type字段
        cursor.execute("ALTER TABLE orders ADD COLUMN business_type VARCHAR(20) NOT NULL DEFAULT 'oil'")
        cursor.execute("""
            UPDATE orders SET business_type = (
                SELECT CASE 
                    WHEN u.business_type = 'admin' THEN 'oil'  
                    ELSE u.business_type 
                END
                FROM users u 
                WHERE u.id = orders.user_id
            )
        """)
        
        # 5. 添加索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_business_type ON suppliers(business_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_business_type ON orders(business_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_business_type ON users(business_type)")
        
        # 6. 清理测试数据（可选，根据需要执行）
        cursor.execute("DELETE FROM quotes")
        cursor.execute("DELETE FROM order_suppliers") 
        cursor.execute("DELETE FROM suppliers WHERE user_id != 1")  # 保留管理员创建的供应商
        cursor.execute("DELETE FROM orders WHERE user_id != 1")     # 保留管理员创建的订单
        cursor.execute("DELETE FROM users WHERE business_type != 'admin'")  # 保留管理员账户
        
        conn.commit()
        print("数据库迁移成功完成")
        
        # 7. 验证迁移结果
        cursor.execute("SELECT COUNT(*) FROM users WHERE business_type = 'admin'")
        admin_count = cursor.fetchone()[0]
        print(f"管理员账户数量: {admin_count}")
        
        cursor.execute("SELECT COUNT(*) FROM suppliers")
        supplier_count = cursor.fetchone()[0]
        print(f"供应商数量: {supplier_count}")
        
        cursor.execute("SELECT COUNT(*) FROM orders")
        order_count = cursor.fetchone()[0]
        print(f"订单数量: {order_count}")
        
    except Exception as e:
        conn.rollback()
        print(f"迁移失败: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()
```

### 初始化脚本

**文件**: `/Users/lichuansong/Desktop/projects/wlxj_python/init_business_type_system.py`
```python
#!/usr/bin/env python3
"""
业务类型系统初始化脚本
创建默认管理员和示例业务用户
"""

from app import app, db
from models import User
from werkzeug.security import generate_password_hash

def init_business_type_system():
    """初始化业务类型系统"""
    with app.app_context():
        # 创建默认管理员
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password=generate_password_hash('admin123'),
                business_type='admin'
            )
            db.session.add(admin)
        
        # 创建示例用户（可选）
        test_users = [
            {'username': 'oil_user1', 'password': 'password123', 'business_type': 'oil'},
            {'username': 'oil_user2', 'password': 'password123', 'business_type': 'oil'},
            {'username': 'fast_user1', 'password': 'password123', 'business_type': 'fast_moving'},
        ]
        
        for user_data in test_users:
            if not User.query.filter_by(username=user_data['username']).first():
                user = User(
                    username=user_data['username'],
                    password=generate_password_hash(user_data['password']),
                    business_type=user_data['business_type']
                )
                db.session.add(user)
        
        db.session.commit()
        print("业务类型系统初始化完成")

if __name__ == '__main__':
    init_business_type_system()
```

## 风险评估和缓解措施

### 主要风险
1. **数据迁移风险**: 现有数据可能丢失或损坏
2. **业务连续性风险**: 迁移期间系统不可用
3. **权限混乱风险**: 用户可能看到不应该看到的数据

### 缓解措施  
1. **数据备份**: 迁移前自动备份数据库
2. **分阶段实施**: 按模块逐步迁移，降低影响范围
3. **充分测试**: 每个阶段完成后进行完整测试
4. **回滚机制**: 准备回滚脚本，问题时快速恢复

本技术规格说明提供了将用户数据隔离模式改为业务类型数据共享模式的完整实施计划，确保代码生成代理可以按照规格直接实施所有必要的修改。