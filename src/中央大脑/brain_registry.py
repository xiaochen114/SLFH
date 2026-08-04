#!/usr/bin/env python3
"""机器人注册中心 — 注册/注销/健康检查/全景导出"""
import time, threading
from typing import Dict, Optional
from 机器人.robot_base import RobotBase

# 品牌名映射（robot_type → 品牌）
品牌映射 = {
    "dog": "绝影",
    "drone": "大疆",
    "other": "设备",
}


def 生成机器人ID(robot_type: str, 序号=0) -> str:
    """系统分配机器人 ID: 品牌-时间戳[-序号]
    唯一性: 品牌+时间戳到秒, 同秒多台加序号兜底"""
    品牌 = 品牌映射.get(robot_type, "设备")
    时间戳 = time.strftime("%Y%m%d-%H%M%S")
    if 序号:
        return f"{品牌}-{时间戳}-{序号}"
    return f"{品牌}-{时间戳}"


class 机器人注册中心:
    def __init__(self, event_bus=None):
        self._robots: Dict[str, RobotBase] = {}
        self._last_heartbeat: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop = False
        self._event_bus = event_bus
        t = threading.Thread(target=self._健康检查循环, daemon=True)
        t.start()

    def 注册(self, robot: RobotBase) -> bool:
        """注册机器人，分配系统 ID（唯一），不信任机器人自报名"""
        with self._lock:
            # 从机器人状态推断类型，生成系统 ID
            类型 = "other"
            try:
                st = robot.get_status()
                类型 = st.robot_type
            except:
                pass

            序号 = 0
            while True:
                rid = 生成机器人ID(类型, 序号 if 序号 else 0)
                if rid not in self._robots:
                    break
                序号 += 1
            # 写入机器人（用系统ID覆盖自报名）
            robot._robot_id = rid
            self._robots[rid] = robot
            self._last_heartbeat[rid] = time.time()
            print(f"[注册中心] {rid} 已注册")
            if self._event_bus:
                self._event_bus.发布("robot_connected", {"robot_id": rid})
            return True

    def 注销(self, robot_id: str):
        with self._lock:
            if robot_id in self._robots:
                self._robots[robot_id].disconnect()
                del self._robots[robot_id]
                self._last_heartbeat.pop(robot_id, None)
                print(f"[注册中心] {robot_id} 已注销")

    def 获取机器人(self, robot_id: str) -> Optional[RobotBase]:
        if not isinstance(robot_id, str):
            return None  # 非法 robot_id，防御
        return self._robots.get(robot_id)

    def 获取所有机器人(self) -> list:
        return list(self._robots.values())

    def 获取在线列表(self) -> list:
        now = time.time()
        return [rid for rid, last in self._last_heartbeat.items() if now - last < 30]

    def 获取数量(self) -> int:
        return len(self._robots)

    def 心跳(self, robot_id: str):
        if not isinstance(robot_id, str):
            return  # 非法 robot_id，忽略
        with self._lock:
            self._last_heartbeat[robot_id] = time.time()

    def _健康检查循环(self):
        while not self._stop:
            time.sleep(10)
            now = time.time()
            with self._lock:
                for rid, last in list(self._last_heartbeat.items()):
                    if not isinstance(rid, str):
                        continue  # 跳过非法的 key
                    gap = now - last
                    if gap > 30:
                        print(f"[注册中心] {rid} 超时断连 ({gap:.0f}s)")
                        if self._event_bus:
                            self._event_bus.发布("robot_disconnected", {
                                "robot_id": rid, "elapsed": gap,
                            })
                        robot = self._robots.get(rid)
                        if robot:
                            robot.on_communication_lost()

    def 导出全景(self) -> dict:
        robots_info = []
        for rid, robot in self._robots.items():
            try:
                s = robot.get_status()
                robots_info.append({
                    "id": rid, "type": s.robot_type,
                    "battery": s.battery, "mode": s.mode,
                    "health": s.health, "comm_level": s.communication_level,
                    "position": list(s.position) if s.position else None,
                    "extra": s.extra,
                })
            except:
                robots_info.append({"id": rid, "error": "状态获取失败"})
        return {
            "total": len(self._robots),
            "online": len(self.获取在线列表()),
            "robots": robots_info,
        }

    def 停止(self):
        self._stop = True
        for rid in list(self._robots.keys()):
            self.注销(rid)
