# 建议的开发命令

## 环境搭建
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境 (macOS/Linux)
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 数据库管理
```bash
# 初始化数据库
python3 init_db.py

# 数据库位置
# SQLite数据库文件: database.db
```

## 应用运行
```bash
# 开发模式运行
python3 app.py

# 生产模式运行 (使用Gunicorn)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## 备份管理
```bash
# 手动创建备份
python3 backup_manager.py --create

# 查看备份列表
python3 backup_manager.py --list

# 验证备份
python3 backup_manager.py --verify backup_file.db.gz

# 恢复备份
python3 backup_manager.py --restore backup_file.db.gz

# 设置定时备份
python3 setup_backup_cron.py

# 手动执行定时备份
python3 scheduled_backup.py
```

## 测试和调试
```bash
# 查看应用日志
tail -f app.log

# 查看备份日志
tail -f backup.log

# 测试数据验证
python3 test_order_fixes.py
python3 test_decimal_fixes.py
```

## 系统工具命令 (macOS)
```bash
# 文件操作
ls -la          # 列出详细文件信息
find . -name    # 查找文件
grep -r         # 搜索文件内容

# 进程管理
lsof -i :5000   # 查看端口占用
kill -9 PID     # 终止进程

# 系统信息
df -h           # 查看磁盘使用情况
ps aux          # 查看进程列表
```

## 默认访问信息
- 应用地址: http://localhost:5000
- 管理员账户: admin / admin123
- 测试账户: test / test123