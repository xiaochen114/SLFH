#!/usr/bin/env python3
import time, threading
from typing import Dict, Optional
from 机器人.robot_base import RobotBase

class 机器人注册中心:
    def __init__(self):
        self._robots: Dict[str, RobotBase] = {}
        self._last_heartbeat: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop = False
        t = threading.Thread(target=self._健康检查循环, daemon=True)
        t.start()

    def 注册(self, robot: RobotBase) -> bool:
        with self._lock:
            rid = robot.robot_id
            if rid in self._robots:
                return False
            self._robots[rid] = robot
            self._last_heartbeat[rid] = time.time()
            print(f"[注册中心] {rid} 已注册")
            return True

    def 注销(self, robot_id: str):
        with self._lock:
            if robot_id in self._robots:
                self._robots[robot_id].disconnect()
                del self._robots[robot_id]
                self._last_heartbeat.pop(robot_id, None)
                print(f"[注册中心] {robot_id} 已注销")

    def 获取机器人(self, robot_id: str) -> Optional[RobotBase]:
        return self._robots.get(robot_id)

    def 获取所有机器人(self) -> list:
        return list(self._robots.values())

    def 获取在线列表(self) -> list:
        now = time.time()
        return [rid for rid, last in self._last_heartbeat.items() if now - last < 30]

    def 获取数量(self) -> int:
        return len(self._robots)

    def 心跳(self, robot_id: str):
        with self._lock:
            self._last_heartbeat[robot_id] = time.time()

    def _健康检查循环(self):
        while not self._stop:
            time.sleep(10)
            now = time.time()
            with self._lock:
                for rid, last in list(self._last_heartbeat.items()):
                    gap = now - last
                    if gap > 30:
                        print(f"[注册中心] {rid} 超时断连 ({gap:.0f}s)")
                        robot = self._robots.get(rid)
                        if robot:
                            robot.on_communication_lost()

    def 导出全景(self) -> dict:
        robots_info = []
        for rid, robot in self._robots.items():
            try:
                s = robot.get_status()
                robots_info.append({"id": rid, "type": s.robot_type, "battery": s.battery, "mode": s.mode, "health": s.health, "comm_level": s.communication_level, "extra": s.extra})
            except:
                robots_info.append({"id": rid, "error": "状态获取失败"})
        return {"total": len(self._robots), "online": len(self.获取在线列表()), "robots": robots_info}

    def 停止(self):
        self._stop = True
        for rid in list(self._robots.keys()):
            self.注销(rid)
