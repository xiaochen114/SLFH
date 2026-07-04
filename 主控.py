#!/usr/bin/env python3
"""森林防火巡逻系统 - 入口 shim"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
os.chdir(os.path.join(os.path.dirname(__file__), 'src'))

from main import main

if __name__ == '__main__':
    main()
