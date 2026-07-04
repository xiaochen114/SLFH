#!/usr/bin/env python3
"""合并火情数据集 + 吸烟检测数据集，生成完整训练集"""
import os, shutil, glob

FIRE_DIR = '/sessions/upbeat-gracious-ramanujan/mnt/zy/训练集/Multi-Scale-Fire-Smoke-and-Flame-Dataset'
SMOKE_ZIP = '/sessions/upbeat-gracious-ramanujan/mnt/AI生成/Smoking Detection.v1i.yolov8.zip'
OUT_DIR = '/sessions/upbeat-gracious-ramanujan/mnt/zy/训练集/Fire-Smoke-Cigarette-Dataset'

# 类别映射（合并后的）
CLASSES = ['smoke', 'fire', 'cigarette']
NC = len(CLASSES)

# 1. 解压吸烟数据集
import zipfile
extract_dir = '/tmp/smoking_data'
os.makedirs(extract_dir, exist_ok=True)
with zipfile.ZipFile(SMOKE_ZIP, 'r') as zf:
    zf.extractall(extract_dir)

print("吸烟数据集解压完成")

# 2. 创建输出目录
for split in ['train', 'val', 'test']:
    os.makedirs(f'{OUT_DIR}/{split}/images', exist_ok=True)
    os.makedirs(f'{OUT_DIR}/{split}/labels', exist_ok=True)

# 3. 复制火情数据（保持类别0,1不变）
print("复制火情数据...")
for split, src_split in [('train', 'train'), ('val', 'val'), ('test', 'test')]:
    imgs = glob.glob(f'{FIRE_DIR}/{src_split}/images/*')
    for img_path in imgs:
        shutil.copy2(img_path, f'{OUT_DIR}/{split}/images/')
    lbls = glob.glob(f'{FIRE_DIR}/{src_split}/labels/*')
    for lbl_path in lbls:
        shutil.copy2(lbl_path, f'{OUT_DIR}/{split}/labels/')
    print(f"  {split}: {len(imgs)}张已复制")

# 4. 复制吸烟数据（类别0→2重编号）
print("复制吸烟数据...")
for split, src_split in [('train', 'train'), ('val', 'valid'), ('test', 'test')]:
    imgs = glob.glob(f'{extract_dir}/{src_split}/images/*')
    for img_path in imgs:
        dst = f'{OUT_DIR}/{split}/images/'
        # 避免文件名冲突
        base = os.path.basename(img_path)
        dst_path = f'{dst}/cig_{base}'
        # 如果文件已存在就跳过
        if not os.path.exists(dst_path):
            shutil.copy2(img_path, dst_path)
    lbls = glob.glob(f'{extract_dir}/{src_split}/labels/*')
    for lbl_path in lbls:
        base = os.path.basename(lbl_path)
        dst_lbl = f'{OUT_DIR}/{split}/labels/cig_{base}'
        if os.path.exists(dst_lbl):
            continue
        with open(lbl_path) as f:
            lines = f.readlines()
        with open(dst_lbl, 'w') as f:
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if not parts:
                    continue
                # 类别0→2 (cigarette)
                cls_id = int(parts[0]) + 2
                parts[0] = str(cls_id)
                f.write(' '.join(parts) + '\n')
    print(f"  {split}: {len(imgs)}张已复制(类别0→2)")

# 5. 创建dataset.yaml
yaml_content = f"""# Fire + Smoke + Cigarette 合并数据集
path: {OUT_DIR}
train: train/images
val: val/images
test: test/images

nc: {NC}
names: {CLASSES}
"""
with open(f'{OUT_DIR}/dataset.yaml', 'w') as f:
    f.write(yaml_content)

# 6. 统计
print("\n=== 合并结果 ===")
for split in ['train', 'val', 'test']:
    imgs = len(glob.glob(f'{OUT_DIR}/{split}/images/*'))
    lbls = len(glob.glob(f'{OUT_DIR}/{split}/labels/*'))
    print(f"{split}: {imgs} images, {lbls} labels")
print(f"类别: {CLASSES}")
print(f"\ndataset.yaml -> {OUT_DIR}/dataset.yaml")
print("完成!")
