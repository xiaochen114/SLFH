#!/usr/bin/env python3
"""YOLO 火情检测服务 — 多路视频流检测，结果带 source 标签写入事件库"""
import time, threading


class 检测服务:
    """后台轮询多路视频流 YOLO 检测
    任何一路检测到火情/烟雾 → 事件库(带 source 标签) + SSE 广播"""

    def __init__(self, 事件总线, 数据库=None, 模型路径=None, 视频源=None,
                 置信度=0.5, 间隔=1.0):
        self._bus = 事件总线
        self._db = 数据库
        self._模型路径 = 模型路径
        # 视频源: 单个(0/rtsp/文件) 或列表
        self._视频源 = 视频源 if isinstance(视频源, list) else ([视频源] if 视频源 is not None else [0])
        self._置信度 = 置信度
        self._间隔 = 间隔
        self._感知 = None
        self._线程 = None
        self._running = False
        self._上次等级 = {}  # source_id -> 上次等级，避免刷屏

    def 启动(self):
        try:
            from 检测.火情检测 import PerceptionSystem
            self._感知 = PerceptionSystem(
                model_path=self._模型路径,
                camera_url=self._视频源,   # 列表 → 多路
                conf_thresh=self._置信度,
                detect_interval=self._间隔,
            )
            if not self._感知.start():
                print("[检测] 视频源全部打开失败")
                return False
            self._running = True
            self._线程 = threading.Thread(target=self._轮询, daemon=True)
            self._线程.start()
            print(f"[检测] YOLO 火情检测已启动, {len(self._感知.sources)} 路视频源")
            return True
        except Exception as e:
            print(f"[检测] 启动异常: {e}")
            return False

    def 停止(self):
        self._running = False
        if self._感知:
            self._感知.stop()

    def 获取源列表(self):
        if not self._感知:
            return []
        return [{"id": i, "source": s} for i, s in enumerate(self._感知.sources)]

    def 获取标注帧(self, src_id=None):
        if not self._感知:
            return None
        return self._感知.get_annotated_frame(src_id)

    def _轮询(self):
        while self._running and self._感知:
            try:
                # 逐路检测，取各路结果
                for src_id in self._感知.get_source_ids():
                    r = self._感知.get_result(src_id)
                    level = r.alert_level
                    if level != self._上次等级.get(src_id, 0):
                        self._上次等级[src_id] = level
                        if level >= 3:
                            self._产生(src_id, "fire_detected", r, "火焰", level, priority=2)
                        elif level == 2:
                            self._产生(src_id, "smoke_detected", r, "烟雾", level, priority=1)
                        elif level == 1:
                            self._产生(src_id, "cigarette_detected", r, "烟头", level, priority=0)
            except:
                pass
            time.sleep(self._间隔)

    def _产生(self, src_id, 事件类型, r, 名称, level, priority=0):
        """检测到事件：写数据库（贴 source+标签+紧急度）+ 广播"""
        dets = [{"name": d.name, "confidence": d.confidence} for d in r.detections]
        data = {
            "source_id": src_id,
            "alert_level": level,
            "detections": dets,
            "position": (0, 0),  # YOLO 无定位，位置由机器狗回传
        }
        prio_label = {2: "特急", 1: "紧急", 0: "普通"}[priority]
        print(f"[检测][源{src_id}] 发现{名称}！[{prio_label}] 等级={level} {dets}")
        if self._db:
            self._db.记录事件(
                source="yolo",
                type=事件类型,
                label=名称,
                level=level,
                priority=priority,
                data=data,
            )
        if self._bus:
            self._bus.发布(事件类型, {**data, "priority": priority})
