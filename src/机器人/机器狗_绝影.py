#!/usr/bin/env python3
"""
绝影Lite3 机器狗 — RobotBase 实现
封装原 机器狗控制.py 的 DogController，适配标准接口
"""
import time
from 机器人.robot_base import RobotBase, RobotOrder, RobotStatus, OrderResult
from 机器人.机器狗控制 import DogController


class 机器狗_绝影(RobotBase):
    """绝影Lite3 机器狗适配层"""

    def __init__(self, robot_id: str = "绝影1号",
                 ip: str = "192.168.1.120",
                 cmd_port: int = 43893,
                 state_port: int = 43894):
        super().__init__(robot_id)
        self._dog = DogController(ip=ip, cmd_port=cmd_port, state_port=state_port)

    def get_capabilities(self) -> list:
        return ["move", "camera", "detect", "ultrasonic"]

    def connect(self) -> bool:
        self._connected = self._dog.connect()
        return self._connected

    def disconnect(self):
        self._dog.close()
        self._connected = False

    def execute_order(self, order: RobotOrder) -> OrderResult:
        if not self._connected:
            return OrderResult(order.order_id, False, "机器狗未连接")

        try:
            if order.type == "stand":
                self._dog.stand_up()
                return OrderResult(order.order_id, True, "起立")

            elif order.type == "lie":
                self._dog.lie_down()
                return OrderResult(order.order_id, True, "趴下")

            elif order.type == "patrol":
                speed = order.params.get("speed", 20000)
                self._dog.start_patrol(speed)
                return OrderResult(order.order_id, True, f"开始巡逻 速度{speed}")

            elif order.type == "stop":
                self._dog.stop_patrol()
                return OrderResult(order.order_id, True, "停止")

            elif order.type == "alert":
                self._dog.alert()
                return OrderResult(order.order_id, True, "紧急停止")

            elif order.type == "return":
                self._dog.stop_patrol()
                self._dog.go_home()
                return OrderResult(order.order_id, True, "开始回零")

            elif order.type == "gait":
                name = order.params.get("name", "medium")
                self._dog.set_gait(name)
                return OrderResult(order.order_id, True, f"切换步态:{name}")

            elif order.type == "continuous":
                on = order.params.get("on", False)
                self._dog.set_continuous_motion(on)
                return OrderResult(order.order_id, True, f"持续运动:{'开' if on else '关'}")

            elif order.type == "action":
                name = order.params.get("name", "wave")
                self._dog.do_action(name)
                return OrderResult(order.order_id, True, f"执行动作:{name}")

            return OrderResult(order.order_id, False, f"未知指令:{order.type}")

        except Exception as e:
            return OrderResult(order.order_id, False, f"执行异常:{e}")

    def get_status(self) -> RobotStatus:
        s = self._dog.state
        dog_mode = s.get("mode", "idle")
        mode_map = {"idle": "idle", "patrolling": "patrolling",
                    "avoiding": "patrolling", "alert": "alert"}
        return RobotStatus(
            robot_id=self._robot_id,
            robot_type="dog",
            position=(0.0, 0.0, 0.0),  # 绝影不上报GPS
            battery=s.get("battery", 0.0) / 100.0,
            mode=mode_map.get(dog_mode, "idle"),
            health="ok",
            communication_level=1 if self._connected else 3,
            extra={"forward_distance": s.get("forward_distance", 4.5)},
            timestamp=time.time(),
        )

    def get_video_frame(self):
        """从机器狗摄像头取一帧 (RTSP)"""
        try:
            import cv2
            url = "rtsp://192.168.1.120:8554/test"
            cap = cv2.VideoCapture(url)
            if not cap.isOpened():
                return None
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return None
            ret, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            return jpeg.tobytes() if ret else None
        except:
            return None

    def get_video_fps(self) -> int:
        return 10

    def on_communication_lost(self):
        """断连 — 进入边缘自主模式"""
        self._dog.set_continuous_motion(True)
        print(f"[{self._robot_id}] 断连，进入边缘自主模式")

    def on_communication_restored(self):
        """重连 — 退出边缘自主"""
        self._dog.set_continuous_motion(False)
        print(f"[{self._robot_id}] 重连，恢复中央调度")


if __name__ == "__main__":
    # 模拟测试
    dog = 机器狗_绝影("绝影测试", ip="192.168.1.120")
    print(dog.robot_id, dog.get_capabilities())
