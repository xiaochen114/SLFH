# 森林防火巡逻系统

YOLO 火情检测 + 绝影Lite3 机器狗控制 + Web 可视化面板

## 项目结构

```
E:\zy\
├── 主控.py                  # 入口 shim（自动跳转到 src/）
│
├── src/                     # 核心源码
│   ├── main.py              # 主入口
│   ├── 配置.yaml            # 唯一配置源
│   ├── requirements.txt     # Python 依赖
│   ├── 巡逻点.yaml           # 巡逻点位配置
│   │
│   ├── 检测/                 # 火情检测模块
│   │   └── 火情检测.py
│   │
│   ├── 机器人/               # 机器狗控制
│   │   ├── robot_base.py     # 机器人抽象基类
│   │   ├── 机器狗控制.py      # 绝影Lite3 UDP 控制
│   │   ├── 机器狗_绝影.py     # RobotBase 适配实现
│   │   ├── 感知主机控制.py    # 感知主机控制
│   │   └── 机器人模拟器.py    # 模拟器
│   │
│   ├── 中央大脑/              # 多机器人调度系统
│   │   ├── main.py           # 中央大脑入口
│   │   ├── brain_registry.py # 机器人注册中心
│   │   ├── brain_comm.py     # 通信管理器
│   │   ├── brain_llm.py      # LLM 后端
│   │   ├── brain_web.py      # Web 面板
│   │   ├── brain_scheduler.py# 调度器
│   │   ├── brain_ops_agent.py# 运维代理
│   │   └── 自主巡逻.py        # 自主巡逻
│   │
│   ├── 面板/                 # 可视化面板
│   │   ├── web_dashboard.html# Web 控制面板
│   │   └── 桌面端.py          # Tkinter 桌面控制端
│   │
│   ├── 通信桥/               # AI 通信桥（Hermes / Claude）
│   │   ├── ai_bridge_server.py
│   │   ├── ai_bridge_simple.py
│   │   ├── claude_bridge_client.py
│   │   ├── claude_client.js
│   │   ├── hermes_bridge.py
│   │   ├── hermes_bridge_monitor.py
│   │   ├── hermes_桥接.py
│   │   ├── AI_BRIDGE_README.md
│   │   └── ai_comm/          # 通信消息队列
│   │
│   ├── 脚本/                 # 训练/工具脚本
│   │   ├── train.py          # 火情检测模型训练
│   │   ├── train_merged.py   # 合并数据集训练
│   │   ├── keyboard_control.py# 键盘遥控机器狗
│   │   └── ...
│   │
│   ├── models/               # YOLO 模型文件
│   ├── runs/                 # 训练结果
│   ├── data/                 # 运行时数据
│   └── 训练集/                # 数据集
│
├── 文档/                     # 项目文档
│   ├── 系统架构设计.md
│   ├── 项目路线图.md
│   ├── 智能体实现计划.md
│   ├── 绝影Lite3 *.pdf       # 官方开发手册
│   └── ...
│
├── 资源/                     # 静态资源
├── 归档/                     # 旧版代码 / 备份
│   ├── 旧版/                 # 旧版本归档
│   └── .git.bak/            # Git 备份
│
├── 第三方/                   # 第三方工具包（独立项目）
│   ├── autonomous-dev-kit/
│   ├── skill-forge/
│   └── external-skills/
│
├── .gitignore
└── README.md
```

## 快速开始

```bash
pip install -r src/requirements.txt
```

## 运行

```bash
# 真机模式（连接机器狗）
python 主控.py

# 模拟模式（不连机器狗，调试检测用）
python 主控.py --simulate

# 仅启动 Web 面板
python 主控.py --web-only

# 指定 Web 端口
python 主控.py --port 8080
```

打开 http://localhost:5000 查看控制面板。

## 训练模型

```bash
# 火情检测（烟雾+火焰）
python src/脚本/train.py

# 火情+吸烟检测（烟雾+火焰+烟头）
python src/脚本/train_merged.py
```

训练完成后修改 `src/配置.yaml` 的 `model_path`。

## 机器狗遥控

```bash
python src/脚本/keyboard_control.py
```

## 技术栈

- **检测**: YOLOv8 (Ultralytics)
- **机器狗**: 云深处绝影Lite3 (UDP 协议)
- **面板**: Flask + HTML / Tkinter
- **训练**: PyTorch + CUDA
- **中央大脑**: 多机器人调度 + LLM 智能体
