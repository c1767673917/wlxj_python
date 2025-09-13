#!/usr/bin/env python3
"""
数据备份管理器
用于自动备份SQLite数据库
"""

import os
import shutil
import sqlite3
import json
import gzip
from datetime import datetime, timedelta
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/backup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self, db_path='database.db', backup_dir='backup'):
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
    def create_backup(self, compress=True):
        """创建数据库备份"""
        try:
            if not os.path.exists(self.db_path):
                logger.error(f"数据库文件不存在: {self.db_path}")
                return False
            
            # 生成备份文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'database_backup_{timestamp}.db'
            
            if compress:
                backup_filename += '.gz'
            
            backup_path = self.backup_dir / backup_filename
            
            # 执行备份
            if compress:
                self._create_compressed_backup(backup_path)
            else:
                self._create_simple_backup(backup_path)
            
            # 记录备份信息
            self._log_backup_info(backup_path, timestamp)
            
            logger.info(f"备份创建成功: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"备份创建失败: {str(e)}")
            return False
    
    def _create_simple_backup(self, backup_path):
        """创建简单备份（直接复制文件）"""
        shutil.copy2(self.db_path, backup_path)
    
    def _create_compressed_backup(self, backup_path):
        """创建压缩备份"""
        with open(self.db_path, 'rb') as f_in:
            with gzip.open(backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    def _log_backup_info(self, backup_path, timestamp):
        """记录备份信息到JSON文件"""
        info_file = self.backup_dir / 'backup_info.json'
        
        backup_info = {
            'timestamp': timestamp,
            'filename': backup_path.name,
            'size': backup_path.stat().st_size,
            'original_size': Path(self.db_path).stat().st_size,
            'created_at': datetime.now().isoformat()
        }
        
        # 读取现有信息
        if info_file.exists():
            with open(info_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {'backups': []}
        
        # 添加新备份信息
        data['backups'].append(backup_info)
        
        # 保持最近50个备份的记录
        data['backups'] = data['backups'][-50:]
        
        # 写入文件
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def cleanup_old_backups(self, keep_days=7):
        """清理旧备份文件"""
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            deleted_count = 0
            
            for backup_file in self.backup_dir.glob('database_backup_*.db*'):
                # 从文件名提取时间戳
                try:
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
                        logger.info(f"删除旧备份: {backup_file}")
                        
                except (ValueError, IndexError) as e:
                    logger.warning(f"无法解析备份文件时间戳: {backup_file}, 错误: {e}")
                    continue
            
            logger.info(f"清理完成，删除了 {deleted_count} 个旧备份文件")
            return deleted_count
            
        except Exception as e:
            logger.error(f"清理旧备份失败: {str(e)}")
            return 0
    
    def list_backups(self):
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
                logger.warning(f"获取备份文件信息失败: {backup_file}, 错误: {e}")
        
        return backups
    
    def restore_backup(self, backup_filename, target_path=None):
        """恢复备份"""
        try:
            backup_path = self.backup_dir / backup_filename
            
            if not backup_path.exists():
                logger.error(f"备份文件不存在: {backup_path}")
                return False
            
            target_path = target_path or self.db_path
            
            # 创建当前数据库的备份
            if os.path.exists(target_path):
                current_backup = f"{target_path}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(target_path, current_backup)
                logger.info(f"当前数据库已备份到: {current_backup}")
            
            # 恢复备份
            if backup_filename.endswith('.gz'):
                self._restore_compressed_backup(backup_path, target_path)
            else:
                shutil.copy2(backup_path, target_path)
            
            logger.info(f"备份恢复成功: {backup_filename} -> {target_path}")
            return True
            
        except Exception as e:
            logger.error(f"备份恢复失败: {str(e)}")
            return False
    
    def _restore_compressed_backup(self, backup_path, target_path):
        """恢复压缩备份"""
        with gzip.open(backup_path, 'rb') as f_in:
            with open(target_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    def verify_backup(self, backup_filename):
        """验证备份文件完整性"""
        try:
            backup_path = self.backup_dir / backup_filename
            
            if not backup_path.exists():
                return False, "备份文件不存在"
            
            # 如果是压缩文件，先解压到临时位置验证
            if backup_filename.endswith('.gz'):
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.db') as temp_file:
                    self._restore_compressed_backup(backup_path, temp_file.name)
                    return self._verify_db_file(temp_file.name)
            else:
                return self._verify_db_file(backup_path)
                
        except Exception as e:
            return False, f"验证失败: {str(e)}"
    
    def _verify_db_file(self, db_path):
        """验证数据库文件完整性"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 执行完整性检查
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            
            conn.close()
            
            if result == "ok":
                return True, "数据库完整性验证通过"
            else:
                return False, f"数据库完整性验证失败: {result}"
                
        except Exception as e:
            return False, f"数据库验证异常: {str(e)}"
    
    def get_backup_stats(self):
        """获取备份统计信息"""
        backups = self.list_backups()
        
        if not backups:
            return {
                'total_backups': 0,
                'total_size': 0,
                'oldest_backup': None,
                'newest_backup': None
            }
        
        total_size = sum(backup['size'] for backup in backups)
        oldest_backup = min(backups, key=lambda x: x['created_at'])
        newest_backup = max(backups, key=lambda x: x['created_at'])
        
        return {
            'total_backups': len(backups),
            'total_size': total_size,
            'oldest_backup': oldest_backup,
            'newest_backup': newest_backup,
            'compressed_count': sum(1 for b in backups if b['is_compressed'])
        }

def main():
    """主函数 - 可以作为命令行工具使用"""
    import argparse
    
    parser = argparse.ArgumentParser(description='数据库备份管理工具')
    parser.add_argument('--create', action='store_true', help='创建备份')
    parser.add_argument('--cleanup', action='store_true', help='清理旧备份')
    parser.add_argument('--list', action='store_true', help='列出所有备份')
    parser.add_argument('--restore', type=str, help='恢复指定备份')
    parser.add_argument('--verify', type=str, help='验证指定备份')
    parser.add_argument('--stats', action='store_true', help='显示备份统计')
    parser.add_argument('--keep-days', type=int, default=7, help='保留备份的天数')
    parser.add_argument('--db-path', type=str, default='database.db', help='数据库文件路径')
    parser.add_argument('--backup-dir', type=str, default='backup', help='备份目录')
    
    args = parser.parse_args()
    
    # 创建备份管理器
    backup_manager = BackupManager(args.db_path, args.backup_dir)
    
    if args.create:
        backup_path = backup_manager.create_backup()
        if backup_path:
            print(f"备份创建成功: {backup_path}")
        else:
            print("备份创建失败")
            
    elif args.cleanup:
        deleted_count = backup_manager.cleanup_old_backups(args.keep_days)
        print(f"清理完成，删除了 {deleted_count} 个旧备份")
        
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
            print(f"备份恢复成功: {args.restore}")
        else:
            print(f"备份恢复失败: {args.restore}")
            
    elif args.verify:
        is_valid, message = backup_manager.verify_backup(args.verify)
        print(f"验证结果: {message}")
        
    elif args.stats:
        stats = backup_manager.get_backup_stats()
        print("备份统计信息:")
        print(f"  总备份数: {stats['total_backups']}")
        print(f"  总大小: {stats['total_size'] / 1024 / 1024:.2f}MB")
        print(f"  压缩备份数: {stats['compressed_count']}")
        if stats['oldest_backup']:
            print(f"  最老备份: {stats['oldest_backup']['filename']} ({stats['oldest_backup']['created_at']})")
        if stats['newest_backup']:
            print(f"  最新备份: {stats['newest_backup']['filename']} ({stats['newest_backup']['created_at']})")
    else:
        parser.print_help()

if __name__ == '__main__':
    main()