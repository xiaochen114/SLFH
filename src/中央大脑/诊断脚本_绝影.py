#!/usr/bin/env python3
"""绝影Lite3 诊断器 — 192.168.1.120"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def 获取诊断器():
    """绝影Lite3(192.168.1.120)诊断器"""
    return {
        "类型": "绝影",
        "ssh": {"host": "192.168.1.120", "user": "ysc", "pass": "'"},
        "检查": [
            {"名称": "ping通", "命令": "ping -c1 {host} -W2 && echo OK"},
            {"名称": "运动主机进程", "命令": "ps aux | grep -v grep | grep jy_exe | head -2"},
            {"名称": "网络配置", "命令": "cat ~/jy_exe/conf/network.toml 2>/dev/null | head -10"},
        ],
        "修复": [
            {"匹配": "grep", "动作": "sudo systemctl restart jy_exe", "级别": "高危"},
            {"匹配": "网络配置", "动作": "sudo systemctl restart jy_exe", "级别": "高危"},
        ],
        "验证": [
            {"名称": "ping验证", "命令": "ping -c1 {host} -W2 && echo OK"},
            {"名称": "进程验证", "命令": "ps aux | grep -v grep | grep jy_exe | head -1"},
        ],
    }
