import os
import logging
from datetime import timedelta
from utils.env_validator import EnvironmentValidator

class Config:
    # 必需配置项 - 生产环境必须通过环境变量设置
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if os.environ.get('FLASK_ENV') == 'production':
            raise EnvironmentError("生产环境必须设置 SECRET_KEY 环境变量")
        SECRET_KEY = 'trade-inquiry-system-secret-key-2025'  # 开发环境默认值
        logging.warning("使用默认SECRET_KEY，仅适用于开发环境")
    
    # 验证密钥强度
    is_secure, key_message = EnvironmentValidator.validate_secret_key_strength(SECRET_KEY)
    if not is_secure:
        if os.environ.get('FLASK_ENV') == 'production':
            raise EnvironmentError(f"SECRET_KEY安全验证失败: {key_message}")
        logging.warning(f"SECRET_KEY安全警告: {key_message}")
    
    # 数据库配置
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        if os.environ.get('FLASK_ENV') == 'production':
            raise EnvironmentError("生产环境必须设置 DATABASE_URL 环境变量")
        DATABASE_URL = 'sqlite:///database.db'
        logging.warning("使用默认数据库配置，仅适用于开发环境")
    
    # 验证数据库配置
    db_valid, db_message = EnvironmentValidator.validate_database_config(DATABASE_URL)
    if not db_valid:
        if os.environ.get('FLASK_ENV') == 'production':
            raise EnvironmentError(f"数据库配置验证失败: {db_message}")
        logging.warning(f"数据库配置警告: {db_message}")
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session配置
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # 企业微信配置
    WEWORK_WEBHOOK_URL = os.environ.get('WEWORK_WEBHOOK_URL', '')
    
    # 备份配置
    BACKUP_DIR = os.environ.get('BACKUP_DIR', 'backup')
    BACKUP_KEEP_DAYS = int(os.environ.get('BACKUP_KEEP_DAYS', '7'))
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', '10485760'))  # 10MB
    
    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/app.log')
    
    # 安全配置
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1小时

# 业务类型配置
BUSINESS_TYPES = {
    'admin': '系统管理员',
    'oil': '油脂',
    'fast_moving': '快消'
}

# 环境特定配置
class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    
    # 开发环境特殊配置
    WTF_CSRF_ENABLED = False  # 开发时可禁用CSRF
    SESSION_COOKIE_SECURE = False  # 开发环境允许HTTP

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    
    # 生产环境额外安全配置
    PREFERRED_URL_SCHEME = 'https'
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_ENABLED = True
    
    # 强制HTTPS重定向
    FORCE_HTTPS = True
    
    # 生产环境日志配置
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'default': {
                'level': 'INFO',
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
            },
            'file': {
                'level': 'INFO',
                'formatter': 'standard',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': Config.LOG_FILE,
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
        },
        'loggers': {
            '': {
                'handlers': ['default', 'file'],
                'level': Config.LOG_LEVEL,
                'propagate': False
            }
        }
    }

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'testing-secret-key'
    WTF_CSRF_ENABLED = False
    
    # 测试环境特殊配置
    BACKUP_KEEP_DAYS = 1
    MAX_CONTENT_LENGTH = 1024 * 1024  # 1MB for testing

# 根据环境选择配置
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(env_name=None):
    """获取配置类
    
    Args:
        env_name: 环境名称，默认从FLASK_ENV环境变量获取
        
    Returns:
        配置类
    """
    if env_name is None:
        env_name = os.environ.get('FLASK_ENV', 'default')
    
    return config.get(env_name, config['default'])