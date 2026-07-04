#!/usr/bin/env python3
"""
训练火焰烟雾吸烟检测模型 (3类: smoke, fire, cigarette)
直接用已合并好的数据集，无需重复合并

用法: python scripts/train_merged.py
"""
from ultralytics import YOLO
import os

# ====== 配置 ======
EPOCHS = 100
BATCH = 16
IMGSZ = 640
MODEL = 'yolo11n.pt'  # 或 yolo11s.pt / yolo11m.pt

# 合并数据集路径（已包含火情+吸烟数据，3类）
DATA_YAML = r'E:\zy\训练集\火焰烟雾吸烟数据集\dataset.yaml'

if __name__ == '__main__':
    import torch
    print(f"PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}")

    model = YOLO(MODEL)
    results = model.train(
        data=DATA_YAML,
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=BATCH,
        workers=4,
        cache=False,
        amp=True,
        device=0,
    )
    print(f"训练完成！模型保存在 runs/detect/ 目录")
    print(f"训练完成后请将 配置.yaml 中的 model_path 指向新的 best.pt")
