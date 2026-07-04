#!/usr/bin/env python3
"""系统日志 — 统一日志记录，控制台 + 文件滚动写入"""
import os, sys, time, logging
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_handler = None


def 获取日志器(模块名="系统"):
    """获取或创建模块日志器，保证只初始化一次"""
    global _handler

    日志器 = logging.getLogger(模块名)
    if _handler is not None:
        return 日志器

    日志器.setLevel(logging.DEBUG)

    # 格式
    fmt = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)-5s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # 文件滚动输出（单文件 5MB，保留 3 个）
    fh = RotatingFileHandler(
        os.path.join(LOG_DIR, "中央大脑.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    日志器.addHandler(fh)

    # 控制台输出
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    日志器.addHandler(ch)

    _handler = fh  # 防止被回收
    return 日志器


def 快速日志(模块名="系统"):
    """快速获取日志器的别名"""
    return 获取日志器(模块名)
