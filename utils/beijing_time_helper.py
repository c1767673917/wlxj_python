from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
import logging

class BeijingTimeHelper:
    """北京时间处理工具类
    
    统一处理系统中的所有时间相关操作，确保时间显示的一致性。
    所有时间都转换为北京时间（UTC+8），格式化为 'YYYY-MM-DD HH:MM'。
    """
    
    # 北京时区定义 (UTC+8)
    BEIJING_TZ = timezone(timedelta(hours=8))
    UTC_TZ = timezone.utc
    
    # 默认时间格式
    DEFAULT_FORMAT = '%Y-%m-%d %H:%M'
    DATE_FORMAT = '%Y-%m-%d'
    TIME_FORMAT = '%H:%M'
    FULL_FORMAT = '%Y-%m-%d %H:%M:%S'
    
    @classmethod
    def now(cls) -> datetime:
        """获取当前北京时间（无时区信息）
        
        返回值用于数据库存储，保持与现有数据的兼容性。
        数据库中存储的是北京时间对应的时间戳。
        
        Returns:
            datetime: 当前北京时间（naive datetime对象）
        """
        beijing_time = datetime.now(cls.BEIJING_TZ)
        # 返回naive datetime以保持与现有数据库模式的兼容性
        return beijing_time.replace(tzinfo=None)
    
    @classmethod
    def utc_now(cls) -> datetime:
        """获取当前UTC时间（替代datetime.utcnow）
        
        提供与datetime.utcnow()相同的接口，但使用timezone-aware的实现。
        
        Returns:
            datetime: 当前UTC时间（naive datetime对象）
        """
        utc_time = datetime.now(cls.UTC_TZ)
        return utc_time.replace(tzinfo=None)
    
    @classmethod
    def to_beijing(cls, utc_dt: datetime) -> datetime:
        """将UTC时间转换为北京时间
        
        Args:
            utc_dt: UTC时间（可以是naive或aware datetime）
            
        Returns:
            datetime: 北京时间（naive datetime对象）
        """
        if utc_dt is None:
            return None
            
        # 如果是naive datetime，假设它是UTC时间
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=cls.UTC_TZ)
        
        # 转换到北京时区
        beijing_dt = utc_dt.astimezone(cls.BEIJING_TZ)
        
        # 返回naive datetime以保持与现有系统的兼容性
        return beijing_dt.replace(tzinfo=None)
    
    @classmethod
    def format_datetime(cls, dt: datetime, format_str: str = None) -> str:
        """格式化时间显示（统一格式）
        
        Args:
            dt: 要格式化的时间
            format_str: 格式化字符串，默认为 '%Y-%m-%d %H:%M'
            
        Returns:
            str: 格式化后的时间字符串
        """
        if dt is None:
            return ''
        
        if format_str is None:
            format_str = cls.DEFAULT_FORMAT
        
        try:
            # 假设传入的datetime是北京时间（与数据库存储一致）
            return dt.strftime(format_str)
        except Exception as e:
            logging.error(f"时间格式化失败: {e}")
            return str(dt)
    
    @classmethod
    def format_date(cls, dt: datetime) -> str:
        """格式化日期显示
        
        Args:
            dt: 要格式化的时间
            
        Returns:
            str: 格式化后的日期字符串（YYYY-MM-DD）
        """
        return cls.format_datetime(dt, cls.DATE_FORMAT)
    
    @classmethod
    def format_time(cls, dt: datetime) -> str:
        """格式化时间显示
        
        Args:
            dt: 要格式化的时间
            
        Returns:
            str: 格式化后的时间字符串（HH:MM）
        """
        return cls.format_datetime(dt, cls.TIME_FORMAT)
    
    @classmethod
    def format_full(cls, dt: datetime) -> str:
        """格式化完整时间显示
        
        Args:
            dt: 要格式化的时间
            
        Returns:
            str: 格式化后的完整时间字符串（YYYY-MM-DD HH:MM:SS）
        """
        return cls.format_datetime(dt, cls.FULL_FORMAT)
    
    @classmethod
    def get_date_range(cls, start_date: str, end_date: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """处理日期范围查询（转换为北京时间范围）
        
        Args:
            start_date: 开始日期字符串（YYYY-MM-DD格式）
            end_date: 结束日期字符串（YYYY-MM-DD格式）
            
        Returns:
            Tuple[Optional[datetime], Optional[datetime]]: 开始时间和结束时间
        """
        start_dt = None
        end_dt = None
        
        try:
            if start_date:
                start_dt = datetime.strptime(start_date, cls.DATE_FORMAT)
                # 设置为当天开始时间（00:00:00）
                start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                
            if end_date:
                end_dt = datetime.strptime(end_date, cls.DATE_FORMAT)
                # 设置为当天结束时间（23:59:59）
                end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                
        except ValueError as e:
            logging.error(f"日期范围解析失败: {e}")
            return None, None
            
        return start_dt, end_dt
    
    @classmethod
    def parse_datetime(cls, datetime_str: str, format_str: str = None) -> Optional[datetime]:
        """解析时间字符串为datetime对象
        
        Args:
            datetime_str: 时间字符串
            format_str: 解析格式，默认为 '%Y-%m-%d %H:%M'
            
        Returns:
            Optional[datetime]: 解析后的datetime对象，失败返回None
        """
        if not datetime_str:
            return None
            
        if format_str is None:
            format_str = cls.DEFAULT_FORMAT
            
        try:
            return datetime.strptime(datetime_str, format_str)
        except ValueError as e:
            logging.error(f"时间解析失败: {datetime_str}, 格式: {format_str}, 错误: {e}")
            return None
    
    @classmethod
    def get_today_range(cls) -> Tuple[datetime, datetime]:
        """获取今天的时间范围（北京时间）
        
        Returns:
            Tuple[datetime, datetime]: 今天的开始时间和结束时间
        """
        today = cls.now().date()
        start_time = datetime.combine(today, datetime.min.time())
        end_time = datetime.combine(today, datetime.max.time())
        return start_time, end_time
    
    @classmethod
    def get_order_date_string(cls, dt: datetime = None) -> str:
        """获取用于订单号生成的日期字符串
        
        Args:
            dt: 指定时间，如果为None则使用当前北京时间
            
        Returns:
            str: YYMMDD格式的日期字符串
        """
        if dt is None:
            dt = cls.now()
        return dt.strftime('%y%m%d')
    
    @classmethod
    def is_same_day(cls, dt1: datetime, dt2: datetime) -> bool:
        """判断两个时间是否为同一天（北京时间）
        
        Args:
            dt1: 第一个时间
            dt2: 第二个时间
            
        Returns:
            bool: 是否为同一天
        """
        if dt1 is None or dt2 is None:
            return False
        return dt1.date() == dt2.date()
    
    @classmethod
    def add_hours(cls, dt: datetime, hours: int) -> datetime:
        """给时间增加指定小时数
        
        Args:
            dt: 基础时间
            hours: 要增加的小时数
            
        Returns:
            datetime: 增加小时后的时间
        """
        if dt is None:
            return None
        return dt + timedelta(hours=hours)
    
    @classmethod
    def add_days(cls, dt: datetime, days: int) -> datetime:
        """给时间增加指定天数
        
        Args:
            dt: 基础时间
            days: 要增加的天数
            
        Returns:
            datetime: 增加天数后的时间
        """
        if dt is None:
            return None
        return dt + timedelta(days=days)
    
    @classmethod
    def get_backup_timestamp(cls) -> str:
        """获取用于备份文件命名的时间戳
        
        Returns:
            str: 备份时间戳（YYYYMMDD_HHMMSS格式）
        """
        now = cls.now()
        return now.strftime('%Y%m%d_%H%M%S')
    
    @classmethod
    def get_log_timestamp(cls) -> str:
        """获取用于日志记录的时间戳
        
        Returns:
            str: 日志时间戳（YYYY-MM-DD HH:MM:SS格式）
        """
        now = cls.now()
        return now.strftime('%Y-%m-%d %H:%M:%S')

# 为了保持向后兼容性，提供一些常用的便捷函数
def beijing_now():
    """获取当前北京时间的便捷函数"""
    return BeijingTimeHelper.now()

def format_beijing_time(dt, format_str='%Y-%m-%d %H:%M'):
    """格式化北京时间的便捷函数"""
    return BeijingTimeHelper.format_datetime(dt, format_str)

def beijing_today_range():
    """获取今天时间范围的便捷函数"""
    return BeijingTimeHelper.get_today_range()