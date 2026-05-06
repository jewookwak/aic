#!/usr/bin/env python3
"""AicMujocoRealEnv CheatCode 테스트 스크립트.

distrobox 터미널에서 실행:
  distrobox enter aic_eval
  python3 ~/ws_aic/src/aic/my_policy/scripts/run_real_env.py
"""
import sys, os
sys.path.insert(0, os.path.expanduser("~/ws_aic/src/aic/my_policy"))

os.environ.setdefault("HILSERL_RANDOMIZE", "0")
os.environ.setdefault("AIC_COLLISION_STIFF", "0")
os.environ.setdefault("HILSERL_RENDER", "1")
os.environ.setdefault("AIC_VIEW_SLOWDOWN_S", "0.02")  # ~50fps

from my_policy.aic_mujoco_real_env import AicMujocoRealEnv

print("env 생성 중...")
env = AicMujocoRealEnv(max_steps=600, image_size=(64, 64))

print("reset 중...")
obs, info = env.reset()
print(f"start dist: {info['dist_m']:.3f}m")

for step in range(600):
    a = env.cheatcode_action()
    obs, r, term, trunc, info = env.step(a)
    if step % 50 == 0:
        print(f"step {step:3d}: dist={info['dist_m']:.4f}m  reward={r:.3f}")
    if term or trunc:
        score = info.get("eval_score", {})
        print(f"\n종료 @ step {step+1}: dist={info['dist_m']:.4f}m")
        print(f"eval_score: {score}")
        break

env.close()
print("완료!")
