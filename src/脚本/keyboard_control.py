#!/usr/bin/env python3
"""键盘遥控绝影Lite3 - 独立运行"""
import sys, time, threading, socket, struct

IP = '192.168.1.120'
PORT = 43893
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(2.0)

def send(code, val=0):
    sock.sendto(struct.pack('<Iii', code, val, 0), (IP, PORT))

def heartbeat():
    while True:
        send(0x21040001)
        time.sleep(0.4)

threading.Thread(target=heartbeat, daemon=True).start()

# 轴值
axis_pitch = 0
axis_roll = 0
axis_yaw = 0

def axis_send():
    while True:
        # 持续发送轴指令（≥20Hz避免超时）
        for code, val in [(0x21010130, axis_pitch), (0x21010131, axis_roll), (0x21010135, axis_yaw)]:
            send(code, val)
        time.sleep(0.05)

threading.Thread(target=axis_send, daemon=True).start()

print("=== 绝影Lite3 键盘控制 ===")
print("1=原地模式  2=移动模式  3=起立/趴下  4=急停  5=回零")
print("W=前进  S=后退  A=左移  D=右移  Q=左转  E=右转")
print("F1~F7=切换步态  SPACE=停止  ESC=退出")
print(f"目标: {IP}:{PORT}")
print("=" * 40)

try:
    import keyboard as kb
    speed = 20000

    def on_key(e):
        global axis_pitch, axis_roll, axis_yaw
        k = e.name
        if e.event_type == 'down':
            if k == 'w': axis_pitch = speed
            elif k == 's': axis_pitch = -speed
            elif k == 'a': axis_roll = -speed
            elif k == 'd': axis_roll = speed
            elif k == 'q': axis_yaw = speed
            elif k == 'e': axis_yaw = -speed
            elif k == '1': send(0x21010D05); print('[原地模式]')
            elif k == '2': send(0x21010D06); print('[移动模式]')
            elif k == '3': send(0x21010202); print('[起立/趴下]')
            elif k == '4': send(0x21020C0E); print('[急停]')
            elif k == '5': send(0x21010C05); print('[回零]')
            elif k == 'space':
                axis_pitch = axis_roll = axis_yaw = 0
                for c in [0x21010130, 0x21010131, 0x21010135]: send(c, 0)
                print('[停止]')
            elif k == 'esc': return False
            # F1-F7 步态
            GAIT_KEYS = {'f1': 0x21010300, 'f2': 0x21010307, 'f3': 0x21010303,
                         'f4': 0x21010406, 'f5': 0x21010402, 'f6': 0x21010401, 'f7': 0x21010407}
            if k in GAIT_KEYS: send(GAIT_KEYS[k]); print(f'[步态 {k}]')
        else:  # release
            if k in ('w', 's'): axis_pitch = 0
            elif k in ('a', 'd'): axis_roll = 0
            elif k in ('q', 'e'): axis_yaw = 0

    kb.hook(on_key)
    kb.wait('esc')
except ImportError:
    print("安装 keyboard 库以获得键盘控制: pip install keyboard --break-system-packages")
    print("或使用已有的 control.py")
