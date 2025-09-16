from enum import Enum
from typing import Dict, Any, Optional, Tuple
import logging
from flask import jsonify

class ErrorCategory(Enum):
    """错误分类"""
    SYSTEM = "SYS"      # 系统错误
    BUSINESS = "BIZ"    # 业务错误
    SECURITY = "SEC"    # 安全错误
    VALIDATION = "VAL"  # 验证错误

class ErrorCode:
    """统一错误码定义"""
    
    # 系统错误 (SYS_001-099)
    SYS_001 = ("SYS_001", "数据库连接失败")
    SYS_002 = ("SYS_002", "数据库操作异常")
    SYS_003 = ("SYS_003", "文件系统错误")
    SYS_004 = ("SYS_004", "网络请求失败")
    SYS_005 = ("SYS_005", "服务暂时不可用")
    SYS_006 = ("SYS_006", "内存不足")
    SYS_007 = ("SYS_007", "系统配置错误")
    SYS_008 = ("SYS_008", "外部服务不可用")
    SYS_009 = ("SYS_009", "系统超时")
    SYS_010 = ("SYS_010", "系统维护中")
    
    # 业务错误 (BIZ_001-099)
    BIZ_001 = ("BIZ_001", "订单不存在")
    BIZ_002 = ("BIZ_002", "供应商不存在")
    BIZ_003 = ("BIZ_003", "报价不存在")
    BIZ_004 = ("BIZ_004", "订单状态不允许此操作")
    BIZ_005 = ("BIZ_005", "供应商已关联到订单")
    BIZ_006 = ("BIZ_006", "报价价格无效")
    BIZ_007 = ("BIZ_007", "订单已有中标供应商")
    BIZ_008 = ("BIZ_008", "业务类型不匹配")
    BIZ_009 = ("BIZ_009", "订单已完成")
    BIZ_010 = ("BIZ_010", "订单已取消")
    BIZ_011 = ("BIZ_011", "供应商无权限访问此订单")
    BIZ_012 = ("BIZ_012", "重复报价")
    BIZ_013 = ("BIZ_013", "报价时间已过期")
    BIZ_014 = ("BIZ_014", "订单数量超出限制")
    BIZ_015 = ("BIZ_015", "供应商账户被禁用")
    
    # 安全错误 (SEC_001-099)
    SEC_001 = ("SEC_001", "用户未登录")
    SEC_002 = ("SEC_002", "权限不足")
    SEC_003 = ("SEC_003", "访问码无效")
    SEC_004 = ("SEC_004", "文件类型不安全")
    SEC_005 = ("SEC_005", "文件大小超出限制")
    SEC_006 = ("SEC_006", "操作频率过高")
    SEC_007 = ("SEC_007", "IP地址被限制")
    SEC_008 = ("SEC_008", "会话已过期")
    SEC_009 = ("SEC_009", "密钥验证失败")
    SEC_010 = ("SEC_010", "恶意请求检测")
    
    # 验证错误 (VAL_001-099)
    VAL_001 = ("VAL_001", "必填字段为空")
    VAL_002 = ("VAL_002", "字段长度超出限制")
    VAL_003 = ("VAL_003", "数据格式无效")
    VAL_004 = ("VAL_004", "价格数值无效")
    VAL_005 = ("VAL_005", "日期格式无效")
    VAL_006 = ("VAL_006", "邮箱格式无效")
    VAL_007 = ("VAL_007", "手机号格式无效")
    VAL_008 = ("VAL_008", "参数类型错误")
    VAL_009 = ("VAL_009", "参数范围超出限制")
    VAL_010 = ("VAL_010", "重复数据")

class ErrorHandler:
    """统一错误处理器"""
    
    @staticmethod
    def create_error_response(error_code: Tuple[str, str], details: str = None, http_status: int = 400) -> Tuple[Dict[str, Any], int]:
        """创建标准错误响应
        
        Args:
            error_code: 错误码元组 (code, message)
            details: 详细错误信息
            http_status: HTTP状态码
            
        Returns:
            Tuple[Dict[str, Any], int]: (错误响应字典, HTTP状态码)
        """
        code, message = error_code
        response = {
            "error_code": code,
            "error_message": message,
            "success": False,
            "timestamp": ErrorHandler._get_timestamp()
        }
        
        if details:
            response["details"] = details
            
        # 根据错误类型确定日志级别
        log_level = ErrorHandler._get_log_level(code)
        ErrorHandler._log_error(code, message, details, log_level)
        
        return response, http_status
    
    @staticmethod
    def create_success_response(data: Any = None, message: str = "操作成功") -> Dict[str, Any]:
        """创建标准成功响应
        
        Args:
            data: 响应数据
            message: 成功消息
            
        Returns:
            Dict[str, Any]: 成功响应字典
        """
        response = {
            "success": True,
            "message": message,
            "timestamp": ErrorHandler._get_timestamp()
        }
        
        if data is not None:
            response["data"] = data
            
        return response
    
    @staticmethod
    def handle_database_error(e: Exception) -> Tuple[Dict[str, Any], int]:
        """处理数据库错误
        
        Args:
            e: 异常对象
            
        Returns:
            Tuple[Dict[str, Any], int]: (错误响应, HTTP状态码)
        """
        error_str = str(e).lower()
        
        if "unique constraint failed" in error_str:
            return ErrorHandler.create_error_response(ErrorCode.VAL_010, str(e), 409)
        elif "foreign key constraint failed" in error_str:
            return ErrorHandler.create_error_response(ErrorCode.BIZ_008, "关联数据不存在", 400)
        elif "not null constraint failed" in error_str:
            return ErrorHandler.create_error_response(ErrorCode.VAL_001, "必填字段为空", 400)
        elif "database is locked" in error_str:
            return ErrorHandler.create_error_response(ErrorCode.SYS_002, "数据库繁忙，请稍后重试", 503)
        else:
            return ErrorHandler.create_error_response(ErrorCode.SYS_002, "数据库操作失败", 500)
    
    @staticmethod
    def handle_validation_error(field: str, value: Any = None, error_type: str = "required") -> Tuple[Dict[str, Any], int]:
        """处理验证错误
        
        Args:
            field: 字段名
            value: 字段值
            error_type: 错误类型 (required, format, length, range)
            
        Returns:
            Tuple[Dict[str, Any], int]: (错误响应, HTTP状态码)
        """
        details = f"字段: {field}"
        if value is not None:
            details += f", 值: {value}"
        
        error_map = {
            "required": ErrorCode.VAL_001,
            "format": ErrorCode.VAL_003,
            "length": ErrorCode.VAL_002,
            "range": ErrorCode.VAL_009,
            "type": ErrorCode.VAL_008
        }
        
        error_code = error_map.get(error_type, ErrorCode.VAL_003)
        return ErrorHandler.create_error_response(error_code, details, 400)
    
    @staticmethod
    def handle_permission_error(user_id: Optional[int] = None, resource: Optional[str] = None, action: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
        """处理权限错误
        
        Args:
            user_id: 用户ID
            resource: 资源名称
            action: 操作类型
            
        Returns:
            Tuple[Dict[str, Any], int]: (错误响应, HTTP状态码)
        """
        details_parts = []
        if user_id:
            details_parts.append(f"用户ID: {user_id}")
        if resource:
            details_parts.append(f"资源: {resource}")
        if action:
            details_parts.append(f"操作: {action}")
            
        details = ", ".join(details_parts) if details_parts else None
        return ErrorHandler.create_error_response(ErrorCode.SEC_002, details, 403)
    
    @staticmethod
    def handle_business_error(business_code: Tuple[str, str], context: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
        """处理业务逻辑错误
        
        Args:
            business_code: 业务错误码
            context: 上下文信息
            
        Returns:
            Tuple[Dict[str, Any], int]: (错误响应, HTTP状态码)
        """
        return ErrorHandler.create_error_response(business_code, context, 400)
    
    @staticmethod
    def handle_file_security_error(security_issue: str, filename: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
        """处理文件安全错误
        
        Args:
            security_issue: 安全问题描述
            filename: 文件名
            
        Returns:
            Tuple[Dict[str, Any], int]: (错误响应, HTTP状态码)
        """
        details = security_issue
        if filename:
            details = f"文件: {filename}, {security_issue}"
            
        if "大小超出限制" in security_issue:
            error_code = ErrorCode.SEC_005
        elif "类型不安全" in security_issue or "不支持的文件" in security_issue:
            error_code = ErrorCode.SEC_004
        else:
            error_code = ErrorCode.SYS_003
            
        return ErrorHandler.create_error_response(error_code, details, 400)
    
    @staticmethod
    def _get_log_level(error_code: str) -> int:
        """根据错误码确定日志级别
        
        Args:
            error_code: 错误码
            
        Returns:
            int: 日志级别
        """
        if error_code.startswith("SYS_"):
            return logging.ERROR
        elif error_code.startswith("SEC_"):
            return logging.WARNING
        elif error_code.startswith("BIZ_"):
            return logging.INFO
        else:  # VAL_
            return logging.DEBUG
    
    @staticmethod
    def _log_error(code: str, message: str, details: Optional[str], level: int) -> None:
        """记录错误日志
        
        Args:
            code: 错误码
            message: 错误消息
            details: 详细信息
            level: 日志级别
        """
        log_message = f"错误码: {code}, 消息: {message}"
        if details:
            log_message += f", 详情: {details}"
            
        logging.log(level, log_message)
    
    @staticmethod
    def _get_timestamp() -> str:
        """获取当前时间戳
        
        Returns:
            str: ISO格式的时间戳
        """
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'

class ErrorResponseHelper:
    """错误响应辅助类 - 用于Flask视图函数"""
    
    @staticmethod
    def json_error_response(error_code: Tuple[str, str], details: str = None, http_status: int = 400):
        """返回JSON格式错误响应
        
        Args:
            error_code: 错误码元组
            details: 详细信息
            http_status: HTTP状态码
            
        Returns:
            Flask响应对象
        """
        response_data, status = ErrorHandler.create_error_response(error_code, details, http_status)
        return jsonify(response_data), status
    
    @staticmethod
    def flash_error_message(error_code: Tuple[str, str], details: str = None):
        """Flash错误消息到页面
        
        Args:
            error_code: 错误码元组
            details: 详细信息
        """
        from flask import flash
        
        code, message = error_code
        flash_msg = message
        if details:
            flash_msg += f": {details}"
            
        flash(flash_msg, 'error')
        
        # 记录到日志
        level = ErrorHandler._get_log_level(code)
        ErrorHandler._log_error(code, message, details, level)

# 常用错误快速访问
class CommonErrors:
    """常用错误快速访问"""
    
    # 用户相关
    LOGIN_REQUIRED = ErrorCode.SEC_001
    PERMISSION_DENIED = ErrorCode.SEC_002
    
    # 数据验证
    REQUIRED_FIELD = ErrorCode.VAL_001
    INVALID_FORMAT = ErrorCode.VAL_003
    
    # 业务逻辑
    ORDER_NOT_FOUND = ErrorCode.BIZ_001
    SUPPLIER_NOT_FOUND = ErrorCode.BIZ_002
    
    # 系统错误
    DATABASE_ERROR = ErrorCode.SYS_002
    SERVICE_UNAVAILABLE = ErrorCode.SYS_005