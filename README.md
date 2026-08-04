# 森林防火巡逻系统 · 异构多机器人中央调度

YOLO 火情检测 + 绝影Lite3 机器狗控制 + 中央大脑智能调度 + 运维自愈

> 一套"中央大脑 + 异构机器人统一接口"架构，以森林防火为落地场景。
> 未来可扩展至安防、搜救、农业等多机器人协同。

---

## 项目结构

```
E:\zy\
├── 主控.py                  # 唯一入口（真机/模拟）
│
├── src/                     # 核心源码
│   ├── 配置.yaml            # 系统配置源（含内网LLM参数）
│   ├── 巡逻点.yaml           # 巡逻点位配置（可持久化）
│   ├── requirements.txt     # Python 依赖
│   │
│   ├── 配置/                 # 配置与基础模块
│   │   ├── 配置加载.py        # YAML 配置加载
│   │   └── 日志系统.py        # 统一日志（控制台 + 文件）
│   │
│   ├── 检测/                 # 火情检测模块
│   │   └── 火情检测.py        # YOLO 实时检测（火焰/烟雾/烟头）
│   │
│   ├── 机器人/               # 机器人控制层
│   │   ├── robot_base.py     # RobotBase 抽象基类 + 数据类型
│   │   ├── 机器狗控制.py      # 绝影Lite3 UDP 通讯封装
│   │   ├── 机器狗_绝影.py     # RobotBase 适配实现
│   │   ├── 感知主机控制.py    # SSH 操控感知主机 ROS2
│   │   └── 机器人模拟器.py    # 模拟机器人（测试用）
│   │
│   ├── 中央大脑/              # 多机器人调度系统（核心）
│   │   ├── main.py           # 中央大脑入口，组装所有模块
│   │   ├── 事件总线.py        # 发布/订阅 + SSE 实时推送
│   │   ├── 数据库.py          # SQLite 持久化（状态/任务/事件）
│   │   ├── 监控告警.py        # 异常检测（低电量/断连/健康）
│   │   ├── 检测服务.py        # YOLO 检测服务（事件入数据库）
│   │   ├── 运维自愈.py        # 自愈框架（诊断器+高危闸门+LLM增强）
│   │   ├── 记忆管理器.py      # LLM 对话记忆（历史拼接，可升级RAG）
│   │   ├── 诊断脚本_感知主机.py # 感知主机诊断器
│   │   ├── 诊断脚本_绝影.py    # 绝影诊断器
│   │   ├── 自主巡逻.py        # 巡逻调度器
│   │   ├── 巡逻数据类型.py    # 巡逻点/状态 data class
│   │   ├── brain_registry.py # 机器人注册中心
│   │   ├── brain_comm.py     # 通信管理器（路由/缓存/重连）
│   │   ├── brain_llm.py      # LLM 调度引擎（API + 规则降级 + 自动重连）
│   │   ├── brain_scheduler.py# 任务规划器
│   │   └── brain_web.py      # RESTful API v1 + SSE
│   │
│   ├── 面板/                 # 可视化界面
│   │   └── web_dashboard.html# 管理面板（由中央大脑 brain_web 服务）
│   │
│   ├── 脚本/                 # 训练与工具
│   │   ├── train.py          # 火情检测模型训练
│   │   └── train_merged.py   # 合并数据集训练
│   │
│   ├── models/               # YOLO 模型权重
│   ├── runs/                 # 训练产出
│   └── data/                 # 运行时数据（SQLite/日志）
│
├── docs/ 文档/ 归档/ 旧版/ 第三方/ 训练集/
└── README.md
```

---

## 快速开始

```bash
pip install -r src/requirements.txt
```

## 运行

```bash
# 真机模式（注册绝影Lite3）
python 主控.py

# 模拟模式（不连真狗）
python 主控.py --simulate

# 带自主巡逻（需感知主机在线）
python 主控.py --patrol
```

打开 http://localhost:5000 查看管理面板。

---

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
| `GET /api/v1/history/stats` | 系统统计 |
| `POST/GET /api/v1/patrol/points` | 巡逻点管理 |
| `POST /api/v1/patrol/start` | 开始巡逻 |
| `POST /api/v1/patrol/stop` | 停止巡逻 |
| `GET /api/v1/llm/status` | LLM 连接状态 |
| `GET /api/v1/llm/history` | LLM 决策记录（流水）|
| `GET /api/v1/chat/history` | 操作员↔LLM 对话历史 |
| `POST /api/v1/chat/send` | 发送对话给 LLM（可生成待确认指令）|
| `GET /api/v1/orders/pending` | 待确认指令 |
| `POST /api/v1/orders/confirm` | 确认/拒绝待确认指令 |
| `POST /api/v1/orders/intervene` | 人工接管下发指令 |
| `GET /api/v1/intervention/history` | 干预审计日志 |
| `GET /api/v1/selfheal/status` | 自愈系统状态 |
| `GET /api/v1/selfheal/pending` | 待确认高危操作 |
| `POST /api/v1/selfheal/confirm` | 确认/拒绝高危操作 |
| `GET /api/v1/selfheal/history` | 自愈历史 |

---

## 智能调度

中央大脑的调度闭环：

```
监控告警/检测服务 → 事件入库（带标签）
    ↓
调度循环(2s) → 取未消费事件
    ↓
特急事件(火焰) → 硬编码急停所有机器人（不过LLM）
    ↓
普通事件 → LLM调度引擎 → 规则降级 → 下发指令
    ↓
运维自愈 → 异常自动诊断修复（低危自动/高危人工）
```

### LLM 调度引擎

- 优先调用大模型 API 做调度决策
- API 不可用 → 自动降级规则模式，后台每 30s 重连
- 单次请求 8s 超时，防止调度循环卡死
- 配置在 `配置.yaml` 的 `llm_api_url/key/model`

### 运维自愈

- 通用诊断器注册表，新设备 `注册诊断器()` 即接入
- 规则诊断优先（ping/查服务/查数据），每步带标签进事件库
- 低危操作自动修复，高危操作 Web 面板人工确认
- 规则查不出 → LLM 增强分析

---

## 技术栈

- **检测**: YOLOv8 (Ultralytics)
- **机器狗**: 云深处绝影Lite3 (UDP 协议) + ROS2
- **后端**: Python + Flask + SQLite + paramiko(SSH)
- **实时推送**: SSE (Server-Sent Events)
- **前端**: 纯 HTML/CSS/JS 单页应用
- **LLM**: OpenAI 兼容 API（DeepSeek/内网算力中心/本地Ollama）
- **训练**: PyTorch + CUDA
