#!/usr/bin/env python3
"""
TQC + ACT Encoder Training Script for AIC Cable Insertion.

두 가지 모드:
  --mode state  : 상태 벡터만 사용 (기본 MLP, 빠른 학습)
  --mode image  : ACT Transformer 인코더 사용 (카메라 + 상태, 더 현실적)

Usage:
  # 터미널 1 (distrobox): 시뮬레이터 실행 (ground_truth 필수)
  ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true

  # 터미널 2 (pixi): 학습 (상태 기반)  ← Zenoh 라우터 자동 시작 포함
  pixi run python3 my_policy/scripts/train_tqc.py --mode state

  # 터미널 2 (pixi): 학습 (ACT 인코더 + 이미지)
  pixi run python3 my_policy/scripts/train_tqc.py --mode image

  # 학습 재개
  pixi run python3 my_policy/scripts/train_tqc.py --mode image --resume logs/tqc_aic_image/best_model.zip

  # TensorBoard 모니터링
  pixi run tensorboard --logdir logs/

NOTE:
  pixi와 distrobox는 Zenoh peer-to-peer 모드로 통신합니다 (라우터 불필요).
  Zenoh 라우터를 별도로 시작하면 오히려 peer discovery가 깨질 수 있으니 주의.
"""

import argparse
import os
import subprocess
import time
from pathlib import Path
from functools import partial

from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.her.her_replay_buffer import HerReplayBuffer
from sb3_contrib import TQC

from my_policy.aic_env import AICEnv

ZENOH_ROUTER_ADDR = "tcp/127.0.0.1:7447"


def _setup_zenoh():
    """
    Zenoh 라우터를 시작하고 이 프로세스가 라우터에 연결하도록 설정합니다.

    프로덕션(Docker)에서는 별도 rmw_zenohd 컨테이너가 이 역할을 합니다.
    로컬 개발 시 이 함수가 그 역할을 대신합니다.

    반드시 rclpy.init() 호출 전에 실행해야 합니다.
    distrobox MuJoCo도 반드시 ZENOH_SESSION_CONFIG_URI를 설정해야 합니다:
      export ZENOH_SESSION_CONFIG_URI=~/ws_aic/src/aic/docker/aic_eval/aic_zenoh_config.json5
    """
    # 1. 이 프로세스의 Zenoh config에 router connect endpoint 추가
    override = os.environ.get("ZENOH_CONFIG_OVERRIDE", "transport/shared_memory/enabled=false")
    if "connect/endpoints" not in override:
        os.environ["ZENOH_CONFIG_OVERRIDE"] = (
            override + f';connect/endpoints=["{ZENOH_ROUTER_ADDR}"]'
        )

    # 2. Zenoh 라우터가 없으면 백그라운드로 시작
    already_running = subprocess.run(
        ["pgrep", "-f", "rmw_zenohd"], capture_output=True
    ).returncode == 0

    if already_running:
        print("[train_tqc] Zenoh 라우터가 이미 실행 중입니다.")
        return None

    print(f"[train_tqc] Zenoh 라우터 시작 중 ({ZENOH_ROUTER_ADDR})...")
    proc = subprocess.Popen(
        ["ros2", "run", "rmw_zenoh_cpp", "rmw_zenohd"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3.0)
    if proc.poll() is not None:
        print("[train_tqc] 경고: Zenoh 라우터 시작 실패.")
        return None
    print(f"[train_tqc] Zenoh 라우터 시작 완료 (PID={proc.pid})")
    return proc


def make_env(use_images: bool) -> AICEnv:
    return AICEnv(use_images=use_images)


def train(mode: str = "state", resume_path: str | None = None):
    use_images = (mode == "image")
    log_dir   = Path(f"logs/tqc_aic_{mode}")
    model_dir = Path(f"models/tqc_aic_{mode}")
    log_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    # 단일 MuJoCo 인스턴스와 통신하므로 env 하나만 생성
    # (eval_env를 별도로 만들면 두 env가 같은 로봇을 동시에 제어하는 문제 발생)
    env = DummyVecEnv([partial(make_env, use_images=use_images)])

    callbacks = [
        CheckpointCallback(
            save_freq=10_000,
            save_path=str(model_dir),
            name_prefix=f"tqc_aic_{mode}",
        ),
    ]

    # ── policy_kwargs: image 모드면 ACTFeaturesExtractor 사용 ──────────
    if use_images:
        from my_policy.act_encoder import ACTFeaturesExtractor
        policy_kwargs = dict(
            features_extractor_class=ACTFeaturesExtractor,
            features_extractor_kwargs=dict(
                repo_id="grkw/aic_act_policy",
                features_dim=512,
                freeze_encoder=True,   # False로 바꾸면 end-to-end fine-tune
                img_size=(84, 84),
            ),
            net_arch=[512, 512],       # Q/Policy MLP hidden layers
        )
        # 이미지 포함 시 buffer 크기 줄임 (메모리)
        buffer_size = 100_000
        batch_size  = 256
        lr          = 3e-4
    else:
        policy_kwargs = dict(net_arch=[256, 256])
        buffer_size = 1_000_000
        batch_size  = 512
        lr          = 1e-3

    if resume_path:
        print(f"학습 재개: {resume_path}")
        model = TQC.load(resume_path, env=env)
    else:
        model = TQC(
            policy="MultiInputPolicy",
            env=env,
            replay_buffer_class=HerReplayBuffer,
            replay_buffer_kwargs=dict(
                n_sampled_goal=4,
                goal_selection_strategy="future",
            ),
            policy_kwargs=policy_kwargs,
            learning_rate=lr,
            buffer_size=buffer_size,
            learning_starts=1_000,
            batch_size=batch_size,
            tau=0.05,
            gamma=0.98,
            top_quantiles_to_drop_per_net=2,
            verbose=1,
            tensorboard_log=str(log_dir),
            device="cuda",
        )

    print(f"TQC 학습 시작 (mode={mode}, 총 1M step)...")
    model.learn(
        total_timesteps=1_000_000,
        callback=callbacks,
        reset_num_timesteps=(resume_path is None),
        tb_log_name=f"tqc_aic_{mode}",
    )

    save_path = str(model_dir / f"tqc_aic_{mode}_final")
    model.save(save_path)
    print(f"최종 모델 저장: {save_path}.zip")


def main():
    rmw = os.environ.get("RMW_IMPLEMENTATION", "")
    if not rmw:
        print("[train_tqc] 경고: RMW_IMPLEMENTATION 미설정. pixi run으로 실행하세요.")
    else:
        print(f"[train_tqc] RMW_IMPLEMENTATION={rmw}")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=["state", "image"], default="state",
        help="state: MLP만 사용 / image: ACT Transformer 인코더 사용"
    )
    parser.add_argument("--resume", type=str, default=None, help="재개할 모델 경로 (.zip)")
    args = parser.parse_args()

    # rclpy.init() 전에 Zenoh 라우터 시작 및 connect endpoint 설정
    # distrobox MuJoCo도 aic_zenoh_config.json5를 사용해야 같은 라우터를 바라봅니다
    router_proc = _setup_zenoh()
    print(f"[train_tqc] ZENOH_CONFIG_OVERRIDE={os.environ.get('ZENOH_CONFIG_OVERRIDE', '(unset)')}")
    try:
        train(mode=args.mode, resume_path=args.resume)
    finally:
        if router_proc is not None:
            router_proc.terminate()
            print(f"[train_tqc] Zenoh 라우터 종료 (PID={router_proc.pid})")


if __name__ == "__main__":
    main()
