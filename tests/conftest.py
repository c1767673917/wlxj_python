#!/usr/bin/env python3
"""
pytest 配置文件
为系统优化功能测试提供共享的测试配置和夹具
"""

import pytest
import os
import tempfile
import shutil
from typing import Generator, Dict, Any
from unittest.mock import patch

# 确保测试环境
os.environ['FLASK_ENV'] = 'testing'
os.environ['TESTING'] = 'True'

# 导入应用模块
from app import app, db
from models import User, Order, Quote, Supplier


class TestConfig:
    """测试配置类"""
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 测试配置
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key-for-testing-only'
    
    # 文件安全配置
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB for testing
    
    # 日志配置
    LOG_LEVEL = 'DEBUG'


@pytest.fixture(scope='session')
def app_config():
    """应用配置夹具"""
    return TestConfig


@pytest.fixture(scope='function')
def test_app(app_config):
    """测试应用夹具"""
    # 配置测试应用
    app.config.from_object(app_config)
    
    with app.app_context():
        yield app


@pytest.fixture(scope='function')
def test_db(test_app):
    """测试数据库夹具"""
    # 创建所有表
    db.create_all()
    
    yield db
    
    # 清理数据库
    db.session.remove()
    db.drop_all()


@pytest.fixture(scope='function')
def test_client(test_app):
    """测试客户端夹具"""
    return test_app.test_client()


@pytest.fixture(scope='function')
def sample_users(test_db):
    """样本用户数据夹具"""
    users = [
        User(
            username='admin_user',
            password_hash='admin_hash',
            business_type='admin',
            access_code='admin123'
        ),
        User(
            username='oil_user',
            password_hash='oil_hash',
            business_type='oil',
            access_code='oil123'
        ),
        User(
            username='fast_user',
            password_hash='fast_hash',
            business_type='fast_moving',
            access_code='fast123'
        )
    ]
    
    for user in users:
        test_db.session.add(user)
    
    test_db.session.commit()
    
    return {user.username: user for user in users}


@pytest.fixture(scope='function')
def sample_suppliers(test_db, sample_users):
    """样本供应商数据夹具"""
    suppliers = [
        Supplier(
            name='油脂供应商A',
            user_id=sample_users['oil_user'].id,
            business_type='oil'
        ),
        Supplier(
            name='油脂供应商B',
            user_id=sample_users['oil_user'].id,
            business_type='oil'
        ),
        Supplier(
            name='快消供应商A',
            user_id=sample_users['fast_user'].id,
            business_type='fast_moving'
        ),
        Supplier(
            name='快消供应商B',
            user_id=sample_users['fast_user'].id,
            business_type='fast_moving'
        )
    ]
    
    for supplier in suppliers:
        test_db.session.add(supplier)
    
    test_db.session.commit()
    
    return suppliers


@pytest.fixture(scope='function')
def sample_orders(test_db, sample_users):
    """样本订单数据夹具"""
    orders = []
    statuses = ['active', 'completed', 'cancelled', 'pending']
    
    for i in range(20):
        user = sample_users['oil_user'] if i % 2 == 0 else sample_users['fast_user']
        order = Order(
            order_no=f'TEST{i:04d}',
            warehouse=f'测试仓库_{i % 5}',
            goods=f'测试商品_{i % 10}',
            delivery_address=f'测试地址_{i}',
            user_id=user.id,
            business_type=user.business_type,
            status=statuses[i % len(statuses)]
        )
        orders.append(order)
        test_db.session.add(order)
    
    test_db.session.commit()
    
    return orders


@pytest.fixture(scope='function')
def sample_quotes(test_db, sample_orders, sample_suppliers):
    """样本报价数据夹具"""
    quotes = []
    
    # 为前10个订单创建报价
    for i, order in enumerate(sample_orders[:10]):
        # 找到匹配业务类型的供应商
        matching_suppliers = [s for s in sample_suppliers if s.business_type == order.business_type]
        
        for j, supplier in enumerate(matching_suppliers):
            quote = Quote(
                order_id=order.id,
                supplier_id=supplier.id,
                price=100.0 + i * 10 + j * 5
            )
            quotes.append(quote)
            test_db.session.add(quote)
    
    test_db.session.commit()
    
    return quotes


@pytest.fixture(scope='function')
def temp_database():
    """临时数据库文件夹具"""
    # 创建临时数据库文件
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    
    yield temp_db.name
    
    # 清理临时文件
    if os.path.exists(temp_db.name):
        os.unlink(temp_db.name)


@pytest.fixture(scope='function')
def temp_directory():
    """临时目录夹具"""
    temp_dir = tempfile.mkdtemp()
    
    yield temp_dir
    
    # 清理临时目录
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture(scope='function')
def mock_file_upload():
    """模拟文件上传夹具"""
    class MockFileUpload:
        def __init__(self, filename: str, content: bytes = b'test content'):
            self.filename = filename
            self.content = content
            self.size = len(content)
        
        def read(self, size: int = -1) -> bytes:
            if size == -1:
                return self.content
            return self.content[:size]
        
        def seek(self, pos: int):
            pass
        
        def tell(self) -> int:
            return 0
    
    return MockFileUpload


@pytest.fixture(scope='function')
def mock_environment_variables():
    """模拟环境变量夹具"""
    def _mock_env(env_vars: Dict[str, str]):
        return patch.dict(os.environ, env_vars)
    
    return _mock_env


@pytest.fixture(scope='function')
def performance_test_data(test_db, sample_users):
    """性能测试数据夹具"""
    # 创建大量数据用于性能测试
    users = list(sample_users.values())
    
    # 创建更多供应商
    suppliers = []
    for i in range(50):
        user = users[i % len(users)]
        supplier = Supplier(
            name=f'性能测试供应商_{i}',
            user_id=user.id,
            business_type=user.business_type
        )
        suppliers.append(supplier)
        test_db.session.add(supplier)
    
    test_db.session.commit()
    
    # 创建大量订单
    orders = []
    statuses = ['active', 'completed', 'cancelled', 'pending']
    
    for i in range(500):
        user = users[i % len(users)]
        order = Order(
            order_no=f'PERF{i:05d}',
            warehouse=f'性能仓库_{i % 20}',
            goods=f'性能商品_{i % 100}',
            delivery_address=f'性能地址_{i}',
            user_id=user.id,
            business_type=user.business_type,
            status=statuses[i % len(statuses)]
        )
        orders.append(order)
        test_db.session.add(order)
        
        # 每100个订单提交一次
        if (i + 1) % 100 == 0:
            test_db.session.commit()
    
    test_db.session.commit()
    
    # 创建大量报价
    quotes = []
    for i, order in enumerate(orders[:200]):  # 为前200个订单创建报价
        matching_suppliers = [s for s in suppliers if s.business_type == order.business_type]
        
        for j, supplier in enumerate(matching_suppliers[:3]):  # 每个订单最多3个报价
            quote = Quote(
                order_id=order.id,
                supplier_id=supplier.id,
                price=50.0 + i + j * 10
            )
            quotes.append(quote)
            test_db.session.add(quote)
            
            # 每50个报价提交一次
            if len(quotes) % 50 == 0:
                test_db.session.commit()
    
    test_db.session.commit()
    
    return {
        'users': users,
        'suppliers': suppliers,
        'orders': orders,
        'quotes': quotes
    }


@pytest.fixture(scope='function')
def logged_in_user(test_client, sample_users):
    """已登录用户夹具"""
    def _login_user(username: str = 'oil_user'):
        user = sample_users[username]
        with test_client.session_transaction() as sess:
            sess['user_id'] = str(user.id)
            sess['_fresh'] = True
        return user
    
    return _login_user


# 自定义pytest标记
def pytest_configure(config):
    """配置自定义pytest标记"""
    config.addinivalue_line(
        "markers", "performance: 标记性能测试"
    )
    config.addinivalue_line(
        "markers", "integration: 标记集成测试"
    )
    config.addinivalue_line(
        "markers", "unit: 标记单元测试"
    )
    config.addinivalue_line(
        "markers", "slow: 标记缓慢测试"
    )
    config.addinivalue_line(
        "markers", "database: 标记数据库相关测试"
    )
    config.addinivalue_line(
        "markers", "security: 标记安全相关测试"
    )


# 测试收集钩子
def pytest_collection_modifyitems(config, items):
    """修改测试收集项"""
    # 为没有标记的测试添加默认标记
    for item in items:
        if not any(mark.name in ['unit', 'integration', 'performance'] for mark in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
        
        # 为包含 'performance' 的测试添加性能标记
        if 'performance' in item.name.lower() or 'performance' in str(item.fspath).lower():
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        
        # 为包含 'database' 的测试添加数据库标记
        if 'database' in item.name.lower() or 'db' in item.name.lower():
            item.add_marker(pytest.mark.database)
        
        # 为包含 'security' 的测试添加安全标记
        if 'security' in item.name.lower() or 'file' in item.name.lower():
            item.add_marker(pytest.mark.security)


# 测试报告钩子
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """生成测试报告"""
    outcome = yield
    rep = outcome.get_result()
    
    # 添加自定义属性到测试报告
    if rep.when == "call":
        # 记录测试分类
        test_categories = []
        for mark in item.iter_markers():
            if mark.name in ['unit', 'integration', 'performance', 'database', 'security']:
                test_categories.append(mark.name)
        
        rep.test_categories = test_categories
        
        # 记录测试文件
        rep.test_file = str(item.fspath.relative_to(item.config.rootdir))


# 会话结束钩子
def pytest_sessionfinish(session, exitstatus):
    """会话结束时的钩子"""
    if hasattr(session.config, 'option') and session.config.option.verbose:
        print("\n" + "="*60)
        print("测试会话结束")
        print("="*60)
        
        # 统计测试结果
        passed = len([r for r in session.config._reports if r.passed])
        failed = len([r for r in session.config._reports if r.failed])
        skipped = len([r for r in session.config._reports if r.skipped])
        
        print(f"通过: {passed}, 失败: {failed}, 跳过: {skipped}")


# 添加命令行选项
def pytest_addoption(parser):
    """添加自定义命令行选项"""
    parser.addoption(
        "--run-performance", 
        action="store_true", 
        default=False, 
        help="运行性能测试"
    )
    parser.addoption(
        "--skip-slow", 
        action="store_true", 
        default=False, 
        help="跳过慢速测试"
    )


def pytest_runtest_setup(item):
    """测试运行前的设置"""
    # 根据命令行选项跳过测试
    if item.config.getoption("--skip-slow"):
        if "slow" in [mark.name for mark in item.iter_markers()]:
            pytest.skip("跳过慢速测试 (--skip-slow)")
    
    if not item.config.getoption("--run-performance"):
        if "performance" in [mark.name for mark in item.iter_markers()]:
            pytest.skip("跳过性能测试 (需要 --run-performance)")


# 工具函数夹具
@pytest.fixture(scope='function')
def test_helpers():
    """测试辅助函数夹具"""
    class TestHelpers:
        @staticmethod
        def create_test_file(directory: str, filename: str, content: bytes = b'test content') -> str:
            """创建测试文件"""
            filepath = os.path.join(directory, filename)
            with open(filepath, 'wb') as f:
                f.write(content)
            return filepath
        
        @staticmethod
        def assert_performance_acceptable(duration: float, limit: float, operation: str):
            """断言性能可接受"""
            assert duration < limit, f"{operation} 性能不佳: {duration:.3f}秒 > {limit}秒"
        
        @staticmethod
        def count_database_queries(func, *args, **kwargs):
            """计算数据库查询数量"""
            # 这是一个简化版本，实际实现可能需要更复杂的监控
            import time
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            return result, end_time - start_time
    
    return TestHelpers()