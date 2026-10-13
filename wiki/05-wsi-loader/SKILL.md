# Skill: wsi_streamer

Fixes `src/utils/wsi_loader.py:13` OOM via `asarray()`.

## Before
- `get_thumbnail` did `self._tifffile.asarray()` → loads full WSI (44G HEMIT .tif is 1024×1024 but WSI 40k×40k = 4.8GB) → OOM, crash observed.
- `read_region` also `asarray()` then crop → 2× RAM (full + region) → killed.
- No level handling: SVS has pyramid, tifffile series.levels not used.
- PIL fallback loaded whole image via `Image.open().load()` → same.

## After
- **Thumbnail**: check `series.levels` for downsampled level closest to `max_size`; use `level.asarray()` (small). Fallback: `series.aszarr()` + `zarr[::4,::4]` virtual slice (no RAM). Last fallback: `page.asarray()[::4,::4]` with RAM guard (`est_mb > avail*0.5` → subsample).
- **Region**: use `series.aszarr()` → `zarr.open(store)` → slice `z[y:y+h, x:x+w]` without loading full. Handles CHW vs HWC via transpose of slice only (not full). If zarr fails, fallback to `asarray` but with RAM warning + `get_ram_state()` budget.
- **Budget**: `get_ram_state()` check before any full load; warns if WSI >50% avail.

## Verify
```bash
.venv/bin/python -c "
from src.utils.wsi_loader import WSILoader
loader=WSILoader('data/raw/wsi/CMU-1.svs')  # or any tif
print(loader.level_dimensions, loader._backend)
thumb=loader.get_thumbnail(512)
print('thumb', thumb.shape)
patch=loader.read_region(0,0,size=(512,512))
print('patch', patch.shape)
"
```

Files: `src/utils/wsi_loader.py:76` (thumbnail), `105` (region)
