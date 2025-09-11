from flask_login import UserMixin
from datetime import datetime
from . import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')  # user, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    suppliers = db.relationship('Supplier', backref='user', lazy=True)
    orders = db.relationship('Order', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def is_admin(self):
        return self.role == 'admin'