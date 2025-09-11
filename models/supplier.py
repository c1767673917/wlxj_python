from datetime import datetime
import secrets
from . import db

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    access_code = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    webhook_url = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    quotes = db.relationship('Quote', backref='supplier', lazy=True)
    
    def __repr__(self):
        return f'<Supplier {self.name}>'
    
    def generate_access_url(self):
        from flask import url_for
        return url_for('supplier_portal', access_code=self.access_code, _external=True)