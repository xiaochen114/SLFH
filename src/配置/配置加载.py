#!/usr/bin/env python3
"""配置加载 — 从 YAML 读取系统配置"""
import os

# 项目根目录（src 的上一级）
项目根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONFIG = {
    'model_path': os.path.join(项目根, 'runs', 'detect', 'train-2', 'weights', 'best.pt'),
    'conf_thresh': 0.5, 'detect_interval': 0.2,
    'camera_url': 0, 'frame_width': 640, 'frame_height': 480,
    'motion_ip': '192.168.1.120', 'cmd_port': 43893, 'state_port': 43894,
    'forward_speed': 20000, 'safe_dist': 0.5, 'sensor_type': 'ultrasonic',
    'http_host': '0.0.0.0', 'http_port': 5000,
}


def 加载配置(path='配置.yaml'):
    """从YAML配置文件读取参数，文件不存在时返回默认配置"""
    import yaml
    try:
        with open(path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        print(f"[配置] 已加载: {path}")
        return {**DEFAULT_CONFIG, **(cfg or {})}
    except FileNotFoundError:
        print(f"[配置] 未找到 {path}，使用默认配置")
        return dict(DEFAULT_CONFIG)


def 保存配置(cfg, path='配置.yaml'):
    """保存配置到 YAML 文件"""
    import yaml
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
    print(f"[配置] 已保存: {path}")
