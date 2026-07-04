#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
森林防火巡逻系统 - 主控程序 v3.0
整合：火情检测 + 机器狗控制 + Web可视化面板

用法:
  python 主控.py                    # 真机模式
  python 主控.py --simulate         # 模拟模式(不连机器狗)
  python 主控.py --web-only         # 仅启动Web面板
  python 主控.py --port 8080        # 指定Web端口
  python 主控.py --no-web           # 不启动Web面板
"""

import os, sys, time, threading, json, argparse
from datetime import datetime

os.environ['ULTRALYTICS_API_URL'] = ''
os.environ['YOLO_VERBOSE'] = 'False'

# ======================== 配置加载 ========================
def 加载配置(path='配置.yaml'):
    """从YAML配置文件读取参数"""
    import yaml
    try:
        with open(path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        print(f"[配置] 已加载: {path}")
        return cfg
    except FileNotFoundError:
        print(f"[配置] 未找到 {path}，使用默认配置")
        return {
            'model_path': 'E:/zy/runs/detect/train-2/weights/best.pt',
            'conf_thresh': 0.5, 'detect_interval': 0.2,
            'camera_url': 0, 'frame_width': 640, 'frame_height': 480,
            'motion_ip': '192.168.1.120', 'cmd_port': 43893, 'state_port': 43894,
            'forward_speed': 20000, 'safe_dist': 0.5, 'sensor_type': 'ultrasonic',
            'http_host': '0.0.0.0', 'http_port': 5000,
        }

# ======================== 核心调度 ========================
class 巡逻控制器:
    def __init__(self, cfg, 模拟=False):
        self.cfg = cfg
        self.模拟 = 模拟

        # 导入模块
        from 机器人.机器狗控制 import DogController
        from 检测.火情检测 import PerceptionSystem

        self.感知 = PerceptionSystem(
            model_path=cfg['model_path'],
            camera_url=cfg['camera_url'],
            conf_thresh=cfg['conf_thresh'],
            detect_interval=cfg['detect_interval'],
            frame_width=cfg['frame_width'],
            frame_height=cfg['frame_height'],
        )
        self.狗 = DogController(
            ip=cfg['motion_ip'],
            cmd_port=cfg['cmd_port'],
            state_port=cfg['state_port'],
        )
        self.运行中 = False
        self.自动模式 = False
        self.日志 = []
        self.启动时间 = time.time()

    def 启动(self):
        print("=" * 50)
        print("  森林防火巡逻系统 v3.0")
        print("=" * 50)
        if not self.感知.start():
            print("[系统] 摄像头启动失败")
        if not self.模拟:
            if self.狗.connect():
                self.狗.stand_up()
                print("[系统] 机器狗已连接")
            else:
                print("[系统] 机器狗未连接")
        else:
            print("[系统] 模拟模式")
        self.运行中 = True
        print("[系统] 启动完成")

    def 停止(self):
        self.运行中 = False
        self.感知.stop()
        if not self.模拟:
            self.狗.close()

    def 切换巡逻(self, 开启):
        if 开启:
            self.狗.start_patrol(self.cfg.get('forward_speed', 20000))
            self.自动模式 = True
            self._记录('开始自动巡逻')
        else:
            self.狗.stop_patrol()
            self.自动模式 = False
            self._记录('停止巡逻')

    def _记录(self, msg):
        t = datetime.now().strftime('%H:%M:%S')
        self.日志.append({'time': t, 'msg': msg})
        if len(self.日志) > 100:
            self.日志.pop(0)
        print(f"[{t}] {msg}")

    def 心跳(self):
        """主循环 - 每次调用执行一次巡检"""
        if not self.运行中:
            return

        p = self.感知.get_result()
        level = p.alert_level
        狗状态 = self.狗.state

        if self.自动模式 and (self.模拟 or 狗状态.get('connected', False)):
            # 检测到火焰 → 急停
            if level >= 3 and 狗状态['mode'] != 'alert':
                self.狗.alert()
                self._记录("检测到火焰！紧急停止")

            # 检测到烟雾 → 暂停前进
            elif level == 2 and 狗状态['mode'] == 'patrolling':
                self.狗.stop_patrol()
                self._记录("检测到烟雾，暂停")
                time.sleep(1)
                self.狗.start_patrol(self.cfg.get('forward_speed', 20000))

            # 检测到烟头
            elif level == 1 and 狗状态['mode'] == 'patrolling':
                self._记录("发现烟头")

            # 超声波避障
            if self.cfg.get('sensor_type') == 'ultrasonic':
                dist = 狗状态.get('forward_distance', 4.5)
                if 狗状态['mode'] == 'patrolling' and dist < self.cfg.get('safe_dist', 0.5):
                    self.狗.perform_avoidance()
                    self._记录(f"避障 {dist:.2f}m")

    def 获取状态(self):
        p = self.感知.get_result()
        return {
            '系统': {
                '运行时长': time.time() - self.启动时间,
                '运行中': self.运行中,
                '自动模式': self.自动模式,
                '模拟': self.模拟,
            },
            '火情': {
                '火焰': p.fire, '烟雾': p.smoke, '烟头': p.cigarette,
                '警报等级': p.alert_level,
                '检测数': len(p.detections),
            },
            '机器狗': dict(self.狗.state),
            '日志': self.日志[-20:],
        }


# ======================== Web面板 ========================
def 创建网页应用(控制器):
    try:
        from flask import Flask, jsonify, request
    except ImportError:
        print("[Web] 请安装 flask: pip install flask --break-system-packages")
        return None

    app = Flask(__name__)
    根目录 = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(根目录, '面板', 'web_dashboard.html')

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


# ======================== 主入口 ========================
def main():
    parser = argparse.ArgumentParser(description='森林防火巡逻系统')
    parser.add_argument('--simulate', action='store_true', help='模拟模式(不连机器狗)')
    parser.add_argument('--web-only', action='store_true', help='仅启动Web面板')
    parser.add_argument('--port', type=int, default=0, help='Web面板端口')
    parser.add_argument('--no-web', action='store_true', help='不启动Web面板')
    args = parser.parse_args()

    # 加载配置
    cfg = 加载配置()
    if args.port:
        cfg['http_port'] = args.port

    # 创建控制器
    控制器 = 巡逻控制器(cfg, 模拟=args.simulate)
    if not args.web_only:
        控制器.启动()

    # 启动Web面板
    if not args.no_web:
        app = 创建网页应用(控制器)
        if app:
            print(f"[Web] http://localhost:{cfg['http_port']}")
            t = threading.Thread(
                target=lambda: app.run(
                    host=cfg['http_host'], port=cfg['http_port'],
                    threaded=True, debug=False, use_reloader=False
                ),
                daemon=True
            )
            t.start()

    # 主循环
    try:
        while True:
            if not args.web_only and 控制器.运行中:
                控制器.心跳()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[系统] 用户退出")
    finally:
        if not args.web_only:
            控制器.停止()

    print("[系统] 已关闭")


if __name__ == '__main__':
    try:
        import cv2
    except ImportError:
        print("请安装 opencv-python: pip install opencv-python --break-system-packages")
        sys.exit(1)
    main()
