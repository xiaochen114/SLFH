# 森林防火巡逻系统

YOLO火情检测 + 绝影Lite3机器狗控制 + Web可视化面板

## 项目结构

```
E:\zy\
├── 主控.py                  # 主入口
├── 机器狗控制.py            # 绝影Lite3 UDP控制模块
├── 火情检测.py              # YOLO火情/烟雾/烟头检测
├── 配置.yaml                # 唯一配置源
├── web_dashboard.html       # Web控制面板
├── requirements.txt         # Python依赖
├── README.md                # 本文件
│
├── scripts/                 # 训练脚本
│   ├── train.py             # 火情检测模型训练
│   ├── train_merged.py      # 合并吸烟数据集训练
│   ├── prepare_data.py      # 数据准备
│   └── keyboard_control.py  # 键盘遥控机器狗
│
├── models/                  # 模型文件
├── runs/                    # 训练结果(含模型权重)
├── 训练集/
│   ├── 火焰烟雾数据集/       # 火焰+烟雾数据集(完整，可直接训练)
│   ├── 吸烟数据集_源/        # 吸烟数据集源文件
│   └── 合并数据集_不完整/     # 合并尝试(缺少标签，不完整)
│
└── 旧版/                    # 归档的旧版本文件
```

## 快速开始

```bash
pip install -r requirements.txt
```

## 运行

```bash
# 真机模式(连接机器狗)
python 主控.py

# 模拟模式(不连机器狗，调试检测用)
python 主控.py --simulate

# 仅启动Web面板
python 主控.py --web-only

# 指定Web端口
python 主控.py --port 8080
```

打开 http://localhost:5000 查看控制面板。

## 训练模型

### 火情检测(烟雾+火焰)
```bash
python scripts/train.py
```

### 火情+吸烟检测(烟雾+火焰+烟头)
```bash
python scripts/train_merged.py
```

训练完成后修改 `配置.yaml` 的 `model_path`。

## 机器狗遥控
```bash
python scripts/keyboard_control.py
```

## 技术栈

- **检测**: YOLOv8 (Ultralytics)
- **机器狗**: 云深处绝影Lite3 (UDP协议)
- **面板**: Flask + HTML
- **训练**: PyTorch + CUDA
