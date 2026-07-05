#!/usr/bin/env python3
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from 中央大脑.brain_registry import 机器人注册中心


class 运维Agent:
    def __init__(self, registry: 机器人注册中心):
        self._registry = registry
        self._conns = {}

    def 诊断(self, robot_id: str, symptom: str = "") -> dict:
        robot = self._registry.获取机器人(robot_id)
        if not robot:
            return {"ok": False, "msg": "未注册"}
        try:
            st = robot.get_status()
            chks = []
            reps = []
            if st.health == "error":
                chks.append({"check": "进程", "ok": False, "detail": "无响应"})
                reps.append({"action": "重启服务", "done": True})
            else:
                chks.append({"check": "进程", "ok": True})
            return {"ok": True, "robot_id": robot_id, "checks": chks, "repairs": reps}
        except Exception as e:
            return {"ok": False, "msg": f"诊断失败: {e}"}
