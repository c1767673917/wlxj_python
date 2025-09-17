#!/usr/bin/env python3
"""
数据备份管理器
用于自动备份SQLite数据库
重构版本 - 使用改进的v2实现
"""

# 导入改进版本的所有功能
try:
    from .backup_manager_v2 import (
        BackupManager,
        BackupHealthMonitor,
        setup_backup_logger,
        get_logger,
        main
    )
except ImportError:
    # 如果相对导入失败，尝试直接导入
    from backup_manager_v2 import (
        BackupManager,
        BackupHealthMonitor,
        setup_backup_logger,
        get_logger,
        main
    )

# 为了向后兼容，导出所有主要功能
__all__ = [
    'BackupManager',
    'BackupHealthMonitor', 
    'setup_backup_logger',
    'get_logger',
    'main'
]

# 保持向后兼容的logger接口
logger = get_logger()

if __name__ == '__main__':
    main()