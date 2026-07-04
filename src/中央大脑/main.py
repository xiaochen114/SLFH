#!/usr/bin/env python3
"""中央大脑 — 异构多机器人调度系统 入口"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time, threading, argparse

from 中央大脑.brain_registry import 机器人注册中心
from 中央大脑.brain_comm import 通信管理器
from 中央大脑.brain_web import Web面板
from 中央大脑.brain_llm import LLM调度引擎
from 中央大脑.brain_scheduler import 任务规划器
from 中央大脑.brain_ops_agent import 运维Agent
from 中央大脑.事件总线 import 事件总线
from 中央大脑.数据库 import 数据库
from 中央大脑.监控告警 import 监控告警
from 中央大脑.自主巡逻 import 自主巡逻
from 机器人.感知主机控制 import 感知主机控制


class 中央大脑:
    """主控制器 — 组装模块、调度循环、事件广播"""

    def __init__(self, web_host="0.0.0.0", web_port=5000, 启用巡逻=False):
        self.事件总线 = 事件总线()
        self.registry = 机器人注册中心(self.事件总线)
        self.comm = 通信管理器(self.registry)
        self.llm = LLM调度引擎()
        self.scheduler = 任务规划器()
        self.ops_agent = 运维Agent(self.registry)
        self.db = 数据库()
        self.告警 = 监控告警(self.事件总线, self.db)
        self._running = False

        # 自主巡逻
        self.感知主机 = None
        self.patrol = None
        if 启用巡逻:
            self.感知主机 = 感知主机控制()
            self.patrol = 自主巡逻(self.感知主机)
            self.patrol.加载配置()

        self.web = Web面板(
            self.registry, self.comm, self.db, self.告警, self.事件总线,
            web_host, web_port, patrol=self.patrol,
        )

    def 启动(self):
        print("=" * 50)
        print("  中央大脑 v1.0 - 异构多机器人调度系统")
        print("=" * 50)

        if self.感知主机:
            if self.感知主机.connect():
                print("[中央大脑] 感知主机已连接，巡逻就绪")
            else:
                print("[中央大脑] 感知主机连接失败，巡逻不可用")

        # 启动 Web（后台线程）
        t = threading.Thread(target=self.web.启动, daemon=True)
        t.start()
        time.sleep(0.5)  # 等 web 起来

        self._running = True
        print("[中央大脑] 启动完成")
        self._调度循环()

    def 停止(self):
        self._running = False
        self.registry.停止()
        self.comm.停止()
        if self.patrol:
            self.patrol.停止()
        if self.感知主机:
            self.感知主机.close()
        print("[中央大脑] 已关闭")

    def _调度循环(self):
        tick = 0
        try:
            while self._running:
                time.sleep(2)
                tick += 1

                # 心跳 & 数据库记录
                for r in self.registry.获取所有机器人():
                    if r.is_connected():
                        self.registry.心跳(r.robot_id)
                        try:
                            st = r.get_status()
                            # 持久化状态快照（每 30s）
                            if tick % 15 == 0:
                                self.db.保存状态快照(
                                    robot_id=r.robot_id,
                                    robot_type=st.robot_type,
                                    battery=st.battery,
                                    mode=st.mode,
                                    health=st.health,
                                    comm_level=st.communication_level,
                                    pos=st.position,
                                )
                            self.事件总线.发布("robot_heartbeat", {
                                "robot_id": r.robot_id,
                                "battery": st.battery,
                                "mode": st.mode,
                                "health": st.health,
                                "comm_level": st.communication_level,
                            })
                        except:
                            pass

                # LLM 决策
                ctx = {
                    "robots": self.registry.导出全景().get("robots", []),
                    "events": [],
                }
                orders = self.llm.决策(ctx)
                if orders:
                    for o in self.scheduler.规划(orders):
                        for r in self.registry.获取所有机器人():
                            if r.is_connected():
                                ok = self.comm.发送指令(r.robot_id, o)
                                # 持久化任务日志
                                self.db.记录任务(
                                    order_id=o.order_id,
                                    robot_id=r.robot_id,
                                    type=o.type,
                                    params=o.params,
                                    priority=o.priority,
                                    source=o.source,
                                    success=ok,
                                    message=f"指令 {o.type} {'成功' if ok else '失败'}",
                                )
                                self.事件总线.发布("brain_order", {
                                    "robot_id": r.robot_id,
                                    "type": o.type,
                                    "priority": o.priority,
                                })
                                break

                # 健康广播 & 清理旧数据（每 30s）
                if tick % 15 == 0:
                    self.事件总线.发布("system_health", {
                        "robot_count": self.registry.获取数量(),
                        "online": len(self.registry.获取在线列表()),
                        "uptime": tick * 2,
                    })
                    self.db.清理旧历史(keep_hours=72)

        except KeyboardInterrupt:
            print("\n[中央大脑] 用户停止")
        finally:
            self.停止()

    def 注册机器人(self, robot):
        self.registry.注册(robot)
        if robot.connect():
            print(f"[中央大脑] {robot.robot_id} 连接成功")
            self.事件总线.发布("robot_registered", {"robot_id": robot.robot_id})
        else:
            print(f"[中央大脑] {robot.robot_id} 连接失败")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="中央大脑")
    parser.add_argument("--patrol", action="store_true", help="启用自主巡逻模块")
    parser.add_argument("--port", type=int, default=5000, help="Web端口")
    args = parser.parse_args()

    brain = 中央大脑(web_port=args.port, 启用巡逻=args.patrol)
    brain.启动()
