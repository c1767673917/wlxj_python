from flask_login import UserMixin
from datetime import datetime
from . import db
from utils.beijing_time_helper import BeijingTimeHelper

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    business_type = db.Column(db.String(20), default='oil')  # admin, oil, fast_moving
    created_at = db.Column(db.DateTime, default=BeijingTimeHelper.now)
    
    # 关联关系配置级联删除策略
    suppliers = db.relationship('Supplier', backref='creator', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='creator', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def is_admin(self):
        return self.business_type == 'admin'
        
    def get_business_type_display(self):
        type_map = {
            'admin': '系统管理员',
            'oil': '油脂',
            'fast_moving': '快消品'
        }
        return type_map.get(self.business_type, self.business_type)