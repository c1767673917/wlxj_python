#!/usr/bin/env python3
"""
备份管理器单元测试
提供全面的测试覆盖，包括正常情况、异常情况和边界条件
"""

import unittest
import tempfile
import shutil
import sqlite3
import os
import json
import gzip
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 设置测试环境路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.backup.backup_manager_v2 import BackupManager, BackupHealthMonitor
from config.backup_config import BackupConfig


class TestBackupConfig(unittest.TestCase):
    """测试备份配置类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = BackupConfig()
        self.assertEqual(config.keep_days, 7)
        self.assertEqual(config.max_backup_files, 50)
        self.assertEqual(config.backup_dir, 'backup')
        self.assertTrue(config.compress_backups)
    
    def test_env_config_override(self):
        """测试环境变量覆盖配置"""
        with patch.dict(os.environ, {
            'BACKUP_KEEP_DAYS': '14',
            'BACKUP_COMPRESS': 'false'
        }):
            config = BackupConfig()
            self.assertEqual(config.keep_days, 14)
            self.assertFalse(config.compress_backups)
    
    def test_config_validation(self):
        """测试配置验证"""
        config = BackupConfig()
        
        # 测试无效的keep_days
        config.keep_days = 0
        with self.assertRaises(Exception):
            config._validate_config()
        
        # 测试无效的日志级别
        config.keep_days = 7
        config.log_level = 'INVALID'
        with self.assertRaises(Exception):
            config._validate_config()


class TestBackupManager(unittest.TestCase):
    """测试备份管理器主要功能"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, 'test.db')
        self.backup_dir = os.path.join(self.temp_dir, 'backup')
        
        # 创建测试数据库
        self._create_test_database()
        
        # 创建测试配置
        self.config = BackupConfig()
        self.config.backup_dir = self.backup_dir
        self.config.keep_days = 1  # 较短的保留期用于测试
        self.config.max_backup_files = 5
        
        # 创建备份管理器
        self.backup_manager = BackupManager(
            db_path=self.test_db_path,
            backup_dir=self.backup_dir,
            config=self.config
        )
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_database(self):
        """创建测试数据库"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # 创建测试表
        cursor.execute('''
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                value INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 插入测试数据
        test_data = [
            ('Test Item 1', 100),
            ('Test Item 2', 200),
            ('Test Item 3', 300),
        ]
        
        cursor.executemany(
            'INSERT INTO test_table (name, value) VALUES (?, ?)',
            test_data
        )
        
        conn.commit()
        conn.close()
    
    def test_backup_creation_success(self):
        """测试成功创建备份"""
        backup_path, message = self.backup_manager.create_backup(compress=False)
        
        self.assertIsInstance(backup_path, Path)
        self.assertTrue(backup_path.exists())
        self.assertGreater(backup_path.stat().st_size, 0)
        self.assertIn('成功', message)
    
    def test_backup_creation_with_compression(self):
        """测试创建压缩备份"""
        backup_path, message = self.backup_manager.create_backup(compress=True)
        
        self.assertIsInstance(backup_path, Path)
        self.assertTrue(backup_path.exists())
        self.assertTrue(backup_path.name.endswith('.gz'))
        self.assertGreater(backup_path.stat().st_size, 0)
        self.assertIn('成功', message)
    
    def test_backup_creation_nonexistent_db(self):
        """测试备份不存在的数据库"""
        # 创建指向不存在文件的备份管理器
        invalid_manager = BackupManager(
            db_path='/nonexistent/database.db',
            backup_dir=self.backup_dir,
            config=self.config
        )
        
        result, message = invalid_manager.create_backup()
        
        self.assertFalse(result)
        self.assertIn('不存在', message)
    
    def test_backup_creation_empty_db(self):
        """测试备份空数据库文件"""
        # 创建空文件
        empty_db_path = os.path.join(self.temp_dir, 'empty.db')
        Path(empty_db_path).touch()
        
        empty_manager = BackupManager(
            db_path=empty_db_path,
            backup_dir=self.backup_dir,
            config=self.config
        )
        
        result, message = empty_manager.create_backup()
        
        self.assertFalse(result)
        self.assertIn('为空', message)
    
    def test_backup_creation_permission_denied(self):
        """测试备份目录权限不足"""
        # 创建只读备份目录
        readonly_backup_dir = os.path.join(self.temp_dir, 'readonly_backup')
        os.makedirs(readonly_backup_dir)
        os.chmod(readonly_backup_dir, 0o444)  # 只读权限
        
        try:
            readonly_manager = BackupManager(
                db_path=self.test_db_path,
                backup_dir=readonly_backup_dir,
                config=self.config
            )
            self.fail("应该抛出权限异常")
        except Exception as e:
            self.assertIn('权限', str(e).lower() + str(type(e).__name__).lower())
        finally:
            # 恢复权限用于清理
            os.chmod(readonly_backup_dir, 0o755)
    
    def test_backup_timeout(self):
        """测试备份超时"""
        with patch('time.time') as mock_time:
            # 模拟超时
            mock_time.side_effect = [0, 0, 0, 400]  # 第4次调用返回超时时间
            
            result, message = self.backup_manager.create_backup(timeout=300)
            
            self.assertFalse(result)
            self.assertIn('超时', message)
    
    def test_list_backups(self):
        """测试列出备份文件"""
        # 创建几个备份
        self.backup_manager.create_backup(compress=False)
        time.sleep(0.1)  # 确保文件名不同
        self.backup_manager.create_backup(compress=True)
        
        backups = self.backup_manager.list_backups()
        
        self.assertEqual(len(backups), 2)
        self.assertFalse(backups[0]['is_compressed'])
        self.assertTrue(backups[1]['is_compressed'])
        
        for backup in backups:
            self.assertIn('filename', backup)
            self.assertIn('size', backup)
            self.assertIn('created_at', backup)
    
    def test_cleanup_old_backups(self):
        """测试清理旧备份"""
        # 创建一些备份
        backup1, _ = self.backup_manager.create_backup()
        time.sleep(0.1)
        backup2, _ = self.backup_manager.create_backup()
        
        # 模拟旧文件（修改文件时间）
        old_time = time.time() - (2 * 24 * 3600)  # 2天前
        os.utime(backup1, (old_time, old_time))
        
        # 清理1天前的备份
        deleted_count = self.backup_manager.cleanup_old_backups(keep_days=1)
        
        self.assertEqual(deleted_count, 1)
        self.assertFalse(backup1.exists())
        self.assertTrue(backup2.exists())
    
    def test_verify_backup_valid(self):
        """测试验证有效备份"""
        backup_path, _ = self.backup_manager.create_backup(compress=False)
        
        is_valid, message = self.backup_manager.verify_backup(backup_path.name)
        
        self.assertTrue(is_valid)
        self.assertIn('通过', message)
    
    def test_verify_backup_compressed(self):
        """测试验证压缩备份"""
        backup_path, _ = self.backup_manager.create_backup(compress=True)
        
        is_valid, message = self.backup_manager.verify_backup(backup_path.name)
        
        self.assertTrue(is_valid)
        self.assertIn('通过', message)
    
    def test_verify_backup_nonexistent(self):
        """测试验证不存在的备份"""
        is_valid, message = self.backup_manager.verify_backup('nonexistent.db')
        
        self.assertFalse(is_valid)
        self.assertIn('不存在', message)
    
    def test_verify_backup_corrupted(self):
        """测试验证损坏的备份"""
        # 创建一个损坏的备份文件
        corrupted_backup = self.backup_manager.backup_dir / 'corrupted_backup.db'
        with open(corrupted_backup, 'w') as f:
            f.write("This is not a valid SQLite database")
        
        is_valid, message = self.backup_manager.verify_backup('corrupted_backup.db')
        
        self.assertFalse(is_valid)
        self.assertIn('异常', message)
    
    def test_restore_backup_success(self):
        """测试成功恢复备份"""
        # 创建备份
        backup_path, _ = self.backup_manager.create_backup(compress=False)
        
        # 修改原数据库
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO test_table (name, value) VALUES ('Modified', 999)")
        conn.commit()
        conn.close()
        
        # 恢复备份
        success = self.backup_manager.restore_backup(backup_path.name)
        
        self.assertTrue(success)
        
        # 验证恢复结果
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM test_table")
        count = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(count, 3)  # 原始的3条记录
    
    def test_restore_backup_compressed(self):
        """测试恢复压缩备份"""
        # 创建压缩备份
        backup_path, _ = self.backup_manager.create_backup(compress=True)
        
        # 删除原数据库
        os.remove(self.test_db_path)
        
        # 恢复备份
        success = self.backup_manager.restore_backup(backup_path.name)
        
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.test_db_path))
        
        # 验证恢复的数据库
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM test_table")
        count = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(count, 3)
    
    def test_restore_backup_nonexistent(self):
        """测试恢复不存在的备份"""
        with self.assertRaises(Exception):
            self.backup_manager.restore_backup('nonexistent.db')
    
    def test_get_backup_stats(self):
        """测试获取备份统计信息"""
        # 创建一些备份
        self.backup_manager.create_backup(compress=False)
        time.sleep(0.1)
        self.backup_manager.create_backup(compress=True)
        
        stats = self.backup_manager.get_backup_stats()
        
        self.assertEqual(stats['total_backups'], 2)
        self.assertEqual(stats['compressed_count'], 1)
        self.assertGreater(stats['total_size'], 0)
        self.assertIsNotNone(stats['oldest_backup'])
        self.assertIsNotNone(stats['newest_backup'])
    
    def test_get_backup_stats_empty(self):
        """测试空备份目录的统计信息"""
        stats = self.backup_manager.get_backup_stats()
        
        self.assertEqual(stats['total_backups'], 0)
        self.assertEqual(stats['total_size'], 0)
        self.assertIsNone(stats['oldest_backup'])
        self.assertIsNone(stats['newest_backup'])
    
    def test_concurrent_operations(self):
        """测试并发操作的线程安全性"""
        import threading
        
        results = []
        
        def create_backup():
            result = self.backup_manager.create_backup()
            results.append(result)
        
        # 创建多个线程同时执行备份
        threads = []
        for i in range(3):
            thread = threading.Thread(target=create_backup)
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证结果
        self.assertEqual(len(results), 3)
        successful_backups = sum(1 for result, _ in results if result)
        self.assertGreater(successful_backups, 0)  # 至少有一个成功
    
    def test_log_backup_info(self):
        """测试备份信息记录"""
        backup_path, _ = self.backup_manager.create_backup()
        
        info_file = self.backup_manager.backup_dir / 'backup_info.json'
        self.assertTrue(info_file.exists())
        
        with open(info_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertIn('backups', data)
        self.assertEqual(len(data['backups']), 1)
        
        backup_info = data['backups'][0]
        self.assertIn('filename', backup_info)
        self.assertIn('size', backup_info)
        self.assertIn('created_at', backup_info)
    
    def test_max_backup_files_limit(self):
        """测试最大备份文件数限制"""
        # 设置较小的限制用于测试
        self.config.max_backup_files = 3
        
        # 创建超过限制的备份
        for i in range(5):
            self.backup_manager.create_backup()
            time.sleep(0.1)
        
        # 检查信息文件中的记录数
        info_file = self.backup_manager.backup_dir / 'backup_info.json'
        with open(info_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 应该只保留最近的3个记录
        self.assertLessEqual(len(data['backups']), 3)


class TestBackupHealthMonitor(unittest.TestCase):
    """测试备份健康监控器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, 'test.db')
        self.backup_dir = os.path.join(self.temp_dir, 'backup')
        
        # 创建测试数据库
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)')
        cursor.execute("INSERT INTO test (data) VALUES ('test data')")
        conn.commit()
        conn.close()
        
        # 创建备份管理器
        self.backup_manager = BackupManager(
            db_path=self.test_db_path,
            backup_dir=self.backup_dir
        )
        
        self.health_monitor = BackupHealthMonitor(self.backup_manager)
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_database_health_check(self):
        """测试数据库健康检查"""
        self.health_monitor._check_database_health()
        
        status = self.health_monitor._health_status.get('database')
        self.assertIsNotNone(status)
        self.assertEqual(status['status'], 'healthy')
        self.assertTrue(status['accessible'])
    
    def test_database_health_check_missing_file(self):
        """测试缺失数据库文件的健康检查"""
        # 删除数据库文件
        os.remove(self.test_db_path)
        
        self.health_monitor._check_database_health()
        
        status = self.health_monitor._health_status.get('database')
        self.assertEqual(status['status'], 'error')
        self.assertIn('不存在', status['message'])
    
    def test_backup_directory_health_check(self):
        """测试备份目录健康检查"""
        self.health_monitor._check_backup_directory_health()
        
        status = self.health_monitor._health_status.get('backup_directory')
        self.assertIsNotNone(status)
        self.assertEqual(status['status'], 'healthy')
        self.assertTrue(status['writable'])
    
    def test_recent_backups_check_no_backups(self):
        """测试无备份的检查"""
        self.health_monitor._check_recent_backups()
        
        status = self.health_monitor._health_status.get('recent_backups')
        self.assertEqual(status['status'], 'warning')
        self.assertIn('没有找到', status['message'])
    
    def test_recent_backups_check_with_backups(self):
        """测试有备份的检查"""
        # 创建一个备份
        self.backup_manager.create_backup()
        
        self.health_monitor._check_recent_backups()
        
        status = self.health_monitor._health_status.get('recent_backups')
        self.assertEqual(status['status'], 'healthy')
        self.assertIn('latest_backup', status)
    
    def test_disk_space_check(self):
        """测试磁盘空间检查"""
        self.health_monitor._check_disk_space()
        
        status = self.health_monitor._health_status.get('disk_space')
        self.assertIsNotNone(status)
        self.assertIn('available_bytes', status)
        self.assertIn('usage_percent', status)
    
    def test_get_health_status(self):
        """测试获取完整健康状态"""
        health_status = self.health_monitor.get_health_status()
        
        self.assertIn('overall_status', health_status)
        self.assertIn('last_check', health_status)
        self.assertIn('database', health_status)
        self.assertIn('backup_directory', health_status)
        self.assertIn('recent_backups', health_status)
        self.assertIn('disk_space', health_status)
    
    def test_overall_status_calculation(self):
        """测试总体状态计算"""
        # 设置不同的组件状态
        self.health_monitor._health_status = {
            'component1': {'status': 'healthy'},
            'component2': {'status': 'healthy'},
            'component3': {'status': 'warning'}
        }
        
        overall = self.health_monitor._calculate_overall_status()
        self.assertEqual(overall, 'warning')
        
        # 测试错误状态优先级
        self.health_monitor._health_status['component4'] = {'status': 'error'}
        overall = self.health_monitor._calculate_overall_status()
        self.assertEqual(overall, 'error')


class TestBackupExceptionHandling(unittest.TestCase):
    """测试异常处理"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, 'test.db')
        self.backup_dir = os.path.join(self.temp_dir, 'backup')
        
        # 创建测试数据库
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE test (id INTEGER PRIMARY KEY)')
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_database_not_found_exception(self):
        """测试数据库文件不存在异常"""
        backup_manager = BackupManager(
            db_path='/nonexistent/path/database.db',
            backup_dir=self.backup_dir
        )
        
        result, message = backup_manager.create_backup()
        self.assertFalse(result)
        self.assertIn('不存在', message)
    
    def test_backup_directory_permission_exception(self):
        """测试备份目录权限异常"""
        # 创建只读目录
        readonly_dir = os.path.join(self.temp_dir, 'readonly')
        os.makedirs(readonly_dir)
        os.chmod(readonly_dir, 0o444)
        
        try:
            with self.assertRaises(Exception):
                BackupManager(
                    db_path=self.test_db_path,
                    backup_dir=readonly_dir
                )
        finally:
            # 恢复权限
            os.chmod(readonly_dir, 0o755)
    
    def test_corrupted_backup_verification(self):
        """测试损坏备份文件的验证"""
        backup_manager = BackupManager(
            db_path=self.test_db_path,
            backup_dir=self.backup_dir
        )
        
        # 创建一个损坏的备份文件
        corrupted_file = os.path.join(self.backup_dir, 'corrupted.db')
        with open(corrupted_file, 'w') as f:
            f.write("invalid sqlite data")
        
        is_valid, message = backup_manager.verify_backup('corrupted.db')
        self.assertFalse(is_valid)


class TestEdgeCases(unittest.TestCase):
    """测试边界条件和特殊情况"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_very_large_database(self):
        """测试大数据库文件的处理"""
        # 创建一个相对较大的测试数据库
        large_db_path = os.path.join(self.temp_dir, 'large.db')
        conn = sqlite3.connect(large_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE large_table (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
        ''')
        
        # 插入大量数据
        large_data = 'x' * 1000  # 1KB per row
        for i in range(1000):  # 约1MB数据
            cursor.execute('INSERT INTO large_table (data) VALUES (?)', (large_data,))
        
        conn.commit()
        conn.close()
        
        backup_dir = os.path.join(self.temp_dir, 'backup')
        backup_manager = BackupManager(
            db_path=large_db_path,
            backup_dir=backup_dir
        )
        
        # 测试创建备份
        backup_path, message = backup_manager.create_backup(compress=True)
        self.assertIsInstance(backup_path, Path)
        self.assertTrue(backup_path.exists())
        
        # 测试验证大文件备份
        is_valid, verify_message = backup_manager.verify_backup(backup_path.name)
        self.assertTrue(is_valid)
    
    def test_database_with_special_characters(self):
        """测试包含特殊字符的数据库"""
        db_path = os.path.join(self.temp_dir, 'special_数据库.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE test_特殊字符 (
                id INTEGER PRIMARY KEY,
                name TEXT,
                描述 TEXT
            )
        ''')
        
        cursor.execute(
            'INSERT INTO test_特殊字符 (name, 描述) VALUES (?, ?)',
            ('测试名称', '包含中文的描述信息')
        )
        
        conn.commit()
        conn.close()
        
        backup_dir = os.path.join(self.temp_dir, 'backup')
        backup_manager = BackupManager(
            db_path=db_path,
            backup_dir=backup_dir
        )
        
        backup_path, message = backup_manager.create_backup()
        self.assertIsInstance(backup_path, Path)
        
        # 验证恢复
        success = backup_manager.restore_backup(backup_path.name)
        self.assertTrue(success)
    
    def test_backup_filename_collision(self):
        """测试备份文件名冲突处理"""
        db_path = os.path.join(self.temp_dir, 'test.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE test (id INTEGER PRIMARY KEY)')
        conn.commit()
        conn.close()
        
        backup_dir = os.path.join(self.temp_dir, 'backup')
        backup_manager = BackupManager(
            db_path=db_path,
            backup_dir=backup_dir
        )
        
        # 在同一秒内创建多个备份
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.strftime = datetime.strftime
            
            backup1, _ = backup_manager.create_backup()
            backup2, _ = backup_manager.create_backup()
            
            # 两个备份应该都成功创建（通过微秒区分）
            self.assertIsInstance(backup1, Path)
            self.assertIsInstance(backup2, Path)
            self.assertNotEqual(backup1, backup2)
    
    def test_cleanup_with_invalid_filenames(self):
        """测试清理包含无效文件名的备份目录"""
        backup_dir = os.path.join(self.temp_dir, 'backup')
        os.makedirs(backup_dir)
        
        # 创建一些有效和无效的文件名
        valid_name = 'database_backup_20230101_120000.db'
        invalid_name1 = 'database_backup_invalid.db'
        invalid_name2 = 'not_a_backup_file.txt'
        
        for filename in [valid_name, invalid_name1, invalid_name2]:
            filepath = os.path.join(backup_dir, filename)
            Path(filepath).touch()
        
        backup_manager = BackupManager(
            db_path=os.path.join(self.temp_dir, 'dummy.db'),
            backup_dir=backup_dir
        )
        
        # 清理应该不会崩溃，只处理有效的备份文件
        deleted_count = backup_manager.cleanup_old_backups(keep_days=0)
        
        # 应该只删除有效的备份文件
        self.assertEqual(deleted_count, 1)
        self.assertFalse(os.path.exists(os.path.join(backup_dir, valid_name)))
        self.assertTrue(os.path.exists(os.path.join(backup_dir, invalid_name1)))
        self.assertTrue(os.path.exists(os.path.join(backup_dir, invalid_name2)))


if __name__ == '__main__':
    # 设置测试运行器
    unittest.main(verbosity=2, buffer=True)