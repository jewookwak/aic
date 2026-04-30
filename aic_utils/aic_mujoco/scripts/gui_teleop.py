#!/usr/bin/env python3
"""
MuJoCo GUI 텔레오퍼레이션 스크립트.

마우스 클릭으로 로봇을 조종합니다. RustDesk 등 원격 환경에서도 동작합니다.

사용법:
    python3 gui_teleop.py
"""

import threading
import time
import tkinter as tk

import numpy as np
import rclpy
from aic_control_interfaces.msg import MotionUpdate, TargetMode, TrajectoryGenerationMode
from aic_control_interfaces.srv import ChangeTargetMode
from geometry_msgs.msg import Twist, Vector3, Wrench
from rclpy.node import Node

SLOW_VEL = 0.02
FAST_VEL = 0.10
CONTROLLER_NS = "aic_controller"


class TeleopNode(Node):
    def __init__(self):
        super().__init__("gui_teleop_node")
        self._pub = self.create_publisher(
            MotionUpdate, f"/{CONTROLLER_NS}/pose_commands", 10
        )
        self._client = self.create_client(
            ChangeTargetMode, f"/{CONTROLLER_NS}/change_target_mode"
        )
        self._vel = FAST_VEL
        self._frame = "gripper/tcp"
        self._twist = np.zeros(6)
        self.create_timer(0.04, self._publish)  # 25Hz

    def set_cartesian_mode(self):
        self._client.wait_for_service(timeout_sec=10.0)
        req = ChangeTargetMode.Request()
        req.target_mode.mode = TargetMode.MODE_CARTESIAN
        future = self._client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

    def set_velocity(self, vx=0.0, vy=0.0, vz=0.0, wx=0.0, wy=0.0, wz=0.0):
        self._twist = np.array([vx, vy, vz, wx, wy, wz]) * self._vel

    def stop(self):
        self._twist = np.zeros(6)

    def _publish(self):
        t = self._twist
        twist = Twist()
        twist.linear.x, twist.linear.y, twist.linear.z = float(t[0]), float(t[1]), float(t[2])
        twist.angular.x, twist.angular.y, twist.angular.z = float(t[3]), float(t[4]), float(t[5])

        msg = MotionUpdate()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame
        msg.velocity = twist
        msg.target_stiffness = np.diag([85.0] * 6).flatten().tolist()
        msg.target_damping = np.diag([75.0] * 6).flatten().tolist()
        msg.feedforward_wrench_at_tip = Wrench(
            force=Vector3(x=0.0, y=0.0, z=0.0),
            torque=Vector3(x=0.0, y=0.0, z=0.0),
        )
        msg.wrench_feedback_gains_at_tip = [0.0] * 6
        msg.trajectory_generation_mode.mode = TrajectoryGenerationMode.MODE_VELOCITY
        self._pub.publish(msg)


class GUITeleop:
    def __init__(self, node: TeleopNode):
        self._node = node
        self._root = tk.Tk()
        self._root.title("AIC GUI Teleop")
        self._root.resizable(False, False)
        self._build_ui()

    def _build_ui(self):
        root = self._root
        PAD = 6
        BTN_W = 6
        BTN_H = 2

        def btn(parent, text, row, col, press_fn, colspan=1):
            b = tk.Button(parent, text=text, width=BTN_W, height=BTN_H, font=("Arial", 11, "bold"))
            b.grid(row=row, column=col, columnspan=colspan, padx=2, pady=2)
            b.bind("<ButtonPress-1>", lambda e: press_fn())
            b.bind("<ButtonRelease-1>", lambda e: self._node.stop())
            return b

        # ── Translation ──────────────────────────────────
        tf = tk.LabelFrame(root, text="Translation", padx=PAD, pady=PAD, font=("Arial", 10))
        tf.grid(row=0, column=0, padx=10, pady=6)

        btn(tf, "Y+\n(w)", 0, 1, lambda: self._node.set_velocity(vy=-1.0))
        btn(tf, "Z+\n(r)", 0, 2, lambda: self._node.set_velocity(vz=-1.0))
        btn(tf, "X-\n(a)", 1, 0, lambda: self._node.set_velocity(vx=-1.0))
        btn(tf, "Y-\n(s)", 1, 1, lambda: self._node.set_velocity(vy=1.0))
        btn(tf, "X+\n(d)", 1, 2, lambda: self._node.set_velocity(vx=1.0))
        btn(tf, "Z-\n(f)", 2, 2, lambda: self._node.set_velocity(vz=1.0))

        # ── Rotation ──────────────────────────────────────
        rf = tk.LabelFrame(root, text="Rotation", padx=PAD, pady=PAD, font=("Arial", 10))
        rf.grid(row=0, column=1, padx=10, pady=6)

        btn(rf, "Rx+", 0, 0, lambda: self._node.set_velocity(wx=1.0))
        btn(rf, "Rx-", 0, 1, lambda: self._node.set_velocity(wx=-1.0))
        btn(rf, "Ry+", 1, 0, lambda: self._node.set_velocity(wy=1.0))
        btn(rf, "Ry-", 1, 1, lambda: self._node.set_velocity(wy=-1.0))
        btn(rf, "Rz+\n(e)", 2, 0, lambda: self._node.set_velocity(wz=1.0))
        btn(rf, "Rz-\n(q)", 2, 1, lambda: self._node.set_velocity(wz=-1.0))

        # ── Settings ──────────────────────────────────────
        sf = tk.LabelFrame(root, text="Settings", padx=PAD, pady=PAD, font=("Arial", 10))
        sf.grid(row=1, column=0, columnspan=2, padx=10, pady=6, sticky="ew")

        self._vel_var = tk.StringVar(value="FAST")
        self._frame_var = tk.StringVar(value="gripper/tcp")

        tk.Label(sf, text="Speed:", font=("Arial", 10)).grid(row=0, column=0, sticky="w")
        slow_btn = tk.Button(sf, text=f"SLOW\n({SLOW_VEL} m/s)", width=8,
                             command=self._set_slow, font=("Arial", 9))
        slow_btn.grid(row=0, column=1, padx=4)
        fast_btn = tk.Button(sf, text=f"FAST\n({FAST_VEL} m/s)", width=8,
                             command=self._set_fast, font=("Arial", 9), relief="sunken")
        fast_btn.grid(row=0, column=2, padx=4)
        self._slow_btn = slow_btn
        self._fast_btn = fast_btn

        tk.Label(sf, text="Frame:", font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=4)
        tcp_btn = tk.Button(sf, text="TCP\n(gripper)", width=8,
                            command=self._set_tcp, font=("Arial", 9), relief="sunken")
        tcp_btn.grid(row=1, column=1, padx=4)
        global_btn = tk.Button(sf, text="Global\n(base)", width=8,
                               command=self._set_global, font=("Arial", 9))
        global_btn.grid(row=1, column=2, padx=4)
        self._tcp_btn = tcp_btn
        self._global_btn = global_btn

        # ── Status ────────────────────────────────────────
        self._status = tk.Label(root, text="Ready", fg="green",
                                font=("Arial", 10), anchor="w")
        self._status.grid(row=2, column=0, columnspan=2, padx=10, pady=4, sticky="ew")

    def _set_slow(self):
        self._node._vel = SLOW_VEL
        self._slow_btn.config(relief="sunken")
        self._fast_btn.config(relief="raised")
        self._status.config(text=f"Speed: SLOW ({SLOW_VEL} m/s)")

    def _set_fast(self):
        self._node._vel = FAST_VEL
        self._slow_btn.config(relief="raised")
        self._fast_btn.config(relief="sunken")
        self._status.config(text=f"Speed: FAST ({FAST_VEL} m/s)")

    def _set_tcp(self):
        self._node._frame = "gripper/tcp"
        self._tcp_btn.config(relief="sunken")
        self._global_btn.config(relief="raised")
        self._status.config(text="Frame: gripper/tcp (TCP)")

    def _set_global(self):
        self._node._frame = "base_link"
        self._tcp_btn.config(relief="raised")
        self._global_btn.config(relief="sunken")
        self._status.config(text="Frame: base_link (Global)")

    def run(self):
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.mainloop()

    def _on_close(self):
        self._node.stop()
        self._root.destroy()
        rclpy.shutdown()


def main():
    rclpy.init()
    node = TeleopNode()

    print("Waiting for aic_controller subscriber...")
    while node._pub.get_subscription_count() == 0:
        rclpy.spin_once(node, timeout_sec=0.5)
    print("Connected! Setting Cartesian mode...")
    node.set_cartesian_mode()
    print("Ready.")

    ros_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    ros_thread.start()

    gui = GUITeleop(node)
    gui.run()

    node.destroy_node()


if __name__ == "__main__":
    main()
