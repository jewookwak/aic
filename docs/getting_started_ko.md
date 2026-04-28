# 시작 가이드

AI for Industry Challenge에 오신 것을 환영합니다! 이 가이드를 따라 툴킷 구조를 익히고, 환경을 준비하고, 솔루션 개발 전에 빠른 시작 예제를 실행하여 설정을 확인하세요.

> [!NOTE]
> **ROS 2 배포판:** 모든 제출물의 공식 평가는 **ROS 2 Kilted Kaiju**를 사용합니다. 다른 배포판(예: Humble, Jazzy)으로 개발하거나 테스트하는 경우, 호환성 확보는 전적으로 참가자의 책임입니다. **배포판 간 통신은 보장되지 않으며 공식 지원되지 않습니다.** ROS 2를 처음 접하는 분들은 [공식 ROS 2 튜토리얼](https://docs.ros.org/en/kilted/Tutorials.html)을 완료하시길 강력히 권장합니다.

## 아키텍처 개요

대회는 두 컴포넌트 아키텍처를 사용합니다:

1. **평가 컴포넌트** (제공됨) — 시뮬레이션, 로봇, 센서, 채점 시스템 실행
2. **참가자 모델** (직접 구현) — 센서 데이터를 처리하고 로봇에 명령을 내리는 ROS 2 노드

**두 컴포넌트의 소스 코드는 이 툴킷에 모두 포함되어 있습니다.** 대회 기간 동안 평가 컴포넌트는 변경되지 않으므로, 편의를 위해 재사용 가능한 Docker 이미지(`aic_eval`)를 제공합니다 — 이것이 **권장 워크플로우**입니다. 소스에서 직접 빌드하려는 고급 사용자는 [소스에서 빌드하기](./build_eval_ko.md) 가이드를 따르세요.

아키텍처, 패키지, 인터페이스에 대한 자세한 설명은 README의 [툴킷 아키텍처](../README_ko.md#툴킷-아키텍처) 섹션을 참조하세요.

---

## 요구 사양

**최소 컴퓨팅 사양:**

- **OS:** Ubuntu 24.04
- **CPU:** 4~8코어
- **RAM:** 32GB 이상
- **GPU:** NVIDIA RTX 2070 이상 또는 동급
- **VRAM:** 8GB 이상

> [!NOTE]
> GPU가 없는 시스템에서도 대회를 실행할 수 있지만 성능이 크게 저하됩니다. CPU 전용 시스템 최적화 팁은 [문제 해결](./troubleshooting_ko.md#gpu-없는-경우)을 참조하세요.

**클라우드 평가 인스턴스:**

모든 참가자 제출물은 동일한 인스턴스 유형에서 평가됩니다:

- **vCPU:** 64코어
- **RAM:** 256 GiB
- **GPU:** NVIDIA L4 Tensor Core 1개
- **VRAM:** 24 GiB

---

## 설정

먼저 다음 도구들을 설치하세요:
* [Docker](#docker-설정) (필수)
* [Distrobox](#distrobox-설정) (필수)
* [Pixi](#pixi-설정) (필수)
* [NVIDIA Container Toolkit](#nvidia-container-toolkit-설정-선택) (선택 - NVIDIA GPU 사용자)

### Docker 설정

1. 플랫폼에 맞는 [Docker Engine](https://docs.docker.com/engine/install/)을 설치합니다.
2. root가 아닌 사용자로 Docker를 관리하기 위한 [Linux 설치 후 단계](https://docs.docker.com/engine/install/linux-postinstall/)를 완료합니다.

### NVIDIA Container Toolkit 설정 (선택)

> [!NOTE]
> NVIDIA GPU가 있고 GPU 가속을 사용하려는 경우에만 필요합니다.

1. [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)을 설치하여 Docker Engine이 NVIDIA GPU에 접근할 수 있도록 합니다.

2. 설치 후 Docker가 NVIDIA 런타임을 사용하도록 설정합니다:
    ```bash
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
    ```

### Distrobox 설정

`aic_eval` 컨테이너를 호스트 시스템과 긴밀하게 통합하기 위해 [Distrobox](https://distrobox.it/)를 사용합니다. 패키지 매니저를 통해 Distrobox를 설치하는 것을 권장합니다.

Ubuntu의 경우:
```bash
sudo apt install distrobox
```

다른 배포판은 [대체 설치 방법](https://distrobox.it/#alternative-methods)을 참조하세요.

### Pixi 설정

ROS 2를 포함한 패키지 및 의존성 관리를 위해 [Pixi](https://pixi.prefix.dev/latest/)를 사용합니다.

Ubuntu의 경우:
```bash
curl -fsSL https://pixi.sh/install.sh | sh
# 설치 후 터미널을 재시작하세요
```

다른 운영 체제는 [대체 설치 방법](https://pixi.prefix.dev/latest/installation/#alternative-installation-methods)을 참조하세요.

> [!IMPORTANT]
> Pixi 환경 내 패키지 변경사항은 자동으로 추적되지 않습니다. 업데이트를 적용하려면 `pixi reinstall <package_name>`을 실행해야 합니다.

## 빠른 시작

이 섹션은 다음 과정을 안내합니다:
1. **워크스페이스 설정** — 대회 저장소를 복제하고 Pixi로 의존성 설치
2. **평가 컴포넌트 실행** — 시뮬레이션 환경, 로봇, 센서, 채점 시스템을 시작하는 `aic_eval` 컨테이너 실행
3. **예제 정책 실행** — 제공된 예제 정책을 로컬 워크스페이스에서 평가 컨테이너에 대해 실행

이 단계들을 완료한 후 제출을 준비하려면 [제출 가이드라인](./submission_ko.md)을 참조하세요.

---
### 1단계: 워크스페이스 설정

```bash
# 저장소 복제
mkdir -p ~/ws_aic/src
cd ~/ws_aic/src
git clone https://github.com/intrinsic-dev/aic

# 의존성 설치 및 빌드
cd ~/ws_aic/src/aic
pixi install
```

**다음과 같이 표시되어야 합니다:**
- Pixi가 ROS 2 패키지 및 의존성을 다운로드하고 설치
- 완료 시 성공 메시지
- 워크스페이스에 모든 의존성이 포함된 `.pixi` 디렉토리 생성

---
### 2단계: 평가 컨테이너 시작

```bash
# distrobox가 Docker를 컨테이너 매니저로 사용하도록 설정
export DBX_CONTAINER_MANAGER=docker

# eval 컨테이너 생성 및 진입
docker pull ghcr.io/intrinsic-dev/aic/aic_eval:latest
# NVIDIA GPU가 없는 경우 --nvidia 플래그를 제거하세요
distrobox create -r --nvidia -i ghcr.io/intrinsic-dev/aic/aic_eval:latest aic_eval
distrobox enter -r aic_eval

# 컨테이너 내부에서 환경 시작
/entrypoint.sh ground_truth:=false start_aic_engine:=true
```

[`entrypoint.sh`](../docker/aic_eval/Dockerfile) 스크립트는 Zenoh 라우터와 `aic_engine`이 포함된 [`aic_gz_bringup.launch.py`](../aic_bringup/README.md#1-aic_gz_bringuplaunchpy) 런치 파일을 실행합니다.

> [!NOTE]
> 평가 컨테이너는 기본적으로 사전 빌드된 워크스페이스이며, `/entrypoint.sh`만이 유일한 사용 방법이 아닙니다. 컨테이너에 진입하여 워크스페이스를 소스(`source /ws_aic/install/setup.bash`)하고 패키지 README 및 문서에 설명된 명령을 실행할 수 있습니다.

**다음과 같이 표시되어야 합니다:**
- 두 창이 열림: **Gazebo** (시뮬레이션) 및 **RViz** (시각화)
- Gazebo에서: 테이블에 마운트된 Universal Robots UR5e 매니퓰레이터가 있는 작업 셀
- 터미널에서: AIC 엔진이 초기화되어 `aic_model` 노드를 기다리는 로그 메시지 (`No node with name 'aic_model' found. Retrying...`)
- 아직 로봇이 움직이지 않음 (정책이 연결될 때까지 대기)

![평가 환경](../../media/eval_environment_waiting.png)

시뮬레이션 환경에 대한 자세한 내용은 [씬 설명](./scene_description_ko.md)을 참조하세요.

> [!Note]
> `docker pull` 명령이 실패하면 [ghcr.io에 로그인](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-with-a-personal-access-token-classic)이 필요할 수 있습니다.

> [!NOTE]
> 평가 컨테이너의 `aic_engine` 노드는 30초 내에 `aic_model` 노드를 찾아야 하며, 그 후에는 타임아웃됩니다. 평가 컨테이너가 Zenoh 라우터를 시작하므로, 이 단계(`/entrypoint.sh`)는 3단계에서 `aic_model` 노드를 시작하기 **전에** 실행해야 합니다.

---

### 3단계: 예제 정책 실행

시뮬레이션 환경이 실행 중인 상태(2단계)에서 다음 정책을 실행하세요:
```bash
cd ~/ws_aic/src/aic
pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.WaveArm
```

> [!NOTE]
> `pixi run`은 자체 환경을 생성하고 그 안에서 `aic_model`을 실행하므로, Docker나 distrobox 외부에서 실행할 수 있습니다. 컨테이너 외부에서 실행하는 것이 일반적으로 더 쉽고 빠릅니다.

`aic_model` 노드가 시작되면 AIC 엔진이 Gazebo 창에 태스크 보드와 그리퍼에 연결된 케이블을 스폰합니다. 그런 다음 eval 컨테이너 터미널이 세 번의 연속 트라이얼을 추적하고 점수를 표시합니다.

**참고:** `WaveArm` 정책은 로봇 팔을 앞뒤로 흔드는 더미 예제입니다. 케이블 삽입 태스크를 해결하려는 시도는 없습니다. 이 예제의 목적은 [`aic_engine`](../aic_engine/README.md)이 [샘플 설정](../aic_engine/config/sample_config.yaml)을 기반으로 트라이얼을 오케스트레이션하고 성과(예상대로 좋지 않음)에 따라 정책을 채점하는 방식을 시연하는 것입니다.

**다음과 같이 표시되어야 합니다:**
- **Gazebo에서**: 태스크 보드와 그리퍼에 연결된 케이블이 시뮬레이션에 나타남
- **로봇**: 팔이 흔들리는 동작을 수행
- **eval 컨테이너 터미널에서**:
  - 트라이얼 진행 상황 로그 메시지 (Trial 1/3, Trial 2/3, Trial 3/3)
  - 각 트라이얼 후 채점 정보
  - 모든 트라이얼의 총점이 포함된 최종 요약
- 세 번의 연속 트라이얼이 자동으로 수행됨
- **결과 저장 위치**: `$HOME/aic_results/` (또는 `$AIC_RESULTS_DIR`이 설정된 경우)

![WaveArm 정책](../../media/wave_arm_policy.gif)

로봇이 움직이지 않거나 예상된 동작이 보이지 않으면 [문제 해결](./troubleshooting_ko.md) 섹션을 확인하세요.

더 많은 예제 정책과 예상 채점 결과는 [채점 테스트 및 평가 가이드](./scoring_tests_ko.md)를 참조하세요.

---

## 🎉 축하합니다!

빠른 시작 가이드를 성공적으로 완료했습니다! 이제 다음이 준비되었습니다:
- ✅ Gazebo와 RViz가 실행 중인 평가 환경
- ✅ 모든 의존성이 설치된 로컬 Pixi 워크스페이스
- ✅ AIC 엔진이 트라이얼을 오케스트레이션하는 방식을 이해하는 예제 정책 실행 경험

**다음 단계:** 솔루션을 제출할 준비가 되면 참가자 워크스페이스를 컨테이너화해야 합니다. 정책 패키징 및 제출에 대한 자세한 지침은 [제출 가이드라인](./submission_ko.md)을 참조하세요.

---

## 다음 단계

환경이 설정되었으면, 다른 [기준 솔루션](../aic_example_policies/README.md)으로 동일한 평가 컨테이너를 실행해보세요.
그런 다음 [툴킷 가이드](../README_ko.md#툴킷-가이드)의 **💻 정책 개발하기** 섹션을 진행하세요.
