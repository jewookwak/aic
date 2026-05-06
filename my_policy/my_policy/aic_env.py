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

import os
import time
import threading
import itertools
import numpy as np
import gymnasium as gym
from gymnasium import spaces

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor

# 프로세스 내 노드 이름 충돌 방지용 카운터
_node_id_counter = itertools.count()

from aic_model_interfaces.msg import Observation
from aic_control_interfaces.msg import MotionUpdate, JointMotionUpdate, TrajectoryGenerationMode, TargetMode
from aic_control_interfaces.srv import ChangeTargetMode
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

HOME_JOINTS = [-0.1597, -1.3542, -1.6648, -1.6933, 1.5710, 1.4110]  # rad (CLAUDE.md)


class AICEnvNode(Node):
    """시뮬레이터와의 ROS2 통신을 담당하는 노드."""

    def __init__(self):
        node_id = next(_node_id_counter)
        super().__init__(f"aic_env_node_{os.getpid()}_{node_id}")
        self._obs_lock = threading.Lock()
        self._latest_obs: Observation | None = None

        self._obs_sub = self.create_subscription(
            Observation, "observations", self._obs_callback, 10
        )
        self._motion_pub = self.create_publisher(
            MotionUpdate, "/aic_controller/pose_commands", 2
        )
        self._joint_pub = self.create_publisher(
            JointMotionUpdate, "/aic_controller/joint_commands", 2
        )
        self._change_target_mode_client = self.create_client(
            ChangeTargetMode, "/aic_controller/change_target_mode"
        )
        self._current_target_mode = TargetMode.MODE_UNSPECIFIED
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

    def _obs_callback(self, msg: Observation):
        with self._obs_lock:
            self._latest_obs = msg

    def get_observation(self) -> Observation | None:
        with self._obs_lock:
            return self._latest_obs

    def wait_for_service(self, timeout: float = 10.0) -> bool:
        """change_target_mode 서비스가 준비될 때까지 대기. 준비되면 True 반환."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._change_target_mode_client.service_is_ready():
                print("[AICEnvNode] change_target_mode 서비스 준비 완료")
                return True
            time.sleep(0.2)
        print(f"[AICEnvNode] WARNING: change_target_mode 서비스 {timeout:.0f}초 내 미응답 — "
              "joint 명령이 무시될 수 있습니다")
        return False

    def _set_target_mode(self, mode: int):
        """Switch aic_controller target mode (MODE_CARTESIAN=1, MODE_JOINT=2)."""
        if self._current_target_mode == mode:
            return
        if not self._change_target_mode_client.service_is_ready():
            print(f"[AICEnvNode] WARNING: change_target_mode 서비스 미준비 — "
                  f"mode {mode} 전환 스킵 (현재: {self._current_target_mode})")
            return
        req = ChangeTargetMode.Request()
        req.target_mode.mode = mode
        future = self._change_target_mode_client.call_async(req)
        # Block until the executor (spin thread) resolves the future
        deadline = time.time() + 5.0
        while not future.done() and time.time() < deadline:
            time.sleep(0.02)
        if future.done() and future.result() is not None and future.result().success:
            self._current_target_mode = mode
        else:
            print(f"[AICEnvNode] ERROR: mode {mode} 전환 실패 "
                  f"(done={future.done()}, result={future.result() if future.done() else 'N/A'})")

    def send_velocity(self, action: np.ndarray, frame_id: str = "base_link"):
        """6-dim velocity action → MotionUpdate 발행."""
        self._set_target_mode(TargetMode.MODE_CARTESIAN)
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

    def send_home_position(self, duration: float = 3.0):
        """관절 공간에서 home position으로 복귀 명령을 duration 초 동안 전송."""
        self._set_target_mode(TargetMode.MODE_JOINT)
        msg = JointMotionUpdate(
            target_stiffness=[200.0, 200.0, 200.0, 100.0, 100.0, 100.0],
            target_damping=[40.0, 40.0, 40.0, 15.0, 15.0, 15.0],
            trajectory_generation_mode=TrajectoryGenerationMode(
                mode=TrajectoryGenerationMode.MODE_POSITION
            ),
        )
        # controller joint order: shoulder_pan(0) shoulder_lift(1) elbow(2)
        #                         wrist_1(3)     wrist_2(4)        wrist_3(5)
        msg.target_state.positions = HOME_JOINTS
        steps = max(1, int(duration / 0.1))
        for _ in range(steps):
            self._joint_pub.publish(msg)
            time.sleep(0.1)
        # Switch back to Cartesian mode for velocity control
        self._set_target_mode(TargetMode.MODE_CARTESIAN)

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
    VEL_LIMIT = 0.05   # 선속도 한계 [m/s]
    # angular.z in base_link frame = 수직축 기준 수평 스윕.
    # ±0.05 rad/s로 500 스텝 탐색 시 최대 누적 71° 회전 → 그리퍼 방향 반전.
    # 1/5로 줄이면 최대 14° 이내로 유지되어 삽입 방향 유지 가능.
    ANG_LIMIT  = 0.01  # 각속도 한계 [rad/s]

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

        # 행동 공간: [vx, vy, vz, wx, wy, wz]
        # 선속도와 각속도를 분리해서 한계 설정 (base_link 프레임 기준)
        self.action_space = spaces.Box(
            low= np.array([-self.VEL_LIMIT]*3 + [-self.ANG_LIMIT]*3, dtype=np.float32),
            high=np.array([ self.VEL_LIMIT]*3 + [ self.ANG_LIMIT]*3, dtype=np.float32),
        )

        # ROS2 초기화
        if not rclpy.ok():
            rclpy.init()
        self._node = AICEnvNode()
        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()
        # Zenoh peer-to-peer 발견에 약간의 시간을 허용
        time.sleep(2.0)

        # 에피소드 상태
        self._step_count = 0
        self._port_pos: np.ndarray | None = None    # reset 시 캐시
        self._port_quat: np.ndarray | None = None   # reset 시 캐시
        self._achieved_stages: set[str] = set()
        self._needs_home_reset: bool = False        # 충돌/이탈 시 True → reset()에서 home 복귀
        self._last_plug_pos: np.ndarray | None = None  # TF 실패 시 fallback용
        self._floor_z_threshold: float | None = None   # home reset 시 home_tcp_z - 0.20 으로 설정
        self._init_logged: bool = False                 # 초기화 진단 출력 여부

        # change_target_mode 서비스 대기 (joint 명령 전달에 필수)
        self._node.wait_for_service(timeout=10.0)

        self._wait_for_obs(timeout=30.0)

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _wait_for_obs(self, timeout=30.0):
        import os as _os
        deadline = time.time() + timeout
        print(
            f"[AICEnv] 관측 대기 중... (RMW={_os.environ.get('RMW_IMPLEMENTATION', 'unset')}, "
            f"timeout={timeout:.0f}s)"
        )
        print("[AICEnv] 시뮬레이터가 실행 중인지 확인하세요 (별도 터미널):")
        print("  distrobox$ source ~/ws_aic/install/setup.bash")
        print("  distrobox$ ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true")

        last_pub_warn = 0.0
        while time.time() < deadline:
            if self._node.get_observation() is not None:
                print("[AICEnv] 관측값 수신 완료!")
                return

            # 5초마다 publisher 수 확인해 시뮬레이터 미실행을 조기 감지
            now = time.time()
            if now - last_pub_warn >= 5.0:
                n_pub = self._node._obs_sub.get_publisher_count()
                elapsed = timeout - (deadline - now)
                if n_pub == 0:
                    print(f"[AICEnv] {elapsed:.0f}s 경과 — /observations publisher 없음. "
                          "MuJoCo가 실행 중인지 확인하세요.")
                else:
                    print(f"[AICEnv] {elapsed:.0f}s 경과 — publisher {n_pub}개 발견, 메시지 대기 중...")
                last_pub_warn = now

            time.sleep(0.2)

        raise RuntimeError(
            f"관측값을 받지 못했습니다 ({timeout:.0f}s 경과).\n"
            "터미널 1(distrobox)에서 MuJoCo를 먼저 실행한 뒤 터미널 2(pixi)에서 학습을 시작하세요:\n"
            "  [터미널 1] source ~/ws_aic/install/setup.bash\n"
            "  [터미널 1] ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true\n"
            "  [터미널 2] cd ~/ws_aic/src/aic && pixi run python3 my_policy/scripts/train_tqc.py --mode state"
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
        if plug_pos is not None:
            self._last_plug_pos = plug_pos
        # TF 실패 시 zeros 대신 마지막 알려진 위치 사용 (zeros면 HER 학습 신호가 깨짐)
        achieved_goal = (self._last_plug_pos.astype(np.float32)
                         if self._last_plug_pos is not None
                         else np.zeros(3, np.float32))
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

    def _coarse_approach_to_port(self, timeout: float = 20.0):
        """
        홈 리셋 후 플러그를 포트 근처로 P-컨트롤러로 이동.
        홈 위치는 포트에서 ~0.87m 떨어져 있으므로, RL 탐색 전 먼저 근접.

        제어: send_velocity(base_link) → TCP 이동 → 플러그가 TCP와 함께 이동.
        목표: port 위치 직접 (velocity mode workspace 한계로 +0.2m 목표는 도달 불가).
        RL 에이전트가 나머지 삽입 방향 정렬을 담당.
        """
        if self._port_pos is None:
            return
        target = self._port_pos.copy()
        # velocity mode에서 task board x,y 위치에서 팔이 port_z+0.2m 도달 불가.
        # port 위치 직접을 목표로 삼아 x,y 정렬 후 RL이 z 삽입 담당.
        target[2] += 0.05  # 포트 5cm 위 (도달 가능한 높이)

        K = 0.5          # P 게인 [1/s]
        v_max = 0.05     # 최대 접근 속도 [m/s] (RL 제한과 동일)
        dt = 0.05
        max_steps = max(1, int(timeout / dt))

        print(f"[AICEnv] 포트 근처로 이동 중... target={target}")
        for i in range(max_steps):
            plug_pos = self._node.get_tf_pos(self.PLUG_FRAME)
            if plug_pos is None:
                time.sleep(dt)
                continue
            error = target - plug_pos
            dist = float(np.linalg.norm(error))
            if dist < 0.10:
                print(f"[AICEnv] 접근 완료 (dist={dist:.3f}m, steps={i})")
                break
            vel = np.clip(error * K, -v_max, v_max)
            action = np.concatenate([vel.astype(np.float32), np.zeros(3, np.float32)])
            self._node.send_velocity(action)
            time.sleep(dt)
        self._node.send_velocity(np.zeros(6, dtype=np.float32))
        time.sleep(0.1)

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

        # 정지 명령으로 이전 에피소드 속도 차단
        self._node.send_velocity(np.zeros(6, dtype=np.float32))

        # 포트 위치를 먼저 캐시 (coarse approach에 필요)
        pos, quat = self._node.get_tf_pose(self.PORT_FRAME)
        self._port_pos = pos
        self._port_quat = quat

        # 첫 번째 에피소드 또는 충돌 후: home 복귀 + 포트 근처로 coarse approach.
        # home position은 포트에서 ~0.87m 떨어져 있으므로 RL 탐색 전 먼저 근접.
        if self._needs_home_reset or self._floor_z_threshold is None:
            print("[AICEnv] Home reset 실행 중...")
            self._node.send_home_position(duration=3.0)
            self._needs_home_reset = False

            # floor threshold는 반드시 home position에서 측정 (coarse approach 전).
            # task board 표면 ≈ home_tcp_z - 0.20. coarse approach 이후 TCP 위치로
            # 측정하면 threshold가 올라가 삽입 중에 floor hit이 잘못 발생함.
            if self._floor_z_threshold is None:
                home_obs = self._build_obs_dict()
                home_tcp_z = float(home_obs["observation"][2])
                self._floor_z_threshold = home_tcp_z - 0.20
                print(f"[AICEnv] floor Z threshold = {self._floor_z_threshold:.3f}m "
                      f"(home Z={home_tcp_z:.3f}m)")

            # 포트 근처로 P-컨트롤러 접근 (홈→포트 ~0.87m 이동)
            self._coarse_approach_to_port(timeout=20.0)
            # 접근 후 포트 pos 갱신
            pos, quat = self._node.get_tf_pose(self.PORT_FRAME)
            if pos is not None:
                self._port_pos = pos
                self._port_quat = quat
        else:
            time.sleep(0.1)

        obs = self._build_obs_dict()

        if not self._init_logged and self._floor_z_threshold is not None:
            self._init_logged = True
            tcp_pos  = obs["observation"][:3]
            joints   = obs["observation"][19:26]  # shoulder_pan ~ gripper
            plug_dist = float(np.linalg.norm(obs['achieved_goal'] - obs['desired_goal']))
            print(f"[AICEnv] === 초기화 완료 ===")
            print(f"  tcp_pos  : {tcp_pos}")
            print(f"  joints(pan~gripper): {joints}")
            print(f"  port_pos : {self._port_pos}")
            print(f"  achieved : {obs['achieved_goal']}  desired: {obs['desired_goal']}")
            print(f"  dist_to_port : {plug_dist:.3f}m  (coarse approach 후)")

        return obs, {}

    def step(self, action: np.ndarray):
        lin = np.clip(action[:3], -self.VEL_LIMIT, self.VEL_LIMIT)
        ang = np.clip(action[3:], -self.ANG_LIMIT, self.ANG_LIMIT)
        action = np.concatenate([lin, ang])
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

        # 바닥 충돌 감지 → 다음 reset() 때 home 복귀
        tcp_z = float(obs["observation"][2])
        floor_hit = (
            self._floor_z_threshold is not None
            and tcp_z < self._floor_z_threshold
        )
        if floor_hit:
            self._needs_home_reset = True
            # HER은 compute_reward()로 리라벨하므로 여기 패널티는 실제 경험에만 적용됨.
            # "바닥 = 목표" HER 수렴을 막으려면 실제 경험에 충분히 큰 음의 신호가 필요.
            reward -= 10.0
            print(f"[AICEnv] floor hit @ step {self._step_count}: "
                  f"tcp_z={tcp_z:.3f} < threshold={self._floor_z_threshold:.3f}, "
                  f"action_vz={action[2]:.4f}")

        truncated = self._step_count >= self.MAX_STEPS or floor_hit
        if truncated and self._step_count >= self.MAX_STEPS:
            print(f"[AICEnv] episode truncated @ {self.MAX_STEPS} steps (dist={dist:.3f}m)")

        info = {
            "distance":    dist,
            "is_success":  terminated,
            "stages_achieved": list(self._achieved_stages),
            "stage_bonus": stage_bonus,
            "floor_hit":   floor_hit,
        }
        return obs, reward, terminated, truncated, info

    def close(self):
        self._executor.shutdown()
        rclpy.shutdown()
