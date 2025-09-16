#!/usr/bin/env python3
"""
系统优化功能综合测试套件
针对数据库索引优化、文件安全、错误码系统、环境验证等功能进行全面验证
"""

import pytest
import os
import sqlite3
import tempfile
import shutil
import logging
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock
from io import BytesIO

# 设置测试环境
os.environ['FLASK_ENV'] = 'testing'

# 导入应用模块
from app import app, db
from models import Order, Quote, Supplier, User
from utils.file_security import FileSecurity, validate_upload_file, file_security_check
from utils.error_codes import ErrorHandler, ErrorCode, ErrorResponseHelper, CommonErrors
from utils.env_validator import EnvironmentValidator, validate_startup_environment
from migrations.add_performance_indexes import add_performance_indexes, validate_index_performance


class TestDatabaseIndexOptimization:
    """数据库索引优化测试"""
    
    @pytest.fixture
    def setup_test_database(self):
        """设置测试数据库"""
        with app.app_context():
            # 创建临时数据库
            self.test_db_path = 'test_database.db'
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
            
            # 创建数据库表
            db.create_all()
            
            # 创建测试数据
            self._create_test_data()
            
            yield
            
            # 清理
            db.session.remove()
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
    
    def _create_test_data(self):
        """创建测试数据"""
        # 创建测试用户
        user1 = User(username='test_user1', password_hash='test', business_type='oil', access_code='test123')
        user2 = User(username='test_user2', password_hash='test', business_type='fast_moving', access_code='test456')
        db.session.add_all([user1, user2])
        db.session.commit()
        
        # 创建测试供应商
        supplier1 = Supplier(name='测试供应商1', user_id=user1.id, business_type='oil')
        supplier2 = Supplier(name='测试供应商2', user_id=user2.id, business_type='fast_moving')
        db.session.add_all([supplier1, supplier2])
        db.session.commit()
        
        # 创建测试订单
        for i in range(10):
            order = Order(
                order_no=f'TEST{i:03d}',
                warehouse=f'仓库{i}',
                goods=f'商品{i}',
                delivery_address=f'地址{i}',
                user_id=user1.id if i % 2 == 0 else user2.id,
                business_type='oil' if i % 2 == 0 else 'fast_moving',
                status='active' if i % 3 == 0 else 'completed'
            )
            db.session.add(order)
        db.session.commit()
        
        # 创建测试报价
        orders = Order.query.all()
        for i, order in enumerate(orders[:5]):
            quote = Quote(
                order_id=order.id,
                supplier_id=supplier1.id if i % 2 == 0 else supplier2.id,
                price=100.0 + i * 10
            )
            db.session.add(quote)
        db.session.commit()
    
    def test_index_creation(self, setup_test_database):
        """测试索引创建功能"""
        # 使用实际的数据库文件进行测试
        with patch('migrations.add_performance_indexes.logging') as mock_logging:
            # 备份原数据库路径配置
            original_path = 'database.db'
            test_path = 'test_database.db'
            
            # 创建测试数据库文件
            shutil.copy2(original_path, test_path) if os.path.exists(original_path) else None
            
            # 修改脚本中的数据库路径
            with patch('migrations.add_performance_indexes.db_path', test_path):
                result = add_performance_indexes()
                
                assert result is True, "索引创建应该成功"
                mock_logging.info.assert_called()
                
                # 验证索引是否创建成功
                conn = sqlite3.connect(test_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
                indexes = cursor.fetchall()
                conn.close()
                
                expected_indexes = [
                    'idx_orders_status',
                    'idx_orders_created_at', 
                    'idx_orders_user_id',
                    'idx_orders_business_type',
                    'idx_quotes_order_id',
                    'idx_quotes_supplier_id',
                    'idx_quotes_price',
                    'idx_suppliers_user_id',
                    'idx_suppliers_business_type',
                    'idx_order_suppliers_order_id',
                    'idx_order_suppliers_supplier_id'
                ]
                
                actual_indexes = [idx[0] for idx in indexes]
                for expected_idx in expected_indexes:
                    assert expected_idx in actual_indexes, f"索引 {expected_idx} 应该被创建"
            
            # 清理测试文件
            if os.path.exists(test_path):
                os.remove(test_path)
    
    def test_query_performance_improvement(self, setup_test_database):
        """测试查询性能提升"""
        with app.app_context():
            import time
            
            # 测试带索引的查询性能
            start_time = time.time()
            
            # 模拟常见查询
            orders_by_status = Order.query.filter_by(status='active').all()
            orders_by_business_type = Order.query.filter_by(business_type='oil').all()
            orders_ordered = Order.query.order_by(Order.created_at.desc()).limit(5).all()
            
            quotes_by_order = Quote.query.filter_by(order_id=1).all()
            quotes_by_price = Quote.query.order_by(Quote.price.asc()).first()
            
            suppliers_by_type = Supplier.query.filter_by(business_type='oil').all()
            
            query_time = time.time() - start_time
            
            # 验证查询能正常执行
            assert isinstance(orders_by_status, list), "状态查询应该返回列表"
            assert isinstance(orders_by_business_type, list), "业务类型查询应该返回列表"
            assert isinstance(orders_ordered, list), "排序查询应该返回列表"
            assert isinstance(quotes_by_order, list), "报价查询应该返回列表"
            assert isinstance(suppliers_by_type, list), "供应商查询应该返回列表"
            
            # 查询时间应该在合理范围内（小于1秒）
            assert query_time < 1.0, f"查询时间过长: {query_time:.3f}秒"
    
    def test_index_validation(self, setup_test_database):
        """测试索引验证功能"""
        with patch('migrations.add_performance_indexes.logging') as mock_logging:
            # 验证索引性能
            result = validate_index_performance()
            
            # 在测试环境中，即使没有真实数据库文件，也应该能处理
            assert isinstance(result, bool), "索引验证应该返回布尔值"
            
            if result:
                mock_logging.info.assert_called()


class TestFileSecurity:
    """文件安全增强测试"""
    
    def test_file_size_validation(self):
        """测试文件大小验证"""
        # 正常大小文件
        valid, msg = FileSecurity.validate_file_size(1024 * 1024)  # 1MB
        assert valid is True, "1MB文件应该通过验证"
        assert "通过" in msg
        
        # 超大文件
        valid, msg = FileSecurity.validate_file_size(20 * 1024 * 1024)  # 20MB
        assert valid is False, "20MB文件应该被拒绝"
        assert "超过限制" in msg
        
        # 边界值测试
        valid, msg = FileSecurity.validate_file_size(FileSecurity.MAX_FILE_SIZE)
        assert valid is True, "最大允许大小应该通过验证"
        
        valid, msg = FileSecurity.validate_file_size(FileSecurity.MAX_FILE_SIZE + 1)
        assert valid is False, "超过最大大小1字节应该被拒绝"
    
    def test_file_type_validation(self):
        """测试文件类型验证"""
        # 创建临时测试文件
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            # 写入XLSX文件头部（ZIP格式）
            tmp_file.write(b'PK\x03\x04\x14\x00\x06\x00')
            tmp_file.flush()
            
            valid, msg = FileSecurity.validate_file_type(tmp_file.name)
            assert valid is True, "有效的XLSX文件应该通过验证"
            
            os.unlink(tmp_file.name)
        
        # 测试不支持的文件类型
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
            tmp_file.write(b'test content')
            tmp_file.flush()
            
            valid, msg = FileSecurity.validate_file_type(tmp_file.name)
            assert valid is False, "TXT文件应该被拒绝"
            assert "不支持的文件扩展名" in msg
            
            os.unlink(tmp_file.name)
        
        # 测试恶意文件（扩展名与内容不匹配）
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            tmp_file.write(b'not a real xlsx file')
            tmp_file.flush()
            
            valid, msg = FileSecurity.validate_file_type(tmp_file.name)
            assert valid is False, "伪造的XLSX文件应该被拒绝"
            
            os.unlink(tmp_file.name)
    
    def test_file_name_validation(self):
        """测试文件名安全验证"""
        # 正常文件名
        valid, msg = FileSecurity.validate_file_name("订单列表.xlsx")
        assert valid is True, "正常文件名应该通过验证"
        
        # 包含危险字符的文件名
        dangerous_names = [
            "file<script>.xlsx",
            "file>test.xlsx", 
            'file"test.xlsx',
            "file|test.xlsx",
            "file?test.xlsx",
            "file*test.xlsx",
            "file\x00test.xlsx",
        ]
        
        for dangerous_name in dangerous_names:
            valid, msg = FileSecurity.validate_file_name(dangerous_name)
            assert valid is False, f"危险文件名应该被拒绝: {dangerous_name}"
            assert "不安全字符" in msg
        
        # 路径遍历攻击
        traversal_names = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "file..name.xlsx",
            "/absolute/path/file.xlsx",
            "folder\\file.xlsx",
        ]
        
        for traversal_name in traversal_names:
            valid, msg = FileSecurity.validate_file_name(traversal_name)
            assert valid is False, f"路径遍历文件名应该被拒绝: {traversal_name}"
        
        # 空文件名
        valid, msg = FileSecurity.validate_file_name("")
        assert valid is False, "空文件名应该被拒绝"
        
        valid, msg = FileSecurity.validate_file_name("   ")
        assert valid is False, "只有空格的文件名应该被拒绝"
        
        # 过长文件名
        long_name = "a" * 300 + ".xlsx"
        valid, msg = FileSecurity.validate_file_name(long_name)
        assert valid is False, "过长文件名应该被拒绝"
        assert "过长" in msg
    
    def test_safe_filename_generation(self):
        """测试安全文件名生成"""
        # 正常文件名
        safe_name = FileSecurity.get_safe_filename("正常文件.xlsx")
        assert safe_name == "正常文件.xlsx", "正常文件名应该保持不变"
        
        # 包含危险字符的文件名
        unsafe_name = "file<>:\"|?*.xlsx"
        safe_name = FileSecurity.get_safe_filename(unsafe_name)
        assert "<" not in safe_name, "危险字符应该被替换"
        assert ">" not in safe_name
        assert ":" not in safe_name
        assert "|" not in safe_name
        assert "?" not in safe_name
        assert "*" not in safe_name
        assert safe_name.endswith(".xlsx"), "文件扩展名应该保留"
        
        # 过长文件名
        long_name = "very_long_filename_" * 10 + ".xlsx"
        safe_name = FileSecurity.get_safe_filename(long_name)
        assert len(safe_name) <= 100, "文件名长度应该被限制"
        assert safe_name.endswith(".xlsx"), "扩展名应该保留"
        
        # 空文件名
        safe_name = FileSecurity.get_safe_filename("")
        assert safe_name == "safe_file", "空文件名应该使用默认名称"
        
        safe_name = FileSecurity.get_safe_filename(None)
        assert safe_name == "unknown_file", "None文件名应该使用默认名称"
    
    def test_upload_file_validation(self):
        """测试上传文件验证"""
        # 模拟Flask文件上传对象
        class MockFileObject:
            def __init__(self, filename):
                self.filename = filename
        
        # 有效文件
        valid_file = MockFileObject("订单数据.xlsx")
        valid, msg = validate_upload_file(valid_file)
        assert valid is True, "有效上传文件应该通过验证"
        
        # 无效文件类型
        invalid_file = MockFileObject("恶意文件.exe")
        valid, msg = validate_upload_file(invalid_file)
        assert valid is False, "无效文件类型应该被拒绝"
        assert "不支持的文件类型" in msg
        
        # 无文件名
        no_name_file = MockFileObject("")
        valid, msg = validate_upload_file(no_name_file)
        assert valid is False, "无文件名应该被拒绝"
        assert "未选择文件" in msg
        
        # 无效对象
        valid, msg = validate_upload_file(None)
        assert valid is False, "None对象应该被拒绝"
        assert "无效的文件对象" in msg
    
    def test_file_security_decorator(self):
        """测试文件安全装饰器"""
        # 正常函数执行
        @file_security_check
        def normal_function():
            return "success"
        
        result = normal_function()
        assert result == "success", "装饰器不应该影响正常函数执行"
        
        # 函数抛出异常
        @file_security_check
        def error_function():
            raise ValueError("测试错误")
        
        with pytest.raises(ValueError):
            error_function()
    
    def test_export_file_validation(self):
        """测试导出文件验证"""
        # 创建有效的测试文件
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            # 写入有效的XLSX文件头
            tmp_file.write(b'PK\x03\x04\x14\x00\x06\x00\x08\x00')
            tmp_file.write(b'A' * 100)  # 添加一些内容
            tmp_file.flush()
            
            valid, msg = FileSecurity.validate_export_file(tmp_file.name)
            assert valid is True, "有效导出文件应该通过验证"
            
            os.unlink(tmp_file.name)
        
        # 测试不存在的文件
        valid, msg = FileSecurity.validate_export_file("/nonexistent/file.xlsx")
        assert valid is False, "不存在的文件应该被拒绝"
        assert "文件不存在" in msg


class TestErrorCodeSystem:
    """统一错误码系统测试"""
    
    def test_error_code_definitions(self):
        """测试错误码定义"""
        # 验证错误码格式
        assert ErrorCode.SYS_001[0] == "SYS_001", "系统错误码格式正确"
        assert ErrorCode.BIZ_001[0] == "BIZ_001", "业务错误码格式正确"
        assert ErrorCode.SEC_001[0] == "SEC_001", "安全错误码格式正确"
        assert ErrorCode.VAL_001[0] == "VAL_001", "验证错误码格式正确"
        
        # 验证错误消息不为空
        assert len(ErrorCode.SYS_001[1]) > 0, "错误消息不应为空"
        assert len(ErrorCode.BIZ_001[1]) > 0, "错误消息不应为空"
        assert len(ErrorCode.SEC_001[1]) > 0, "错误消息不应为空"
        assert len(ErrorCode.VAL_001[1]) > 0, "错误消息不应为空"
    
    def test_error_response_creation(self):
        """测试错误响应创建"""
        # 基本错误响应
        response, status = ErrorHandler.create_error_response(ErrorCode.BIZ_001)
        
        assert response["error_code"] == "BIZ_001", "错误码应该正确"
        assert response["error_message"] == "订单不存在", "错误消息应该正确"
        assert response["success"] is False, "成功标志应该为False"
        assert "timestamp" in response, "应该包含时间戳"
        assert status == 400, "默认HTTP状态码应该为400"
        
        # 带详细信息的错误响应
        response, status = ErrorHandler.create_error_response(
            ErrorCode.VAL_001, "字段名: username", 422
        )
        
        assert response["details"] == "字段名: username", "详细信息应该被包含"
        assert status == 422, "自定义HTTP状态码应该正确"
    
    def test_success_response_creation(self):
        """测试成功响应创建"""
        # 基本成功响应
        response = ErrorHandler.create_success_response()
        
        assert response["success"] is True, "成功标志应该为True"
        assert response["message"] == "操作成功", "默认成功消息正确"
        assert "timestamp" in response, "应该包含时间戳"
        
        # 带数据的成功响应
        test_data = {"id": 1, "name": "测试"}
        response = ErrorHandler.create_success_response(test_data, "创建成功")
        
        assert response["data"] == test_data, "数据应该被包含"
        assert response["message"] == "创建成功", "自定义消息应该正确"
    
    def test_database_error_handling(self):
        """测试数据库错误处理"""
        # 唯一约束错误
        unique_error = Exception("UNIQUE constraint failed")
        response, status = ErrorHandler.handle_database_error(unique_error)
        
        assert response["error_code"] == "VAL_010", "应该映射到重复数据错误"
        assert status == 409, "唯一约束冲突应该返回409状态码"
        
        # 外键约束错误
        fk_error = Exception("FOREIGN KEY constraint failed")
        response, status = ErrorHandler.handle_database_error(fk_error)
        
        assert response["error_code"] == "BIZ_008", "应该映射到关联数据错误"
        assert status == 400, "外键约束错误应该返回400状态码"
        
        # 非空约束错误
        not_null_error = Exception("NOT NULL constraint failed")
        response, status = ErrorHandler.handle_database_error(not_null_error)
        
        assert response["error_code"] == "VAL_001", "应该映射到必填字段错误"
        assert status == 400, "非空约束错误应该返回400状态码"
        
        # 数据库锁定错误
        lock_error = Exception("database is locked")
        response, status = ErrorHandler.handle_database_error(lock_error)
        
        assert response["error_code"] == "SYS_002", "应该映射到数据库操作错误"
        assert status == 503, "数据库繁忙应该返回503状态码"
        
        # 一般数据库错误
        general_error = Exception("some other database error")
        response, status = ErrorHandler.handle_database_error(general_error)
        
        assert response["error_code"] == "SYS_002", "应该映射到一般数据库错误"
        assert status == 500, "一般数据库错误应该返回500状态码"
    
    def test_validation_error_handling(self):
        """测试验证错误处理"""
        # 必填字段错误
        response, status = ErrorHandler.handle_validation_error("username", None, "required")
        assert response["error_code"] == "VAL_001", "必填字段错误码正确"
        assert "username" in response["details"], "字段名应该被包含"
        
        # 格式错误
        response, status = ErrorHandler.handle_validation_error("email", "invalid-email", "format")
        assert response["error_code"] == "VAL_003", "格式错误码正确"
        assert "email" in response["details"], "字段名应该被包含"
        assert "invalid-email" in response["details"], "错误值应该被包含"
        
        # 长度错误
        response, status = ErrorHandler.handle_validation_error("password", "123", "length")
        assert response["error_code"] == "VAL_002", "长度错误码正确"
        
        # 范围错误
        response, status = ErrorHandler.handle_validation_error("age", 200, "range")
        assert response["error_code"] == "VAL_009", "范围错误码正确"
        
        # 类型错误
        response, status = ErrorHandler.handle_validation_error("price", "not-a-number", "type")
        assert response["error_code"] == "VAL_008", "类型错误码正确"
    
    def test_permission_error_handling(self):
        """测试权限错误处理"""
        # 基本权限错误
        response, status = ErrorHandler.handle_permission_error()
        assert response["error_code"] == "SEC_002", "权限错误码正确"
        assert status == 403, "权限错误应该返回403状态码"
        
        # 详细权限错误
        response, status = ErrorHandler.handle_permission_error(
            user_id=123, resource="orders", action="delete"
        )
        assert "用户ID: 123" in response["details"], "用户ID应该被包含"
        assert "资源: orders" in response["details"], "资源名应该被包含"
        assert "操作: delete" in response["details"], "操作类型应该被包含"
    
    def test_business_error_handling(self):
        """测试业务错误处理"""
        response, status = ErrorHandler.handle_business_error(
            ErrorCode.BIZ_004, "订单状态为已完成"
        )
        
        assert response["error_code"] == "BIZ_004", "业务错误码正确"
        assert response["details"] == "订单状态为已完成", "上下文信息应该被包含"
        assert status == 400, "业务错误应该返回400状态码"
    
    def test_file_security_error_handling(self):
        """测试文件安全错误处理"""
        # 文件大小错误
        response, status = ErrorHandler.handle_file_security_error(
            "文件大小超出限制", "large_file.xlsx"
        )
        assert response["error_code"] == "SEC_005", "文件大小错误码正确"
        assert "large_file.xlsx" in response["details"], "文件名应该被包含"
        
        # 文件类型错误
        response, status = ErrorHandler.handle_file_security_error(
            "不支持的文件类型", "malicious.exe"
        )
        assert response["error_code"] == "SEC_004", "文件类型错误码正确"
        assert "malicious.exe" in response["details"], "文件名应该被包含"
        
        # 一般文件系统错误
        response, status = ErrorHandler.handle_file_security_error("文件读取失败")
        assert response["error_code"] == "SYS_003", "文件系统错误码正确"
    
    def test_common_errors_shortcuts(self):
        """测试常用错误快捷方式"""
        assert CommonErrors.LOGIN_REQUIRED == ErrorCode.SEC_001, "登录错误快捷方式正确"
        assert CommonErrors.PERMISSION_DENIED == ErrorCode.SEC_002, "权限错误快捷方式正确"
        assert CommonErrors.REQUIRED_FIELD == ErrorCode.VAL_001, "必填字段错误快捷方式正确"
        assert CommonErrors.ORDER_NOT_FOUND == ErrorCode.BIZ_001, "订单不存在错误快捷方式正确"
        assert CommonErrors.DATABASE_ERROR == ErrorCode.SYS_002, "数据库错误快捷方式正确"
    
    def test_error_response_helper(self):
        """测试错误响应辅助类"""
        with app.test_request_context():
            # JSON错误响应
            response, status = ErrorResponseHelper.json_error_response(ErrorCode.BIZ_001)
            assert status == 400, "JSON响应状态码正确"
            
            # Flash错误消息（需要模拟Flask上下文）
            with app.test_client():
                ErrorResponseHelper.flash_error_message(ErrorCode.VAL_001, "测试详情")
                # Flash消息会被添加到会话中，这里主要测试不会抛出异常


class TestEnvironmentValidator:
    """环境验证器测试"""
    
    def test_secret_key_strength_validation(self):
        """测试密钥强度验证"""
        # 强密钥
        strong_key = "MyVerySecureSecretKey123!@#$%^&*()"
        valid, msg = EnvironmentValidator.validate_secret_key_strength(strong_key)
        assert valid is True, "强密钥应该通过验证"
        assert "通过" in msg
        
        # 弱密钥 - 太短
        short_key = "short"
        valid, msg = EnvironmentValidator.validate_secret_key_strength(short_key)
        assert valid is False, "短密钥应该被拒绝"
        assert "长度" in msg
        
        # 弱密钥 - 默认值
        default_key = "trade-inquiry-system-secret-key-2025"
        valid, msg = EnvironmentValidator.validate_secret_key_strength(default_key)
        assert valid is False, "默认密钥应该被拒绝"
        assert "默认" in msg
        
        # 弱密钥 - 复杂度不足
        simple_key = "a" * 40  # 长度够但复杂度不足
        valid, msg = EnvironmentValidator.validate_secret_key_strength(simple_key)
        assert valid is False, "简单密钥应该被拒绝"
        assert "复杂度" in msg
        
        # 弱密钥 - 包含常见词汇
        common_word_key = "MyPasswordContainsPasswordWord123!"
        valid, msg = EnvironmentValidator.validate_secret_key_strength(common_word_key)
        assert valid is False, "包含常见词汇的密钥应该被拒绝"
        assert "常见词汇" in msg
        
        # 空密钥
        valid, msg = EnvironmentValidator.validate_secret_key_strength("")
        assert valid is False, "空密钥应该被拒绝"
        assert "不能为空" in msg
    
    def test_database_config_validation(self):
        """测试数据库配置验证"""
        # 有效的生产数据库配置
        prod_db_url = "postgresql://user:pass@prod-server:5432/mydb"
        valid, msg = EnvironmentValidator.validate_database_config(prod_db_url)
        assert valid is True, "生产数据库配置应该通过验证"
        
        # 危险的默认配置
        default_db_url = "sqlite:///database.db"
        valid, msg = EnvironmentValidator.validate_database_config(default_db_url)
        assert valid is False, "默认数据库配置应该被拒绝"
        assert "不安全" in msg
        
        # 内存数据库
        memory_db_url = "sqlite:///:memory:"
        valid, msg = EnvironmentValidator.validate_database_config(memory_db_url)
        assert valid is False, "内存数据库应该被拒绝"
        assert "内存数据库" in msg
        
        # 相对路径SQLite
        relative_db_url = "sqlite:///relative/path/db.sqlite"
        valid, msg = EnvironmentValidator.validate_database_config(relative_db_url)
        assert valid is False, "相对路径数据库应该被拒绝"
        assert "绝对路径" in msg
        
        # 空配置
        valid, msg = EnvironmentValidator.validate_database_config("")
        assert valid is False, "空数据库配置应该被拒绝"
        assert "不能为空" in msg
    
    def test_logging_config_validation(self):
        """测试日志配置验证"""
        # 设置有效日志级别
        with patch.dict(os.environ, {'LOG_LEVEL': 'INFO'}):
            valid, suggestions = EnvironmentValidator.validate_logging_config()
            assert isinstance(valid, bool), "日志验证应该返回布尔值"
            assert isinstance(suggestions, list), "建议应该是列表"
        
        # 设置无效日志级别
        with patch.dict(os.environ, {'LOG_LEVEL': 'INVALID'}):
            valid, suggestions = EnvironmentValidator.validate_logging_config()
            assert valid is False, "无效日志级别应该失败"
            assert any("无效" in s for s in suggestions), "应该包含无效级别提示"
        
        # 设置DEBUG级别（生产环境不推荐）
        with patch.dict(os.environ, {'LOG_LEVEL': 'DEBUG'}):
            valid, suggestions = EnvironmentValidator.validate_logging_config()
            assert any("生产环境" in s for s in suggestions), "应该建议不要在生产环境使用DEBUG"
        
        # 测试日志文件路径
        with patch.dict(os.environ, {'LOG_FILE': '/nonexistent/path/app.log'}):
            valid, suggestions = EnvironmentValidator.validate_logging_config()
            assert any("不存在" in s for s in suggestions), "应该检查日志目录是否存在"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_production_environment_validation(self):
        """测试生产环境验证"""
        # 空环境（缺少必需变量）
        is_valid, errors, warnings = EnvironmentValidator.validate_production_env()
        assert is_valid is False, "空环境应该验证失败"
        assert len(errors) > 0, "应该有错误信息"
        assert any("SECRET_KEY" in error for error in errors), "应该提示缺少SECRET_KEY"
        assert any("DATABASE_URL" in error for error in errors), "应该提示缺少DATABASE_URL"
    
    @patch.dict(os.environ, {
        'SECRET_KEY': 'MyVerySecureSecretKey123!@#$%^&*()',
        'DATABASE_URL': 'postgresql://user:pass@prod-server:5432/mydb',
        'FLASK_ENV': 'production'
    })
    def test_valid_production_environment(self):
        """测试有效的生产环境配置"""
        is_valid, errors, warnings = EnvironmentValidator.validate_production_env()
        assert is_valid is True, "有效的生产环境配置应该通过验证"
        assert len(errors) == 0, "不应该有错误"
    
    @patch.dict(os.environ, {
        'SECRET_KEY': 'trade-inquiry-system-secret-key-2025',
        'DATABASE_URL': 'sqlite:///database.db',
        'FLASK_DEBUG': 'true'
    })
    def test_dangerous_production_environment(self):
        """测试危险的生产环境配置"""
        is_valid, errors, warnings = EnvironmentValidator.validate_production_env()
        assert is_valid is False, "危险配置应该验证失败"
        assert any("不安全的默认值" in error for error in errors), "应该检测到不安全的默认值"
        assert any("FLASK_DEBUG" in error for error in errors), "应该检测到DEBUG模式启用"
    
    def test_security_report_generation(self):
        """测试安全配置报告生成"""
        with patch.dict(os.environ, {
            'SECRET_KEY': 'MyVerySecureSecretKey123!@#$%^&*()',
            'DATABASE_URL': 'postgresql://user:pass@prod-server:5432/mydb',
            'FLASK_ENV': 'production'
        }):
            report = EnvironmentValidator.generate_security_report()
            
            assert isinstance(report, dict), "报告应该是字典格式"
            assert "overall_status" in report, "应该包含总体状态"
            assert "timestamp" in report, "应该包含时间戳"
            assert "environment" in report, "应该包含环境信息"
            assert "validation_results" in report, "应该包含验证结果"
            assert "recommendations" in report, "应该包含建议"
            
            # 验证各项检查结果
            results = report["validation_results"]
            assert "environment_variables" in results, "应该包含环境变量检查"
            assert "secret_key" in results, "应该包含密钥检查"
            assert "database" in results, "应该包含数据库检查"
            assert "logging" in results, "应该包含日志检查"
    
    def test_startup_environment_validation(self):
        """测试启动时环境验证"""
        with patch.dict(os.environ, {'FLASK_ENV': 'development'}):
            # 开发环境应该不会抛出异常，即使配置有问题
            is_valid, errors, warnings = validate_startup_environment()
            assert isinstance(is_valid, bool), "应该返回验证结果"
            assert isinstance(errors, list), "错误应该是列表"
            assert isinstance(warnings, list), "警告应该是列表"
        
        with patch.dict(os.environ, {
            'FLASK_ENV': 'production',
            'SECRET_KEY': 'invalid',
            'DATABASE_URL': 'sqlite:///database.db'
        }):
            # 生产环境配置错误应该抛出异常
            with pytest.raises(EnvironmentError):
                validate_startup_environment()


class TestIntegrationScenarios:
    """集成测试场景"""
    
    @pytest.fixture
    def setup_integration_test(self):
        """设置集成测试环境"""
        with app.app_context():
            # 创建测试数据
            db.create_all()
            
            # 创建测试用户
            user = User(username='integration_user', password_hash='test', business_type='oil', access_code='test123')
            db.session.add(user)
            db.session.commit()
            
            yield user
            
            # 清理
            db.session.remove()
    
    def test_order_creation_with_error_handling(self, setup_integration_test):
        """测试订单创建的完整错误处理流程"""
        user = setup_integration_test
        
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = str(user.id)
                sess['_fresh'] = True
            
            # 测试缺少必填字段的情况
            response = client.post('/orders/new', data={
                'warehouse': '',  # 空仓库名
                'goods': '测试商品',
                'delivery_address': '测试地址'
            })
            
            # 验证错误处理是否正确
            assert response.status_code in [200, 302], "应该处理错误并返回适当响应"
    
    def test_file_upload_security_integration(self, setup_integration_test):
        """测试文件上传安全集成"""
        user = setup_integration_test
        
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = str(user.id)
                sess['_fresh'] = True
            
            # 创建恶意文件
            malicious_content = b'<script>alert("xss")</script>'
            malicious_file = (BytesIO(malicious_content), 'malicious.exe')
            
            # 尝试上传恶意文件（如果有文件上传端点）
            # 这里假设有一个文件上传的路由，实际项目中可能需要调整
            
            # 验证文件安全检查是否生效
            valid, msg = validate_upload_file(type('MockFile', (), {'filename': 'malicious.exe'})())
            assert valid is False, "恶意文件应该被拒绝"
    
    def test_database_performance_with_indexes(self, setup_integration_test):
        """测试数据库索引对性能的影响"""
        user = setup_integration_test
        
        # 创建大量测试数据
        for i in range(100):
            order = Order(
                order_no=f'PERF{i:04d}',
                warehouse=f'仓库{i}',
                goods=f'商品{i}',
                delivery_address=f'地址{i}',
                user_id=user.id,
                business_type='oil',
                status='active' if i % 2 == 0 else 'completed'
            )
            db.session.add(order)
        
        db.session.commit()
        
        # 测试查询性能
        import time
        
        start_time = time.time()
        
        # 执行常见查询
        active_orders = Order.query.filter_by(status='active').count()
        oil_orders = Order.query.filter_by(business_type='oil').count()
        recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
        
        query_time = time.time() - start_time
        
        # 验证查询结果
        assert active_orders > 0, "应该有活跃订单"
        assert oil_orders > 0, "应该有油脂订单"
        assert len(recent_orders) > 0, "应该有最近订单"
        
        # 验证查询时间在合理范围内
        assert query_time < 2.0, f"查询时间过长: {query_time:.3f}秒"
    
    def test_error_code_in_business_flow(self, setup_integration_test):
        """测试错误码在业务流程中的使用"""
        user = setup_integration_test
        
        # 模拟业务错误场景
        try:
            # 尝试访问不存在的订单
            non_existent_order_id = 99999
            order = Order.query.get(non_existent_order_id)
            
            if not order:
                # 使用统一错误码
                response, status = ErrorHandler.create_error_response(
                    ErrorCode.BIZ_001, f"订单ID: {non_existent_order_id}"
                )
                
                assert response["error_code"] == "BIZ_001", "错误码应该正确"
                assert response["success"] is False, "业务错误应该标记为失败"
                assert "99999" in response["details"], "错误详情应该包含订单ID"
        
        except Exception as e:
            # 验证异常处理
            response, status = ErrorHandler.handle_database_error(e)
            assert response["success"] is False, "数据库错误应该被正确处理"


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v', '--tb=short'])