#!/usr/bin/env python3
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json, threading, time
from flask import Flask, jsonify, request, Response
from 中央大脑.brain_registry import 机器人注册中心
from 中央大脑.brain_comm import 通信管理器
from 机器人.robot_base import RobotOrder

class Web面板:
    def __init__(self, registry, comm, host="0.0.0.0", port=5000, patrol=None):
        self._registry = registry
        self._comm = comm
        self._host = host
        self._port = port
        self._patrol = patrol
        self._app = Flask(__name__)
        self._html = os.path.join(os.path.dirname(__file__), "..", "web_dashboard.html")
        self._app.add_url_rule("/", "index", self._index)
        self._app.add_url_rule("/api/status", "api_status", self._api_status)
        self._app.add_url_rule("/api/command", "api_command", self._api_command, methods=["POST"])
        self._app.add_url_rule("/api/register", "api_register", self._api_register, methods=["POST"])
        self._app.add_url_rule("/api/video_feed/<robot_id>", "video_feed", self._video_feed)
        # 巡逻API
        self._app.add_url_rule("/api/patrol/points", "patrol_points", self._patrol_points)
        self._app.add_url_rule("/api/patrol/points", "patrol_add_point", self._patrol_add_point, methods=["POST"])
        self._app.add_url_rule("/api/patrol/points/<int:index>", "patrol_delete_point", self._patrol_delete_point, methods=["DELETE"])
        self._app.add_url_rule("/api/patrol/start", "patrol_start", self._patrol_start, methods=["POST"])
        self._app.add_url_rule("/api/patrol/stop", "patrol_stop", self._patrol_stop, methods=["POST"])
        self._app.add_url_rule("/api/patrol/status", "patrol_status", self._patrol_status)

    def _index(self):
        if os.path.exists(self._html):
            return open(self._html, "r", encoding="utf-8").read()
        return "<h1>web_dashboard.html not found</h1>"

    def _api_status(self):
        return jsonify(self._registry.导出全景())

    def _api_command(self):
        d = request.get_json()
        rid = d.get("robot_id", "")
        cmd = d.get("command", "")
        r = self._registry.获取机器人(rid)
        if not r:
            return jsonify({"ok": False, "msg": "not found"}), 404
        order = RobotOrder(order_id=f"web_{int(time.time())}", type=cmd, params=d.get("params", {}), priority=d.get("priority", 0), source="web")
        ok = self._comm.发送指令(rid, order)
        return jsonify({"ok": ok, "msg": f"exec {cmd}"})

    def _api_register(self):
        d = request.get_json()
        a = d.get("action", "status")
        if a == "status":
            r = self._registry.获取机器人(d.get("robot_id", ""))
            if r:
                return jsonify({"ok": True, "status": r.get_status().__dict__})
            return jsonify({"ok": False, "msg": "unregistered"}), 404
        return jsonify({"ok": False, "msg": f"unknown {a}"})

    def _video_feed(self, robot_id):
        robot = self._registry.获取机器人(robot_id)
        if not robot:
            return "not found", 404
        fps = robot.get_video_fps() or 5
 