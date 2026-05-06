#!/usr/bin/env bash
# 로컬 개발용 MuJoCo 실행 스크립트 (distrobox 내부에서 실행)
#
# train_tqc.py는 Zenoh 라우터를 tcp/localhost:7447에 자동으로 시작합니다.
# 이 스크립트는 MuJoCo가 같은 라우터를 바라보도록 ZENOH_SESSION_CONFIG_URI를 설정합니다.
#
# 사용법:
#   # 터미널 1 (distrobox):
#   distrobox enter aic_eval
#   bash ~/ws_aic/src/aic/my_policy/scripts/run_mujoco_dev.sh
#
#   # 터미널 2 (pixi):
#   cd ~/ws_aic/src/aic
#   pixi run python3 my_policy/scripts/train_tqc.py --mode state

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZENOH_CONFIG="$SCRIPT_DIR/../../docker/aic_eval/aic_zenoh_config.json5"

if [ ! -f "$ZENOH_CONFIG" ]; then
  echo "ERROR: aic_zenoh_config.json5 not found at $ZENOH_CONFIG"
  exit 1
fi

export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_SESSION_CONFIG_URI="$(realpath "$ZENOH_CONFIG")"
export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=false;connect/endpoints=["tcp/127.0.0.1:7447"]'

echo "[run_mujoco_dev] RMW_IMPLEMENTATION=$RMW_IMPLEMENTATION"
echo "[run_mujoco_dev] ZENOH_SESSION_CONFIG_URI=$ZENOH_SESSION_CONFIG_URI"
echo "[run_mujoco_dev] Zenoh 라우터: tcp/127.0.0.1:7447 (train_tqc.py가 시작해야 합니다)"
echo ""

source ~/ws_aic/install/setup.bash
ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true
