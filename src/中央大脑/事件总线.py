#!/usr/bin/env python3
"""事件总线 — 中央大脑内部发布/订阅，SSE 实时推送的基础"""
import queue, time, json


class 事件总线:
    """轻量级事件总线 — 模块间解耦 + SSE 推送"""

    def __init__(self):
        self._订阅者 = {}       # event_type → [callback, ...]
        self._sse队列 = queue.Queue()  # 所有事件→SSE 统一推送

    def 发布(self, 事件类型, 数据=None):
        """发布事件到总线"""
        event = {"type": 事件类型, "data": 数据, "time": time.time()}
        # 同步回调
        for cb in self._订阅者.get(事件类型, []):
            try:
                cb(event)
            except Exception as e:
                print(f"[事件总线] 回调异常 {事件类型}: {e}")
        # SSE 队列
        self._sse队列.put(event)

    def 订阅(self, 事件类型, 回调):
        """订阅某类事件"""
        self._订阅者.setdefault(事件类型, []).append(回调)

    def 取消订阅(self, 事件类型, 回调):
        if 事件类型 in self._订阅者:
            self._订阅者[事件类型] = [cb for cb in self._订阅者[事件类型] if cb != 回调]

    # ---- SSE 协议 ----

    def sse_生成(self):
        """SSE 生成器 — 持续监听队列，推送事件给客户端"""
        while True:
            try:
                event = self._sse队列.get(timeout=30)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"  # 心跳
