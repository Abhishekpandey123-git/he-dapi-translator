"""Patch + tiled inference for H&E <-> DAPI virtual staining."""
from __future__ import annotations

import numpy as np
import torch
from PIL import Image

from .model import load_generator

TILE = 512
STRIDE = 256
_MULT = 16  # 4 downsamplings in the UNet


def _as_rgb_uint8(image) -> np.ndarray:
    """Accept a path, PIL image, or array -> HxWx3 uint8 RGB."""
    if isinstance(image, (str, bytes)) or hasattr(image, "__fspath__"):
        return np.array(Image.open(image).convert("RGB"))
    if isinstance(image, Image.Image):
        return np.array(image.convert("RGB"))
    arr = np.asarray(image)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr[..., :3]


@torch.no_grad()
def _infer_patch(model, he_uint8: np.ndarray, device: str) -> np.ndarray:
    h, w = he_uint8.shape[:2]
    ph, pw = (-h) % _MULT, (-w) % _MULT
    if ph or pw:
        he_uint8 = np.pad(he_uint8, ((0, ph), (0, pw), (0, 0)), mode="reflect")
    t = torch.from_numpy(np.ascontiguousarray(he_uint8)).permute(2, 0, 1).float() / 127.5 - 1.0
    out = model(t.unsqueeze(0).to(device))[0, 0].clamp(0, 1).cpu().numpy()
    return out[:h, :w]


def _positions(total: int) -> list[int]:
    if total <= TILE:
        return [0]
    pos = list(range(0, total - TILE + 1, STRIDE))
    if pos[-1] != total - TILE:
        pos.append(total - TILE)
    return pos


def translate(
    image,
    direction: str = "he2dapi",
    model=None,
    weights=None,
    device: str = "cpu",
    tile: int = TILE,
    stride: int = STRIDE,
) -> np.ndarray:
    """Virtual-stain ``image`` and return a uint8 array.

    For the paired direction this returns an ``HxW`` grayscale DAPI image.
    Large inputs are processed in 512px tiles with overlap averaging.
    """
    he = _as_rgb_uint8(image)
    if model is None:
        model = load_generator(direction, weights=weights, device=device)
    H, W = he.shape[:2]

    if max(H, W) <= tile:
        pred = _infer_patch(model, he, device)
    else:
        acc = np.zeros((H, W), np.float32)
        cnt = np.zeros((H, W), np.float32)
        for y in _positions(H):
            for x in _positions(W):
                pred_t = _infer_patch(model, he[y:y + tile, x:x + tile], device)
                acc[y:y + tile, x:x + tile] += pred_t
                cnt[y:y + tile, x:x + tile] += 1.0
        pred = acc / np.maximum(cnt, 1e-6)

    return (pred * 255).astype(np.uint8)


def translate_to_file(image, out_path, **kwargs) -> str:
    """Run :func:`translate` and save the result as an image file."""
    result = translate(image, **kwargs)
    Image.fromarray(result, mode="L" if result.ndim == 2 else "RGB").save(out_path)
    return str(out_path)
