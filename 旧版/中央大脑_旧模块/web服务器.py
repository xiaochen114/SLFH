#!/usr/bin/env python3
"""Web 服务器 — 森林防火巡逻系统的后端 API"""
import os, json, threading, time
from flask import Flask, jsonify, request


def 创建网页应用(控制器):
    """为巡逻控制器创建 Flask Web 应用"""
    try:
        from flask import Flask, jsonify, request
    except ImportError:
        print("[Web] 请安装 flask: pip install flask --break-system-packages")
        return None

    app = Flask(__name__)
    根目录 = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(根目录, 'web_dashboard.html')

    @app.route('/')
    def index():
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                return f.read()
        return '<h1>请确保 web_dashboard.html 存在</h1>'

    @app.route('/api/status')
    def api_status():
        return jsonify(控制器.获取状态())

    @app.route('/api/patrol', methods=['POST'])
    def api_patrol():
        d = request.get_json()
        控制器.切换巡逻(d.get('enable', False))
        return jsonify({'ok': True})

    @app.route('/api/command', methods=['POST'])
    def api_command():
        cmd = request.get_json().get('command', '')
        狗 = 控制器.狗
        指令 = {
            'stand':     lambda: 狗.stand_up(),
            'lie':       lambda: 狗.lie_down(),
            'estop':     lambda: 狗.emergency_stop(),
            'home':      lambda: 狗.go_home(),
            'forward':   lambda: 狗.start_patrol(),
            'stop':      lambda: 狗.stop_patrol(),
        }
        if cmd in 指令:
            指令[cmd]()
            return jsonify({'ok': True, 'msg': f'执行 {cmd}'})
        return jsonify({'ok': False, 'msg': f'未知指令: {cmd}'}), 400

    return app


def 创建中央大脑Web应用(脑):
    """为中央大脑创建 Flask Web 应用"""
    app = Flask(__name__)
    html_path = os.path.join(os.path.dirname(__file__), '..', 'web_dashboard.html')

    @app.route('/')
    def index():
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                return f.read()
        return '<h1>中央大脑面板</h1>'

    @app.route('/api/status')
    def api_status():
        return jsonify(脑.registry.导出全景())

    @app.route('/api/command', methods=['POST'])
    def api_command():
        d = request.get_json()
        rid = d.get('robot_id', '')
        cmd = d.get('command', '')
        r = 脑.registry.获取机器人(rid)
        if not r:
            return jsonify({'ok': False, 'msg': 'not found'}), 404
        from 机器人.robot_base import RobotOrder
        order = RobotOrder(order_id=f'web_{int(time.time())}', type=cmd,
                           params=d.get('params', {}), priority=d.get('priority', 0), source='web')
        ok = 脑.comm.发送指令(rid, order)
        return jsonify({'ok': ok, 'msg': f'exec {cmd}'})

    @app.route('/api/patrol/start', methods=['POST'])
    def patrol_start():
        if 脑.patrol:
            ok = 脑.patrol.开始巡逻()
            return jsonify({'ok': ok})
        return jsonify({'ok': False, 'msg': '巡逻未启用'})

    @app.route('/api/patrol/stop', methods=['POST'])
    def patrol_stop():
        if 脑.patrol:
            脑.patrol.停止巡逻()
            return jsonify({'ok': True})
        return jsonify({'ok': False})

    @app.route('/api/patrol/points')
    def patrol_points():
        if 脑.patrol:
            return jsonify(脑.patrol.获取点列表())
        return jsonify([])

    @app.route('/api/patrol/status')
    def patrol_status():
        if 脑.patrol:
            return jsonify(脑.patrol.获取状态())
        return jsonify({'巡逻运行中': False})

    return app
