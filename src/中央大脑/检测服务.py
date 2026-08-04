#!/usr/bin/env python3
"""YOLO 火情检测服务 — 包装 PerceptionSystem，检测结果写入事件库"""
import time, threading


class 检测服务:
    """后台轮询 YOLO 检测，检测到火情/烟雾写入带标签的事件库"""

    def __init__(self, 事件总线, 数据库=None, 模型路径=None, 摄像头=0, 置信度=0.5, 间隔=1.0):
        self._bus = 事件总线
        self._db = 数据库
        self._模型路径 = 模型路径
        self._摄像头 = 摄像头
        self._置信度 = 置信度
        self._间隔 = 间隔
        self._感知 = None
        self._线程 = None
        self._running = False
        self._上次等级 = 0  # 只在新等级出现时发事件，避免刷屏

    def 启动(self):
        """启动 YOLO 检测（后台线程）"""
        try:
            from 检测.火情检测 import PerceptionSystem
            self._感知 = PerceptionSystem(
                model_path=self._模型路径,
                camera_url=self._摄像头,
                conf_thresh=self._置信度,
                detect_interval=self._间隔,
            )
            if not self._感知.start():
                print("[检测] 摄像头启动失败")
                return False
            self._running = True
            self._线程 = threading.Thread(target=self._轮询, daemon=True)
            self._线程.start()
            print("[检测] YOLO 火情检测已启动")
            return True
        except Exception as e:
            print(f"[检测] 启动异常: {e}")
            return False

    def 停止(self):
        self._running = False
        if self._感知:
            self._感知.stop()

    def _轮询(self):
        while self._running and self._感知:
            try:
                r = self._感知.get_result()
                level = r.alert_level
                if level != self._上次等级:
                    self._上次等级 = level
                    if level >= 3:
                        self._产生("fire_detected", r, "火焰", level, priority=2)  # 特急
                    elif level == 2:
                        self._产生("smoke_detected", r, "烟雾", level, priority=1)  # 紧急
                    elif level == 1:
                        self._产生("cigarette_detected", r, "烟头", level, priority=0)  # 普通
            except:
                pass
            time.sleep(self._间隔)

    def _产生(self, 事件类型, r, 名称, level, priority=0):
        """检测到事件：写数据库（贴标签+紧急度）+ 广播"""
        dets = [{"name": d.name, "confidence": d.confidence} for d in r.detections]
        data = {
            "alert_level": level,
            "detections": dets,
            "position": (0, 0),  # YOLO 无定位，位置由机器狗回传
        }
        prio_label = {2: "特急", 1: "紧急", 0: "普通"}[priority]
        print(f"[检测] 发现{名称}！[{prio_label}] 等级={level} {dets}")
        # 写入事件库，贴标签（来源=yolo + 紧急度）
        if self._db:
            self._db.记录事件(
                source="yolo",
                type=事件类型,
                label=名称,
                level=level,
                priority=priority,
                data=data,
            )
        # 广播（SSE 前端实时显示）
        if self._bus:
            self._bus.发布(事件类型, {**data, "priority": priority})

