#!/usr/bin/env python3
"""
备份系统健康检查API端点
提供REST API接口用于监控备份系统的健康状态
"""

import json
import os
from datetime import datetime
from flask import Flask, jsonify, request
from pathlib import Path

try:
    from .backup_manager_v2 import BackupManager, get_logger
    from config.backup_config import get_backup_config
except ImportError:
    # 如果无法导入，使用相对导入
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from backup_manager_v2 import BackupManager, get_logger
    from config.backup_config import get_backup_config


class BackupHealthAPI:
    """备份健康检查API类"""
    
    def __init__(self, app=None, backup_manager=None):
        """
        初始化健康检查API
        
        Args:
            app: Flask应用实例
            backup_manager: 备份管理器实例
        """
        self.app = app
        self.backup_manager = backup_manager or self._create_backup_manager()
        self.logger = get_logger()
        
        if app is not None:
            self.init_app(app)
    
    def _create_backup_manager(self):
        """创建默认的备份管理器"""
        try:
            return BackupManager()
        except Exception as e:
            self.logger.error(f"创建备份管理器失败: {e}")
            return None
    
    def init_app(self, app):
        """初始化Flask应用"""
        self.app = app
        self._register_routes()
    
    def _register_routes(self):
        """注册API路由"""
        
        @self.app.route('/api/backup/health', methods=['GET'])
        def get_health_status():
            """获取系统整体健康状态"""
            try:
                if not self.backup_manager:
                    return jsonify({
                        'status': 'error',
                        'message': '备份管理器未初始化',
                        'timestamp': datetime.now().isoformat()
                    }), 500
                
                health_status = self.backup_manager.get_health_status()
                
                # 添加API信息
                health_status['api_version'] = '2.0'
                health_status['timestamp'] = datetime.now().isoformat()
                
                # 根据状态返回适当的HTTP状态码
                http_status = {
                    'healthy': 200,
                    'warning': 200,
                    'error': 503
                }.get(health_status.get('overall_status'), 500)
                
                return jsonify(health_status), http_status
                
            except Exception as e:
                self.logger.error(f"健康检查API错误: {e}")
                return jsonify({
                    'status': 'error',
                    'message': f'健康检查失败: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        @self.app.route('/api/backup/stats', methods=['GET'])
        def get_backup_stats():
            """获取备份统计信息"""
            try:
                if not self.backup_manager:
                    return jsonify({
                        'error': '备份管理器未初始化'
                    }), 500
                
                stats = self.backup_manager.get_backup_stats()
                
                # 格式化统计信息
                formatted_stats = self._format_stats(stats)
                formatted_stats['timestamp'] = datetime.now().isoformat()
                
                return jsonify(formatted_stats)
                
            except Exception as e:
                self.logger.error(f"统计信息API错误: {e}")
                return jsonify({
                    'error': f'获取统计信息失败: {str(e)}'
                }), 500
        
        @self.app.route('/api/backup/list', methods=['GET'])
        def list_backups():
            """列出所有备份文件"""
            try:
                if not self.backup_manager:
                    return jsonify({
                        'error': '备份管理器未初始化'
                    }), 500
                
                # 获取查询参数
                limit = request.args.get('limit', type=int)
                offset = request.args.get('offset', 0, type=int)
                
                backups = self.backup_manager.list_backups()
                
                # 应用分页
                if limit:
                    total = len(backups)
                    backups = backups[offset:offset+limit]
                    pagination_info = {
                        'total': total,
                        'limit': limit,
                        'offset': offset,
                        'has_more': offset + limit < total
                    }
                else:
                    pagination_info = {'total': len(backups)}
                
                # 格式化备份信息
                formatted_backups = []
                for backup in backups:
                    formatted_backup = {
                        'filename': backup['filename'],
                        'size_bytes': backup['size'],
                        'size_mb': round(backup['size'] / 1024 / 1024, 2),
                        'created_at': backup['created_at'].isoformat(),
                        'is_compressed': backup['is_compressed'],
                        'age_hours': round((datetime.now() - backup['created_at']).total_seconds() / 3600, 1)
                    }
                    formatted_backups.append(formatted_backup)
                
                return jsonify({
                    'backups': formatted_backups,
                    'pagination': pagination_info,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"备份列表API错误: {e}")
                return jsonify({
                    'error': f'获取备份列表失败: {str(e)}'
                }), 500
        
        @self.app.route('/api/backup/create', methods=['POST'])
        def create_backup():
            """创建新备份"""
            try:
                if not self.backup_manager:
                    return jsonify({
                        'error': '备份管理器未初始化'
                    }), 500
                
                # 获取请求参数
                data = request.get_json() or {}
                compress = data.get('compress', True)
                timeout = data.get('timeout', 300)
                
                # 创建备份
                backup_path, message = self.backup_manager.create_backup(
                    compress=compress,
                    timeout=timeout
                )
                
                if backup_path:
                    return jsonify({
                        'success': True,
                        'message': message,
                        'backup_filename': backup_path.name,
                        'backup_size': backup_path.stat().st_size,
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': message,
                        'timestamp': datetime.now().isoformat()
                    }), 400
                    
            except Exception as e:
                self.logger.error(f"创建备份API错误: {e}")
                return jsonify({
                    'success': False,
                    'error': f'创建备份失败: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        @self.app.route('/api/backup/verify/<filename>', methods=['GET'])
        def verify_backup(filename):
            """验证指定备份文件"""
            try:
                if not self.backup_manager:
                    return jsonify({
                        'error': '备份管理器未初始化'
                    }), 500
                
                is_valid, message = self.backup_manager.verify_backup(filename)
                
                return jsonify({
                    'filename': filename,
                    'is_valid': is_valid,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"验证备份API错误: {e}")
                return jsonify({
                    'error': f'验证备份失败: {str(e)}'
                }), 500
        
        @self.app.route('/api/backup/cleanup', methods=['POST'])
        def cleanup_backups():
            """清理旧备份"""
            try:
                if not self.backup_manager:
                    return jsonify({
                        'error': '备份管理器未初始化'
                    }), 500
                
                # 获取请求参数
                data = request.get_json() or {}
                keep_days = data.get('keep_days')
                
                deleted_count = self.backup_manager.cleanup_old_backups(keep_days)
                
                return jsonify({
                    'success': True,
                    'deleted_count': deleted_count,
                    'message': f'成功清理了 {deleted_count} 个旧备份',
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"清理备份API错误: {e}")
                return jsonify({
                    'success': False,
                    'error': f'清理备份失败: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        @self.app.route('/api/backup/config', methods=['GET'])
        def get_backup_config():
            """获取备份配置信息"""
            try:
                config = get_backup_config()
                
                config_dict = config.to_dict()
                config_dict['timestamp'] = datetime.now().isoformat()
                
                return jsonify(config_dict)
                
            except Exception as e:
                self.logger.error(f"获取配置API错误: {e}")
                return jsonify({
                    'error': f'获取配置失败: {str(e)}'
                }), 500
        
        @self.app.route('/ping', methods=['GET'])
        def ping():
            """简单的存活检查端点"""
            return jsonify({
                'status': 'ok',
                'service': 'backup-api',
                'timestamp': datetime.now().isoformat()
            })
    
    def _format_stats(self, stats):
        """格式化统计信息"""
        formatted = {
            'total_backups': stats['total_backups'],
            'compressed_backups': stats['compressed_count'],
            'total_size': {
                'bytes': stats['total_size'],
                'mb': round(stats['total_size'] / 1024 / 1024, 2),
                'gb': round(stats['total_size'] / 1024 / 1024 / 1024, 3)
            },
            'average_size': {
                'bytes': stats['average_size'],
                'mb': round(stats['average_size'] / 1024 / 1024, 2)
            },
            'compression_savings': {
                'bytes': stats['compression_savings'],
                'mb': round(stats['compression_savings'] / 1024 / 1024, 2)
            }
        }
        
        if stats['oldest_backup']:
            formatted['oldest_backup'] = {
                'filename': stats['oldest_backup']['filename'],
                'created_at': stats['oldest_backup']['created_at'].isoformat(),
                'age_days': (datetime.now() - stats['oldest_backup']['created_at']).days
            }
        
        if stats['newest_backup']:
            formatted['newest_backup'] = {
                'filename': stats['newest_backup']['filename'],
                'created_at': stats['newest_backup']['created_at'].isoformat(),
                'age_hours': round((datetime.now() - stats['newest_backup']['created_at']).total_seconds() / 3600, 1)
            }
        
        return formatted


def create_health_app(backup_manager=None):
    """创建独立的健康检查Flask应用"""
    app = Flask(__name__)
    
    # 配置CORS（如果需要）
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
    
    # 初始化健康检查API
    health_api = BackupHealthAPI(app, backup_manager)
    
    return app


def run_health_server(host='0.0.0.0', port=5001, debug=False):
    """运行独立的健康检查服务器"""
    app = create_health_app()
    
    print(f"启动备份健康检查服务器...")
    print(f"访问地址: http://{host}:{port}")
    print(f"健康检查: http://{host}:{port}/api/backup/health")
    print(f"API文档: http://{host}:{port}/ping")
    
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='备份健康检查API服务器')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=5001, help='监听端口')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    run_health_server(args.host, args.port, args.debug)