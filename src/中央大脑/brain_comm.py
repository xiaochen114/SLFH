#!/usr/bin/env python3
"""通信管理层 — 统一消息路由、离线缓存、重连补发"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import Optional
from 机器人.robot_base import RobotOrder, RobotStatus
from 中央大脑.brain_registry import 机器人注册中心


class 通信管理器:
    """消息收发、离线缓存、重连补发"""

    def __init__(self, registry: 机器人注册中心, 事件总线=None):
        self._registry = registry
        self._event_bus = 事件总线
        self._pending_orders: list = []  # 离线未送达
        if 事件总线:
            事件总线.订阅("robot_connected", self.补发离线)

    # === 发送 ===

    def 发送指令(self, robot_id: str, order: RobotOrder) -> bool:
        if not isinstance(robot_id, str) or not robot_id:
            print(f"[通信] 非法 robot_id，指令丢弃: {robot_id!r}")
            return False
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

    def 补发离线(self, event=None):
        """机器人重连后补发离线期间缓存的指令"""
        robot_id = (event or {}).get("data", {}).get("robot_id", "") if event else ""
        if not isinstance(robot_id, str) or not robot_id:
            return
        still_pending = []
        count = 0
        for rid, order in self._pending_orders:
            if rid == robot_id:
                robot = self._registry.获取机器人(robot_id)
                if robot and robot.is_connected():
                    robot.execute_order(order)
                    count += 1
                    continue
            still_pending.append((rid, order))
        self._pending_orders = still_pending
        if count > 0:
            print(f"[通信] 已补发 {count} 条离线指令给 {robot_id}")

    def 停止(self):
        pass
