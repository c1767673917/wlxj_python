# 代码风格和约定

## 编程语言
- **Python 3.8+**
- 使用UTF-8编码
- 中文注释和文档字符串

## 命名规范
- **类名**: 使用PascalCase (如: `User`, `Supplier`, `Order`)
- **函数/方法名**: 使用snake_case (如: `get_lowest_quote`, `generate_order_no`)
- **变量名**: 使用snake_case (如: `user_id`, `access_code`)
- **常量**: 使用UPPER_CASE (如: `SECRET_KEY`, `DATABASE_URL`)
- **表名**: 使用复数形式 (如: `users`, `suppliers`, `orders`, `quotes`)

## 数据库约定
- 使用SQLAlchemy ORM
- 表名使用`__tablename__`明确指定
- 主键统一使用`id`字段，类型为`Integer`
- 外键命名格式: `{表名}_id` (如: `user_id`, `supplier_id`)
- 时间字段统一使用`created_at`，默认值为`datetime.utcnow`
- 关联关系使用`db.relationship`定义

## 模型结构模式
```python
class ModelName(db.Model):
    __tablename__ = 'table_name'
    
    # 字段定义
    id = db.Column(db.Integer, primary_key=True)
    # ... 其他字段
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    related_objects = db.relationship('RelatedModel', backref='model_name', lazy=True)
    
    def __repr__(self):
        return f'<ModelName {self.name}>'
```

## 注释和文档
- 使用中文注释
- 重要方法使用文档字符串说明功能
- 复杂逻辑添加行内注释
- 模型字段使用注释说明用途

## 错误处理
- 使用try-except处理异常
- 记录详细的错误日志
- 为关键方法提供降级方案
- 使用logging模块记录信息

## 代码组织
- 按功能模块组织代码
- 路由处理器使用Blueprint组织
- 数据模型独立文件存放
- 配置集中在config.py中管理

## 性能优化模式
- 使用缓存机制减少数据库查询
- 优先使用relationship关系而非重复查询
- 实现线程安全的单例模式
- 添加性能监控和统计