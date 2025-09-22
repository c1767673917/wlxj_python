from typing import Any, List, Optional, Tuple
from sqlalchemy.orm import Query
from models import Order, Quote, Supplier
from datetime import datetime, date, timedelta
import logging
import re
from utils.beijing_time_helper import BeijingTimeHelper

class QueryOptimizer:
    """查询优化工具类"""
    
    @staticmethod
    def apply_business_type_filter(query: Query, model_class: Any, user_business_type: str) -> Query:
        """应用业务类型筛选
        
        Args:
            query: SQLAlchemy查询对象
            model_class: 模型类
            user_business_type: 用户业务类型
            
        Returns:
            Query: 过滤后的查询对象
        """
        if user_business_type == 'admin':
            return query  # 管理员可查看所有数据
        return query.filter(model_class.business_type == user_business_type)
    
    @staticmethod
    def apply_pagination(query: Query, page: int, per_page: int = 10) -> Any:
        """应用分页
        
        Args:
            query: SQLAlchemy查询对象
            page: 页码
            per_page: 每页数量
            
        Returns:
            分页对象
        """
        return query.paginate(page=page, per_page=per_page, error_out=False)
    
    @staticmethod
    def get_order_with_quotes(order_id: int) -> Optional[Order]:
        """获取包含报价的订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            Optional[Order]: 订单对象，包含预加载的报价
        """
        from sqlalchemy.orm import joinedload
        return Order.query.options(
            joinedload(Order.quotes),
            joinedload(Order.selected_supplier)
        ).filter_by(id=order_id).first()
    
    @staticmethod
    def get_orders_with_stats(business_type: Optional[str] = None, limit: int = 100) -> List[Tuple[Order, dict]]:
        """获取订单及其统计信息
        
        Args:
            business_type: 业务类型筛选
            limit: 结果数量限制
            
        Returns:
            List[Tuple[Order, dict]]: 订单和统计信息的元组列表
        """
        from sqlalchemy import func
        
        query = Order.query
        if business_type and business_type != 'admin':
            query = query.filter(Order.business_type == business_type)
        
        orders = query.order_by(Order.created_at.desc()).limit(limit).all()
        results = []
        
        for order in orders:
            stats = {
                'quote_count': order.get_quote_count(),
                'lowest_quote': order.get_lowest_quote(),
                'supplier_count': len(order.suppliers)
            }
            results.append((order, stats))
        
        return results
    
    @staticmethod
    def get_supplier_performance_stats(supplier_id: int) -> dict:
        """获取供应商绩效统计
        
        Args:
            supplier_id: 供应商ID
            
        Returns:
            dict: 供应商绩效统计信息
        """
        from sqlalchemy import func
        
        # 总报价数
        total_quotes = Quote.query.filter_by(supplier_id=supplier_id).count()
        
        # 中标次数
        won_orders = Order.query.filter_by(selected_supplier_id=supplier_id).count()
        
        # 平均报价
        avg_price = Quote.query.filter_by(supplier_id=supplier_id).with_entities(
            func.avg(Quote.price)
        ).scalar() or 0
        
        # 中标率
        win_rate = (won_orders / total_quotes * 100) if total_quotes > 0 else 0
        
        return {
            'total_quotes': total_quotes,
            'won_orders': won_orders,
            'win_rate': round(win_rate, 2),
            'average_price': float(avg_price) if avg_price else 0.0
        }

class DateHelper:
    """日期处理工具类"""
    
    DATE_FORMAT = '%Y-%m-%d'
    DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
    
    @staticmethod
    def parse_date_range(start_date: str, end_date: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """解析日期范围
        
        Args:
            start_date: 开始日期字符串
            end_date: 结束日期字符串
            
        Returns:
            Tuple[Optional[datetime], Optional[datetime]]: 解析后的日期对象
        """
        start_dt = None
        end_dt = None
        
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, DateHelper.DATE_FORMAT)
            except ValueError:
                logging.warning(f"无效的开始日期格式: {start_date}")
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, DateHelper.DATE_FORMAT)
                # 设置为当天的最后一刻
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
            except ValueError:
                logging.warning(f"无效的结束日期格式: {end_date}")
        
        return start_dt, end_dt
    
    @staticmethod
    def get_quick_date_range(date_quick: str) -> Tuple[str, str]:
        """获取快捷日期范围
        
        Args:
            date_quick: 快捷日期选项
            
        Returns:
            Tuple[str, str]: (开始日期, 结束日期)
        """
        today = date.today()
        
        if date_quick == 'today':
            date_str = today.strftime(DateHelper.DATE_FORMAT)
            return date_str, date_str
        elif date_quick == 'this_week':
            # 本周一到今天
            week_start = today - timedelta(days=today.weekday())
            return week_start.strftime(DateHelper.DATE_FORMAT), today.strftime(DateHelper.DATE_FORMAT)
        elif date_quick == 'this_month':
            start = today.replace(day=1)
            return start.strftime(DateHelper.DATE_FORMAT), today.strftime(DateHelper.DATE_FORMAT)
        elif date_quick == 'last_7_days':
            start = today - timedelta(days=7)
            return start.strftime(DateHelper.DATE_FORMAT), today.strftime(DateHelper.DATE_FORMAT)
        elif date_quick == 'last_30_days':
            start = today - timedelta(days=30)
            return start.strftime(DateHelper.DATE_FORMAT), today.strftime(DateHelper.DATE_FORMAT)
        
        return '', ''
    
    @staticmethod
    def validate_date_format(date_str: str) -> Tuple[bool, str]:
        """验证日期格式
        
        Args:
            date_str: 日期字符串
            
        Returns:
            Tuple[bool, str]: (是否有效, 验证消息)
        """
        if not date_str:
            return True, ""  # 空字符串被认为是有效的（表示不筛选）
        
        # 正则表达式验证基本格式
        pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        if not pattern.match(date_str):
            return False, "日期格式应为YYYY-MM-DD"
        
        # 尝试解析日期
        try:
            parsed_date = datetime.strptime(date_str, DateHelper.DATE_FORMAT)
            
            # 验证日期合理性
            current_year = BeijingTimeHelper.now().year
            if parsed_date.year < 2020 or parsed_date.year > current_year + 1:
                return False, "日期年份超出有效范围（2020-明年）"
            
            return True, "日期格式有效"
            
        except ValueError as e:
            return False, f"无效日期: {str(e)}"
    
    @staticmethod
    def validate_date_range(start_date: str, end_date: str) -> Tuple[bool, str]:
        """验证日期范围
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Tuple[bool, str]: (是否有效, 验证消息)
        """
        # 验证单个日期格式
        if start_date:
            valid, msg = DateHelper.validate_date_format(start_date)
            if not valid:
                return False, f"开始日期{msg}"
        
        if end_date:
            valid, msg = DateHelper.validate_date_format(end_date)
            if not valid:
                return False, f"结束日期{msg}"
        
        # 验证日期范围逻辑
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, DateHelper.DATE_FORMAT)
                end_dt = datetime.strptime(end_date, DateHelper.DATE_FORMAT)
                
                if start_dt > end_dt:
                    return False, "开始日期不能大于结束日期"
                
                # 检查日期范围是否过大（超过2年）
                date_diff = end_dt - start_dt
                if date_diff.days > 730:
                    return False, "日期范围不能超过2年"
                
            except ValueError:
                return False, "日期解析失败"
        
        return True, "日期范围有效"
    
    @staticmethod
    def format_relative_time(dt: datetime) -> str:
        """格式化相对时间
        
        Args:
            dt: 日期时间对象
            
        Returns:
            str: 相对时间描述
        """
        now = BeijingTimeHelper.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours}小时前"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes}分钟前"
        else:
            return "刚刚"

class SearchHelper:
    """搜索优化工具类"""
    
    @staticmethod
    def sanitize_search_keyword(keyword: str) -> str:
        """清理搜索关键词
        
        Args:
            keyword: 原始关键词
            
        Returns:
            str: 清理后的关键词
        """
        if not keyword:
            return ""
        
        # 移除危险字符
        keyword = re.sub(r'[<>"\';]', '', keyword)
        
        # 限制长度
        if len(keyword) > 100:
            keyword = keyword[:100]
        
        return keyword.strip()
    
    @staticmethod
    def build_search_conditions(keyword: str, search_fields: List[str]) -> List:
        """构建搜索条件
        
        Args:
            keyword: 搜索关键词
            search_fields: 搜索字段列表
            
        Returns:
            List: SQLAlchemy查询条件列表
        """
        if not keyword or not search_fields:
            return []
        
        clean_keyword = SearchHelper.sanitize_search_keyword(keyword)
        if not clean_keyword:
            return []
        
        conditions = []
        for field in search_fields:
            conditions.append(field.ilike(f'%{clean_keyword}%'))
        
        return conditions
    
    @staticmethod
    def validate_search_params(keyword: str, page: int, per_page: int) -> Tuple[bool, str]:
        """验证搜索参数
        
        Args:
            keyword: 搜索关键词
            page: 页码
            per_page: 每页数量
            
        Returns:
            Tuple[bool, str]: (是否有效, 错误消息)
        """
        # 验证关键词长度
        if keyword and len(keyword) > 100:
            return False, "搜索关键词过长"
        
        # 验证页码
        if page < 1 or page > 1000:
            return False, "页码超出有效范围"
        
        # 验证每页数量
        if per_page < 1 or per_page > 100:
            return False, "每页数量超出有效范围"
        
        return True, ""

class FilterHelper:
    """筛选工具类"""
    
    @staticmethod
    def apply_status_filter(query: Query, model_class: Any, status: str) -> Query:
        """应用状态筛选
        
        Args:
            query: 查询对象
            model_class: 模型类
            status: 状态值
            
        Returns:
            Query: 筛选后的查询对象
        """
        valid_statuses = {'active', 'completed', 'cancelled'}
        if status and status in valid_statuses:
            return query.filter(model_class.status == status)
        return query
    
    @staticmethod
    def apply_date_filter(query: Query, model_class: Any, start_date: str, end_date: str) -> Query:
        """应用日期筛选
        
        Args:
            query: 查询对象
            model_class: 模型类
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Query: 筛选后的查询对象
        """
        start_dt, end_dt = DateHelper.parse_date_range(start_date, end_date)
        
        if start_dt:
            query = query.filter(model_class.created_at >= start_dt)
        
        if end_dt:
            query = query.filter(model_class.created_at <= end_dt)
        
        return query
    
    @staticmethod
    def get_filter_summary(filters: dict) -> str:
        """获取筛选条件摘要
        
        Args:
            filters: 筛选条件字典
            
        Returns:
            str: 筛选条件摘要
        """
        summary_parts = []
        
        if filters.get('status'):
            status_map = {'active': '进行中', 'completed': '已完成', 'cancelled': '已取消'}
            summary_parts.append(f"状态:{status_map.get(filters['status'], filters['status'])}")
        
        if filters.get('start_date') or filters.get('end_date'):
            date_part = "时间:"
            if filters.get('start_date'):
                date_part += filters['start_date']
            date_part += " 至 "
            if filters.get('end_date'):
                date_part += filters['end_date']
            else:
                date_part += "今天"
            summary_parts.append(date_part)
        
        if filters.get('keyword'):
            summary_parts.append(f"关键词:'{filters['keyword']}'")
        
        return " | ".join(summary_parts) if summary_parts else "无筛选条件"