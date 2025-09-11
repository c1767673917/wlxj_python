from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# 导入所有模型
from .user import User
from .supplier import Supplier
from .order import Order, order_suppliers
from .quote import Quote