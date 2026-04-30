"""
AIC Cable Insertion Gymnasium Environment for TQC Training.

Observation space (Dict, HER-compatible):
  observation : 26-dim robot state
                [tcp_pos(3), tcp_quat(4), tcp_linvel(3), tcp_angvel(3),
                 tcp_error(6), joint_pos(7)]
  achieved_goal : plug tip position in base_link frame (3-dim)
  desired_goal  : port position in base_link frame (3-dim)

Action space:
  6-dim Cartesian velocity [vx, vy, vz, wx, wy, wz], clipped to [-0.05, 0.05]

Image observations (optional, for ACT encoder):
  left_image, center_image, right_image : (IMG_H, IMG_W, 3) uint8
  IMG_SIZE = (84, 84) 기본값 (메모리 vs 품질 트레이드오프)

Reward (5-stage):
  Dense base   : -||achieved_goal - desired_goal||  (항상 활성, HER 호환)
  Stage 1 (+1) : 방향 정렬  — 플러그↔포트 자세 오차 < 25°
  Stage 2 (+1) : X축 정렬  — 포트 로컬 X 오차 < 10mm
  Stage 3 (+1) : Y축 정렬  — 포트 로컬 Y 오차 < 10mm
  Stage 4 (+2) : 삽입 전   — X·Y 모두 < 5mm (삽입 축 진입 준비 완료)
  Stage 5 (+5) : 삽입 성공 — 전체 거리 < 3mm

  단계 보상은 에피소드 내 최초 달성 시 1회만 지급 (누적 달성 추적).
  포트 로컬 프레임 기준으로 축별 오차를 분리하므로, 삽입 방향(Z)과
  측면(X, Y)을 독립적으로 가이드할 수 있습니다.
"""

import time
import threading
import numpy as np
import gymnasium as gym
from gymnasium import spaces

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor

from aic_model_interfaces.msg import Observation
from aic_control_interfaces.msg import MotionUpdate, TrajectoryGenerationMode
from geometry_msgs.msg import Twist, Vector3, Wrench
from std_msgs.msg import Header
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener


# ---------------------------------------------------------------------------
# 회전 유틸 (scipy 없이 numpy만 사용)
# ---------------------------------------------------------------------------

def _quat_to_rot(q: np.ndarray) -> np.ndarray:
    """쿼터니언 [x, y, z, w] → 3×3 회전 행렬."""
    x, y, z, w = q / np.linalg.norm(q)
    return np.array([
        [1 - 2*(y*y + z*z),   2*(x*y - z*w),     2*(x*z + y*w)],
        [2*(x*y + z*w),       1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w),       2*(y*z + x*w),     1 - 2*(x*x + y*y)],
    ], dtype=np.float64)


def _quat_angle_diff(q1: np.ndarray, q2: np.ndarray) -> float:
    """두 쿼터니언 사이 각도 차이 (라디안)."""
    q1 = q1 / np.linalg.norm(q1)
    q2 = q2 / np.linalg.norm(q2)
    dot = float(np.clip(np.abs(np.dot(q1, q2)), 0.0, 1.0))
    return 2.0 * np.arccos(dot)


def _to_local_frame(vec_world: np.ndarray, frame_quat: np.ndarray) -> np.ndarray:
    """world 벡터를 frame_quat 로컬 프레임으로 변환 (R^T * v)."""
    R = _quat_to_rot(frame_quat)
    return R.T @ vec_world


# ---------------------------------------------------------------------------
# ROS2 통신 노드
# ---------------------------------------------------------------------------

class AICEnvNode(Node):
    """시뮬레이터와의 ROS2 통신을 담당하는 노드."""

    def __init__(self):
        super().__init__("aic_env_node")
        self._obs_lock = threading.Lock()
        self._latest_obs: Observation | None = None

        self._obs_sub = self.create_subscription(
            Observation, "observations", self._obs_callback, 10
        )
        self._motion_pub = self.create_publisher(
            MotionUpdate, "/aic_controller/pose_commands", 2
        )
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

    def _obs_callback(self, msg: Observation):
        with self._obs_lock:
            self._latest_obs = msg

    def get_observation(self) -> Observation | None:
        with self._obs_lock:
            return self._latest_obs

    def send_velocity(self, action: np.ndarray, frame_id: str = "base_link"):
        """6-dim velocity action → MotionUpdate 발행."""
        msg = MotionUpdate()
        msg.header = Header(
            frame_id=frame_id,
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
        self._motion_pub.publish(msg)

    def get_tf_pos(self, target_frame: str, source_frame: str = "base_link") -> np.ndarray | None:
        """위치만 반환 (3-dim)."""
        try:
            t = self._tf_buffer.lookup_transform(source_frame, target_frame, rclpy.time.Time())
            tr = t.transform.translation
            return np.array([tr.x, tr.y, tr.z], dtype=np.float64)
        except Exception:
            return None

    def get_tf_pose(self, target_frame: str, source_frame: str = "base_link"):
        """위치(3) + 쿼터니언(4, [x,y,z,w]) 반환. 실패 시 (None, None)."""
        try:
            t = self._tf_buffer.lookup_transform(source_frame, target_frame, rclpy.time.Time())
            tr = t.transform.translation
            ro = t.transform.rotation
            pos = np.array([tr.x, tr.y, tr.z], dtype=np.float64)
            quat = np.array([ro.x, ro.y, ro.z, ro.w], dtype=np.float64)
            return pos, quat
        except Exception:
            return None, None


# ---------------------------------------------------------------------------
# Gymnasium 환경
# ---------------------------------------------------------------------------

class AICEnv(gym.Env):
    """
    AIC 케이블 삽입 학습용 Gymnasium 환경 (TQC + HER).

    실행 전 MuJoCo 시뮬레이터가 필요합니다:
      ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true
    """

    metadata = {"render_modes": []}

    # TF 프레임 이름 (CLAUDE.md 규칙)
    PLUG_FRAME = "cable_0/sfp_tip_link"
    PORT_FRAME = "task_board/nic_card_mount_0/sfp_port_0_link"

    # 단계 보상 설정
    # 포트 로컬 프레임 기준 (Z = 삽입 축, X·Y = 측면)
    STAGE_REWARDS = {
        "orientation": 1.0,   # Stage 1: 방향 정렬
        "x_align":     1.0,   # Stage 2: X 측면 정렬
        "y_align":     1.0,   # Stage 3: Y 측면 정렬
        "pre_insert":  2.0,   # Stage 4: 삽입 전 준비 (X·Y 세밀 정렬)
        "success":     5.0,   # Stage 5: 삽입 성공
    }

    ORIENT_THRESH     = np.radians(25)  # Stage 1: 25°
    LATERAL_COARSE    = 0.010           # Stage 2·3: 10mm
    LATERAL_FINE      = 0.005           # Stage 4: 5mm
    SUCCESS_THRESH    = 0.003           # Stage 5: 3mm

    MAX_STEPS = 500
    VEL_LIMIT = 0.05

    # 이미지 크기: (H, W). 메모리 vs 품질 트레이드오프
    # 84×84 uint8: ~21KB/cam, 3cam×100K step buffer ≈ 6.3GB
    # 160×120 uint8: ~58KB/cam, 3cam×100K step buffer ≈ 17GB
    IMG_SIZE: tuple[int, int] = (84, 84)

    def __init__(self, use_images: bool = True):
        """
        Args:
            use_images: True면 카메라 이미지를 관측에 포함 (ACTFeaturesExtractor 필요).
                        False면 상태 벡터만 사용 (기본 MLP TQC).
        """
        super().__init__()
        self.use_images = use_images

        # 관측 공간 (HER 호환 Dict)
        obs_dict = {
            "observation":   spaces.Box(-np.inf, np.inf, (26,), np.float32),
            "achieved_goal": spaces.Box(-np.inf, np.inf, (3,),  np.float32),
            "desired_goal":  spaces.Box(-np.inf, np.inf, (3,),  np.float32),
        }
        if use_images:
            H, W = self.IMG_SIZE
            # (C, H, W) 형식 — SB3의 VecTransposeImage 자동 변환 방지
            img_space = spaces.Box(0, 255, (3, H, W), dtype=np.uint8)
            obs_dict["left_image"]   = img_space
            obs_dict["center_image"] = img_space
            obs_dict["right_image"]  = img_space
        self.observation_space = spaces.Dict(obs_dict)

        # 행동 공간: 6-dim Cartesian 속도
        self.action_space = spaces.Box(
            low=-self.VEL_LIMIT, high=self.VEL_LIMIT, shape=(6,), dtype=np.float32
        )

        # ROS2 초기화
        if not rclpy.ok():
            rclpy.init()
        self._node = AICEnvNode()
        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()

        # 에피소드 상태
        self._step_count = 0
        self._port_pos: np.ndarray | None = None    # reset 시 캐시
        self._port_quat: np.ndarray | None = None   # reset 시 캐시
        self._achieved_stages: set[str] = set()

        self._wait_for_obs(timeout=10.0)

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _wait_for_obs(self, timeout=10.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._node.get_observation() is not None:
                return
            time.sleep(0.1)
        raise RuntimeError(
            "관측값을 받지 못했습니다. 시뮬레이터가 실행 중인지 확인하세요."
        )

    @staticmethod
    def _ros_image_to_uint8(ros_img, size: tuple[int, int]) -> np.ndarray:
        """ROS Image → (3, H, W) uint8, 리사이즈 포함. (C,H,W) 형식."""
        import cv2
        arr = np.frombuffer(ros_img.data, dtype=np.uint8).reshape(ros_img.height, ros_img.width, 3)
        if arr.shape[:2] != size:
            arr = cv2.resize(arr, (size[1], size[0]), interpolation=cv2.INTER_AREA)
        return arr.transpose(2, 0, 1)  # (H, W, 3) → (3, H, W)

    def _build_obs_dict(self) -> dict:
        obs_msg = self._node.get_observation()
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

        plug_pos = self._node.get_tf_pos(self.PLUG_FRAME)
        achieved_goal = plug_pos.astype(np.float32) if plug_pos is not None else np.zeros(3, np.float32)
        desired_goal = self._port_pos.astype(np.float32) if self._port_pos is not None else np.zeros(3, np.float32)

        obs = {
            "observation":   state,
            "achieved_goal": achieved_goal,
            "desired_goal":  desired_goal,
        }

        if self.use_images:
            obs["left_image"]   = self._ros_image_to_uint8(obs_msg.left_image,   self.IMG_SIZE)
            obs["center_image"] = self._ros_image_to_uint8(obs_msg.center_image, self.IMG_SIZE)
            obs["right_image"]  = self._ros_image_to_uint8(obs_msg.right_image,  self.IMG_SIZE)

        return obs

    def _compute_staged_reward(
        self,
        plug_pos: np.ndarray,
        plug_quat: np.ndarray | None,
    ) -> float:
        """
        5단계 보상 계산. 각 단계는 에피소드 내 최초 달성 시 1회만 지급.

        포트 로컬 프레임으로 변환해 축별 오차를 분리합니다:
          local[0] = X (측면 좌우)
          local[1] = Y (측면 상하)
          local[2] = Z (삽입 깊이 축)
        """
        if self._port_pos is None or self._port_quat is None:
            return 0.0

        bonus = 0.0

        # --- Stage 1: 방향 정렬 ---
        if "orientation" not in self._achieved_stages and plug_quat is not None:
            angle_err = _quat_angle_diff(plug_quat, self._port_quat)
            if angle_err < self.ORIENT_THRESH:
                self._achieved_stages.add("orientation")
                bonus += self.STAGE_REWARDS["orientation"]

        # 포트 로컬 프레임 기준 오차 벡터
        pos_err_world = plug_pos - self._port_pos
        err_local = _to_local_frame(pos_err_world, self._port_quat)  # [ex, ey, ez]

        # --- Stage 2: X축 측면 정렬 ---
        if "x_align" not in self._achieved_stages:
            if abs(err_local[0]) < self.LATERAL_COARSE:
                self._achieved_stages.add("x_align")
                bonus += self.STAGE_REWARDS["x_align"]

        # --- Stage 3: Y축 측면 정렬 ---
        if "y_align" not in self._achieved_stages:
            if abs(err_local[1]) < self.LATERAL_COARSE:
                self._achieved_stages.add("y_align")
                bonus += self.STAGE_REWARDS["y_align"]

        # --- Stage 4: 삽입 전 준비 (X·Y 세밀 정렬, Z 접근) ---
        # X·Y가 이미 coarse 달성 후, fine 수준까지 좁혀졌을 때
        if "pre_insert" not in self._achieved_stages:
            xy_fine = abs(err_local[0]) < self.LATERAL_FINE and abs(err_local[1]) < self.LATERAL_FINE
            if xy_fine:
                self._achieved_stages.add("pre_insert")
                bonus += self.STAGE_REWARDS["pre_insert"]

        # --- Stage 5: 삽입 성공 ---
        if "success" not in self._achieved_stages:
            total_dist = float(np.linalg.norm(pos_err_world))
            if total_dist < self.SUCCESS_THRESH:
                self._achieved_stages.add("success")
                bonus += self.STAGE_REWARDS["success"]

        return bonus

    # ------------------------------------------------------------------
    # HER 호환 compute_reward (위치 기반 dense, 항상 활성)
    # ------------------------------------------------------------------

    def compute_reward(
        self,
        achieved_goal: np.ndarray,
        desired_goal: np.ndarray,
        info: dict,
    ) -> np.ndarray:
        """HER가 가상 목표로 보상을 재계산할 때 사용. 단계 보상 제외."""
        dist = np.linalg.norm(achieved_goal - desired_goal, axis=-1)
        return (-dist).astype(np.float32)

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._step_count = 0
        self._achieved_stages = set()

        # 포트 위치·자세를 에피소드 시작 시 한 번 캐시
        pos, quat = self._node.get_tf_pose(self.PORT_FRAME)
        self._port_pos = pos
        self._port_quat = quat

        obs = self._build_obs_dict()
        return obs, {}

    def step(self, action: np.ndarray):
        action = np.clip(action, -self.VEL_LIMIT, self.VEL_LIMIT)
        self._node.send_velocity(action)
        time.sleep(0.05)  # 20Hz 제어 주기

        self._step_count += 1
        obs = self._build_obs_dict()

        # 플러그 위치·자세 조회 (단계 보상 계산용)
        plug_pos, plug_quat = self._node.get_tf_pose(self.PLUG_FRAME)
        if plug_pos is None:
            plug_pos = obs["achieved_goal"].astype(np.float64)
            plug_quat = None

        # 보상 = dense base + 단계 보너스
        dist = float(np.linalg.norm(obs["achieved_goal"] - obs["desired_goal"]))
        dense_reward = -dist
        stage_bonus = self._compute_staged_reward(plug_pos, plug_quat)
        reward = dense_reward + stage_bonus

        terminated = "success" in self._achieved_stages
        truncated = self._step_count >= self.MAX_STEPS

        info = {
            "distance":       dist,
            "is_success":     terminated,
            "stages_achieved": list(self._achieved_stages),
            "stage_bonus":    stage_bonus,
        }
        return obs, reward, terminated, truncated, info

    def close(self):
        self._executor.shutdown()
        rclpy.shutdown()
