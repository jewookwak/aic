# aic_controller

[aic_controller](../aic_controller/) 패키지는 ROS 2용 컨트롤러입니다. 제어 정책이나 플래너로부터 약 10~30Hz로 목표 명령(관절 또는 카르테시안)을 받아 약 500Hz로 로봇 하드웨어에 전달합니다. 목표값은 안전 검사와 스무딩을 거친 후 임피던스 제어가 적용됩니다.

## 아키텍처

아키텍처의 고수준 개요는 다음 다이어그램에 나와 있습니다:
<img width="1889" height="437" alt="image" src="../../media/aic_controller.png" />

### 제어 파이프라인

1. **명령 클램핑**: 입력 목표값이 안전 범위 내에 머물도록 클램핑됩니다.
    - 관절 목표는 로봇의 URDF/설명에 정의된 한계로 클램핑됩니다.
    - 카르테시안 목표는 사용자가 지정한 파라미터로 클램핑됩니다.

2. **명령 보간**: 클램핑된 목표는 느린 정책 명령을 부드러운 고속 설정점으로 전환하기 위해 스무딩됩니다.

3. **임피던스 제어**: 스무딩된 설정점은 [CartesianImpedanceAction](../aic_controller/include/aic_controller/actions/cartesian_impedance_action.hpp) 또는 [JointImpedanceAction](../aic_controller/include/aic_controller/actions/joint_impedance_action.hpp)에 의해 처리되어 필요한 관절 토크를 계산합니다.

4. **중력 보상**: [GravityCompensationAction](../aic_controller/include/aic_controller/actions/gravity_compensation_action.hpp)을 사용하여 로봇 링크의 중력을 상쇄하는 추가 토크가 계산됩니다.

5. **명령 실행**: 임피던스 토크와 중력 보상 토크를 더하여 로봇 관절로 전송됩니다.

> [!NOTE]
> `aic_controller`는 타임아웃 동안 줄어들지 않는 큰 오차가 있으면 컨트롤러 목표를 리셋합니다([aic_ros2_controllers.yaml](../aic_bringup/config/aic_ros2_controllers.yaml)의 `tracking_error`에서 설정 가능). 이는 일반적인 원격 조작 문제를 완화합니다: 로봇이 충돌 중인데 사용자가 계속 명령을 전송하면 추적 오차가 누적됩니다. 리셋이 없으면 로봇이 충돌에서 벗어날 때 누적된 오차를 급격하게 실행합니다.

### 카르테시안 임피던스 제어

카르테시안 목표는 엔드 이펙터의 현재 위치와 목표 위치의 차이를 기반으로 관절 토크를 계산하는 `CartesianImpedanceAction`이 처리합니다.

$$
\tau = \mathbf{J}^T \Big[ \mathbf{K}_p (\mathbf{x}_{des} - \mathbf{x}) + \mathbf{K}_d (\dot{\mathbf{x}}_{des} - \dot{\mathbf{x}}) + \mathbf{W}_f \Big] + \tau_{null}
$$

**변수 설명**:
- $\tau \in \mathbb{R}^n$: 계산된 관절 토크.
- $\mathbf{J} \in \mathbb{R}^{6 \times n}$: 로봇 팔의 야코비안 행렬.
- $\mathbf{K}_p, \mathbf{K}_d \in \mathbb{R}^{6 \times 6}$: 강성 및 감쇠 행렬.
- $\mathbf{x}_{des}, \mathbf{x} \in \mathbb{R}^6$: 목표 및 현재 엔드 이펙터 포즈.
- $\mathbf{W}_f \in \mathbb{R}^6$: 추가 외부 힘/토크.
- $\tau_{null} \in \mathbb{R}^n$: 관절 한계 회피 등 보조 태스크를 위한 추가 토크.

### 관절 임피던스 제어

관절 목표는 목표와 현재 관절 위치의 차이를 기반으로 관절 토크를 계산하는 `JointImpedanceAction`이 처리합니다.

$$
\tau = \mathbf{K}_p (\mathbf{q}_{des} - \mathbf{q}) + \mathbf{K}_d (\dot{\mathbf{q}}_{des} - \dot{\mathbf{q}}) + \tau_f
$$

**변수 설명**:
- $\tau \in \mathbb{R}^n$: 계산된 관절 토크.
- $\mathbf{K}_p, \mathbf{K}_d \in \mathbb{R}^n$: 각 관절의 강성 및 감쇠.
- $\mathbf{q}_{des}, \mathbf{q} \in \mathbb{R}^n$: 목표 및 현재 관절 위치.
- $\dot{\mathbf{q}}_{des}, \dot{\mathbf{q}} \in \mathbb{R}^n$: 목표 및 현재 관절 속도.
- $\tau_f \in \mathbb{R}^n$: 추가 관절 토크.


### ROS 2 인터페이스

#### 명령 인터페이스

`aic_controller`는 두 개의 ROS 2 토픽으로 명령을 수락합니다. 자세한 메시지 정의는 [컨트롤러 목표 파라미터](#컨트롤러-목표-파라미터)를 참조하세요.

- **카르테시안 목표** ([`MotionUpdate`](../aic_interfaces/aic_control_interfaces/msg/MotionUpdate.msg)): `/aic_controller/pose_commands`
- **관절 목표** ([`JointMotionUpdate`](../aic_interfaces/aic_control_interfaces/msg/JointMotionUpdate.msg)): `/aic_controller/joint_commands`

#### 관절 및 카르테시안 목표 모드 전환

관절 제어와 카르테시안 제어를 전환하려면 `/aic_controller/change_target_mode`로 ROS 2 서비스 요청을 보내세요. 컨트롤러는 기본적으로 **카르테시안** 모드로 시작합니다.

ROS 2 CLI로 컨트롤러의 목표 모드를 전환하는 서비스 호출:
```bash
# 카르테시안 목표 모드로 전환하는 서비스 요청
ros2 service call /aic_controller/change_target_mode aic_control_interfaces/srv/ChangeTargetMode "{target_mode: {mode: 1}}"

# 관절 목표 모드로 전환하는 서비스 요청
ros2 service call /aic_controller/change_target_mode aic_control_interfaces/srv/ChangeTargetMode "{target_mode: {mode: 2}}"
```

> **참고:** 컨트롤러는 한 번에 하나의 모드만 사용할 수 있습니다. 예를 들어 `Cartesian` 모드인 경우 `/aic_controller/pose_commands`만 수신하고 `/aic_controller/joint_commands`의 메시지는 무시합니다. `/aic_controller/change_target_mode` 서비스를 사용하여 모드를 전환해야 해당 타입의 명령을 수락합니다.

#### 상태 피드백

컨트롤러는 `/aic_controller/controller_state` ([`ControllerState`](../aic_interfaces/aic_control_interfaces/msg/ControllerState.msg))에 실시간 데이터를 발행합니다. 이 메시지에는:
- 현재 TCP 포즈 및 속도
- 목표 TCP 포즈
- 현재와 목표 TCP 포즈 사이의 오차
- 목표 관절 토크

#### 힘-토크 센서 영점 조정

컨트롤러는 `/aic_controller/tare_force_torque_sensor`에서 힘-토크 센서를 영점 조정(tare)하는 서비스를 제공합니다. 이 서비스는 현재 힘/토크 측정값을 0으로 초기화하여 센서 캘리브레이션이나 센서 바이어스 제거에 유용합니다. 영점 조정 오프셋은 [`ControllerState`](../aic_interfaces/aic_control_interfaces/msg/ControllerState.msg) 메시지의 `fts_tare_offset`으로 발행됩니다.

> **참고:** 각 훈련 에피소드 시작 전(즉, 원격 조작이나 환경에 케이블 스폰 전)에 정확한 힘-토크 피드백을 위해 F/T 센서를 영점 조정하는 것이 중요합니다.

```bash
# FT 센서 영점 조정
ros2 service call /aic_controller/tare_force_torque_sensor std_srvs/srv/Trigger
```

> **중요:** 이 서비스는 평가 중에는 **사용 불가**합니다. 힘-토크 센서 측정값은 채점에 사용되며 참가자는 대회 실행 중 센서를 영점 조정할 수 없습니다.

## 컨트롤러 목표 파라미터

아래 표는 정책이 다양한 태스크를 위해 일반적으로 수정해야 하는 주요 컨트롤러 파라미터를 보여줍니다.

### MotionUpdate

| 파라미터 | 타입 | 설명 |
| :--- | :--- | :--- |
| `header` | `std_msgs/Header` | `frame_id`는 `gripper/tcp` (TCP 프레임) 또는 `base_link` (전역 프레임)이어야 합니다. `stamp` 필드에는 현재 타임스탬프가 있어야 합니다. |
| `pose` | `geometry_msgs/Pose` | TCP의 목표 카르테시안 포즈. `trajectory_generation_mode`가 `MODE_POSITION`일 때 사용됩니다. `frame_id`가 `base_link`인 경우 포즈는 로봇 베이스 기준입니다. `gripper/tcp`인 경우 현재 TCP 위치에서의 오프셋입니다. |
| `velocity` | `geometry_msgs/Twist` | TCP의 목표 속도. `trajectory_generation_mode`가 `MODE_VELOCITY`일 때 사용됩니다. 속도는 `frame_id`에 지정된 프레임 기준입니다. |
| `target_stiffness` | `float64[36]` | 로봇이 목표 포즈에서 벗어나려는 저항을 제어하는 6x6 강성 행렬. 값이 높을수록 더 단단한 제어, 낮을수록 더 유순한 제어. |
| `target_damping` | `float64[36]` | 진동을 줄이는 6x6 감쇠 행렬. 일반적으로 흔들림을 방지하고 안정적인 동작을 위해 `target_stiffness`에 맞게 조정됩니다. |
| `feedforward_wrench_at_tip` | `geometry_msgs/Wrench` | TCP에서의 선택적 외부 힘/토크. 일정한 하향력 적용이나 알려진 도구-환경 상호작용 처리 같은 접촉 태스크에 유용합니다. |
| `wrench_feedback_gains_at_tip` | `float64[6]` | 센서로 측정된 힘/토크에 대한 피드백 게인. |
| `trajectory_generation_mode` | `TrajectoryGenerationMode` | 목표를 해석하는 방법. `MODE_POSITION`은 `pose` 값을 따릅니다. `MODE_VELOCITY`는 `velocity` 값을 따릅니다. |

#### 예제

ROS 2 CLI로 [`MotionUpdate`](../aic_interfaces/aic_control_interfaces/msg/MotionUpdate.msg) 메시지를 통해 포즈 목표를 발행하려면:
```bash
# 카르테시안 목표 모드로 전환하는 서비스 요청
ros2 service call /aic_controller/change_target_mode aic_control_interfaces/srv/ChangeTargetMode "{target_mode: {mode: 1}}"

# 카르테시안 포즈 목표 전송
ros2 topic pub --once /aic_controller/pose_commands aic_control_interfaces/msg/MotionUpdate "{
  header: {
    frame_id: 'base_link'
  },
  pose: {
    position: {x: -0.501, y: -0.175, z: 0.2},
    orientation: {x: 0.7071068, y: 0.7071068, z: 0.0, w: 0.0}
  },
  target_stiffness: [
    85.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 85.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 85.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 85.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 85.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 85.0
  ],
  target_damping: [
    75.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 75.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 75.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 75.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 75.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 75.0
  ],
  feedforward_wrench_at_tip: {
    force: {x: 0.0, y: 0.0, z: 0.0},
    torque: {x: 0.0, y: 0.0, z: 0.0}
  },
  wrench_feedback_gains_at_tip: [
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0
  ],
  trajectory_generation_mode: {mode: 2}
}"
```

속도 목표를 발행하는 방법도 마찬가지로 간단합니다:
```bash
# 다음 명령은 다른 목표가 재정의할 때까지 TCP를 x축으로 0.025 m/s로 이동하고 z축을 중심으로 0.25 rad/s로 회전시킵니다:
ros2 topic pub --once /aic_controller/pose_commands aic_control_interfaces/msg/MotionUpdate "{
  header: {
    frame_id: 'gripper/tcp'
  },
  velocity: {
    linear: {x: 0.025, y: 0.0, z: 0.0},
    angular: {x: 0.0, y: 0.0, z: 0.25}
  },
  target_stiffness: [
    85.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 85.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 85.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 85.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 85.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 85.0
  ],
  target_damping: [
    75.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 75.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 75.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 75.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 75.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 75.0
  ],
  trajectory_generation_mode: {mode: 1}
}"
```

`rclpy`를 사용한 예제는 [test_impedance.py](../aic_bringup/scripts/test_impedance.py) 스크립트 내의 `generate_motion_update()` 함수를 참조하세요.

### JointMotionUpdate

| 파라미터 | 타입 | 설명 |
| :--- | :--- | :--- |
| `target_state` | `trajectory_msgs/JointTrajectoryPoint` | 각 로봇 관절의 목표 관절 값. `trajectory_generation_mode`가 `MODE_POSITION`일 때 `positions` 필드가 사용됩니다. `MODE_VELOCITY`일 때 `velocities` 필드가 사용됩니다. |
| `target_stiffness` | `float64[]` | 각 로봇 관절의 강성. 값이 높을수록 더 단단한 제어, 낮을수록 더 유순한 제어. 배열 크기는 관절 수와 일치해야 합니다. |
| `target_damping` | `float64[]` | 각 로봇 관절의 감쇠. 흔들림 방지 및 안정적인 동작을 위해 `target_stiffness`에 맞게 조정됩니다. 배열 크기는 관절 수와 일치해야 합니다. |
| `target_feedforward_torque` | `float64[]` | 각 로봇 관절의 선택적 추가 토크. 일정한 힘 적용이나 알려진 도구-환경 상호작용 처리에 유용합니다. |
| `trajectory_generation_mode` | `TrajectoryGenerationMode` | 목표를 해석하는 방법. `MODE_POSITION`은 `target_state.positions` 값을 따릅니다. `MODE_VELOCITY`는 `target_state.velocities` 값을 따릅니다. |

#### 예제

[test_impedance.py](../aic_bringup/scripts/test_impedance.py)의 `generate_joint_motion_update()` 함수를 참조하세요.

ROS 2 CLI로 [`JointMotionUpdate`](../aic_interfaces/aic_control_interfaces/msg/JointMotionUpdate.msg) 메시지를 통해 관절 위치 목표를 발행하려면:
```bash
# 관절 목표 모드로 전환하는 서비스 요청
ros2 service call /aic_controller/change_target_mode aic_control_interfaces/srv/ChangeTargetMode "{target_mode: {mode: 2}}"

# 관절 위치 목표 전송
ros2 topic pub --once /aic_controller/joint_commands aic_control_interfaces/msg/JointMotionUpdate "{
  target_state: {
    positions: [0.0, -1.57, -1.57, -1.57, 1.57, 0]
  },
  target_stiffness: [85.0, 85.0, 85.0, 85.0, 85.0, 85.0],
  target_damping: [75.0, 75.0, 75.0, 75.0, 75.0, 75.0], trajectory_generation_mode: {mode: 2}
}"
```

관절 속도 목표를 발행하는 방법도 마찬가지로 간단합니다:
```bash
# 다음 명령은 다른 목표가 재정의할 때까지 모든 관절을 0.025 rad/s로 회전시킵니다:
ros2 topic pub --once /aic_controller/joint_commands aic_control_interfaces/msg/JointMotionUpdate "{
  target_state: {
    velocities: [0.025, 0.025, 0.025, 0.025, 0.025, 0.025]
  },
  target_stiffness: [85.0, 85.0, 85.0, 85.0, 85.0, 85.0],
  target_damping: [75.0, 75.0, 75.0, 75.0, 75.0, 75.0], trajectory_generation_mode: {mode: 1}
}"
```

## 컨트롤러 설정 파라미터

`aic_controller`는 ROS 2 파라미터를 사용하여 목표 제한, 스무딩, 임피던스 제어의 값을 설정합니다. 이는 [aic_controller_parameters.yaml](../aic_controller/src/aic_controller_parameters.yaml)에 설명 및 데이터 타입과 함께 정의되어 있습니다.

> **참고:** 설정은 평가 중 고정되며 모든 참가자가 동일한 컨트롤러 설정을 사용합니다.
