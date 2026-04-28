# Custom Policy 개발 가이드

이 문서는 `my_policy` 패키지를 기반으로 자신만의 정책(Policy)을 개발하는 방법을 설명합니다.

---

## 1. 패키지 구조

```
aic/my_policy/
  my_policy/
    __init__.py       ← Python 패키지 선언 (빈 파일, 수정 불필요)
    MyPolicy.py       ← 실제 정책 코드 (여기만 수정)
  resource/
    my_policy         ← ament 패키지 등록용 빈 파일 (수정 불필요)
  package.xml         ← ROS2 패키지 의존성 선언
  setup.py            ← Python 패키지 설치 설정
  pixi.toml           ← pixi 빌드 설정
```

---

## 2. MyPolicy.py 구조

`MyPolicy`는 `Policy` 추상 클래스를 상속받아 `insert_cable()` 메서드를 구현합니다.

```python
from aic_model.policy import Policy, GetObservationCallback, MoveRobotCallback, SendFeedbackCallback
from aic_task_interfaces.msg import Task

class MyPolicy(Policy):
    def __init__(self, parent_node):
        super().__init__(parent_node)
        # 초기화 코드 (모델 로드 등)

    def insert_cable(
        self,
        task: Task,
        get_observation: GetObservationCallback,
        move_robot: MoveRobotCallback,
        send_feedback: SendFeedbackCallback,
    ) -> bool:
        # 케이블 삽입 로직 구현
        return True  # 성공 시 True, 실패 시 False
```

### insert_cable() 인자 설명

| 인자 | 타입 | 설명 |
|---|---|---|
| `task` | `Task` | 어떤 케이블을 어떤 포트에 꽂는지 정보 |
| `get_observation` | `Callable` | 호출 시 최신 센서 데이터 반환 |
| `move_robot` | `Callable` | 로봇 이동 명령 전송 |
| `send_feedback` | `Callable` | 진행 상황 문자열 전송 |

### Task 메시지 주요 필드

```python
task.id                  # 작업 고유 ID (예: "mujoco_task_1")
task.cable_name          # 케이블 이름 (예: "cable_0")
task.plug_name           # 플러그 이름 (예: "sfp_tip")
task.port_name           # 포트 이름 (예: "sfp_port_0")
task.target_module_name  # 모듈 이름 (예: "nic_card_mount_0")
task.time_limit          # 제한 시간 (초)
```

---

## 3. Policy 기반 클래스 헬퍼 메서드

`Policy` 기반 클래스가 제공하는 편의 메서드들입니다.

### 로봇 이동

```python
from geometry_msgs.msg import Pose, Point, Quaternion

pose = Pose(
    position=Point(x=0.3, y=0.0, z=0.5),
    orientation=Quaternion(w=1.0, x=0.0, y=0.0, z=0.0),
)
self.set_pose_target(move_robot=move_robot, pose=pose)
# gripper/tcp를 base_link 기준 지정 pose로 이동
```

### 대기

```python
self.sleep_for(2.0)   # 시뮬레이션 시간 기준 2초 대기
```

### 시간 조회

```python
now = self.time_now()  # 현재 시뮬레이션 시간 반환
```

### 센서 데이터 읽기

```python
obs = get_observation()

obs.left_image        # 왼쪽 카메라 이미지 (sensor_msgs/Image)
obs.center_image      # 중앙 카메라 이미지
obs.right_image       # 오른쪽 카메라 이미지
obs.joint_states      # 관절 각도 (sensor_msgs/JointState)
obs.wrist_wrench      # 손목 힘/토크 (geometry_msgs/WrenchStamped)
obs.controller_state  # 컨트롤러 상태 (현재 TCP pose, velocity 등)
```

---

## 4. 빌드 및 실행

### 빌드 (코드 수정 후 매번 실행)

```bash
cd ~/ws_aic/src/aic
pixi reinstall ros-kilted-my-policy
```

### MuJoCo 환경에서 실행

```bash
# 터미널 1: MuJoCo 시뮬레이터 시작
ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true

# 터미널 2: aic_model 노드 실행 (my_policy 로드)
ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=my_policy.MyPolicy

# 터미널 3: 정책 트리거
python3 ~/ws_aic/src/aic/aic_utils/aic_mujoco/scripts/trigger_policy.py
```

### 파라미터 설명

| 파라미터 | 값 | 설명 |
|---|---|---|
| `use_sim_time` | `true` | MuJoCo 시뮬레이션 시계 사용 |
| `policy` | `my_policy.MyPolicy` | `패키지명.클래스명` 형식 |

---

## 5. TF 활용 (ground_truth 사용 시)

`ground_truth:=true`로 실행하면 포트/플러그의 정확한 위치가 TF로 제공됩니다.
CheatCode처럼 TF를 직접 조회하려면 `AicModel` 노드의 TF 버퍼를 사용합니다.

```python
from tf2_ros import TransformException
from rclpy.time import Time

# 포트 위치 조회 (base_link 기준)
try:
    port_tf = self._parent_node._tf_buffer.lookup_transform(
        "base_link",
        f"task_board/{task.target_module_name}/{task.port_name}_link",
        Time(),
    )
    px = port_tf.transform.translation.x
    py = port_tf.transform.translation.y
    pz = port_tf.transform.translation.z
except TransformException as ex:
    self.get_logger().warn(f"TF 조회 실패: {ex}")
```

TF 프레임 이름 규칙:
- 포트: `task_board/{target_module_name}/{port_name}_link`
- 플러그: `{cable_name}/{plug_name}_link`
- 그리퍼: `gripper/tcp`

---

## 6. 새 정책 클래스 추가 방법

`my_policy/` 디렉토리에 새 파일을 추가하면 여러 정책을 관리할 수 있습니다.

```
my_policy/
  MyPolicy.py        ← 기본 정책
  VisionPolicy.py    ← 카메라 기반 정책
  ForcePolicy.py     ← 힘 제어 기반 정책
```

실행 시 파라미터만 바꾸면 됩니다:

```bash
-p policy:=my_policy.VisionPolicy
-p policy:=my_policy.ForcePolicy
```

---

## 7. 주의사항

- `insert_cable()`은 **별도 스레드**에서 실행됩니다. ROS2 콜백과 동시에 실행되므로 공유 데이터 접근 시 주의하세요.
- `sleep_for()`는 반드시 `self.sleep_for()`를 사용하세요. `time.sleep()`은 시뮬레이션 시간과 무관하게 실제 시간을 기다립니다.
- `return True`는 삽입 **성공**, `return False`는 **실패**입니다. `None`을 반환하면 `False`로 처리됩니다.
- 코드 수정 후 반드시 `pixi reinstall ros-kilted-my-policy`를 실행해야 변경사항이 반영됩니다.
