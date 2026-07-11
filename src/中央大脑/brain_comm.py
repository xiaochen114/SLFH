#!/usr/bin/env python3
"""通信管理层 — 统一消息路由、缓存、重连"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time, json, queue, threading
from typing import Callable, Optional
from 机器人.robot_base import RobotOrder, RobotStatus
from 中央大脑.brain_registry import 机器人注册中心


class 通信管理器:
    """消息收发、连接质量检测、离线缓存"""

    def __init__(self, registry: 机器人注册中心):
        self._registry = registry
        self._msg_queue = queue.Queue()
        self._pending_orders: list = []  # 离线未送达
        self._callbacks: dict = {}
        self._stop = False

        t = threading.Thread(target=self._dispatch_loop, daemon=True)
        t.start()

    # === 发送 ===

    def 发送指令(self, robot_id: str, order: RobotOrder) -> bool:
        robot = self._registry.获取机器人(robot_id)
        if not robot or not robot.is_connected():
            self._pending_orders.append((robot_id, order))
            print(f"[通信] {robot_id} 离线，指令缓存 (oid={order.order_id})")
            return False
        result = robot.execute_order(order)
        self._msg_queue.put(("order_result", robot_id, result))
        return result.success

    def 获取状态(self, robot_id: str) -> Optional[RobotStatus]:
        robot = self._registry.获取机器人(robot_id)
        if not robot:
            return None
        try:
            return robot.get_status()
        except:
            return None

    # === 接收 ===

    def on(self, event_type: str, callback: Callable):
        """注册事件回调"""
        self._callbacks[event_type] = callback

    def _dispatch_loop(self):
        while not self._stop:
            try:
                event_type, robot_id, data = self._msg_queue.get(timeout=1)
                cb = self._callbacks.get(event_type)
                if cb:
                    cb(robot_id, data)
            except queue.Empty:
                pass

    def 停止(self):
        self._stop = True
