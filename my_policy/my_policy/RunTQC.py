"""
TQC Policy for AIC Cable Insertion (inference only).

사전 학습된 TQC 모델을 로드하여 케이블 삽입 태스크를 수행합니다.
학습은 my_policy/scripts/train_tqc.py 스크립트를 사용하세요.

주의: sb3/tqc-FetchPickAndPlace-v1 (HuggingFace 공개 모델)은
  FetchPickAndPlace 태스크용으로 학습된 모델이며,
  관측/행동 공간이 AIC와 다르므로 직접 적용 불가합니다.
  train_tqc.py로 AIC 전용 모델을 학습한 후 사용하세요.
"""

import time
import numpy as np
from pathlib import Path

from sb3_contrib import TQC
from geometry_msgs.msg import Vector3, Twist, Wrench
from std_msgs.msg import Header

from aic_model.policy import (
    GetObservationCallback,
    MoveRobotCallback,
    Policy,
    SendFeedbackCallback,
)
from aic_control_interfaces.msg import MotionUpdate, TrajectoryGenerationMode
from aic_task_interfaces.msg import Task


# 학습된 모델 경로 (train_tqc.py 실행 후 생성)
DEFAULT_MODEL_PATH = "models/tqc_aic/tqc_aic_final.zip"

# 포트 TF 프레임 (CLAUDE.md 규칙)
PORT_FRAME_TEMPLATE = "task_board/{target_module_name}/{port_name}_link"

VEL_LIMIT = 0.05    # m/s, rad/s
CONTROL_HZ = 20     # 제어 주기
SUCCESS_THRESHOLD = 0.005  # 5mm


class RunTQC(Policy):
    def __init__(self, parent_node):
        super().__init__(parent_node)

        model_path = DEFAULT_MODEL_PATH
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"학습된 모델을 찾을 수 없습니다: {model_path}\n"
                "먼저 학습을 실행하세요:\n"
                "  pixi run python3 my_policy/scripts/train_tqc.py"
            )

        self.model = TQC.load(model_path, device="cuda")
        self.model.set_env(None)
        self.get_logger().info(f"TQC 모델 로드 완료: {model_path}")

    def _obs_to_sb3(self, obs_msg, desired_goal: np.ndarray) -> dict:
        """AIC Observation → SB3 Dict 형식 변환 (aic_env.py와 동일 포맷)."""
        tcp_pose = obs_msg.controller_state.tcp_pose
        tcp_vel = obs_msg.controller_state.tcp_velocity

        state = np.array([
            tcp_pose.position.x, tcp_pose.position.y, tcp_pose.position.z,
            tcp_pose.orientation.x, tcp_pose.orientation.y,
            tcp_pose.orientation.z, tcp_pose.orientation.w,
            tcp_vel.linear.x, tcp_vel.linear.y, tcp_vel.linear.z,
            tcp_vel.angular.x, tcp_vel.angular.y, tcp_vel.angular.z,
            *obs_msg.controller_state.tcp_error,
            *list(obs_msg.joint_states.position[:7]),
        ], dtype=np.float32)

        achieved_goal = np.array([
            tcp_pose.position.x,
            tcp_pose.position.y,
            tcp_pose.position.z,
        ], dtype=np.float32)

        return {
            "observation": state[np.newaxis],         # (1, 26)
            "achieved_goal": achieved_goal[np.newaxis],  # (1, 3)
            "desired_goal": desired_goal[np.newaxis],    # (1, 3)
        }

    def _action_to_motion_update(self, action: np.ndarray) -> MotionUpdate:
        """6-dim velocity → MotionUpdate 변환."""
        action = np.clip(action, -VEL_LIMIT, VEL_LIMIT)
        msg = MotionUpdate()
        msg.header = Header(
            frame_id="base_link",
            stamp=self.get_clock().now().to_msg(),
        )
        msg.velocity = Twist(
            linear=Vector3(x=float(action[0]), y=float(action[1]), z=float(action[2])),
            angular=Vector3(x=float(action[3]), y=float(action[4]), z=float(action[5])),
        )
        msg.target_stiffness = np.diag([100.0, 100.0, 100.0, 50.0, 50.0, 50.0]).flatten()
        msg.target_damping = np.diag([40.0, 40.0, 40.0, 15.0, 15.0, 15.0]).flatten()
        msg.feedforward_wrench_at_tip = Wrench(
            force=Vector3(x=0.0, y=0.0, z=0.0),
            torque=Vector3(x=0.0, y=0.0, z=0.0),
        )
        msg.wrench_feedback_gains_at_tip = [0.5, 0.5, 0.5, 0.0, 0.0, 0.0]
        msg.trajectory_generation_mode.mode = TrajectoryGenerationMode.MODE_VELOCITY
        return msg

    def _get_port_position(self, task: Task) -> np.ndarray | None:
        """TF에서 포트 위치(base_link 기준)를 가져옵니다."""
        port_frame = PORT_FRAME_TEMPLATE.format(
            target_module_name=task.target_module_name,
            port_name=task.port_name,
        )
        try:
            import rclpy
            from tf2_ros.buffer import Buffer
            tf_buffer: Buffer = self._parent_node._tf_buffer
            t = tf_buffer.lookup_transform("base_link", port_frame, rclpy.time.Time())
            pos = t.transform.translation
            return np.array([pos.x, pos.y, pos.z], dtype=np.float32)
        except Exception as e:
            self.get_logger().warn(f"포트 TF 조회 실패: {e}")
            return None

    def insert_cable(
        self,
        task: Task,
        get_observation: GetObservationCallback,
        move_robot: MoveRobotCallback,
        send_feedback: SendFeedbackCallback,
    ) -> bool:
        self.get_logger().info(f"RunTQC.insert_cable() 시작: {task.id}")

        # 포트 위치 조회 (desired_goal)
        desired_goal = None
        for _ in range(20):
            desired_goal = self._get_port_position(task)
            if desired_goal is not None:
                break
            time.sleep(0.5)

        if desired_goal is None:
            self.get_logger().error("포트 TF를 가져올 수 없습니다. ground_truth:=true 확인 필요")
            return False

        self.get_logger().info(f"목표 포트 위치: {desired_goal}")

        start_time = time.time()
        step_interval = 1.0 / CONTROL_HZ
        success = False

        while time.time() - start_time < 60.0:
            loop_start = time.time()

            obs_msg = get_observation()
            if obs_msg is None:
                time.sleep(step_interval)
                continue

            obs_dict = self._obs_to_sb3(obs_msg, desired_goal)

            # TQC 추론 (결정론적)
            action, _ = self.model.predict(obs_dict, deterministic=True)
            action = action[0]  # (1, 6) → (6,)

            motion_update = self._action_to_motion_update(action)
            move_robot(motion_update=motion_update)

            # 성공 판정
            tcp_pos = np.array([
                obs_msg.controller_state.tcp_pose.position.x,
                obs_msg.controller_state.tcp_pose.position.y,
                obs_msg.controller_state.tcp_pose.position.z,
            ])
            dist = float(np.linalg.norm(tcp_pos - desired_goal))
            send_feedback(f"포트까지 거리: {dist:.4f}m")

            if dist < SUCCESS_THRESHOLD:
                self.get_logger().info(f"삽입 성공! 거리: {dist:.4f}m")
                success = True
                break

            elapsed = time.time() - loop_start
            time.sleep(max(0, step_interval - elapsed))

        self.get_logger().info(f"RunTQC.insert_cable() 종료 (성공: {success})")
        return success
