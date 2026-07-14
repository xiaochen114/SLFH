#!/usr/bin/env python3
"""中央大脑 — 异构多机器人调度系统（入口）"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
os.chdir(os.path.join(os.path.dirname(__file__), 'src'))

if __name__ == '__main__':
    from 中央大脑.main import main
    main()
