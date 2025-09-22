#!/usr/bin/env python3
"""
北京时区转换实现的功能验证测试脚本

简化版测试，专注于核心功能验证：
1. 时间存储和显示一致性
2. 模板过滤器正常工作
3. 订单号生成使用北京时间
4. 数据库时间存储正确性
"""

import sys
import os
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入项目模块
from app import app
from models import db
from models.user import User
from models.order import Order
from models.quote import Quote
from models.supplier import Supplier
from utils.beijing_time_helper import BeijingTimeHelper
from werkzeug.security import generate_password_hash

def setup_test_environment():
    """设置测试环境"""
    print("设置测试环境...")
    
    # 创建临时数据库
    db_fd, app.config['DATABASE'] = tempfile.mkstemp()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + app.config['DATABASE']
    app.config['WTF_CSRF_ENABLED'] = False
    
    app_context = app.app_context()
    app_context.push()
    
    # 创建数据库表
    db.create_all()
    
    # 创建测试用户
    admin = User(
        username='test_admin',
        password=generate_password_hash('admin123'),
        business_type='admin'
    )
    db.session.add(admin)
    db.session.commit()
    
    print("✓ 测试环境设置完成")
    return db_fd, app_context, admin

def cleanup_test_environment(db_fd, app_context):
    """清理测试环境"""
    db.session.remove()
    db.drop_all()
    app_context.pop()
    os.close(db_fd)
    os.unlink(app.config['DATABASE'])
    print("✓ 测试环境清理完成")

def test_beijing_time_helper_core_functions():
    """测试北京时间助手核心功能"""
    print("\n1. 测试BeijingTimeHelper核心功能...")
    
    # 测试当前时间获取
    beijing_now = BeijingTimeHelper.now()
    assert isinstance(beijing_now, datetime), "应该返回datetime对象"
    assert beijing_now.tzinfo is None, "应该返回naive datetime"
    print("  ✓ 当前北京时间获取正常")
    
    # 测试时间格式化
    formatted = BeijingTimeHelper.format_datetime(beijing_now)
    assert len(formatted) == 16, f"格式化时间长度应该是16，实际: {len(formatted)}"
    assert ' ' in formatted, "格式化时间应该包含空格"
    print(f"  ✓ 时间格式化正常: {formatted}")
    
    # 测试不同格式
    date_only = BeijingTimeHelper.format_date(beijing_now)
    time_only = BeijingTimeHelper.format_time(beijing_now)
    full_format = BeijingTimeHelper.format_full(beijing_now)
    
    assert len(date_only) == 10, "日期格式应该是10个字符"
    assert len(time_only) == 5, "时间格式应该是5个字符"
    assert len(full_format) == 19, "完整格式应该是19个字符"
    print(f"  ✓ 各种格式化正常: {date_only}, {time_only}, {full_format}")
    
    # 测试UTC转换
    utc_time = datetime(2024, 3, 15, 6, 30, 0)  # UTC 06:30
    beijing_time = BeijingTimeHelper.to_beijing(utc_time)
    expected = datetime(2024, 3, 15, 14, 30, 0)  # 北京时间 14:30
    assert beijing_time == expected, f"UTC转换错误，期望{expected}，实际{beijing_time}"
    print("  ✓ UTC到北京时间转换正常")

def test_model_time_storage(admin_user):
    """测试模型时间存储"""
    print("\n2. 测试数据库模型时间存储...")
    
    # 记录创建前的时间
    before_creation = BeijingTimeHelper.now()
    
    # 创建各种模型
    supplier = Supplier(
        name='测试供应商',
        user_id=admin_user.id,
        business_type='oil'
    )
    db.session.add(supplier)
    db.session.commit()
    
    order = Order(
        order_no=Order.generate_temp_order_no(),
        warehouse='北京仓库',
        goods='测试货物',
        delivery_address='北京市海淀区',
        user_id=admin_user.id
    )
    db.session.add(order)
    db.session.commit()
    
    quote = Quote(
        order_id=order.id,
        supplier_id=supplier.id,
        price=Decimal('1000.00'),
        delivery_time='3天'
    )
    db.session.add(quote)
    db.session.commit()
    
    # 记录创建后的时间
    after_creation = BeijingTimeHelper.now()
    
    # 验证时间范围
    for model_name, model in [('Supplier', supplier), ('Order', order), ('Quote', quote)]:
        assert model.created_at >= before_creation, f"{model_name}创建时间过早"
        assert model.created_at <= after_creation, f"{model_name}创建时间过晚"
        
        # 验证格式化
        formatted = BeijingTimeHelper.format_datetime(model.created_at)
        assert len(formatted) == 16, f"{model_name}时间格式化长度错误"
        print(f"  ✓ {model_name}时间存储正常: {formatted}")
    
    return supplier, order, quote

def test_order_number_generation():
    """测试订单号生成"""
    print("\n3. 测试订单号生成...")
    
    # 测试临时订单号
    temp_no = Order.generate_temp_order_no()
    assert temp_no.startswith('TEMP'), "临时订单号应该以TEMP开头"
    print(f"  ✓ 临时订单号生成正常: {temp_no}")
    
    # 测试日期字符串生成
    date_str = BeijingTimeHelper.get_order_date_string()
    assert len(date_str) == 6, "日期字符串应该是6位"
    assert date_str.isdigit(), "日期字符串应该全是数字"
    
    # 验证是今天的日期
    today = BeijingTimeHelper.now()
    expected_date = today.strftime('%y%m%d')
    assert date_str == expected_date, f"日期字符串错误，期望{expected_date}，实际{date_str}"
    print(f"  ✓ 订单日期字符串正常: {date_str}")

def test_template_filters():
    """测试模板过滤器"""
    print("\n4. 测试模板过滤器...")
    
    test_time = BeijingTimeHelper.now()
    
    with app.test_request_context():
        # 导入过滤器函数
        from app import beijing_time_filter, beijing_date_filter, beijing_time_short_filter, beijing_full_filter
        
        # 测试各个过滤器
        time_result = beijing_time_filter(test_time)
        date_result = beijing_date_filter(test_time)
        short_result = beijing_time_short_filter(test_time)
        full_result = beijing_full_filter(test_time)
        
        assert len(time_result) == 16, "beijing_time过滤器格式错误"
        assert len(date_result) == 10, "beijing_date过滤器格式错误"
        assert len(short_result) == 5, "beijing_time_short过滤器格式错误"
        assert len(full_result) == 19, "beijing_full过滤器格式错误"
        
        print(f"  ✓ beijing_time过滤器: {time_result}")
        print(f"  ✓ beijing_date过滤器: {date_result}")
        print(f"  ✓ beijing_time_short过滤器: {short_result}")
        print(f"  ✓ beijing_full过滤器: {full_result}")
        
        # 测试空值处理
        empty_result = beijing_time_filter(None)
        assert empty_result == '', "空值应该返回空字符串"
        print("  ✓ 空值处理正常")

def test_date_range_functionality():
    """测试日期范围功能"""
    print("\n5. 测试日期范围功能...")
    
    start_date = "2024-03-15"
    end_date = "2024-03-16"
    
    start_dt, end_dt = BeijingTimeHelper.get_date_range(start_date, end_date)
    
    # 验证开始时间
    assert start_dt.hour == 0, "开始时间应该是00:00:00"
    assert start_dt.minute == 0, "开始时间分钟应该是0"
    assert start_dt.second == 0, "开始时间秒数应该是0"
    
    # 验证结束时间
    assert end_dt.hour == 23, "结束时间应该是23:59:59"
    assert end_dt.minute == 59, "结束时间分钟应该是59"
    assert end_dt.second == 59, "结束时间秒数应该是59"
    
    print(f"  ✓ 日期范围解析正常: {start_dt} ~ {end_dt}")
    
    # 测试今天范围
    today_start, today_end = BeijingTimeHelper.get_today_range()
    assert today_start < today_end, "今天开始时间应该小于结束时间"
    assert today_start.hour == 0, "今天开始时间应该是00:00"
    print(f"  ✓ 今天范围获取正常: {today_start.strftime('%H:%M')} ~ {today_end.strftime('%H:%M')}")

def test_time_utility_functions():
    """测试时间工具函数"""
    print("\n6. 测试时间工具函数...")
    
    base_time = BeijingTimeHelper.now()
    
    # 测试增加小时
    added_hours = BeijingTimeHelper.add_hours(base_time, 2)
    expected_hours = base_time + timedelta(hours=2)
    assert added_hours == expected_hours, "增加小时功能错误"
    print("  ✓ 增加小时功能正常")
    
    # 测试增加天数
    added_days = BeijingTimeHelper.add_days(base_time, 1)
    expected_days = base_time + timedelta(days=1)
    assert added_days == expected_days, "增加天数功能错误"
    print("  ✓ 增加天数功能正常")
    
    # 测试同一天判断
    same_day = BeijingTimeHelper.is_same_day(base_time, added_hours)
    different_day = BeijingTimeHelper.is_same_day(base_time, added_days)
    assert same_day == True, "同一天判断错误"
    assert different_day == False, "不同天判断错误"
    print("  ✓ 同一天判断功能正常")
    
    # 测试备份时间戳
    backup_timestamp = BeijingTimeHelper.get_backup_timestamp()
    assert len(backup_timestamp) == 15, "备份时间戳长度错误"  # YYYYMMDD_HHMMSS
    assert '_' in backup_timestamp, "备份时间戳格式错误"
    print(f"  ✓ 备份时间戳生成正常: {backup_timestamp}")
    
    # 测试日志时间戳
    log_timestamp = BeijingTimeHelper.get_log_timestamp()
    assert len(log_timestamp) == 19, "日志时间戳长度错误"  # YYYY-MM-DD HH:MM:SS
    print(f"  ✓ 日志时间戳生成正常: {log_timestamp}")

def test_error_handling():
    """测试错误处理"""
    print("\n7. 测试错误处理...")
    
    # 测试空值处理
    result = BeijingTimeHelper.to_beijing(None)
    assert result is None, "空值转换应该返回None"
    print("  ✓ 空值转换处理正常")
    
    # 测试格式化空值
    result = BeijingTimeHelper.format_datetime(None)
    assert result == '', "空值格式化应该返回空字符串"
    print("  ✓ 空值格式化处理正常")
    
    # 测试无效日期范围
    start_dt, end_dt = BeijingTimeHelper.get_date_range('invalid', 'date')
    assert start_dt is None, "无效日期开始时间应该是None"
    assert end_dt is None, "无效日期结束时间应该是None"
    print("  ✓ 无效日期处理正常")

def run_functional_validation():
    """运行功能验证测试"""
    print("=" * 80)
    print("北京时区转换实现 - 功能验证测试")
    print("=" * 80)
    
    # 设置测试环境
    db_fd, app_context, admin_user = setup_test_environment()
    
    try:
        # 运行各项测试
        test_beijing_time_helper_core_functions()
        supplier, order, quote = test_model_time_storage(admin_user)
        test_order_number_generation()
        test_template_filters()
        test_date_range_functionality()
        test_time_utility_functions()
        test_error_handling()
        
        print("\n" + "=" * 80)
        print("✓ 所有功能验证测试通过！")
        print("=" * 80)
        
        # 显示测试创建的数据
        print("\n测试数据摘要:")
        print(f"- 供应商: {supplier.name} (创建时间: {BeijingTimeHelper.format_datetime(supplier.created_at)})")
        print(f"- 订单: {order.order_no} (创建时间: {BeijingTimeHelper.format_datetime(order.created_at)})")
        print(f"- 报价: ¥{quote.price} (创建时间: {BeijingTimeHelper.format_datetime(quote.created_at)})")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # 清理测试环境
        cleanup_test_environment(db_fd, app_context)

def main():
    """主函数"""
    success = run_functional_validation()
    
    if success:
        print("\n✅ 北京时区转换实现功能验证完成，所有核心功能正常工作！")
        print("\n核心验证点:")
        print("1. ✓ BeijingTimeHelper工具类功能正常")
        print("2. ✓ 数据库模型时间存储使用北京时间") 
        print("3. ✓ 订单号生成基于北京时间日期")
        print("4. ✓ 模板过滤器正确格式化时间显示")
        print("5. ✓ 日期范围查询功能正常")
        print("6. ✓ 时间工具函数工作正常")
        print("7. ✓ 错误处理机制健壮")
        
        print("\n🚀 建议:")
        print("- 实现已通过核心功能验证，可以部署到生产环境")
        print("- 时间显示格式统一为 'YYYY-MM-DD HH:MM' 格式")
        print("- 所有新数据都将使用北京时间存储")
        print("- 模板过滤器确保前端显示一致性")
        
        return 0
    else:
        print("\n❌ 功能验证失败，请检查实现并修复问题后重新测试")
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)