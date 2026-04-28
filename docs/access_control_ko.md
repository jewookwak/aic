# 접근 제어

평가 시스템은 Zenoh 접근 제어 목록(ACL)을 사용하여 제출물이 시뮬레이션 내 부품의 포즈를 단순히 조회함으로써 부정행위를 할 수 없도록 합니다.

제출 환경이 제공하는 보안을 복제하려면 Zenoh 보안을 활성화한 상태로 환경과 모델 제출물을 실행할 수 있습니다. 이렇게 하면 Zenoh가 부정행위를 방지하기 위해 `gz_server` 네임스페이스의 토픽과 서비스 같은 특정 토픽과 서비스에 대한 접근을 차단합니다.

## 별도의 터미널로 테스트하기

다음 시연은 Zenoh 접근 제어가 작동하는 것을 보여줍니다. 이 모든 단계는 제출 포털에서 Docker에 의해 자동으로 수행되지만, 상호작용 및 명확성을 위해 여기서는 커맨드라인에서 수동으로 보여줍니다. 이 단계들은 무단 토픽이나 서비스가 사용되지 않는지 확인하기 위한 로컬 테스트에 유용합니다.

### 터미널 1: ACL로 Zenoh 라우터 시작

```
. install/setup.bash
. src/aic/docker/aic_eval/zenoh_config_router.sh
ros2 run rmw_zenoh_cpp rmw_zenohd
```

### 터미널 2: 시뮬레이션 환경 시작

다음 명령은 일부 엔티티가 스폰된 시뮬레이션 환경을 실행합니다:
```
. install/setup.bash
. src/aic/docker/aic_eval/zenoh_config_eval_session.sh
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
ros2 launch aic_bringup aic_gz_bringup.launch.py nic_card_mount_0_present:=true sc_port_0_present:=true ground_truth:=false spawn_task_board:=true spawn_cable:=true attach_cable_to_gripper:=true sfp_mount_rail_0_present:=true cable_type:=sfp_sc_cable
```

### 터미널 3: 서비스가 차단되었음을 시연

```
. install/setup.bash
. src/aic/docker/aic_model/zenoh_config_model_session.sh
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
ros2 service call /gz_server/get_entities_states simulation_interfaces/srv/GetEntitiesStates
```

이 호출은 ACL에 의해 차단되어 성공하지 않습니다.

대신 이 터미널에 `eval` 신원에 관련된 환경 변수가 있으면 시뮬레이션 내 모든 엔티티의 포즈와 속도 목록을 반환합니다:
```
. install/setup.bash
. src/aic/docker/aic_eval/zenoh_config_eval_session.sh
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
ros2 service call /gz_server/get_entities_states simulation_interfaces/srv/GetEntitiesStates
```

`eval` 신원은 비밀번호로 보호되며, 제출 포털에서 실행될 때는 다른 비밀번호가 사용됩니다.

## docker-compose로 테스트하기

Docker-compose는 평가 컨테이너와 모델 컨테이너 간의 상호작용을 테스트하는 편리한 방법을 제공합니다:

먼저 컨테이너를 빌드하세요:
```
docker compose -f docker/docker-compose.yaml build
```

그런 다음 실행하세요:
```
docker compose -f docker/docker-compose.yaml up
```
