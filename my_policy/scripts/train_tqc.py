#!/usr/bin/env python3
"""
TQC Training Script for AIC Cable Insertion.

Usage:
  # 터미널 1: 시뮬레이터 실행
  ros2 launch aic_mujoco aic_mujoco_bringup.launch.py ground_truth:=true

  # 터미널 2: 학습 실행
  pixi run python3 my_policy/scripts/train_tqc.py

  # 학습 재개
  pixi run python3 my_policy/scripts/train_tqc.py --resume logs/tqc_aic/best_model.zip
"""

import argparse
from pathlib import Path

from stable_baselines3.common.callbacks import (
    CheckpointCallback,
    EvalCallback,
)
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.her.her_replay_buffer import HerReplayBuffer
from sb3_contrib import TQC

from my_policy.aic_env import AICEnv

LOG_DIR = Path("logs/tqc_aic")
MODEL_DIR = Path("models/tqc_aic")


def make_env():
    return AICEnv()


def train(resume_path: str | None = None):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    env = DummyVecEnv([make_env])

    callbacks = [
        CheckpointCallback(
            save_freq=10_000,
            save_path=str(MODEL_DIR),
            name_prefix="tqc_aic",
        ),
        EvalCallback(
            eval_env=DummyVecEnv([make_env]),
            best_model_save_path=str(LOG_DIR),
            log_path=str(LOG_DIR),
            eval_freq=20_000,
            n_eval_episodes=5,
            deterministic=True,
        ),
    ]

    if resume_path:
        print(f"학습 재개: {resume_path}")
        model = TQC.load(resume_path, env=env)
    else:
        model = TQC(
            policy="MultiInputPolicy",     # Dict observation space 지원
            env=env,
            replay_buffer_class=HerReplayBuffer,
            replay_buffer_kwargs=dict(
                n_sampled_goal=4,          # HER: 에피소드당 추가 목표 샘플 수
                goal_selection_strategy="future",
            ),
            learning_rate=1e-3,
            buffer_size=1_000_000,
            learning_starts=1_000,
            batch_size=512,
            tau=0.05,
            gamma=0.98,
            top_quantiles_to_drop_per_net=2,
            verbose=1,
            tensorboard_log=str(LOG_DIR),
            device="cuda",
        )

    print("TQC 학습 시작...")
    model.learn(
        total_timesteps=1_000_000,
        callback=callbacks,
        reset_num_timesteps=(resume_path is None),
        tb_log_name="tqc_aic",
    )

    save_path = str(MODEL_DIR / "tqc_aic_final")
    model.save(save_path)
    print(f"최종 모델 저장: {save_path}.zip")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", type=str, default=None, help="재개할 모델 경로 (.zip)")
    args = parser.parse_args()
    train(resume_path=args.resume)
