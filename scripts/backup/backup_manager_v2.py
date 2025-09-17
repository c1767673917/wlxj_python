#!/usr/bin/env python3
"""
数据备份管理器 v2.0
用于自动备份SQLite数据库 - 改进版本
包含增强的错误处理、配置管理和监控功能
"""

import os
import shutil
import sqlite3
import json
import gzip
import time
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Optional, Dict, List, Tuple, Union

# 导入配置和异常类
try:
    from config.backup_config import get_backup_config, BackupConfig
except ImportError:
    # 如果无法导入配置，使用默认配置
    class BackupConfig:
        DEFAULT_KEEP_DAYS = 7
        DEFAULT_MAX_BACKUP_FILES = 50
        DEFAULT_BACKUP_DIR = 'backup'
        DEFAULT_COMPRESS_BACKUPS = True
        DEFAULT_CHUNK_SIZE = 64 * 1024
        DEFAULT_MAX_BACKUP_SIZE_MB = 1024
        DEFAULT_LOG_LEVEL = 'INFO'
        DEFAULT_LOG_DIR = 'logs'
        
        def __init__(self):
            self.keep_days = self.DEFAULT_KEEP_DAYS
            self.max_backup_files = self.DEFAULT_MAX_BACKUP_FILES
            self.backup_dir = self.DEFAULT_BACKUP_DIR
            self.compress_backups = self.DEFAULT_COMPRESS_BACKUPS
            self.chunk_size = self.DEFAULT_CHUNK_SIZE
            self.max_backup_size_mb = self.DEFAULT_MAX_BACKUP_SIZE_MB
            self.log_level = self.DEFAULT_LOG_LEVEL
            self.log_dir = self.DEFAULT_LOG_DIR
        
        def get_backup_dir_path(self):
            return Path(self.backup_dir).resolve()
        
        def get_log_dir_path(self):
            return Path(self.log_dir).resolve()
    
    def get_backup_config():
        return BackupConfig()

try:
    from .backup_exceptions import (
        BackupException,
        DatabaseNotFoundException,
        DatabaseAccessException,
        DatabaseCorruptedException,
        BackupDirectoryException,
        BackupCreationException,
        BackupVerificationException,
        BackupRestoreException,
        BackupCompressionException,
        BackupCleanupException,
        BackupSizeException,
        BackupTimeoutException,
        wrap_exception
    )
except ImportError:
    # 如果无法导入自定义异常，使用基础异常
    class BackupException(Exception):
        def __init__(self, message, error_code=None, original_exception=None):
            super().__init__(message)
            self.message = message
            self.error_code = error_code
            self.original_exception = original_exception
    
    DatabaseNotFoundException = BackupException
    DatabaseAccessException = BackupException
    DatabaseCorruptedException = BackupException
    BackupDirectoryException = BackupException
    BackupCreationException = BackupException
    BackupVerificationException = BackupException
    BackupRestoreException = BackupException
    BackupCompressionException = BackupException
    BackupCleanupException = BackupException
    BackupSizeException = BackupException
    BackupTimeoutException = BackupException
    
    def wrap_exception(original_exception, context=None):
        return BackupException(str(original_exception), "WRAPPED_ERROR", original_exception)


# 配置备份专用日志
def setup_backup_logger(config: Optional[BackupConfig] = None) -> logging.Logger:
    """设置备份专用日志配置"""
    if config is None:
        config = get_backup_config()
    
    backup_logger = logging.getLogger('backup_manager')
    
    # 避免重复配置
    if backup_logger.handlers:
        return backup_logger
    
    # 设置日志级别
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    backup_logger.setLevel(log_level)
    
    # 创建日志目录
    log_dir = config.get_log_dir_path()
    try:
        log_dir.mkdir(exist_ok=True, parents=True)
    except (OSError, PermissionError) as e:
        raise BackupDirectoryException(str(log_dir), "创建日志目录", e)
    
    # 文件处理器 - 专用备份日志
    log_file = log_dir / 'backup.log'
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
    except (OSError, PermissionError) as e:
        raise BackupDirectoryException(str(log_file), "创建日志文件", e)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # 只在控制台显示警告和错误
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    backup_logger.addHandler(file_handler)
    backup_logger.addHandler(console_handler)
    
    # 防止向上传播到根日志器
    backup_logger.propagate = False
    
    return backup_logger


# 延迟初始化logger
logger = None

def get_logger() -> logging.Logger:
    """获取全局日志器实例"""
    global logger
    if logger is None:
        logger = setup_backup_logger()
    return logger


class BackupHealthMonitor:
    """备份健康监控器"""
    
    def __init__(self, backup_manager):
        self.backup_manager = backup_manager
        self.logger = get_logger()
        self._last_check_time = None
        self._last_backup_time = None
        self._health_status = {}
    
    def get_health_status(self) -> Dict:
        """获取健康状态"""
        try:
            self._check_database_health()
            self._check_backup_directory_health()
            self._check_recent_backups()
            self._check_disk_space()
            
            self._health_status['last_check'] = datetime.now().isoformat()
            self._health_status['overall_status'] = self._calculate_overall_status()
            
            return self._health_status
            
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return {
                'overall_status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    def _check_database_health(self):
        """检查数据库健康状态"""
        try:
            if not os.path.exists(self.backup_manager.db_path):
                self._health_status['database'] = {
                    'status': 'error',
                    'message': '数据库文件不存在'
                }
                return
            
            # 检查数据库可访问性
            conn = sqlite3.connect(self.backup_manager.db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            
            # 检查文件大小
            file_size = os.path.getsize(self.backup_manager.db_path)
            
            self._health_status['database'] = {
                'status': 'healthy',
                'path': self.backup_manager.db_path,
                'size_bytes': file_size,
                'accessible': True
            }
            
        except Exception as e:
            self._health_status['database'] = {
                'status': 'error',
                'message': f'数据库检查失败: {e}'
            }
    
    def _check_backup_directory_health(self):
        """检查备份目录健康状态"""
        try:
            backup_dir = self.backup_manager.backup_dir
            
            if not backup_dir.exists():
                self._health_status['backup_directory'] = {
                    'status': 'error',
                    'message': '备份目录不存在'
                }
                return
            
            # 检查写权限
            test_file = backup_dir / '.health_check'
            test_file.touch()
            test_file.unlink()
            
            # 统计备份文件
            backup_files = list(backup_dir.glob('database_backup_*.db*'))
            total_size = sum(f.stat().st_size for f in backup_files)
            
            self._health_status['backup_directory'] = {
                'status': 'healthy',
                'path': str(backup_dir),
                'backup_count': len(backup_files),
                'total_size_bytes': total_size,
                'writable': True
            }
            
        except Exception as e:
            self._health_status['backup_directory'] = {
                'status': 'error',
                'message': f'备份目录检查失败: {e}'
            }
    
    def _check_recent_backups(self):
        """检查最近的备份"""
        try:
            backups = self.backup_manager.list_backups()
            
            if not backups:
                self._health_status['recent_backups'] = {
                    'status': 'warning',
                    'message': '没有找到备份文件'
                }
                return
            
            latest_backup = max(backups, key=lambda x: x['created_at'])
            hours_since_last = (datetime.now() - latest_backup['created_at']).total_seconds() / 3600
            
            status = 'healthy'
            if hours_since_last > 48:  # 超过48小时
                status = 'warning'
            elif hours_since_last > 168:  # 超过一周
                status = 'error'
            
            self._health_status['recent_backups'] = {
                'status': status,
                'latest_backup': latest_backup['filename'],
                'last_backup_time': latest_backup['created_at'].isoformat(),
                'hours_since_last': round(hours_since_last, 1)
            }
            
        except Exception as e:
            self._health_status['recent_backups'] = {
                'status': 'error',
                'message': f'备份检查失败: {e}'
            }
    
    def _check_disk_space(self):
        """检查磁盘空间"""
        try:
            backup_dir = self.backup_manager.backup_dir
            statvfs = os.statvfs(backup_dir)
            
            # 可用空间 (bytes)
            available_bytes = statvfs.f_frsize * statvfs.f_bavail
            total_bytes = statvfs.f_frsize * statvfs.f_blocks
            used_bytes = total_bytes - available_bytes
            
            usage_percent = (used_bytes / total_bytes) * 100 if total_bytes > 0 else 0
            
            status = 'healthy'
            if usage_percent > 90:
                status = 'error'
            elif usage_percent > 80:
                status = 'warning'
            
            self._health_status['disk_space'] = {
                'status': status,
                'available_bytes': available_bytes,
                'total_bytes': total_bytes,
                'usage_percent': round(usage_percent, 1)
            }
            
        except Exception as e:
            self._health_status['disk_space'] = {
                'status': 'error',
                'message': f'磁盘空间检查失败: {e}'
            }
    
    def _calculate_overall_status(self) -> str:
        """计算总体健康状态"""
        statuses = []
        for component, info in self._health_status.items():
            if isinstance(info, dict) and 'status' in info:
                statuses.append(info['status'])
        
        if 'error' in statuses:
            return 'error'
        elif 'warning' in statuses:
            return 'warning'
        else:
            return 'healthy'


class BackupManager:
    """数据库备份管理器 v2.0"""
    
    def __init__(self, db_path: Optional[str] = None, backup_dir: Optional[str] = None, config: Optional[BackupConfig] = None):
        """
        初始化备份管理器
        
        Args:
            db_path: 数据库文件路径
            backup_dir: 备份目录路径
            config: 备份配置对象
        """
        self.config = config or get_backup_config()
        self.logger = get_logger()
        
        # 如果没有指定路径，尝试从Flask应用获取
        if db_path is None:
            db_path = self._get_flask_db_path()
        
        self.db_path = db_path
        
        # 使用配置中的备份目录或传入的目录
        if backup_dir is None:
            backup_dir = self.config.backup_dir
        self.backup_dir = Path(backup_dir)
        
        # 确保备份目录存在且可写
        self._setup_backup_directory()
        
        # 初始化健康监控器
        self.health_monitor = BackupHealthMonitor(self)
        
        # 操作锁，防止并发操作
        self._operation_lock = threading.Lock()
    
    def _setup_backup_directory(self):
        """设置备份目录"""
        try:
            self.backup_dir.mkdir(exist_ok=True, parents=True)
            
            # 测试写权限
            test_file = self.backup_dir / '.write_test'
            test_file.touch()
            test_file.unlink()
            
            self.logger.info(f"备份目录已就绪: {self.backup_dir}")
            
        except (OSError, PermissionError) as e:
            error_msg = f"备份目录设置失败: {self.backup_dir}"
            self.logger.error(f"{error_msg}, 错误: {e}")
            raise BackupDirectoryException(str(self.backup_dir), "设置", e)
    
    def _get_flask_db_path(self) -> str:
        """获取Flask应用的实际数据库路径"""
        try:
            # 尝试导入Flask配置
            from flask import current_app
            if current_app:
                uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
                if uri.startswith('sqlite:///'):
                    path_part = uri[10:]  # 去掉 'sqlite:///'
                    if not path_part.startswith('/'):
                        # 相对路径，基于instance文件夹
                        instance_path = current_app.instance_path
                        return os.path.join(instance_path, path_part)
                    return path_part
        except (ImportError, RuntimeError):
            # Flask应用上下文不可用，使用默认查找逻辑
            pass
        
        # 回退到智能查找
        return self._find_database_file()
    
    def _find_database_file(self) -> str:
        """智能查找数据库文件"""
        current_dir = os.getcwd()
        
        # 优先级顺序查找
        search_paths = [
            os.path.join(current_dir, 'instance', 'database.db'),
            os.path.join(current_dir, 'database.db'),
            os.path.join(current_dir, 'app.db'),
            os.path.join(current_dir, 'instance', 'app.db')
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                self.logger.info(f"找到数据库文件: {path}")
                return path
        
        # 如果都没找到，使用默认路径并警告
        default_path = os.path.join(current_dir, 'database.db')
        self.logger.warning(f"未找到数据库文件，使用默认路径: {default_path}")
        return default_path
    
    def _validate_database_file(self):
        """验证数据库文件的有效性"""
        if not os.path.exists(self.db_path):
            raise DatabaseNotFoundException(self.db_path)
        
        if not os.access(self.db_path, os.R_OK):
            raise DatabaseAccessException(self.db_path, "read")
        
        file_size = os.path.getsize(self.db_path)
        if file_size == 0:
            raise DatabaseCorruptedException(self.db_path, "文件为空")
        
        max_size_bytes = self.config.max_backup_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise BackupSizeException(self.db_path, file_size, max_size_bytes)
        
        return file_size
    
    def create_backup(self, compress: Optional[bool] = None, timeout: int = 300) -> Tuple[Union[Path, bool], str]:
        """
        创建数据库备份
        
        Args:
            compress: 是否压缩备份文件，None时使用配置默认值
            timeout: 操作超时时间（秒）
        
        Returns:
            tuple: (备份文件路径或False, 结果消息)
        """
        with self._operation_lock:
            start_time = time.time()
            
            try:
                # 验证数据库文件
                file_size = self._validate_database_file()
                
                if compress is None:
                    compress = self.config.compress_backups
                
                self.logger.info(f"开始备份数据库: {self.db_path} (大小: {file_size} 字节)")
                
                # 生成备份文件名
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f'database_backup_{timestamp}.db'
                
                if compress:
                    backup_filename += '.gz'
                
                backup_path = self.backup_dir / backup_filename
                
                # 检查超时
                if time.time() - start_time > timeout:
                    raise BackupTimeoutException("create_backup", timeout)
                
                # 执行备份
                if compress:
                    self._create_compressed_backup(backup_path, timeout - (time.time() - start_time))
                else:
                    self._create_simple_backup(backup_path, timeout - (time.time() - start_time))
                
                # 验证备份文件
                backup_size = self._validate_backup_file(backup_path)
                
                # 记录备份信息
                self._log_backup_info(backup_path, timestamp)
                
                elapsed_time = time.time() - start_time
                success_msg = f"备份创建成功: {backup_path.name} (大小: {backup_size} 字节, 用时: {elapsed_time:.2f}秒)"
                self.logger.info(success_msg)
                return backup_path, success_msg
                
            except (DatabaseNotFoundException, DatabaseAccessException, DatabaseCorruptedException,
                    BackupSizeException, BackupTimeoutException) as e:
                self.logger.error(f"备份创建失败: {e}")
                return False, str(e)
            except Exception as e:
                wrapped_exception = wrap_exception(e, {
                    'operation': 'create_backup',
                    'db_path': self.db_path,
                    'backup_dir': str(self.backup_dir)
                })
                self.logger.error(f"备份创建过程发生未知错误: {wrapped_exception}", exc_info=True)
                return False, str(wrapped_exception)
    
    def _validate_backup_file(self, backup_path: Path) -> int:
        """验证备份文件的有效性"""
        if not backup_path.exists():
            raise BackupCreationException(str(backup_path), "备份文件不存在")
        
        backup_size = backup_path.stat().st_size
        if backup_size == 0:
            backup_path.unlink()  # 删除空文件
            raise BackupCreationException(str(backup_path), "备份文件为空")
        
        return backup_size
    
    def _create_simple_backup(self, backup_path: Path, timeout: float):
        """创建简单备份（直接复制文件）"""
        try:
            start_time = time.time()
            
            # 使用分块复制来支持大文件和超时检查
            with open(self.db_path, 'rb') as src:
                with open(backup_path, 'wb') as dst:
                    while True:
                        if time.time() - start_time > timeout:
                            backup_path.unlink(missing_ok=True)
                            raise BackupTimeoutException("simple_backup", timeout)
                        
                        chunk = src.read(self.config.chunk_size)
                        if not chunk:
                            break
                        dst.write(chunk)
            
        except (OSError, IOError) as e:
            backup_path.unlink(missing_ok=True)
            raise BackupCreationException(str(backup_path), f"文件复制失败: {e}", e)
    
    def _create_compressed_backup(self, backup_path: Path, timeout: float):
        """创建压缩备份"""
        try:
            start_time = time.time()
            
            with open(self.db_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    while True:
                        if time.time() - start_time > timeout:
                            backup_path.unlink(missing_ok=True)
                            raise BackupTimeoutException("compressed_backup", timeout)
                        
                        chunk = f_in.read(self.config.chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        
        except (OSError, IOError, gzip.BadGzipFile) as e:
            backup_path.unlink(missing_ok=True)
            raise BackupCompressionException(str(backup_path), "compression", e)
    
    def _log_backup_info(self, backup_path: Path, timestamp: str):
        """记录备份信息到JSON文件"""
        try:
            info_file = self.backup_dir / 'backup_info.json'
            
            backup_info = {
                'timestamp': timestamp,
                'filename': backup_path.name,
                'size': backup_path.stat().st_size,
                'original_size': Path(self.db_path).stat().st_size,
                'created_at': datetime.now().isoformat(),
                'compression_ratio': None
            }
            
            # 计算压缩比
            if backup_path.suffix == '.gz':
                backup_info['compression_ratio'] = backup_info['size'] / backup_info['original_size']
            
            # 读取现有信息
            if info_file.exists():
                with open(info_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {'backups': []}
            
            # 添加新备份信息
            data['backups'].append(backup_info)
            
            # 保持最近的备份记录
            data['backups'] = data['backups'][-self.config.max_backup_files:]
            
            # 写入文件
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.warning(f"记录备份信息失败: {e}")
    
    def cleanup_old_backups(self, keep_days: Optional[int] = None) -> int:
        """
        清理旧备份文件
        
        Args:
            keep_days: 保留天数，None时使用配置默认值
        
        Returns:
            int: 删除的文件数量
        """
        if keep_days is None:
            keep_days = self.config.keep_days
        
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            deleted_count = 0
            failed_files = []
            
            for backup_file in self.backup_dir.glob('database_backup_*.db*'):
                try:
                    # 从文件名提取时间戳
                    filename = backup_file.stem
                    if filename.endswith('.db'):
                        timestamp_str = filename.split('_')[-2] + '_' + filename.split('_')[-1]
                    else:
                        # 处理 .gz 文件
                        parts = filename.split('_')
                        timestamp_str = parts[-2] + '_' + parts[-1].replace('.db', '')
                    
                    file_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    
                    if file_date < cutoff_date:
                        backup_file.unlink()
                        deleted_count += 1
                        self.logger.info(f"删除旧备份: {backup_file}")
                        
                except (ValueError, IndexError, OSError) as e:
                    self.logger.warning(f"无法删除备份文件: {backup_file}, 错误: {e}")
                    failed_files.append(str(backup_file))
                    continue
            
            if failed_files:
                raise BackupCleanupException(str(self.backup_dir), failed_files)
            
            self.logger.info(f"清理完成，删除了 {deleted_count} 个旧备份文件")
            return deleted_count
            
        except BackupCleanupException:
            raise
        except Exception as e:
            raise BackupCleanupException(str(self.backup_dir), [], e)
    
    def list_backups(self) -> List[Dict]:
        """列出所有备份文件"""
        backups = []
        
        for backup_file in sorted(self.backup_dir.glob('database_backup_*.db*')):
            try:
                stat = backup_file.stat()
                backups.append({
                    'filename': backup_file.name,
                    'path': str(backup_file),
                    'size': stat.st_size,
                    'created_at': datetime.fromtimestamp(stat.st_mtime),
                    'is_compressed': backup_file.suffix == '.gz'
                })
            except Exception as e:
                self.logger.warning(f"获取备份文件信息失败: {backup_file}, 错误: {e}")
        
        return backups
    
    def restore_backup(self, backup_filename: str, target_path: Optional[str] = None) -> bool:
        """
        恢复备份
        
        Args:
            backup_filename: 备份文件名
            target_path: 目标路径，None时使用原数据库路径
        
        Returns:
            bool: 是否成功
        """
        with self._operation_lock:
            try:
                backup_path = self.backup_dir / backup_filename
                
                if not backup_path.exists():
                    raise BackupRestoreException(str(backup_path), None, 
                                                FileNotFoundError("备份文件不存在"))
                
                target_path = target_path or self.db_path
                
                # 创建当前数据库的备份
                if os.path.exists(target_path):
                    current_backup = f"{target_path}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(target_path, current_backup)
                    self.logger.info(f"当前数据库已备份到: {current_backup}")
                
                # 恢复备份
                if backup_filename.endswith('.gz'):
                    self._restore_compressed_backup(backup_path, target_path)
                else:
                    shutil.copy2(backup_path, target_path)
                
                # 验证恢复的文件
                self._verify_restored_database(target_path)
                
                self.logger.info(f"备份恢复成功: {backup_filename} -> {target_path}")
                return True
                
            except (BackupRestoreException, BackupVerificationException):
                raise
            except Exception as e:
                raise BackupRestoreException(backup_filename, target_path, e)
    
    def _restore_compressed_backup(self, backup_path: Path, target_path: str):
        """恢复压缩备份"""
        try:
            with gzip.open(backup_path, 'rb') as f_in:
                with open(target_path, 'wb') as f_out:
                    while True:
                        chunk = f_in.read(self.config.chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
        except (gzip.BadGzipFile, OSError, IOError) as e:
            raise BackupCompressionException(str(backup_path), "decompression", e)
    
    def _verify_restored_database(self, db_path: str):
        """验证恢复的数据库"""
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()
            
            if result != "ok":
                raise BackupVerificationException(db_path, f"完整性检查失败: {result}")
                
        except sqlite3.Error as e:
            raise BackupVerificationException(db_path, f"数据库验证异常: {e}", e)
    
    def verify_backup(self, backup_filename: str) -> Tuple[bool, str]:
        """
        验证备份文件完整性
        
        Args:
            backup_filename: 备份文件名
        
        Returns:
            tuple: (是否有效, 验证消息)
        """
        try:
            backup_path = self.backup_dir / backup_filename
            
            if not backup_path.exists():
                return False, "备份文件不存在"
            
            # 如果是压缩文件，先解压到临时位置验证
            if backup_filename.endswith('.gz'):
                with tempfile.NamedTemporaryFile(suffix='.db') as temp_file:
                    self._restore_compressed_backup(backup_path, temp_file.name)
                    return self._verify_db_file(temp_file.name)
            else:
                return self._verify_db_file(str(backup_path))
                
        except (BackupCompressionException, BackupVerificationException) as e:
            return False, str(e)
        except Exception as e:
            return False, f"验证失败: {e}"
    
    def _verify_db_file(self, db_path: str) -> Tuple[bool, str]:
        """验证数据库文件完整性"""
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            
            # 执行完整性检查
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            
            # 检查schema
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            conn.close()
            
            if result == "ok":
                return True, f"数据库完整性验证通过 (包含 {len(tables)} 个表)"
            else:
                return False, f"数据库完整性验证失败: {result}"
                
        except sqlite3.Error as e:
            return False, f"数据库验证异常: {e}"
    
    def get_backup_stats(self) -> Dict:
        """获取备份统计信息"""
        backups = self.list_backups()
        
        if not backups:
            return {
                'total_backups': 0,
                'total_size': 0,
                'oldest_backup': None,
                'newest_backup': None,
                'compressed_count': 0,
                'average_size': 0,
                'compression_savings': 0
            }
        
        total_size = sum(backup['size'] for backup in backups)
        compressed_backups = [b for b in backups if b['is_compressed']]
        
        # 计算压缩节省的空间
        compression_savings = 0
        if compressed_backups:
            # 估算：假设压缩备份节省了约60%的空间
            estimated_uncompressed = sum(b['size'] for b in compressed_backups) / 0.4
            compression_savings = estimated_uncompressed - sum(b['size'] for b in compressed_backups)
        
        oldest_backup = min(backups, key=lambda x: x['created_at'])
        newest_backup = max(backups, key=lambda x: x['created_at'])
        
        return {
            'total_backups': len(backups),
            'total_size': total_size,
            'oldest_backup': oldest_backup,
            'newest_backup': newest_backup,
            'compressed_count': len(compressed_backups),
            'average_size': total_size // len(backups) if backups else 0,
            'compression_savings': int(compression_savings)
        }
    
    def get_health_status(self) -> Dict:
        """获取系统健康状态"""
        return self.health_monitor.get_health_status()


def main():
    """主函数 - 可以作为命令行工具使用"""
    import argparse
    
    parser = argparse.ArgumentParser(description='数据库备份管理工具 v2.0')
    parser.add_argument('--create', action='store_true', help='创建备份')
    parser.add_argument('--cleanup', action='store_true', help='清理旧备份')
    parser.add_argument('--list', action='store_true', help='列出所有备份')
    parser.add_argument('--restore', type=str, help='恢复指定备份')
    parser.add_argument('--verify', type=str, help='验证指定备份')
    parser.add_argument('--stats', action='store_true', help='显示备份统计')
    parser.add_argument('--health', action='store_true', help='显示健康状态')
    parser.add_argument('--keep-days', type=int, help='保留备份的天数')
    parser.add_argument('--db-path', type=str, help='数据库文件路径')
    parser.add_argument('--backup-dir', type=str, help='备份目录')
    parser.add_argument('--no-compress', action='store_true', help='不压缩备份')
    
    args = parser.parse_args()
    
    try:
        # 创建备份管理器
        backup_manager = BackupManager(args.db_path, args.backup_dir)
        
        if args.create:
            backup_path, message = backup_manager.create_backup(compress=not args.no_compress)
            if backup_path:
                print(f"✓ {message}")
            else:
                print(f"✗ {message}")
                
        elif args.cleanup:
            deleted_count = backup_manager.cleanup_old_backups(args.keep_days)
            print(f"✓ 清理完成，删除了 {deleted_count} 个旧备份")
            
        elif args.list:
            backups = backup_manager.list_backups()
            if backups:
                print("备份文件列表:")
                for backup in backups:
                    size_mb = backup['size'] / 1024 / 1024
                    compressed = " (压缩)" if backup['is_compressed'] else ""
                    print(f"  {backup['filename']} - {size_mb:.2f}MB - {backup['created_at']}{compressed}")
            else:
                print("没有找到备份文件")
                
        elif args.restore:
            success = backup_manager.restore_backup(args.restore)
            if success:
                print(f"✓ 备份恢复成功: {args.restore}")
            else:
                print(f"✗ 备份恢复失败: {args.restore}")
                
        elif args.verify:
            is_valid, message = backup_manager.verify_backup(args.verify)
            status = "✓" if is_valid else "✗"
            print(f"{status} 验证结果: {message}")
            
        elif args.stats:
            stats = backup_manager.get_backup_stats()
            print("备份统计信息:")
            print(f"  总备份数: {stats['total_backups']}")
            print(f"  总大小: {stats['total_size'] / 1024 / 1024:.2f}MB")
            print(f"  压缩备份数: {stats['compressed_count']}")
            print(f"  平均大小: {stats['average_size'] / 1024 / 1024:.2f}MB")
            if stats['compression_savings'] > 0:
                print(f"  压缩节省: {stats['compression_savings'] / 1024 / 1024:.2f}MB")
            if stats['oldest_backup']:
                print(f"  最老备份: {stats['oldest_backup']['filename']} ({stats['oldest_backup']['created_at']})")
            if stats['newest_backup']:
                print(f"  最新备份: {stats['newest_backup']['filename']} ({stats['newest_backup']['created_at']})")
                
        elif args.health:
            health = backup_manager.get_health_status()
            print("系统健康状态:")
            print(f"  总体状态: {health['overall_status']}")
            
            for component, info in health.items():
                if component in ['overall_status', 'last_check']:
                    continue
                if isinstance(info, dict) and 'status' in info:
                    status_icon = {"healthy": "✓", "warning": "⚠", "error": "✗"}.get(info['status'], "?")
                    print(f"  {component}: {status_icon} {info['status']}")
                    if 'message' in info:
                        print(f"    {info['message']}")
        else:
            parser.print_help()
            
    except BackupException as e:
        print(f"✗ 备份操作失败: {e}")
        if e.error_code:
            print(f"   错误代码: {e.error_code}")
    except Exception as e:
        print(f"✗ 未知错误: {e}")


if __name__ == '__main__':
    main()