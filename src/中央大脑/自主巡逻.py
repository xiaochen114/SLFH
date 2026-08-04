#!/usr/bin/env python3
"""
自主巡逻调度器 — 管理巡逻点队列，循环下发导航目标
依赖: 机器人/感知主机控制.py → Nav2
"""
import os, sys, time, threading, yaml
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from 中央大脑.巡逻数据类型 import 巡逻点, 巡逻状态


class 自主巡逻:
    """巡逻调度器 — 点管理、循环调度、超时/障碍处理"""

    def __init__(self, 感知主机):
        self._ph = 感知主机
        self._db = None
        self._points: list[巡逻点] = []
        self._stop = False
        self._thread = None
        self.状态 = 巡逻状态()

        # 可调参数
        self.停留时间 = 5
        self.导航超时 = 120
        self.遇障策略 = "skip"   # skip / retry
        self.循环模式 = "loop"   # loop / once

    def set_db(self, db):
        """绑定数据库（巡逻点持久化到 SQLite）"""
        self._db = db
        # 优先从数据库加载
        if db:
            点列表 = db.加载巡逻点()
            if 点列表:
                self._points = [巡逻点(x=p["x"], y=p["y"], yaw=p.get("yaw", 0), name=p.get("name", f"点{i+1}"))
                                for i, p in enumerate(点列表)]
                self.状态.总点数 = len(self._points)
                self._log(f"从数据库加载 {len(self._points)} 个巡逻点")

    # ========== 配置读写 ==========

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

    def 保存配置(self, path="巡逻点.yaml"):
        # 同步到数据库（唯一持久化真源）
        if self._db:
            self._db.保存巡逻点([
                {"x": p.x, "y": p.y, "yaw": p.yaw, "name": p.name}
                for p in self._points
            ])
        # 兼容旧版 yaml（保留，后续可删）
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
        self._points.append(巡逻点(x=x, y=y, yaw=yaw, name=name or f"点{idx}"))
        self.状态.总点数 = len(self._points)
        self._log(f"添加 {self._points[-1].name}")
        self.保存配置()

    def 删除点(self, index):
        if 0 <= index < len(self._points):
            p = self._points.pop(index)
            self.状态.总点数 = len(self._points)
            self._log(f"删除 {p.name}")
            self.保存配置()

    def 获取点列表(self):
        return [{"index": i, "x": p.x, "y": p.y, "yaw": p.yaw, "name": p.name}
                for i, p in enumerate(self._points)]

    # ========== 巡逻循环 ==========

    def 开始巡逻(self):
        if not self._points:
            self._log("无巡逻点，请先添加")
            return False
        if not self._ph or not self._ph.connected:
            self._log("感知主机未连接，无法开始巡逻。请使用 --patrol 参数启动")
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
        if self._ph:
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
                idx = 0

            point = self._points[idx]
            self.状态.当前点索引 = idx
            self.状态.当前点 = point
            self._log(f"→ {point.name} ({point.x:.1f}, {point.y:.1f})")
            self.状态.状态 = "导航中"

            if not self._ph.send_goal(point.x, point.y, point.yaw):
                self._log(f"  {point.name} 目标发送失败，跳过")
                idx += 1
                continue

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
                for _ in range(self.停留时间):
                    if self._stop:
                        return
                    time.sleep(1)
            elif not self._stop:
                self._log(f"  {point.name} 超时 {self.导航超时}s，跳过")
            idx += 1

    # ========== 日志与状态 ==========

    def _log(self, msg):
        t = time.strftime("%H:%M:%S")
        entry = f"[{t}] {msg}"
        self.状态.日志.append(entry)
        if len(self.状态.日志) > 100:
            self.状态.日志.pop(0)
        print(entry)

    def 获取状态(self):
        nav_running = nav_state = False
        if self._ph:
            nav = self._ph.get_status()
            nav_running = nav.running
            nav_state = nav.state
        return {
            "巡逻运行中": self.状态.运行中,
            "巡逻状态": self.状态.状态,
            "当前点": self.状态.当前点.name if self.状态.当前点 else "",
            "当前点坐标": (self.状态.当前点.x, self.状态.当前点.y) if self.状态.当前点 else None,
            "当前索引": self.状态.当前点索引 + 1,
            "总点数": self.状态.总点数,
            "导航运行中": nav_running,
            "导航状态": nav_state,
            "日志": self.状态.日志[-20:],
        }

    def 停止(self):
        self.停止巡逻()
