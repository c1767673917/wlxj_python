#!/usr/bin/env python3
"""
备份管理器配置文件
集中管理所有备份相关的配置项
"""

import os
from pathlib import Path


class BackupConfig:
    """备份配置类"""
    
    # 默认配置
    DEFAULT_KEEP_DAYS = 7
    DEFAULT_MAX_BACKUP_FILES = 50
    DEFAULT_BACKUP_DIR = 'backup'
    DEFAULT_LOG_LEVEL = 'INFO'
    DEFAULT_LOG_DIR = 'logs'
    DEFAULT_COMPRESS_BACKUPS = True
    
    # 性能配置
    DEFAULT_CHUNK_SIZE = 64 * 1024  # 64KB chunks for file operations
    DEFAULT_MAX_BACKUP_SIZE_MB = 1024  # 1GB max backup size
    
    # 监控配置
    DEFAULT_HEALTH_CHECK_INTERVAL = 300  # 5 minutes
    DEFAULT_BACKUP_SCHEDULE_HOUR = 2  # 凌晨2点执行备份
    
    def __init__(self, config_file=None):
        """
        初始化配置
        
        Args:
            config_file: 可选的配置文件路径
        """
        self._load_defaults()
        
        if config_file and os.path.exists(config_file):
            self._load_from_file(config_file)
        
        self._load_from_env()
        self._validate_config()
    
    def _load_defaults(self):
        """加载默认配置"""
        self.keep_days = self.DEFAULT_KEEP_DAYS
        self.max_backup_files = self.DEFAULT_MAX_BACKUP_FILES
        self.backup_dir = self.DEFAULT_BACKUP_DIR
        self.log_level = self.DEFAULT_LOG_LEVEL
        self.log_dir = self.DEFAULT_LOG_DIR
        self.compress_backups = self.DEFAULT_COMPRESS_BACKUPS
        self.chunk_size = self.DEFAULT_CHUNK_SIZE
        self.max_backup_size_mb = self.DEFAULT_MAX_BACKUP_SIZE_MB
        self.health_check_interval = self.DEFAULT_HEALTH_CHECK_INTERVAL
        self.backup_schedule_hour = self.DEFAULT_BACKUP_SCHEDULE_HOUR
    
    def _load_from_file(self, config_file):
        """从配置文件加载配置"""
        try:
            import json
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            for key, value in config_data.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                    
        except (json.JSONDecodeError, IOError) as e:
            raise ConfigurationError(f"配置文件加载失败: {e}")
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        env_mappings = {
            'BACKUP_KEEP_DAYS': ('keep_days', int),
            'BACKUP_MAX_FILES': ('max_backup_files', int),
            'BACKUP_DIR': ('backup_dir', str),
            'BACKUP_LOG_LEVEL': ('log_level', str),
            'BACKUP_LOG_DIR': ('log_dir', str),
            'BACKUP_COMPRESS': ('compress_backups', bool),
            'BACKUP_CHUNK_SIZE': ('chunk_size', int),
            'BACKUP_MAX_SIZE_MB': ('max_backup_size_mb', int),
            'BACKUP_HEALTH_INTERVAL': ('health_check_interval', int),
            'BACKUP_SCHEDULE_HOUR': ('backup_schedule_hour', int),
        }
        
        for env_key, (attr_name, attr_type) in env_mappings.items():
            env_value = os.environ.get(env_key)
            if env_value is not None:
                try:
                    if attr_type == bool:
                        value = env_value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        value = attr_type(env_value)
                    setattr(self, attr_name, value)
                except ValueError as e:
                    raise ConfigurationError(f"环境变量 {env_key} 格式错误: {e}")
    
    def _validate_config(self):
        """验证配置的有效性"""
        if self.keep_days < 1:
            raise ConfigurationError("keep_days 必须大于0")
        
        if self.max_backup_files < 1:
            raise ConfigurationError("max_backup_files 必须大于0")
        
        if self.chunk_size < 1024:
            raise ConfigurationError("chunk_size 必须至少为1024字节")
        
        if self.max_backup_size_mb < 1:
            raise ConfigurationError("max_backup_size_mb 必须大于0")
        
        if not (0 <= self.backup_schedule_hour <= 23):
            raise ConfigurationError("backup_schedule_hour 必须在0-23之间")
        
        if self.health_check_interval < 60:
            raise ConfigurationError("health_check_interval 必须至少为60秒")
        
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_log_levels:
            raise ConfigurationError(f"log_level 必须是以下之一: {valid_log_levels}")
    
    def get_backup_dir_path(self):
        """获取备份目录的完整路径"""
        return Path(self.backup_dir).resolve()
    
    def get_log_dir_path(self):
        """获取日志目录的完整路径"""
        return Path(self.log_dir).resolve()
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'keep_days': self.keep_days,
            'max_backup_files': self.max_backup_files,
            'backup_dir': self.backup_dir,
            'log_level': self.log_level,
            'log_dir': self.log_dir,
            'compress_backups': self.compress_backups,
            'chunk_size': self.chunk_size,
            'max_backup_size_mb': self.max_backup_size_mb,
            'health_check_interval': self.health_check_interval,
            'backup_schedule_hour': self.backup_schedule_hour,
        }


class ConfigurationError(Exception):
    """配置错误异常"""
    pass


# 全局配置实例
_global_config = None


def get_backup_config(config_file=None):
    """获取全局备份配置实例"""
    global _global_config
    if _global_config is None:
        _global_config = BackupConfig(config_file)
    return _global_config


def reset_backup_config():
    """重置全局配置实例（主要用于测试）"""
    global _global_config
    _global_config = None