#!/usr/bin/env python3
"""感知主机诊断器 — 192.168.1.103"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def 获取诊断器():
    """感知主机(192.168.1.103)诊断器"""
    return {
        "类型": "感知主机",
        "ssh": {"host": "192.168.1.103", "user": "ysc", "pass": "'"},
        "检查": [
            {"名称": "ping通", "命令": "ping -c1 {host} -W2 && echo OK"},
            {"名称": "transfer服务", "命令": "systemctl is-active transfer_ros2"},
            {"名称": "IMU数据", "命令": "timeout 2 ros2 topic hz /imu/data 2>&1 | tail -3"},
            {"名称": "雷达数据", "命令": "timeout 2 ros2 topic hz /rslidar_points 2>&1 | tail -3"},
            {"名称": "雷达驱动", "命令": "ps aux | grep -v grep | grep -E 'lslidar|rslidar|livox' | head -2"},
        ],
        "修复": [
            {"匹配": "inactive", "动作": "systemctl start transfer_ros2", "级别": "低危"},
            {"匹配": "no new messages", "动作": "systemctl restart transfer_ros2", "级别": "低危"},
            {"匹配": "0 publishers", "动作": "systemctl restart transfer_ros2", "级别": "低危"},
        ],
        "验证": [
            {"名称": "ping验证", "命令": "ping -c1 {host} -W2 && echo OK"},
            {"名称": "服务验证", "命令": "systemctl is-active transfer_ros2"},
        ],
    }
