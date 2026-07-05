#!/usr/bin/env python3
"""任务规划器 — 将 LLM 决策拆解为具体可执行任务"""
from 机器人.robot_base import RobotOrder


class 任务规划器:
    """将高层决策转为具体可执行指令序列"""

    def 规划(self, orders: list) -> list:
        """输入 LLM 决策列表，输出增强后的任务列表"""
        planned = []
        for order in orders:
            if order.type == "patrol":
                # 拆解为: 移动模式(如果没在) → 设定速度 → 持续前进
                if "mode_move" not in [o.type for o in planned]:
                    planned.append(RobotOrder(
                        f"{order.order_id}_pre", "custom",
                        {"command": "set_mode_move"}, priority=order.priority, source="brain"))
                planned.append(order)

            elif order.type == "alert":
                planned.append(order)
                # 追加回零
                planned.append(RobotOrder(
                    f"{order.order_id}_post", "return", {}, priority=order.priority, source="brain"))

            else:
                planned.append(order)

        return planned
