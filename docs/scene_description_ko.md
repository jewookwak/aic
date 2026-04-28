# 씬 설명

![](../../media/aic_scene.png)

> [!NOTE]
> 이 가이드는 [시작 가이드](./getting_started_ko.md)를 완료하고 평가 환경이 실행 중인 상태를 전제로 합니다.

시뮬레이션 환경은 [`aic_description`](./../aic_description) 패키지에 정의되어 있으며, 케이블 삽입 태스크에 필요한 로봇, 태스크 보드, 다양한 객체로 구성됩니다. 씬의 모든 3D 모델은 [`aic_assets`](./../aic_assets) 패키지에 저장되어 있습니다.

## 씬 구성 요소

### 로봇

대회에서는 다음 하드웨어가 장착된 **Universal Robots UR5e** 로봇 팔을 사용합니다:
* **그리퍼:** **Robotiq Hand-E**
* **힘-토크 센서:** **ATI AXIA80-M20**
* **카메라:** **Basler acA2440-20gc** + **Edmunds lens 58-000** (해상도: 1152x1024, 프레임 레이트: 20 FPS)

* **설정:** 로봇의 물리적 특성과 설정은 [`ur_gz.urdf.xacro`](../aic_description/urdf/ur_gz.urdf.xacro) 파일에 정의되어 있습니다.
* **제어:** 로봇은 `aic_controller`로 조작됩니다. 자세한 인터페이스 및 사용 지침은 [AIC 컨트롤러 문서](./aic_controller_ko.md)를 참조하세요.

### 태스크 보드

대회의 핵심 구성 요소는 [`task_board.urdf.xacro`](../aic_description/urdf/task_board.urdf.xacro)에 정의된 태스크 보드입니다. 이 모듈식 플랫폼에는 태스크에 필요한 다양한 마운트, 커넥터, 모듈이 장착됩니다.

**핵심 구성 요소:**
* **커넥터:** SC 및 SFP 타입을 포함한 표준 광섬유 커넥터.
* **NIC 카드:** 네트워크 인터페이스 카드.
* **마운트:** 커넥터와 모듈을 고정하는 전용 고정 장치.

자세한 사양은 [태스크 보드 설명](./task_board_description_ko.md)을 참조하세요.

### 환경

조명, 물리 속성, 일반 세계 설정을 포함한 전역 시뮬레이션 설정은 [`aic.sdf`](../aic_description/world/aic.sdf) 파일에 정의되어 있습니다.

---

## 환경 탐색

기본 환경이 실행 중이면 대회를 더 잘 이해하고 다양한 훈련 시나리오를 만들기 위해 다양한 설정을 탐색할 수 있습니다.

> [!TIP]
> [Gazebo에서 씬을 탐색하는 방법](https://gazebosim.org/docs/latest/gui/#the-scene)을 참조하세요.

### 환경 커스터마이징

런치 명령에 파라미터를 전달하여 시뮬레이션 환경을 커스터마이징할 수 있습니다. **eval 컨테이너**든 **소스 빌드**든 파라미터는 동일합니다.

**eval 컨테이너에서 (distrobox 경유):**
```bash
/entrypoint.sh [파라미터]
```

**소스 빌드에서:**
```bash
ros2 launch aic_bringup aic_gz_bringup.launch.py [파라미터]
```

> [!TIP]
> 현재 터미널이 eval 컨테이너 내부에 있는지 확인하려면:
> ```bash
> echo $CONTAINER_ID  # 출력: aic_eval
> ```

### 예제: 커스텀 태스크 보드 설정

다양한 구성 요소를 포함한 태스크 보드를 스폰하는 완전한 예제:

```bash
spawn_task_board:=true \
    task_board_x:=0.3 task_board_y:=-0.1 task_board_z:=1.2 \
    task_board_roll:=0.0 task_board_pitch:=0.0 task_board_yaw:=0.785 \
    sfp_mount_rail_0_present:=true sfp_mount_rail_0_translation:=-0.08 \
    sc_mount_rail_0_present:=true sc_mount_rail_0_translation:=-0.09 \
    nic_card_mount_0_present:=true nic_card_mount_0_translation:=0.005 \
    sc_port_0_present:=true sc_port_0_translation:=-0.04 \
    spawn_cable:=true cable_type:=sfp_sc_cable attach_cable_to_gripper:=true \
    ground_truth:=true start_aic_engine:=false
```

**탐색을 위한 주요 파라미터:**
- `ground_truth:=true` — 개발 중 디버깅을 쉽게 하기 위한 ground truth TF 프레임 활성화
- `start_aic_engine:=false` — 자동 트라이얼 오케스트레이션 비활성화하여 자유롭게 탐색 가능
- `spawn_task_board:=true` — 즉시 태스크 보드 스폰
- `spawn_cable:=true` — 씬에 케이블 스폰
- `attach_cable_to_gripper:=true` — 그리퍼에 케이블 부착
- `cable_type:=sfp_sc_cable` — 케이블 타입 (옵션: `sfp_sc_cable`, `sfp_sc_cable_reversed`)

설정 가능한 파라미터의 전체 목록은 [aic_bringup README](../aic_bringup/README.md)를 참조하세요.

### 훈련 시나리오 만들기

**다양한 훈련 환경 생성:** 파라미터를 변경하여 다양한 시나리오를 만드세요:

1. **다양한 설정으로 실행**하여 무작위 시나리오 생성
2. **스폰 후 전체 세계 상태가 자동으로 `/tmp/aic.sdf`에 저장됨**
3. **파일을 복사하여 여러 시나리오 보존:**
   ```bash
   cp /tmp/aic.sdf ~/training_scenarios/scenario_001.sdf
   ```
4. **다른 시뮬레이터로 가져오기** (IsaacLab, MuJoCo 등에서 훈련용)

**예제 워크플로우:**
```bash
# 시나리오 1: 슬롯 2의 NIC 카드
/entrypoint.sh spawn_task_board:=true nic_card_mount_2_present:=true \
    spawn_cable:=true cable_type:=sfp_sc_cable ground_truth:=true start_aic_engine:=false
cp /tmp/aic.sdf ~/training_scenarios/nic_slot_2.sdf

# 시나리오 2: 다른 포즈로 오른쪽 레일의 SC 커넥터
/entrypoint.sh spawn_task_board:=true task_board_yaw:=1.57 \
    sc_mount_rail_1_present:=true spawn_cable:=true ground_truth:=true start_aic_engine:=false
cp /tmp/aic.sdf ~/training_scenarios/sc_right_rotated.sdf
```

### 프로그래밍 방식 엔티티 스폰

태스크 보드와 케이블을 스폰하거나 재스폰해야 하는 훈련 워크플로우의 경우, `/expand_xacro` 서비스를 사용하면 eval 환경의 파일 시스템에 직접 접근하지 않고도 모델 측 코드에서 xacro 템플릿을 확장할 수 있습니다.
다음 런치 파일은 표준 `aic_bringup` Gazebo 스택과 훈련 유틸리티를 포함합니다:

```bash
ros2 launch aic_training_utils aic_training_gz_bringup.launch.py

# 태스크 보드 스폰
ros2 service call /expand_xacro aic_training_interfaces/srv/ExpandXacro \
  "{package_name: 'aic_description', relative_path: 'urdf/task_board.urdf.xacro', \
    xacro_arguments: ['ground_truth:=true', 'nic_card_mount_0_present:=true']}"
```

반환된 XML은 `/gz_server/spawn_entity`에 전달하여 임의의 포즈로 엔티티를 스폰할 수 있습니다. `/gz_server/delete_entity`와 결합하면 훈련 코드에서 에피소드별 씬 무작위화(태스크 보드 포즈, 레일 위치, 케이블 타입 변경 등)를 가능하게 합니다.

eval 컨테이너 내부에서는 `distrobox enter`로 시작할 수 있습니다:
```bash
distrobox enter aic_eval -- bash -lc '
  source /ws_aic/install/setup.bash &&
  ros2 launch aic_training_utils aic_training_gz_bringup.launch.py \
    spawn_task_board:=true \
    spawn_cable:=true \
    nic_card_mount_2_present:=true
'
```

### 원격 조작

관절 공간 또는 카르테시안 공간에서 **로봇을 원격 조작**하여:
- 작업 공간 탐색
- 케이블 삽입 수동 테스트
- 로봇의 도달 범위와 한계 이해
- 케이블 부착 여부에 따른 연습

원격 조작 전에 대회에서 사용되는 컨트롤러를 이해하기 위해 [AIC 컨트롤러 가이드](./aic_controller_ko.md)를 읽어보시길 권장합니다.

자세한 지침은 [로봇 원격 조작 가이드](../aic_utils/aic_teleoperation/README.md)를 참조하세요.

훈련 데이터 수집을 위해 원격 조작을 사용할 때는 각 훈련 에피소드 시작 시 힘/토크 센서를 영점 조정하세요. [훈련 전 영점 조정](#훈련-전-영점-조정)을 참조하세요.

> [!TIP]
> 로봇이 물체 근처에서 움직이지 않는 것 같다면, 실제로 접촉하지 않더라도 충돌 상태일 수 있습니다. 물체의 충돌 메시를 보려면 마우스 오른쪽 버튼을 클릭하고 `View >`를 클릭한 후 `Collisions`를 선택하세요.

---

## AI 훈련을 위한 세계 상태 내보내기

시뮬레이션에는 모든 엔티티(로봇, 태스크 보드, 케이블)가 스폰된 후 완전한 세계 상태를 자동으로 내보내는 세계 플러그인이 포함되어 있습니다. 이 기능은 AI 정책 훈련과 크로스 플랫폼 시뮬레이션 워크플로우에 특히 유용합니다.

**주요 이점:**
- **재현 가능한 시나리오:** 일관된 훈련 환경을 위해 런치 파라미터로 생성된 무작위 설정을 캡처합니다.
- **크로스 플랫폼 호환성:** 내보낸 SDF 파일을 IsaacLab이나 MuJoCo 같은 다른 시뮬레이터로 가져옵니다.
- **훈련 데이터 생성:** 런치 파라미터를 변경하고 각 설정을 내보내어 다양한 훈련 시나리오를 만듭니다.

**내보내기 세부사항:**
- **기본 위치:** `/tmp/aic.sdf`
- **플러그인 설정:** [`aic.sdf`](../aic_description/world/aic.sdf)에 파라미터와 함께 정의됨:
  - `<save_world_path>`: 세계 파일이 저장되는 경로 (기본값: `/tmp/aic.sdf`)
  - `<save_world_delay_s>`: 내보내기 전 시뮬레이션 시간(초) 지연 (기본값: `0.0`)

> [!NOTE]
> **MuJoCo 통합:** AIC 환경은 MuJoCo에서 네이티브로 시나리오 내보내기 및 정책 훈련을 지원합니다. 내보낸 시나리오는 MJCF 형식으로 변환하여 Gazebo에서 사용하는 동일한 ROS 2 제어 인터페이스로 실행할 수 있습니다. 시뮬레이션 설정, Gazebo 세계 변환, MuJoCo에서의 `ros2_control` 사용에 대한 자세한 지침은 [MuJoCo 통합 가이드](../aic_utils/aic_mujoco/README.md)를 참조하세요.

> [!NOTE]
> **Isaac Lab 통합:** AIC 환경은 데이터 수집 및 훈련을 위해 NVIDIA의 Isaac Lab에서도 로드할 수 있습니다. 자세한 내용은 [Isaac Lab 통합 가이드](../aic_utils/aic_isaac/README.md)를 참조하세요.

---

## 훈련 전 영점 조정

각 훈련 에피소드 시작 시(즉, 원격 조작 전 및 환경에 케이블 스폰 전)에 다음 서비스 호출을 사용하여 힘/토크 센서(F/T 센서)를 영점 조정하세요:
```bash
ros2 service call /aic_controller/tare_force_torque_sensor std_srvs/srv/Trigger
```

---

## 다음 단계

씬을 이해했으니:

- **정책 개발:** [정책 통합 가이드](./policy_ko.md) 참조
- **인터페이스 이해:** [AIC 인터페이스](./aic_interfaces_ko.md) 검토
- **채점 학습:** [채점](./scoring_ko.md) 읽기
- **예제 정책 탐색:** [`aic_example_policies/`](../aic_example_policies/) 확인
