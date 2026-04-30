# Custom Policy 만들기

## 1. 파일 생성 위치

```
aic/aic_example_policies/aic_example_policies/ros/
    CheatCode.py
    RunACT.py
    MyPolicy.py   ← 여기에 생성
```

---

## 2. 규칙

### 파일명 = 클래스명

`aic_model.py`가 모듈 경로의 마지막 이름으로 클래스를 찾기 때문에 반드시 일치해야 합니다.

- 파일명: `MyPolicy.py`
- 클래스명: `class MyPolicy`

### `Policy` 추상 클래스 상속 + `insert_cable()` 구현 필수

---

## 3. 최소 템플릿

```python
from aic_model.policy import (
    Policy,
    GetObservationCallback,
    MoveRobotCallback,
    SendFeedbackCallback,
)
from aic_task_interfaces.msg import Task


class MyPolicy(Policy):
    def __init__(self, parent_node):
        super().__init__(parent_node)
        # 모델 로드 등 초기화 작업

    def insert_cable(
        self,
        task: Task,
        get_observation: GetObservationCallback,
        move_robot: MoveRobotCallback,
        send_feedback: SendFeedbackCallback,
    ) -> bool:
        # task: 어떤 케이블을 어떤 포트에 꽂아야 하는지 정보
        # get_observation(): 카메라 이미지 등 센서 데이터 반환
        # move_robot(): 로봇 이동 명령
        # send_feedback(): 진행 상황 전송

        # 예시: Cartesian 목표 위치로 이동
        # self.set_pose_target(move_robot, pose)

        return True   # True=성공, False=실패
```

---

## 4. 로봇 제어 방법

### Cartesian 모드 (그리퍼 위치/방향 지정)

```python
from geometry_msgs.msg import Pose

pose = Pose()
pose.position.x = 0.5
pose.position.y = 0.0
pose.position.z = 1.2
self.set_pose_target(move_robot, pose)
```

`Policy` 기반 클래스의 `set_pose_target()`을 사용하면 `MotionUpdate` 메시지를 자동으로 구성해 발행합니다. 컨트롤러가 역기구학을 계산하여 관절을 움직입니다.

### 유용한 헬퍼 메서드 (Policy 기반 클래스 제공)

| 메서드 | 설명 |
|--------|------|
| `set_pose_target(move_robot, pose)` | 그리퍼 TCP를 지정 pose로 이동 |
| `sleep_for(duration_sec)` | 시뮬 시간 기준 대기 |
| `time_now()` | 현재 시뮬 시간 반환 |
| `get_logger()` | ROS2 로거 반환 |

---

## 5. 관찰 데이터 사용

```python
obs = get_observation()

# 카메라 이미지
obs.left_image     # 왼쪽 카메라
obs.center_image   # 중앙 카메라
obs.right_image    # 오른쪽 카메라

# 로봇 상태
obs.controller_state.tcp_pose      # 그리퍼 위치/방향
obs.controller_state.tcp_velocity  # 그리퍼 속도
obs.controller_state.tcp_error     # 목표와의 오차 (6차원)
obs.joint_states.position          # 관절 각도
```

---

## 6. ACT 모델 사용 예시 (RunACT.py 참고)

```python
import torch
from lerobot.policies.act.modeling_act import ACTPolicy
from safetensors.torch import load_file
from huggingface_hub import snapshot_download

class MyPolicy(Policy):
    def __init__(self, parent_node):
        super().__init__(parent_node)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # HuggingFace에서 가중치 다운로드
        policy_path = snapshot_download(repo_id="your_hf_id/your_model")

        # 모델 로드
        self.model = ACTPolicy(config)
        self.model.load_state_dict(load_file(policy_path + "/model.safetensors"))
        self.model.eval()
        self.model.to(self.device)
```

---

## 7. 빌드 및 실행

### 빌드

```bash
cd ~/ws_aic/src/aic
pixi run build
```

### 실행

```bash
# 터미널 1: 시뮬레이터
ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true

# 터미널 2: Policy 노드 실행
pixi run ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.MyPolicy

# 터미널 3: 정책 트리거
python3 ~/ws_aic/src/aic/aic_utils/aic_mujoco/scripts/trigger_policy.py
```

---

## 8. 동작 원리 요약

```
trigger_policy.py
    │
    └─ /insert_cable 액션 Goal 전송
            │
            ▼
        AicModel 노드 (aic_model.py)
            │  importlib로 MyPolicy 동적 로드
            │  on_configure() 시 MyPolicy(self) 인스턴스 생성
            │
            └─ MyPolicy.insert_cable() 호출
                    │
                    ├─ get_observation() → 카메라/센서 데이터
                    ├─ move_robot()      → MotionUpdate 발행 → aic_controller
                    └─ send_feedback()   → 진행 상황 전송
```

---

## 9. TQC (Truncated Quantile Critics) 적용

### 왜 sb3/tqc-FetchPickAndPlace-v1을 직접 쓸 수 없나?

HuggingFace의 `sb3/tqc-FetchPickAndPlace-v1` 모델은 블록 집기/놓기 태스크용으로 학습되어, AIC 케이블 삽입과 관측/행동 공간이 달라 **직접 적용 불가**합니다.

| | FetchPickAndPlace | AIC |
|--|--|--|
| 관측 | 25-dim 상태 + goal (3) | 26-dim 상태 + 카메라 3대 |
| 행동 | 4-dim (dx,dy,dz,그리퍼) | 6-dim Cartesian 속도 |
| 태스크 | 블록 집어서 목표 위치에 놓기 | SFP 케이블 포트에 삽입 |

→ **TQC 알고리즘**만 차용하여 AIC 전용 모델을 새로 학습해야 합니다.

### 파일 구성

```
my_policy/
  my_policy/
    aic_env.py      ← AIC용 Gymnasium 환경 (학습에 사용)
    RunTQC.py       ← 학습된 TQC 모델로 추론하는 Policy
  scripts/
    train_tqc.py    ← TQC 학습 스크립트
```

### 설계 (AIC 전용 관측/행동 공간)

**관측 공간 (HER 호환 Dict)**

| 키 | 차원 | 내용 |
|---|---|---|
| `observation` | 26 | TCP 위치(3) + 자세(4) + 선속도(3) + 각속도(3) + 오차(6) + 관절각(7) |
| `achieved_goal` | 3 | 현재 플러그 끝 위치 (base_link 기준) |
| `desired_goal` | 3 | 목표 포트 위치 (base_link 기준, TF에서 조회) |

**행동 공간**: 6-dim Cartesian 속도 `[vx, vy, vz, wx, wy, wz]`, ±0.05 m/s 클리핑

**보상: 5단계 구조**

축별 오차는 **포트 로컬 프레임** 기준으로 분리합니다:
- Local X, Y = 삽입 구멍 측면 (좌우, 상하)
- Local Z = 삽입 깊이 축 (포트 안으로 들어가는 방향)

```
보상 = Dense base + 단계 보너스 (최초 달성 시 1회)

Dense base : -||plug_pos - port_pos||     (항상 활성, HER 호환)

Stage 1 (+1.0) : 방향 정렬
                 플러그↔포트 자세 각도 오차 < 25°

Stage 2 (+1.0) : X축 측면 정렬
                 포트 로컬 X 오차 < 10mm

Stage 3 (+1.0) : Y축 측면 정렬
                 포트 로컬 Y 오차 < 10mm

Stage 4 (+2.0) : 삽입 전 준비
                 X·Y 오차 모두 < 5mm (삽입 축 진입 직전 위치)

Stage 5 (+5.0) : 삽입 성공
                 전체 거리 < 3mm → 에피소드 종료
```

단계가 누적되므로 최대 에피소드당 +10.0 보너스.
HER는 `compute_reward()`를 통해 dense base만 재계산합니다.

### 의존성 설치

`pixi.toml`에 아래 항목이 추가됩니다 (이미 적용됨):

```toml
[pypi-dependencies]
stable-baselines3 = ">=2.3.0"
sb3-contrib = ">=2.3.0"
gymnasium = ">=0.29.0"
huggingface-sb3 = ">=3.0.0"
```

설치:
```bash
cd ~/ws_aic/src/aic
pixi install
```

### 학습 명령어 (MuJoCo 로컬 환경)

**터미널 1** — 패키지 설치 및 MuJoCo 시뮬레이터 시작:

```bash
cd ~/ws_aic/src/aic && pixi install
```

설치 완료 후:

```bash
cd ~/ws_aic/src/aic && pixi run ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true
```

**터미널 2** — TQC 학습 시작 (~1M 스텝, GPU 권장):

```bash
cd ~/ws_aic/src/aic && pixi run python3 my_policy/scripts/train_tqc.py
```

학습 재개 시:

```bash
cd ~/ws_aic/src/aic && pixi run python3 my_policy/scripts/train_tqc.py --resume logs/tqc_aic/best_model.zip
```

**터미널 3** — TensorBoard 모니터링 (선택):

```bash
cd ~/ws_aic/src/aic && pixi run tensorboard --logdir logs/tqc_aic
```

학습 완료 후 생성 파일:
```
models/tqc_aic/tqc_aic_final.zip    ← 최종 모델
logs/tqc_aic/best_model.zip         ← 평가 기준 최고 모델
logs/tqc_aic/evaluations.npz        ← 평가 기록
```

---

### 추론 명령어

#### MuJoCo 로컬 테스트

**터미널 1** — MuJoCo 시뮬레이터:

```bash
cd ~/ws_aic/src/aic && pixi run ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true
```

**터미널 2** — RunTQC 정책
(미리 준비 후 `Retrying...` 보이면 Enter):

```bash
cd ~/ws_aic/src/aic && pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=my_policy.RunTQC
```

**터미널 3** — 정책 트리거:

```bash
python3 ~/ws_aic/src/aic/aic_utils/aic_mujoco/scripts/trigger_policy.py
```

#### Gazebo 평가 환경 (제출용)

**터미널 1** — 컨테이너 진입 및 시뮬레이션 시작:

```bash
export DBX_CONTAINER_MANAGER=docker
distrobox enter -r aic_eval
```

컨테이너 안에서:

```bash
/entrypoint.sh ground_truth:=false start_aic_engine:=true
```

**터미널 2** — RunTQC 정책
(미리 준비 후 `Retrying...` 보이면 Enter):

```bash
cd ~/ws_aic/src/aic && pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=my_policy.RunTQC
```

### 전체 데이터 흐름

```
[학습]
AICEnv (aic_env.py)
  ├─ reset() → 초기 관측 반환
  ├─ step(action)
  │     ├─ send_velocity() → /aic_controller/pose_commands 발행
  │     ├─ 0.05초 대기 (20Hz)
  │     ├─ 관측 수집 → achieved_goal / desired_goal 계산
  │     └─ reward = -||achieved - desired||
  └─ TQC + HER가 replay buffer에서 샘플링 → 학습

[추론]
RunTQC.insert_cable()
  ├─ TF에서 포트 위치 조회 → desired_goal
  └─ 루프 (60초, 20Hz):
        ├─ get_observation() → obs_dict 변환
        ├─ TQC.predict(obs_dict) → 6-dim action
        ├─ action → MotionUpdate → move_robot()
        └─ 거리 < 5mm → 성공 종료
```
