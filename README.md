# 瑞勋物流询价

一个基于Flask的B2B物流报价比较平台，支持多角色权限控制、实时报价比较、企业微信通知集成等完整业务流程。

## 功能特性

### 核心功能
- ✅ **用户认证系统** - 注册、登录、会话管理
- ✅ **供应商管理** - CRUD操作、专属访问码生成
- ✅ **订单管理** - 创建、列表、详情、供应商选择
- ✅ **供应商门户** - 免密访问、报价提交
- ✅ **报价对比** - 多维度对比分析、可视化展示
- ✅ **企业微信通知** - 自动通知新订单和报价
- ✅ **数据备份** - 自动备份、压缩存储、定时清理

### 技术特性
- 🏗️ **简单架构** - Flask单体应用，易于部署维护
- 🔒 **安全认证** - 密码哈希、会话管理、权限控制
- 📱 **响应式设计** - Bootstrap 5、移动端友好
- 💾 **SQLite数据库** - 零配置、文件存储、自动备份
- 🔔 **实时通知** - 企业微信Webhook集成

## 快速开始

### 1. 环境要求
- Python 3.8+
- 推荐使用虚拟环境

### 2. 安装依赖
```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 初始化数据库
```bash
python3 init_db.py
```

### 4. 运行应用
```bash
python3 app.py
```

访问 http://localhost:5000

### 5. 默认账户
- **管理员账户**: `admin` / `admin123`
- **测试账户**: `test` / `test123`

## 系统架构

### 目录结构
```
project/
├── app.py                     # Flask主应用
├── config.py                  # 配置文件
├── init_db.py                # 数据库初始化脚本
├── backup_manager.py         # 备份管理器
├── scheduled_backup.py       # 定时备份脚本
├── models/                   # 数据模型
│   ├── __init__.py
│   ├── user.py              # 用户模型
│   ├── supplier.py          # 供应商模型
│   ├── order.py             # 订单模型
│   └── quote.py             # 报价模型
├── routes/                   # 路由处理
│   ├── supplier.py          # 供应商路由
│   ├── order.py             # 订单路由
│   ├── quote.py             # 报价路由
│   ├── supplier_portal.py   # 供应商门户
│   └── admin.py             # 管理路由
├── templates/                # HTML模板
│   ├── base.html            # 基础模板
│   ├── login.html           # 登录页
│   ├── dashboard.html       # 仪表板
│   ├── suppliers/           # 供应商模板
│   ├── orders/              # 订单模板
│   ├── quotes/              # 报价模板
│   ├── portal/              # 供应商门户模板
│   └── admin/               # 管理模板
├── static/                   # 静态文件
├── backup/                   # 数据库备份目录
└── database.db              # SQLite数据库文件
```

### 数据模型

#### 用户表 (users)
- 用户认证信息
- 角色权限管理（user/admin）

#### 供应商表 (suppliers)
- 供应商基本信息
- 专属访问码
- 企业微信Webhook配置

#### 订单表 (orders)
- 订单详细信息
- 货物、仓库、配送地址
- 订单状态管理

#### 报价表 (quotes)
- 供应商报价信息
- 价格、交期、备注
- 关联订单和供应商

## 核心功能使用

### 1. 供应商管理
1. 登录系统后，点击"供应商管理"
2. 添加供应商信息
3. 系统自动生成专属访问码
4. 可配置企业微信Webhook用于自动通知

### 2. 创建询价订单
1. 点击"创建订单"
2. 填写货物信息、仓库、收货地址
3. 选择要询价的供应商
4. 系统自动发送通知给供应商

### 3. 供应商报价
1. 供应商通过专属链接访问系统
2. 查看订单详情
3. 提交报价（价格、交期、备注）
4. 可随时修改报价

### 4. 报价对比与选择
1. 在订单详情页查看所有报价
2. 使用报价对比功能分析不同报价
3. 选择最优供应商
4. 订单状态自动更新为已完成

## 企业微信集成

### 配置步骤
1. 在企业微信中创建群聊机器人
2. 获取Webhook URL
3. 在供应商管理中配置Webhook地址
4. 系统将自动发送以下通知：
   - 新订单通知（发送给供应商）
   - 新报价通知（发送给采购方）

### 通知内容
- 订单号、货物信息
- 仓库和收货地址
- 专属访问链接
- 操作提醒

## 数据备份

### 自动备份
系统提供完整的备份解决方案：

#### 手动备份
```bash
# 创建备份
python3 backup_manager.py --create

# 查看备份列表
python3 backup_manager.py --list

# 验证备份
python3 backup_manager.py --verify backup_file.db.gz

# 恢复备份
python3 backup_manager.py --restore backup_file.db.gz
```

#### 定时备份
```bash
# 设置定时任务（每天凌晨2点）
python3 setup_backup_cron.py

# 手动执行定时备份
python3 scheduled_backup.py
```

#### 备份特性
- 🗜️ **自动压缩** - 节省存储空间
- 🕒 **定时清理** - 自动删除7天前的备份
- ✅ **完整性验证** - 确保备份文件可用
- 📊 **统计信息** - 备份大小、数量统计
- 🔄 **一键恢复** - 支持快速恢复

### Web界面管理
管理员可通过Web界面进行备份管理：
- 创建新备份
- 下载备份文件
- 验证备份完整性
- 恢复备份
- 清理旧备份

## 部署说明

### 开发环境
```bash
python3 app.py
```
应用将运行在 http://localhost:5000

### 生产环境

#### 使用Gunicorn
```bash
# 安装Gunicorn
pip install gunicorn

# 运行应用
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

#### 使用Nginx反向代理
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /static {
        alias /path/to/your/project/static;
    }
}
```

## 配置说明

### 环境变量
- `SECRET_KEY`: Flask密钥（生产环境必须设置）
- `DATABASE_URL`: 数据库连接URL
- `WEWORK_WEBHOOK_URL`: 默认企业微信Webhook地址

### 配置文件
修改 `config.py` 中的配置：
- 数据库路径
- 备份保留天数
- Session超时时间

## API接口

### 供应商门户API
- `GET /supplier/<access_code>` - 供应商门户首页
- `GET /portal/order/<order_id>` - 订单详情
- `POST /portal/order/<order_id>/quote` - 提交报价

### 数据导出API
- `GET /quotes/export/<order_id>` - 导出订单报价数据

## 安全说明

### 安全特性
- 密码哈希存储（Werkzeug）
- 会话管理（Flask-Login）
- 供应商专属访问码
- 输入验证和SQL注入防护
- 定期访问码更新

### 安全建议
1. 定期更新供应商访问码
2. 使用HTTPS部署
3. 定期备份数据
4. 监控系统日志
5. 限制管理员权限

## 故障排除

### 常见问题

#### 1. 数据库初始化失败
```bash
# 删除现有数据库文件
rm database.db

# 重新初始化
python3 init_db.py
```

#### 2. 企业微信通知失败
- 检查Webhook URL是否正确
- 确认网络连接正常
- 查看系统日志

#### 3. 备份失败
```bash
# 检查磁盘空间
df -h

# 检查文件权限
ls -la database.db backup/

# 手动创建备份目录
mkdir -p backup
```

#### 4. 性能问题
- 定期清理旧数据
- 检查数据库文件大小
- 考虑迁移到PostgreSQL

## 开发说明

### 添加新功能
1. 在 `models/` 中定义数据模型
2. 在 `routes/` 中创建路由处理
3. 在 `templates/` 中创建HTML模板
4. 在 `app.py` 中注册蓝图

### 数据库迁移
由于使用SQLite，建议：
1. 备份现有数据
2. 修改模型定义
3. 重新初始化数据库
4. 导入必要数据

### 测试
```bash
# 创建测试数据
python3 init_db.py

# 添加测试供应商和订单
# 通过Web界面操作
```

## 更新日志

### v1.0.0 (2025-01-10)
- ✅ 完整的询价流程实现
- ✅ 供应商管理和门户
- ✅ 报价对比分析
- ✅ 企业微信通知集成
- ✅ 数据备份系统
- ✅ 响应式Web界面

## 技术栈

- **后端**: Python Flask
- **前端**: HTML5 + Bootstrap 5 + JavaScript
- **数据库**: SQLite
- **认证**: Flask-Login
- **通知**: 企业微信Webhook
- **部署**: Gunicorn + Nginx

## 许可证

MIT License

## 支持

如有问题或建议，请联系系统管理员。

---

**瑞勋物流询价** - 简化您的采购流程