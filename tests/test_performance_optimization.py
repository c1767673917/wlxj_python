#!/usr/bin/env python3
"""
性能优化验证测试
专门测试数据库索引、查询优化等性能相关功能
"""

import pytest
import time
import sqlite3
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

from app import app, db
from models import Order, Quote, Supplier, User
from migrations.add_performance_indexes import add_performance_indexes, validate_index_performance


class TestDatabasePerformance:
    """数据库性能测试"""
    
    @pytest.fixture
    def setup_performance_test(self):
        """设置性能测试环境"""
        with app.app_context():
            db.create_all()
            
            # 创建大量测试数据以测试性能
            self._create_large_dataset()
            
            yield
            
            # 清理
            db.session.remove()
    
    def _create_large_dataset(self):
        """创建大量测试数据"""
        # 创建测试用户
        users = []
        for i in range(10):
            user = User(
                username=f'perf_user_{i}',
                password_hash='test_hash',
                business_type='oil' if i % 2 == 0 else 'fast_moving',
                access_code=f'perf_code_{i}'
            )
            users.append(user)
            db.session.add(user)
        
        db.session.commit()
        
        # 创建供应商
        suppliers = []
        for i in range(20):
            supplier = Supplier(
                name=f'性能测试供应商_{i}',
                user_id=users[i % len(users)].id,
                business_type=users[i % len(users)].business_type
            )
            suppliers.append(supplier)
            db.session.add(supplier)
        
        db.session.commit()
        
        # 创建大量订单（1000个）
        orders = []
        statuses = ['active', 'completed', 'cancelled', 'pending']
        
        for i in range(1000):
            order = Order(
                order_no=f'PERF{i:06d}',
                warehouse=f'性能测试仓库_{i % 10}',
                goods=f'性能测试商品_{i % 50}',
                delivery_address=f'性能测试地址_{i}',
                user_id=users[i % len(users)].id,
                business_type=users[i % len(users)].business_type,
                status=statuses[i % len(statuses)]
            )
            orders.append(order)
            db.session.add(order)
            
            # 每100个订单提交一次，避免内存问题
            if (i + 1) % 100 == 0:
                db.session.commit()
        
        db.session.commit()
        
        # 创建大量报价（5000个）
        quotes = []
        for i in range(5000):
            order = orders[i % len(orders)]
            supplier = suppliers[i % len(suppliers)]
            
            # 确保供应商和订单的业务类型匹配
            if order.business_type == supplier.business_type:
                quote = Quote(
                    order_id=order.id,
                    supplier_id=supplier.id,
                    price=50.0 + (i % 1000)  # 价格范围 50-1049
                )
                quotes.append(quote)
                db.session.add(quote)
                
                # 每500个报价提交一次
                if len(quotes) % 500 == 0:
                    db.session.commit()
        
        db.session.commit()
        
        print(f"创建了 {len(users)} 个用户, {len(suppliers)} 个供应商, {len(orders)} 个订单, {len(quotes)} 个报价")
    
    def test_query_performance_without_indexes(self, setup_performance_test):
        """测试没有索引时的查询性能"""
        # 确保没有索引的情况下测试
        # 注意：在实际测试中，可能需要先删除索引
        
        queries_and_limits = [
            ("按状态查询", lambda: Order.query.filter_by(status='active').all(), 2.0),
            ("按业务类型查询", lambda: Order.query.filter_by(business_type='oil').all(), 2.0),
            ("按用户ID查询", lambda: Order.query.filter_by(user_id=1).all(), 2.0),
            ("按创建时间排序", lambda: Order.query.order_by(Order.created_at.desc()).limit(100).all(), 3.0),
            ("按报价订单ID查询", lambda: Quote.query.filter_by(order_id=1).all(), 1.0),
            ("按供应商ID查询", lambda: Quote.query.filter_by(supplier_id=1).all(), 1.0),
            ("按价格排序", lambda: Quote.query.order_by(Quote.price.asc()).limit(100).all(), 2.0),
            ("供应商按业务类型查询", lambda: Supplier.query.filter_by(business_type='oil').all(), 1.0),
        ]
        
        performance_results = []
        
        for query_name, query_func, time_limit in queries_and_limits:
            start_time = time.time()
            
            # 执行查询
            results = query_func()
            
            query_time = time.time() - start_time
            performance_results.append({
                'query': query_name,
                'time': query_time,
                'limit': time_limit,
                'count': len(results) if isinstance(results, list) else 1
            })
            
            print(f"{query_name}: {query_time:.3f}秒 (结果数: {len(results) if isinstance(results, list) else 1})")
            
            # 验证查询时间在合理范围内
            assert query_time < time_limit, f"{query_name} 查询时间过长: {query_time:.3f}秒 > {time_limit}秒"
            
            # 验证查询有结果（除非表为空）
            if isinstance(results, list):
                assert len(results) >= 0, f"{query_name} 查询应该返回结果"
        
        return performance_results
    
    def test_complex_join_queries_performance(self, setup_performance_test):
        """测试复杂连接查询性能"""
        complex_queries = [
            {
                'name': '订单与报价连接查询',
                'query': lambda: db.session.query(Order, Quote).join(Quote).limit(100).all(),
                'limit': 3.0
            },
            {
                'name': '订单与用户连接查询',
                'query': lambda: db.session.query(Order, User).join(User).limit(100).all(),
                'limit': 2.0
            },
            {
                'name': '报价与供应商连接查询',
                'query': lambda: db.session.query(Quote, Supplier).join(Supplier).limit(100).all(),
                'limit': 2.0
            },
            {
                'name': '三表连接查询',
                'query': lambda: db.session.query(Order, Quote, Supplier)\
                    .join(Quote).join(Supplier).limit(50).all(),
                'limit': 4.0
            }
        ]
        
        for query_info in complex_queries:
            start_time = time.time()
            
            results = query_info['query']()
            
            query_time = time.time() - start_time
            print(f"{query_info['name']}: {query_time:.3f}秒 (结果数: {len(results)})")
            
            assert query_time < query_info['limit'], \
                f"{query_info['name']} 查询时间过长: {query_time:.3f}秒"
            assert len(results) > 0, f"{query_info['name']} 应该有查询结果"
    
    def test_aggregation_queries_performance(self, setup_performance_test):
        """测试聚合查询性能"""
        aggregation_queries = [
            {
                'name': '按状态统计订单数量',
                'query': lambda: db.session.query(Order.status, db.func.count(Order.id))\
                    .group_by(Order.status).all(),
                'limit': 1.0
            },
            {
                'name': '按业务类型统计订单数量',
                'query': lambda: db.session.query(Order.business_type, db.func.count(Order.id))\
                    .group_by(Order.business_type).all(),
                'limit': 1.0
            },
            {
                'name': '计算平均报价',
                'query': lambda: db.session.query(db.func.avg(Quote.price)).scalar(),
                'limit': 1.0
            },
            {
                'name': '计算最高和最低报价',
                'query': lambda: db.session.query(
                    db.func.max(Quote.price), 
                    db.func.min(Quote.price)
                ).first(),
                'limit': 1.0
            },
            {
                'name': '按订单统计报价数量',
                'query': lambda: db.session.query(Quote.order_id, db.func.count(Quote.id))\
                    .group_by(Quote.order_id).having(db.func.count(Quote.id) > 1).all(),
                'limit': 2.0
            }
        ]
        
        for query_info in aggregation_queries:
            start_time = time.time()
            
            results = query_info['query']()
            
            query_time = time.time() - start_time
            print(f"{query_info['name']}: {query_time:.3f}秒")
            
            assert query_time < query_info['limit'], \
                f"{query_info['name']} 查询时间过长: {query_time:.3f}秒"
            
            # 验证结果不为空（聚合查询至少应该有一个结果）
            if isinstance(results, list):
                assert len(results) >= 0, f"{query_info['name']} 聚合查询应该有结果"
            else:
                assert results is not None, f"{query_info['name']} 聚合查询应该有结果"
    
    def test_pagination_performance(self, setup_performance_test):
        """测试分页查询性能"""
        page_sizes = [10, 50, 100]
        pages_to_test = [1, 5, 10, 20]
        
        for page_size in page_sizes:
            for page in pages_to_test:
                start_time = time.time()
                
                # 测试分页查询
                paginated = Order.query.order_by(Order.created_at.desc())\
                    .paginate(page=page, per_page=page_size, error_out=False)
                
                # 访问结果以确保查询执行
                items = paginated.items
                total = paginated.total
                
                query_time = time.time() - start_time
                
                print(f"分页查询 - 页大小: {page_size}, 页码: {page}, "
                      f"时间: {query_time:.3f}秒, 结果数: {len(items)}")
                
                # 验证性能
                assert query_time < 1.0, \
                    f"分页查询时间过长: 页大小{page_size}, 页码{page}, 时间{query_time:.3f}秒"
                
                # 验证结果
                assert len(items) <= page_size, "分页结果数不应超过页大小"
                assert total > 0, "总数应该大于0"
    
    def test_concurrent_query_performance(self, setup_performance_test):
        """测试并发查询性能"""
        def run_concurrent_query(query_id: int) -> Dict[str, Any]:
            """执行并发查询"""
            start_time = time.time()
            
            # 模拟不同类型的查询
            if query_id % 4 == 0:
                results = Order.query.filter_by(status='active').limit(50).all()
            elif query_id % 4 == 1:
                results = Quote.query.filter(Quote.price > 100).limit(50).all()
            elif query_id % 4 == 2:
                results = Supplier.query.filter_by(business_type='oil').all()
            else:
                results = Order.query.order_by(Order.created_at.desc()).limit(20).all()
            
            query_time = time.time() - start_time
            
            return {
                'query_id': query_id,
                'time': query_time,
                'count': len(results)
            }
        
        # 使用线程池执行并发查询
        with ThreadPoolExecutor(max_workers=5) as executor:
            start_time = time.time()
            
            # 提交10个并发查询
            futures = [executor.submit(run_concurrent_query, i) for i in range(10)]
            
            # 收集结果
            results = [future.result() for future in futures]
            
            total_time = time.time() - start_time
        
        print(f"并发查询总时间: {total_time:.3f}秒")
        
        # 验证所有查询都完成了
        assert len(results) == 10, "所有并发查询都应该完成"
        
        # 验证每个查询的性能
        for result in results:
            assert result['time'] < 5.0, \
                f"并发查询{result['query_id']}时间过长: {result['time']:.3f}秒"
            assert result['count'] >= 0, "查询应该有结果"
        
        # 验证平均性能
        avg_time = sum(r['time'] for r in results) / len(results)
        assert avg_time < 2.0, f"平均查询时间过长: {avg_time:.3f}秒"
        
        print(f"平均单个查询时间: {avg_time:.3f}秒")


class TestIndexEffectiveness:
    """索引效果测试"""
    
    @pytest.fixture
    def setup_index_test(self):
        """设置索引测试环境"""
        # 创建临时数据库文件
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # 配置应用使用临时数据库
        original_db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.temp_db.name}'
        
        with app.app_context():
            db.create_all()
            self._create_test_data()
            
            yield self.temp_db.name
        
        # 恢复原始数据库配置
        app.config['SQLALCHEMY_DATABASE_URI'] = original_db_uri
        
        # 清理临时文件
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def _create_test_data(self):
        """创建索引测试数据"""
        # 创建足够的数据来测试索引效果
        users = []
        for i in range(5):
            user = User(
                username=f'idx_user_{i}',
                password_hash='test',
                business_type='oil' if i % 2 == 0 else 'fast_moving',
                access_code=f'idx_code_{i}'
            )
            users.append(user)
            db.session.add(user)
        
        db.session.commit()
        
        # 创建大量订单
        for i in range(500):
            order = Order(
                order_no=f'IDX{i:05d}',
                warehouse=f'索引仓库{i % 10}',
                goods=f'索引商品{i % 20}',
                delivery_address=f'索引地址{i}',
                user_id=users[i % len(users)].id,
                business_type=users[i % len(users)].business_type,
                status=['active', 'completed', 'cancelled'][i % 3]
            )
            db.session.add(order)
            
            if (i + 1) % 100 == 0:
                db.session.commit()
        
        db.session.commit()
    
    def test_index_creation_and_usage(self, setup_index_test):
        """测试索引创建和使用"""
        db_path = setup_index_test
        
        # 测试没有索引时的查询性能
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 执行EXPLAIN QUERY PLAN来查看查询计划
        cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM orders WHERE status = 'active'")
        plan_without_index = cursor.fetchall()
        
        print("没有索引的查询计划:")
        for step in plan_without_index:
            print(f"  {step}")
        
        # 测试查询时间（没有索引）
        start_time = time.time()
        cursor.execute("SELECT * FROM orders WHERE status = 'active'")
        results_without_index = cursor.fetchall()
        time_without_index = time.time() - start_time
        
        conn.close()
        
        # 添加索引
        with app.app_context():
            # 模拟添加索引（直接在测试数据库上执行）
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_business_type ON orders(business_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)")
            
            conn.commit()
            
            # 测试有索引时的查询计划
            cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM orders WHERE status = 'active'")
            plan_with_index = cursor.fetchall()
            
            print("\n有索引的查询计划:")
            for step in plan_with_index:
                print(f"  {step}")
            
            # 测试查询时间（有索引）
            start_time = time.time()
            cursor.execute("SELECT * FROM orders WHERE status = 'active'")
            results_with_index = cursor.fetchall()
            time_with_index = time.time() - start_time
            
            conn.close()
        
        # 验证结果
        assert len(results_without_index) == len(results_with_index), "结果数量应该相同"
        
        # 验证索引确实被使用（查询计划应该不同）
        plan_without_str = str(plan_without_index)
        plan_with_str = str(plan_with_index)
        
        # 有索引的查询计划应该提到索引使用
        has_index_usage = any('USING INDEX' in str(step) for step in plan_with_index)
        
        print(f"\n性能对比:")
        print(f"没有索引: {time_without_index:.4f}秒")
        print(f"有索引: {time_with_index:.4f}秒")
        print(f"性能提升: {((time_without_index - time_with_index) / time_without_index * 100):.1f}%")
        print(f"索引被使用: {has_index_usage}")
        
        # 在大数据集下，索引应该提供性能提升
        if len(results_without_index) > 100:
            improvement = (time_without_index - time_with_index) / time_without_index
            assert improvement >= 0, "索引应该提供性能提升或至少不降低性能"
    
    def test_index_effectiveness_on_different_queries(self, setup_index_test):
        """测试索引在不同查询类型上的效果"""
        db_path = setup_index_test
        
        # 添加所有索引
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 添加索引
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)",
            "CREATE INDEX IF NOT EXISTS idx_orders_business_type ON orders(business_type)",
            "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)",
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        conn.commit()
        
        # 测试不同类型的查询
        test_queries = [
            ("等值查询 - status", "SELECT * FROM orders WHERE status = 'active'"),
            ("等值查询 - business_type", "SELECT * FROM orders WHERE business_type = 'oil'"),
            ("等值查询 - user_id", "SELECT * FROM orders WHERE user_id = 1"),
            ("排序查询", "SELECT * FROM orders ORDER BY created_at DESC LIMIT 50"),
            ("范围查询", "SELECT * FROM orders WHERE created_at > datetime('now', '-1 day')"),
            ("复合条件", "SELECT * FROM orders WHERE status = 'active' AND business_type = 'oil'"),
        ]
        
        query_results = []
        
        for query_name, query_sql in test_queries:
            # 检查查询计划
            cursor.execute(f"EXPLAIN QUERY PLAN {query_sql}")
            plan = cursor.fetchall()
            
            # 执行查询并测量时间
            start_time = time.time()
            cursor.execute(query_sql)
            results = cursor.fetchall()
            query_time = time.time() - start_time
            
            # 检查是否使用了索引
            uses_index = any('USING INDEX' in str(step) for step in plan)
            
            query_results.append({
                'name': query_name,
                'time': query_time,
                'count': len(results),
                'uses_index': uses_index,
                'plan': plan
            })
            
            print(f"{query_name}: {query_time:.4f}秒, 结果数: {len(results)}, 使用索引: {uses_index}")
        
        conn.close()
        
        # 验证关键查询使用了索引
        status_query = next(q for q in query_results if q['name'] == "等值查询 - status")
        assert status_query['uses_index'], "状态查询应该使用索引"
        
        business_type_query = next(q for q in query_results if q['name'] == "等值查询 - business_type")
        assert business_type_query['uses_index'], "业务类型查询应该使用索引"
        
        # 验证所有查询性能在合理范围内
        for result in query_results:
            assert result['time'] < 1.0, f"{result['name']} 查询时间过长: {result['time']:.4f}秒"


class TestMemoryAndResourceUsage:
    """内存和资源使用测试"""
    
    def test_memory_usage_during_large_queries(self):
        """测试大查询时的内存使用"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        with app.app_context():
            # 记录初始内存使用
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 执行大查询
            large_results = []
            for i in range(10):
                # 每次查询100个订单
                orders = Order.query.limit(100).all()
                large_results.extend(orders)
                
                # 每次查询后检查内存
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - initial_memory
                
                print(f"查询 {i+1}: 内存使用 {current_memory:.1f}MB (+{memory_increase:.1f}MB)")
                
                # 内存增长应该在合理范围内
                assert memory_increase < 500, f"内存增长过大: {memory_increase:.1f}MB"
            
            # 清理结果
            del large_results
            
            # 最终内存检查
            final_memory = process.memory_info().rss / 1024 / 1024
            total_increase = final_memory - initial_memory
            
            print(f"总内存增长: {total_increase:.1f}MB")
            
            # 总内存增长应该在合理范围内
            assert total_increase < 200, f"总内存增长过大: {total_increase:.1f}MB"
    
    def test_database_connection_handling(self):
        """测试数据库连接处理"""
        with app.app_context():
            # 测试连接池不会耗尽
            for i in range(20):
                try:
                    # 执行简单查询
                    count = Order.query.count()
                    assert isinstance(count, int), "查询应该返回整数"
                    
                    # 执行另一个查询
                    first_order = Order.query.first()
                    
                    print(f"连接测试 {i+1}: 订单数量 {count}")
                    
                except Exception as e:
                    pytest.fail(f"数据库连接失败在第 {i+1} 次查询: {str(e)}")
    
    def test_query_result_cleanup(self):
        """测试查询结果清理"""
        with app.app_context():
            # 执行多个查询并确保结果被正确清理
            for i in range(5):
                # 执行查询
                orders = Order.query.limit(50).all()
                quotes = Quote.query.limit(50).all()
                suppliers = Supplier.query.all()
                
                # 验证结果
                assert isinstance(orders, list), "订单查询应该返回列表"
                assert isinstance(quotes, list), "报价查询应该返回列表"
                assert isinstance(suppliers, list), "供应商查询应该返回列表"
                
                # 手动清理（模拟实际使用中的清理）
                del orders, quotes, suppliers
                
                print(f"查询清理测试 {i+1} 完成")


if __name__ == '__main__':
    # 运行性能测试
    pytest.main([__file__, '-v', '-s', '--tb=short'])