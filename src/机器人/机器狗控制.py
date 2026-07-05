#!/usr/bin/env python3
"""
绝影Lite3 控制模块 (精简版)
基于: 运动主机通讯接口 V1.0.8
用途: 森林防火巡逻 - 只保留巡逻/避障/检测必需功能
"""
import socket, struct, time, threading, random

CMD = {
    'HEARTBEAT':    0x21040001,
    'STAND_LIE':    0x21010202,
    'ESTOP':        0x21020C0E,
    'HOME':         0x21010C05,
    'MODE_STAND':   0x21010D05,
    'MODE_MOVE':    0x21010D06,
    'AXIS_PITCH':   0x21010130,
    'AXIS_ROLL':    0x21010131,
    'AXIS_YAW':     0x21010135,
    'AXIS_HEIGHT':  0x21010102,
    'GAIT_SLOW':    0x21010300,
    'GAIT_MEDIUM':  0x21010307,
    'GAIT_FAST':    0x21010303,
    'GAIT_CREEP':   0x21010406,
    'GAIT_OBSTACLE':0x21010402,
    'MODE_AUTO':    0x21010C02,
    'CONT_MOTION':  0x21010C06,
}
ACTIONS = {
    'twist':    0x21010204,
    'flip':     0x21010205,
    'moonwalk': 0x2101030C,
    'wave':     0x21010507,
}
MAX_AXIS = 32767
DEAD_ZONE = {"pitch": 6553, "roll": 12553, "yaw": 9553}


class DogController:
    def __init__(self, ip="192.168.1.120", cmd_port=43893, state_port=43894):
        self.ip = ip
        self.cmd_port = cmd_port
        self.state_port = state_port
        self.sock = None
        self.connected = False
        self.state = {"mode": "idle", "battery": 0, "forward_distance": 4.5, "connected": False}
        self._stop = False
        self._axis = {"pitch": 0, "roll": 0, "yaw": 0}

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(2.0)
            threading.Thread(target=self._heartbeat, daemon=True).start()
            threading.Thread(target=self._state_recv, daemon=True).start()
            threading.Thread(target=self._axis_send, daemon=True).start()
            self.connected = True
            self.state["connected"] = True
            return True
        except Exception as e:
            print("[\u72d7] \u8fde\u63a5\u5931\u8d25: %s" % e)
            return False

    def close(self):
        self._stop = True
        if self.sock: self.sock.close()
        self.connected = False
        self.state["connected"] = False

    def _send(self, code, val=0):
        if self.sock:
            try: self.sock.sendto(struct.pack("<Iii", code, val, 0), (self.ip, self.cmd_port))
            except: pass

    def _heartbeat(self):
        while not self._stop:
            if self.sock: self._send(CMD["HEARTBEAT"])
            time.sleep(0.4)

    def _axis_send(self):
        while not self._stop:
            if self.connected and self.state["mode"] in ("patrolling", "avoiding"):
                for code, key in [(CMD["AXIS_PITCH"], "pitch"), (CMD["AXIS_ROLL"], "roll"), (CMD["AXIS_YAW"], "yaw")]:
                    v = self._axis[key]
                    self._send(code, v if abs(v) > DEAD_ZONE[key] else 0)
            time.sleep(0.05)

    def _state_recv(self):
        recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv.bind(("0.0.0.0", self.state_port))
        recv.settimeout(0.5)
        while not self._stop:
            try:
                data, _ = recv.recvfrom(512)
                if len(data) >= 120:
                    batt = struct.unpack_from("<d", data, 120 - 16)[0]
                    self.state["battery"] = batt if 0 <= batt <= 100 else self.state["battery"]
                if len(data) >= 136:
                    d = struct.unpack("<d", data[-16:-8])[0]
                    if 0.28 <= d <= 4.50: self.state["forward_distance"] = d
            except: pass
        recv.close()

    # ===== basic control =====
    def stand_up(self):
        self._send(CMD["STAND_LIE"])

    def lie_down(self):
        self._send(CMD["STAND_LIE"])

    def emergency_stop(self):
        self._send(CMD["ESTOP"])
        self.state["mode"] = "alert"

    def go_home(self):
        self._send(CMD["HOME"])

    def set_mode_stand(self):
        self._send(CMD["MODE_STAND"])

    def set_mode_move(self):
        self._send(CMD["MODE_MOVE"])

    def set_gait(self, name):
        m = {"slow": CMD["GAIT_SLOW"], "medium": CMD["GAIT_MEDIUM"],
             "fast": CMD["GAIT_FAST"], "creep": CMD["GAIT_CREEP"],
             "obstacle": CMD["GAIT_OBSTACLE"]}
        if name in m:
            self._send(m[name])

    def set_continuous_motion(self, on):
        val = -1 if on else 2
        self._send(CMD["CONT_MOTION"], val)

    def do_action(self, name):
        if name in ACTIONS:
            self._send(ACTIONS[name])

    def set_auto_mode(self):
        self._send(CMD["MODE_AUTO"])

    # ===== patrol =====
    def start_patrol(self, speed=20000):
        if self.state["mode"] != "patrolling":
            self._send(CMD["MODE_MOVE"])
            time.sleep(0.1)
        self._axis["pitch"] = speed
        self.state["mode"] = "patrolling"

    def stop_patrol(self):
        for k in self._axis: self._axis[k] = 0
        for c in [CMD["AXIS_PITCH"], CMD["AXIS_ROLL"], CMD["AXIS_YAW"], CMD["AXIS_HEIGHT"]]:
            self._send(c, 0)
        self.state["mode"] = "idle"

    def perform_avoidance(self):
        if self.state["mode"] in ("avoiding", "alert"): return
        old = self.state["mode"]
        self.state["mode"] = "avoiding"
        self._axis["pitch"] = -15000
        time.sleep(0.8)
        self._axis["pitch"] = 0
        self._axis["yaw"] = 15000 if random.choice([True, False]) else -15000
        time.sleep(0.6)
        self._axis["yaw"] = 0
        self.state["mode"] = old
        if old == "patrolling": self.start_patrol()

    def alert(self):
        self.emergency_stop()
