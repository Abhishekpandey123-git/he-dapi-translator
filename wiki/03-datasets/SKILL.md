# Skill: dataset_streamer

You fix `src/models/datasets.py:26` OOM patterns for 3.7GB box.

## Before
- `PairedHEMITDataset.__getitem__` kept single `self._h5 = h5py.File(...)` shared across workers → fork dup fd, stale cache, `OSError: unable to open file (file locking disabled)`, and no chunk cache tuning → slow lzf decompress.
- No handling of HEMIT `mihc` 3ch vs `dapi` 1ch → crashed on `hemit_train_512.h5:38` when `dapi` missing.
- `UnpairedDataset` scanned PNGs only, ignoring HDF5 (`mhist_512.h5` 1.9G, `hemit_train` 3.7G) → forced PNG decode (CPU spike) + missing DAPI pngs → synthetic 8 fallback, wastes H5.
- Preloaded file list but no cache limit; `__del__` never closed H5 → fd leak after 1000 batches.
- No subset support for low-RAM smoke (`dummy` used Subset but still scanned 3000 files).

## After
- **Per-worker lazy open** `_get_h5()` with `SWMR=True, rdcc_nbytes=4MB, rdcc_nslots=10007` → safe with `num_workers>0`, amortizes lzf.
- **`indices` param** for low-RAM: `PairedHEMITDataset(..., indices=range(200))` → no need for `Subset` that still holds parent.
- **Auto `mihc` fallback**: if `dapi` missing, take `mihc[...,2]` (DAPI channel) → works with `hemit_train_512.h5`.
- **`__del__` close** + `gc` on fork.
- **Unpaired HDF5 fallback**: if `he_root` has <10 pngs, use `mhist_512.h5`; if `dapi_root` empty, use `hemit_train_512.h5`/`maxpmx`. Samples 50% from H5 to avoid PNG I/O spikes.
- **Cache**: `_he_cache` LRU 32 entries minor; but primary is H5 SWMR.

## Verify
```bash
.venv/bin/python -c "from src.models.datasets import PairedHEMITDataset; ds=PairedHEMITDataset(h5_path='data/processed/hemit_train_512.h5', patch_size=512); print(len(ds), ds[0]['he'].shape)"
.venv/bin/python -c "from src.models.datasets import UnpairedDataset; ds=UnpairedDataset('data/raw/mhist','data/raw/hemit/dapi', patch_size=256); print(len(ds), ds[0]['he'].shape)"
```
