# 供应商门户报价列表筛选功能技术规范

## Problem Statement
- **Business Issue**: 供应商门户缺乏报价列表筛选功能，供应商无法高效查找和管理自己的报价记录
- **Current State**: 现有`/portal/quotes`路由只显示简单的报价列表，无筛选、搜索、导出功能
- **Expected Outcome**: 供应商可以按订单状态、日期范围、关键词筛选报价，支持分页和Excel导出

## Solution Overview
- **Approach**: 在现有供应商门户基础上增强报价列表页面，复用用户端订单筛选的设计模式和代码逻辑
- **Core Changes**: 修改`/portal/quotes`路由处理逻辑，更新模板添加筛选组件，新增Excel导出功能
- **Success Criteria**: 筛选功能正常工作，响应速度<2秒，Excel导出包含所需字段，UI保持中文界面一致性

## Technical Implementation

### Database Changes
无需修改数据库表结构。使用现有表关联查询：
- **Quote表**: 报价信息 (`quotes`)
- **Order表**: 订单信息 (`orders`)  
- **Supplier表**: 供应商信息 (`suppliers`)

查询优化建议：
```sql
-- 为常用筛选字段添加索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_quotes_created_at ON quotes(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
```

### Code Changes

#### Files to Modify:

**1. `/routes/supplier_portal.py`**
- 修改`my_quotes()`函数，添加筛选逻辑
- 新增`export_quotes()`路由处理Excel导出
- 添加查询构建辅助函数

**2. `/templates/portal/quotes.html`**
- 在现有统计概览下方添加筛选表单
- 更新表格显示结构支持筛选结果
- 添加分页控件和Excel导出按钮

#### New Files:
无需创建新文件，所有功能集成到现有文件中。

#### Function Signatures:

```python
# routes/supplier_portal.py 新增/修改的函数
def my_quotes():
    """我的报价列表 - 支持筛选和分页"""
    
def export_quotes():
    """导出筛选后的报价Excel"""
    
def build_quotes_query(supplier_id, status=None, start_date=None, end_date=None, keyword=None):
    """构建报价查询条件"""
    
def apply_quote_filters(query, status, start_date, end_date, keyword):
    """应用报价筛选条件"""
```

### API Changes

#### Endpoints:
- **修改**: `GET /portal/quotes` - 添加筛选参数支持
- **新增**: `GET /portal/quotes/export` - Excel导出功能

#### Request/Response:

**GET /portal/quotes 参数:**
```
status: string (可选) - 订单状态 ('active', 'completed', 'cancelled')
start_date: string (可选) - 开始日期 (YYYY-MM-DD格式)
end_date: string (可选) - 结束日期 (YYYY-MM-DD格式)
keyword: string (可选) - 搜索关键词 (最长100字符)
page: int (可选) - 页码 (默认1)
per_page: int (可选) - 每页数量 (10/20/50, 默认10)
```

**GET /portal/quotes/export 参数:**
```
继承上述所有筛选参数，返回Excel文件流
```

#### Validation Rules:
- status: 枚举验证 ('active', 'completed', 'cancelled', '')
- start_date/end_date: 日期格式验证，结束日期不能早于开始日期
- keyword: 长度限制100字符，过滤特殊字符
- page: 正整数，最大1000
- per_page: 枚举值 (10, 20, 50)

### Configuration Changes
无需修改配置文件，使用现有设置。

### Implementation Sequence

#### Phase 1: 后端筛选逻辑实现
具体任务：
1. 修改 `/routes/supplier_portal.py` 中的 `my_quotes()` 函数
2. 添加查询构建辅助函数 `build_quotes_query()` 和 `apply_quote_filters()`
3. 实现分页逻辑，参考 `/routes/order.py` 中的模式
4. 添加参数验证和错误处理

#### Phase 2: Excel导出功能
具体任务：
1. 在 `/routes/supplier_portal.py` 新增 `export_quotes()` 路由
2. 实现Excel生成逻辑，使用openpyxl库
3. 设置响应头支持文件下载
4. 包含字段：订单号、货物信息、收货地址、仓库、报价、创建时间

#### Phase 3: 前端界面更新
具体任务：
1. 修改 `/templates/portal/quotes.html` 添加筛选表单
2. 复用 `/templates/orders/index.html` 的筛选UI组件结构
3. 添加分页控件和导出按钮
4. 实现JavaScript筛选逻辑和AJAX交互
5. 保持中文界面和现有样式一致性

## Validation Plan

### Unit Tests
- **筛选查询逻辑测试**: 
  - 测试各筛选条件的SQL查询构建正确性
  - 边界值测试（空参数、无效日期、超长关键词）
  - 供应商权限隔离测试

- **Excel导出功能测试**:
  - 导出文件格式正确性
  - 筛选结果与导出数据一致性
  - 大数据量导出性能测试

### Integration Tests  
- **端到端筛选工作流测试**:
  - 访问`/portal/quotes`页面，应用各种筛选条件
  - 验证分页功能正常工作
  - 测试快捷日期选择功能

- **供应商会话权限测试**:
  - 验证只能查看自己的报价数据
  - 测试会话过期处理
  - 跨供应商数据泄露防护

### Business Logic Verification
- **筛选结果准确性验证**:
  - 手动创建测试数据，验证各筛选条件返回正确结果
  - 关键词搜索覆盖订单号、货物信息、地址、仓库等字段
  - 日期范围筛选精确匹配

- **用户体验验证**:
  - 响应时间<2秒
  - 筛选状态保持（表单回填）
  - 错误提示清晰明确
  - 移动端响应式适配

## 具体实现细节

### 查询构建逻辑
```python
def build_quotes_query(supplier_id, status=None, start_date=None, end_date=None, keyword=None):
    """构建报价查询 - 连接Order表进行筛选"""
    query = Quote.query.join(Order).filter(Quote.supplier_id == supplier_id)
    
    # 状态筛选
    if status:
        query = query.filter(Order.status == status)
    
    # 日期筛选
    if start_date:
        query = query.filter(Order.created_at >= start_date)
    if end_date:
        query = query.filter(Order.created_at <= end_date)
    
    # 关键词搜索 - 多字段模糊匹配
    if keyword:
        search_pattern = f"%{keyword}%"
        query = query.filter(or_(
            Order.order_no.like(search_pattern),
            Order.goods.like(search_pattern),
            Order.delivery_address.like(search_pattern),
            Order.warehouse.like(search_pattern)
        ))
    
    return query.order_by(Quote.created_at.desc())
```

### Excel导出字段映射
```python
excel_columns = [
    ('订单号', lambda q: q.order.order_no),
    ('货物信息', lambda q: q.order.goods),
    ('收货地址', lambda q: q.order.delivery_address),
    ('仓库', lambda q: q.order.warehouse),
    ('报价', lambda q: f'¥{q.price:.2f}'),
    ('创建时间', lambda q: q.created_at.strftime('%Y-%m-%d %H:%M'))
]
```

### 前端筛选表单结构
```html
<form method="GET" id="quoteFilterForm">
  <div class="row g-3">
    <div class="col-md-3">
      <select name="status" class="form-select">
        <option value="">全部状态</option>
        <option value="active">待报价/进行中</option>
        <option value="completed">已成交</option>
        <option value="cancelled">已取消</option>
      </select>
    </div>
    <div class="col-md-4">
      <input type="date" name="start_date" class="form-control">
      <input type="date" name="end_date" class="form-control">
    </div>
    <div class="col-md-5">
      <input type="text" name="keyword" class="form-control" 
             placeholder="订单号/仓库/地址/货物信息">
    </div>
  </div>
</form>
```

此技术规范提供了完整的实现蓝图，可直接用于代码生成和开发实施。