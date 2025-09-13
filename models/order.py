from datetime import datetime
import logging
import time
import threading
import uuid
from . import db

# 订单供应商关联表 - 添加级联删除
order_suppliers = db.Table('order_suppliers',
    db.Column('order_id', db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), primary_key=True),
    db.Column('supplier_id', db.Integer, db.ForeignKey('suppliers.id', ondelete='CASCADE'), primary_key=True),
    db.Column('notified', db.Boolean, default=False)
)

class Order(db.Model):
    __tablename__ = 'orders'
    
    # 类级别的Quote模型缓存，支持延迟加载和异常处理
    _quote_model_cache = None
    _quote_import_lock = threading.Lock()
    _cache_stats = {'hits': 0, 'misses': 0, 'import_time': None}
    
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False)
    warehouse = db.Column(db.String(200), nullable=False)
    goods = db.Column(db.Text, nullable=False)
    delivery_address = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    selected_supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    selected_price = db.Column(db.Numeric(10, 2), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)  # 创建者
    business_type = db.Column(db.String(20), nullable=False, default='oil')  # 业务类型
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系 - 添加级联删除
    quotes = db.relationship('Quote', backref='order', lazy=True, cascade='all, delete-orphan')
    selected_supplier = db.relationship('Supplier', foreign_keys=[selected_supplier_id])
    suppliers = db.relationship('Supplier', secondary=order_suppliers, backref='orders')
    
    def __repr__(self):
        return f'<Order {self.order_no}>'
    
    @classmethod
    def _get_quote_model(cls):
        """
        获取Quote模型类的缓存方法
        使用双重检查锁定模式确保线程安全和性能
        包含性能监控和统计信息
        """
        # 缓存命中，直接返回
        if cls._quote_model_cache is not None:
            cls._cache_stats['hits'] += 1
            return cls._quote_model_cache
        
        # 缓存未命中，需要导入
        cls._cache_stats['misses'] += 1
        
        with cls._quote_import_lock:
            # 双重检查，避免重复导入
            if cls._quote_model_cache is None:
                import_start_time = time.time()
                try:
                    from .quote import Quote
                    cls._quote_model_cache = Quote
                    cls._cache_stats['import_time'] = time.time() - import_start_time
                    logging.info(f"Quote模型已成功导入并缓存，耗时: {cls._cache_stats['import_time']:.4f}秒")
                    logging.debug(f"缓存统计 - 命中: {cls._cache_stats['hits']}, 未命中: {cls._cache_stats['misses']}")
                except ImportError as e:
                    logging.error(f"Quote模型导入失败: {str(e)}")
                    raise ImportError(f"无法导入Quote模型: {str(e)}")
                except Exception as e:
                    logging.error(f"Quote模型导入时发生未知错误: {str(e)}")
                    raise RuntimeError(f"Quote模型导入异常: {str(e)}")
            else:
                # 其他线程已经完成导入
                cls._cache_stats['hits'] += 1
        
        return cls._quote_model_cache
    
    @classmethod
    def get_cache_stats(cls):
        """获取缓存统计信息"""
        total_requests = cls._cache_stats['hits'] + cls._cache_stats['misses']
        hit_rate = (cls._cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hits': cls._cache_stats['hits'],
            'cache_misses': cls._cache_stats['misses'],
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2),
            'import_time_seconds': cls._cache_stats['import_time'],
            'is_cached': cls._quote_model_cache is not None
        }
    
    @classmethod
    def reset_cache_stats(cls):
        """重置缓存统计信息（用于测试）"""
        cls._cache_stats = {'hits': 0, 'misses': 0, 'import_time': None}
        logging.info("Quote模型缓存统计信息已重置")
    
    def generate_order_no(self):
        """生成订单号 - RX+yymmdd+3位数流水号格式"""
        if not self.id:
            raise ValueError("订单ID不能为空，请先保存订单")
        
        from datetime import datetime
        from sqlalchemy import func, and_
        
        # 获取当前日期
        now = datetime.now()
        date_str = now.strftime('%y%m%d')
        
        # 查询当天的所有订单号，使用LIKE模式匹配
        date_pattern = f'RX{date_str}%'
        today_orders = Order.query.filter(
            Order.order_no.like(date_pattern)
        ).all()
        
        # 过滤出符合格式的订单号并找到最大流水号
        max_seq = 0
        expected_length = 11  # RX + 6位日期 + 3位流水号
        
        for order in today_orders:
            if (len(order.order_no) == expected_length and 
                order.order_no.startswith(f'RX{date_str}') and
                order.order_no[-3:].isdigit()):
                try:
                    seq = int(order.order_no[-3:])
                    max_seq = max(max_seq, seq)
                except ValueError:
                    continue
        
        # 计算新的流水号
        new_seq = max_seq + 1
        
        # 确保流水号不超过999
        if new_seq > 999:
            raise ValueError(f"当日订单数量已达上限999个")
        
        return f'RX{date_str}{new_seq:03d}'
    
    @staticmethod
    def generate_temp_order_no():
        """生成临时订单号（用于初始化）- 使用新的RX格式但带TEMP前缀"""
        from datetime import datetime
        import uuid
        
        timestamp = datetime.now().strftime('%y%m%d')
        # 使用UUID确保唯一性，但保持格式一致性
        unique_suffix = str(uuid.uuid4())[:3].upper()
        return f'TEMP{timestamp}{unique_suffix}'
    
    def get_lowest_quote(self):
        """
        获取最低报价
        优先使用relationship关系，提升性能并减少数据库查询
        """
        try:
            # 优先使用已建立的relationship关系
            if hasattr(self, 'quotes') and self.quotes:
                # 在内存中排序，避免额外数据库查询
                return min(self.quotes, key=lambda q: q.price) if self.quotes else None
            
            # 备用方案：使用缓存的Quote模型进行查询
            Quote = self._get_quote_model()
            return Quote.query.filter_by(order_id=self.id).order_by(Quote.price.asc()).first()
            
        except Exception as e:
            logging.error(f"获取最低报价时发生错误 (订单ID: {self.id}): {str(e)}")
            return None
    
    def get_quote_count(self):
        """
        获取报价数量
        优先使用relationship关系，提升性能
        """
        try:
            # 优先使用已建立的relationship关系
            if hasattr(self, 'quotes'):
                return len(self.quotes) if self.quotes else 0
            
            # 备用方案：使用缓存的Quote模型进行查询
            Quote = self._get_quote_model()
            return Quote.query.filter_by(order_id=self.id).count()
            
        except Exception as e:
            logging.error(f"获取报价数量时发生错误 (订单ID: {self.id}): {str(e)}")
            return 0
    
    def get_quotes_summary(self):
        """
        获取报价摘要信息
        返回包含最低价格、报价数量等信息的字典
        """
        try:
            quotes_count = self.get_quote_count()
            lowest_quote = self.get_lowest_quote()
            
            summary = {
                'total_count': quotes_count,
                'lowest_price': lowest_quote.price if lowest_quote else None,
                'lowest_quote_id': lowest_quote.id if lowest_quote else None,
                'has_quotes': quotes_count > 0,
                'supplier_count': len(set(q.supplier_id for q in self.quotes)) if self.quotes else 0
            }
            
            logging.debug(f"订单 {self.id} 报价摘要: {summary}")
            return summary
            
        except Exception as e:
            logging.error(f"获取订单报价摘要时发生错误 (订单ID: {self.id}): {str(e)}")
            return {
                'total_count': 0,
                'lowest_price': None,
                'lowest_quote_id': None,
                'has_quotes': False,
                'supplier_count': 0
            }
    
    @staticmethod
    def generate_unique_order_no(max_retries=5):
        """生成唯一订单号（带重试机制）- 使用RX+yymmdd+3位数流水号格式"""
        from datetime import datetime
        from sqlalchemy import func, and_
        import time
        import logging
        
        for attempt in range(max_retries):
            try:
                # 获取当前日期
                now = datetime.now()
                date_str = now.strftime('%y%m%d')
                
                # 查询当天的所有订单号，使用LIKE模式匹配
                date_pattern = f'RX{date_str}%'
                today_orders = Order.query.filter(
                    Order.order_no.like(date_pattern)
                ).all()
                
                # 过滤出符合格式的订单号并找到最大流水号
                max_seq = 0
                expected_length = 11  # RX + 6位日期 + 3位流水号
                
                for order in today_orders:
                    if (len(order.order_no) == expected_length and 
                        order.order_no.startswith(f'RX{date_str}') and
                        order.order_no[-3:].isdigit()):
                        try:
                            seq = int(order.order_no[-3:])
                            max_seq = max(max_seq, seq)
                        except ValueError:
                            continue
                
                # 计算新的流水号
                new_seq = max_seq + 1
                
                # 确保流水号不超过999
                if new_seq > 999:
                    raise ValueError(f"当日订单数量已达上限999个")
                
                order_no = f'RX{date_str}{new_seq:03d}'
                
                # 检查唯一性
                existing = Order.query.filter_by(order_no=order_no).first()
                if not existing:
                    return order_no
                    
                # 如果重复，等待短暂时间后重试
                time.sleep(0.001 * (attempt + 1))  # 递增等待时间
                
            except Exception as e:
                logging.error(f"生成订单号失败，尝试 {attempt + 1}/{max_retries}: {str(e)}")
                if attempt == max_retries - 1:
                    raise Exception(f"生成唯一订单号失败，已重试 {max_retries} 次")
                time.sleep(0.01 * (attempt + 1))
        
        raise Exception("生成唯一订单号失败")
    
    def validate_order_data(self):
        """验证订单数据"""
        errors = []
        
        if not self.warehouse or len(self.warehouse.strip()) == 0:
            errors.append("仓库信息不能为空")
        elif len(self.warehouse) > 200:
            errors.append("仓库信息长度不能超过200字符")
            
        if not self.goods or len(self.goods.strip()) == 0:
            errors.append("货物信息不能为空")
            
        if not self.delivery_address or len(self.delivery_address.strip()) == 0:
            errors.append("收货地址不能为空")
        elif len(self.delivery_address) > 300:
            errors.append("收货地址长度不能超过300字符")
            
        if not self.user_id:
            errors.append("用户ID不能为空")
            
        return errors

    def reset_to_active(self):
        """将已完成的订单重新激活为进行中状态"""
        if self.status != 'completed':
            raise ValueError("只能重新激活已完成的订单")
        
        if not self.selected_supplier_id:
            raise ValueError("订单没有选择供应商，无法重新激活")
        
        # 清除选中的供应商和价格
        self.selected_supplier_id = None
        self.selected_price = None
        self.status = 'active'
        
        logging.info(f"订单 {self.order_no} 已重新激活为进行中状态")
        
        return True
