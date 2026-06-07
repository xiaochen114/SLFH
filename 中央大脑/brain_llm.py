#!/usr/bin/env python3
"""LLM 调度引擎 — 大模型决策接口（占位）"""
from 机器人.robot_base import RobotOrder


class LLM调度引擎:
    """大模型调度引擎，可切换不同后端"""

    def __init__(self, provider: str = "deepseek", api_key: str = ""):
        self._provider = provider
        self._api_key = api_key

    def 决策(self, context: dict) -> list:
        """
        根据全局状态做决策
        输入: 所有机器人状态 + 检测事件 + 通信质量
        输出: RobotOrder 列表
        """
        # ===== 当前为规则模拟 ====
        # 后续替换为真实 LLM API 调用
        orders = []
        events = context.get("events", [])
        robots = context.get("robots", [])

        for ev in events:
            etype = ev.get("type", "")
            if etype == "fire_detected":
                # 发现火情 → 急停该机器人 + 派无人机复核
                rid = ev.get("robot_id", "")
                orders.append(RobotOrder(f"llm_{id(self)}_1", "alert",
                                         {"reason": "fire"}, priority=3, source="brain"))
                # 找无人机
                for r in robots:
                    if r.get("type") == "drone" and r.get("health") == "ok":
                        pos = ev.get("position", (0, 0))
                        orders.append(RobotOrder(f"llm_{id(self)}_2", "inspect",
                                                 {"target": pos}, priority=2, source="brain"))
                        break

            elif etype == "smoke_detected":
                orders.append(RobotOrder(f"llm_{id(self)}_3", "patrol",
                                         {"speed": 10000}, priority=1, source="brain"))

            elif etype == "communication_lost":
                # 断连 → 派无人机中继
                for r in robots:
                    if r.get("type") == "drone" and r.get("health") == "ok":
                        orders.append(RobotOrder(f"llm_{id(self)}_4", "custom",
                                                 {"command": "fly_to_relay", "target": ev.get("position", (0, 0))},
                                                 priority=2, source="brain"))
                        break

        return orders

    def 设置提供者(self, provider: str):
        self._provider = provider
