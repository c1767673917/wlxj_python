#!/usr/bin/env python3
"""
定时备份脚本
可以通过cron定时执行，实现自动备份
"""

import sys
import os
from datetime import datetime
from backup_manager import BackupManager

def scheduled_backup():
    """执行定时备份任务"""
    print(f"开始执行定时备份任务 - {datetime.now()}")
    
    try:
        # 创建备份管理器
        backup_manager = BackupManager()
        
        # 创建压缩备份
        backup_path = backup_manager.create_backup(compress=True)
        
        if backup_path:
            print(f"✅ 备份创建成功: {backup_path}")
            
            # 清理旧备份（保留7天）
            deleted_count = backup_manager.cleanup_old_backups(keep_days=7)
            print(f"✅ 清理旧备份完成，删除了 {deleted_count} 个文件")
            
            # 显示备份统计
            stats = backup_manager.get_backup_stats()
            print(f"📊 当前备份统计: {stats['total_backups']} 个备份文件，总大小 {stats['total_size'] / 1024 / 1024:.2f}MB")
            
            return True
        else:
            print("❌ 备份创建失败")
            return False
            
    except Exception as e:
        print(f"❌ 定时备份任务执行失败: {str(e)}")
        return False

if __name__ == '__main__':
    success = scheduled_backup()
    sys.exit(0 if success else 1)