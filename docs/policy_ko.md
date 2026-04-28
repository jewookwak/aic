# 정책 통합하기

많은 컴퓨팅 분야처럼, _모델_ 및 _정책_ 같은 AI 용어는 다양한 맥락에서 서로 다른 의미로 사용됩니다. 다음 다이어그램은 AI for Industry Challenge의 소프트웨어 블록에서 이 용어들이 어떻게 사용되는지 보여줍니다:

![블록 다이어그램](../../media/aic_policy_diagram.png)

_정책_은 센서 데이터를 소비하고 로봇에 출력 명령을 생성하는 소프트웨어입니다. _정책_ 만들기는 AI for Industry Challenge의 핵심으로, 센서와 액추에이터 사이의 루프를 "닫는" 핵심 블록이기 때문입니다.

더 구체적으로, _정책_은 최대 20Hz로 다음 데이터를 수신할 수 있습니다:
 * 📷📷📷 로봇 손목에 장착된 세 개의 카메라 이미지
 * 🦾 로봇 팔과 그리퍼의 관절 각도
 * ⚖️ 로봇 손목의 3D 힘 및 3D 토크 측정값
 * 📐 그리퍼-핑거 도구 중심점(TCP)의 목표 및 실제 포즈
 * ☄️ 그리퍼-핑거 도구 중심점(TCP)의 속도

편의를 위해 대회 환경의 `aic_adapter`는 센서 스위트의 시간 동기화된 값을 20Hz로 `aic_model` 블록에 전달되는 단일 복합 `Observation` 데이터 구조로 결합합니다. 사용자 정의 `policy`는 런타임에 `aic_model`에 동적으로 로드되며 언제든지 최신 `Observation`을 가져올 수 있습니다.

정책은 접촉 중 힘을 관리하기 위해 저수준 제어를 제공하는 `aic_controller`에 위치 또는 속도 목표를 전달할 책임이 있습니다. 목표는 어떤 속도로든 `aic_controller`로 전송할 수 있습니다.

대회가 ROS로 구현되어 있기 때문에 정책 작성 시 여러 API 스타일이 가능합니다. 가장 간단한 API는 다음 섹션에 나와 있는 것처럼 ROS 2 Python 클라이언트 라이브러리인 `rclpy`가 생성한 데이터 구조를 사용합니다.

## Policy API

`geometry_msgs.msg.Pose`, `sensor_msgs.msg.Image` 등의 ROS 데이터 구조를 사용하여 정책을 통합하려면:
 * [`aic_model.Policy`](https://github.com/intrinsic-dev/aic/blob/main/aic_model/aic_model/policy.py)에서 파생되는 Python 클래스를 정의합니다
 * `aic_engine`이 새 태스크를 요청할 때 호출되는 [`insert_cable()`](https://github.com/intrinsic-dev/aic/blob/main/aic_model/aic_model/policy.py#L49) 메서드를 구현합니다
 * 이 Python 클래스 이름을 런타임에 `aic_model`의 파라미터로 제공합니다

`insert_cable()` 함수는 여러 `Callable` 메서드를 파라미터로 수신합니다:
 * `get_observation()`은 ROS 메시지로 가장 최근의 [`Observation`](https://github.com/intrinsic-dev/aic/blob/main/aic_interfaces/aic_model_interfaces/msg/Observation.msg)을 반환합니다. 이 메시지는 여러 ROS 서브메시지로 구성됩니다:
   * [`sensor_msgs/Image left_image`](https://github.com/ros2/common_interfaces/blob/kilted/sensor_msgs/msg/Image.msg) (및 `center_image`, `right_image`)
   * [`sensor_msgs/CameraInfo left_camera_info`](https://github.com/ros2/common_interfaces/blob/kilted/sensor_msgs/msg/CameraInfo.msg) (및 `center_camera_info`, `right_camera_info`)
   * [`sensor_msgs/JointState joint_states`](https://github.com/ros2/common_interfaces/blob/kilted/sensor_msgs/msg/JointState.msg)
   * [`geometry_msgs/WrenchStamped wrist_wrench`](https://github.com/ros2/common_interfaces/blob/kilted/geometry_msgs/msg/WrenchStamped.msg)
   * [`aic_control_interfaces/ControllerState controller_state`](https://github.com/intrinsic-dev/aic/blob/main/aic_interfaces/aic_control_interfaces/msg/ControllerState.msg)
 * `move_robot()`은 `MotionUpdate` 또는 `JointMotionUpdate` 메시지를 로봇 팔 컨트롤러로 전송합니다.
 * `send_feedback()`은 `InsertCable` 액션의 [피드백](https://docs.ros.org/en/kilted/Tutorials/Intermediate/Creating-an-Action.html#defining-an-action) 메시지로 `string`을 발행하며, 디버깅에 유용합니다.

_정책_은 로봇에 모션 명령을 발행하는 API 함수들을 호출할 수 있습니다. 구현 세부사항으로, 그 API 함수들은 [`ros2_control`](https://control.ros.org/rolling/index.html) 프레임워크를 사용하여 구현된 `aic_controller`에 데이터를 발행하기 위해 `aic_model` ROS 노드를 사용합니다.

## 기준 정책

케이블 삽입 태스크에 대한 다양한 접근법을 보여주는 여러 기준 정책 구현을 [`aic_example_policies`](../aic_example_policies/) 패키지에서 제공합니다:

- **WaveArm** — 기본 Policy API 구조를 보여주는 최소 예제
- **CheatCode** — 훈련 및 디버깅을 위해 ground truth 데이터를 사용하는 "치트" 정책
- **RunACT** — ACT(Action Chunking with Transformers) 정책 구현

자세한 설명, 사용법, 소스 코드는 [예제 정책 README](../aic_example_policies/README.md)를 참조하세요.

각 기준 정책의 예상 채점 결과는 [채점 테스트 및 평가 가이드](./scoring_tests_ko.md)를 참조하세요.

## 튜토리얼: 새 정책 노드 만들기

정책 노드는 본질적으로 관측값을 구독하고 실행할 액션을 발행하는 ROS 2 노드입니다.

이 튜토리얼에서는 [aic_model](../aic_model/)을 사용하여 정책 노드를 구현합니다.

> [!Important]
> bash 예제의 프롬프트에 주목하세요. `(aic) $`로 시작하면 pixi 환경 내부에서 실행해야 합니다.
>
> 예시:
> ```bash
> $ pixi shell # pixi 환경 외부
> (aic) $ ros2 pkg list # pixi 환경 내부
> ```

### 새 ROS 2 패키지 만들기

```bash
# pixi 환경에 진입하려면 "pixi shell"을 실행하세요
(aic) $ ros2 pkg create my_policy_node --build-type ament_python
```

### AIC 의존성 추가

`package.xml`에 다음을 추가합니다:
```xml
	<depend>aic_control_interfaces</depend>
	<depend>aic_model</depend>
	<depend>aic_model_interfaces</depend>
	<depend>aic_task_interfaces</depend>
	<depend>geometry_msgs</depend>
	<depend>rclpy</depend>
	<depend>sensor_msgs</depend>
	<depend>std_srvs</depend>
	<depend>trajectory_msgs</depend>
```

### pixi 패키지 만들기

`my_policy_node` 패키지 디렉토리에 다음 내용으로 `pixi.toml`을 만듭니다:

```toml
[package.build.backend]
name = "pixi-build-ros"
version = "==0.3.3.20260113.c8b6a54"
channels = [
	"https://prefix.dev/pixi-build-backends",
	"robostack-kilted",
	"conda-forge",
]

[package.host-dependencies]
ros-kilted-aic-control-interfaces = { path = "../aic_interfaces/aic_control_interfaces" }
ros-kilted-aic-model = { path = "../aic_model" }
ros-kilted-aic-model-interfaces = { path = "../aic_interfaces/aic_model_interfaces" }
ros-kilted-aic-task-interfaces = { path = "../aic_interfaces/aic_task_interfaces" }

[package.build-dependencies]
ros-kilted-aic-control-interfaces = { path = "../aic_interfaces/aic_control_interfaces" }
ros-kilted-aic-model = { path = "../aic_model" }
ros-kilted-aic-model-interfaces = { path = "../aic_interfaces/aic_model_interfaces" }
ros-kilted-aic-task-interfaces = { path = "../aic_interfaces/aic_task_interfaces" }
```

> [!Tip]
> 일반적으로 pixi는 `package.xml`에서 의존성을 자동으로 발견합니다. 하지만 aic 인터페이스를 소스에서 빌드하기 때문에 pixi에게 위치를 알려줘야 합니다.

### 워크스페이스에 pixi 패키지 추가하기

루트 `pixi.toml`의 `[dependencies]`에 새 패키지를 추가합니다:

```toml
[dependencies]
# ...
ros-kilted-my-policy-node = { path = "my_policy_node" }
```

### `PolicyRos` 구현하기

간략하게, `aic_example_policies`의 코드를 재사용합니다. 구현 세부사항은 위의 [ROS Policy API](#policy-api) 섹션을 참조하세요.

```bash
(aic) $ cp aic_example_policies/aic_example_policies/ros/WaveArm.py my_policy_node/my_policy_node/WaveArm.py
```

### 정책 노드 테스트하기

터미널 1:
```bash
# 'export DBX_CONTAINER_MANAGER=docker'를 실행했는지 확인하세요
$ distrobox enter -r aic_eval -- /entrypoint.sh
```

터미널 2:
```bash
$ pixi reinstall ros-kilted-my-policy-node
$ pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=my_policy_node.WaveArm
```

> [!Note]
> 위 명령은 `aic_model` 노드를 실행하고, 그러면 해당 노드가 특정 정책 구현(`my_policy_node.WaveArm`)을 동적으로 로드하고 실행합니다.

### 의존성 관리

pixi 워크스페이스에서 의존성을 관리하는 방법에 대한 간단한 가이드입니다. 일반적인 ROS 워크스페이스와 달리 시스템 의존성을 사용하지 않으며, 모든 의존성은 conda 또는 pypi에서 가져와야 합니다.

#### 의존성 추가하기

##### ROS 의존성

pixi 워크스페이스는 robostack-kilted 채널로 설정됩니다. pixi로 대부분의 ROS 패키지를 설치할 수 있습니다.

```bash
$ pixi add ros-kilted-ros-core
```

##### pypi 의존성

네이티브 ROS 워크스페이스와 달리 pixi 워크스페이스는 ROS와 pypi 의존성을 혼합할 수 있습니다.

```bash
$ pixi add --pypi torch
```

##### 로컬 의존성

패키지가 동일한 워크스페이스의 로컬 의존성을 필요로 한다면, 그 의존성은 패키지의 `pixi.toml`과 루트 `pixi.toml` 모두에 선언되어야 합니다.

예를 들어, `my_policy_node`가 `my_local_dep`을 필요로 한다면:

`my_policy_node/pixi.toml`:
```toml
[package.host-dependencies]
# ...
ros-kilted-my-local-dep = { path = "../my_local_dep" }

[package.build-dependencies]
# ...
ros-kilted-my-local-dep = { path = "../my_local_dep" }
```

`pixi.toml`:
```toml
[dependencies]
# ...
ros-kilted-my-policy-node = { path = "my_policy_node" }
ros-kilted-my-local-dep = { path = "my_local_dep" }
```

> [!Tip]
> pixi는 자동으로 ROS 패키지 이름 앞에 `ros-<distro>-`를 붙이고 언더스코어를 하이픈으로 변환합니다.

### 빌드-실행-디버그 사이클 (Python)

> [!IMPORTANT]
> Pixi 환경 내 패키지 변경사항은 자동으로 추적되지 않습니다. 업데이트를 적용하려면 `pixi reinstall <package_name>`을 실행해야 합니다.

```bash
$ pixi reinstall <package>
```

> [!Tip]
> `pixi shell`로 pixi 환경에 진입하고 `pip install -e`로 "편집 가능한" 설치를 강제할 수 있습니다. 하지만 이는 pixi를 우회하므로 의도치 않은 부작용이 발생할 수 있습니다.

### 제출 준비하기

정책이 완성되면 제출을 위한 Docker 이미지를 준비해야 합니다. 자세한 내용은 [제출](./submission_ko.md)을 참조하세요.

### 마무리

축하합니다! 정책 노드를 성공적으로 만들고, 테스트하고, 패키징했습니다.

이 튜토리얼에서 배운 내용:
- 정책 노드를 위한 새 ROS 2 패키지 만들기 및 설정.
- `pixi` 워크스페이스에서 Python 및 ROS 의존성 관리.
- 정책 개발을 위한 빌드, 실행, 디버그 사이클 이해.
- 제출을 위한 정책 Docker 이미지 준비.

이제 AI for Industry Challenge를 위한 정책을 개발하고, 테스트하고, 제출하는 데 필요한 기본 기술이 갖춰졌습니다. 더 고급 개념과 영감을 얻으려면 제공된 예제 정책과 기타 문서를 자유롭게 살펴보세요.
