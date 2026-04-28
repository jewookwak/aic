# 채점 테스트 및 평가 가이드

이 문서는 AIC 채점 시스템을 테스트하는 재현 가능한 예제들을 제공합니다.
각 예제는 목표, 테스트하는 채점 카테고리, 예상 결과, 각 터미널에서 실행할 정확한 명령어를 나열합니다.

## 사전 조건

모든 터미널에서 ROS 2 워크스페이스와 Zenoh 미들웨어가 설정되어 있어야 합니다:

```bash
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_ROUTER_CHECK_ATTEMPTS=-1
export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true;transport/shared_memory/transport_optimization/pool_size=536870912'
```

워크스페이스 빌드 (아직 빌드하지 않은 경우):

```bash
cd ~/ws_aic
GZ_BUILD_FROM_SOURCE=1 colcon build \
  --cmake-args -DCMAKE_BUILD_TYPE=Release \
  --merge-install --symlink-install \
  --packages-ignore lerobot_robot_aic
```

## 채점 티어 참조표

| 티어 | 카테고리 | 범위 | 설명 |
|------|----------|-------|-------------|
| 1 | 모델 유효성 | 0~1 | 합격/불합격: 모델이 로드되고 기대에 부합하는지 사전 조건 검사 |
| 2 | 궤적 부드러움 | 0~5 | 팔 움직임의 부드러움; 저크에 반비례(높을수록 부드러움); 성공적인 삽입 또는 플러그가 포트 근처에 있을 때만 부여 |
| 2 | 태스크 소요 시간 | 0~10 | 빠른 완료에 대한 보상; 성공적인 삽입 또는 플러그가 포트 근처에 있을 때만 부여 |
| 2 | 궤적 효율성 | 0~5 | 더 짧은 엔드 이펙터 경로 길이에 대한 보상(높을수록 더 직접적); 성공적인 삽입 또는 플러그가 포트 근처에 있을 때만 부여 |
| 2 | 삽입 힘 | 0 ~ -12 | 1초 이상 지속된 20N 초과 힘에 대한 패널티 |
| 2 | 접촉 금지 구역 | 0 ~ -24 | 인클로저 또는 태스크 보드와의 충돌에 대한 패널티 |
| 3 | 케이블 삽입 | -10 또는 0~60 | 잘못된 포트 삽입 -10 패널티; 올바른 포트 삽입 60점; 부분 삽입 또는 근접 0~40점 |

결과는 엔진 사용 시 `$AIC_RESULTS_DIR/scoring.yaml`에 기록됩니다.
기본 디렉토리는 `~/aic_results`입니다. 각 엔진 실행은 이전 `scoring.yaml`을 **덮어씁니다**. 결과를 보존하려면 실행별로 `AIC_RESULTS_DIR`을 고유한 경로로 설정하세요.

---

## 예제 1: Tier 1 실패 — 모델 미실행

**목표:** `aic_model`을 실행하지 않고 엔진을 시작합니다. 엔진이 정책을 발견하기 위해 기다리다 타임아웃되어야 합니다.

**예상 결과:**
- 엔진이 각 트라이얼에 대해 타임아웃 또는 실패를 보고합니다.
- Tier 1이 모든 트라이얼에서 **실패**해야 합니다.
- Tier 2와 Tier 3도 유사한 방식으로 실패합니다.

### 터미널 0 — Zenoh 라우터

```bash
ros2 run rmw_zenoh_cpp rmw_zenohd
```

### 터미널 1 — 시뮬레이션 + 엔진 (모델 없음)

```bash
AIC_RESULTS_DIR=~/aic_results/no_model \
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  start_aic_engine:=true
```

---

## 예제 2: CheatCode 참조 솔루션

**목표:** CheatCode 정책을 전체 엔진 파이프라인으로 실행합니다. Tier 1(통과), Tier 2(부드러움, 소요 시간, 효율성, 힘), Tier 3(케이블 삽입)을 테스트합니다.

**예상 결과:**
- 모든 3번의 트라이얼이 완료됩니다.
- Tier 1이 모든 트라이얼에서 **통과**해야 합니다.
- Tier 2는 높은 부드러움 점수(최대 5), 성공한 트라이얼에서 태스크 소요 시간 보너스(최대 10), 힘 패널티 없음, 접촉 금지 구역 없음을 보여야 합니다.
- Tier 3는 모든 트라이얼에서 성공적인 케이블 삽입(60점)을 보고해야 합니다.

### 터미널 0 — Zenoh 라우터

```bash
ros2 run rmw_zenoh_cpp rmw_zenohd
```

### 터미널 1 — AIC 모델 (CheatCode)

```bash
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.CheatCode
```

### 터미널 2 — 시뮬레이션 + 엔진

```bash
AIC_RESULTS_DIR=~/aic_results/cheatcode \
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  ground_truth:=true \
  start_aic_engine:=true
```

---

## 예제 3: WaveArm 기준

**목표:** WaveArm 정책을 엔진으로 실행합니다. 팔이 흔들리지만 케이블을 삽입하지는 않습니다. Tier 1(통과)과 Tier 2(부드러움, 효율성)를 테스트합니다.

**예상 결과:**
- 모든 3번의 트라이얼이 완료됩니다.
- Tier 1이 모든 트라이얼에서 **통과**해야 합니다.
- Tier 2는 높은 부드러움 점수(부드러운 흔들기 동작), 태스크 소요 시간 보너스 없음(성공적인 삽입 없음), 힘 패널티 없음, 접촉 금지 구역 없음을 보여야 합니다.
- Tier 3는 모든 트라이얼에서 0점을 보고해야 합니다(팔은 흔들리지만 포트에 접근하지 않음).

### 터미널 0 — Zenoh 라우터

```bash
ros2 run rmw_zenoh_cpp rmw_zenohd
```

### 터미널 1 — AIC 모델 (WaveArm)

```bash
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.WaveArm
```

### 터미널 2 — 시뮬레이션 + 엔진

```bash
AIC_RESULTS_DIR=~/aic_results/wavearm \
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  start_aic_engine:=true
```

---

## 예제 4: 접촉 금지 구역 충돌

**목표:** `WallToucher` 정책을 엔진으로 실행합니다. 이 정책은 관절 공간 제어로 팔을 옆으로 뻗어 인클로저 벽 패널에 전완을 닿게 합니다. 접촉 금지 구역 패널티가 채점 출력에 나타나야 합니다.

**예상 결과:**
- 모든 3번의 트라이얼이 완료됩니다.
- Tier 1이 모든 트라이얼에서 **통과**해야 합니다.
- Tier 2는 로봇 링크(예: `forearm_link`)가 인클로저 벽과 충돌한 모든 트라이얼에서 접촉 금지 구역 패널티(-24)를 보여야 합니다.
- Tier 3는 모든 트라이얼에서 0점을 보고해야 합니다(삽입 없음, 플러그가 포트 근처에 없음).

> **참고 — 접촉 금지 구역:** "접촉 금지" 모델은 태스크 중 로봇이 접촉해서는 안 되는 표면입니다. `OffLimitContactsPlugin`은 세 가지 모델을 모니터링합니다:
>
> | 모델 | 포함 내용 |
> |-------|-----------------|
> | `enclosure` | 바닥, 모서리 기둥, 천장 (구조 프레임) |
> | `enclosure walls` | 작업 공간을 둘러싼 투명 아크릴 패널 |
> | `task_board` | 보드와 마운트된 모든 것 (NIC 카드 마운트, SC 포트 등) |
>
> 한쪽이 **로봇 링크**인 접촉만 패널티가 부여됩니다. 케이블은 별도의 Gazebo 모델이므로 패널티를 발생시키지 않습니다.

### 터미널 0 — Zenoh 라우터

```bash
ros2 run rmw_zenoh_cpp rmw_zenohd
```

### 터미널 1 — AIC 모델 (WallToucher)

```bash
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.WallToucher
```

### 터미널 2 — 시뮬레이션 + 엔진

```bash
AIC_RESULTS_DIR=~/aic_results/wall_toucher \
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  ground_truth:=true \
  start_aic_engine:=true
```

---

## 예제 5: 과도한 힘

**목표:** `WallPresser` 정책을 엔진으로 실행합니다. 이 정책은 관절 공간 제어로 높은 강성으로 인클로저 벽에 전완을 눌러 Tier 2 삽입 힘 패널티를 유발하는 지속적인 접촉력을 생성합니다.

**예상 결과:**
- 모든 3번의 트라이얼이 완료됩니다.
- Tier 1이 모든 트라이얼에서 **통과**해야 합니다.
- Tier 2는 모든 트라이얼에서 삽입 힘 패널티(-12)를 보여야 합니다. 벽 접촉의 부작용으로 접촉 금지 구역 패널티(-24)도 나타날 수 있습니다.
- Tier 3는 모든 트라이얼에서 0점을 보고해야 합니다(삽입 없음, 플러그가 포트 근처에 없음).

### 터미널 0 — Zenoh 라우터

```bash
ros2 run rmw_zenoh_cpp rmw_zenohd
```

### 터미널 1 — AIC 모델 (WallPresser)

```bash
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.WallPresser
```

### 터미널 2 — 시뮬레이션 + 엔진

```bash
AIC_RESULTS_DIR=~/aic_results/wall_presser \
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  ground_truth:=true \
  start_aic_engine:=true
```

---

## 예제 6: 부드러운 동작 — 낮은 저크

**목표:** `GentleGiant` 정책을 엔진으로 실행합니다. 이 정책은 낮은 강성과 높은 감쇠를 사용하여 두 관절 설정 사이를 천천히 이동하여 최소한의 저크를 생성합니다.

**예상 결과:**
- 모든 3번의 트라이얼이 완료됩니다.
- Tier 1이 모든 트라이얼에서 **통과**해야 합니다.
- Tier 2는 부드러움 점수 없음(플러그가 포트 근처에 없음), 태스크 소요 시간 보너스 없음(플러그가 포트 근처에 없음), 힘 패널티 없음, 접촉 금지 구역 없음을 보여야 합니다.
- Tier 3는 모든 트라이얼에서 0점을 보고해야 합니다(삽입 없음, 플러그가 포트 근처에 없음).

### 터미널 0 — Zenoh 라우터

```bash
ros2 run rmw_zenoh_cpp rmw_zenohd
```

### 터미널 1 — AIC 모델 (GentleGiant)

```bash
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.GentleGiant
```

### 터미널 2 — 시뮬레이션 + 엔진

```bash
AIC_RESULTS_DIR=~/aic_results/gentle_giant \
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  ground_truth:=true \
  start_aic_engine:=true
```

---

## 예제 7: 공격적인 동작 — 높은 저크

**목표:** `SpeedDemon` 정책을 엔진으로 실행합니다. 이 정책은 높은 강성과 낮은 감쇠를 사용하여 두 관절 설정 사이를 빠르게 이동하여 삽입 힘 패널티를 유발하는 공격적인 동작을 생성합니다.

**예상 결과:**
- 모든 3번의 트라이얼이 완료됩니다.
- Tier 1이 모든 트라이얼에서 **통과**해야 합니다.
- Tier 2는 부드러움 점수 없음(플러그가 포트 근처에 없음)과 모든 트라이얼에서 삽입 힘 패널티(-12)를 보여야 합니다. 낮은 감쇠로 인해 팔이 격렬하게 진동하여 F/T 센서에서 지속적인 힘이 발생합니다. 팔은 눈에 띄게 위치 사이를 급격하게 전환해야 합니다.
- Tier 3는 모든 트라이얼에서 0점을 보고해야 합니다(삽입 없음, 플러그가 포트 근처에 없음).

### 터미널 0 — Zenoh 라우터

```bash
ros2 run rmw_zenoh_cpp rmw_zenohd
```

### 터미널 1 — AIC 모델 (SpeedDemon)

```bash
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.SpeedDemon
```

### 터미널 2 — 시뮬레이션 + 엔진

```bash
AIC_RESULTS_DIR=~/aic_results/speed_demon \
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  ground_truth:=true \
  start_aic_engine:=true
```

---
