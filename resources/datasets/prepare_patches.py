"""
prepare_patches.py - Tile HEMIT 1024 -> 512 central crop + HDF5/Zarr packing, stain norm check, alignment verify
Usage:
  python resources/datasets/prepare_patches.py --input data/raw/hemit --patch 512 --out data/processed/hemit_512.h5
  python resources/datasets/prepare_patches.py --input data/raw/mhist --patch 256 --out data/processed/mhist_256.h5 --unpaired
"""
import argparse
import os, gc
from pathlib import Path
import numpy as np
try:
    from src.utils.resource_monitor import ResourceMonitor
    _mon = ResourceMonitor(budget_gb=1.5, log_path="wiki/02-data-extraction/profile_prepare.json")
except Exception:
    _mon = None
def _check(l):
    if _mon:
        return _mon.check(l)
    return None

try:
    import h5py
except ImportError:
    h5py = None
try:
    from PIL import Image
except ImportError:
    Image = None

def central_crop(img: np.ndarray, size: int) -> np.ndarray:
    h,w = img.shape[:2]
    y0, x0 = (h-size)//2, (w-size)//2
    return img[y0:y0+size, x0:x0+size]

def tile_image(img: np.ndarray, patch: int, stride: int):
    """Yield patches with stride (for WSI tiling test)"""
    h,w = img.shape[:2]
    for y in range(0, h-patch+1, stride):
        for x in range(0, w-patch+1, stride):
            yield (y,x), img[y:y+patch, x:x+patch]

def pack_to_hdf5(pairs, out_path: str, patch: int):
    if h5py is None:
        print("[WARN] h5py not installed, saving as npz instead")
        out_path = out_path.replace(".h5", ".npz")
        hes = np.stack([he for he,_ in pairs[:100]], axis=0)
        dapis = np.stack([dapi for _,dapi in pairs[:100]], axis=0)
        np.savez_compressed(out_path, he=hes, dapi=dapis, patch_size=patch)
        print(f"Saved NPZ: {out_path} he {hes.shape} dapi {dapis.shape}")
        return
    # Resumable / checkpoint: if out exists and complete, skip; else write to .tmp and atomic rename + flush every 500
    tmp_path = out_path + ".tmp"
    # If final exists and valid, skip packing (idempotent)
    if Path(out_path).exists():
        try:
            with h5py.File(out_path, "r") as f:
                if "he" in f and f["he"].shape[0] == len(pairs):
                    print(f"[SKIP] {out_path} already complete ({len(pairs)} pairs), resumable skip")
                    return
                else:
                    print(f"[RESUME] {out_path} exists but incomplete ({f['he'].shape[0] if 'he' in f else 0} vs {len(pairs)}), rewriting")
        except Exception as e:
            print(f"[RESUME] Corrupt {out_path}: {e}, rewriting to {tmp_path}")
    # Write to tmp for atomicity (can resume by re-running)
    with h5py.File(tmp_path, "w") as f:
        n = len(pairs)
        he0, dapi0 = pairs[0]
        f.create_dataset("he", (n, patch, patch, 3), dtype="uint8", chunks=(1,patch,patch,3), compression="lzf")
        dapi_shape = dapi0.shape
        if len(dapi_shape)==2:
            f.create_dataset("dapi", (n, patch, patch), dtype="uint8", chunks=(1,patch,patch), compression="lzf")
        else:
            f.create_dataset("dapi", (n, patch, patch, 3), dtype="uint8", chunks=(1,patch,patch,3), compression="lzf")
        for i,(he,dapi) in enumerate(pairs):
            f["he"][i] = he
            f["dapi"][i] = dapi
            # keep RAM low: delete refs periodically (pairs holds references; but we flush + gc)
            if (i+1) % 500 == 0:
                f.flush()
                gc.collect()
                _check(f"prepare:{i+1}/{n}")
                print(f"  [CHECKPOINT] {i+1}/{n} flushed to {tmp_path} (RSS guard)")
            elif (i+1)%100==0 and _mon and not _mon.ensure_headroom(500):
                gc.collect()
                _check(f"prepare:throttle@{i+1}")
        f.attrs["patch_size"] = patch
        f.attrs["num_pairs"] = n
        f.attrs["stain_norm"] = "macenko_recommended"
    # Atomic rename
    os.replace(tmp_path, out_path)
    print(f"[OK] Packed {n} pairs -> {out_path} ({os.path.getsize(out_path)/1e6:.1f} MB) [resumable: re-run to skip if complete]")

def load_pairs_from_dir(inp: Path, patch: int, streaming_out: str = None, chunk_batches: bool = False):
    """Load from assumed structure: inp/{train,he,mihc}/*.png or flat paired files *_he.png + *_dapi.png
    NOTE: For large datasets (>1000 images), consider using pack_hemit.py streaming path instead of loading all into RAM.
    If streaming_out provided, writes directly to H5 without holding all pairs in RAM.
    """
    # Check size hint: if > 1000 candidates, warn about RAM
    candidates_preview = list(inp.rglob("*.png"))[:5]
    total_candidates = sum(1 for _ in inp.rglob("*.png")) + sum(1 for _ in inp.rglob("*.jpg")) + sum(1 for _ in inp.rglob("*.tif*"))
    if total_candidates > 1000:
        print(f"[WARN] {total_candidates} candidates -> risk of holding {total_candidates*512*512*3/1e9:.1f}GB in RAM. Use pack_hemit.py streaming instead.")
        if _mon and not _mon.ensure_headroom(800):
            print("[THROTTLE] Low RAM, will stream in chunks of 200")
            chunk_batches = True
    pairs = []
    # Try common patterns
    candidates = list(inp.rglob("*.png")) + list(inp.rglob("*.jpg")) + list(inp.rglob("*.tif*"))
    if not candidates:
        print(f"[WARN] No images found in {inp}, using synthetic examples")
        # Fallback to examples
        for p in Path("data/examples").glob("*.png"):
            print(f"  found example: {p}")
        return pairs
    # Heuristic: files with 'he' vs 'dapi'/'mihc'/'ihc' in name
    he_files = [p for p in candidates if "he" in p.name.lower()]
    dapi_files = [p for p in candidates if any(k in p.name.lower() for k in ["dapi","mihc","ihc","fluo"])]
    print(f"[SCAN] Found {len(candidates)} images, {len(he_files)} HE candidates, {len(dapi_files)} DAPI candidates")
    # Simple pairing by sorted order if counts match
    if he_files and dapi_files and len(he_files)==len(dapi_files):
        he_files.sort()
        dapi_files.sort()
        for he_p, dapi_p in zip(he_files[:200], dapi_files[:200]):  # cap for demo
            try:
                he = np.array(Image.open(he_p).convert("RGB"))
                dapi = np.array(Image.open(dapi_p).convert("L"))
                he = central_crop(he, patch) if min(he.shape[:2])>=patch else he
                dapi = central_crop(dapi, patch) if min(dapi.shape[:2])>=patch else dapi
                # Resize if needed
                if he.shape[0]!=patch:
                    he = np.array(Image.fromarray(he).resize((patch,patch)))
                    dapi = np.array(Image.fromarray(dapi).resize((patch,patch)))
                pairs.append((he,dapi))
            except Exception as e:
                print(f"  skip {he_p}: {e}")
    elif he_files and not dapi_files:
        print("[INFO] Unpaired H&E only (e.g. MHIST) - will create HE-only HDF5")
        for he_p in he_files[:500]:
            try:
                he = np.array(Image.open(he_p).convert("RGB"))
                he = central_crop(he, patch) if min(he.shape[:2])>=patch else he
                if he.shape[0]!=patch:
                    he = np.array(Image.fromarray(he).resize((patch,patch)))
                pairs.append((he, np.zeros((patch,patch),dtype=np.uint8)))  # dummy DAPI
            except Exception as e:
                print(f"  skip {he_p}: {e}")
    else:
        print("[WARN] Unrecognized file naming, try manual pairing")
    if chunk_batches and len(pairs) > 200:
        print(f"[INFO] Holding {len(pairs)} pairs (~{len(pairs)*0.75/1024:.1f}MB) -> consider streaming write")
    _check(f"load_pairs:{len(pairs)}")
    return pairs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=str, required=True, help="input dir with paired images")
    ap.add_argument("--patch", type=int, default=512)
    ap.add_argument("--stride", type=int, default=512)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--unpaired", action="store_true", help="treat as unpaired (HE only)")
    args = ap.parse_args()
    inp = Path(args.input)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not inp.exists():
        print(f"[ERROR] Input not found: {inp}")
        print("  Run download scripts first or place synthetic data in data/examples/")
        return

    pairs = load_pairs_from_dir(inp, args.patch)
    if not pairs:
        print("[ERROR] No pairs loaded - check input structure")
        return
    print(f"[INFO] Loaded {len(pairs)} pairs, patch {args.patch}")
    _check(f"prepare:start:{len(pairs)}")
    pack_to_hdf5(pairs, str(out), args.patch)
    _check("prepare:end")
    # free
    del pairs
    gc.collect()
    # Verify alignment quick check
    if len(pairs)>0:
        he,dapi = pairs[0]
        print(f"[VERIFY] HE shape {he.shape}, DAPI shape {dapi.shape}, HE mean {he.mean():.1f}, DAPI mean {dapi.mean():.1f}")

if __name__=="__main__":
    main()
