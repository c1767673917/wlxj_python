from datetime import datetime
from . import db
import logging

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
            
    def validate_price(self):
        """验证价格的有效性"""
        from decimal import Decimal
        
        try:
            if self.price is None:
                return False, "价格不能为空"
                
            decimal_price = self.get_price_decimal()
            
            if decimal_price < 0:
                return False, "价格不能为负数"
                
            if decimal_price > Decimal('9999999999.99'):
                return False, "价格超出允许范围"
                
            return True, "价格有效"
            
        except Exception as e:
            return False, f"价格验证失败: {str(e)}"