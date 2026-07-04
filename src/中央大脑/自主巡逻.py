#!/usr/bin/env python3
"""
自主巡逻调度器 — 管理巡逻点队列，循环下发导航目标
依赖: 机器人/感知主机控制.py → Nav2

用法:
  p = 自主巡逻(感知主机)
  p.加载配置("巡逻点.yaml")
  p.添加点(x, y, yaw)
  p.开始巡逻()
"""
import os, sys, time, threading, yaml
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class 巡逻点:
    x: float
    y: float
    yaw: float = 0.0
    name: str = ""


@dataclass
class 巡逻状态:
    运行中: bool = False
    当前点索引: int = -1
    当前点: Optional[巡逻点] = None
    状态: str = "idle"     # idle/导航中/停留/跳过/完成
    总点数: int = 0
    日志: list = field(default_factory=list)


class 自主巡逻:
    """巡逻调度器"""

    def __init__(self, 感知主机):
        self._ph = 感知主机
        self._points: List[巡逻点] = []
        self._stop = False
        self._thread = None
        self.状态 = 巡逻状态()

        # 配置
        self.停留时间 = 5       # 每点停留秒数
        self.导航超时 = 120     # 导航超时秒数
        self.遇障策略 = "skip"  # skip/retry
        self.循环模式 = "loop"  # loop/once

    # ========== 加载配置 ==========

    def 加载配置(self, path="巡逻点.yaml"):
        if not os.path.exists(path):
            print(f"[巡逻] 配置文件不存在: {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        self.停留时间 = cfg.get("dwell_time", 5)
        self.导航超时 = cfg.get("nav_timeout", 120)
        self.遇障策略 = cfg.get("obstacle_policy", "skip")
        self.循环模式 = cfg.get("mode", "loop")

        pts = cfg.get("patrol_points", [])
        if pts:
            self._points = [
                巡逻点(x=p["x"], y=p["y"], yaw=p.get("yaw", 0), name=p.get("name", f"点{i+1}"))
                for i, p in enumerate(pts)
            ]
            self.状态.总点数 = len(self._points)
            self._log(f"加载 {len(self._points)} 个巡逻点")
        else:
            self._log("巡逻点为空，请用Web面板添加或修改配置文件")

    def 保存配置(self, path="巡逻点.yaml"):
        cfg = {
            "patrol_points": [
                {"x": p.x, "y": p.y, "yaw": p.yaw, "name": p.name}
                for p in self._points
            ],
            "dwell_time": self.停留时间,
            "nav_timeout": self.导航超时,
            "obstacle_policy": self.遇障策略,
            "mode": self.循环模式,
        }
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        self._log(f"配置已保存 ({len(self._points)} 点)")

    # ========== 点管理 ==========

    def 添加点(self, x, y, yaw=0.0, name=""):
        idx = len(self._points) + 1
        nm = name or f"点{idx}"
        self._points.append(巡逻点(x=x, y=y, yaw=yaw, name=nm))
        self.状态.总点数 = len(self._points)
        self._log(f"添加 {nm} ({x:.1f}, {y:.1f})")

    def 删除点(self, index):
        if 0 <= index < len(self._points):
            p = self._points.pop(index)
            self.状态.总点数 = len(self._points)
            self._log(f"删除 {p.name}")

    def 清空点(self):
        self._points.clear()
        self.状态.总点数 = 0

    def 获取点列表(self):
        return [{"index": i, "x": p.x, "y": p.y, "yaw": p.yaw, "name": p.name}
                for i, p in enumerate(self._points)]

    # ========== 巡逻循环 ==========

    def 开始巡逻(self):
        if not self._points:
            self._log("无巡逻点，请先添加")
            return False

        if not self._ph.connected:
            self._log("感知主机未连接")
            return False

        if not self._ph.is_nav_running():
            self._log("导航未启动，正在启动...")
            if not self._ph.start_navigation():
                self._log("导航启动失败")
                return False

        self._stop = False
        self.状态.运行中 = True
        self._thread = threading.Thread(target=self._巡逻循环, daemon=True)
        self._thread.start()
        self._log("巡逻开始")
        return True

    def 停止巡逻(self):
        self._stop = True
        self.状态.运行中 = False
        self.状态.状态 = "idle"
        self._ph.cancel_goal()
        self._log("巡逻停止")

    def _巡逻循环(self):
        idx = 0
        while not self._stop:
            if idx >= len(self._points):
                if self.循环模式 == "once":
                    self._log("巡逻完成（once模式）")
                    self.状态.状态 = "完成"
                    self.状态.运行中 = False
                    return
                idx = 0  # loop 模式：从头开始

            point = self._points[idx]
            self.状态.当前点索引 = idx
            self.状态.当前点 = point

            # 下发导航目标
            self._log(f"→ {point.name} ({point.x:.1f}, {point.y:.1f})")
            self.状态.状态 = "导航中"

            if not self._ph.send_goal(point.x, point.y, point.yaw):
                self._log(f"  {point.name} 目标发送失败，跳过")
                idx += 1
                continue

            # 等待到达或超时
            start = time.time()
            arrived = False
            while not self._stop and time.time() - start < self.导航超时:
                result = self._ph.get_nav_result()
                if result == "arrived":
                    arrived = True
                    break
                elif result == "failed":
                    self._log(f"  {point.name} 导航失败（障碍/blocked），跳过")
                    self.状态.状态 = "跳过"
                    break
                time.sleep(2)

            if arrived:
                self._log(f"  {point.name} 到达，停留{self.停留时间}s")
                self.状态.状态 = "停留"
                # 停留观察（火情检测继续跑）
                for _ in range(self.停留时间):
                    if self._stop:
                        return
                    time.sleep(1)

            elif not self._stop:
                # 超时
                if time.time() - start >= self.导航超时:
                    self._log(f"  {point.name} 超时 {self.导航超时}s，跳过")

            idx += 1

    # ========== 日志 ==========

    def _log(self, msg):
        t = time.strftime("%H:%M:%S")
        entry = f"[{t}] {msg}"
        self.状态.日志.append(entry)
        if len(self.状态.日志) > 100:
            self.状态.日志.pop(0)
        print(entry)

    # ========== 状态 ==========

    def 获取状态(self) -> dict:
        nav = self._ph.get_status()
        return {
            "巡逻运行中": self.状态.运行中,
            "巡逻状态": self.状态.状态,
            "当前点": self.状态.当前点.name if self.状态.当前点 else "",
            "当前点坐标": (self.状态.当前点.x, self.状态.当前点.y) if self.状态.当前点 else None,
            "当前索引": self.状态.当前点索引 + 1,
            "总点数": self.状态.总点数,
            "停留时间": self.停留时间,
            "导航超时": self.导航超时,
            "遇障策略": self.遇障策略,
            "循环模式": self.循环模式,
            "导航运行中": nav.running,
            "导航状态": nav.state,
            "日志": self.状态.日志[-20:],
        }

    def 停止(self):
        self.停止巡逻()
