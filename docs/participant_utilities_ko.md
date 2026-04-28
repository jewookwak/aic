# 참가자 유틸리티

## 원격 조작

### aic_teleoperation

- [aic_teleoperation](../aic_utils/aic_teleoperation/README.md): 관절 공간 및 카르테시안 공간 제어를 위한 키보드 기반 원격 조작

### lerobot_robot_aic

- [lerobot_robot_aic](../aic_utils/lerobot_robot_aic/README.md#teleoperating-with-lerobot): 관절 공간 및 카르테시안 공간 제어를 위한 LeRobot 기반 원격 조작(`lerobot-teleoperate`, 키보드 또는 SpaceMouse 장치 사용)
- `lerobot-record`를 사용하여 LeRobot 정책 훈련을 위한 데이터셋 기록 가능

### 추가 예제

- 지정된 포즈나 관절 설정으로 로봇 명령: [test_impedance.py](../aic_bringup/scripts/test_impedance.py), [home_robot.py](../aic_bringup/scripts/home_robot.py)

## LeRobot 데이터 수집 및 훈련

- [lerobot_robot_aic](../aic_utils/lerobot_robot_aic/README.md#recording-training-data): AIC와의 [LeRobot](https://huggingface.co/lerobot) 통합 — LeRobot을 사용한 원격 조작 및 데이터셋 기록 가능

## 시각화

- [PlotJuggler](https://github.com/facontidavide/PlotJuggler): ROS 토픽의 시계열 데이터 시각화

## RViz

- [RViz](https://docs.ros.org/en/kilted/Tutorials/Intermediate/RViz/RViz-User-Guide/RViz-User-Guide.html)는 ROS 2용 시각화 도구입니다. 제공된 RViz 설정 파일(`aic.rviz`)은 대역폭 문제로 인해 중앙 카메라 스트림만 표시하지만, 다른 두 카메라에 대한 뷰를 추가하면 유용할 수 있습니다.

## ROS 2 CLI 도구

ROS 2는 시스템을 내성 및 디버깅하기 위한 포괄적인 커맨드라인 도구를 제공합니다:

- **[ROS 2 초급 CLI 도구](https://docs.ros.org/en/rolling/Tutorials/Beginner-CLI-Tools.html)**: 다음을 다루는 필수 튜토리얼:
  - `ros2 node` — 실행 중인 노드 목록 조회 및 검사
  - `ros2 topic` — 토픽 보기, 메시지 에코, 발행 속도 모니터링
  - `ros2 service` — 서비스 호출 및 서비스 타입 보기
  - `ros2 param` — 노드 파라미터 가져오기 및 설정하기
  - `ros2 action` — 액션과 상호작용
  - `ros2 bag` — 데이터 기록 및 재생
  - `ros2 launch` — 여러 노드 실행
  - `ros2 interface` — 메시지/서비스/액션 타입 검사

**빠른 예제:**
```bash
# 모든 활성 노드 목록
ros2 node list

# 토픽 에코
ros2 topic echo /aic_controller/state

# 노드 파라미터 가져오기
ros2 param list /aic_controller

# 데이터를 bag 파일에 기록
ros2 bag record -o my_recording /aic_controller/state /camera/image
```
