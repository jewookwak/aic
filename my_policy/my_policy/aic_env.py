"""
AIC Cable Insertion Gymnasium Environment for TQC Training.

Observation space (Dict, HER-compatible):
  observation : 26-dim robot state
                [tcp_pos(3), tcp_quat(4), tcp_linvel(3), tcp_angvel(3),
                 tcp_error(6), joint_pos(7)]
  achieved_goal : plug tip position in base_link frame (3-dim)
  desired_goal  : port position in base_link frame (3-dim)

Action space:
  6-dim Cartesian velocity [vx, vy, vz, wx, wy, wz], clipped to [-0.1, 0.1]

Reward:
  Dense: -||achieved_goal - desired_goal||
  Sparse bonus: +10 if distance < success_threshold
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
from aic_control_interfaces.srv import ChangeTargetMode
from geometry_msgs.msg import Twist, Vector3, Wrench
from std_msgs.msg import Header
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener


class AICEnvNode(Node):
    """ROS2 node that handles communication with the simulator."""

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
        """Publish 6-dim velocity action as MotionUpdate."""
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

    def get_tf(self, target_frame: str, source_frame: str = "base_link"):
        """Look up transform. Returns (position np.array, None) or (None, None) on fail."""
        try:
            t = self._tf_buffer.lookup_transform(
                source_frame, target_frame, rclpy.time.Time()
            )
            pos = t.transform.translation
            return np.array([pos.x, pos.y, pos.z])
        except Exception:
            return None


class AICEnv(gym.Env):
    """
    Gymnasium environment for AIC cable insertion training with TQC.

    Requires the MuJoCo simulation to be running:
      ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true
    """

    metadata = {"render_modes": []}

    # TF frame names (matches CLAUDE.md conventions)
    PLUG_FRAME = "cable_0/sfp_tip_link"
    PORT_FRAME = "task_board/nic_card_mount_0/sfp_port_0_link"

    SUCCESS_THRESHOLD = 0.005  # 5mm
    MAX_STEPS = 500
    VEL_LIMIT = 0.05           # m/s and rad/s

    def __init__(self):
        super().__init__()

        # --- Observation space (HER-compatible Dict) ---
        obs_dim = 26
        goal_dim = 3
        self.observation_space = spaces.Dict(
            {
                "observation": spaces.Box(-np.inf, np.inf, (obs_dim,), np.float32),
                "achieved_goal": spaces.Box(-np.inf, np.inf, (goal_dim,), np.float32),
                "desired_goal": spaces.Box(-np.inf, np.inf, (goal_dim,), np.float32),
            }
        )

        # --- Action space: 6-dim Cartesian velocity ---
        self.action_space = spaces.Box(
            low=-self.VEL_LIMIT,
            high=self.VEL_LIMIT,
            shape=(6,),
            dtype=np.float32,
        )

        # --- ROS2 setup ---
        if not rclpy.ok():
            rclpy.init()
        self._node = AICEnvNode()
        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()

        self._step_count = 0
        self._desired_goal = None

        # Wait for first observation
        self._wait_for_obs(timeout=10.0)

    def _wait_for_obs(self, timeout=10.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._node.get_observation() is not None:
                return
            time.sleep(0.1)
        raise RuntimeError("No observation received within timeout. Is the simulation running?")

    def _get_obs_dict(self) -> dict:
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

        plug_pos = self._node.get_tf(self.PLUG_FRAME)
        port_pos = self._node.get_tf(self.PORT_FRAME)

        achieved_goal = plug_pos if plug_pos is not None else np.zeros(3, np.float32)
        desired_goal = port_pos if port_pos is not None else np.zeros(3, np.float32)

        if self._desired_goal is not None:
            desired_goal = self._desired_goal

        return {
            "observation": state,
            "achieved_goal": achieved_goal.astype(np.float32),
            "desired_goal": desired_goal.astype(np.float32),
        }

    def compute_reward(self, achieved_goal, desired_goal, info):
        dist = np.linalg.norm(achieved_goal - desired_goal, axis=-1)
        reward = -dist
        reward = np.where(dist < self.SUCCESS_THRESHOLD, reward + 10.0, reward)
        return reward.astype(np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._step_count = 0

        # Cache port position at episode start as desired goal
        port_pos = self._node.get_tf(self.PORT_FRAME)
        self._desired_goal = port_pos.astype(np.float32) if port_pos is not None else None

        obs = self._get_obs_dict()
        return obs, {}

    def step(self, action: np.ndarray):
        action = np.clip(action, -self.VEL_LIMIT, self.VEL_LIMIT)
        self._node.send_velocity(action)
        time.sleep(0.05)  # ~20Hz control loop (adjust to match sim rate)

        self._step_count += 1
        obs = self._get_obs_dict()

        reward = float(self.compute_reward(obs["achieved_goal"], obs["desired_goal"], {}))
        dist = np.linalg.norm(obs["achieved_goal"] - obs["desired_goal"])
        terminated = bool(dist < self.SUCCESS_THRESHOLD)
        truncated = self._step_count >= self.MAX_STEPS

        info = {"distance": dist, "is_success": terminated}
        return obs, reward, terminated, truncated, info

    def close(self):
        self._executor.shutdown()
        rclpy.shutdown()
