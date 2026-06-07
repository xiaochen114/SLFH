# train.py
import os

from sympy import false

os.environ["CUDA_VISIBLE_DEVICES"] = "0"   # 强制只使用 NVIDIA 独显

import torch
from ultralytics import YOLO

# 把诊断代码放到主程序保护块内，这样只会在主进程中执行一次
if __name__ == '__main__':
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"CUDA 是否可用: {torch.cuda.is_available()}")
    print(f"可用的 GPU 数量: {torch.cuda.device_count()}")
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            print(f"GPU {i}: {torch.cuda.get_device_name(i)}")

    # 加载模型
    model = YOLO('yolov8n.pt')   # 替换成你的模型路径

    # 开始训练
    results = model.train(
        data="E:/zy/训练集/火焰烟雾数据集/dataset.yaml",
        epochs=100,
        imgsz=320 ,
        batch=24,
        workers=4,
        cache=False,
        amp=True,
        device=0          # 此时 device=0 指向的就是唯一的 NVIDIA 卡
    )