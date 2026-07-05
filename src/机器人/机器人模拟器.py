#!/usr/bin/env python3
import time, threading, random
from 机器人.robot_base import RobotBase, RobotOrder, RobotStatus, OrderResult

class 模拟机器人(RobotBase):
    def __init__(self, robot_id: str, robot_type: str = "dog"):
        super().__init__(robot_id)
        self._type = robot_type
        self._position = [0.0, 0.0, 0.0]
        self._battery = 0.85
        self._mode = "idle"
        self._health = "ok"
        self._comm_level = 1
        self._orders_log = []
        self._stop = False

    def get_capabilities(self) -> list:
        if self._type == "dog":
            return ["move", "camera", "detect", "ultrasonic"]
        elif self._type == "drone":
            return ["move", "camera", "fly", "relay"]
        return ["move"]

    def connect(self) -> bool:
        self._connected = True
        print(f"[模拟器] {self._robot_id} 已连接")
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()
        return True

    def _heartbeat_loop(self):
        while not self._stop and self._connected:
            time.sleep(3)
            self._battery = max(0.1, self._battery - 0.005)
            if random.random() < 0.05:
                self._health = random.choice(["warning", "error"])

    def execute_order(self, order: RobotOrder) -> OrderResult:
        self._orders_log.append(order)
        if order.type == "patrol":
            speed = order.params.get("speed", 1.0)
            self._position[0] += speed * 0.5
            self._mode = "patrolling"
            return OrderResult(order.order_id, True, f"开始巡逻 速度{speed}")
        elif order.type == "stand":
            self._mode = "idle"
            return OrderResult(order.order_id, True, "起立")
        elif order.type == "stop":
            self._mode = "idle"
            return OrderResult(order.order_id, True, "停止")
        elif order.type == "alert":
            self._mode = "alert"
            return OrderResult(order.order_id, True, "紧急停止")
        elif order.type == "return":
            self._mode = "returning"
            return OrderResult(order.order_id, True, "正在返航")
        elif order.type == "inspect":
            target = order.params.get("target", "unknown")
            return OrderResult(order.order_id, True, f"检查 {target}")
        elif order.type == "custom":
            cmd = order.params.get("command", "")
            return OrderResult(order.order_id, True, f"执行自定义: {cmd}")
        return OrderResult(order.order_id, False, f"未知指令类型: {order.type}")

    def get_status(self) -> RobotStatus:
        return RobotStatus(
            robot_id=self._robot_id, robot_type=self._type,
            position=tuple(self._position), battery=self._battery,
            mode=self._mode, health=self._health,
            communication_level=self._comm_level,
            extra={"orders_executed": len(self._orders_log)},
            timestamp=time.time(),
        )

    def get_video_frame(self):
        try:
            from PIL import Image, ImageDraw
            frame = Image.new("RGB", (320, 240), (20, 30, 50))
            draw = ImageDraw.Draw(frame)
            draw.text((10, 20), f"模拟器: {self._robot_id}", fill=(100, 200, 255))
            draw.text((10, 50), f"位置: ({self._position[0]:.1f}, {self._position[1]:.1f})", fill=(200, 200, 200))
            draw.text((10, 80), f"模式: {self._mode}  电量: {int(self._battery*100)}%", fill=(200, 200, 200))
            draw.text((10, 110), f"通信: L{self._comm_level}", fill=(200, 200, 100))
            import io
            buf = io.BytesIO()
            frame.save(buf, "JPEG")
            return buf.getvalue()
        except:
            return None

    def get_video_fps(self) -> int:
        return 5

    def disconnect(self):
        self._stop = True
        self._connected = False
        print(f"[模拟器] {self._robot_id} 已断开")

if __name__ == "__main__":
    r = 模拟机器人("模拟狗1")
    r.connect()
    print(r.get_status())
    r.disconnect()
