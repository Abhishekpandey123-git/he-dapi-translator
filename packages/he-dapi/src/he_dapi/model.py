"""Generator architectures for H&E <-> DAPI virtual staining.

These mirror the architectures used in training (``src/models/train_paired.py``
and ``src/models/train_unpaired.py``) so published checkpoints load unchanged.
"""
from __future__ import annotations

import os
from pathlib import Path

import torch
import torch.nn as nn

HF_REPO_ID = "urbiologicalpa/he-dapi-translator"

# direction -> weight filename in the Hugging Face model repo
WEIGHT_FILES = {
    "he2dapi": "he2dapi_unet_epoch169.pt",
    # "dapi2he": "dapi2he_cyclegan_G.pt",  # added when unpaired training completes
}

INPUT_CHANNELS = {"he2dapi": 3, "dapi2he": 1}
OUTPUT_CHANNELS = {"he2dapi": 1, "dapi2he": 3}


class UNetGenerator(nn.Module):
    """Paired Pix2Pix generator: 3 -> 1 (H&E RGB -> DAPI).

    Input is expected in [-1, 1]; output is in [0, 1].
    """

    def __init__(self, in_ch: int = 3, out_ch: int = 1, ngf: int = 64):
        super().__init__()
        self.enc1 = nn.Sequential(nn.Conv2d(in_ch, ngf, 4, 2, 1), nn.LeakyReLU(0.2))
        self.enc2 = nn.Sequential(nn.Conv2d(ngf, ngf * 2, 4, 2, 1), nn.BatchNorm2d(ngf * 2), nn.LeakyReLU(0.2))
        self.enc3 = nn.Sequential(nn.Conv2d(ngf * 2, ngf * 4, 4, 2, 1), nn.BatchNorm2d(ngf * 4), nn.LeakyReLU(0.2))
        self.enc4 = nn.Sequential(nn.Conv2d(ngf * 4, ngf * 8, 4, 2, 1), nn.BatchNorm2d(ngf * 8), nn.LeakyReLU(0.2))
        self.dec4 = nn.Sequential(nn.ConvTranspose2d(ngf * 8, ngf * 4, 4, 2, 1), nn.BatchNorm2d(ngf * 4), nn.ReLU())
        self.dec3 = nn.Sequential(nn.ConvTranspose2d(ngf * 8, ngf * 2, 4, 2, 1), nn.BatchNorm2d(ngf * 2), nn.ReLU())
        self.dec2 = nn.Sequential(nn.ConvTranspose2d(ngf * 4, ngf, 4, 2, 1), nn.BatchNorm2d(ngf), nn.ReLU())
        self.dec1 = nn.Sequential(nn.ConvTranspose2d(ngf * 2, out_ch, 4, 2, 1), nn.Tanh())

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(e1)
        e3 = self.enc3(e2)
        e4 = self.enc4(e3)
        d4 = self.dec4(e4)
        d3 = self.dec3(torch.cat([d4, e3], 1))
        d2 = self.dec2(torch.cat([d3, e2], 1))
        d1 = self.dec1(torch.cat([d2, e1], 1))
        return (d1 + 1) / 2


def build_model(direction: str = "he2dapi", ngf: int = 64) -> nn.Module:
    if direction not in WEIGHT_FILES:
        raise ValueError(f"Unknown/unavailable direction {direction!r}; have {sorted(WEIGHT_FILES)}")
    return UNetGenerator(
        in_ch=INPUT_CHANNELS[direction],
        out_ch=OUTPUT_CHANNELS[direction],
        ngf=ngf,
    )


def resolve_weights(direction: str = "he2dapi", weights: str | os.PathLike | None = None) -> Path:
    """Return a local path to the weights, downloading from the HF Hub if needed."""
    if weights is not None:
        p = Path(weights)
        if not p.exists():
            raise FileNotFoundError(p)
        return p
    filename = WEIGHT_FILES[direction]
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(repo_id=HF_REPO_ID, filename=filename))


def load_generator(
    direction: str = "he2dapi",
    weights: str | os.PathLike | None = None,
    device: str = "cpu",
    ngf: int = 64,
) -> nn.Module:
    """Build the generator for ``direction`` and load its published weights."""
    model = build_model(direction, ngf=ngf)
    state = torch.load(resolve_weights(direction, weights), map_location=device)
    if isinstance(state, dict) and direction == "he2dapi" and "G" in state:
        state = state["G"]
    model.load_state_dict(state)
    model.to(device).eval()
    return model
