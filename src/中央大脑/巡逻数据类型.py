#!/usr/bin/env python3
"""巡逻数据类型 — 巡逻点和巡逻状态的 data class"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class 巡逻点:
    x: float
    y: float
    yaw: float = 0.0
    name: str = ""


@dataclass
class 巡逻状态:
    运行中: bool = False
    当前点索引: int = -1
    当前点: Optional[巡逻点] = None
    状态: str = "idle"     # idle/导航中/停留/跳过/完成
    总点数: int = 0
    日志: list = field(default_factory=list)
