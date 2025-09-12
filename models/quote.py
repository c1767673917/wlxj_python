from datetime import datetime
from . import db
import logging
from decimal import Decimal

class Quote(db.Model):
    __tablename__ = 'quotes'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id', ondelete='CASCADE'), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    delivery_time = db.Column(db.String(50), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Quote {self.id}: {self.price}>'
    
    def format_price(self):
        """格式化价格显示"""
        return f'¥{self.price:,.2f}'
    
    def get_price_decimal(self):
        """获取Decimal类型的价格，确保类型安全"""
        from decimal import Decimal, InvalidOperation
        import logging
        
        try:
            if self.price is None:
                logging.warning(f"Quote {self.id} has None price")
                return Decimal('0')
                
            if isinstance(self.price, Decimal):
                if not self.price.is_finite():
                    logging.error(f"Quote {self.id} has non-finite Decimal price: {self.price}")
                    return Decimal('0')
                return self.price
                
            # 转换其他类型
            return Decimal(str(self.price))
            
        except (InvalidOperation, ValueError) as e:
            logging.error(f"Failed to convert price to Decimal for Quote {self.id}: {e}")
            return Decimal('0')
            
    def get_price_float(self):
        """获取float类型的价格，用于模板显示和计算"""
        try:
            decimal_price = self.get_price_decimal()
            return float(decimal_price)
        except Exception as e:
            logging.error(f"Failed to convert price to float for Quote {self.id}: {e}")
            return 0.0
            
    def format_price_safe(self, currency='¥'):
        """安全的价格格式化方法"""
        try:
            price_float = self.get_price_float()
            return f"{currency}{price_float:,.2f}"
        except Exception as e:
            logging.error(f"Failed to format price for Quote {self.id}: {e}")
            return f"{currency}0.00"
            
    def get_price_change_info(self, new_price):
        """获取价格变动信息"""
        try:
            current_price = self.get_price_float()
            if current_price <= 0 or not new_price:
                return None
                
            diff = new_price - current_price
            diff_percent = (abs(diff) / current_price) * 100
            
            return {
                'original': current_price,
                'new': new_price,
                'diff': diff,
                'diff_percent': diff_percent,
                'is_increase': diff > 0,
                'is_significant': diff_percent > 20
            }
        except Exception as e:
            logging.error(f"Failed to calculate price change for Quote {self.id}: {e}")
            return None
            
    def validate_price(self):
        """验证价格的有效性"""
        from decimal import Decimal
        
        try:
            if self.price is None:
                return False, "价格不能为空"
                
            decimal_price = self.get_price_decimal()
            
            if decimal_price <= 0:
                return False, "价格必须大于0"
                
            if decimal_price > Decimal('9999999999.99'):
                return False, "价格超出允许范围"
                
            return True, "价格有效"
            
        except Exception as e:
            return False, f"价格验证失败: {str(e)}"
            
    @classmethod
    def validate_price_change(cls, original_price, new_price):
        """验证价格变动的合理性"""
        from decimal import Decimal
        
        warnings = []
        
        try:
            if original_price is None or new_price is None:
                return warnings
                
            if isinstance(original_price, (int, float)):
                original_price = Decimal(str(original_price))
            if isinstance(new_price, (int, float)):
                new_price = Decimal(str(new_price))
                
            if original_price <= 0 or new_price <= 0:
                return warnings
                
            # 计算变动幅度
            price_diff = abs(original_price - new_price)
            price_diff_percent = (price_diff / original_price) * 100
            
            # 大幅变动警告
            if price_diff_percent > 50:
                warnings.append(f'价格变动较大({price_diff_percent:.1f}%)，请确认是否正确')
            
            # 价格翻倍警告
            if new_price > original_price * 2:
                warnings.append('新报价是原报价的2倍以上，请仔细核对')
            
            # 价格过低警告
            if new_price < original_price / 2:
                warnings.append('新报价比原报价低50%以上，请确认盈利能力')
                
            # 异常高价警告
            if new_price > Decimal('1000000'):
                warnings.append('报价金额较高，请确认是否正确')
                
        except Exception as e:
            logging.error(f'价格变动验证失败: {e}')
            
        return warnings