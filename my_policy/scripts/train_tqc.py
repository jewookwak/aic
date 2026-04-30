#!/usr/bin/env python3
"""
TQC + ACT Encoder Training Script for AIC Cable Insertion.

두 가지 모드:
  --mode state  : 상태 벡터만 사용 (기본 MLP, 빠른 학습)
  --mode image  : ACT Transformer 인코더 사용 (카메라 + 상태, 더 현실적)

Usage:
  # 터미널 1: 시뮬레이터 실행 (ground_truth 필수)
  ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true

  # 터미널 2: 학습 (상태 기반)
  pixi run python3 my_policy/scripts/train_tqc.py --mode state

  # 터미널 2: 학습 (ACT 인코더 + 이미지)
  pixi run python3 my_policy/scripts/train_tqc.py --mode image

  # 학습 재개
  pixi run python3 my_policy/scripts/train_tqc.py --mode image --resume logs/tqc_aic_image/best_model.zip

  # TensorBoard 모니터링
  pixi run tensorboard --logdir logs/
"""

import argparse
from pathlib import Path
from functools import partial

from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.her.her_replay_buffer import HerReplayBuffer
from sb3_contrib import TQC

from my_policy.aic_env import AICEnv


def make_env(use_images: bool) -> AICEnv:
    return AICEnv(use_images=use_images)


def train(mode: str = "state", resume_path: str | None = None):
    use_images = (mode == "image")
    log_dir   = Path(f"logs/tqc_aic_{mode}")
    model_dir = Path(f"models/tqc_aic_{mode}")
    log_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    env_fn  = partial(make_env, use_images=use_images)
    env     = DummyVecEnv([env_fn])
    eval_env = DummyVecEnv([env_fn])

    callbacks = [
        CheckpointCallback(
            save_freq=10_000,
            save_path=str(model_dir),
            name_prefix=f"tqc_aic_{mode}",
        ),
        EvalCallback(
            eval_env=eval_env,
            best_model_save_path=str(log_dir),
            log_path=str(log_dir),
            eval_freq=20_000,
            n_eval_episodes=5,
            deterministic=True,
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

    print(f"TQC 학습 시작 (mode={mode})...")
    model.learn(
        total_timesteps=1_000_000,
        callback=callbacks,
        reset_num_timesteps=(resume_path is None),
        tb_log_name=f"tqc_aic_{mode}",
    )

    save_path = str(model_dir / f"tqc_aic_{mode}_final")
    model.save(save_path)
    print(f"최종 모델 저장: {save_path}.zip")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=["state", "image"], default="state",
        help="state: MLP만 사용 / image: ACT Transformer 인코더 사용"
    )
    parser.add_argument("--resume", type=str, default=None, help="재개할 모델 경로 (.zip)")
    args = parser.parse_args()
    train(mode=args.mode, resume_path=args.resume)
