"""Smoke tests for module setup"""
def test_utils_imports():
    from src.utils.stain_norm import MacenkoNormalizer, ReinhardNormalizer
    from src.utils.tiling import TiledInference
    from src.utils.wsi_loader import WSILoader
    assert TiledInference

def test_datasets_imports():
    from src.models.datasets import PairedHEMITDataset, UnpairedDataset
    ds = PairedHEMITDataset(patch_size=64)
    assert len(ds) >= 1
    sample = ds[0]
    assert "he" in sample and "dapi" in sample
    # torch installed -> tensor 3xHxW, else numpy HxWx3 fallback
    try:
        import torch
        has_torch = True
    except ImportError:
        has_torch = False
    if has_torch:
        assert sample["he"].shape[0]==3
        assert sample["dapi"].shape[0]==1
    else:
        assert sample["he"].shape==(64,64,3) or sample["he"].shape[0]==3
        assert sample["dapi"].shape==(64,64) or sample["dapi"].shape[0]==1

def test_tiling_merge():
    import numpy as np
    from src.utils.tiling import TiledInference
    tiler = TiledInference(tile_size=64, stride=32)
    img = np.random.randint(0,255,(128,128,3),dtype=np.uint8)
    def dummy(tile): return 255-tile
    out = tiler.infer_image(img, dummy)
    assert out.shape==(128,128,3)

def test_infer_patch(tmp_path):
    import numpy as np
    from PIL import Image
    from src.models.infer import run_torch_model
    tile = np.random.randint(0,255,(64,64,3),dtype=np.uint8)
    # Don't require torch - fallback dummy should work
    res = run_torch_model(tile, "he2dapi")
    assert res.shape in [(64,64),(64,64,1),(64,64,3)]
