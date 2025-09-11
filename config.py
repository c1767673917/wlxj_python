import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'trade-inquiry-system-secret-key-2025'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session配置
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # 企业微信配置
    WEWORK_WEBHOOK_URL = os.environ.get('WEWORK_WEBHOOK_URL') or ''
    
    # 备份配置
    BACKUP_DIR = 'backup'
    BACKUP_KEEP_DAYS = 7