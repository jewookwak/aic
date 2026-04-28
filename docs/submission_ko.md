# 제출 가이드라인

## 소개

**AI for Industry Challenge**에 오신 것을 환영합니다. 이 문서는 솔루션을 패키징하고, 컨테이너화하고, 평가를 위해 업로드하는 기술적 요구사항을 설명합니다. 이 단계를 따르면 모델이 로컬 머신에서와 정확히 동일하게 자동화된 평가 환경에서 실행됩니다.

> [!IMPORTANT]
> 레지스트리 업로드를 완료하려면 팀 리더에게 전송된 **온보딩 이메일**에 제공된 자격 증명이 있어야 합니다. 여기에는 고유한 AWS 액세스 자격 증명과 팀에 할당된 ECR 저장소 URI가 포함됩니다.

---

## 1. 이미지 준비 및 빌드

모든 제출물은 Docker나 Podman 같은 OCI 호환 이미지 빌더를 사용하여 컨테이너화해야 합니다. 모든 정책 로직과 의존성 요구사항을 커스텀 정책 패키지 내에 직접 배치하여 프로젝트를 구성하세요.

추가 패키지나 의존성이 없는 경우 [policy.py](../aic_model/aic_model/policy.py)에 정책 코드를 유지하고 [Dockerfile](../docker/aic_model/Dockerfile)이 있는 `aic_model` 디렉토리를 재사용할 수 있습니다. 이 경우 Dockerfile을 업데이트하여 `CMD ["--ros-args", "-p", "policy:=aic_example_policies.ros.CheatCode", "-p", "use_sim_time:=true"]`를 `CMD ["--ros-args", "-p", "policy:=aic_model.MyPolicy", "-p", "use_sim_time:=true"]`로 변경하고 [이미지 빌드](#이미지-빌드) 섹션으로 건너뛰세요.

예제 aic_model Dockerfile을 시작점으로 사용하는 것을 강력히 권장합니다.

```bash
mkdir -p docker/my_policy
cp docker/aic_model/Dockerfile docker/my_policy/
```

그런 다음 `docker/my_policy/Dockerfile`을 수정하여 커스텀 정책 패키지를 추가하세요:

```dockerfile
# 다른 의존성 추가
COPY my_policy_node /ws_aic/src/aic/my_policy_node # <-- 이 줄 추가
```

`CMD`를 편집하여 정책을 실행하세요:

```dockerfile
CMD ["--ros-args", "-p", "policy:=my_policy_node.MyPolicy"]
CMD ["--ros-args", "-p", "policy:=my_policy_node.MyPolicy", "-p", "use_sim_time:=true"]
```

### `docker-compose.yaml` 업데이트

`docker/docker-compose.yaml`을 열고 모델 서비스 설정을 Dockerfile과 정책에 맞게 업데이트하세요:

```yaml
    model:
        image: my-solution:v1
        build:
            dockerfile: docker/my_policy_node/Dockerfile # <-- 이 줄 교체
            context: ..
```

### 이미지 빌드

제출 이미지를 빌드하려면 **루트 디렉토리**에서 다음 명령을 실행하세요:

```bash
docker compose -f docker/docker-compose.yaml build model
```

### 로컬에서 검증하기

이미지를 서버에 푸시하기 전에 컨테이너가 올바르게 초기화되고 데이터를 예상대로 처리하는지 확인해야 합니다.

`docker compose`를 사용하여 평가를 로컬에서 실행할 수 있습니다:

```bash
docker compose -f docker/docker-compose.yaml up
```

> [!WARNING]
> 로컬 검증을 건너뛰지 마세요. 컨테이너가 로컬 평가 중 시작에 실패하거나 충돌하면 제출 포털에서 자동으로 거부되며, 이는 일일 제출 한도에 포함될 수 있습니다.

> [!IMPORTANT]
> 시뮬레이터의 내부 데이터 구조를 단순히 구독하는 최소한의 "치트" 솔루션을 방지하기 위해 사용되는 Zenoh 접근 제어에 대한 설명은 [접근 제어](access_control_ko.md) 문서를 참조하세요.

---

## 2. 이미지를 레지스트리에 업로드하기

팀 OCI 이미지를 호스팅하기 위해 Amazon Elastic Container Registry (ECR)를 사용합니다. [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)가 설치되어 있어야 합니다.

### 인증

팀 리더에게 전송된 온보딩 이메일에 제공된 자격 증명을 사용하여 다음 단계에 따라 로컬 환경을 설정하세요:

#### A. AWS 프로필 설정
다음 명령을 실행하고 `<team_name>`을 이메일에 제공된 슬러그(예: `team123`)로 교체하세요:

```bash
aws configure --profile <team_name>
```

프롬프트가 나타나면 다음을 입력하세요:

- **Access Key ID:** (이메일에서 복사)
- **Secret Access Key:** (이메일에서 복사)
- **Default region name:** us-east-1
- **Default output format:** json (또는 Enter를 눌러 기본값 사용)

#### B. 환경 변수 설정

이후 명령이 올바른 자격 증명을 사용하도록 셸을 새 프로필로 지정하세요:

```bash
export AWS_PROFILE=<team_name>
```

#### C. 레지스트리 인증

마지막으로 로컬 Docker 클라이언트를 개인 레지스트리로 인증하세요:

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 973918476471.dkr.ecr.us-east-1.amazonaws.com
```

### 이미지 태그 지정

로컬 이미지에 팀에 제공된 원격 저장소 URI와 일치하는 태그를 지정해야 합니다. 아래의 더미 URI를 팀의 특정 URI로 교체하세요:

```bash
docker tag localhost/my-solution:v1 973918476471.dkr.ecr.us-east-1.amazonaws.com/aic-team/<team_name>:v1
```

> [!IMPORTANT]
> ECR 레지스트리의 이미지 태그는 불변입니다. 기존 태그를 덮어쓸 수 없습니다. 새 제출이나 빌드마다 버전 태그를 증가시키거나(예: :v2, :v3) Git 커밋 SHA 같은 고유 식별자를 사용해야 합니다. 레지스트리에 이미 존재하는 태그로 이미지를 푸시하려고 하면 푸시가 실패합니다.

### 이미지 푸시

태그된 이미지를 대회 레지스트리에 업로드하세요:

```bash
docker push 973918476471.dkr.ecr.us-east-1.amazonaws.com/aic-team/<team_name>:v1
```

---

## 3. 제출 등록

ECR에 이미지를 푸시하는 것만으로는 평가가 시작되지 않습니다. 새 버전이 채점 준비가 되었음을 플랫폼에 알려야 합니다.

> [!NOTE]
> 제출 포털은 곧 열릴 예정입니다. 제출 포털의 로그인 자격 증명은 3월 말까지 팀 리더에게 이메일로 전송될 것입니다.

1. 방금 푸시한 전체 이미지 URI를 복사하세요 (예: `973918476471.dkr.ecr.us-east-1.amazonaws.com/aic-team/<team_name>:v1`).
2. 제출 포털에 로그인하세요.
3. `AI for Industry Challenge`를 클릭한 다음 `Submit`으로 이동하세요.
4. `Qualification` 단계를 선택하고 URI를 제출 `OCI Image` 필드에 붙여넣으세요.
5. `Submit`을 클릭하여 진행하세요.

---

### 4. 평가 모니터링

OCI 이미지 URI를 등록한 후 오케스트레이션 플랫폼이 컨테이너를 전용 격리된 평가 환경으로 스핀업합니다. 이 과정은 자동화되어 있지만 포털의 모니터링 대시보드를 통해 라이프사이클을 추적할 수 있습니다.

#### 대시보드 접근
1. 포털의 **My Submissions** 페이지로 이동하세요.
2. "Phase" 드롭다운의 `Qualification` 필터를 적용하여 현재 항목을 확인하세요.
3. 테이블 상단에서 가장 최근 제출을 찾으세요.

#### 평가 라이프사이클

**Status** 열은 평가 클러스터를 통한 컨테이너의 실시간 상태를 제공합니다.

| 상태 | 기술적 맥락 |
| :--- | :--- |
| **Submitted** | 플랫폼이 이미지 URI를 수신했습니다. |
| **Queued** | 제출물이 실행 버퍼에 있습니다. 클러스터에서 사용 가능한 평가 노드를 기다리고 있습니다. |
| **Running** | 이미지가 ECR에서 가져와졌으며 ROS 2 노드가 현재 시뮬레이션 환경에서 대회 로직을 실행하고 있습니다. |
| **Finished** | 평가가 자연스럽게 완료되었습니다. 성공 지표가 계산되어 리더보드에 표시됩니다. |
| **Failed** | 컨테이너가 조기에 종료되었습니다. 일반적으로 런타임 충돌(예: Python `ImportError`), 누락된 의존성, 또는 시스템 타임아웃을 나타냅니다. |

> [!TIP]
> 클러스터 부하와 정책의 복잡성에 따라 **Queued**에서 **Finished**로 전환하는 데 일반적으로 **5~15분**이 소요됩니다. 상태가 "Queued" 또는 "Running"인 경우 재제출할 필요가 없습니다. 최신 상태를 보려면 페이지를 새로고침하세요.

---

## FAQ

**예제 Dockerfile을 사용할 수 없습니다**: 예제 Dockerfile은 `aic_model`을 사용하여 정책을 실행한다고 가정합니다. `aic_model`을 사용하지 않는 경우 [커스텀 Dockerfile을 만들 수 있습니다](./custom_dockerfile_ko.md).

**"no basic auth credentials"로 푸시가 실패했습니다**: Docker 로그인 세션이 만료되었을 가능성이 높습니다. ECR 로그인 토큰은 12시간 동안 유효합니다. 섹션 2의 [인증](#인증) 단계를 반복하세요.

**결과는 어디서 볼 수 있나요?** 모든 이전 결과와 로그는 포털의 "My submissions" 섹션에서 확인할 수 있습니다. 리더보드를 방문하여 다른 팀과 결과를 비교할 수도 있습니다.

**여러 번 제출할 수 있나요?** 네. 하지만 하루에 1회 제출로 제한됩니다. 대회 기간 동안 총 제출 횟수에는 제한이 없습니다.

---

## 문의

- **이슈**: [GitHub Issues](https://github.com/intrinsic-dev/aic/issues)를 통해 문제를 보고하세요.
- **커뮤니티**: [Open Robotics Discourse](https://discourse.openrobotics.org/c/competitions/ai-for-industry-challenge/)에서 토론에 참여하세요.
