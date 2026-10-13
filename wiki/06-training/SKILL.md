# Skill: train_cpu_optimizer

Fixes `src/models/train_paired.py:61` + `train_unpaired.py:54` OOM on 3.7GB CPU.

## Before (crash)
- Batch 8×512×512×3 float32 = 25MB ×3 grads =75MB but VGG DISTS `torchvision.models.vgg16` 528MB + grads → 1.2GB per batch → OOM on 2.6GB avail.
- `num_workers:8` in `hemit_dual_branch.yaml:9` → 8 forks each dup H5 handle + 200MB → 1.6GB extra → kill.
- `mixed_precision:true` on CPU → torch.cuda.amp fallback overhead, no benefit, extra cast.
- `PairedHEMITDataset` with `stain_norm: macenko` runs SVD per sample (O(N³) 512²) → 10ms ×8 =80ms + 2× RAM spike for OD matrix.
- No grad accumulation → must use large batch to mimic effective 8.
- No OOM catch → `RuntimeError: out of memory` kills whole run, no resume.

## After
- **Config**: `batch_size:2` (hemit) /2 (cyclegan, 4 nets), `grad_accum:4` → effective 8, peak 18MB vs 75MB.
- `num_workers:0` (WSL2 CPU safest), `mixed_precision:false`, `dists_on_cpu:false` (use_dists gate).
- `stain_norm:none` by default (enable after profiling), `max_cache_mb:4` for H5.
- `train_paired.py:61` now `train_one_epoch(..., grad_accum, oom_guard, monitor)`:
  - `/ grad_accum` loss scaling, `step` only every `grad_accum`.
  - Try/catch `RuntimeError OOM` → gc + skip.
  - Periodic `monitor.check` every 20 steps + gc.
  - `if not ensure_headroom(800)` → gc + weight map flush.
  - DISTS skipped if low RAM.
- `train_unpaired.py:54` same + `train_dummy(monitor, batch_size, grad_accum)` with advised batch.
- **Resume**: still `checkpoint_last.pt` every epoch, now also GC before save.

## Verify
```bash
.venv/bin/python src/models/train_paired.py --config configs/hemit_dual_branch.yaml --dummy --optimize-for lowram
# expect RAM peak <1.2GB, avail >1GB
.venv/bin/python -m src.utils.resource_monitor --check
cat wiki/06-training/profile_paired.json | tail -n 20
```

Files: `configs/hemit_dual_branch.yaml:35`, `configs/cyclegan_dapi2he.yaml:27`, `src/models/train_paired.py:1`, `src/models/train_unpaired.py:1`
