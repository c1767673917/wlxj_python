# 备份管理器 v2.0 使用说明

## 概述

这是一个全面重构的数据库备份管理系统，提供了增强的错误处理、配置管理、监控功能和生产就绪的特性。

## 主要改进

### 1. 代码质量提升
- 使用具体异常类型替换通用Exception
- 外部化配置项，支持环境变量覆盖
- 改进日志配置的健壮性
- 增强权限检查的可靠性

### 2. 测试覆盖完善
- 完整的单元测试套件
- 边界条件和异常情况测试
- 并发操作测试
- 特殊字符和大文件处理测试

### 3. 监控和健康检查
- 实时健康状态监控
- REST API端点
- 系统状态报告
- 磁盘空间监控

### 4. 生产就绪特性
- 线程安全的操作
- 超时控制
- 配置验证
- 完整的错误处理

## 快速开始

### 基本使用

```python
from scripts.backup.backup_manager import BackupManager

# 创建备份管理器
backup_manager = BackupManager()

# 创建备份
backup_path, message = backup_manager.create_backup()
if backup_path:
    print(f"备份成功: {message}")
else:
    print(f"备份失败: {message}")

# 列出备份
backups = backup_manager.list_backups()
for backup in backups:
    print(f"{backup['filename']} - {backup['size']} bytes")

# 获取健康状态
health = backup_manager.get_health_status()
print(f"系统状态: {health['overall_status']}")
```

### 配置管理

```python
from config.backup_config import BackupConfig

# 使用自定义配置
config = BackupConfig('config/backup_config.json')
backup_manager = BackupManager(config=config)

# 或使用环境变量
import os
os.environ['BACKUP_KEEP_DAYS'] = '14'
os.environ['BACKUP_COMPRESS'] = 'true'

backup_manager = BackupManager()  # 自动读取环境变量
```

### 命令行使用

```bash
# 创建备份
python -m scripts.backup.backup_manager --create

# 列出备份
python -m scripts.backup.backup_manager --list

# 清理旧备份（保留3天）
python -m scripts.backup.backup_manager --cleanup --keep-days 3

# 验证备份
python -m scripts.backup.backup_manager --verify backup_file.db.gz

# 查看健康状态
python -m scripts.backup.backup_manager --health

# 查看统计信息
python -m scripts.backup.backup_manager --stats
```

### 健康检查API

启动健康检查服务器：

```bash
python scripts/backup/backup_health_api.py --host 0.0.0.0 --port 5001
```

API端点：

- `GET /api/backup/health` - 获取系统健康状态
- `GET /api/backup/stats` - 获取备份统计信息
- `GET /api/backup/list` - 列出所有备份
- `POST /api/backup/create` - 创建新备份
- `GET /api/backup/verify/<filename>` - 验证备份文件
- `POST /api/backup/cleanup` - 清理旧备份
- `GET /api/backup/config` - 获取配置信息
- `GET /ping` - 存活检查

## 配置选项

### 基本配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `keep_days` | 7 | 备份保留天数 |
| `max_backup_files` | 50 | 最大备份文件数 |
| `backup_dir` | "backup" | 备份目录 |
| `compress_backups` | true | 是否压缩备份 |

### 高级配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `chunk_size` | 65536 | 文件操作块大小（字节）|
| `max_backup_size_mb` | 1024 | 最大备份文件大小（MB）|
| `health_check_interval` | 300 | 健康检查间隔（秒）|
| `backup_schedule_hour` | 2 | 定时备份时间（小时）|

### 环境变量

所有配置都可以通过环境变量覆盖：

```bash
export BACKUP_KEEP_DAYS=14
export BACKUP_COMPRESS=true
export BACKUP_LOG_LEVEL=DEBUG
export BACKUP_MAX_SIZE_MB=2048
```

## 异常处理

系统使用具体的异常类型来处理不同的错误情况：

- `DatabaseNotFoundException` - 数据库文件不存在
- `DatabaseAccessException` - 数据库访问权限问题
- `DatabaseCorruptedException` - 数据库文件损坏
- `BackupDirectoryException` - 备份目录相关错误
- `BackupCreationException` - 备份创建失败
- `BackupVerificationException` - 备份验证失败
- `BackupTimeoutException` - 操作超时

## 监控指标

健康检查系统监控以下指标：

### 数据库健康
- 文件存在性
- 访问权限
- 文件大小
- 数据库完整性

### 备份目录健康
- 目录存在性
- 写权限
- 备份文件统计
- 总大小

### 最近备份状态
- 最新备份时间
- 备份文件数量
- 备份完整性

### 系统资源
- 磁盘空间使用
- 可用空间
- 使用率警告

## 集成指南

### Flask应用集成

```python
from flask import Flask
from scripts.backup.backup_health_api import BackupHealthAPI
from scripts.backup.backup_manager import BackupManager

app = Flask(__name__)
backup_manager = BackupManager()

# 集成健康检查API
health_api = BackupHealthAPI(app, backup_manager)

# 定时备份任务
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=backup_manager.create_backup,
    trigger="cron",
    hour=2,  # 每天凌晨2点
    id='daily_backup'
)
scheduler.start()
```

### Docker部署

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5001/ping || exit 1

# 启动健康检查服务
CMD ["python", "scripts/backup/backup_health_api.py", "--host", "0.0.0.0"]
```

## 故障排除

### 常见问题

1. **权限不足**
   ```
   确保备份目录有写权限
   检查数据库文件的读权限
   ```

2. **磁盘空间不足**
   ```
   检查磁盘可用空间
   清理旧备份文件
   调整备份保留策略
   ```

3. **备份验证失败**
   ```
   检查备份文件完整性
   验证压缩文件是否损坏
   重新创建备份
   ```

### 日志调试

```bash
# 设置调试日志级别
export BACKUP_LOG_LEVEL=DEBUG

# 查看详细日志
tail -f logs/backup.log
```

## 性能优化

### 大文件处理
- 使用分块读写（默认64KB）
- 启用压缩以节省空间
- 配置合适的超时时间

### 存储优化
- 定期清理旧备份
- 使用压缩备份
- 监控磁盘使用情况

### 网络部署
- 使用反向代理
- 配置适当的超时设置
- 启用健康检查

## 许可证

本项目遵循 MIT 许可证。