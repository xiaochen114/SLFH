#!/usr/bin/env python3
"""一键下载训练所需的数据和模型"""
import os, zipfile, urllib.request, sys

BASE = os.path.dirname(os.path.abspath(__file__))

# 需要下载的数据集
DATASETS = {
    'fire_smoke': {
        'url': 'https://universe.roboflow.com/roboflow-100/smoke-uvylj',
        'desc': '火情数据集（Roboflow，训练时自动加载）',
    },
}

def download_file(url, path):
    """下载文件"""
    print(f"下载中: {url}")
    try:
        urllib.request.urlretrieve(url, path)
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False

def main():
    print("=" * 50)
    print("  森林防火 - 训练数据准备")
    print("=" * 50)

    # 确认数据集位置
    fire_dir = r'E:\zy\训练集\Multi-Scale-Fire-Smoke-and-Flame-Dataset'
    smoke_zip = r'D:\AI生成\Smoking Detection.v1i.yolov8.zip'

    if os.path.exists(fire_dir):
        print(f"[OK] 火情数据集: {fire_dir}")
    else:
        print(f"[!] 火情数据集不存在，需从Roboflow下载")
        print(f"    下载地址: https://universe.roboflow.com/search?q=fire+smoke+dataset")

    if os.path.exists(smoke_zip):
        print(f"[OK] 吸烟数据集: {smoke_zip}")
    else:
        print(f"[!] 吸烟数据集不存在，需从Roboflow下载")
        print(f"    下载地址: https://universe.roboflow.com/harran-uni-ceng/smoking-detection-qwx74")

    print("\n训练命令:")
    print("  python scripts/train_merged.py")
    print("\n或单独训练火情模型:")
    print("  python scripts/train.py")
    print("\n说明:")
    print("  - YOLO模型权重会自动下载（需联网）")
    print("  - 数据集合并脚本会自动处理类别映射")
    print("  - 训练结果保存到 runs/detect/ 目录")

if __name__ == '__main__':
    main()
