# 技术栈

## 后端框架
- **Flask 2.3.3**: Web应用框架
- **Flask-SQLAlchemy 3.0.5**: ORM数据库操作
- **Flask-Login 0.6.3**: 用户认证和会话管理
- **Werkzeug 2.3.7**: 密码哈希和安全工具

## 数据库
- **SQLite**: 轻量级文件数据库

## 前端技术
- **HTML5 + Bootstrap 5**: 响应式界面
- **JavaScript**: 前端交互

## 外部集成
- **企业微信 Webhook**: 消息通知
- **requests 2.31.0**: HTTP请求处理

## 开发工具
- **python-dotenv 1.0.0**: 环境变量管理

## 项目结构
```
project/
├── app.py                  # Flask主应用
├── config.py               # 配置文件
├── init_db.py             # 数据库初始化脚本
├── models/                # 数据模型
│   ├── user.py           # 用户模型
│   ├── supplier.py       # 供应商模型
│   ├── order.py          # 订单模型
│   └── quote.py          # 报价模型
├── routes/                # 路由处理
│   ├── admin.py          # 管理路由
│   ├── supplier.py       # 供应商路由
│   ├── order.py          # 订单路由
│   ├── quote.py          # 报价路由
│   └── supplier_portal.py # 供应商门户
├── templates/             # HTML模板
└── static/               # 静态文件
```