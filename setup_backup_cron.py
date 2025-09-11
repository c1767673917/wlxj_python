#!/usr/bin/env python3
"""
设置定时备份任务脚本
用于自动配置cron任务
"""

import os
import sys
from pathlib import Path

def setup_cron_job():
    """设置定时备份的cron任务"""
    current_dir = Path(__file__).parent.absolute()
    script_path = current_dir / 'scheduled_backup.py'
    log_path = current_dir / 'backup_cron.log'
    
    # 创建cron任务内容（每天凌晨2点执行）
    cron_entry = f"0 2 * * * cd {current_dir} && /usr/bin/python3 {script_path} >> {log_path} 2>&1"
    
    print("定时备份任务设置指南")
    print("=" * 50)
    print()
    print("1. 手动添加到crontab:")
    print("   执行命令: crontab -e")
    print("   添加以下行:")
    print(f"   {cron_entry}")
    print()
    print("2. 或者使用系统脚本（需要root权限）:")
    print(f"   echo '{cron_entry}' | sudo tee /etc/cron.d/trade-system-backup")
    print()
    print("3. 验证cron任务:")
    print("   crontab -l")
    print()
    print("4. 查看备份日志:")
    print(f"   tail -f {log_path}")
    print()
    print("备份说明:")
    print("- 每天凌晨2点自动执行备份")
    print("- 自动压缩备份文件")
    print("- 自动清理7天前的旧备份")
    print("- 备份文件保存在 backup/ 目录")
    print("- 执行日志保存在 backup_cron.log")

def create_backup_script():
    """创建可执行的备份脚本"""
    current_dir = Path(__file__).parent.absolute()
    script_path = current_dir / 'backup.sh'
    
    script_content = f"""#!/bin/bash
# 贸易询价系统自动备份脚本

cd {current_dir}

echo "开始执行备份任务 - $(date)"

# 执行Python备份脚本
/usr/bin/python3 scheduled_backup.py

# 检查执行结果
if [ $? -eq 0 ]; then
    echo "备份任务执行成功 - $(date)"
else
    echo "备份任务执行失败 - $(date)"
fi
"""
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # 设置执行权限
    os.chmod(script_path, 0o755)
    
    print(f"已创建备份脚本: {script_path}")
    print("可以使用以下cron条目:")
    print(f"0 2 * * * {script_path} >> {current_dir}/backup_cron.log 2>&1")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--create-script':
        create_backup_script()
    else:
        setup_cron_job()