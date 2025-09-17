#!/usr/bin/env python3
"""
备份管理器自定义异常类
定义所有备份相关的具体异常类型
"""


class BackupException(Exception):
    """备份操作基础异常类"""
    
    def __init__(self, message, error_code=None, original_exception=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.original_exception = original_exception
    
    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class DatabaseNotFoundException(BackupException):
    """数据库文件未找到异常"""
    
    def __init__(self, db_path, original_exception=None):
        message = f"数据库文件未找到: {db_path}"
        super().__init__(message, "DB_NOT_FOUND", original_exception)
        self.db_path = db_path


class DatabaseAccessException(BackupException):
    """数据库访问权限异常"""
    
    def __init__(self, db_path, access_type="read", original_exception=None):
        message = f"数据库文件无法{access_type}: {db_path}"
        super().__init__(message, "DB_ACCESS_DENIED", original_exception)
        self.db_path = db_path
        self.access_type = access_type


class DatabaseCorruptedException(BackupException):
    """数据库文件损坏异常"""
    
    def __init__(self, db_path, corruption_details=None, original_exception=None):
        message = f"数据库文件损坏: {db_path}"
        if corruption_details:
            message += f" - {corruption_details}"
        super().__init__(message, "DB_CORRUPTED", original_exception)
        self.db_path = db_path
        self.corruption_details = corruption_details


class BackupDirectoryException(BackupException):
    """备份目录相关异常"""
    
    def __init__(self, backup_dir, operation="access", original_exception=None):
        message = f"备份目录{operation}失败: {backup_dir}"
        super().__init__(message, "BACKUP_DIR_ERROR", original_exception)
        self.backup_dir = backup_dir
        self.operation = operation


class BackupCreationException(BackupException):
    """备份创建异常"""
    
    def __init__(self, backup_path, reason=None, original_exception=None):
        message = f"备份创建失败: {backup_path}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, "BACKUP_CREATE_FAILED", original_exception)
        self.backup_path = backup_path
        self.reason = reason


class BackupVerificationException(BackupException):
    """备份验证异常"""
    
    def __init__(self, backup_path, verification_error=None, original_exception=None):
        message = f"备份验证失败: {backup_path}"
        if verification_error:
            message += f" - {verification_error}"
        super().__init__(message, "BACKUP_VERIFY_FAILED", original_exception)
        self.backup_path = backup_path
        self.verification_error = verification_error


class BackupRestoreException(BackupException):
    """备份恢复异常"""
    
    def __init__(self, backup_path, target_path=None, original_exception=None):
        message = f"备份恢复失败: {backup_path}"
        if target_path:
            message += f" -> {target_path}"
        super().__init__(message, "BACKUP_RESTORE_FAILED", original_exception)
        self.backup_path = backup_path
        self.target_path = target_path


class BackupCompressionException(BackupException):
    """备份压缩/解压异常"""
    
    def __init__(self, file_path, operation="compression", original_exception=None):
        message = f"备份{operation}失败: {file_path}"
        super().__init__(message, "BACKUP_COMPRESSION_FAILED", original_exception)
        self.file_path = file_path
        self.operation = operation


class BackupCleanupException(BackupException):
    """备份清理异常"""
    
    def __init__(self, backup_dir, failed_files=None, original_exception=None):
        message = f"备份清理失败: {backup_dir}"
        if failed_files:
            message += f" - 失败文件: {failed_files}"
        super().__init__(message, "BACKUP_CLEANUP_FAILED", original_exception)
        self.backup_dir = backup_dir
        self.failed_files = failed_files or []


class BackupSizeException(BackupException):
    """备份文件大小异常"""
    
    def __init__(self, file_path, size, max_size=None, original_exception=None):
        if max_size:
            message = f"备份文件过大: {file_path} ({size} bytes > {max_size} bytes)"
        else:
            message = f"备份文件大小异常: {file_path} ({size} bytes)"
        super().__init__(message, "BACKUP_SIZE_ERROR", original_exception)
        self.file_path = file_path
        self.size = size
        self.max_size = max_size


class BackupConfigurationException(BackupException):
    """备份配置异常"""
    
    def __init__(self, config_item, config_value=None, original_exception=None):
        message = f"备份配置错误: {config_item}"
        if config_value is not None:
            message += f" = {config_value}"
        super().__init__(message, "BACKUP_CONFIG_ERROR", original_exception)
        self.config_item = config_item
        self.config_value = config_value


class BackupTimeoutException(BackupException):
    """备份操作超时异常"""
    
    def __init__(self, operation, timeout_seconds, original_exception=None):
        message = f"备份操作超时: {operation} (超时时间: {timeout_seconds}秒)"
        super().__init__(message, "BACKUP_TIMEOUT", original_exception)
        self.operation = operation
        self.timeout_seconds = timeout_seconds


# 异常映射表，用于从通用异常转换为具体异常
def get_exception_mapping():
    """获取异常映射表（延迟导入sqlite3）"""
    import sqlite3
    return {
        FileNotFoundError: DatabaseNotFoundException,
        PermissionError: DatabaseAccessException,
        OSError: BackupDirectoryException,
        IOError: BackupCreationException,
        sqlite3.DatabaseError: DatabaseCorruptedException,
    }


def wrap_exception(original_exception, context=None):
    """
    将通用异常包装为具体的备份异常
    
    Args:
        original_exception: 原始异常
        context: 上下文信息字典
    
    Returns:
        BackupException: 包装后的具体异常
    """
    import sqlite3
    
    exception_type = type(original_exception)
    context = context or {}
    
    exception_mapping = get_exception_mapping()
    
    if exception_type in exception_mapping:
        specific_exception_class = exception_mapping[exception_type]
        
        # 根据异常类型和上下文创建具体异常
        if specific_exception_class == DatabaseNotFoundException:
            return specific_exception_class(
                context.get('db_path', 'unknown'),
                original_exception
            )
        elif specific_exception_class == DatabaseAccessException:
            return specific_exception_class(
                context.get('db_path', 'unknown'),
                context.get('access_type', 'read'),
                original_exception
            )
        elif specific_exception_class == BackupDirectoryException:
            return specific_exception_class(
                context.get('backup_dir', 'unknown'),
                context.get('operation', 'access'),
                original_exception
            )
        elif specific_exception_class == BackupCreationException:
            return specific_exception_class(
                context.get('backup_path', 'unknown'),
                str(original_exception),
                original_exception
            )
        elif specific_exception_class == DatabaseCorruptedException:
            return specific_exception_class(
                context.get('db_path', 'unknown'),
                str(original_exception),
                original_exception
            )
    
    # 如果没有找到特定映射，返回通用BackupException
    return BackupException(
        str(original_exception),
        "UNKNOWN_ERROR",
        original_exception
    )