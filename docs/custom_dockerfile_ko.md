# 커스텀 Dockerfile 만들기 (고급)

예제 Dockerfile은 `aic_model`을 사용하여 정책을 실행한다고 가정합니다. `aic_model`을 사용하지 않는 경우 커스텀 Dockerfile을 만들어야 합니다.

이 문서는 ROS 2 미들웨어 개념, Zenoh 및 Docker에 대한 고급 지식이 있다고 가정합니다.

## 1. ROS 2 및 rmw_zenoh_cpp

정책 노드는 본질적으로 관측값을 구독하고 실행할 액션을 발행하는 ROS 2 노드입니다.
편의를 위해 예제 정책은 실제 정책을 구현하는 `Policy` 클래스를 인스턴스화하는 `aic_model`이라는 Python ROS 노드를 사용하여 보일러플레이트를 최대한 줄입니다.

ROS 2는 미들웨어에 구애받지 않지만, AI for Industry Challenge에서는 `rmw_zenoh_cpp`만 사용됩니다. Dockerfile은 반드시 `rmw_zenoh_cpp`로 정책 노드를 실행해야 합니다. 이는 일반적으로 `RMW_IMPLEMENTATION` 환경 변수를 `rmw_zenoh_cpp`로 설정하여 수행합니다.

이미지 실행 시 자동으로 설정되므로, Dockerfile이 이를 재정의하지 않도록 하고 `rmw_zenoh_cpp`를 사용 가능한 상태로 유지해야 합니다.

## 2. Zenoh

평가 중 이미지는 다음 환경 변수와 함께 실행됩니다:

| 변수 | 설명 |
| :-------------------------- | :-------------------------------------------------------------------------------------------------------------- |
| RMW_IMPLEMENTATION | 사용할 ROS 2 미들웨어. 항상 `rmw_zenoh_cpp`로 설정됨 |
| ZENOH_ROUTER_CHECK_ATTEMPTS | 항상 `-1`로 설정. 모델 라우터가 준비되기 전에 컨테이너가 시작될 때 오류가 발생하는 것을 방지함 |
| AIC_MODEL_ROUTER_ADDR | 정책 노드가 연결해야 하는 Zenoh 라우터 주소 |
| AIC_MODEL_PASSWD | 정책 노드를 식별하기 위해 사용해야 하는 비밀번호 |

정책 노드는 **반드시**:

1. `AIC_MODEL_ROUTER_ADDR` 환경 변수에 제공된 Zenoh 라우터에 연결해야 합니다.
2. 사용자 `model`과 `AIC_MODEL_PASSWD`에 제공된 비밀번호로 사용자-비밀번호 인증을 사용해야 합니다.

가장 쉬운 방법은 `ZENOH_CONFIG_OVERRIDE`를 다음과 같이 설정하는 것입니다:

```bash
ZENOH_CONFIG_OVERRIDE='connect/endpoints=["tcp/'"$AIC_MODEL_ROUTER_ADDR"'"];transport/auth/usrpwd/user="model";transport/auth/usrpwd/password="'"$AIC_MODEL_PASSWD"'";transport/auth/usrpwd/dictionary_file="/credentials.txt"'
```

자격 증명 파일도 만들어야 합니다:

```bash
echo "model:$AIC_MODEL_PASSWD" >> /credentials.txt
```

자세한 내용은 https://github.com/ros2/rmw_zenoh 와 https://zenoh.io/docs/manual/access-control/ 을 참조하세요.

## 3. 엔트리포인트

이미지의 엔트리포인트는 정책 노드를 시작해야 합니다. 추가 커맨드라인 인수는 제공되지 않습니다.
