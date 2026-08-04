#!/usr/bin/env python3
"""
中央大脑 Web 面板 — 统一 RESTful API + SSE 实时推送
API 版本 v1，统一响应格式: {code, message, data}
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json, threading, time
from flask import Flask, jsonify, request, Response
from 中央大脑.brain_registry import 机器人注册中心
from 中央大脑.brain_comm import 通信管理器
from 中央大脑.事件总线 import 事件总线
from 机器人.robot_base import RobotOrder


# ======================== 工具函数 ========================

def ok(data=None, message="success"):
    return jsonify({"code": 200, "message": message, "data": data})


def fail(code=400, message="error", data=None):
    return jsonify({"code": code, "message": message, "data": data}), code




# ======================== Web 面板 ========================

class Web面板:
    """中央大脑 HTTP API v1 + SSE 实时推送"""

    def __init__(self, registry, comm, db=None, 告警=None, event_bus=None, host="0.0.0.0", port=5000, patrol=None, llm=None, 自愈=None, 记忆=None, 大脑=None):
        self._registry = registry
        self._comm = comm
        self._db = db
        self._告警 = 告警
        self._llm = llm
        self._自愈 = 自愈
        self._记忆 = 记忆
        self._大脑 = 大脑
        self._event_bus = event_bus or 事件总线()
        self._host = host
        self._port = port
        self._patrol = patrol
        self._app = Flask(__name__)
        self._注册路由()

    def _注册路由(self):
        """注册所有 API 路由"""
        a = self._app
        # 页面
        a.add_url_rule("/", "index", self._index)

        # API v1 - 状态
        a.add_url_rule("/api/v1/status", "api_status", self._api_status)
        a.add_url_rule("/api/v1/robots", "api_robots", self._api_robots)
        a.add_url_rule("/api/v1/robots/<robot_id>", "api_robot", self._api_robot)

        # API v1 - 指令
        a.add_url_rule("/api/v1/command", "api_command", self._api_command, methods=["POST"])
        a.add_url_rule("/api/v1/robots/<robot_id>/command", "api_robot_cmd",
                       self._api_robot_cmd, methods=["POST"])

        # API v1 - 视频
        a.add_url_rule("/api/v1/robots/<robot_id>/video", "api_video", self._api_video)

        # API v1 - 注册（外部机器人接入）
        a.add_url_rule("/api/v1/robots/<robot_id>/register", "api_register",
                       self._api_register, methods=["POST"])

        # API v1 - SSE 实时事件
        a.add_url_rule("/api/v1/events", "api_events", self._api_events)

        # API v1 - 健康检查
        a.add_url_rule("/api/v1/health", "api_health", self._api_health)

        # API v1 - 历史数据
        a.add_url_rule("/api/v1/history/robots", "hist_robots", self._hist_robots)
        a.add_url_rule("/api/v1/history/tasks", "hist_tasks", self._hist_tasks)
        a.add_url_rule("/api/v1/history/patrol", "hist_patrol", self._hist_patrol)
        a.add_url_rule("/api/v1/history/stats", "hist_stats", self._hist_stats)

        # API v1 - 告警
        a.add_url_rule("/api/v1/alerts", "api_alerts", self._api_alerts)
        a.add_url_rule("/api/v1/alerts/stats", "api_alert_stats", self._api_alert_stats)

        # API v1 - 巡逻
        a.add_url_rule("/api/v1/patrol/points", "patrol_points", self._patrol_points)
        a.add_url_rule("/api/v1/patrol/points", "patrol_add",
                       self._patrol_add, methods=["POST"])
        a.add_url_rule("/api/v1/patrol/points/<int:index>", "patrol_del",
                       self._patrol_del, methods=["DELETE"])
        a.add_url_rule("/api/v1/patrol/start", "patrol_start",
                       self._patrol_start, methods=["POST"])
        a.add_url_rule("/api/v1/patrol/stop", "patrol_stop",
                       self._patrol_stop, methods=["POST"])
        a.add_url_rule("/api/v1/patrol/status", "patrol_status", self._patrol_status)

        # API v1 - LLM 状态 / 决策日志 / 对话 / 接管
        a.add_url_rule("/api/v1/llm/status", "llm_status", self._llm_status)
        a.add_url_rule("/api/v1/llm/history", "llm_history", self._llm_history)
        a.add_url_rule("/api/v1/chat/history", "chat_history", self._chat_history)
        a.add_url_rule("/api/v1/chat/send", "chat_send", self._chat_send, methods=["POST"])
        a.add_url_rule("/api/v1/orders/pending", "orders_pending", self._orders_pending)
        a.add_url_rule("/api/v1/orders/confirm", "orders_confirm", self._orders_confirm, methods=["POST"])
        a.add_url_rule("/api/v1/orders/intervene", "orders_intervene", self._orders_intervene, methods=["POST"])
        a.add_url_rule("/api/v1/intervention/history", "intervention_history", self._intervention_history)

        # API v1 - 自愈
        a.add_url_rule("/api/v1/selfheal/status", "selfheal_status", self._selfheal_status)
        a.add_url_rule("/api/v1/selfheal/pending", "selfheal_pending", self._selfheal_pending)
        a.add_url_rule("/api/v1/selfheal/confirm", "selfheal_confirm", self._selfheal_confirm, methods=["POST"])
        a.add_url_rule("/api/v1/selfheal/history", "selfheal_history", self._selfheal_history)

        # 兼容旧版 API
        a.add_url_rule("/api/status", "old_status", self._api_status)

    # ======================== 页面 ========================

    def _index(self):
        html = os.path.join(os.path.dirname(__file__), "..", "面板", "web_dashboard.html")
        if os.path.exists(html):
            return open(html, "r", encoding="utf-8").read()
        return "<h1>中央大脑 · 仪表盘</h1><p>web_dashboard.html 未找到</p>"

    # ======================== API v1: 状态 ========================

    def _api_health(self):
        return ok({"status": "running", "time": time.time()})

    def _llm_status(self):
        """LLM 连接状态（是否降级）"""
        if self._llm:
            return ok(self._llm.获取状态())
        # 无 LLM 引擎时从数据库读上次状态
        if self._db:
            return ok(self._db.读取配置("llm_status", {"mode": "unknown"}))
        return ok({"mode": "unknown"})

    # ======================== API v1: LLM 决策日志 ========================

    def _llm_history(self):
        """最近 LLM 决策记录（指挥台流水）"""
        if not self._db:
            return ok([])
        return ok(self._db.查询LLM决策(limit=50))

    # ======================== API v1: 操作员↔LLM 对话 ========================

    def _chat_history(self):
        """对话历史"""
        if not self._记忆:
            return ok([])
        return ok(self._记忆.取对话历史(50))

    def _chat_send(self):
        """操作员发消息给 LLM，LLM 回复（可附带待确认指令）"""
        d = request.get_json(silent=True) or {}
        content = d.get("content", "").strip()
        if not content:
            return fail(400, "消息不能为空")
        if not self._llm or not self._db:
            return fail(400, "LLM 或数据库未启用")

        # 1. 记录操作员消息
        self._db.记录对话("operator", content)
        # 2. 构建带记忆的上下文
        prompt = self._记忆.构建上下文(content) if self._记忆 else content
        # 3. 调 LLM（半自动：返回自然语言回复 + 可选指令，不直接下发）
        结果 = self._llm.对话(prompt)
        if 结果.get("error"):
            return fail(500, f"LLM 调用失败: {结果['error']}")
        回复文本 = 结果.get("reply", "")
        指令列表 = 结果.get("orders", []) or []

        # 4. 半自动：指令进待确认队列，不直接下发
        if 指令列表:
            self._db.记录对话("llm", 回复文本, 指令列表)
            for 指令 in 指令列表:
                if 指令.get("robot_id"):
                    self._db.添加待确认(指令["robot_id"], 指令, source="llm")
            return ok({"reply": 回复文本, "orders": 指令列表, "pending": True})
        self._db.记录对话("llm", 回复文本, [])
        return ok({"reply": 回复文本, "orders": []})

    # ======================== API v1: 待确认 / 接管 ========================

    def _orders_pending(self):
        """待确认指令列表（对话转指令/接管）"""
        if not self._db:
            return ok([])
        return ok(self._db.查询待确认(20))

    def _orders_confirm(self):
        """确认/拒绝/修改待确认指令"""
        d = request.get_json(silent=True) or {}
        pid = d.get("id")
        action = d.get("action", "confirm")  # confirm / reject / modified
        if not pid:
            return fail(400, "缺少指令 id")
        if not self._db:
            return fail(400, "数据库未启用")
        if action == "modified":
            new_order = d.get("order", {})
            self._db.处理待确认(pid, "modified", new_order)
        else:
            self._db.处理待确认(pid, "confirmed" if action == "confirm" else "rejected")
        # 审计
        self._db.记录干预(f"待确认_{action}", order={"id": pid})
        return ok(None, f"指令已{action}")

    def _orders_intervene(self):
        """操作员接管：拦截 LLM 决策并发布新指令"""
        d = request.get_json(silent=True) or {}
        robot_id = d.get("robot_id", "")
        指令 = d.get("command", "")
        params = d.get("params", {})
        reason = d.get("reason", "")
        if not robot_id or not 指令:
            return fail(400, "缺少 robot_id 或 command")
        from 机器人.robot_base import RobotOrder
        order = RobotOrder(
            order_id=f"op_{int(time.time())}", type=指令,
            params=params, priority=3, source="operator")
        ok_result = self._comm.发送指令(robot_id, order)
        # 审计
        self._db.记录干预("人工接管", robot_id, {
            "type": 指令, "params": params,
        }, reason)
        return ok({"ok": ok_result, "robot_id": robot_id, "command": 指令})

    def _intervention_history(self):
        """干预审计日志"""
        if not self._db:
            return ok([])
        return ok(self._db.查询干预日志(50))

    # ======================== API v1: 自愈 ========================

    def _selfheal_status(self):
        """自愈系统状态"""
        if not self._自愈:
            return ok({"诊断器": [], "待确认数": 0, "历史数": 0, "最近": []})
        return ok(self._自愈.获取状态())

    def _selfheal_pending(self):
        """待确认的高危操作列表"""
        if not self._自愈:
            return ok([])
        return ok(self._自愈.获取待确认())

    def _selfheal_confirm(self):
        """人工确认/拒绝高危操作"""
        if not self._自愈:
            return fail(400, "自愈模块未启用")
        d = request.get_json(silent=True) or {}
        index = d.get("index", -1)
        action = d.get("action", "approve")
        result = self._自愈.处理待确认(index, action)
        if result.get("ok"):
            return ok(result, f"高危操作{action}")
        return fail(400, result.get("msg", "操作失败"))

    def _selfheal_history(self):
        """自愈历史"""
        if not self._自愈:
            return ok([])
        limit = int(request.args.get("limit", 50))
        return ok(self._自愈.获取历史(limit))

    def _api_status(self):
        return ok(self._registry.导出全景())

    def _api_robots(self):
        robots = self._registry.获取所有机器人()
        return ok([{
            "id": r.robot_id,
            "connected": r.is_connected(),
            "capabilities": r.get_capabilities(),
        } for r in robots])

    def _api_robot(self, robot_id):
        robot = self._registry.获取机器人(robot_id)
        if not robot:
            return fail(404, f"机器人 {robot_id} 未注册")
        try:
            return ok({"status": robot.get_status().__dict__, "capabilities": robot.get_capabilities()})
        except Exception as e:
            return fail(500, f"获取状态失败: {e}")

    # ======================== API v1: 指令 ========================

    def _api_command(self):
        d = request.get_json(silent=True) or {}
        rid = d.get("robot_id", "")
        cmd = d.get("command", "")
        if not rid or not cmd:
            return fail(400, "robot_id 和 command 不能为空")
        robot = self._registry.获取机器人(rid)
        if not robot:
            return fail(404, f"机器人 {rid} 未注册")
        order = RobotOrder(
            order_id=f"web_{int(time.time())}", type=cmd,
            params=d.get("params", {}), priority=d.get("priority", 0), source="web",
        )
        ok_result = self._comm.发送指令(rid, order)
        if ok_result:
            self._event_bus.发布("command", {"robot_id": rid, "command": cmd, "result": "ok"})
            return ok({"robot_id": rid, "command": cmd}, f"指令 {cmd} 执行成功")
        return ok({"robot_id": rid, "command": cmd}, f"指令 {cmd} 已下发（机器人可能离线）")

    def _api_robot_cmd(self, robot_id):
        d = request.get_json(silent=True) or {}
        cmd = d.get("command", "")
        if not cmd:
            return fail(400, "command 不能为空")
        robot = self._registry.获取机器人(robot_id)
        if not robot:
            return fail(404, f"机器人 {robot_id} 未注册")
        order = RobotOrder(
            order_id=f"web_{int(time.time())}", type=cmd,
            params=d.get("params", {}), priority=d.get("priority", 0), source="web",
        )
        ok_result = self._comm.发送指令(robot_id, order)
        return ok({"robot_id": robot_id, "command": cmd})

    # ======================== API v1: 机器人注册 ========================

    def _api_register(self, robot_id):
        """接收外部机器人注册（POST）"""
        d = request.get_json(silent=True) or {}
        action = d.get("action", "status")
        if action == "status":
            r = self._registry.获取机器人(robot_id)
            if r:
                return ok({"id": robot_id, "status": r.get_status().__dict__})
            return fail(404, "未注册")
        return fail(400, f"未知 action: {action}")

    # ======================== API v1: 视频 ========================

    def _api_video(self, robot_id):
        robot = self._registry.获取机器人(robot_id)
        if not robot:
            return "not found", 404

        def 生成帧():
            while True:
                frame = robot.get_video_frame()
                if frame:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                time.sleep(1.0 / (robot.get_video_fps() or 5))

        return Response(生成帧(), mimetype="multipart/x-mixed-replace; boundary=frame")

    # ======================== API v1: SSE 实时事件 ========================

    def _api_events(self):
        """SSE 实时事件流 — 客户端用 EventSource 连接"""
        return Response(
            self._event_bus.sse_生成(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ======================== API v1: 历史数据 ========================

    def _hist_robots(self):
        if not self._db:
            return fail(400, "数据库未启用")
        robot_id = request.args.get("robot_id")
        limit = int(request.args.get("limit", 100))
        return ok(self._db.查询状态历史(robot_id, limit))

    def _hist_tasks(self):
        if not self._db:
            return fail(400, "数据库未启用")
        robot_id = request.args.get("robot_id")
        limit = int(request.args.get("limit", 100))
        return ok(self._db.查询任务日志(robot_id, limit))

    def _hist_patrol(self):
        if not self._db:
            return fail(400, "数据库未启用")
        limit = int(request.args.get("limit", 100))
        return ok(self._db.查询巡逻日志(limit))

    def _hist_stats(self):
        if not self._db:
            return fail(400, "数据库未启用")
        return ok(self._db.获取统计())

    # ======================== API v1: 告警 ========================

    def _api_alerts(self):
        if not self._告警:
            return ok([])
        level = request.args.get("level")
        limit = int(request.args.get("limit", 50))
        return ok(self._告警.获取告警(limit, level))

    def _api_alert_stats(self):
        if not self._告警:
            return ok({"total": 0, "by_level": {}})
        return ok(self._告警.获取统计())

    # ======================== API v1: 巡逻 ========================

    def _patrol_points(self):
        if not self._patrol:
            return ok([])
        return ok(self._patrol.获取点列表())

    def _patrol_add(self):
        d = request.get_json(silent=True)
        if not d:
            return fail(400, "需要 JSON body")
        if not self._patrol:
            return fail(400, "巡逻模块未启用")
        self._patrol.添加点(d["x"], d["y"], d.get("yaw", 0), d.get("name", ""))
        self._event_bus.发布("patrol", {"action": "add_point", "x": d["x"], "y": d["y"]})
        return ok(None, "点已添加")

    def _patrol_del(self, index):
        if not self._patrol:
            return fail(400, "巡逻模块未启用")
        self._patrol.删除点(index)
        self._event_bus.发布("patrol", {"action": "delete_point", "index": index})
        return ok(None, "点已删除")

    def _patrol_start(self):
        if not self._patrol:
            return fail(400, "巡逻模块未启用")
        ok_result = self._patrol.开始巡逻()
        if ok_result:
            self._event_bus.发布("patrol", {"action": "start"})
            return ok(None, "巡逻已启动")
        return fail(500, "巡逻启动失败")

    def _patrol_stop(self):
        if self._patrol:
            self._patrol.停止巡逻()
            self._event_bus.发布("patrol", {"action": "stop"})
        return ok(None, "巡逻已停止")

    def _patrol_status(self):
        if not self._patrol:
            return ok({"patrol_running": False})
        return ok(self._patrol.获取状态())

    # ======================== 启动 ========================

    def 启动(self):
        print(f"[Web面板] http://{self._host}:{self._port}")
        print(f"[Web面板] SSE 事件流: http://{self._host}:{self._port}/api/v1/events")
        self._app.run(host=self._host, port=self._port, threaded=True, debug=False, use_reloader=False)
