# AI for Industry Challenge 툴킷

[![build](https://github.com/intrinsic-dev/aic/actions/workflows/build.yml/badge.svg)](https://github.com/intrinsic-dev/aic/actions/workflows/build.yml)
[![style](https://github.com/intrinsic-dev/aic/actions/workflows/style.yml/badge.svg)](https://github.com/intrinsic-dev/aic/actions/workflows/style.yml)

![](../media/aic_banner.png)

**AI for Industry Challenge**는 로보틱스와 제조업 분야에서 가장 어렵고 파급력 큰 문제를 해결하기 위한 개방형 경연 대회입니다.

이 저장소는 참가자들이 솔루션 개발을 시작할 수 있도록 공식 툴킷을 제공합니다. 등록 세부사항, 공식 규칙, FAQ는 [AI for Industry Challenge 이벤트 페이지](https://www.intrinsic.ai/events/ai-for-industry-challenge)를 참조하세요.

---

## 툴킷 가이드

AIC 툴킷 문서에 오신 것을 환영합니다. 이 가이드는 대회 참여의 전체 흐름—요구사항 이해부터 솔루션 제출까지—을 안내합니다.

아래 순서에 따라 각 단계를 진행하세요.

1. **📖 대회 이해하기**
   - [대회 개요](./docs/overview_ko.md)를 읽고 목표를 파악하세요.
   - [예선 단계](./docs/phases_ko.md#예선-단계-모델-훈련하기)를 검토하여 무엇을 만들어야 하는지 이해하세요.
   - [채점 가이드](./docs/scoring_ko.md)를 검토하여 평가 방식을 이해하세요.

2. **🔧 환경 설정하기**
   - [시작 가이드](./docs/getting_started_ko.md)를 따라 개발 환경을 설정하고 검증하세요.
   - 평가 컨테이너를 실행하고 Pixi로 로컬 워크스페이스를 설정하세요.

3. **💻 정책 개발하기**
   - [씬 설명](./docs/scene_description_ko.md)을 살펴보고 환경을 커스터마이징하는 방법을 익히세요.
   - [AIC 인터페이스](./docs/aic_interfaces_ko.md)를 검토하여 센서 및 액추에이터와 통신하는 방법을 이해하세요.
   - [AIC 컨트롤러](./docs/aic_controller_ko.md)를 참조하여 로봇 제어 방법을 익히세요.
   - [대회 규칙](./docs/challenge_rules_ko.md)을 확인하여 규정 준수 여부를 검토하세요.
   - [정책 통합 가이드](./docs/policy_ko.md)를 시작점으로 솔루션을 구현하세요.
   - [참가자 유틸리티](./docs/participant_utilities_ko.md)에서 유용한 도구 목록을 확인하세요.

4. **🧪 솔루션 테스트하기**
   - 제공된 시뮬레이션 환경을 사용하여 정책을 테스트하세요.
   - [`aic_engine/config/`](./aic_engine/config/)의 `sample_config`로 `aic_engine`을 실행하여 다양한 시나리오를 테스트하세요.
   - 문제가 발생하면 [문제 해결](./docs/troubleshooting_ko.md)을 참조하세요.

5. **📦 제출하기**
   - [제출 가이드라인](./docs/submission_ko.md)에 따라 솔루션을 패키징하세요.
   - 제출 전 [이 지침](./docs/submission_ko.md#로컬에서-검증하기)에 따라 컨테이너를 로컬에서 테스트하세요.
   - [이 지침](./docs/submission_ko.md#2-이미지를-레지스트리에-업로드하기)에 따라 공식 포털을 통해 제출하세요.

---

## 툴킷 아키텍처

![AIC Competition Components](../media/aic_competition_components.png)

AI for Industry Challenge 툴킷은 **두 가지 주요 컴포넌트**로 구성됩니다.

### 1. 평가 컴포넌트 (제공됨 - 주최자가 운영)

이 컴포넌트는 완전한 평가 인프라를 제공합니다:
- **`aic_engine`** — 트라이얼을 오케스트레이션하고 점수를 계산합니다.
- **`aic_bringup`** — 시뮬레이션 환경(Gazebo, 로봇, 센서)을 실행합니다.
- **`aic_controller`** — 힘 관리를 포함한 저수준 로봇 제어를 담당합니다.
- **`aic_adapter`** — 센서 융합 및 데이터 동기화를 처리합니다.

**제공 내용:** 카메라 이미지, 관절 상태, 힘/토크 측정값, TF 프레임을 제공하는 표준 ROS 센서 토픽.

### 2. 참가자 모델 컴포넌트 (직접 구현 - 제출 대상)

직접 개발하고 제출하는 부분입니다:
- **ROS 2 노드** — [대회 규칙](./docs/challenge_rules_ko.md)에 정의된 행동 요구사항을 따릅니다.
- **커스텀 로직** — 센서 데이터를 처리하고 로봇에게 케이블 삽입 명령을 내리는 코드.

**제공 내용:** `/insert_cable` 액션에 응답하고 표준 ROS 토픽/서비스로 로봇 모션 명령을 출력하는 `aic_model`이라는 ROS 2 Lifecycle 노드가 포함된 컨테이너.

**편리한 진입점:** 모든 ROS 2 보일러플레이트와 라이프사이클 관리를 처리하는 `aic_model` 프레임워크를 제공합니다. 런타임에 동적으로 로드되는 Python 정책 클래스만 구현하면 됩니다. 자세한 내용은 [정책 통합 가이드](./docs/policy_ko.md)를 참조하세요.

### 개발 및 제출 워크플로우

> [!IMPORTANT]
> **ROS 2 배포판:** 모든 제출물의 공식 평가는 **ROS 2 Kilted Kaiju**를 사용하여 진행됩니다. 다른 ROS 2 배포판(예: Humble, Jazzy)으로 개발하거나 테스트할 경우, 호환성 확보는 전적으로 참가자의 책임입니다. **배포판 간 통신은 보장되지 않으며 공식적으로 지원되지 않습니다.**

**개발 옵션:**
- 컨테이너 내부에서 개발 (권장 - 평가 환경과 일치).
- 또는 네이티브 Ubuntu 24.04 환경에서 개발 (모든 의존성 필요).

**제출 요구사항:**
- 제공된 `aic_model` Dockerfile을 사용하여 솔루션을 패키징하세요.
- 컨테이너를 제출하세요 — 표준 ROS 입력에 응답하고 케이블 삽입을 위해 로봇을 제어해야 합니다.
- 컨테이너는 ROS 토픽을 통해 평가 컴포넌트와 인터페이스합니다.

---

## 저장소 구조

```
aic/
├── aic_adapter/          # 모델과 컨트롤러 간 인터페이싱 어댑터
├── aic_assets/           # 3D 모델 및 시뮬레이션 에셋
├── aic_bringup/          # 대회 환경 실행용 런치 파일
├── aic_controller/       # 로봇 컨트롤러 구현
├── aic_description/      # 로봇 및 환경 URDF/SDF 설명
├── aic_engine/           # 트라이얼 오케스트레이션 및 검증 엔진
├── aic_example_policies/ # 예제 정책 구현
├── aic_gazebo/           # Gazebo 전용 플러그인 및 설정
├── aic_interfaces/       # ROS 2 메시지, 서비스, 액션 정의
├── aic_model/            # 참가자 정책 구현 템플릿
├── aic_scoring/          # 채점 시스템 구현
├── aic_utils/            # 유틸리티 패키지 및 도구
├── docker/               # Docker 컨테이너 정의
└── docs/                 # 상세 문서
```

---

## 참가자를 위한 핵심 패키지

### `aic_model` — 편리한 정책 프레임워크 (권장)
Python 정책 구현을 동적으로 로드하고 실행하는 기성 ROS 2 Lifecycle 노드를 제공합니다. 모든 ROS 2 보일러플레이트, 라이프사이클 관리, 대회 규칙 준수를 처리하므로 정책 로직 구현에만 집중할 수 있습니다.
- **위치**: `aic_model/`
- **문서**: [정책 통합 가이드](./docs/policy_ko.md)
- **튜토리얼**: [새 정책 노드 만들기](./docs/policy_ko.md#튜토리얼-새-정책-노드-만들기)

> **참고:** 이 프레임워크 사용을 권장하지만, [대회 규칙](./docs/challenge_rules_ko.md)을 준수한다면 직접 ROS 2 노드를 구현해도 됩니다.

### `aic_interfaces` — 통신 프로토콜
대회에서 사용하는 모든 ROS 2 메시지, 서비스, 액션을 정의합니다.
- **위치**: `aic_interfaces/`
- **문서**: [AIC 인터페이스](./docs/aic_interfaces_ko.md)

### `aic_example_policies` — 참조 구현
다양한 접근 방식과 기법을 보여주는 예제 정책들입니다.
- **위치**: `aic_example_policies/`
- **README**: [aic_example_policies/README.md](./aic_example_policies/README.md)

### `aic_bringup` — 환경 실행
시뮬레이션, 로봇, 채점 시스템을 시작하는 런치 파일들입니다.
- **위치**: `aic_bringup/`
- **README**: [aic_bringup/README.md](./aic_bringup/README.md)

### `aic_engine` — 트라이얼 오케스트레이터
트라이얼 실행을 관리하고, 참가자 모델을 검증하며, 채점 데이터를 수집합니다.
- **위치**: `aic_engine/`
- **README**: [aic_engine/README.md](./aic_engine/README.md)

---

## 추가 문서

### 대회 정보

* **[대회 개요](./docs/overview_ko.md):** 경연 목표와 구조에 대한 고수준 요약.
* **[경연 단계](./docs/phases_ko.md):** 예선, Phase 1, Phase 2 세부 내용.
* **[예선 단계](./docs/qualification_phase_ko.md):** 예선 트라이얼 및 채점에 대한 기술적 개요.
* **[대회 규칙](./docs/challenge_rules_ko.md):** 참가자 모델의 필수 행동 요건.
* **[채점](./docs/scoring_ko.md):** 성과 평가에 사용되는 지표와 방법.
* **[채점 테스트 예제](./docs/scoring_tests_ko.md):** 각 채점 티어를 테스트하는 재현 가능한 예제와 정확한 명령어.

### 기술 문서

* **[시작 가이드](./docs/getting_started_ko.md):** 로컬 개발 환경 설정 방법.
* **[정책 통합](./docs/policy_ko.md):** `aic_model` 프레임워크에서 정책 구현 가이드.
* **[AIC 인터페이스](./docs/aic_interfaces_ko.md):** 정책에서 사용 가능한 ROS 2 토픽, 서비스, 액션.
* **[AIC 컨트롤러](./docs/aic_controller_ko.md):** 로봇 컨트롤러와 모션 명령 이해.
* **[씬 설명](./docs/scene_description_ko.md):** 시뮬레이션 환경의 기술적 세부사항.
* **[태스크 보드 설명](./docs/task_board_description_ko.md):** 태스크 보드의 물리적 레이아웃 및 사양.
* **[문제 해결](./docs/troubleshooting_ko.md):** 일반적인 문제 및 디버깅 전략.

### 참고 자료

* **[용어집](./docs/glossary_ko.md):** AI for Industry Challenge 전반에 사용되는 용어와 정의.

### 제출

* **[제출 가이드라인](./docs/submission_ko.md):** 최종 모델 패키징 및 제출 방법.

---

## 지원 및 리소스

- **토론**: [Open Robotics Discourse](https://discourse.openrobotics.org/c/competitions/ai-for-industry-challenge/)에서 대화하고 질문하세요. 커뮤니티의 적극적인 참여와 상호 도움을 환영합니다.
- **이슈**: 버그나 기술적 문제는 [GitHub Issues](https://github.com/intrinsic-dev/aic/issues)를 통해 보고하세요. 대회에 관한 일반적인 질문은 이슈 트래커를 사용하지 마세요.
- **이벤트 페이지**: 공식 업데이트는 [AI for Industry Challenge](https://www.intrinsic.ai/events/ai-for-industry-challenge)를 방문하세요.

---

## 라이선스

이 프로젝트는 Apache License 2.0 하에 라이선스됩니다. 개별 패키지 파일을 참조하세요.
[aic_isaac](./aic_utils/aic_isaac/) 폴더는 BSD-3 라이선스 하에 있습니다 — [aic_isaac/LICENSE](./aic_utils/aic_isaac/LICENSE) 참조.
