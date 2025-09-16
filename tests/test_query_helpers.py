#!/usr/bin/env python3
"""
查询辅助工具测试
测试 utils/query_helpers.py 中的查询优化功能
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch

from app import app, db
from models import Order, Quote, Supplier, User
from utils.query_helpers import QueryOptimizer, DateHelper


class TestQueryOptimizer:
    """查询优化器测试"""
    
    @pytest.fixture
    def setup_test_data(self):
        """设置测试数据"""
        with app.app_context():
            db.create_all()
            
            # 创建测试用户
            admin_user = User(username='admin', password_hash='test', business_type='admin', access_code='admin123')
            oil_user = User(username='oil_user', password_hash='test', business_type='oil', access_code='oil123')
            fast_user = User(username='fast_user', password_hash='test', business_type='fast_moving', access_code='fast123')
            
            db.session.add_all([admin_user, oil_user, fast_user])
            db.session.commit()
            
            # 创建测试订单
            orders = []
            for i in range(15):
                order = Order(
                    order_no=f'QO{i:03d}',
                    warehouse=f'仓库{i}',
                    goods=f'商品{i}',
                    delivery_address=f'地址{i}',
                    user_id=oil_user.id if i % 2 == 0 else fast_user.id,
                    business_type='oil' if i % 2 == 0 else 'fast_moving'
                )
                orders.append(order)
                db.session.add(order)
            
            db.session.commit()
            
            # 创建测试供应商
            oil_supplier = Supplier(name='油脂供应商', user_id=oil_user.id, business_type='oil')
            fast_supplier = Supplier(name='快消供应商', user_id=fast_user.id, business_type='fast_moving')
            
            db.session.add_all([oil_supplier, fast_supplier])
            db.session.commit()
            
            # 创建测试报价
            for order in orders[:5]:
                quote = Quote(
                    order_id=order.id,
                    supplier_id=oil_supplier.id if order.business_type == 'oil' else fast_supplier.id,
                    price=100.0 + order.id * 10
                )
                db.session.add(quote)
            
            db.session.commit()
            
            yield {
                'admin_user': admin_user,
                'oil_user': oil_user,
                'fast_user': fast_user,
                'oil_supplier': oil_supplier,
                'fast_supplier': fast_supplier,
                'orders': orders
            }
            
            # 清理
            db.session.remove()
    
    def test_business_type_filter_admin(self, setup_test_data):
        """测试管理员业务类型过滤"""
        data = setup_test_data
        
        # 管理员查询 - 应该看到所有数据
        query = Order.query
        filtered_query = QueryOptimizer.apply_business_type_filter(
            query, Order, data['admin_user'].business_type
        )
        
        orders = filtered_query.all()
        assert len(orders) == 15, "管理员应该能看到所有订单"
        
        # 验证包含不同业务类型的订单
        oil_orders = [o for o in orders if o.business_type == 'oil']
        fast_orders = [o for o in orders if o.business_type == 'fast_moving']
        
        assert len(oil_orders) > 0, "应该包含油脂订单"
        assert len(fast_orders) > 0, "应该包含快消订单"
    
    def test_business_type_filter_regular_user(self, setup_test_data):
        """测试普通用户业务类型过滤"""
        data = setup_test_data
        
        # 油脂用户查询 - 只能看到油脂相关数据
        query = Order.query
        filtered_query = QueryOptimizer.apply_business_type_filter(
            query, Order, data['oil_user'].business_type
        )
        
        orders = filtered_query.all()
        oil_orders = [o for o in orders if o.business_type == 'oil']
        
        assert len(orders) == len(oil_orders), "油脂用户只应该看到油脂订单"
        assert all(o.business_type == 'oil' for o in orders), "所有订单都应该是油脂类型"
        
        # 快消用户查询 - 只能看到快消相关数据
        query = Order.query
        filtered_query = QueryOptimizer.apply_business_type_filter(
            query, Order, data['fast_user'].business_type
        )
        
        orders = filtered_query.all()
        fast_orders = [o for o in orders if o.business_type == 'fast_moving']
        
        assert len(orders) == len(fast_orders), "快消用户只应该看到快消订单"
        assert all(o.business_type == 'fast_moving' for o in orders), "所有订单都应该是快消类型"
    
    def test_supplier_business_type_filter(self, setup_test_data):
        """测试供应商业务类型过滤"""
        data = setup_test_data
        
        # 测试供应商过滤
        query = Supplier.query
        oil_filtered = QueryOptimizer.apply_business_type_filter(
            query, Supplier, 'oil'
        )
        
        suppliers = oil_filtered.all()
        assert all(s.business_type == 'oil' for s in suppliers), "应该只返回油脂供应商"
        
        # 测试快消供应商过滤
        fast_filtered = QueryOptimizer.apply_business_type_filter(
            query, Supplier, 'fast_moving'
        )
        
        suppliers = fast_filtered.all()
        assert all(s.business_type == 'fast_moving' for s in suppliers), "应该只返回快消供应商"
    
    def test_pagination_application(self, setup_test_data):
        """测试分页应用"""
        data = setup_test_data
        
        query = Order.query
        
        # 测试第一页
        page1 = QueryOptimizer.apply_pagination(query, page=1, per_page=5)
        
        assert hasattr(page1, 'items'), "分页对象应该有items属性"
        assert hasattr(page1, 'page'), "分页对象应该有page属性"
        assert hasattr(page1, 'per_page'), "分页对象应该有per_page属性"
        assert hasattr(page1, 'total'), "分页对象应该有total属性"
        
        assert page1.page == 1, "页码应该正确"
        assert page1.per_page == 5, "每页数量应该正确"
        assert len(page1.items) <= 5, "页面项目数量不应超过设定值"
        
        # 测试第二页
        page2 = QueryOptimizer.apply_pagination(query, page=2, per_page=5)
        assert page2.page == 2, "第二页页码应该正确"
        
        # 验证页面内容不重复
        page1_ids = [item.id for item in page1.items]
        page2_ids = [item.id for item in page2.items]
        
        assert len(set(page1_ids) & set(page2_ids)) == 0, "不同页面的内容不应重复"
    
    def test_get_order_with_quotes(self, setup_test_data):
        """测试获取包含报价的订单"""
        data = setup_test_data
        
        # 获取有报价的订单
        order_with_quotes = data['orders'][0]  # 前5个订单有报价
        
        loaded_order = QueryOptimizer.get_order_with_quotes(order_with_quotes.id)
        
        assert loaded_order is not None, "应该能找到订单"
        assert loaded_order.id == order_with_quotes.id, "订单ID应该匹配"
        
        # 验证预加载的关联数据
        # 注意：在测试环境中，由于数据量小，预加载的效果可能不明显
        # 但至少应该能正常访问关联属性而不引发额外查询
        quotes = loaded_order.quotes
        assert isinstance(quotes, list), "报价应该是列表类型"
        
        # 测试不存在的订单
        non_existent_order = QueryOptimizer.get_order_with_quotes(99999)
        assert non_existent_order is None, "不存在的订单应该返回None"
    
    def test_pagination_with_business_type_filter(self, setup_test_data):
        """测试业务类型过滤与分页的组合使用"""
        data = setup_test_data
        
        # 组合使用过滤和分页
        query = Order.query
        filtered_query = QueryOptimizer.apply_business_type_filter(
            query, Order, 'oil'
        )
        paginated = QueryOptimizer.apply_pagination(filtered_query, page=1, per_page=3)
        
        assert all(item.business_type == 'oil' for item in paginated.items), \
            "分页结果应该只包含油脂订单"
        assert len(paginated.items) <= 3, "分页大小应该正确"
    
    def test_query_optimizer_edge_cases(self, setup_test_data):
        """测试查询优化器边界情况"""
        data = setup_test_data
        
        # 测试空查询结果的分页
        empty_query = Order.query.filter(Order.id < 0)  # 不会有结果的查询
        empty_page = QueryOptimizer.apply_pagination(empty_query, page=1, per_page=10)
        
        assert len(empty_page.items) == 0, "空查询的分页应该返回空列表"
        assert empty_page.total == 0, "总数应该为0"
        
        # 测试超出范围的页码
        large_page = QueryOptimizer.apply_pagination(Order.query, page=100, per_page=10)
        assert len(large_page.items) == 0, "超出范围的页码应该返回空结果"
        
        # 测试无效的业务类型
        query = Order.query
        invalid_filtered = QueryOptimizer.apply_business_type_filter(
            query, Order, 'invalid_type'
        )
        
        orders = invalid_filtered.all()
        assert len(orders) == 0, "无效业务类型应该返回空结果"


class TestDateHelper:
    """日期辅助工具测试"""
    
    def test_parse_date_range_valid_dates(self):
        """测试有效日期范围解析"""
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        
        start_dt, end_dt = DateHelper.parse_date_range(start_date, end_date)
        
        assert start_dt is not None, "开始日期应该被正确解析"
        assert end_dt is not None, "结束日期应该被正确解析"
        
        assert start_dt.year == 2024, "开始年份应该正确"
        assert start_dt.month == 1, "开始月份应该正确"
        assert start_dt.day == 1, "开始日期应该正确"
        
        assert end_dt.year == 2024, "结束年份应该正确"
        assert end_dt.month == 1, "结束月份应该正确"
        assert end_dt.day == 31, "结束日期应该正确"
        
        # 验证结束日期被设置为当天的最后一刻
        assert end_dt.hour == 23, "结束时间应该是23点"
        assert end_dt.minute == 59, "结束分钟应该是59分"
        assert end_dt.second == 59, "结束秒数应该是59秒"
    
    def test_parse_date_range_invalid_dates(self):
        """测试无效日期范围解析"""
        # 无效日期格式
        invalid_start = "2024/01/01"  # 错误格式
        valid_end = "2024-01-31"
        
        start_dt, end_dt = DateHelper.parse_date_range(invalid_start, valid_end)
        
        assert start_dt is None, "无效开始日期应该返回None"
        assert end_dt is not None, "有效结束日期应该被正确解析"
        
        # 完全无效的日期
        invalid_date = "not-a-date"
        start_dt, end_dt = DateHelper.parse_date_range(invalid_date, invalid_date)
        
        assert start_dt is None, "无效开始日期应该返回None"
        assert end_dt is None, "无效结束日期应该返回None"
        
        # 空字符串
        start_dt, end_dt = DateHelper.parse_date_range("", "")
        assert start_dt is None, "空开始日期应该返回None"
        assert end_dt is None, "空结束日期应该返回None"
    
    def test_parse_date_range_partial_dates(self):
        """测试部分日期解析"""
        # 只有开始日期
        start_dt, end_dt = DateHelper.parse_date_range("2024-01-01", "")
        assert start_dt is not None, "开始日期应该被解析"
        assert end_dt is None, "空结束日期应该返回None"
        
        # 只有结束日期
        start_dt, end_dt = DateHelper.parse_date_range("", "2024-01-31")
        assert start_dt is None, "空开始日期应该返回None"
        assert end_dt is not None, "结束日期应该被解析"
    
    def test_get_quick_date_range_today(self):
        """测试今天快捷日期范围"""
        start_date, end_date = DateHelper.get_quick_date_range('today')
        
        today_str = date.today().strftime('%Y-%m-%d')
        
        assert start_date == today_str, "今天的开始日期应该是今天"
        assert end_date == today_str, "今天的结束日期应该是今天"
    
    def test_get_quick_date_range_this_month(self):
        """测试本月快捷日期范围"""
        start_date, end_date = DateHelper.get_quick_date_range('this_month')
        
        today = date.today()
        month_start = today.replace(day=1).strftime('%Y-%m-%d')
        today_str = today.strftime('%Y-%m-%d')
        
        assert start_date == month_start, "本月开始日期应该是月初"
        assert end_date == today_str, "本月结束日期应该是今天"
    
    def test_get_quick_date_range_invalid_option(self):
        """测试无效快捷日期选项"""
        start_date, end_date = DateHelper.get_quick_date_range('invalid_option')
        
        assert start_date == '', "无效选项应该返回空字符串"
        assert end_date == '', "无效选项应该返回空字符串"
    
    def test_get_quick_date_range_empty_option(self):
        """测试空快捷日期选项"""
        start_date, end_date = DateHelper.get_quick_date_range('')
        
        assert start_date == '', "空选项应该返回空字符串"
        assert end_date == '', "空选项应该返回空字符串"
    
    def test_date_helper_logging(self):
        """测试日期解析的日志记录"""
        with patch('utils.query_helpers.logging') as mock_logging:
            # 测试无效日期格式会记录警告
            DateHelper.parse_date_range("invalid-date", "2024-01-01")
            
            # 验证日志被调用
            mock_logging.warning.assert_called()
            
            # 检查日志消息内容
            call_args = mock_logging.warning.call_args[0]
            assert "无效的开始日期格式" in call_args[0], "应该记录无效日期格式的警告"
    
    def test_date_range_order_validation(self):
        """测试日期范围顺序验证（如果需要的话）"""
        # 这个测试演示如何验证开始日期不晚于结束日期
        start_date = "2024-01-31"
        end_date = "2024-01-01"  # 结束日期早于开始日期
        
        start_dt, end_dt = DateHelper.parse_date_range(start_date, end_date)
        
        # 当前实现不验证日期顺序，但这里演示如何检查
        if start_dt and end_dt:
            assert start_dt <= end_dt, "开始日期不应该晚于结束日期"


class TestQueryHelpersIntegration:
    """查询辅助工具集成测试"""
    
    @pytest.fixture
    def setup_integration_data(self):
        """设置集成测试数据"""
        with app.app_context():
            db.create_all()
            
            # 创建多个用户和大量数据进行性能测试
            users = []
            for i in range(3):
                user = User(
                    username=f'user_{i}',
                    password_hash='test',
                    business_type='oil' if i % 2 == 0 else 'fast_moving',
                    access_code=f'code_{i}'
                )
                users.append(user)
                db.session.add(user)
            
            db.session.commit()
            
            # 创建大量订单数据
            orders = []
            for i in range(50):
                order = Order(
                    order_no=f'INT{i:04d}',
                    warehouse=f'集成仓库{i}',
                    goods=f'集成商品{i}',
                    delivery_address=f'集成地址{i}',
                    user_id=users[i % len(users)].id,
                    business_type=users[i % len(users)].business_type,
                    status='active' if i % 3 == 0 else ('completed' if i % 3 == 1 else 'cancelled')
                )
                orders.append(order)
                db.session.add(order)
            
            db.session.commit()
            
            yield {'users': users, 'orders': orders}
            
            # 清理
            db.session.remove()
    
    def test_complex_query_optimization(self, setup_integration_data):
        """测试复杂查询优化"""
        data = setup_integration_data
        
        # 组合使用多个查询优化功能
        base_query = Order.query
        
        # 应用业务类型过滤
        filtered_query = QueryOptimizer.apply_business_type_filter(
            base_query, Order, 'oil'
        )
        
        # 添加状态过滤
        status_filtered = filtered_query.filter(Order.status == 'active')
        
        # 应用分页
        paginated = QueryOptimizer.apply_pagination(status_filtered, page=1, per_page=5)
        
        # 验证结果
        assert all(item.business_type == 'oil' for item in paginated.items), \
            "所有结果应该是油脂业务类型"
        assert all(item.status == 'active' for item in paginated.items), \
            "所有结果应该是活跃状态"
        assert len(paginated.items) <= 5, "分页大小应该正确"
    
    def test_date_filtering_with_pagination(self, setup_integration_data):
        """测试日期过滤与分页结合"""
        data = setup_integration_data
        
        # 使用日期辅助工具
        start_date, end_date = DateHelper.get_quick_date_range('today')
        start_dt, end_dt = DateHelper.parse_date_range(start_date, end_date)
        
        # 构建查询
        query = Order.query
        if start_dt:
            query = query.filter(Order.created_at >= start_dt)
        if end_dt:
            query = query.filter(Order.created_at <= end_dt)
        
        # 应用分页
        paginated = QueryOptimizer.apply_pagination(query, page=1, per_page=10)
        
        # 验证结果在日期范围内
        for order in paginated.items:
            if start_dt:
                assert order.created_at >= start_dt, "订单创建时间应该在开始日期之后"
            if end_dt:
                assert order.created_at <= end_dt, "订单创建时间应该在结束日期之前"
    
    def test_performance_with_large_dataset(self, setup_integration_data):
        """测试大数据集下的性能"""
        data = setup_integration_data
        
        import time
        
        # 测试未优化的查询性能
        start_time = time.time()
        
        # 模拟复杂查询
        results = []
        for business_type in ['oil', 'fast_moving']:
            filtered_query = QueryOptimizer.apply_business_type_filter(
                Order.query, Order, business_type
            )
            
            for page in range(1, 4):  # 测试多页
                paginated = QueryOptimizer.apply_pagination(filtered_query, page=page, per_page=5)
                results.extend(paginated.items)
        
        query_time = time.time() - start_time
        
        # 验证结果
        assert len(results) > 0, "应该有查询结果"
        assert query_time < 1.0, f"查询时间应该在合理范围内: {query_time:.3f}秒"
        
        # 验证结果的业务类型正确性
        oil_count = len([r for r in results if r.business_type == 'oil'])
        fast_count = len([r for r in results if r.business_type == 'fast_moving'])
        
        assert oil_count > 0, "应该有油脂订单"
        assert fast_count > 0, "应该有快消订单"


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v', '--tb=short'])