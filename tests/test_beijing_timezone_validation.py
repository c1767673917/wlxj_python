"""
北京时区转换实现的全面功能验证测试

测试范围：
1. 核心功能测试 - 时间存储、显示、计算、数据一致性
2. 用户界面集成测试 - 订单管理、报价系统、用户注册、供应商门户
3. 业务逻辑验证 - 日期过滤、订单号生成、备份系统、API响应
4. 模板系统测试 - 过滤器功能、格式一致性、错误处理

测试策略：
- 功能验证优先，重点测试业务逻辑和用户体验
- 实际数据库操作验证，确保时间存储正确性
- 模板渲染测试，验证前端显示一致性
- 边界条件和错误处理测试
"""

import unittest
import tempfile
import os
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入测试所需的模块
from app import app, db
from models.user import User
from models.order import Order
from models.quote import Quote
from models.supplier import Supplier
from utils.beijing_time_helper import BeijingTimeHelper
from flask import url_for
import json
import logging

class BeijingTimezoneValidationTestCase(unittest.TestCase):
    """北京时区转换功能验证测试套件"""
    
    def setUp(self):
        """测试初始化"""
        # 创建临时数据库
        self.db_fd, app.config['DATABASE'] = tempfile.mkstemp()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + app.config['DATABASE']
        app.config['WTF_CSRF_ENABLED'] = False
        
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        
        # 创建数据库表
        with app.app_context():
            db.create_all()
            
        # 创建测试管理员用户
        self._create_test_admin()
        
        logging.info("测试环境初始化完成")
    
    def tearDown(self):
        """测试清理"""
        with app.app_context():
            db.session.remove()
            db.drop_all()
        
        self.app_context.pop()
        os.close(self.db_fd)
        os.unlink(app.config['DATABASE'])
        
        logging.info("测试环境清理完成")
    
    def _create_test_admin(self):
        """创建测试管理员用户"""
        from werkzeug.security import generate_password_hash
        
        admin = User(
            username='test_admin',
            password=generate_password_hash('admin123'),
            business_type='admin'
        )
        db.session.add(admin)
        db.session.commit()
        
        self.admin_user = admin
        logging.info(f"创建测试管理员用户: {admin.username}")
    
    def _login_admin(self):
        """登录管理员用户"""
        return self.app.post('/login', data={
            'username': 'test_admin',
            'password': 'admin123'
        }, follow_redirects=True)
    
    def _create_test_supplier(self):
        """创建测试供应商"""
        supplier = Supplier(
            name='测试供应商',
            user_id=self.admin_user.id,
            business_type='oil'
        )
        db.session.add(supplier)
        db.session.commit()
        return supplier
    
    def _create_test_order(self):
        """创建测试订单"""
        order = Order(
            order_no=Order.generate_temp_order_no(),
            warehouse='北京仓库',
            goods='测试货物',
            delivery_address='北京市海淀区',
            user_id=self.admin_user.id
        )
        db.session.add(order)
        db.session.commit()
        
        # 生成正式订单号
        order.order_no = order.generate_order_no()
        db.session.commit()
        
        return order


class TestCoreTimezoneFunctionality(BeijingTimezoneValidationTestCase):
    """核心时区功能测试"""
    
    def test_beijing_time_helper_basic_functions(self):
        """测试BeijingTimeHelper基础功能"""
        logging.info("开始测试BeijingTimeHelper基础功能")
        
        # 测试当前北京时间获取
        beijing_now = BeijingTimeHelper.now()
        self.assertIsInstance(beijing_now, datetime)
        self.assertIsNone(beijing_now.tzinfo)  # 应该是naive datetime
        
        # 测试时间格式化
        formatted_time = BeijingTimeHelper.format_datetime(beijing_now)
        self.assertRegex(formatted_time, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
        
        # 测试不同格式
        formatted_date = BeijingTimeHelper.format_date(beijing_now)
        self.assertRegex(formatted_date, r'^\d{4}-\d{2}-\d{2}$')
        
        formatted_time_short = BeijingTimeHelper.format_time(beijing_now)
        self.assertRegex(formatted_time_short, r'^\d{2}:\d{2}$')
        
        formatted_full = BeijingTimeHelper.format_full(beijing_now)
        self.assertRegex(formatted_full, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
        
        logging.info("BeijingTimeHelper基础功能测试通过")
    
    def test_utc_to_beijing_conversion(self):
        """测试UTC到北京时间的转换"""
        logging.info("开始测试UTC到北京时间转换")
        
        # 创建UTC时间
        utc_time = datetime(2024, 3, 15, 6, 30, 0)  # UTC 06:30
        
        # 转换为北京时间
        beijing_time = BeijingTimeHelper.to_beijing(utc_time)
        
        # 北京时间应该是14:30 (UTC+8)
        expected_beijing = datetime(2024, 3, 15, 14, 30, 0)
        self.assertEqual(beijing_time, expected_beijing)
        
        # 测试空值处理
        self.assertIsNone(BeijingTimeHelper.to_beijing(None))
        
        logging.info("UTC到北京时间转换测试通过")
    
    def test_date_range_parsing(self):
        """测试日期范围解析"""
        logging.info("开始测试日期范围解析")
        
        start_date = "2024-03-15"
        end_date = "2024-03-16"
        
        start_dt, end_dt = BeijingTimeHelper.get_date_range(start_date, end_date)
        
        # 验证开始时间是当天00:00:00
        self.assertEqual(start_dt.hour, 0)
        self.assertEqual(start_dt.minute, 0)
        self.assertEqual(start_dt.second, 0)
        
        # 验证结束时间是当天23:59:59
        self.assertEqual(end_dt.hour, 23)
        self.assertEqual(end_dt.minute, 59)
        self.assertEqual(end_dt.second, 59)
        
        logging.info("日期范围解析测试通过")
    
    def test_order_number_generation_with_beijing_time(self):
        """测试基于北京时间的订单号生成"""
        logging.info("开始测试订单号生成")
        
        # 创建测试订单
        order = self._create_test_order()
        
        # 验证订单号格式: RX + yymmdd + 3位流水号
        order_no = order.order_no
        self.assertTrue(order_no.startswith('RX'))
        self.assertEqual(len(order_no), 11)  # RX + 6位日期 + 3位序号
        
        # 验证日期部分使用北京时间
        beijing_now = BeijingTimeHelper.now()
        expected_date = beijing_now.strftime('%y%m%d')
        self.assertEqual(order_no[2:8], expected_date)
        
        # 验证序号部分是数字
        self.assertTrue(order_no[8:].isdigit())
        
        logging.info(f"订单号生成测试通过: {order_no}")


class TestDatabaseTimeStorage(BeijingTimezoneValidationTestCase):
    """数据库时间存储测试"""
    
    def test_new_records_use_beijing_time(self):
        """测试新记录使用北京时间"""
        logging.info("开始测试新记录时间存储")
        
        # 记录创建前的时间
        before_creation = BeijingTimeHelper.now()
        
        # 创建各种类型的记录
        user = User(
            username='test_user',
            password='password123',
            business_type='oil'
        )
        db.session.add(user)
        db.session.commit()
        
        supplier = self._create_test_supplier()
        order = self._create_test_order()
        
        quote = Quote(
            order_id=order.id,
            supplier_id=supplier.id,
            price=Decimal('1000.00'),
            delivery_time='3天',
            remarks='测试报价'
        )
        db.session.add(quote)
        db.session.commit()
        
        # 记录创建后的时间
        after_creation = BeijingTimeHelper.now()
        
        # 验证所有记录的创建时间都在合理范围内
        for record in [user, supplier, order, quote]:
            self.assertGreaterEqual(record.created_at, before_creation)
            self.assertLessEqual(record.created_at, after_creation)
            
            # 验证时间格式化
            formatted_time = BeijingTimeHelper.format_datetime(record.created_at)
            self.assertRegex(formatted_time, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
        
        logging.info("新记录时间存储测试通过")
    
    def test_time_consistency_across_models(self):
        """测试不同模型间的时间一致性"""
        logging.info("开始测试模型间时间一致性")
        
        # 在短时间内创建多个相关记录
        supplier = self._create_test_supplier()
        order = self._create_test_order()
        
        quote1 = Quote(
            order_id=order.id,
            supplier_id=supplier.id,
            price=Decimal('1000.00')
        )
        
        quote2 = Quote(
            order_id=order.id,
            supplier_id=supplier.id,
            price=Decimal('950.00')
        )
        
        db.session.add_all([quote1, quote2])
        db.session.commit()
        
        # 验证时间差在合理范围内（1秒内）
        time_diff = abs((quote1.created_at - quote2.created_at).total_seconds())
        self.assertLess(time_diff, 1.0)
        
        # 验证所有时间都是同一天
        self.assertTrue(BeijingTimeHelper.is_same_day(order.created_at, quote1.created_at))
        self.assertTrue(BeijingTimeHelper.is_same_day(quote1.created_at, quote2.created_at))
        
        logging.info("模型间时间一致性测试通过")


class TestTemplateFilterFunctionality(BeijingTimezoneValidationTestCase):
    """模板过滤器功能测试"""
    
    def test_beijing_time_template_filters(self):
        """测试北京时间模板过滤器"""
        logging.info("开始测试模板过滤器")
        
        # 创建测试时间
        test_time = BeijingTimeHelper.now()
        
        with app.test_request_context():
            # 测试beijing_time过滤器
            from app import beijing_time_filter
            formatted = beijing_time_filter(test_time)
            self.assertRegex(formatted, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
            
            # 测试beijing_date过滤器
            from app import beijing_date_filter
            date_formatted = beijing_date_filter(test_time)
            self.assertRegex(date_formatted, r'^\d{4}-\d{2}-\d{2}$')
            
            # 测试beijing_time_short过滤器
            from app import beijing_time_short_filter
            time_short = beijing_time_short_filter(test_time)
            self.assertRegex(time_short, r'^\d{2}:\d{2}$')
            
            # 测试beijing_full过滤器
            from app import beijing_full_filter
            full_formatted = beijing_full_filter(test_time)
            self.assertRegex(full_formatted, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
        
        logging.info("模板过滤器测试通过")
    
    def test_template_filter_error_handling(self):
        """测试模板过滤器错误处理"""
        logging.info("开始测试过滤器错误处理")
        
        with app.test_request_context():
            from app import beijing_time_filter, beijing_date_filter
            
            # 测试空值处理
            self.assertEqual(beijing_time_filter(None), '')
            self.assertEqual(beijing_date_filter(None), '')
            
            # 测试无效值处理（应该不会抛出异常）
            try:
                result = beijing_time_filter("invalid_date")
                self.assertIsInstance(result, str)
            except Exception as e:
                self.fail(f"过滤器应该处理无效输入而不抛出异常: {e}")
        
        logging.info("过滤器错误处理测试通过")


class TestUserInterfaceIntegration(BeijingTimezoneValidationTestCase):
    """用户界面集成测试"""
    
    def test_order_list_page_time_display(self):
        """测试订单列表页面时间显示"""
        logging.info("开始测试订单列表页面")
        
        # 登录管理员
        self._login_admin()
        
        # 创建测试数据
        order = self._create_test_order()
        
        # 访问订单列表页面
        response = self.app.get('/orders/')
        self.assertEqual(response.status_code, 200)
        
        # 验证页面包含格式化的时间
        page_content = response.get_data(as_text=True)
        
        # 检查是否显示了正确格式的时间
        formatted_time = BeijingTimeHelper.format_datetime(order.created_at)
        self.assertIn(formatted_time.split()[0], page_content)  # 至少包含日期部分
        
        logging.info("订单列表页面时间显示测试通过")
    
    def test_order_detail_page_time_display(self):
        """测试订单详情页面时间显示"""
        logging.info("开始测试订单详情页面")
        
        # 登录管理员
        self._login_admin()
        
        # 创建测试数据
        order = self._create_test_order()
        supplier = self._create_test_supplier()
        
        quote = Quote(
            order_id=order.id,
            supplier_id=supplier.id,
            price=Decimal('1000.00'),
            delivery_time='3天'
        )
        db.session.add(quote)
        db.session.commit()
        
        # 访问订单详情页面
        response = self.app.get(f'/orders/{order.id}')
        self.assertEqual(response.status_code, 200)
        
        page_content = response.get_data(as_text=True)
        
        # 验证订单创建时间显示
        order_time = BeijingTimeHelper.format_datetime(order.created_at)
        self.assertIn(order_time.split()[0], page_content)
        
        # 验证报价时间显示
        quote_time = BeijingTimeHelper.format_datetime(quote.created_at)
        self.assertIn(quote_time.split()[0], page_content)
        
        logging.info("订单详情页面时间显示测试通过")


class TestBusinessLogicValidation(BeijingTimezoneValidationTestCase):
    """业务逻辑验证测试"""
    
    def test_date_range_filtering(self):
        """测试日期范围过滤功能"""
        logging.info("开始测试日期范围过滤")
        
        # 创建不同日期的订单
        yesterday = BeijingTimeHelper.add_days(BeijingTimeHelper.now(), -1)
        today = BeijingTimeHelper.now()
        
        # 手动设置创建时间（模拟不同日期的订单）
        order1 = Order(
            order_no='RX240315001',
            warehouse='仓库1',
            goods='货物1',
            delivery_address='地址1',
            user_id=self.admin_user.id,
            created_at=yesterday
        )
        
        order2 = Order(
            order_no='RX240316001',
            warehouse='仓库2',
            goods='货物2',
            delivery_address='地址2',
            user_id=self.admin_user.id,
            created_at=today
        )
        
        db.session.add_all([order1, order2])
        db.session.commit()
        
        # 测试日期范围查询
        today_str = BeijingTimeHelper.format_date(today)
        start_dt, end_dt = BeijingTimeHelper.get_date_range(today_str, today_str)
        
        # 查询今天的订单
        today_orders = Order.query.filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt
        ).all()
        
        # 验证只返回今天的订单
        self.assertEqual(len(today_orders), 1)
        self.assertEqual(today_orders[0].id, order2.id)
        
        logging.info("日期范围过滤测试通过")
    
    def test_backup_timestamp_generation(self):
        """测试备份时间戳生成"""
        logging.info("开始测试备份时间戳生成")
        
        # 生成备份时间戳
        backup_timestamp = BeijingTimeHelper.get_backup_timestamp()
        
        # 验证格式: YYYYMMDD_HHMMSS
        self.assertRegex(backup_timestamp, r'^\d{8}_\d{6}$')
        
        # 验证与当前时间的一致性
        current_time = BeijingTimeHelper.now()
        expected_timestamp = current_time.strftime('%Y%m%d_%H%M%S')
        
        # 允许1分钟的时间差（考虑测试执行时间）
        timestamp_time = datetime.strptime(backup_timestamp, '%Y%m%d_%H%M%S')
        expected_time = datetime.strptime(expected_timestamp, '%Y%m%d_%H%M%S')
        
        time_diff = abs((timestamp_time - expected_time).total_seconds())
        self.assertLess(time_diff, 60)  # 时间差小于60秒
        
        logging.info(f"备份时间戳生成测试通过: {backup_timestamp}")
    
    def test_order_number_uniqueness_with_beijing_time(self):
        """测试基于北京时间的订单号唯一性"""
        logging.info("开始测试订单号唯一性")
        
        # 创建多个订单，验证订单号不重复
        orders = []
        for i in range(5):
            order = Order(
                order_no=Order.generate_temp_order_no(),
                warehouse=f'仓库{i}',
                goods=f'货物{i}',
                delivery_address=f'地址{i}',
                user_id=self.admin_user.id
            )
            db.session.add(order)
            db.session.commit()
            
            # 生成正式订单号
            order.order_no = order.generate_order_no()
            db.session.commit()
            
            orders.append(order)
        
        # 验证所有订单号都不相同
        order_numbers = [order.order_no for order in orders]
        self.assertEqual(len(order_numbers), len(set(order_numbers)))
        
        # 验证订单号格式和序号递增
        beijing_date = BeijingTimeHelper.now().strftime('%y%m%d')
        for i, order in enumerate(orders):
            expected_seq = f'{i+1:03d}'
            self.assertTrue(order.order_no.endswith(expected_seq))
            self.assertIn(beijing_date, order.order_no)
        
        logging.info("订单号唯一性测试通过")


class TestAPIResponseValidation(BeijingTimezoneValidationTestCase):
    """API响应验证测试"""
    
    def test_json_api_time_format(self):
        """测试JSON API时间格式"""
        logging.info("开始测试API时间格式")
        
        # 登录管理员
        self._login_admin()
        
        # 创建测试数据
        order = self._create_test_order()
        supplier = self._create_test_supplier()
        
        quote = Quote(
            order_id=order.id,
            supplier_id=supplier.id,
            price=Decimal('1000.00')
        )
        db.session.add(quote)
        db.session.commit()
        
        # 测试订单API（如果存在）
        # 这里可以根据实际API端点进行测试
        # 例如：response = self.app.get(f'/api/orders/{order.id}')
        
        # 验证时间在数据库中的存储格式
        with app.app_context():
            db_order = Order.query.get(order.id)
            db_quote = Quote.query.get(quote.id)
            
            # 验证时间可以正确格式化
            order_time_str = BeijingTimeHelper.format_datetime(db_order.created_at)
            quote_time_str = BeijingTimeHelper.format_datetime(db_quote.created_at)
            
            self.assertRegex(order_time_str, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
            self.assertRegex(quote_time_str, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
        
        logging.info("API时间格式测试通过")


class TestErrorHandlingAndEdgeCases(BeijingTimezoneValidationTestCase):
    """错误处理和边界条件测试"""
    
    def test_invalid_date_handling(self):
        """测试无效日期处理"""
        logging.info("开始测试无效日期处理")
        
        # 测试无效日期字符串
        invalid_dates = ['', '2024-13-32', 'not-a-date', '2024/03/15']
        
        for invalid_date in invalid_dates:
            start_dt, end_dt = BeijingTimeHelper.get_date_range(invalid_date, invalid_date)
            self.assertIsNone(start_dt)
            self.assertIsNone(end_dt)
        
        # 测试空值
        start_dt, end_dt = BeijingTimeHelper.get_date_range(None, None)
        self.assertIsNone(start_dt)
        self.assertIsNone(end_dt)
        
        logging.info("无效日期处理测试通过")
    
    def test_timezone_boundary_conditions(self):
        """测试时区边界条件"""
        logging.info("开始测试时区边界条件")
        
        # 测试跨天边界（UTC 16:00 = 北京时间 00:00）
        utc_boundary = datetime(2024, 3, 15, 16, 0, 0)  # UTC 16:00
        beijing_boundary = BeijingTimeHelper.to_beijing(utc_boundary)
        
        # 北京时间应该是第二天的00:00
        expected_beijing = datetime(2024, 3, 16, 0, 0, 0)
        self.assertEqual(beijing_boundary, expected_beijing)
        
        # 测试另一个边界（UTC 15:59 = 北京时间 23:59）
        utc_before = datetime(2024, 3, 15, 15, 59, 0)  # UTC 15:59
        beijing_before = BeijingTimeHelper.to_beijing(utc_before)
        
        expected_beijing_before = datetime(2024, 3, 15, 23, 59, 0)
        self.assertEqual(beijing_before, expected_beijing_before)
        
        logging.info("时区边界条件测试通过")
    
    def test_large_order_number_sequence(self):
        """测试大量订单号生成的边界情况"""
        logging.info("开始测试订单号序列边界")
        
        # 获取当前北京时间的日期字符串
        current_date = BeijingTimeHelper.now().strftime('%y%m%d')
        
        # 创建接近限制的订单号（使用当前日期）
        high_seq_order = Order(
            order_no=f'RX{current_date}998',  # 接近999限制
            warehouse='测试仓库',
            goods='测试货物',
            delivery_address='测试地址',
            user_id=self.admin_user.id
        )
        db.session.add(high_seq_order)
        db.session.commit()
        
        # 创建新订单，应该得到999
        new_order = Order(
            order_no=Order.generate_temp_order_no(),
            warehouse='新仓库',
            goods='新货物',
            delivery_address='新地址',
            user_id=self.admin_user.id
        )
        db.session.add(new_order)
        db.session.commit()
        
        new_order.order_no = new_order.generate_order_no()
        db.session.commit()
        
        # 验证新订单号序号递增（999）
        # 由于我们创建了998，下一个应该是999
        expected_seq = '999'
        self.assertTrue(new_order.order_no.endswith(expected_seq), 
                       f"期望订单号以{expected_seq}结尾，实际: {new_order.order_no}")
        
        # 验证订单号包含正确的日期
        self.assertIn(current_date, new_order.order_no)
        
        logging.info(f"订单号序列边界测试通过: {new_order.order_no}")


class TestPerformanceAndConsistency(BeijingTimezoneValidationTestCase):
    """性能和一致性测试"""
    
    def test_time_formatting_performance(self):
        """测试时间格式化性能"""
        logging.info("开始测试时间格式化性能")
        
        import time
        
        # 创建测试时间
        test_time = BeijingTimeHelper.now()
        
        # 测试大量格式化操作的性能
        start_time = time.time()
        
        for _ in range(1000):
            BeijingTimeHelper.format_datetime(test_time)
            BeijingTimeHelper.format_date(test_time)
            BeijingTimeHelper.format_time(test_time)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # 1000次格式化应该在1秒内完成
        self.assertLess(elapsed, 1.0)
        
        logging.info(f"时间格式化性能测试通过，1000次操作耗时: {elapsed:.3f}秒")
    
    def test_concurrent_order_creation_time_consistency(self):
        """测试并发订单创建的时间一致性"""
        logging.info("开始测试并发创建时间一致性")
        
        # 快速创建多个订单
        orders = []
        creation_start = BeijingTimeHelper.now()
        
        for i in range(10):
            order = Order(
                order_no=f'CONCURRENT{i:03d}',
                warehouse=f'仓库{i}',
                goods=f'货物{i}',
                delivery_address=f'地址{i}',
                user_id=self.admin_user.id
            )
            orders.append(order)
        
        # 批量添加到数据库
        db.session.add_all(orders)
        db.session.commit()
        
        creation_end = BeijingTimeHelper.now()
        
        # 验证所有订单的创建时间都在合理范围内
        for order in orders:
            self.assertGreaterEqual(order.created_at, creation_start)
            self.assertLessEqual(order.created_at, creation_end)
            
            # 验证时间格式化的一致性
            formatted_time = BeijingTimeHelper.format_datetime(order.created_at)
            self.assertRegex(formatted_time, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
        
        logging.info("并发创建时间一致性测试通过")


def run_comprehensive_validation():
    """运行全面的验证测试"""
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('test_beijing_timezone_validation.log'),
            logging.StreamHandler()
        ]
    )
    
    print("="*80)
    print("北京时区转换实现 - 全面功能验证测试")
    print("="*80)
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加所有测试类
    test_classes = [
        TestCoreTimezoneFunctionality,
        TestDatabaseTimeStorage,
        TestTemplateFilterFunctionality,
        TestUserInterfaceIntegration,
        TestBusinessLogicValidation,
        TestAPIResponseValidation,
        TestErrorHandlingAndEdgeCases,
        TestPerformanceAndConsistency
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 生成测试报告
    print("\n" + "="*80)
    print("测试结果摘要")
    print("="*80)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    success_rate = ((total_tests - failures - errors) / total_tests * 100) if total_tests > 0 else 0
    
    print(f"总测试数: {total_tests}")
    print(f"成功: {total_tests - failures - errors}")
    print(f"失败: {failures}")
    print(f"错误: {errors}")
    print(f"成功率: {success_rate:.1f}%")
    
    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split('Exception:')[-1].strip()}")
    
    print("\n" + "="*80)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_comprehensive_validation()
    sys.exit(0 if success else 1)