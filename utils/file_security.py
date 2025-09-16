import os
import logging
from functools import wraps
from typing import Tuple, Set

class FileSecurity:
    """文件安全验证工具类"""
    
    # 文件大小限制 (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    # 允许的文件类型 - 只允许Excel和CSV文件
    ALLOWED_MIME_TYPES = {
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
        'application/vnd.ms-excel',  # .xls
        'text/csv',  # .csv
        'text/plain',  # .csv可能被识别为text/plain
    }
    
    ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv'}
    
    @classmethod
    def validate_file_size(cls, file_size: int) -> Tuple[bool, str]:
        """验证文件大小
        
        Args:
            file_size: 文件字节大小
            
        Returns:
            Tuple[bool, str]: (是否通过验证, 验证消息)
        """
        if file_size > cls.MAX_FILE_SIZE:
            max_mb = cls.MAX_FILE_SIZE // 1024 // 1024
            actual_mb = file_size / 1024 / 1024
            return False, f"文件大小超过限制(最大{max_mb}MB，实际{actual_mb:.1f}MB)"
        return True, "文件大小验证通过"
    
    @classmethod
    def validate_file_type(cls, file_path: str) -> Tuple[bool, str]:
        """验证文件类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            Tuple[bool, str]: (是否通过验证, 验证消息)
        """
        try:
            # 获取文件扩展名
            _, ext = os.path.splitext(file_path.lower())
            if ext not in cls.ALLOWED_EXTENSIONS:
                allowed_exts = ', '.join(cls.ALLOWED_EXTENSIONS)
                return False, f"不支持的文件扩展名: {ext}，仅支持: {allowed_exts}"
            
            # 基础文件头检查（不依赖python-magic）
            if not cls._check_file_header(file_path, ext):
                return False, f"文件内容与扩展名不匹配"
            
            return True, "文件类型验证通过"
            
        except Exception as e:
            logging.error(f"文件类型验证失败: {str(e)}")
            return False, f"文件验证失败: {str(e)}"
    
    @classmethod
    def _check_file_header(cls, file_path: str, ext: str) -> bool:
        """检查文件头部魔数
        
        Args:
            file_path: 文件路径
            ext: 文件扩展名
            
        Returns:
            bool: 文件头部是否匹配扩展名
        """
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)
            
            if ext == '.xlsx':
                # XLSX文件以PK开头（ZIP格式）
                return header.startswith(b'PK')
            elif ext == '.xls':
                # XLS文件的魔数
                return (header.startswith(b'\xd0\xcf\x11\xe0') or  # OLE2格式
                       header.startswith(b'\x09\x08\x06\x00'))    # BIFF格式
            elif ext == '.csv':
                # CSV文件通常是纯文本，检查是否包含常见的CSV特征
                try:
                    content = header.decode('utf-8', errors='ignore')
                    # 简单检查：不包含二进制控制字符
                    return all(ord(c) >= 32 or c in '\t\n\r' for c in content)
                except:
                    return False
            
            return True
            
        except Exception as e:
            logging.error(f"文件头部检查失败: {str(e)}")
            return False
    
    @classmethod
    def validate_file_name(cls, filename: str) -> Tuple[bool, str]:
        """验证文件名安全性
        
        Args:
            filename: 文件名
            
        Returns:
            Tuple[bool, str]: (是否安全, 验证消息)
        """
        if not filename or len(filename.strip()) == 0:
            return False, "文件名不能为空"
        
        # 文件名长度限制
        if len(filename) > 255:
            return False, "文件名过长（最大255字符）"
        
        # 危险字符检查
        dangerous_chars = {'<', '>', ':', '"', '|', '?', '*', '\0'}
        if any(char in filename for char in dangerous_chars):
            return False, "文件名包含不安全字符"
        
        # 路径遍历检查
        if '..' in filename or filename.startswith('/') or '\\' in filename:
            return False, "文件名包含路径遍历字符"
        
        return True, "文件名验证通过"
    
    @classmethod
    def validate_export_file(cls, file_path: str) -> Tuple[bool, str]:
        """验证导出文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            Tuple[bool, str]: (是否通过验证, 验证消息)
        """
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        try:
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            size_valid, size_msg = cls.validate_file_size(file_size)
            if not size_valid:
                return False, size_msg
            
            # 检查文件类型
            type_valid, type_msg = cls.validate_file_type(file_path)
            if not type_valid:
                return False, type_msg
            
            # 检查文件名
            filename = os.path.basename(file_path)
            name_valid, name_msg = cls.validate_file_name(filename)
            if not name_valid:
                return False, name_msg
            
            return True, "文件验证通过"
            
        except Exception as e:
            logging.error(f"文件验证过程出错: {str(e)}")
            return False, f"文件验证失败: {str(e)}"
    
    @classmethod
    def get_safe_filename(cls, filename: str) -> str:
        """生成安全的文件名
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 安全的文件名
        """
        if not filename:
            return "unknown_file"
        
        # 移除危险字符
        dangerous_chars = {'<', '>', ':', '"', '|', '?', '*', '\0', '\\', '/'}
        safe_name = ''.join(c if c not in dangerous_chars else '_' for c in filename)
        
        # 限制长度
        if len(safe_name) > 100:
            name, ext = os.path.splitext(safe_name)
            safe_name = name[:95] + ext
        
        # 确保不为空
        if not safe_name or safe_name in ('.', '..'):
            safe_name = "safe_file"
        
        return safe_name

def file_security_check(f):
    """文件安全检查装饰器
    
    用于装饰文件操作相关的视图函数，自动进行安全检查
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # 在函数执行前记录日志
            logging.debug(f"执行文件安全检查装饰器，函数: {f.__name__}")
            
            # 执行原函数
            result = f(*args, **kwargs)
            
            # 在函数执行后记录成功日志
            logging.debug(f"文件操作安全检查通过，函数: {f.__name__}")
            
            return result
            
        except Exception as e:
            logging.error(f"文件操作安全检查失败，函数: {f.__name__}, 错误: {str(e)}")
            raise
            
    return decorated_function

def validate_upload_file(file_obj) -> Tuple[bool, str]:
    """验证上传的文件对象
    
    Args:
        file_obj: Flask上传的文件对象
        
    Returns:
        Tuple[bool, str]: (是否安全, 验证消息)
    """
    try:
        # 检查文件对象
        if not file_obj or not hasattr(file_obj, 'filename'):
            return False, "无效的文件对象"
        
        # 检查是否有文件名
        if not file_obj.filename:
            return False, "未选择文件"
        
        # 验证文件名
        name_valid, name_msg = FileSecurity.validate_file_name(file_obj.filename)
        if not name_valid:
            return False, name_msg
        
        # 检查文件扩展名
        _, ext = os.path.splitext(file_obj.filename.lower())
        if ext not in FileSecurity.ALLOWED_EXTENSIONS:
            allowed = ', '.join(FileSecurity.ALLOWED_EXTENSIONS)
            return False, f"不支持的文件类型: {ext}，仅支持: {allowed}"
        
        return True, "文件上传验证通过"
        
    except Exception as e:
        logging.error(f"文件上传验证失败: {str(e)}")
        return False, f"文件验证失败: {str(e)}"