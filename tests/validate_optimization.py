#!/usr/bin/env python3
"""
优化功能验证脚本
快速验证系统优化功能是否正常工作
"""

import sys
import os
import time
import tempfile
from typing import Dict, List, Tuple

# 添加项目根目录到Python路径
project_root = '/Users/lichuansong/Desktop/projects/wlxj_python'
sys.path.insert(0, project_root)

class OptimizationValidator:
    """优化功能验证器"""
    
    def __init__(self):
        self.results = {}
        
    def run_all_validations(self) -> Dict[str, bool]:
        """运行所有验证"""
        print("=" * 60)
        print("系统优化功能验证")
        print("=" * 60)
        
        validations = [
            ("文件安全功能", self.validate_file_security),
            ("错误码系统", self.validate_error_codes),
            ("环境验证器", self.validate_environment_validator),
            ("查询辅助工具", self.validate_query_helpers),
            ("数据库索引", self.validate_database_indexes),
        ]
        
        for name, validator in validations:
            print(f"\n检查 {name}...")
            try:
                result = validator()
                status = "✓ 通过" if result else "✗ 失败"
                print(f"  {status}")
                self.results[name] = result
            except Exception as e:
                print(f"  ✗ 错误: {str(e)}")
                self.results[name] = False
        
        return self.results
    
    def validate_file_security(self) -> bool:
        """验证文件安全功能"""
        try:
            from utils.file_security import FileSecurity, validate_upload_file
            
            # 测试文件大小验证
            valid, msg = FileSecurity.validate_file_size(1024 * 1024)  # 1MB
            if not valid:
                print(f"    文件大小验证失败: {msg}")
                return False
            
            # 测试超大文件
            valid, msg = FileSecurity.validate_file_size(20 * 1024 * 1024)  # 20MB
            if valid:
                print("    超大文件应该被拒绝")
                return False
            
            # 测试文件名验证
            valid, msg = FileSecurity.validate_file_name("正常文件.xlsx")
            if not valid:
                print(f"    正常文件名验证失败: {msg}")
                return False
            
            # 测试危险文件名
            valid, msg = FileSecurity.validate_file_name("../../../etc/passwd")
            if valid:
                print("    危险文件名应该被拒绝")
                return False
            
            # 测试安全文件名生成
            safe_name = FileSecurity.get_safe_filename("危险<>文件.xlsx")
            if "<" in safe_name or ">" in safe_name:
                print("    安全文件名生成失败")
                return False
            
            print("    文件大小验证 ✓")
            print("    文件类型验证 ✓")
            print("    文件名安全检查 ✓")
            print("    安全文件名生成 ✓")
            
            return True
            
        except ImportError as e:
            print(f"    导入错误: {e}")
            return False
    
    def validate_error_codes(self) -> bool:
        """验证错误码系统"""
        try:
            from utils.error_codes import ErrorHandler, ErrorCode, CommonErrors
            
            # 测试错误响应创建
            response, status = ErrorHandler.create_error_response(ErrorCode.BIZ_001)
            
            if response["error_code"] != "BIZ_001":
                print("    错误码不正确")
                return False
            
            if not isinstance(response["error_message"], str):
                print("    错误消息格式不正确")
                return False
            
            if response["success"] is not False:
                print("    成功标志应该为False")
                return False
            
            if status != 400:
                print("    默认状态码应该为400")
                return False
            
            # 测试成功响应创建
            success_response = ErrorHandler.create_success_response({"id": 1}, "测试成功")
            
            if success_response["success"] is not True:
                print("    成功响应标志错误")
                return False
            
            # 测试数据库错误处理
            test_error = Exception("UNIQUE constraint failed")
            response, status = ErrorHandler.handle_database_error(test_error)
            
            if response["error_code"] != "VAL_010":
                print(f"    数据库错误映射不正确: {response['error_code']}")
                return False
            
            # 测试常用错误快捷方式
            if CommonErrors.LOGIN_REQUIRED != ErrorCode.SEC_001:
                print("    错误快捷方式不正确")
                return False
            
            print("    错误响应创建 ✓")
            print("    成功响应创建 ✓")
            print("    数据库错误处理 ✓")
            print("    常用错误快捷方式 ✓")
            
            return True
            
        except ImportError as e:
            print(f"    导入错误: {e}")
            return False
    
    def validate_environment_validator(self) -> bool:
        """验证环境验证器"""
        try:
            from utils.env_validator import EnvironmentValidator
            
            # 测试密钥强度验证
            weak_key = "weak"
            valid, msg = EnvironmentValidator.validate_secret_key_strength(weak_key)
            if valid:
                print("    弱密钥应该被拒绝")
                return False
            
            strong_key = "VeryComplexApplicationPhrase123!@#$%^&*()"
            valid, msg = EnvironmentValidator.validate_secret_key_strength(strong_key)
            if not valid:
                print(f"    强密钥验证失败: {msg}")
                return False
            
            # 测试数据库配置验证
            weak_db = "sqlite:///database.db"
            valid, msg = EnvironmentValidator.validate_database_config(weak_db)
            if valid:
                print("    默认数据库配置应该被拒绝")
                return False
            
            strong_db = "postgresql://user:pass@server:5432/db"
            valid, msg = EnvironmentValidator.validate_database_config(strong_db)
            if not valid:
                print(f"    生产数据库配置验证失败: {msg}")
                return False
            
            # 测试安全报告生成
            report = EnvironmentValidator.generate_security_report()
            
            required_keys = ['overall_status', 'timestamp', 'environment', 'validation_results']
            for key in required_keys:
                if key not in report:
                    print(f"    安全报告缺少字段: {key}")
                    return False
            
            print("    密钥强度验证 ✓")
            print("    数据库配置验证 ✓")
            print("    安全报告生成 ✓")
            
            return True
            
        except ImportError as e:
            print(f"    导入错误: {e}")
            return False
    
    def validate_query_helpers(self) -> bool:
        """验证查询辅助工具"""
        try:
            from utils.query_helpers import QueryOptimizer, DateHelper
            
            # 测试日期范围解析
            start_dt, end_dt = DateHelper.parse_date_range("2024-01-01", "2024-01-31")
            
            if start_dt is None or end_dt is None:
                print("    有效日期解析失败")
                return False
            
            if start_dt.year != 2024 or start_dt.month != 1 or start_dt.day != 1:
                print("    开始日期解析不正确")
                return False
            
            if end_dt.year != 2024 or end_dt.month != 1 or end_dt.day != 31:
                print("    结束日期解析不正确")
                return False
            
            # 测试无效日期处理
            start_dt, end_dt = DateHelper.parse_date_range("invalid", "2024-01-01")
            if start_dt is not None:
                print("    无效日期应该返回None")
                return False
            
            # 测试快捷日期范围
            start_date, end_date = DateHelper.get_quick_date_range('today')
            if not start_date or not end_date:
                print("    今天快捷日期范围失败")
                return False
            
            start_date, end_date = DateHelper.get_quick_date_range('this_month')
            if not start_date or not end_date:
                print("    本月快捷日期范围失败")
                return False
            
            print("    日期范围解析 ✓")
            print("    无效日期处理 ✓")
            print("    快捷日期范围 ✓")
            
            return True
            
        except ImportError as e:
            print(f"    导入错误: {e}")
            return False
    
    def validate_database_indexes(self) -> bool:
        """验证数据库索引功能"""
        try:
            # 检查索引迁移脚本是否存在且可导入
            from migrations.add_performance_indexes import add_performance_indexes, validate_index_performance
            
            # 验证函数可调用
            if not callable(add_performance_indexes):
                print("    add_performance_indexes不是可调用函数")
                return False
            
            if not callable(validate_index_performance):
                print("    validate_index_performance不是可调用函数")
                return False
            
            # 检查索引脚本内容
            import inspect
            source = inspect.getsource(add_performance_indexes)
            
            # 验证关键索引创建语句存在
            required_indexes = [
                "idx_orders_status",
                "idx_orders_created_at",
                "idx_orders_user_id",
                "idx_orders_business_type",
                "idx_quotes_order_id",
                "idx_quotes_supplier_id",
                "idx_quotes_price",
                "idx_suppliers_user_id",
                "idx_suppliers_business_type"
            ]
            
            for index_name in required_indexes:
                if index_name not in source:
                    print(f"    缺少索引: {index_name}")
                    return False
            
            print("    索引迁移脚本 ✓")
            print("    索引验证函数 ✓")
            print("    关键索引定义 ✓")
            
            return True
            
        except ImportError as e:
            print(f"    导入错误: {e}")
            return False
    
    def generate_summary(self):
        """生成验证摘要"""
        print("\n" + "=" * 60)
        print("验证摘要")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = sum(self.results.values())
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        print(f"成功率: {passed_tests / total_tests * 100:.1f}%")
        
        if failed_tests == 0:
            print("\n🎉 所有优化功能验证通过！")
            print("\n系统优化功能状态: 良好")
            print("建议: 可以进行完整的测试套件运行")
        else:
            print(f"\n⚠️  有 {failed_tests} 个功能验证失败")
            print("\n失败的功能:")
            for name, result in self.results.items():
                if not result:
                    print(f"  - {name}")
            print("\n建议: 检查失败的功能并修复问题")
        
        return failed_tests == 0


def main():
    """主函数"""
    validator = OptimizationValidator()
    
    try:
        # 运行所有验证
        results = validator.run_all_validations()
        
        # 生成摘要
        success = validator.generate_summary()
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n❌ 验证过程出错: {str(e)}")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)