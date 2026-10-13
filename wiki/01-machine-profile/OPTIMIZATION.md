# Machine Profile — 3.7GB RAM WSL2

## Spec (Sep 19 2026)
- Intel i5-10210U 1.60GHz 4c/8t, 3.7GB RAM +1GB swap, no GPU, disk 867GB free.
- `free -h`: 1.2Gi used, 1.5Gi free, 1.2Gi buff/cache, 2.6Gi avail.
- `lscpu`: 8 vCPU, hypervisor Microsoft, L1d 128KiB×4.
- `nvidia-smi`: not found → CPU-only.

## Budgets enforced
- Per-process <1.5GB (leave 1GB OS), spike Δ <500MB/5s, throttles batch/DISTS.
- WSI canvas budget 512MB (vs 4.8GB for 20k² → must stream).
- Batch 512px: batch_size 2 (effective 8 via grad_accum 4) peak 18MB vs 75MB at 8.
- Swap avoid: avail<400MB → 429 in backend, not crash.

## Monitor logs
`wiki/01-machine-profile/profile.json` written by `ResourceMonitor` at each step. Check:
```bash
.venv/bin/python -m src.utils.resource_monitor --check
cat wiki/01-machine-profile/profile.json | python -m json.tool | tail
```
