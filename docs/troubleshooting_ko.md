# 문제 해결

## Gazebo에서 낮은 실시간 계수

시뮬레이션은 **1.0 RTF(100% 실시간 계수)**로 실행되도록 설정되어 있으며, 시뮬레이션 시간이 실제 시계 시간과 일치해야 합니다. RTF가 낮은 경우 다음 섹션이 문제 진단 및 해결에 도움이 될 수 있습니다.

### Gazebo가 전용 GPU를 사용하지 않는 경우

머신에 두 개의 GPU(또는 내장 GPU가 있는 CPU)가 있는 경우, OpenGL이 렌더링에 *내장* GPU를 사용하여 RTF가 매우 낮아질 수 있습니다. 이를 해결하려면 수동으로 *독립* GPU를 사용하도록 강제해야 할 수 있습니다.

OpenGL이 독립 GPU를 사용하고 있는지 확인하려면 `glxinfo -B`를 실행하세요. 출력에는 독립 GPU의 세부 정보가 표시되어야 합니다. 또한 `nvidia-smi`를 실행하여 GPU별 프로세스를 확인할 수 있습니다. AIC 시뮬이 활성화되면 프로세스 목록에 `gz sim`이 나타나야 합니다.

잘못된 GPU가 선택된 경우 `sudo prime-select nvidia`를 실행하세요.
**참고**: 변경 사항이 적용되려면 로그아웃하고 다시 로그인해야 합니다. 그런 다음 `glxinfo -B`를 다시 실행하여 독립 GPU가 활성화되었는지 확인하세요.

[듀얼 Intel 및 Nvidia GPU 시스템 문제](https://gazebosim.org/docs/latest/troubleshooting/#problems-with-dual-intel-and-nvidia-gpu-systems)도 참조하세요.

### GPU 없는 경우

전용 GPU가 없는 경우 RTF 성능이 좋지 않을 수 있습니다. AIC 씬의 Gazebo 렌더링이 최적의 성능을 위해 GPU 가속이 필요한 [GlobalIllumination (GI)](https://gazebosim.org/api/sim/9/global_illumination.html) 기반 렌더링을 사용하기 때문입니다.

**GPU가 없는 시스템에서 시뮬레이션 성능 향상:**

[`aic.sdf`](../aic_description/world/aic.sdf)를 편집하고 [여기](https://github.com/intrinsic-dev/aic/blob/c8aa4571d9dc4bd55bbefc02b0a160ba0e8e1e90/aic_description/world/aic.sdf#L39)와 [여기](https://github.com/intrinsic-dev/aic/blob/c8aa4571d9dc4bd55bbefc02b0a160ba0e8e1e90/aic_description/world/aic.sdf#L109)의 글로벌 일루미네이션 설정에서 `<enabled>`를 `false`로 설정하여 GlobalIllumination을 비활성화할 수 있습니다. 이는 렌더링 품질을 낮추지만 CPU 전용 시스템에서 RTF를 크게 향상시킬 수 있습니다.

> [!WARNING]
> GI를 비활성화하면 씬의 시각적 모습이 변경되어 비전 기반 정책에 영향을 미칠 수 있습니다.

## Zenoh 공유 메모리 감시자 경고

시스템 실행 중 다음과 같은 경고가 표시될 수 있습니다:

```
WARN Watchdog Validator ThreadId(17) zenoh_shm::watchdog::periodic_task:
error setting scheduling priority for thread: OS(1), will run with priority 48.
This is not an hard error and it can be safely ignored under normal operating conditions.
```

**이 경고는 무해하며 안전하게 무시할 수 있습니다.** Zenoh의 공유 메모리 감시자 스레드가 더 높은 스케줄링 우선순위를 설정할 수 없음을 나타냅니다(상승된 권한 필요). 시스템은 정상적으로 계속 작동합니다.

**발생 이유:**
- 감시자 스레드는 공유 메모리 상태를 모니터링합니다.
- 더 높은 우선순위 설정에는 `CAP_SYS_NICE` 기능 또는 root 권한이 필요합니다.
- 없으면 스레드는 기본 우선순위(48)로 실행됩니다.

**문제가 될 수 있는 경우:**
- CPU 부하가 매우 높을 때 감시자가 간헐적으로 마감 시간을 놓칠 수 있습니다.
- 이는 공유 메모리 작업에서 드물게 타임아웃을 유발할 수 있습니다.
- 실제로 이는 일반적인 워크로드에서 거의 문제가 되지 않습니다.

**공유 메모리가 작동 중인지 확인:**
```bash
# Zenoh 공유 메모리 파일 확인
ls -lh /dev/shm | grep zenoh

# 네트워크 트래픽 모니터링 (최소여야 함)
sudo tcpdump -i lo port 7447 -v
```

`/dev/shm`에 Zenoh 파일이 있고 포트 7447의 트래픽이 최소라면 경고에도 불구하고 공유 메모리가 정상적으로 작동하고 있는 것입니다.

## Pixi에 잠긴 PyTorch 버전이 NVIDIA RTX 50xx 카드를 지원하지 않는 경우

```
UserWarning:
NVIDIA GeForce RTX 5090 with CUDA capability sm_120 is not compatible with the current PyTorch installation.

The current PyTorch install supports CUDA capabilities sm_50 sm_60 sm_70 sm_75 sm_80 sm_86 sm_90.
If you want to use the NVIDIA GeForce RTX 5090 GPU with PyTorch, please check the instructions at https://pytorch.org/get-started/locally/
```

`pixi.toml`의 `lerobot` 버전은 이전 버전의 `pytorch`(이전 버전의 cuda용으로 빌드된)에 의존합니다.
`pixi install`은 NVIDIA RTX 50xx 카드의 새로운 sm_120 아키텍처를 지원하지 않는 이전 버전을 가져옵니다.

NVIDIA RTX 5090에서 이 정책을 실행하려면 `pixi.toml`에 다음을 추가하세요:
```
[pypi-options.dependency-overrides]
torch = ">=2.7.1"
torchvision = ">=0.22.1"
```

자세한 내용은 이 [LeRobot 이슈](https://github.com/huggingface/lerobot/issues/2217)를 참조하세요.

## 오류: aic_eval 컨테이너를 찾을 수 없음

`distrobox enter -r aic_eval`을 실행할 때 다음 오류가 발생할 수 있습니다:
```bash
Error: no such container aic_eval
```

기본적으로 distrobox는 podman을 사용하지만 우리는 docker를 사용합니다. `DBX_CONTAINER_MANAGER` 환경 변수를 내보내어 기본 컨테이너 매니저를 설정했는지 확인하세요:
```bash
export DBX_CONTAINER_MANAGER=docker
```
