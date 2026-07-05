# 森林防火巡逻系统

YOLO 火情检测 + 绝影Lite3 机器狗控制 + 中央大脑调度

## 项目结构

```
E:\zy\
├── 主控.py                  # 入口（自动跳转 src/）
│
├── src/                     # 核心源码
│   ├── main.py              # 巡逻系统主入口（YOLO + 机器狗 + Web）
│   ├── 配置.yaml            # 系统配置源
│   ├── 巡逻点.yaml           # 巡逻点位配置（可持久化）
│   ├── requirements.txt     # Python 依赖
│   │
│   ├── 配置/                 # 配置与基础模块
│   │   ├── 配置加载.py        # YAML 配置加载
│   │   └── 日志系统.py        # 统一日志（控制台 + 文件，WARNING+）
│   │
│   ├── 检测/                 # 火情检测模块
│   │   └── 火情检测.py        # YOLO 实时检测（火焰/烟雾/烟头）
│   │
│   ├── 机器人/               # 机器狗控制
│   │   ├── robot_base.py     # 机器人抽象基类 + 数据类型定义
│   │   ├── 机器狗控制.py      # 绝影Lite3 UDP 通讯封装
│   │   ├── 机器狗_绝影.py     # RobotBase 适配实现
│   │   ├── 感知主机控制.py    # SSH 操控感知主机 ROS2 导航
│   │   └── 机器人模拟器.py    # 模拟机器人（测试用）
│   │
│   ├── 中央大脑/              # 多机器人调度系统（核心）
│   │   ├── main.py           # 中央大脑入口，组装所有模块
│   │   ├── 事件总线.py        # 发布/订阅 + SSE 实时推送
│   │   ├── 数据库.py          # SQLite 持久化（状态快照/任务日志）
│   │   ├── 监控告警.py        # 异常检测（低电量/断连/健康）
│   │   ├── 巡逻数据类型.py    # 巡逻点/状态 data class
│   │   ├── 自主巡逻.py        # 巡逻调度器（点管理 + 导航控制）
│   │   ├── brain_registry.py # 机器人注册中心
│   │   ├── brain_comm.py     # 通信管理器（路由/缓存/重连）
│   │   ├── brain_llm.py      # LLM 调度引擎（DeepSeek API + 规则降级）
│   │   ├── brain_scheduler.py# 任务规划器
│   │   ├── brain_ops_agent.py# 运维诊断
│   │   └── brain_web.py      # RESTful API v1 + SSE + 巡逻接口
│   │
│   ├── 面板/                 # 可视化界面
│   │   ├── web服务器.py       # Flask Web 服务器
│   │   ├── web_dashboard.html# 管理面板（总览/机器人/巡逻/日志）
│   │   └── 桌面端.py          # Tkinter 桌面控制端
│   │
│   ├── 脚本/                 # 训练与工具
│   │   ├── train.py          # 火情检测模型训练
│   │   ├── train_merged.py   # 合并数据集训练
│   │   ├── keyboard_control.py# 键盘遥控机器狗
│   │   ├── merge_dataset.py  # 数据集合并
│   │   └── ...
│   │
│   ├── models/               # YOLO 模型权重
│   ├── runs/                 # 训练产出
│   └── data/                 # 运行时数据
│       ├── logs/             # 日志文件（系统_YYYYMMDD.log）
│       └── *.json            # 敏感数据（已 gitignore）
│
├── 文档/                     # 项目文档
│   ├── 系统架构设计.md
│   ├── 项目路线图.md
│   ├── 智能体实现计划.md
│   └── *.pdf                 # 绝影Lite3 官方开发手册
│
├── 资源/                     # 静态资源
├── 归档/                     # 旧版代码
├── 第三方/                   # 外部工具包
├── 训练集/                   # 数据集
├── .gitignore
└── README.md
```

## 快速开始

```bash
pip install -r src/requirements.txt
```

## 运行

```bash
# 森林防火巡逻系统（真机）
python 主控.py

# 模拟模式
python 主控.py --simulate

# 中央大脑（多机器人调度）
python src/中央大脑/main.py
```

打开 http://localhost:5000 查看管理面板。

## 中央大脑 API

统一响应格式 `{code, message, data}`：

| 端点 | 说明 |
|------|------|
| `GET /api/v1/health` | 健康检查 |
| `GET /api/v1/status` | 全景状态 |
| `GET /api/v1/robots` | 机器人列表 |
| `GET /api/v1/robots/<id>` | 机器人详情 |
| `POST /api/v1/command` | 下发指令 |
| `GET /api/v1/events` | SSE 实时事件流 |
| `GET /api/v1/alerts` | 告警列表 |
| `GET /api/v1/history/tasks` | 任务日志 |
| `GET /api/v1/history/robots` | 状态历史 |
| `POST/GET /api/v1/patrol/points` | 巡逻点管理 |
| `POST /api/v1/patrol/start` | 开始巡逻 |
| `POST /api/v1/patrol/stop` | 停止巡逻 |

## 技术栈

- **检测**: YOLOv8 (Ultralytics)
- **机器狗**: 云深处绝影Lite3 (UDP 协议)
- **后端**: Python + Flask + SQLite
- **实时推送**: SSE (Server-Sent Events)
- **前端**: 纯 HTML/CSS/JS 单页应用
- **LLM**: DeepSeek API（自动降级规则引擎）
- **训练**: PyTorch + CUDA