# 소스에서 평가 컴포넌트 빌드하기

이 가이드는 제공된 Docker 컨테이너 대신 Ubuntu 24.04에서 로컬로 평가 컴포넌트를 빌드하려는 고급 사용자를 위한 것입니다.

> [!NOTE]
> **대부분의 사용자에게는 [시작 가이드](./getting_started_ko.md)에서 설명한 대로 사전 빌드된 `aic_eval` Docker 컨테이너를 사용하는 것을 권장합니다.** 컨테이너는 공식 평가 설정과 일치하는 일관되고 테스트된 환경을 제공합니다.

## 소스에서 빌드하는 이유?

로컬 빌드가 유용한 경우:
- 평가 컴포넌트를 수정하거나 디버깅하려는 경우
- 컨테이너 없이 네이티브 개발을 선호하는 경우
- 호스트 시스템의 다른 도구와 통합이 필요한 경우

> [!IMPORTANT]
> 평가 컴포넌트를 변경해도 공식 평가에는 **반영되지 않습니다**. 컨테이너로 제출된 참가자 모델만 평가됩니다.

---

## 사전 요구사항

| 의존성 | 릴리스 / 배포판 |
| ---------- | ------- |
| 운영 체제 | [Ubuntu 24.04 (Noble Numbat)](https://releases.ubuntu.com/noble/) |
| ROS 2 | [ROS 2 Kilted Kaiju](https://docs.ros.org/en/kilted/Installation/Ubuntu-Install-Debs.html) |

---

## 설정 지침

시스템에 현재 ROS 2 Kilted 및 Gazebo 바이너리가 설치되어 있다면, 소스 설치를 시작하기 전에 제거해야 합니다. 사전 설치된 바이너리가 있는 상태에서 특정 저장소를 소스에서 빌드하면 환경 충돌이 발생할 수 있습니다.

관련 바이너리를 제거하려면 다음 명령을 실행하세요:

```bash
sudo apt purge ros-kilted-ros2-control* ros-kilted-control* ros-kilted-kinematics* ros-kilted-joint-state-publisher ros-kilted-realtime-tools ros-kilted-gz*
```

### 1. Gazebo 저장소 추가

```bash
sudo curl https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
sudo apt-get update
```

### 2. 워크스페이스 복제 및 빌드

```bash
# 워크스페이스 생성
sudo apt update && sudo apt upgrade -y
mkdir -p ~/ws_aic/src
cd ~/ws_aic/src

# 저장소 복제
git clone https://github.com/intrinsic-dev/aic

# 의존성 가져오기
vcs import . < aic/aic.repos --recursive

# Gazebo 의존성 설치
sudo apt -y install $(sort -u $(find . -iname 'packages-'`lsb_release -cs`'.apt' -o -iname 'packages.apt' | grep -v '/\.git/') | sed '/gz\|sdf/d' | tr '\n' ' ')

# ROS 2 의존성 설치
cd ~/ws_aic
sudo rosdep init  # rosdep을 처음 실행하는 경우에만
rosdep install --from-paths src --ignore-src --rosdistro kilted -yr --skip-keys "gz-cmake3 DART libogre-dev libogre-next-2.3-dev rosetta"

# rmw_zenoh_cpp 미들웨어 및 추가 의존성 설치
sudo apt install -y ros-kilted-rmw-zenoh-cpp python3-pynput

# 워크스페이스 빌드
source /opt/ros/kilted/setup.bash
GZ_BUILD_FROM_SOURCE=1 colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release --merge-install --symlink-install --packages-ignore lerobot_robot_aic
```

### 3. 환경 설정

다음 환경 변수를 셸 설정에 추가하세요(예: `~/.bashrc`):

```bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true;transport/shared_memory/transport_optimization/pool_size=536870912'
```

그런 다음 셸 설정을 다시 로드하세요:
```bash
source ~/.bashrc
```

> [!NOTE]
> 이 대회는 ROS 2 미들웨어로 [rmw_zenoh](https://github.com/ros2/rmw_zenoh)를 사용합니다. 모든 터미널에서 `RMW_IMPLEMENTATION` 환경 변수를 `rmw_zenoh_cpp`로 설정해야 합니다.

---

## 시스템 실행

세 개의 터미널이 필요합니다. 각 터미널에서 워크스페이스를 소스하세요:

```bash
source ~/ws_aic/install/setup.bash
```

> [!TIP]
> 3단계에서 `~/.bashrc`에 환경 변수를 추가하지 않은 경우, 각 터미널에서 내보내야 합니다:
> ```bash
> export RMW_IMPLEMENTATION=rmw_zenoh_cpp
> export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true;transport/shared_memory/transport_optimization/pool_size=536870912'
> ```

그런 다음 각 터미널에서 다음 명령을 실행하세요:

### 터미널 1 — Zenoh 라우터 시작

```bash
ros2 run rmw_zenoh_cpp rmw_zenohd
```

### 터미널 2 — 평가 환경 실행

```bash
ros2 launch aic_bringup aic_gz_bringup.launch.py ground_truth:=false start_aic_engine:=true
```

이는 로봇 팔과 엔드 이펙터 툴링이 있는 Gazebo를 실행합니다. `TaskBoard`와 `Cable`은 모델이 준비되면 `aic_engine`에 의해 스폰됩니다.

### 터미널 3 — 정책 실행

```bash
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.WaveArm
```

`aic_example_policies.ros.WaveArm`을 정책 구현으로 교체하세요.

---

## 다음 단계

평가 환경이 로컬에서 실행 중이면:

- [씬 설명](./scene_description_ko.md)을 살펴보고 환경을 커스터마이징하는 방법을 익히세요.
- [정책 통합 가이드](./policy_ko.md)를 읽어 정책 노드를 만드는 방법을 이해하세요.
- 참조 구현을 위해 [`aic_example_policies/`](../aic_example_policies/)를 확인하세요.
- [AIC 인터페이스](./aic_interfaces_ko.md)를 검토하여 사용 가능한 센서와 액추에이터를 이해하세요.
- [AIC 컨트롤러](./aic_controller_ko.md)를 참조하여 모션 명령에 대해 배우세요.
- [채점 테스트 예제](./scoring_tests_ko.md)를 실행하여 각 기준 정책의 예상 결과를 확인하세요.

---

## 문제 해결

문제가 발생하면:

1. **빌드 오류**: 모든 의존성이 올바르게 설치되어 있는지 확인하세요.
2. **런타임 오류**: 모든 터미널에서 환경 변수가 설정되어 있는지 확인하세요.
3. **ROS 2 통신**: Zenoh 라우터가 실행 중이고 미들웨어가 설정되어 있는지 확인하세요.

더 많은 도움이 필요하면 [문제 해결](./troubleshooting_ko.md)을 참조하거나 [GitHub](https://github.com/intrinsic-dev/aic/issues)에 이슈를 보고하세요.
