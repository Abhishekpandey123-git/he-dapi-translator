"""Tests for the he-dapi inference library + CLI."""
import numpy as np
import pytest


def test_version():
    import he_dapi

    assert he_dapi.__version__


def test_as_rgb_uint8_accepts_array_and_pil():
    from PIL import Image

    from he_dapi.translate import _as_rgb_uint8

    arr = (np.random.rand(20, 30, 3) * 255).astype(np.uint8)
    assert _as_rgb_uint8(arr).shape == (20, 30, 3)

    gray = (np.random.rand(20, 30) * 255).astype(np.uint8)
    assert _as_rgb_uint8(gray).shape == (20, 30, 3)

    assert _as_rgb_uint8(Image.fromarray(arr)).shape == (20, 30, 3)


def test_build_model_forward():
    torch = pytest.importorskip("torch")
    from he_dapi import build_model

    model = build_model("he2dapi").eval()
    with torch.no_grad():
        out = model(torch.randn(1, 3, 64, 64))
    assert tuple(out.shape) == (1, 1, 64, 64)
    assert 0.0 <= float(out.min()) and float(out.max()) <= 1.0


@pytest.mark.parametrize("h,w", [(96, 128), (100, 130)])
def test_translate_synthetic(h, w):
    pytest.importorskip("torch")
    from he_dapi import build_model, translate

    model = build_model("he2dapi")
    img = (np.random.rand(h, w, 3) * 255).astype(np.uint8)
    pred = translate(img, model=model)
    assert pred.dtype == np.uint8
    assert pred.shape == (h, w)  # padding is cropped back to the input size


def test_cli_info(capsys):
    from he_dapi.cli import main

    assert main(["info"]) == 0
    out = capsys.readouterr().out
    assert "he-dapi" in out
    assert "he2dapi" in out
