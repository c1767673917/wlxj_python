#!/usr/bin/env python3
"""
系统优化功能测试运行器
统一运行所有优化相关测试并生成报告
"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tests/test_results.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class OptimizationTestRunner:
    """优化功能测试运行器"""
    
    def __init__(self):
        self.test_files = [
            'tests/test_optimization_features.py',
            'tests/test_query_helpers.py', 
            'tests/test_performance_optimization.py'
        ]
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有优化测试"""
        logger.info("开始系统优化功能测试")
        self.start_time = time.time()
        
        # 运行每个测试文件
        for test_file in self.test_files:
            logger.info(f"运行测试文件: {test_file}")
            result = self._run_single_test_file(test_file)
            self.results[test_file] = result
        
        self.end_time = time.time()
        
        # 生成综合报告
        report = self._generate_comprehensive_report()
        
        # 保存报告
        self._save_report(report)
        
        logger.info("所有优化测试完成")
        return report
    
    def _run_single_test_file(self, test_file: str) -> Dict[str, Any]:
        """运行单个测试文件"""
        start_time = time.time()
        
        try:
            # 使用pytest运行测试
            cmd = [
                sys.executable, '-m', 'pytest', 
                test_file, 
                '-v', 
                '--tb=short',
                '--capture=no',
                f'--junitxml=tests/results_{Path(test_file).stem}.xml'
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                cwd=project_root
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # 解析输出
            passed, failed, errors = self._parse_pytest_output(result.stdout)
            
            return {
                'status': 'success' if result.returncode == 0 else 'failed',
                'return_code': result.returncode,
                'duration': duration,
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
        except Exception as e:
            logger.error(f"运行测试文件 {test_file} 时出错: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'duration': time.time() - start_time,
                'passed': 0,
                'failed': 0,
                'errors': 1
            }
    
    def _parse_pytest_output(self, output: str) -> tuple:
        """解析pytest输出获取测试统计"""
        passed = failed = errors = 0
        
        lines = output.split('\n')
        for line in lines:
            if 'passed' in line and 'failed' in line:
                # 寻找类似 "5 passed, 2 failed" 的行
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed' and i > 0:
                        try:
                            passed = int(parts[i-1])
                        except ValueError:
                            pass
                    elif part == 'failed' and i > 0:
                        try:
                            failed = int(parts[i-1])
                        except ValueError:
                            pass
                    elif part == 'error' and i > 0:
                        try:
                            errors = int(parts[i-1])
                        except ValueError:
                            pass
            elif 'passed in' in line:
                # 处理只有通过测试的情况
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed' and i > 0:
                        try:
                            passed = int(parts[i-1])
                        except ValueError:
                            pass
        
        return passed, failed, errors
    
    def _generate_comprehensive_report(self) -> Dict[str, Any]:
        """生成综合测试报告"""
        total_duration = self.end_time - self.start_time if self.start_time and self.end_time else 0
        
        # 计算总体统计
        total_passed = sum(result.get('passed', 0) for result in self.results.values())
        total_failed = sum(result.get('failed', 0) for result in self.results.values())
        total_errors = sum(result.get('errors', 0) for result in self.results.values())
        total_tests = total_passed + total_failed + total_errors
        
        # 计算成功率
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        # 分析结果
        all_passed = all(result.get('status') == 'success' for result in self.results.values())
        
        report = {
            'summary': {
                'timestamp': datetime.now().isoformat(),
                'total_duration': total_duration,
                'total_tests': total_tests,
                'passed': total_passed,
                'failed': total_failed,
                'errors': total_errors,
                'success_rate': success_rate,
                'overall_status': 'PASS' if all_passed and total_failed == 0 and total_errors == 0 else 'FAIL'
            },
            'test_files': self.results,
            'feature_coverage': self._analyze_feature_coverage(),
            'performance_metrics': self._extract_performance_metrics(),
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _analyze_feature_coverage(self) -> Dict[str, Any]:
        """分析功能覆盖率"""
        covered_features = {
            'database_indexes': False,
            'file_security': False,
            'error_codes': False,
            'environment_validation': False,
            'query_optimization': False,
            'performance_testing': False
        }
        
        # 检查每个测试文件的输出来确定覆盖的功能
        for test_file, result in self.results.items():
            output = result.get('stdout', '')
            
            if 'test_optimization_features.py' in test_file:
                if 'TestDatabaseIndexOptimization' in output:
                    covered_features['database_indexes'] = True
                if 'TestFileSecurity' in output:
                    covered_features['file_security'] = True
                if 'TestErrorCodeSystem' in output:
                    covered_features['error_codes'] = True
                if 'TestEnvironmentValidator' in output:
                    covered_features['environment_validation'] = True
            
            elif 'test_query_helpers.py' in test_file:
                if 'TestQueryOptimizer' in output:
                    covered_features['query_optimization'] = True
            
            elif 'test_performance_optimization.py' in test_file:
                if 'TestDatabasePerformance' in output:
                    covered_features['performance_testing'] = True
        
        coverage_percentage = sum(covered_features.values()) / len(covered_features) * 100
        
        return {
            'features': covered_features,
            'coverage_percentage': coverage_percentage
        }
    
    def _extract_performance_metrics(self) -> Dict[str, Any]:
        """提取性能指标"""
        metrics = {
            'query_performance': {},
            'index_effectiveness': {},
            'memory_usage': {},
            'concurrent_performance': {}
        }
        
        # 从测试输出中提取性能数据
        for test_file, result in self.results.items():
            output = result.get('stdout', '')
            
            if 'performance_optimization.py' in test_file:
                # 提取查询时间
                lines = output.split('\n')
                for line in lines:
                    if '查询:' in line and '秒' in line:
                        # 解析查询性能数据
                        try:
                            parts = line.split()
                            for i, part in enumerate(parts):
                                if '秒' in part:
                                    time_str = part.replace('秒', '')
                                    time_val = float(time_str)
                                    query_name = ' '.join(parts[:i])
                                    metrics['query_performance'][query_name] = time_val
                        except (ValueError, IndexError):
                            continue
                    
                    elif '并发查询总时间:' in line:
                        try:
                            time_val = float(line.split()[-1].replace('秒', ''))
                            metrics['concurrent_performance']['total_time'] = time_val
                        except ValueError:
                            pass
                    
                    elif '平均单个查询时间:' in line:
                        try:
                            time_val = float(line.split()[-1].replace('秒', ''))
                            metrics['concurrent_performance']['average_time'] = time_val
                        except ValueError:
                            pass
        
        return metrics
    
    def _generate_recommendations(self) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 基于测试结果生成建议
        total_failed = sum(result.get('failed', 0) for result in self.results.values())
        total_errors = sum(result.get('errors', 0) for result in self.results.values())
        
        if total_failed > 0:
            recommendations.append(f"发现 {total_failed} 个测试失败，需要修复相关功能")
        
        if total_errors > 0:
            recommendations.append(f"发现 {total_errors} 个测试错误，需要检查测试环境和代码")
        
        # 检查性能相关建议
        performance_result = self.results.get('tests/test_performance_optimization.py', {})
        if performance_result.get('status') != 'success':
            recommendations.append("性能测试未通过，建议检查数据库索引和查询优化")
        
        # 检查功能覆盖率
        feature_coverage = self._analyze_feature_coverage()
        if feature_coverage['coverage_percentage'] < 100:
            missing_features = [
                feature for feature, covered in feature_coverage['features'].items()
                if not covered
            ]
            recommendations.append(f"以下功能缺少测试覆盖: {', '.join(missing_features)}")
        
        # 通用建议
        recommendations.extend([
            "定期运行完整的测试套件以确保系统稳定性",
            "监控生产环境的查询性能，确保优化效果持续有效",
            "定期检查错误日志，及时发现和处理问题",
            "保持测试数据的更新，确保测试的相关性"
        ])
        
        return recommendations
    
    def _save_report(self, report: Dict[str, Any]):
        """保存测试报告"""
        import json
        
        # 保存JSON格式报告
        json_file = f'tests/optimization_test_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # 保存人类可读的报告
        text_file = f'tests/optimization_test_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        with open(text_file, 'w', encoding='utf-8') as f:
            self._write_text_report(f, report)
        
        logger.info(f"测试报告已保存: {json_file}, {text_file}")
    
    def _write_text_report(self, file, report: Dict[str, Any]):
        """写入文本格式报告"""
        file.write("系统优化功能测试报告\n")
        file.write("=" * 50 + "\n\n")
        
        # 总体摘要
        summary = report['summary']
        file.write("测试摘要:\n")
        file.write(f"  时间戳: {summary['timestamp']}\n")
        file.write(f"  总执行时间: {summary['total_duration']:.2f} 秒\n")
        file.write(f"  总测试数: {summary['total_tests']}\n")
        file.write(f"  通过: {summary['passed']}\n")
        file.write(f"  失败: {summary['failed']}\n")
        file.write(f"  错误: {summary['errors']}\n")
        file.write(f"  成功率: {summary['success_rate']:.1f}%\n")
        file.write(f"  总体状态: {summary['overall_status']}\n\n")
        
        # 功能覆盖率
        coverage = report['feature_coverage']
        file.write("功能覆盖率:\n")
        for feature, covered in coverage['features'].items():
            status = "✓" if covered else "✗"
            file.write(f"  {status} {feature}\n")
        file.write(f"  总覆盖率: {coverage['coverage_percentage']:.1f}%\n\n")
        
        # 性能指标
        if report['performance_metrics']['query_performance']:
            file.write("查询性能指标:\n")
            for query, time_val in report['performance_metrics']['query_performance'].items():
                file.write(f"  {query}: {time_val:.3f}秒\n")
            file.write("\n")
        
        # 详细结果
        file.write("详细测试结果:\n")
        for test_file, result in report['test_files'].items():
            file.write(f"\n{test_file}:\n")
            file.write(f"  状态: {result['status']}\n")
            file.write(f"  执行时间: {result['duration']:.2f}秒\n")
            file.write(f"  通过: {result.get('passed', 0)}\n")
            file.write(f"  失败: {result.get('failed', 0)}\n")
            file.write(f"  错误: {result.get('errors', 0)}\n")
            
            if result.get('stderr'):
                file.write(f"  错误输出: {result['stderr'][:200]}...\n")
        
        # 改进建议
        file.write("\n改进建议:\n")
        for i, recommendation in enumerate(report['recommendations'], 1):
            file.write(f"  {i}. {recommendation}\n")
    
    def run_specific_test_category(self, category: str) -> Dict[str, Any]:
        """运行特定类别的测试"""
        category_files = {
            'database': ['tests/test_optimization_features.py::TestDatabaseIndexOptimization'],
            'security': ['tests/test_optimization_features.py::TestFileSecurity'],
            'error_handling': ['tests/test_optimization_features.py::TestErrorCodeSystem'],
            'environment': ['tests/test_optimization_features.py::TestEnvironmentValidator'],
            'query_optimization': ['tests/test_query_helpers.py'],
            'performance': ['tests/test_performance_optimization.py']
        }
        
        if category not in category_files:
            raise ValueError(f"未知的测试类别: {category}")
        
        logger.info(f"运行 {category} 类别的测试")
        
        # 运行指定类别的测试
        for test_target in category_files[category]:
            result = self._run_single_test_file(test_target)
            self.results[test_target] = result
        
        return self.results


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='运行系统优化功能测试')
    parser.add_argument('--category', '-c', 
                       choices=['database', 'security', 'error_handling', 'environment', 'query_optimization', 'performance'],
                       help='运行特定类别的测试')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='详细输出')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    runner = OptimizationTestRunner()
    
    try:
        if args.category:
            results = runner.run_specific_test_category(args.category)
        else:
            results = runner.run_all_tests()
        
        # 打印简要结果
        print("\n" + "="*60)
        print("测试执行完成")
        print("="*60)
        
        summary = results.get('summary', {})
        if summary:
            print(f"总测试数: {summary.get('total_tests', 0)}")
            print(f"通过: {summary.get('passed', 0)}")
            print(f"失败: {summary.get('failed', 0)}")
            print(f"错误: {summary.get('errors', 0)}")
            print(f"成功率: {summary.get('success_rate', 0):.1f}%")
            print(f"总体状态: {summary.get('overall_status', 'UNKNOWN')}")
        
        return 0 if summary.get('overall_status') == 'PASS' else 1
        
    except Exception as e:
        logger.error(f"测试运行失败: {str(e)}")
        return 1


if __name__ == '__main__':
    sys.exit(main())