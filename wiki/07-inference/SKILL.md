# Skill: infer_streamer

Fixes `src/models/infer.py:108` + `src/backend/main.py:40` WSI OOM.

## Before
- `load_image` loaded 40k×40k SVS via `asarray()` → 4.8GB → kill. Or `PIL.Image.open().load()` same.
- `infer_patch` did `img = load_image()` (full) then `tiles = list(extract_tiles(img))` + `results=[]` → 2× image + canvas → 6GB.
- No streaming flag; backend `translate` held `data` (500MB upload) + `tile` + `result` simultaneously → 1GB extra before GC.

## After
- **`load_image(..., max_size=2048)`**: checks `est_mb = w*h*3/1e6` vs `avail_mb`; if >50% avail or >512MB → `thumbnail(2048)` before `np.array`.
- **`infer_patch(..., stream=False)`**: probes tile to know `out_c`, est `est_mb = H*W*C*4/1e6`; if >512 or avail<800 → streaming. `tiler.infer_image(img, fn, out_path=tiff)` writes tiled TIFF via memmap bands, returns dummy 1×1 (no RAM).
- **`infer_wsi_streaming(wsi_path, out_path)`**: true zero-copy: `loader.read_region(x,y,512)` per tile, `run_torch_model` per tile, `merge_tiles_streaming(gen, out_shape, out_path)` → peak <512MB even for 40k.
- **`backend/main.py:40`**: RAM guard `used_pct>85 or avail<400 → 429`. Limits upload 500MB, thumbnails large PIL before numpy, streaming branch to temp tiff if est_out>512, then preview 2048 thumb for response.

## Verify
```bash
.venv/bin/python src/models/infer.py --input data/examples/he_example.png --direction he2dapi --out /tmp/out.png
.venv/bin/python src/models/infer.py --input data/examples/he_example.png --direction he2dapi --out /tmp/out.tiff --stream
# WSI (if large):
.venv/bin/python src/models/infer.py --input data/raw/wsi/CMU-1.svs --direction he2dapi --wsi --stream --out /tmp/wsi_stream.tiff
```

Files: `src/models/infer.py:17` (load guard), `108` (streaming), `src/backend/main.py:40` (429 guard)
