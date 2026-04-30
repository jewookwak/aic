# 예제 정책

이 패키지는 케이블 삽입 태스크에 대한 다양한 접근 방식을 보여주는 기준 정책 구현들을 포함합니다. 이 예제들은 참조 구현 및 자신만의 정책 개발을 위한 시작점으로 활용할 수 있습니다.

> [!NOTE]
> **사전 조건:** 이 정책들을 실행하기 전에 평가 환경이 실행 중인지 확인하세요. 설정 지침은 [시작 가이드](../docs/getting_started_ko.md)를 참조하세요.
>
> **명령어 형식:**
> - **컨테이너 워크플로우** (권장) 사용 시: `distrobox enter -r aic_eval -- /entrypoint.sh [파라미터]`로 실행
> - **소스 빌드** 사용 시: `ros2 launch aic_bringup aic_gz_bringup.launch.py [파라미터]`로 실행
> - 정책 실행: `pixi run ros2 run` (Pixi 워크스페이스) 또는 `ros2 run` (네이티브 ROS 2)

---

## 사용 가능한 정책

### 1. WaveArm — 최소 예제

![Wave Arm Policy](../../media/wave_arm_policy.gif)

`insert_cable()` 콜백을 구현하고 팔에 모션 명령을 발행하는 방법을 보여주는 최소 예제입니다. 이 정책은 태스크를 해결하려는 시도 없이 단순히 로봇 팔을 앞뒤로 흔드는 동작만 수행합니다.

**목적:** 기본 Policy API 구조를 시연합니다.

**평가 환경 실행:**
```bash
/entrypoint.sh ground_truth:=false start_aic_engine:=true
```

**정책 실행:**
```bash
pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.WaveArm
```

**소스:** [`WaveArm.py`](./aic_example_policies/ros/WaveArm.py)

---

### 2. CheatCode — Ground Truth 정책

![Cheat Code Policy](../../media/cheat_code_policy.gif)

실행 시 `ground_truth:=true`로 설정하면 시뮬레이션이 제공하는 TF 변환 트리를 사용하는 "치트" 솔루션입니다. 이 정책은 플러그와 포트의 포즈를 사용하여 `aic_controller`에 전송할 목표 포즈를 계산합니다.

**목적:** 훈련 및 디버깅에 유용합니다. Ground truth 데이터는 공식 평가 중에는 사용 불가합니다.

**시뮬레이션 실행 *ground truth 포함*:**
```bash
/entrypoint.sh ground_truth:=true start_aic_engine:=true
```

**정책 실행:**
```bash
pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.CheatCode
```

**소스:** [`CheatCode.py`](./aic_example_policies/ros/CheatCode.py)

---

### 3. RunACT — ACT 정책

![Run ACT Policy](../../media/run_act_policy.gif)

[HuggingFace](https://huggingface.co/grkw/aic_act_policy)에서 사용 가능한 [LeRobot ACT](https://huggingface.co/docs/lerobot/en/act)(Action Chunking with Transformers) 정책의 개념 증명 구현입니다. 이 정책은 [`lerobot_robot_aic`](../aic_utils/lerobot_robot_aic/README.md#recording-training-data)에 설명된 대로 `lerobot-record`를 사용하여 수집된 소규모 데이터셋으로, NVIDIA RTX A5000 머신에서 기본 파라미터로 `lerobot-train`을 사용하여 훈련되었습니다.

하드웨어 설정에 맞게 `lerobot`을 실행하기 위해 `pixi.toml`을 수정해야 할 수 있습니다. [문제 해결](../docs/troubleshooting_ko.md#pixi에-잠긴-pytorch-버전이-nvidia-rtx-50xx-카드를-지원하지-않는-경우)을 참조하세요.

**목적:** 케이블 삽입 태스크를 위한 훈련된 신경망 정책 통합을 시연합니다.

**평가 환경 실행:**
```bash
/entrypoint.sh ground_truth:=false start_aic_engine:=true
```

**정책 실행:**
```bash
pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.RunACT
```

**소스:** [`RunACT.py`](./aic_example_policies/ros/RunACT.py)

---

## 채점 예제

각 정책의 예상 채점 결과와 재현 가능한 테스트 명령어는 [채점 테스트 및 평가 가이드](../docs/scoring_tests_ko.md)를 참조하세요.
