#!/usr/bin/env python3
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from 中央大脑.brain_registry import 机器人注册中心
from 中央大脑.brain_comm import 通信管理器
from 中央大脑.brain_web import Web面板
from 中央大脑.brain_llm import LLM调度引擎
from 中央大脑.brain_scheduler import 任务规划器
from 中央大脑.brain_ops_agent import 运维Agent

class 中央大脑:
    def __init__(self, web_host="0.0.0.0", web_port=5000):
        self.registry = 机器人注册中心()
        self.comm = 通信管理器(self.registry)
        self.llm = LLM调度引擎()
        self.scheduler = 任务规划器()
        self.ops_agent = 运维Agent(self.registry)
        self.web = Web面板(self.registry, self.comm, web_host, web_port)
        self._running = False

    def 启动(self):
        print("=" * 50)
        print("  中央大脑 v1.0 - 异构多机器人调度系统")
        print("=" * 50)
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
                        self.comm.发送指令(r.robot_id, o); break

    def 注册机器人(self, robot):
        self.registry.注册(robot)
        if robot.connect():
            print(f"[中央大脑] {robot.robot_id} 连接成功")
        else:
            print(f"[中央大脑] {robot.robot_id} 连接失败")

if __name__ == "__main__":
    brain = 中央大脑()
    from 机器人.机器人模拟器 import 模拟机器人
    brain.注册机器人(模拟机器人("模拟狗1"))
    brain.注册机器人(模拟机器人("模拟无人机1", robot_type="drone"))
    brain.启动()
