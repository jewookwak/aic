#!/usr/bin/env python3
"""
Ground truth TF publisher for MuJoCo simulation.

ati/tool_link TF를 RSP(URDF FK)에서 직접 조회한 뒤 weld 변환 체인으로
sfp_tip_link 위치를 계산합니다. MJCF FK 대신 TF를 사용하므로
CheatCode의 gripper/tcp 조회와 좌표계가 일치합니다.
"""

import logging
import os
from datetime import datetime

import rclpy
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import (
    TransformBroadcaster,
    StaticTransformBroadcaster,
    Buffer,
    TransformListener,
    TransformException,
)
from geometry_msgs.msg import TransformStamped
import mujoco
import numpy as np

MJCF_PATH = "/home/jewoo2963/ws_aic/src/aic/aic_utils/aic_mujoco/mjcf/scene.xml"

TARGET_MODULE_NAME = "nic_card_mount_0"
PORT_NAME = "sfp_port_0"
CABLE_NAME = "cable_0"
PLUG_NAME = "sfp_tip"

MUJOCO_PORT_BODY = "sfp_port_0_link"

TF_PORT_FRAME = f"task_board/{TARGET_MODULE_NAME}/{PORT_NAME}_link"
TF_TIP_FRAME = f"{CABLE_NAME}/{PLUG_NAME}_link"

# weld 제약: ati/tool_link → lc_plug_link
WELD_POS = np.array([-0.000711, 0.001759, 0.168213])
WELD_QUAT = np.array([0.577301, 0.816105, -0.021418, -0.015395])  # [w,x,y,z]

# lc_plug_link → sfp_module_link
LC_TO_SFP_MODULE_POS = np.array([0.0, 0.0384001, 0.0])
LC_TO_SFP_MODULE_QUAT = np.array([0.0, 1.0, 0.0, 0.0])  # 180° around x

# sfp_module_link → sfp_tip_link
SFP_MODULE_TO_TIP_POS = np.array([0.0, -0.02365, 0.0])
SFP_MODULE_TO_TIP_QUAT = np.array([0.707105, 0.707108, 0.0, 0.0])


def quat_mul(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
    ])


def quat_rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    qv = np.array([0.0, v[0], v[1], v[2]])
    q_conj = np.array([q[0], -q[1], -q[2], -q[3]])
    result = quat_mul(quat_mul(q, qv), q_conj)
    return result[1:]


def compose_transform(pos_a, quat_a, pos_b, quat_b):
    pos_out = pos_a + quat_rotate(quat_a, pos_b)
    quat_out = quat_mul(quat_a, quat_b)
    quat_out /= np.linalg.norm(quat_out)
    return pos_out, quat_out


def compute_tip_from_tool(tool_pos: np.ndarray, tool_quat: np.ndarray):
    lc_pos, lc_quat = compose_transform(tool_pos, tool_quat, WELD_POS, WELD_QUAT)
    sfp_pos, sfp_quat = compose_transform(lc_pos, lc_quat,
                                          LC_TO_SFP_MODULE_POS, LC_TO_SFP_MODULE_QUAT)
    tip_pos, tip_quat = compose_transform(sfp_pos, sfp_quat,
                                          SFP_MODULE_TO_TIP_POS, SFP_MODULE_TO_TIP_QUAT)
    return tip_pos, tip_quat


class GroundTruthTFPublisher(Node):
    def __init__(self):
        super().__init__("mujoco_ground_truth_tf")

        log_dir = os.path.expanduser("~/cheatcode_logs")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"ground_truth_{ts}.log")
        self._flog = logging.getLogger(f"GroundTruth_{ts}")
        self._flog.setLevel(logging.DEBUG)
        handler = logging.FileHandler(log_path)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        self._flog.addHandler(handler)
        self._flog.info(f"GroundTruth log started: {log_path}")

        # MuJoCo 모델: 포트 위치(정적) 계산에만 사용
        self._model = mujoco.MjModel.from_xml_path(MJCF_PATH)
        self._data = mujoco.MjData(self._model)

        self._port_id = mujoco.mj_name2id(
            self._model, mujoco.mjtObj.mjOBJ_BODY, MUJOCO_PORT_BODY
        )
        if self._port_id < 0:
            self.get_logger().error(f"Body '{MUJOCO_PORT_BODY}' not found in MJCF!")

        self._static_broadcaster = StaticTransformBroadcaster(self)
        self._dynamic_broadcaster = TransformBroadcaster(self)

        # TF listener: RSP에서 ati/tool_link 조회
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        # 포트는 정적 — 한 번만 publish
        mujoco.mj_kinematics(self._model, self._data)
        self._publish_static_port()

        self.create_timer(0.02, self._publish_tip_tf)  # 50Hz

        self.get_logger().info(
            f"Publishing TF:\n"
            f"  static : world → {TF_PORT_FRAME}\n"
            f"  dynamic: world → {TF_TIP_FRAME}\n"
            f"  (tip computed from TF ati/tool_link + weld transform)"
        )

    def _make_transform(self, pos, quat, child_frame: str) -> TransformStamped:
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = "world"
        t.child_frame_id = child_frame
        t.transform.translation.x = float(pos[0])
        t.transform.translation.y = float(pos[1])
        t.transform.translation.z = float(pos[2])
        t.transform.rotation.w = float(quat[0])
        t.transform.rotation.x = float(quat[1])
        t.transform.rotation.y = float(quat[2])
        t.transform.rotation.z = float(quat[3])
        return t

    def _publish_static_port(self):
        port_id = self._port_id
        pos = self._data.xpos[port_id]
        quat = self._data.xquat[port_id]  # [w,x,y,z]
        t = self._make_transform(pos, quat, TF_PORT_FRAME)
        self._static_broadcaster.sendTransform([t])
        msg = (
            f"[PORT] Static port TF: "
            f"pos=({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f}) "
            f"quat=({quat[0]:.4f}, {quat[1]:.4f}, {quat[2]:.4f}, {quat[3]:.4f})"
        )
        self.get_logger().info(msg)
        self._flog.info(msg)

    def _publish_tip_tf(self):
        # RSP TF에서 ati/tool_link world 위치 조회
        try:
            tf_stamped = self._tf_buffer.lookup_transform(
                "world", "ati/tool_link", Time()
            )
        except TransformException:
            return  # TF 아직 없으면 skip

        tr = tf_stamped.transform.translation
        ro = tf_stamped.transform.rotation
        tool_pos = np.array([tr.x, tr.y, tr.z])
        tool_quat = np.array([ro.w, ro.x, ro.y, ro.z])  # [w,x,y,z]

        tip_pos, tip_quat = compute_tip_from_tool(tool_pos, tool_quat)

        t = self._make_transform(tip_pos, tip_quat, TF_TIP_FRAME)
        self._dynamic_broadcaster.sendTransform(t)

        # 1초마다 디버그 로그
        if not hasattr(self, '_dbg_count'):
            self._dbg_count = 0
        self._dbg_count += 1
        if self._dbg_count % 50 == 1:
            msg1 = f"[DBG] ati/tool_link(world)=({tool_pos[0]:.4f},{tool_pos[1]:.4f},{tool_pos[2]:.4f})"
            msg2 = f"[DBG] sfp_tip(world)=({tip_pos[0]:.4f},{tip_pos[1]:.4f},{tip_pos[2]:.4f})"
            self.get_logger().info(msg1)
            self.get_logger().info(msg2)
            self._flog.info(msg1)
            self._flog.info(msg2)


def main():
    rclpy.init()
    node = GroundTruthTFPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
