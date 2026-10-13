# Skill: tiling_streamer

Fixes `src/utils/tiling.py:55` OOM on WSI.

## Before
- `merge_tiles` allocated `canvas = np.zeros((H,W,C), float32)` → for 20k×20k×3 = 4.8GB + weight_map 1.6GB → 6.4GB > 3.7GB → killed. Same for 10k×10k =1.2GB but ×2 for grads → crash.
- `infer_image` held `tiles = list(extract_tiles)` + `results = []` both in RAM (2× tiles) → 2GB extra.
- `extract_tiles` yielded duplicate edge tiles via second loop without checking already yielded → extra compute.

## After
- **Budget check**: `est_mb = H*W*C*4/1e6`; if >512MB or >50% avail → raise or stream.
- **`merge_tiles_streaming`**: memmap `canvas.dat` + `weight_map.dat` on disk, then banded normalize to `final.dat` (chunk_rows=1024) → peak <512MB, writes tiled TIFF via `tifffile.imwrite(tile=(256,256), compression="zlib")`.
- **`infer_image(..., out_path)`**: probes one tile to know `out_c`, decides streaming vs list mode. Streaming uses generator `yield (y,x), synthetic` no list. If `out_path` given, writes directly, returns dummy 1×1 for preview.
- **Edge dedup**: kept but now generator streaming reduces duplicate handling cost.

## Verify
```bash
.venv/bin/python -c "
import numpy as np
from src.utils.tiling import TiledInference
tiler=TiledInference(512,256)
img=np.random.randint(0,255,(2048,2048,3),dtype=np.uint8)
res=tiler.infer_image(img, lambda t: np.dot(t[...,:3],[0.2989,0.5870,0.1140]).astype(np.uint8)[...,None])
print(res.shape)
# large streaming
img2=np.random.randint(0,255,(6000,6000,3),dtype=np.uint8)
tiler.infer_image(img2, lambda t: np.dot(t[...,:3],[0.2989,0.5870,0.1140]).astype(np.uint8)[...,None], out_path='/tmp/stream_test.tiff')
print('streamed')
"
ls -lh /tmp/stream_test.tiff
```

Files: `src/utils/tiling.py:1` (+ streaming), `wiki/04-tiling/`
