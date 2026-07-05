#!/usr/bin/env python3
"""
机器人抽象基类 — 所有机器人的标准接口
任何机器人/设备实现此接口即可接入中央大脑
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# ======================== 数据类型定义 ========================

@dataclass
class RobotOrder:
    """中央大脑下发给末端的任务指令"""
    order_id: str                          # 指令唯一ID
    type: str                              # patrol / inspect / alert / return / custom
    params: dict = field(default_factory=dict)  # 参数 {target:[x,y], speed:1.0, ...}
    priority: int = 0                      # 0=低 1=中 2=高 3=紧急
    source: str = "brain"                  # 来源 brain / web / auto


@dataclass
class RobotStatus:
    """末端上报给中央大脑的状态"""
    robot_id: str
    robot_type: str                        # dog / drone / other
    position: tuple = (0.0, 0.0, 0.0)     # (x, y, yaw)
    battery: float = 0.0                   # 0.0 ~ 1.0
    mode: str = "idle"                     # idle / patrolling / alert / returning / charging
    health: str = "ok"                     # ok / warning / error
    communication_level: int = 1           # 1=在线(L1) 2=弱连接(L2) 3=断连(L3)
    extra: dict = field(default_factory=dict)  # 各机器人特有状态
    timestamp: float = 0.0                 # 时间戳


@dataclass
class OrderResult:
    """指令执行结果"""
    order_id: str
    success: bool
    message: str = ""
    data: dict = field(default_factory=dict)


# ======================== 抽象基类 ========================

class RobotBase(ABC):
    """所有机器人必须实现的基类"""

    def __init__(self, robot_id: str):
        self._robot_id = robot_id
        self._connected = False

    # === 基本信息 ===

    @property
    def robot_id(self) -> str:
        return self._robot_id

    @abstractmethod
    def get_capabilities(self) -> list:
        """返回机器人能力列表，如 ['move','camera','detect','audio','carry']"""
        ...

    # === 生命周期 ===

    @abstractmethod
    def connect(self) -> bool:
        """建立与机器人的连接"""
        ...

    def disconnect(self):
        """断开连接，默认实现设 connected=False"""
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    # === 控制 ===

    @abstractmethod
    def execute_order(self, order: RobotOrder) -> OrderResult:
        """执行中央下发的指令，返回执行结果"""
        ...

    # === 状态 ===

    @abstractmethod
    def get_status(self) -> RobotStatus:
        """获取机器人当前状态"""
        ...

    # === 视频 ===

    def get_video_frame(self):
        """
        返回当前视频帧（JPEG 编码字节）
        无摄像头返回 None
        """
        return None

    def get_video_fps(self) -> int:
        return 0

    # === 边缘自主（断连降级）===

    def on_communication_lost(self):
        """断网时调用 — 进入边缘自主模式"""
        pass

    def on_communication_restored(self):
        """重连时调用 — 同步离线数据"""
        pass
