#!/usr/bin/env python3
"""中央大脑 — 异构多机器人调度系统 入口"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time, threading, argparse

from 中央大脑.brain_registry import 机器人注册中心
from 中央大脑.brain_comm import 通信管理器
from 中央大脑.brain_web import Web面板
from 中央大脑.brain_llm import LLM调度引擎
from 中央大脑.brain_scheduler import 任务规划器
from 中央大脑.事件总线 import 事件总线
from 中央大脑.数据库 import 数据库
from 中央大脑.监控告警 import 监控告警
from 中央大脑.检测服务 import 检测服务
from 中央大脑.运维自愈 import 运维自愈
from 中央大脑.记忆管理器 import 记忆管理器
from 中央大脑.自主巡逻 import 自主巡逻
from 机器人.感知主机控制 import 感知主机控制
from 机器人.robot_base import RobotOrder


class 中央大脑:
    """主控制器 — 组装模块、调度循环、事件广播"""

    def __init__(self, web_host="0.0.0.0", web_port=5000, 启用巡逻=False, 配置=None):
        self.事件总线 = 事件总线()
        self.registry = 机器人注册中心(self.事件总线)
        self.comm = 通信管理器(self.registry, self.事件总线)
        self.db = 数据库()
        cfg = 配置 or {}
        self.llm = LLM调度引擎(
            api_url=cfg.get("llm_api_url"),
            api_key=cfg.get("llm_api_key"),
            api_model=cfg.get("llm_api_model"),
            数据库=self.db,
        )
        self.scheduler = 任务规划器()
        self.告警 = 监控告警(self.事件总线, self.db)
        self.记忆 = 记忆管理器(self.db)
        self._running = False

        # 运维自愈（规则诊断优先，LLM增强）
        self.自愈 = 运维自愈(
            self.事件总线, self.db, llm=self.llm, 注册中心=self.registry,
        )
        from 中央大脑.诊断脚本_感知主机 import 获取诊断器 as 感知主机诊断器
        from 中央大脑.诊断脚本_绝影 import 获取诊断器 as 绝影诊断器
        self.自愈.注册诊断器("感知主机", 感知主机诊断器())
        self.自愈.注册诊断器("绝影", 绝影诊断器())

        # 巡逻模块（点管理始终可用，持久化到数据库）
        self.patrol = 自主巡逻(None)
        self.patrol.set_db(self.db)  # 从数据库加载巡逻点
        self.感知主机 = None
        if 启用巡逻:
            self.感知主机 = 感知主机控制()

        # YOLO 火情检测（多路视频流，事件写入数据库，带 source 标签）
        self.检测 = None
        if cfg.get("model_path"):
            self.检测 = 检测服务(
                self.事件总线,
                self.db,
                模型路径=cfg["model_path"],
                视频源=cfg.get("视频源", cfg.get("camera_url", 0)),
                置信度=cfg.get("conf_thresh", 0.5),
            )
        else:
            print("[检测] 未配置 model_path，YOLO 火情检测未启用")

        self.web = Web面板(
            self.registry, self.comm, self.db, self.告警, self.事件总线,
            web_host, web_port, patrol=self.patrol, llm=self.llm,
            自愈=self.自愈, 记忆=self.记忆, 大脑=self, 检测=self.检测,
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

        if self.检测:
            self.检测.启动()

        t = threading.Thread(target=self.web.启动, daemon=True)
        t.start()
        time.sleep(0.5)

        self._running = True
        print("[中央大脑] 启动完成")
        self._调度循环()

    def 停止(self):
        self._running = False
        self.registry.停止()
        self.comm.停止()
        if self.检测:
            self.检测.停止()
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

                for r in self.registry.获取所有机器人():
                    if r.is_connected():
                        self.registry.心跳(r.robot_id)
                        try:
                            st = r.get_status()
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

                # LLM 决策（从事件库取未消费的检测事件）
                events = self.db.取未消费事件(source="yolo", limit=10)
                for ev in events:
                    if ev.get("priority", 0) >= 2:
                        print(f"[中央大脑] 特急事件: {ev.get('label','')} 紧急急停所有机器人")
                        for r in self.registry.获取所有机器人():
                            if r.is_connected():
                                order = RobotOrder(
                                    order_id=f"urgent_{int(time.time())}",
                                    type="alert", params={"reason": "urgent_fire"},
                                    priority=3, source="brain")
                                self.comm.发送指令(r.robot_id, order)
                ctx = {
                    "robots": self.registry.导出全景().get("robots", []),
                    "events": events,
                    "patrol_points": self.patrol.获取点列表() if self.patrol else [],
                }
                import time as _t
                _start = _t.time()
                orders = self.llm.决策(ctx)
                _latency = int((_t.time() - _start) * 1000)
                # 记录 LLM 决策（记忆来源 + 审计）
                llm状态 = self.llm.获取状态()
                mode = "rule" if llm状态.get("降级中") or llm状态.get("mode") == "rule" else "llm"
                order_list = [
                    {"type": o.type, "robot_id": o.robot_id, "priority": o.priority}
                    for o in orders
                ]
                self.db.记录LLM决策(mode, events, ctx["robots"], order_list, _latency)
                self.事件总线.发布("llm_decision", {
                    "mode": mode, "orders": order_list, "latency_ms": _latency,
                })
                if orders:
                    for o in self.scheduler.规划(orders):
                        # 无标签 → 按能力路由兜底
                        if not o.robot_id:
                            类型 = {"inspect": "drone"}.get(o.type, "dog")
                            for r in self.registry.获取所有机器人():
                                if r.is_connected():
                                    try:
                                        if r.get_status().robot_type == 类型:
                                            o.robot_id = r.robot_id
                                            break
                                    except:
                                        pass
                        # 按指令标签找目标机器人下发
                        if o.robot_id:
                            r = self.registry.获取机器人(o.robot_id)
                            if r and r.is_connected():
                                ok = self.comm.发送指令(o.robot_id, o)
                                self.db.记录任务(
                                    order_id=o.order_id,
                                    robot_id=o.robot_id,
                                    type=o.type,
                                    params=o.params,
                                    priority=o.priority,
                                    source=o.source,
                                    success=ok,
                                    message=f"指令 {o.type} {'成功' if ok else '失败'}",
                                )
                                self.事件总线.发布("brain_order", {
                                    "robot_id": o.robot_id,
                                    "type": o.type,
                                    "priority": o.priority,
                                })

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
        """先连接成功再注册（避免注册了连不上的机器人）"""
        if robot.connect():
            self.registry.注册(robot)
            print(f"[中央大脑] {robot.robot_id} 连接成功")
            self.事件总线.发布("robot_registered", {"robot_id": robot.robot_id})
        else:
            print(f"[中央大脑] 机器人连接失败，未注册")


def main():
    parser = argparse.ArgumentParser(description="中央大脑")
    parser.add_argument("--patrol", action="store_true", help="启用自主巡逻模块")
    parser.add_argument("--simulate", action="store_true", help="模拟模式(不连真狗)")
    parser.add_argument("--port", type=int, default=5000, help="Web端口")
    args = parser.parse_args()

    from 配置.配置加载 import 加载配置
    cfg = 加载配置()

    brain = 中央大脑(web_port=args.port, 启用巡逻=args.patrol, 配置=cfg)

    if args.simulate:
        from 机器人.机器人模拟器 import 模拟机器人
        # robot_id 由系统分配，此处只传类型
        brain.注册机器人(模拟机器人(robot_id="", robot_type="dog"))
        print("[系统] 模拟模式")
    else:
        from 机器人.机器狗_绝影 import 机器狗_绝影
        brain.注册机器人(机器狗_绝影(robot_id=""))
        print("[系统] 真机模式")

    brain.启动()


if __name__ == "__main__":
    main()
