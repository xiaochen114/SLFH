#!/usr/bin/env python3
"""通信管理层 — 统一消息路由、缓存、重连"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import Optional
from 机器人.robot_base import RobotOrder, RobotStatus
from 中央大脑.brain_registry import 机器人注册中心


class 通信管理器:
    """消息收发、离线缓存"""

    def __init__(self, registry: 机器人注册中心):
        self._registry = registry
        self._pending_orders: list = []  # 离线未送达

    # === 发送 ===

    def 发送指令(self, robot_id: str, order: RobotOrder) -> bool:
        robot = self._registry.获取机器人(robot_id)
        if not robot or not robot.is_connected():
            self._pending_orders.append((robot_id, order))
            print(f"[通信] {robot_id} 离线，指令缓存 (oid={order.order_id})")
            return False
        result = robot.execute_order(order)
        return result.success

    def 获取状态(self, robot_id: str) -> Optional[RobotStatus]:
        robot = self._registry.获取机器人(robot_id)
        if not robot:
            return None
        try:
            return robot.get_status()
        except:
            return None

    def 停止(self):
        pass
