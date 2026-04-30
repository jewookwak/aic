"""
ACT Transformer Encoder as SB3 BaseFeaturesExtractor for TQC.

Architecture:
  [camera images × 3] → ResNet backbone → image tokens (H'×W' per cam)
  [robot state 26-dim] → linear proj     → state token
  [latent = zeros]    → linear proj     → latent token
  [latent, state, *img_tokens] → ACT Transformer Encoder → encoder_out (N, B, D)
  mean_pool(encoder_out) concat [achieved_goal, desired_goal] → Linear → features_dim

SB3 preprocesses uint8 images to float [0,1] before calling the extractor.
This extractor then applies ACT's dataset-specific mean/std normalization on top.

Usage in TQC:
    policy_kwargs = dict(
        features_extractor_class=ACTFeaturesExtractor,
        features_extractor_kwargs=dict(
            repo_id="grkw/aic_act_policy",
            features_dim=512,
            freeze_encoder=True,
        ),
    )
    model = TQC("MultiInputPolicy", env, policy_kwargs=policy_kwargs, ...)
"""

import json
import torch
import torch.nn as nn
import torch.nn.functional as F
import einops
import numpy as np
from pathlib import Path
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from huggingface_hub import snapshot_download
from safetensors.torch import load_file
import draccus


# 카메라 obs key → ACT stats key 매핑
_CAM_KEY_MAP = {
    "left_image":   "left_camera",
    "center_image": "center_camera",
    "right_image":  "right_camera",
}


class ACTFeaturesExtractor(BaseFeaturesExtractor):
    """
    ACT Transformer 인코더를 SB3 features extractor로 사용.

    Args:
        observation_space : Dict obs space (image keys + state + goals 포함)
        repo_id           : HuggingFace ACT 모델 repo ID
        features_dim      : 출력 feature 차원
        freeze_encoder    : True면 ACT 가중치 동결 (TQC만 학습)
        img_size          : (H, W) 이미지 리사이즈 크기
    """

    def __init__(
        self,
        observation_space: spaces.Dict,
        repo_id: str = "grkw/aic_act_policy",
        features_dim: int = 512,
        freeze_encoder: bool = True,
        img_size: tuple[int, int] = (84, 84),
    ):
        super().__init__(observation_space, features_dim)

        from lerobot.policies.act.modeling_act import ACTPolicy
        from lerobot.policies.act.configuration_act import ACTConfig

        # ACT 모델 다운로드 및 로드
        policy_path = Path(snapshot_download(
            repo_id=repo_id,
            allow_patterns=["config.json", "model.safetensors", "*.safetensors"],
        ))
        with open(policy_path / "config.json") as f:
            config_dict = json.load(f)
            config_dict.pop("type", None)
        config = draccus.decode(ACTConfig, config_dict)

        act = ACTPolicy(config)
        act.load_state_dict(load_file(policy_path / "model.safetensors"))
        act.eval()

        # Encoder 컴포넌트만 추출 (Decoder / action_head 제외)
        self.backbone                    = act.model.backbone
        self.transformer_encoder         = act.model.encoder
        self.encoder_img_feat_proj       = act.model.encoder_img_feat_input_proj
        self.encoder_state_proj          = act.model.encoder_robot_state_input_proj
        self.encoder_latent_proj         = act.model.encoder_latent_input_proj
        self.encoder_1d_pos_embed        = act.model.encoder_1d_feature_pos_embed
        self.encoder_cam_pos_embed       = act.model.encoder_cam_feat_pos_embed
        self.dim_model = config.dim_model

        # 이미지 정규화 통계 (dataset-specific, ACT 학습 시 사용한 값)
        stats_file = policy_path / "policy_preprocessor_step_3_normalizer_processor.safetensors"
        stats = load_file(stats_file)
        for obs_key, cam_key in _CAM_KEY_MAP.items():
            self.register_buffer(
                f"mean_{obs_key}",
                stats[f"observation.images.{cam_key}.mean"].view(1, 3, 1, 1)
            )
            self.register_buffer(
                f"std_{obs_key}",
                stats[f"observation.images.{cam_key}.std"].view(1, 3, 1, 1)
            )

        # ACT 가중치 동결 여부
        if freeze_encoder:
            for module in [
                self.backbone, self.transformer_encoder,
                self.encoder_img_feat_proj, self.encoder_state_proj,
                self.encoder_latent_proj, self.encoder_1d_pos_embed,
                self.encoder_cam_pos_embed,
            ]:
                for p in module.parameters():
                    p.requires_grad = False

        self.img_size = img_size

        # 출력 헤드: mean_pool(encoder_out) + goal → features_dim
        # achieved_goal(3) + desired_goal(3) = 6
        self.output_proj = nn.Linear(self.dim_model + 6, features_dim)

    # ------------------------------------------------------------------
    # 이미지 전처리
    # ------------------------------------------------------------------

    def _preprocess_img(self, img: torch.Tensor, obs_key: str) -> torch.Tensor:
        """
        SB3가 uint8 이미지를 [0,1] float로 정규화한 후 전달합니다.
        여기서는 (B, H, W, C) → (B, C, H, W) 변환 후 ACT stats 적용.
        """
        # (B, H, W, C) → (B, C, H, W)
        x = img.float().permute(0, 3, 1, 2)

        # 리사이즈
        if x.shape[-2:] != self.img_size:
            x = F.interpolate(x, size=self.img_size, mode="bilinear", align_corners=False)

        # ACT 학습 시 사용한 mean/std 정규화
        mean = getattr(self, f"mean_{obs_key}")
        std = getattr(self, f"std_{obs_key}")
        return (x - mean) / std

    # ------------------------------------------------------------------
    # Forward
    # ------------------------------------------------------------------

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        device = observations["observation"].device
        batch_size = observations["observation"].shape[0]

        # ── 1. 1D 토큰: [latent, state] ──────────────────────────────
        latent = torch.zeros(batch_size, self.encoder_latent_proj.in_features, device=device)
        latent_token = self.encoder_latent_proj(latent)          # (B, D)

        state = observations["observation"].float()
        state_token = self.encoder_state_proj(state)             # (B, D)

        encoder_in_tokens   = [latent_token, state_token]
        encoder_in_pos_embed = list(self.encoder_1d_pos_embed.weight.unsqueeze(1))  # [(1, D), (1, D)]

        # ── 2. 이미지 토큰: 카메라별 ResNet → projection → flatten ──
        for obs_key in _CAM_KEY_MAP:
            img = self._preprocess_img(observations[obs_key], obs_key)  # (B, 3, H, W)
            feat_map = self.backbone(img)["feature_map"]                # (B, C_back, H', W')
            cam_pos  = self.encoder_cam_pos_embed(feat_map).to(feat_map.dtype)
            feat_proj = self.encoder_img_feat_proj(feat_map)            # (B, D, H', W')

            feat_tokens = einops.rearrange(feat_proj, "b c h w -> (h w) b c")
            pos_tokens  = einops.rearrange(cam_pos,   "b c h w -> (h w) b c")

            encoder_in_tokens.extend(list(feat_tokens))
            encoder_in_pos_embed.extend(list(pos_tokens))

        # ── 3. 토큰 스택 → Transformer Encoder ──────────────────────
        tokens    = torch.stack(encoder_in_tokens,    dim=0)  # (N, B, D)
        pos_embed = torch.stack(encoder_in_pos_embed, dim=0)  # (N, 1 or B, D)

        encoder_out = self.transformer_encoder(tokens, pos_embed=pos_embed)  # (N, B, D)

        # ── 4. Mean pooling + goal concat → output projection ────────
        pooled = encoder_out.mean(dim=0)                       # (B, D)

        goal = torch.cat([
            observations["achieved_goal"].float(),
            observations["desired_goal"].float(),
        ], dim=-1)                                             # (B, 6)

        combined = torch.cat([pooled, goal], dim=-1)           # (B, D+6)
        return self.output_proj(combined)                      # (B, features_dim)
