#!/usr/bin/env python3
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from 中央大脑.brain_registry import 机器人注册中心
from 中央大脑.brain_comm import 通信管理器
from 中央大脑.brain_web import Web面板
from 中央大脑.brain_llm import LLM调度引擎
from 中央大脑.brain_scheduler import 任务规划器
from 中央大脑.brain_ops_agent import 运维Agent
from 中央大脑.自主巡逻 import 自主巡逻
from 机器人.感知主机控制 import 感知主机控制

class 中央大脑:
    def __init__(self, web_host="0.0.0.0", web_port=5000, 启用巡逻=False):
        self.registry = 机器人注册中心()
        self.comm = 通信管理器(self.registry)
        self.llm = LLM调度引擎()
        self.scheduler = 任务规划器()
        self.ops_agent = 运维Agent(self.registry)

        # 自主巡逻模块
        self.感知主机 = None
        self.patrol = None
        if 启用巡逻:
            self.感知主机 = 感知主机控制()
            self.patrol = 自主巡逻(self.感知主机)
            self.patrol.加载配置()

        self.web = Web面板(self.registry, self.comm, web_host, web_port, patrol=self.patrol)
        self._running = False

    def 启动(self):
        print("=" * 50)
        print("  中央大脑 v1.0 - 异构多机器人调度系统")
        print("=" * 50)

        # 连接感知主机（巡逻模式）
        if self.感知主机:
            if self.感知主机.connect():
                print("[中央大脑] 感知主机已连接，巡逻就绪")
            else:
                print("[中央大脑] 感知主机连接失败，巡逻不可用")

        self.web.启动()
        self._running = True
        print("[中央大脑] 启动完成")
        try:
            while self._running:
                import time; time.sleep(2)
                self._调度循环()
        except KeyboardInterrupt:
            print("\n[中央大脑] 用户停止")
        finally:
            self.停止()

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
        for r in self.registry.获取所有机器人():
            if r.is_connected():
                self.registry.心跳(r.robot_id)
        ctx = {"robots": self.registry.导出全景().get("robots", []), "events": []}
        orders = self.llm.决策(ctx)
        if orders:
            for o in self.scheduler.规划(orders):
                for r in self.registry.获取所有机器人():
                    if r.is_connected():
                        self.comm.发送指令(r.robot_id, o)
                        break

    def 注册机器人(self, robot):
        self.registry.注册(robot)
        if robot.connect():
            print(f"[中央大脑] {robot.robot_id} 连接成功")
        else:
            print(f"[中央大脑] {robot.robot_id} 连接失败")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='中央大脑')
    parser.add_argument('--patrol', action='store_true', help='启用自主巡逻模块')
    parser.add_argument('--port', type=int, default=5000, help='Web端口')
    args = parser.parse_args()

    brain = 中央大脑(web_port=args.port, 启用巡逻=args.patrol)
    from 机器人.机器人模拟器 import 模拟机器人
    brain.注册机器人(模拟机器人("模拟狗1"))
    brain.注册机器人(模拟机器人("模拟无人机1", robot_type="drone"))
    brain.启动()
