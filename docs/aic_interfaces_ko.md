# AI Challenge 인터페이스

이 문서는 AI for Industry Challenge에서 참가자들이 사용할 수 있는 모든 인터페이스를 정의합니다. 표준 ROS 2 인터페이스와 이 대회를 위해 특별히 정의된 새로운 인터페이스를 포함합니다.

aic_interfaces 폴더에는 하드웨어와 삽입 정책을 연결하는 커스텀 메시지 및 액션 정의가 포함되어 있습니다. 이 인터페이스들은 로봇 및 태스크 환경과 상호작용하는 솔루션을 개발하는 데 중요합니다.

## 인터페이스 개요

대회는 표준 ROS 2 인터페이스와 [aic_interfaces](../aic_interfaces/) 폴더에 정의된 커스텀 인터페이스를 조합하여 사용합니다:

### 표준 ROS 2 인터페이스
- **[sensor_msgs/msg/Image](https://github.com/ros2/common_interfaces/blob/kilted/sensor_msgs/msg/Image.msg)** — 카메라 이미지 데이터용
- **[sensor_msgs/msg/CameraInfo](https://github.com/ros2/common_interfaces/blob/kilted/sensor_msgs/msg/CameraInfo.msg)** — 카메라 캘리브레이션 데이터용
- **[geometry_msgs/msg/WrenchStamped](https://github.com/ros2/common_interfaces/blob/kilted/geometry_msgs/msg/WrenchStamped.msg)** — 힘/토크 센서 데이터용
- **[sensor_msgs/msg/JointState](https://github.com/ros2/common_interfaces/blob/kilted/sensor_msgs/msg/JointState.msg)** — 관절 상태 정보용
- **[tf2_msgs/msg/TFMessage](https://github.com/ros2/geometry2/blob/kilted/tf2_msgs/msg/TFMessage.msg)** — 좌표 변환 데이터용

### 커스텀 인터페이스 ([aic_interfaces](../aic_interfaces/)에 정의)
* **[aic_task_interfaces/action/InsertCable.action](../aic_interfaces/aic_task_interfaces/action/InsertCable.action)**
    * 삽입 정책을 트리거하여 케이블 삽입 태스크를 수행하는 Action 인터페이스.
* **[aic_task_interfaces/msg/Task.msg](../aic_interfaces/aic_task_interfaces/msg/Task.msg)**
    * 케이블 삽입 태스크의 특정 파라미터와 상태를 설명합니다.
* **[aic_control_interfaces/msg/MotionUpdate.msg](../aic_interfaces/aic_control_interfaces/msg/MotionUpdate.msg)**
    * 카르테시안 공간 제어를 위한 목표 포즈와 관련 허용 오차를 설명합니다.
* **[aic_control_interfaces/msg/JointMotionUpdate.msg](../aic_interfaces/aic_control_interfaces/msg/JointMotionUpdate.msg)**
    * 관절 공간 제어를 위한 목표 관절 설정과 관련 허용 오차를 설명합니다.
* **[aic_model_interfaces/msg/Observation.msg](../aic_interfaces/aic_model_interfaces/msg/Observation.msg)**
    * `aic_model` 노드가 구독하는 세계 스냅샷.

---

## 입력

다음 토픽들은 모델에 센서 데이터와 상태 정보를 제공합니다.

### 센서 토픽

| 토픽 | 메시지 타입 | 설명 |
| :--- | :--- | :--- |
| `/left_camera/image` | `sensor_msgs/msg/Image` | 왼쪽 손목 카메라의 보정된 이미지 데이터. |
| `/left_camera/camera_info` | `sensor_msgs/msg/CameraInfo` | 왼쪽 손목 카메라의 캘리브레이션 데이터. |
| `/center_camera/image` | `sensor_msgs/msg/Image` | 중앙 손목 카메라의 보정된 이미지 데이터. |
| `/center_camera/camera_info` | `sensor_msgs/msg/CameraInfo` | 중앙 손목 카메라의 캘리브레이션 데이터. |
| `/right_camera/image` | `sensor_msgs/msg/Image` | 오른쪽 손목 카메라의 보정된 이미지 데이터. |
| `/right_camera/camera_info` | `sensor_msgs/msg/CameraInfo` | 오른쪽 손목 카메라의 캘리브레이션 데이터. |
| `/fts_broadcaster/wrench` | `geometry_msgs/msg/WrenchStamped` | 힘/토크 센서 데이터. |
| `/joint_states` | `sensor_msgs/msg/JointState` | 로봇 관절의 현재 상태. |
| `/gripper_state` | `sensor_msgs/msg/JointState` | 엔드 이펙터/그리퍼의 현재 상태. |
| `/tf` | `tf2_msgs/msg/TFMessage` | 동적 좌표 프레임의 변환 데이터. |
| `/tf_static` | `tf2_msgs/msg/TFMessage` | 정적 좌표 프레임의 변환 데이터. |

### 액션 서버

| 액션 이름 | 액션 타입 | 설명 |
| :--- | :--- | :--- |
| `/insert_cable` | `aic_task_interfaces/action/InsertCable` | 자율 삽입 태스크 트리거. |

### 컨트롤러 토픽

다음 토픽은 모니터링 및 디버깅을 위한 고주파 실시간 상태 텔레메트리 데이터를 제공합니다.

| 토픽 | 메시지 타입 | 설명 |
| :--- | :--- | :--- |
| `/aic_controller/controller_state` | `aic_control_interfaces/msg/ControllerState` | 현재 TCP 포즈 및 속도, 참조 TCP 포즈, TCP 추적 오차, 참조 관절 토크 데이터. |

---

## 출력

삽입 정책은 다음 토픽들에 발행하여 로봇을 제어합니다.

### 명령 토픽

| 토픽 | 메시지 타입 | 설명 |
| :--- | :--- | :--- |
| `/aic_controller/joint_commands` | `aic_control_interfaces/msg/JointMotionUpdate` | 관절 공간 제어를 위한 목표 설정. |
| `/aic_controller/pose_commands` | `aic_control_interfaces/msg/MotionUpdate` | 카르테시안 공간 제어를 위한 목표 포즈. |

> **참고:** 컨트롤러는 상호 배타적인 모드로 작동합니다. 예를 들어, 컨트롤러가 `Cartesian` 목표 모드인 경우 `/aic_controller/pose_commands` 토픽의 메시지를 처리하고 `/aic_controller/joint_commands`의 메시지는 무시합니다. 컨트롤러가 해당 타입의 명령을 수락하려면 `/aic_controller/change_target_mode` 서비스를 통해 활성 목표 모드를 설정해야 합니다.

---

## 컨트롤러 설정

### 서비스

| 서비스 이름 | 서비스 타입 | 설명 |
| :--- | :--- | :--- |
| `/aic_controller/change_target_mode` | `aic_control_interfaces/srv/ChangeTargetMode` | 목표 모드(카르테시안 또는 관절)를 선택합니다. 컨트롤러는 그에 따라 `/aic_controller/pose_commands` 또는 `/aic_controller/joint_commands`를 구독합니다. |
| `/aic_controller/tare_force_torque_sensor` | `std_srvs/srv/Trigger` | 힘/토크 센서를 영점 조정하는 서비스. 평가 중에는 비활성화됩니다. 평가 시스템은 환경에 케이블이 스폰되기 전에 자동으로 이 서비스를 호출합니다. |
| `/expand_xacro` | `aic_training_interfaces/srv/ExpandXacro` | 설치된 ROS 패키지에서 xacro 파일을 XML로 확장합니다. 확장된 XML 문자열을 반환합니다. 평가 환경에 직접 파일 시스템 접근 없이 훈련 중 엔티티 스폰(예: 태스크 보드, 케이블)에 유용합니다. |
