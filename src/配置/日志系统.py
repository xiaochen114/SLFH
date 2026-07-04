#!/usr/bin/env python3
"""系统日志 — 统一日志记录，控制台 + 文件按日期写入（只记 WARNING 及以上）"""
import os, sys, logging
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_日志器缓存 = {}
_已初始化 = False


def 获取日志器(模块名="系统"):
    """获取模块日志器，文件只记 WARNING+，控制台 INFO+"""
    global _已初始化

    if 模块名 in _日志器缓存:
        return _日志器缓存[模块名]

    日志器 = logging.getLogger(模块名)
    if _已初始化:
        _日志器缓存[模块名] = 日志器
        return 日志器

    日志器.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)-5s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # 文件输出 — 每天一个文件，只记 WARNING+
    日期 = datetime.now().strftime("%Y%m%d")
    fh = logging.FileHandler(
        os.path.join(LOG_DIR, f"系统_{日期}.log"),
        encoding="utf-8",
    )
    fh.setLevel(logging.WARNING)
    fh.setFormatter(fmt)
    日志器.addHandler(fh)

    # 控制台输出
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    日志器.addHandler(ch)

    _已初始化 = True
    _日志器缓存[模块名] = 日志器
    return 日志器
