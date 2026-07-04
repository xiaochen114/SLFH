#!/usr/bin/env python3
"""中央大脑 Web 面板 — 机器人状态展示、指令下发、巡逻管理"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json, threading, time
from flask import Flask, jsonify, request, Response
from 中央大脑.brain_registry import 机器人注册中心
from 中央大脑.brain_comm import 通信管理器
from 机器人.robot_base import RobotOrder


class Web面板:
    """中央大脑的 HTTP API + 前端"""

    def __init__(self, registry, comm, host="0.0.0.0", port=5000, patrol=None):
        self._registry = registry
        self._comm = comm
        self._host = host
        self._port = port
        self._patrol = patrol
        self._app = Flask(__name__)
        self._app.add_url_rule("/", "index", self._index)
        self._app.add_url_rule("/api/status", "api_status", self._api_status)
        self._app.add_url_rule("/api/robot/<robot_id>", "api_robot", self._api_robot)
        self._app.add_url_rule("/api/command", "api_command", self._api_command, methods=["POST"])
        self._app.add_url_rule("/api/video_feed/<robot_id>", "video_feed", self._video_feed)
        self._app.add_url_rule("/api/patrol/points", "patrol_points", self._patrol_points)
        self._app.add_url_rule("/api/patrol/points", "patrol_add_point", self._patrol_add_point, methods=["POST"])
        self._app.add_url_rule("/api/patrol/points/<int:index>", "patrol_delete_point", self._patrol_delete_point, methods=["DELETE"])
        self._app.add_url_rule("/api/patrol/start", "patrol_start", self._patrol_start, methods=["POST"])
        self._app.add_url_rule("/api/patrol/stop", "patrol_stop", self._patrol_stop, methods=["POST"])
        self._app.add_url_rule("/api/patrol/status", "patrol_status", self._patrol_status)

    def 启动(self):
        print(f"[Web面板] http://{self._host}:{self._port}")
        self._app.run(host=self._host, port=self._port, threaded=True, debug=False, use_reloader=False)

    # ---- 页面 ----

    def _index(self):
        html = os.path.join(os.path.dirname(__file__), "..", "面板", "web_dashboard.html")
        if os.path.exists(html):
            return open(html, "r", encoding="utf-8").read()
        return "<h1>web_dashboard.html not found</h1>"

    # ---- API: 状态 ----

    def _api_status(self):
        return jsonify(self._registry.导出全景())

    def _api_robot(self, robot_id):
        robot = self._registry.获取机器人(robot_id)
        if not robot:
            return jsonify({"ok": False, "msg": "not found"}), 404
        return jsonify({"ok": True, "status": robot.get_status().__dict__})

    # ---- API: 指令 ----

    def _api_command(self):
        d = request.get_json()
        rid = d.get("robot_id", "")
        cmd = d.get("command", "")
        robot = self._registry.获取机器人(rid)
        if not robot:
            return jsonify({"ok": False, "msg": "not found"}), 404
        order = RobotOrder(
            order_id=f"web_{int(time.time())}", type=cmd,
            params=d.get("params", {}), priority=d.get("priority", 0), source="web",
        )
        ok = self._comm.发送指令(rid, order)
        return jsonify({"ok": ok, "msg": f"exec {cmd}"})

    # ---- API: 视频流 ----

    def _video_feed(self, robot_id):
        robot = self._registry.获取机器人(robot_id)
        if not robot:
            return "not found", 404

        def 生成帧():
            while True:
                frame = robot.get_video_frame()
                if frame:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                time.sleep(1.0 / (robot.get_video_fps() or 5))

        return Response(生成帧(), mimetype="multipart/x-mixed-replace; boundary=frame")

    # ---- API: 巡逻 ----

    def _patrol_points(self):
        if not self._patrol:
            return jsonify([])
        return jsonify(self._patrol.获取点列表())

    def _patrol_add_point(self):
        d = request.get_json()
        if not self._patrol:
            return jsonify({"ok": False, "msg": "巡逻模块未启用"})
        self._patrol.添加点(d["x"], d["y"], d.get("yaw", 0), d.get("name", ""))
        return jsonify({"ok": True})

    def _patrol_delete_point(self, index):
        if not self._patrol:
            return jsonify({"ok": False})
        self._patrol.删除点(index)
        return jsonify({"ok": True})

    def _patrol_start(self):
        if not self._patrol:
            return jsonify({"ok": False, "msg": "巡逻未启用"})
        ok = self._patrol.开始巡逻()
        return jsonify({"ok": ok})

    def _patrol_stop(self):
        if self._patrol:
            self._patrol.停止巡逻()
        return jsonify({"ok": True})

    def _patrol_status(self):
        if not self._patrol:
            return jsonify({"巡逻运行中": False})
        return jsonify(self._patrol.获取状态())
