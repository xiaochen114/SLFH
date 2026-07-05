#!/usr/bin/env python3
"""YOLO火情检测模块 - 独立可复用"""
import time, threading
from dataclasses import dataclass, field
from typing import List, Dict

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
    def __init__(self, model_path="E:/zy/runs/detect/fire_smoke_cigarette/weights/best.pt"
                 camera_url=0, conf_thresh=0.5, detect_interval=0.2,
                 frame_width=640, frame_height=480):
        self.model_path = model_path
        self.camera_url = camera_url
        self.conf_thresh = conf_thresh
        self.detect_interval = detect_interval
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.model = None
        self.cap = None
        self.running = False
        self._lock = threading.Lock()
        self._latest = None
        self._annotated = None
        self.result = PerceptionResult()

    def start(self):
        from ultralytics import YOLO
        import cv2
        self.model = YOLO(self.model_path)
        self.cap = cv2.VideoCapture(self.camera_url)
        if not self.cap.isOpened():
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()
        return True

    def _loop(self):
        import cv2
        last = 0
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue
            now = time.time()
            if now - last >= self.detect_interval:
                last = now
                try:
                    results = self.model(frame, conf=self.conf_thresh, verbose=False)
                    self._process(results)
                except:
                    pass
            with self._lock:
                self._annotated = results[0].plot() if 'results' in dir() and results else frame.copy()
            time.sleep(0.03)

    def _process(self, results):
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
            self.result.fire = fire
            self.result.smoke = smoke
            self.result.cigarette = cig
            self.result.detections = dets
            self.result.alert_level = 3 if fire else 2 if smoke else 1 if cig else 0

    def get_result(self) -> PerceptionResult:
        with self._lock:
            import copy
            return copy.deepcopy(self.result)

    def get_annotated_frame(self):
        with self._lock:
            return self._annotated.copy() if self._annotated is not None else None

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
