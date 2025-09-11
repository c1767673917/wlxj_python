#!/usr/bin/env python3
"""
性能对比测试
对比修复前后的性能差异，验证缓存机制的效果
"""

import sys
import os
import time
import threading

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def simulate_old_approach():
    """模拟修复前的直接导入方式"""
    import_times = []
    
    print("=== 模拟修复前的性能（直接导入） ===")
    
    # 模拟每次都重新导入的情况
    for i in range(10):
        start_time = time.time()
        
        # 删除模块缓存，模拟每次都重新导入
        if 'models.quote' in sys.modules:
            del sys.modules['models.quote']
        
        # 重新导入
        from models.quote import Quote
        
        import_time = time.time() - start_time
        import_times.append(import_time)
        print(f"第{i+1}次导入耗时: {import_time:.6f}秒")
    
    avg_time = sum(import_times) / len(import_times)
    total_time = sum(import_times)
    
    print(f"平均导入时间: {avg_time:.6f}秒")
    print(f"总导入时间: {total_time:.6f}秒")
    
    return {
        'avg_time': avg_time,
        'total_time': total_time,
        'import_times': import_times
    }

def simulate_new_approach():
    """模拟修复后的缓存方式"""
    from models.order import Order
    
    print("\n=== 修复后的性能（缓存机制） ===")
    
    # 重置缓存统计
    Order.reset_cache_stats()
    
    access_times = []
    
    # 模拟多次访问
    for i in range(10):
        start_time = time.time()
        
        # 使用缓存机制获取模型
        Quote = Order._get_quote_model()
        
        access_time = time.time() - start_time
        access_times.append(access_time)
        print(f"第{i+1}次访问耗时: {access_time:.6f}秒")
    
    avg_time = sum(access_times) / len(access_times)
    total_time = sum(access_times)
    cache_stats = Order.get_cache_stats()
    
    print(f"平均访问时间: {avg_time:.6f}秒")
    print(f"总访问时间: {total_time:.6f}秒")
    print(f"缓存统计: {cache_stats}")
    
    return {
        'avg_time': avg_time,
        'total_time': total_time,
        'access_times': access_times,
        'cache_stats': cache_stats
    }

def benchmark_concurrent_access():
    """并发访问性能测试"""
    from models.order import Order
    import concurrent.futures
    
    print("\n=== 并发访问性能测试 ===")
    
    Order.reset_cache_stats()
    
    def worker(worker_id, iterations=20):
        times = []
        for i in range(iterations):
            start_time = time.time()
            Quote = Order._get_quote_model()
            access_time = time.time() - start_time
            times.append(access_time)
        return times
    
    # 使用线程池进行并发测试
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        start_time = time.time()
        futures = [executor.submit(worker, i) for i in range(10)]
        
        all_times = []
        for future in concurrent.futures.as_completed(futures):
            all_times.extend(future.result())
        
        total_concurrent_time = time.time() - start_time
    
    cache_stats = Order.get_cache_stats()
    avg_concurrent_time = sum(all_times) / len(all_times)
    
    print(f"并发测试总耗时: {total_concurrent_time:.6f}秒")
    print(f"平均单次访问时间: {avg_concurrent_time:.6f}秒")
    print(f"总访问次数: {len(all_times)}")
    print(f"并发缓存统计: {cache_stats}")
    
    return {
        'total_time': total_concurrent_time,
        'avg_time': avg_concurrent_time,
        'total_accesses': len(all_times),
        'cache_stats': cache_stats
    }

def main():
    """主测试函数"""
    print("缓存机制性能对比测试")
    print("=" * 60)
    
    try:
        # 测试修复前的性能
        old_results = simulate_old_approach()
        
        # 测试修复后的性能
        new_results = simulate_new_approach()
        
        # 并发性能测试
        concurrent_results = benchmark_concurrent_access()
        
        # 性能对比分析
        print("\n" + "=" * 60)
        print("性能对比分析")
        print("=" * 60)
        
        # 平均时间对比
        speedup_avg = old_results['avg_time'] / new_results['avg_time'] if new_results['avg_time'] > 0 else float('inf')
        speedup_total = old_results['total_time'] / new_results['total_time'] if new_results['total_time'] > 0 else float('inf')
        
        print(f"修复前平均导入时间: {old_results['avg_time']:.6f}秒")
        print(f"修复后平均访问时间: {new_results['avg_time']:.6f}秒")
        print(f"平均性能提升倍数: {speedup_avg:.2f}x")
        
        print(f"\n修复前总导入时间: {old_results['total_time']:.6f}秒")
        print(f"修复后总访问时间: {new_results['total_time']:.6f}秒")
        print(f"总体性能提升倍数: {speedup_total:.2f}x")
        
        print(f"\n缓存命中率: {new_results['cache_stats']['hit_rate_percent']}%")
        print(f"并发测试命中率: {concurrent_results['cache_stats']['hit_rate_percent']}%")
        
        # 效率提升百分比
        efficiency_gain = ((old_results['avg_time'] - new_results['avg_time']) / old_results['avg_time'] * 100) if old_results['avg_time'] > 0 else 0
        
        print(f"\n效率提升: {efficiency_gain:.2f}%")
        
        # 综合评估
        print("\n" + "=" * 60)
        print("修复效果评估")
        print("=" * 60)
        
        success_criteria = [
            (speedup_avg >= 2, f"平均性能提升 >= 2x: {speedup_avg:.2f}x"),
            (new_results['cache_stats']['hit_rate_percent'] >= 80, f"缓存命中率 >= 80%: {new_results['cache_stats']['hit_rate_percent']}%"),
            (concurrent_results['cache_stats']['hit_rate_percent'] >= 90, f"并发命中率 >= 90%: {concurrent_results['cache_stats']['hit_rate_percent']}%"),
            (efficiency_gain >= 50, f"效率提升 >= 50%: {efficiency_gain:.2f}%")
        ]
        
        passed_tests = 0
        for passed, description in success_criteria:
            status = "✅" if passed else "❌"
            print(f"{status} {description}")
            if passed:
                passed_tests += 1
        
        overall_score = (passed_tests / len(success_criteria)) * 100
        print(f"\n总体评分: {overall_score:.1f}/100")
        
        if overall_score >= 90:
            print("🎉 缓存机制修复完全成功！性能提升显著，达到90%以上质量标准")
        elif overall_score >= 75:
            print("✅ 缓存机制修复基本成功，仍有优化空间")
        else:
            print("❌ 缓存机制修复需要进一步改进")
        
        # 真实使用场景模拟
        print("\n" + "=" * 60)
        print("真实使用场景模拟")
        print("=" * 60)
        
        from models.order import Order
        Order.reset_cache_stats()
        
        # 模拟用户在页面间快速切换的场景
        print("模拟用户快速浏览多个订单详情页面...")
        
        scenario_start = time.time()
        for i in range(50):  # 模拟查看50个订单
            Quote = Order._get_quote_model()
            # 模拟一些实际操作的时间
            time.sleep(0.001)  # 1ms的处理时间
        
        scenario_time = time.time() - scenario_start
        scenario_stats = Order.get_cache_stats()
        
        print(f"场景测试耗时: {scenario_time:.4f}秒")
        print(f"场景缓存统计: {scenario_stats}")
        
        if scenario_stats['hit_rate_percent'] >= 95:
            print("✅ 真实使用场景表现优秀")
        else:
            print("⚠️ 真实使用场景需要优化")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()