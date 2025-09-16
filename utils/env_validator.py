import os
import logging
import re
from typing import Dict, List, Tuple, Set, Optional

class EnvironmentValidator:
    """生产环境配置验证器"""
    
    # 必需的环境变量
    REQUIRED_ENV_VARS = {
        'SECRET_KEY': '应用密钥，用于会话加密和安全令牌生成',
        'DATABASE_URL': '数据库连接字符串',
    }
    
    # 可选但推荐的环境变量
    RECOMMENDED_ENV_VARS = {
        'WEWORK_WEBHOOK_URL': '企业微信通知地址',
        'FLASK_ENV': 'Flask运行环境（development/production/testing）',
        'LOG_LEVEL': '日志级别（DEBUG/INFO/WARNING/ERROR）',
        'LOG_FILE': '日志文件路径',
        'BACKUP_DIR': '备份文件目录',
        'BACKUP_KEEP_DAYS': '备份文件保留天数',
        'MAX_CONTENT_LENGTH': '最大上传文件大小（字节）',
    }
    
    # 危险的默认值
    DANGEROUS_DEFAULTS = {
        'SECRET_KEY': {
            'trade-inquiry-system-secret-key-2025',
            'dev-secret-key',
            'test-secret',
            'default-secret',
            'secret-key',
            'flask-secret-key',
        },
        'DATABASE_URL': {
            'sqlite:///database.db',
            'sqlite:///test.db',
            'sqlite:///:memory:',
        },
    }
    
    # 生产环境不应设置的变量
    PRODUCTION_FORBIDDEN_VARS = {
        'FLASK_DEBUG': '生产环境不应启用调试模式',
        'DEBUG': '生产环境不应启用调试模式',
    }
    
    @classmethod
    def validate_production_env(cls) -> Tuple[bool, List[str], List[str]]:
        """验证生产环境配置
        
        Returns:
            Tuple[bool, List[str], List[str]]: (是否通过验证, 错误列表, 警告列表)
        """
        errors = []
        warnings = []
        
        # 检查必需环境变量
        for var_name, description in cls.REQUIRED_ENV_VARS.items():
            value = os.environ.get(var_name)
            if not value:
                errors.append(f"缺少必需环境变量: {var_name} ({description})")
            elif cls._is_dangerous_default(var_name, value):
                errors.append(f"使用了不安全的默认值: {var_name}")
        
        # 检查推荐环境变量
        for var_name, description in cls.RECOMMENDED_ENV_VARS.items():
            if not os.environ.get(var_name):
                warnings.append(f"建议设置环境变量: {var_name} ({description})")
        
        # 检查Flask环境
        flask_env = os.environ.get('FLASK_ENV', '').lower()
        if flask_env and flask_env != 'production':
            warnings.append(f"当前Flask环境为'{flask_env}'，生产环境建议设置为'production'")
        
        # 检查生产环境禁用的变量
        for var_name, reason in cls.PRODUCTION_FORBIDDEN_VARS.items():
            value = os.environ.get(var_name, '').lower()
            if value in ['true', '1', 'yes', 'on']:
                errors.append(f"生产环境不应启用: {var_name} ({reason})")
        
        # 检查数据库URL安全性
        db_url = os.environ.get('DATABASE_URL', '')
        if db_url:
            db_warnings = cls._validate_database_url(db_url)
            warnings.extend(db_warnings)
        
        # 检查文件路径配置
        path_warnings = cls._validate_file_paths()
        warnings.extend(path_warnings)
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    @classmethod
    def validate_secret_key_strength(cls, secret_key: str) -> Tuple[bool, str]:
        """验证密钥强度
        
        Args:
            secret_key: 应用密钥
            
        Returns:
            Tuple[bool, str]: (是否安全, 验证消息)
        """
        if not secret_key:
            return False, "密钥不能为空"
        
        if len(secret_key) < 32:
            return False, "密钥长度应至少32个字符"
        
        if cls._is_dangerous_default('SECRET_KEY', secret_key):
            return False, "不能使用默认或常见的密钥"
        
        # 检查复杂度
        has_upper = any(c.isupper() for c in secret_key)
        has_lower = any(c.islower() for c in secret_key)
        has_digit = any(c.isdigit() for c in secret_key)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in secret_key)
        
        complexity_score = sum([has_upper, has_lower, has_digit, has_special])
        if complexity_score < 3:
            return False, "密钥复杂度不足，建议包含大小写字母、数字和特殊字符"
        
        # 检查是否包含常见词汇
        common_words = {'password', 'secret', 'key', 'admin', 'user', 'test', 'dev', 'prod'}
        secret_lower = secret_key.lower()
        for word in common_words:
            if word in secret_lower:
                return False, f"密钥不应包含常见词汇: {word}"
        
        return True, "密钥强度验证通过"
    
    @classmethod
    def validate_database_config(cls, db_url: str) -> Tuple[bool, str]:
        """验证数据库配置
        
        Args:
            db_url: 数据库连接字符串
            
        Returns:
            Tuple[bool, str]: (是否有效, 验证消息)
        """
        if not db_url:
            return False, "数据库URL不能为空"
        
        if cls._is_dangerous_default('DATABASE_URL', db_url):
            return False, "使用了不安全的默认数据库配置"
        
        # 检查SQLite文件路径
        if db_url.startswith('sqlite:///'):
            file_path = db_url.replace('sqlite:///', '')
            if file_path and not os.path.isabs(file_path):
                return False, "SQLite数据库路径应为绝对路径"
        
        # 检查是否使用内存数据库
        if 'memory' in db_url.lower():
            return False, "生产环境不应使用内存数据库"
        
        return True, "数据库配置验证通过"
    
    @classmethod
    def validate_logging_config(cls) -> Tuple[bool, List[str]]:
        """验证日志配置
        
        Returns:
            Tuple[bool, List[str]]: (是否有效, 建议列表)
        """
        suggestions = []
        
        log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        
        if log_level not in valid_levels:
            suggestions.append(f"日志级别'{log_level}'无效，建议使用: {', '.join(valid_levels)}")
        elif log_level == 'DEBUG':
            suggestions.append("生产环境建议使用INFO或更高级别的日志")
        
        log_file = os.environ.get('LOG_FILE')
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                suggestions.append(f"日志目录不存在: {log_dir}")
        else:
            suggestions.append("建议设置LOG_FILE环境变量指定日志文件路径")
        
        return len(suggestions) == 0, suggestions
    
    @classmethod
    def generate_security_report(cls) -> Dict[str, any]:
        """生成安全配置报告
        
        Returns:
            Dict[str, any]: 安全配置报告
        """
        is_valid, errors, warnings = cls.validate_production_env()
        
        # 密钥强度检查
        secret_key = os.environ.get('SECRET_KEY', '')
        key_valid, key_msg = cls.validate_secret_key_strength(secret_key)
        
        # 数据库配置检查
        db_url = os.environ.get('DATABASE_URL', '')
        db_valid, db_msg = cls.validate_database_config(db_url)
        
        # 日志配置检查
        log_valid, log_suggestions = cls.validate_logging_config()
        
        report = {
            'overall_status': 'PASS' if is_valid and key_valid and db_valid else 'FAIL',
            'timestamp': cls._get_current_timestamp(),
            'environment': os.environ.get('FLASK_ENV', 'unknown'),
            'validation_results': {
                'environment_variables': {
                    'status': 'PASS' if is_valid else 'FAIL',
                    'errors': errors,
                    'warnings': warnings
                },
                'secret_key': {
                    'status': 'PASS' if key_valid else 'FAIL',
                    'message': key_msg,
                    'length': len(secret_key) if secret_key else 0
                },
                'database': {
                    'status': 'PASS' if db_valid else 'FAIL',
                    'message': db_msg,
                    'type': cls._get_database_type(db_url)
                },
                'logging': {
                    'status': 'PASS' if log_valid else 'WARN',
                    'suggestions': log_suggestions
                }
            },
            'recommendations': cls._generate_recommendations(errors, warnings)
        }
        
        return report
    
    @classmethod
    def _is_dangerous_default(cls, var_name: str, value: str) -> bool:
        """检查是否为危险的默认值"""
        dangerous_values = cls.DANGEROUS_DEFAULTS.get(var_name, set())
        return value in dangerous_values
    
    @classmethod
    def _validate_database_url(cls, db_url: str) -> List[str]:
        """验证数据库URL"""
        warnings = []
        
        if 'localhost' in db_url or '127.0.0.1' in db_url:
            warnings.append("数据库连接使用localhost，请确认是否为生产环境配置")
        
        if 'password' not in db_url.lower() and not db_url.startswith('sqlite'):
            warnings.append("数据库连接字符串中未检测到密码，请确认安全性")
        
        if db_url.startswith('sqlite:///') and 'database.db' in db_url:
            warnings.append("使用默认SQLite数据库文件名，建议使用更具体的名称")
        
        return warnings
    
    @classmethod
    def _validate_file_paths(cls) -> List[str]:
        """验证文件路径配置"""
        warnings = []
        
        # 检查备份目录
        backup_dir = os.environ.get('BACKUP_DIR', 'backup')
        if not os.path.isabs(backup_dir):
            warnings.append("备份目录使用相对路径，建议使用绝对路径")
        
        # 检查日志文件
        log_file = os.environ.get('LOG_FILE')
        if log_file and not os.path.isabs(log_file):
            warnings.append("日志文件使用相对路径，建议使用绝对路径")
        
        return warnings
    
    @classmethod
    def _get_database_type(cls, db_url: str) -> str:
        """获取数据库类型"""
        if db_url.startswith('sqlite'):
            return 'SQLite'
        elif db_url.startswith('postgresql'):
            return 'PostgreSQL'
        elif db_url.startswith('mysql'):
            return 'MySQL'
        else:
            return 'Unknown'
    
    @classmethod
    def _generate_recommendations(cls, errors: List[str], warnings: List[str]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        if errors:
            recommendations.append("立即修复所有错误项，这些问题会影响应用安全性")
        
        if warnings:
            recommendations.append("考虑处理警告项以提高系统安全性和稳定性")
        
        recommendations.extend([
            "定期更新SECRET_KEY以提高安全性",
            "在生产环境使用外部数据库（如PostgreSQL）而非SQLite",
            "配置日志轮转以防止日志文件过大",
            "设置适当的文件权限限制访问敏感文件",
            "考虑使用环境变量管理工具（如dotenv）"
        ])
        
        return recommendations
    
    @classmethod
    def _get_current_timestamp(cls) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'

def validate_startup_environment() -> Tuple[bool, List[str], List[str]]:
    """应用启动时的环境验证
    
    Returns:
        Tuple[bool, List[str], List[str]]: (是否通过验证, 错误列表, 警告列表)
    """
    is_valid, errors, warnings = EnvironmentValidator.validate_production_env()
    
    # 记录验证结果
    if errors:
        for error in errors:
            logging.error(f"环境配置错误: {error}")
    
    if warnings:
        for warning in warnings:
            logging.warning(f"环境配置警告: {warning}")
    
    # 在生产环境下，配置错误应该阻止应用启动
    flask_env = os.environ.get('FLASK_ENV', '').lower()
    if not is_valid and flask_env == 'production':
        logging.critical("生产环境配置验证失败，应用启动中止")
        raise EnvironmentError("生产环境配置验证失败，请修复配置错误后重启应用")
    
    # 生成安全报告
    if flask_env == 'production':
        report = EnvironmentValidator.generate_security_report()
        logging.info(f"安全配置报告: {report['overall_status']}")
    
    return is_valid, errors, warnings

def check_environment_security() -> Dict[str, any]:
    """检查环境安全性（用于管理员查看）
    
    Returns:
        Dict[str, any]: 安全检查报告
    """
    return EnvironmentValidator.generate_security_report()