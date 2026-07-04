#!/usr/bin/env python3
"""监控告警引擎 — 订阅事件总线，检测异常并推送告警"""
import time
from datetime import datetime


class 监控告警:
    """异常检测 + 告警广播"""

    def __init__(self, 事件总线, 数据库=None):
        self._bus = 事件总线
        self._db = 数据库
        self._告警历史 = []
        self._低电量记录 = {}    # robot_id → 上次警告时间

        # 订阅事件
        self._bus.订阅("robot_heartbeat", self._检查心跳)
        self._bus.订阅("robot_disconnected", self._处理断连)

    def _检查心跳(self, event):
        """心跳事件中检测异常"""
        data = event.get("data", {})
        robot_id = data.get("robot_id", "?")
        battery = data.get("battery", 1.0)
        health = data.get("health", "ok")
        comm = data.get("comm_level", 1)

        now = time.time()
        alerts = []

        # 低电量告警（每 5 分钟最多一次）
        if battery < 0.2:
            last = self._低电量记录.get(robot_id, 0)
            if now - last > 300:
                alerts.append({
                    "type": "low_battery",
                    "level": "warning",
                    "robot_id": robot_id,
                    "message": f"{robot_id} 电量不足 ({battery*100:.0f}%)",
                    "time": now,
                })
                self._低电量记录[robot_id] = now

        # 健康异常
        if health in ("warning", "error"):
            alerts.append({
                "type": "health_issue",
                "level": "error" if health == "error" else "warning",
                "robot_id": robot_id,
                "message": f"{robot_id} 健康状态异常: {health}",
                "time": now,
            })

        # 通信弱
        if comm >= 2:
            alerts.append({
                "type": "poor_connection",
                "level": "warning" if comm == 2 else "error",
                "robot_id": robot_id,
                "message": f"{robot_id} 通信质量 L{comm}",
                "time": now,
            })

        for alert in alerts:
            self._触发告警(alert)

    def _处理断连(self, event):
        data = event.get("data", {})
        self._触发告警({
            "type": "disconnected",
            "level": "error",
            "robot_id": data.get("robot_id", "?"),
            "message": f"{data.get('robot_id', '?')} 断连 ({data.get('elapsed', 0):.0f}s 无心跳)",
            "time": time.time(),
        })

    def _触发告警(self, alert):
        """记录告警并广播"""
        self._告警历史.append(alert)
        if len(self._告警历史) > 500:
            self._告警历史 = self._告警历史[-250:]

        # 打印
        level_map = {"error": "✗", "warning": "!", "info": "i"}
        print(f"[告警][{level_map.get(alert['level'],'?')}] {alert['message']}")

        # 持久化
        if self._db:
            try:
                self._db.保存配置(f"alert_{int(alert['time'])}", alert)
            except:
                pass

        # SSE 广播
        try:
            self._bus.发布("alert", alert)
        except:
            pass

    def 获取告警(self, limit=50, level=None):
        """获取最近的告警"""
        result = self._告警历史
        if level:
            result = [a for a in result if a.get("level") == level]
        return result[-limit:]

    def 获取统计(self):
        """告警统计"""
        total = len(self._告警历史)
        by_level = {}
        for a in self._告警历史:
            lv = a.get("level", "unknown")
            by_level[lv] = by_level.get(lv, 0) + 1
        return {
            "total": total,
            "by_level": by_level,
            "recent": self._告警历史[-5:] if self._告警历史 else [],
        }
