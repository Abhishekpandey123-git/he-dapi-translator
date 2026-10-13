# Skill: orchestrator

You coordinate all sub-agents and ensure no crash on this 3.7GB box.

## Workflow (resumable, spike-guarded)

1. **Data** (`02`): `pack_hemit.py` streaming combined (peak 140MB). Resumable: skip if `he.shape[0]==len(pairs)`, atomic `.tmp→replace`, flush 500.
2. **Dataset** (`03`): lazy H5 SWMR per worker, subset support.
3. **Tiling** (`04`) + **WSI** (`05`): streaming merge to TIFF, not full canvas.
4. **Training** (`06`): batch 2 + grad_accum 4, DISTS off on CPU, num_workers 0, OOM try/catch.
5. **Inference** (`07`): stream if est>512MB, thumbnail guard.
6. **Backend** (`08`): 429 on `used_pct>85`.

## Orchestration files
- `Makefile` (targets: data, train-paired, train-unpaired, infer, health, clean)
- `wiki/README.md` (map)
- `docs/optimization/REPORT.md` (summary)

## Commands
```bash
make data       # pack hemit/bci streaming
make train-paired-dummy  # 4 samples, batch 2, checks monitor
make infer      # patch demo
make health     # resource check
```

## Recovery
Every long step is `nohup + tee + checkpoint`:
```bash
nohup .venv/bin/python pack_hemit.py 2>&1 | tee /tmp/pack_hemit.log &
# resume: re-run same command (skip if complete)
```

## Wiki skill invocation
Each folder `wiki/0X-*/SKILL.md` is agent prompt. To re-apply: `cat wiki/0X-*/SKILL.md` + edit linked file.
