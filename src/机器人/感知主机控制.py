#!/usr/bin/env python3
"""
感知主机控制 — 通过SSH操控感知主机ROS2导航
基于 绝影Lite3感知开发手册 V2.2.3 第8章

主机: 192.168.1.103, 用户: ysc
ROS2路径: ~/lite_cog_ros2/
"""
import time, threading, os
from dataclasses import dataclass

HOST = "192.168.1.103"
USER = "ysc"
PASS = "'"

PATHS = {
    "lidar_leishen":   "~/lite_cog_ros2/system/scripts/lidar/start_lslidar.sh",
    "lidar_livox":     "~/lite_cog_ros2/system/scripts/lidar/start_livox.sh",
    "lidar_robosense": "~/lite_cog_ros2/system/scripts/lidar/start_rslidar.sh",
    "start_nav":       "~/lite_cog_ros2/system/scripts/nav/start_nav.sh",
}


@dataclass
class NavStatus:
    running: bool = False
    state: str = "idle"        # idle/navigating/arrived/failed/blocked
    current_goal: tuple = None
    robot_pose: tuple = None


class 感知主机控制:
    """SSH封装 — 操控感知主机ROS2导航"""

    def __init__(self, host=HOST, user=USER, password=PASS):
        self._host = host
        self._user = user
        self._pass = password
        self._ssh = None
        self._connected = False
        self._nav_proc = None   # SSH channel for long-running nav
        self._stop = False
        self._status = NavStatus()

    # ========== 连接 ==========

    def connect(self) -> bool:
        try:
            import paramiko
            self._ssh = paramiko.SSHClient()
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._ssh.connect(self._host, username=self._user,
                            password=self._pass, timeout=5)
            self._connected = True
            print(f"[感知主机] 已连接 {self._host}")
            return True
        except ImportError:
            print("[感知主机] 需要 pip install paramiko --break-system-packages")
            return False
        except Exception as e:
            print(f"[感知主机] 连接失败: {e}")
            return False

    def close(self):
        self._stop = True
        self.stop_navigation()
        if self._ssh:
            self._ssh.close()
        self._connected = False

    # ========== 基础命令 ==========

    def _exec(self, cmd, timeout=10):
        """执行短命令，返回 (stdout, stderr)"""
        if not self._ssh:
            return None, "未连接"
        try:
            _, stdout, stderr = self._ssh.exec_command(cmd, timeout=timeout)
            return stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace")
        except Exception as e:
            return None, str(e)

    def _exec_bg(self, cmd):
        """后台启动长时间运行的命令，返回 channel"""
        if not self._ssh:
            return None
        t = self._ssh.get_transport()
        ch = t.open_session()
        ch.exec_command(cmd)
        return ch

    # ========== 雷达 ==========

    def start_lidar(self, lidar_type="leishen"):
        script = PATHS.get(f"lidar_{lidar_type}")
        if not script:
            print(f"[感知主机] 未知雷达类型: {lidar_type}")
            return False
        out, err = self._exec(f"bash {script} &", timeout=5)
        time.sleep(2)
        # 验证
        ping, _ = self._exec("ping -c1 -W1 192.168.1.201 2>/dev/null && echo OK")
        if ping and "OK" in ping:
            print(f"[感知主机] {lidar_type} 雷达已启动")
            return True
        print(f"[感知主机] 雷达启动中（ping未确认）")
        return True

    def stop_lidar(self):
        self._exec("pkill -f lslidar; pkill -f livox; pkill -f rslidar", timeout=5)

    # ========== 导航 ==========

    def start_navigation(self) -> bool:
        """启动定位+导航 (hdl_localization + bt_navigator)"""
        # 先检查是否已运行
        out, _ = self._exec("ps aux | grep -v grep | grep bt_navigator")
        if out and "bt_navigator" in out:
            print("[感知主机] 导航已在运行")
            return True

        # 检查地图
        map_out, _ = self._exec("ls ~/lite_cog_ros2/system/map/*.yaml 2>/dev/null | head -1")
        if not map_out:
            print("[感知主机] 未找到地图文件，请先建图")
            return False

        # 后台启动导航
        self._nav_proc = self._exec_bg(f"bash {PATHS['start_nav']}")
        time.sleep(5)
        print("[感知主机] 导航已启动")
        print("  请在RViz中用2D Pose Estimate初始化定位")
        self._status.running = True
        return True

    def stop_navigation(self):
        self._exec("pkill -f bt_navigator; pkill -f hdl_localization", timeout=5)
        self._status.running = False
        self._status.state = "idle"

    def is_nav_running(self) -> bool:
        out, _ = self._exec("ps aux | grep -v grep | grep bt_navigator | wc -l")
        return out and int(out.strip()) > 0

    # ========== 目标点 ==========

    def send_goal(self, x: float, y: float, yaw: float = 0.0) -> bool:
        """通过 ros2 action 发送导航目标点 (Nav2 NavigateToPose)"""
        # 构造 ros2 action 目标点 JSON
        import math as _m
        qz = _m.sin(yaw / 2)
        qw = _m.cos(yaw / 2)
        json_str = (
            '{pose: {header: {frame_id: "map"}, '
            f'pose: {{position: {{x: {x}, y: {y}, z: 0.0}}, '
            f'orientation: {{z: {qz}, w: {qw}}}}}}}'
        )
        cmd = (
            f'source /home/ysc/lite_cog_ros2/nav/install/setup.bash && '
            f'ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose '
            f'\'{json_str}\' --feedback 2>/dev/null'
        )
        out, err = self._exec(cmd, timeout=10)
        if out and "accepted" in out.lower():
            self._status.current_goal = (x, y)
            self._status.state = "navigating"
            print(f"[感知主机] 目标点 ({x:.2f}, {y:.2f}) 已接受")
            return True
        print(f"[感知主机] 目标点发送失败: {err or out}")
        return False

    def cancel_goal(self):
        """取消当前导航目标"""
        self._exec(
            f'source /home/ysc/lite_cog_ros2/nav/install/setup.bash && '
            f'ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose '
            f'"{{}}" --cancel 2>/dev/null',
            timeout=5
        )
        self._status.state = "idle"

    # ========== 状态查询 ==========

    def get_nav_result(self) -> str:
        """查询最近一次导航结果: arrived/failed/blocked/navigating"""
        out, _ = self._exec(
            f'source /home/ysc/lite_cog_ros2/nav/install/setup.bash && '
            f'ros2 topic echo /navigate_to_pose/_action/status -n1 2>/dev/null | grep status',
            timeout=5
        )
        if not out:
            return "unknown"
        # Nav2 status: 0=UNKNOWN, 1=ACCEPTED, 2=EXECUTING, 3=CANCELING, 4=SUCCEEDED, 5=CANCELED, 6=ABORTED
        if "4" in out or "SUCCEEDED" in out:
            self._status.state = "arrived"
            return "arrived"
        if "6" in out or "ABORTED" in out:
            self._status.state = "failed"
            return "failed"
        if "2" in out or "EXECUTING" in out:
            return "navigating"
        return "unknown"

    def get_robot_pose(self) -> str:
        """获取机器狗当前位姿 (hdl_localization 发布的 /odom)"""
        out, _ = self._exec(
            f'source /home/ysc/lite_cog_ros2/nav/install/setup.bash && '
            f'ros2 topic echo /odom -n1 2>/dev/null | head -15',
            timeout=5
        )
        return out

    def get_status(self) -> NavStatus:
        """获取完整状态"""
        self._status.running = self.is_nav_running()
        if self._status.running and self._status.state == "navigating":
            self.get_nav_result()  # 更新状态
        return self._status

    @property
    def connected(self) -> bool:
        return self._connected


# ========== 测试 ==========
if __name__ == "__main__":
    ph = 感知主机控制()
    if ph.connect():
        print("1=启动雷达  2=启动导航  3=发目标点  4=查状态  5=停止导航  6=退出")
        while True:
            c = input("> ").strip()
            if c == "1":
                ph.start_lidar("leishen")
            elif c == "2":
                ph.start_navigation()
            elif c == "3":
                try:
                    x = float(input("  x: "))
                    y = float(input("  y: "))
                    ph.send_goal(x, y)
                except:
                    pass
            elif c == "4":
                s = ph.get_status()
                print(f"  导航运行:{s.running} 状态:{s.state} 目标:{s.current_goal}")
            elif c == "5":
                ph.stop_navigation()
            elif c == "6":
                break
        