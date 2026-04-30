# aic_bringup

## 개요

`aic_bringup`은 AI for Industry Challenge 시뮬레이션 환경을 구성하기 위한 launch 파일과 설정을 제공합니다. 이 패키지는 평가 컴포넌트의 일부이며, 평가 환경 시작, 로봇 및 태스크 보드 스폰, 시험 실행을 위한 진입점입니다.

**이 패키지가 하는 일:**
- UR5e 로봇과 함께 Gazebo 시뮬레이션 실행
- 다양한 커넥터 마운트가 있는 태스크 보드 스폰
- 로봇 제어를 위한 AIC 컨트롤러 시작
- 자동화된 시험 조율을 위한 `aic_engine` 선택적 시작
- 센서/액추에이터 통신을 위한 ROS-Gazebo 브릿지 구성

---

## 빠른 시작

### 기본 시뮬레이션 (태스크 보드 없음)

```bash
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true;transport/shared_memory/transport_optimization/pool_size=536870912'

ros2 launch aic_bringup aic_gz_bringup.launch.py
```

실행 내용:
- Gazebo 시뮬레이션
- 손목 카메라 3대가 달린 UR5e 로봇
- AIC 컨트롤러 (임피던스 제어 모드)
- ROS-Gazebo 브릿지

### 완전한 예선 환경

실제 예선 시험을 위해:

```bash
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  ground_truth:=false \
  start_aic_engine:=true
```

추가 내용:
- 시험 조율을 위한 AIC 엔진
- 평가 채점 시스템
- Ground truth 데이터 숨김 (실제 평가와 동일)

### 개발 모드 (Ground Truth 포함)

정책 개발 시 디버깅을 위해 ground truth를 활성화:

```bash
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  ground_truth:=true \
  spawn_task_board:=true
```

제공 내용:
- 태스크 보드 요소에 대한 ground truth TF 프레임
- Gazebo에서의 시각적 디버깅
- 더 쉬운 정책 개발

---

## Launch 파일

### 1. `aic_gz_bringup.launch.py`

완전한 AIC 시뮬레이션 환경을 위한 **주요 launch 파일**입니다.

> [!NOTE]
> 평가 중에는 태스크 보드와 모든 컴포넌트의 roll 및 pitch가 고정되며 (모두 0.0), SC 포트 yaw도 0.0으로 고정됩니다. 그러나 도메인 랜덤화를 위해 참가자는 임의의 방향을 설정할 수 있습니다.

#### 사용법
```bash
ros2 launch aic_bringup aic_gz_bringup.launch.py [파라미터]
```

#### 설정 가능한 파라미터

**로봇 스폰 위치:**
- `robot_x` (기본값: `"-0.2"`) - 로봇 스폰 X 위치 (미터)
- `robot_y` (기본값: `"0.2"`) - 로봇 스폰 Y 위치 (미터)
- `robot_z` (기본값: `"1.14"`) - 로봇 스폰 Z 위치 (미터)
- `robot_roll` (기본값: `"0.0"`) - 로봇 스폰 roll 방향 (라디안)
- `robot_pitch` (기본값: `"0.0"`) - 로봇 스폰 pitch 방향 (라디안)
- `robot_yaw` (기본값: `"-3.141"`) - 로봇 스폰 yaw 방향 (라디안)

**컨트롤러 설정:**
- `controllers_file` (기본값: `"ur_controllers.yaml"`) - 컨트롤러 설정 YAML 파일
- `activate_joint_controller` (기본값: `"true"`) - 시작 시 joint 컨트롤러 활성화
- `initial_joint_controller` (기본값: `"aic_controller"`) - 초기 활성화할 컨트롤러
- `description_file` (기본값: `"ur.urdf.xacro"`) - 로봇 description 파일

**태스크 보드 설정:**
- `spawn_task_board` (기본값: `"false"`) - 태스크 보드 스폰 여부
- `task_board_description_file` (기본값: `"task_board.urdf.xacro"`) - 태스크 보드 URDF/XACRO 파일
- `task_board_x` (기본값: `"0.15"`) - 태스크 보드 스폰 X 위치 (미터)
- `task_board_y` (기본값: `"-0.2"`) - 태스크 보드 스폰 Y 위치 (미터)
- `task_board_z` (기본값: `"1.14"`) - 태스크 보드 스폰 Z 위치 (미터)
- `task_board_roll` (기본값: `"0.0"`) - 태스크 보드 스폰 roll 방향 (라디안)
- `task_board_pitch` (기본값: `"0.0"`) - 태스크 보드 스폰 pitch 방향 (라디안)
- `task_board_yaw` (기본값: `"0.0"`) - 태스크 보드 스폰 yaw 방향 (라디안)

**케이블 설정:**
- `spawn_cable` (기본값: `"false"`) - 케이블 스폰 여부
- `cable_description_file` (기본값: `"cable.sdf.xacro"`) - 케이블 SDF/XACRO 파일
- `attach_cable_to_gripper` (기본값: `"false"`) - 케이블을 그리퍼에 부착 여부
- `cable_type` (기본값: `"sfp_sc_cable"`) - 스폰할 케이블 타입. 옵션: [`sfp_sc_cable`, `sfp_sc_cable_reversed`]
- `cable_x` (기본값: `"0.172"`) - 케이블 스폰 X 위치 (미터)
- `cable_y` (기본값: `"0.024"`) - 케이블 스폰 Y 위치 (미터)
- `cable_z` (기본값: `"1.518"`) - 케이블 스폰 Z 위치 (미터)
    - 참고: `cable_type`이 `sfp_sc_cable_reversed`인 경우 `cable_z`를 `1.508`로 설정
- `cable_roll` (기본값: `"0.4432"`) - 케이블 스폰 roll 방향 (라디안)
- `cable_pitch` (기본값: `"-0.48"`) - 케이블 스폰 pitch 방향 (라디안)
- `cable_yaw` (기본값: `"1.3303"`) - 케이블 스폰 yaw 방향 (라디안)

**Gazebo 설정:**
- `world_file` (기본값: `"aic.sdf"`) - Gazebo 월드 파일
- `gazebo_gui` (기본값: `"true"`) - Gazebo GUI 실행
- `ros_gz_bridge_config_file` (기본값: `"ros_gz_bridge.yaml"`) - ROS-Gazebo 브릿지 설정 파일

**시각화:**
- `launch_rviz` (기본값: `"false"`) - 시각화를 위한 RViz 실행
- `rviz_config_file` (기본값: `"view_robot.rviz"`) - RViz 설정 파일

**Ground Truth:**
- `ground_truth` (기본값: `"false"`) - TF 토픽에 ground truth 포즈 데이터 포함 여부

**AIC 엔진:**
- `start_aic_engine` (기본값: `"false"`) - 평가를 위한 `aic_engine` 조율 노드 시작 여부
- `shutdown_on_aic_engine_exit` (기본값: `"false"`) - `aic_engine` 종료 시 전체 launch 파일 종료 및 종료 코드 전파 여부. `start_aic_engine`이 `true`일 때만 적용됨. 시험 완료 후 컨테이너가 종료되어야 하는 자동화 평가에 유용.
- `aic_engine_config_file` (기본값: `"aic_engine/config/sample_config.yaml"`) - AIC 엔진 설정 YAML 파일의 절대 경로
- `model_discovery_timeout_seconds` (기본값: `"30"`) - 참가자 모델 검색 타임아웃 (초)

---

### 2. `spawn_task_board.launch.py`

기존 Gazebo 시뮬레이션에서 태스크 보드를 스폰하기 위한 독립형 launch 파일입니다.

> [!NOTE]
> 평가 중에는 태스크 보드와 모든 컴포넌트의 roll 및 pitch가 고정되며 (모두 0.0), SC 포트 yaw도 0.0으로 고정됩니다. 그러나 도메인 랜덤화를 위해 참가자는 임의의 방향을 설정할 수 있습니다.

#### 사용법
```bash
ros2 launch aic_bringup spawn_task_board.launch.py
```

#### 설정 가능한 파라미터

**태스크 보드 기본 설정:**
- `task_board_description_file` (기본값: `"task_board.urdf.xacro"`) - 태스크 보드 URDF/XACRO description 파일
- `task_board_x` (기본값: `"0.25"`) - 태스크 보드 스폰 X 위치 (미터)
- `task_board_y` (기본값: `"0.0"`) - 태스크 보드 스폰 Y 위치 (미터)
- `task_board_z` (기본값: `"1.14"`) - 태스크 보드 스폰 Z 위치 (미터)
- `task_board_roll` (기본값: `"0.0"`) - 태스크 보드 스폰 roll 방향 (라디안)
- `task_board_pitch` (기본값: `"0.0"`) - 태스크 보드 스폰 pitch 방향 (라디안)
- `task_board_yaw` (기본값: `"0.0"`) - 태스크 보드 스폰 yaw 방향 (라디안)

**마운트 레일 (LC/SFP/SC):**

태스크 보드에는 LC, SFP, SC 커넥터 마운트를 위한 6개의 마운트 레일이 있습니다. 각 레일은 유무, 레일을 따른 이동량, 방향을 설정할 수 있습니다.

*LC 마운트 레일 0 (왼쪽):*
- `lc_mount_rail_0_present` (기본값: `"false"`) - 레일 0에 LC 마운트 유무
- `lc_mount_rail_0_translation` (기본값: `"0.0"`) - 레일을 따른 이동량 (미터, 범위: -0.09625 ~ 0.09625)
- `lc_mount_rail_0_roll` (기본값: `"0.0"`) - roll 방향 (라디안)
- `lc_mount_rail_0_pitch` (기본값: `"0.0"`) - pitch 방향 (라디안)
- `lc_mount_rail_0_yaw` (기본값: `"0.0"`) - yaw 방향 (라디안)

*SFP 마운트 레일 0 (왼쪽):*
- `sfp_mount_rail_0_present` (기본값: `"false"`) - 레일 0에 SFP 마운트 유무
- `sfp_mount_rail_0_translation` (기본값: `"0.0"`) - 레일을 따른 이동량 (미터, 범위: -0.09625 ~ 0.09625)
- `sfp_mount_rail_0_roll` (기본값: `"0.0"`) - roll 방향 (라디안)
- `sfp_mount_rail_0_pitch` (기본값: `"0.0"`) - pitch 방향 (라디안)
- `sfp_mount_rail_0_yaw` (기본값: `"0.0"`) - yaw 방향 (라디안)

*SC 마운트 레일 0 (왼쪽):*
- `sc_mount_rail_0_present` (기본값: `"false"`) - 레일 0에 SC 마운트 유무
- `sc_mount_rail_0_translation` (기본값: `"0.0"`) - 레일을 따른 이동량 (미터, 범위: -0.09625 ~ 0.09625)
- `sc_mount_rail_0_roll` (기본값: `"0.0"`) - roll 방향 (라디안)
- `sc_mount_rail_0_pitch` (기본값: `"0.0"`) - pitch 방향 (라디안)
- `sc_mount_rail_0_yaw` (기본값: `"0.0"`) - yaw 방향 (라디안)

*LC 마운트 레일 1 (오른쪽):*
- `lc_mount_rail_1_present` (기본값: `"false"`) - 레일 1에 LC 마운트 유무
- `lc_mount_rail_1_translation` (기본값: `"0.0"`) - 레일을 따른 이동량 (미터, 범위: -0.09625 ~ 0.09625)
- `lc_mount_rail_1_roll` (기본값: `"0.0"`) - roll 방향 (라디안)
- `lc_mount_rail_1_pitch` (기본값: `"0.0"`) - pitch 방향 (라디안)
- `lc_mount_rail_1_yaw` (기본값: `"0.0"`) - yaw 방향 (라디안)

*SFP 마운트 레일 1 (오른쪽):*
- `sfp_mount_rail_1_present` (기본값: `"false"`) - 레일 1에 SFP 마운트 유무
- `sfp_mount_rail_1_translation` (기본값: `"0.0"`) - 레일을 따른 이동량 (미터, 범위: -0.09625 ~ 0.09625)
- `sfp_mount_rail_1_roll` (기본값: `"0.0"`) - roll 방향 (라디안)
- `sfp_mount_rail_1_pitch` (기본값: `"0.0"`) - pitch 방향 (라디안)
- `sfp_mount_rail_1_yaw` (기본값: `"0.0"`) - yaw 방향 (라디안)

*SC 마운트 레일 1 (오른쪽):*
- `sc_mount_rail_1_present` (기본값: `"false"`) - 레일 1에 SC 마운트 유무
- `sc_mount_rail_1_translation` (기본값: `"0.0"`) - 레일을 따른 이동량 (미터, 범위: -0.09625 ~ 0.09625)
- `sc_mount_rail_1_roll` (기본값: `"0.0"`) - roll 방향 (라디안)
- `sc_mount_rail_1_pitch` (기본값: `"0.0"`) - pitch 방향 (라디안)
- `sc_mount_rail_1_yaw` (기본값: `"0.0"`) - yaw 방향 (라디안)

**SC 포트 레일:**

SC 포트 모듈을 부착하기 위한 2개의 SC 포트 레일입니다.

*SC 포트 0:*
- `sc_port_0_present` (기본값: `"false"`) - 레일 0에 SC 포트 유무
- `sc_port_0_translation` (기본값: `"0.0"`) - 레일을 따른 이동량 (미터)
- `sc_port_0_roll` (기본값: `"0.0"`) - roll 방향 (라디안)
- `sc_port_0_pitch` (기본값: `"0.0"`) - pitch 방향 (라디안)
- `sc_port_0_yaw` (기본값: `"0.0"`) - yaw 방향 (라디안)

*SC 포트 1:*
- `sc_port_1_present` (기본값: `"false"`) - 레일 1에 SC 포트 유무
- `sc_port_1_translation` (기본값: `"0.0"`) - 레일을 따른 이동량 (미터)
- `sc_port_1_roll` (기본값: `"0.0"`) - roll 방향 (라디안)
- `sc_port_1_pitch` (기본값: `"0.0"`) - pitch 방향 (라디안)
- `sc_port_1_yaw` (기본값: `"0.0"`) - yaw 방향 (라디안)

**NIC 카드 마운트 레일:**

네트워크 인터페이스 카드를 부착하기 위한 5개의 NIC 카드 마운트 레일입니다.

*NIC 카드 마운트 0~4:* (각 마운트 0, 1, 2, 3, 4에 대해 파라미터 반복)
- `nic_card_mount_N_present` (기본값: `"false"`) - NIC 카드 마운트 N 유무
- `nic_card_mount_N_translation` (기본값: `"0.0"`) - 레일을 따른 이동량 (미터)
- `nic_card_mount_N_roll` (기본값: `"0.0"`) - roll 방향 (라디안)
- `nic_card_mount_N_pitch` (기본값: `"0.0"`) - pitch 방향 (라디안)
- `nic_card_mount_N_yaw` (기본값: `"0.0"`) - yaw 방향 (라디안)

---

### 3. `spawn_cable.launch.py`

기존 Gazebo 시뮬레이션에서 케이블을 스폰하기 위한 독립형 launch 파일입니다.

#### 사용법
```bash
ros2 launch aic_bringup spawn_cable.launch.py
```

#### 설정 가능한 파라미터

- `cable_description_file` (기본값: `"cable.sdf.xacro"`) - 케이블 URDF/XACRO description 파일
- `cable_x` (기본값: `"-0.35"`) - 케이블 스폰 X 위치 (미터)
- `cable_y` (기본값: `"0.4"`) - 케이블 스폰 Y 위치 (미터)
- `cable_z` (기본값: `"1.15"`) - 케이블 스폰 Z 위치 (미터)
- `cable_roll` (기본값: `"0.0"`) - 케이블 스폰 roll 방향 (라디안)
- `cable_pitch` (기본값: `"0.0"`) - 케이블 스폰 pitch 방향 (라디안)
- `cable_yaw` (기본값: `"0.0"`) - 케이블 스폰 yaw 방향 (라디안)
- `attach_cable_to_gripper` (기본값: `"false"`) - 케이블을 그리퍼에 부착 여부

---

## 사용 예시

### 기본 시뮬레이션 실행
기본 파라미터로 완전한 시뮬레이션 시작:
```bash
ros2 launch aic_bringup aic_gz_bringup.launch.py
```

### 커스텀 로봇 위치로 실행
```bash
ros2 launch aic_bringup aic_gz_bringup.launch.py robot_x:=1.0 robot_y:=0.5
```

### 태스크 보드 및 케이블과 함께 실행
```bash
ros2 launch aic_bringup aic_gz_bringup.launch.py spawn_task_board:=true spawn_cable:=true
```

### 레일 0에 LC 마운트가 있는 태스크 보드 스폰
```bash
ros2 launch aic_bringup spawn_task_board.launch.py \
  lc_mount_rail_0_present:=true \
  lc_mount_rail_0_translation:=0.05
```

---

## 임피던스 컨트롤러로 실행

### AIC 컨트롤러로 시뮬레이션 시작

```bash
ros2 launch aic_bringup aic_gz_bringup.launch.py
```

### joint(`JointMotionUpdate`) 및 Cartesian 목표(`MotionUpdate`)를 전송하는 스크립트 시작

이 스크립트는 목표를 전송하는 사이에 `ChangeTargetMode` 서비스를 호출하여 Joint 모드와 Cartesian 모드를 전환합니다.
```bash
ros2 run aic_bringup test_impedance.py
```

---

## 참고 사항

- 모든 위치 값의 단위는 미터입니다
- 모든 방향 값의 단위는 라디안입니다
- 마운트 레일의 이동 범위는 충돌 방지를 위해 -0.09625 ~ 0.09625 미터로 제한됩니다
- 마운트 레일은 타입별로 구분됩니다: LC, SFP, SC 마운트는 각자 지정된 레일에만 부착 가능합니다
- 포트 레일(`sc_port` 및 `nic_card_mount`)은 마운트 레일과 별개입니다
