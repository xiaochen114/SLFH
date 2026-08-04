#!/usr/bin/env python3
"""YOLO火情检测模块 - 独立可复用"""
import os, time, threading
from dataclasses import dataclass, field
from typing import List, Dict

# 项目根目录（检测 的上一级）
项目根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
默认模型 = os.path.join(项目根, 'runs', 'detect', 'fire_smoke_cigarette', 'weights', 'best.pt')

@dataclass
class Detection:
    class_id: int
    name: str
    confidence: float
    bbox: List[float]

@dataclass
class PerceptionResult:
    fire: bool = False
    smoke: bool = False
    cigarette: bool = False
    alert_level: int = 0  # 0=正常 1=烟头 2=烟雾 3=火焰
    detections: List[Detection] = field(default_factory=list)
    fps: float = 0
    frame_count: int = 0


class PerceptionSystem:
    """多路视频流检测 — 共享单个 YOLO 模型
    支持 camera_url 为单个源或列表: [0, 'rtsp://...', 'demo.mp4']
    每路独立结果和标注帧, 带 source 标签"""

    def __init__(self, model_path=None,
                 camera_url=0, conf_thresh=0.5, detect_interval=0.2,
                 frame_width=640, frame_height=480):
        if model_path is None:
            model_path = 默认模型
        self.model_path = model_path
        # 统一为列表: [0, 'rtsp://...', 'demo.mp4']
        self.sources = [camera_url] if not isinstance(camera_url, list) else camera_url
        self.conf_thresh = conf_thresh
        self.detect_interval = detect_interval
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.model = None
        self._caps = {}          # source_id -> VideoCapture
        self.running = False
        self._lock = threading.Lock()
        self._results = {}       # source_id -> PerceptionResult
        self._frames = {}        # source_id -> 最新标注帧

    def start(self):
        from ultralytics import YOLO
        import cv2
        self.model = YOLO(self.model_path)
        for i, src in enumerate(self.sources):
            cap = cv2.VideoCapture(src)
            if not cap.isOpened():
                print(f"[检测] 源{i}({src}) 打开失败")
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            self._caps[i] = cap
            self._results[i] = PerceptionResult()
        if not self._caps:
            return False
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()
        return True

    def _loop(self):
        import cv2
        last = 0
        while self.running:
            for src_id, cap in list(self._caps.items()):
                ret, frame = cap.read()
                if not ret:
                    continue
                now = time.time()
                if now - last >= self.detect_interval:
                    last = now
                    try:
                        results = self.model(frame, conf=self.conf_thresh, verbose=False)
                        self._process(src_id, results)
                    except:
                        pass
                    annotated = results[0].plot() if results else frame.copy()
                else:
                    annotated = frame.copy()
                with self._lock:
                    self._frames[src_id] = annotated
            time.sleep(0.03)

    def _process(self, src_id, results):
        fire = smoke = cig = False
        dets = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                name = self.model.names.get(cls_id, str(cls_id))
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                dets.append(Detection(cls_id, name, round(conf, 3), [round(x, 1) for x in [x1, y1, x2, y2]]))
                nl = name.lower()
                if 'fire' in nl or 'flame' in nl: fire = True
                elif 'smoke' in nl: smoke = True
                elif 'cigarette' in nl or 'cigar' in nl: cig = True
        with self._lock:
            r = self._results.setdefault(src_id, PerceptionResult())
            r.fire = fire
            r.smoke = smoke
            r.cigarette = cig
            r.detections = dets
            r.alert_level = 3 if fire else 2 if smoke else 1 if cig else 0

    def get_result(self, src_id=None) -> PerceptionResult:
        """取某路结果；src_id=None 取所有路中最高等级"""
        with self._lock:
            import copy
            if src_id is not None:
                r = self._results.get(src_id, PerceptionResult())
                return copy.deepcopy(r)
            # 汇总: 取所有路最高 alert_level
            汇总 = PerceptionResult()
            for r in self._results.values():
                if r.alert_level > 汇总.alert_level:
                    汇总.alert_level = r.alert_level
                    汇总.fire, 汇总.smoke, 汇总.cigarette = r.fire, r.smoke, r.cigarette
                    汇总.detections = r.detections
            return copy.deepcopy(汇总)

    def get_annotated_frame(self, src_id=None):
        """取某路标注帧；src_id=None 取第一路"""
        with self._lock:
            if src_id is not None:
                f = self._frames.get(src_id)
            else:
                f = next(iter(self._frames.values()), None) if self._frames else None
            return f.copy() if f is not None else None

    def get_source_ids(self):
        return list(self._caps.keys())

    def stop(self):
        self.running = False
        for cap in self._caps.values():
            cap.release()
        self._caps.clear()
