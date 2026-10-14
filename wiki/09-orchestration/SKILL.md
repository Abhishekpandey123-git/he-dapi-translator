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

## Token & push-auth map (reboot-safe — lesson 2026-10-14, do NOT re-break)
All tokens live as `600` files in `$HOME` (outside repo — CI secret-scan blocks
`ghp_/KGAT_` patterns in tracked files). Exact names matter: on 2026-10-14 a push
failed 3x because the agent looked for `~/.git_pat` while the real file is
`~/.github_pat`. Always `ls ~` first, never guess the filename.

| Token | File (`chmod 600`) | Used by |
|-------|--------------------|---------|
| GitHub PAT | `~/.github_pat` | `git push` via credential helper (below) |
| Kaggle API | `~/.kaggle/api_token` | `watch_runs.sh` via `KAGGLE_API_TOKEN=$(cat ~/.kaggle/api_token)` |
| HuggingFace | `~/.hf_token` | manual HF uploads only |

```bash
ls -l ~/.github_pat ~/.kaggle/api_token ~/.hf_token   # verify exist, mode 600
# one-time: wire GitHub PAT into git (survives reboot, never commit it)
git config credential.helper '!f() { echo username=urbiologicalpa; echo password=$(cat ~/.github_pat); }; f'
git push origin main   # must print "main -> main"; if "Authentication failed", re-check filename/perms
```

## Reboot recovery (week-mode relaunch order — lesson 2026-10-14)
1. Ground truth = `resources/models/checkpoints/he2dapi/checkpoint_epoch*.pt` count + `checkpoint_last.pt` (`torch.load` → `epoch`/`loss`); tracker files are secondary.
2. Relaunch train FIRST: `setsid nohup nice -n 10 env PYTHONPATH=. .venv/bin/python -u -m src.models.train_paired --config configs/hemit_dual_branch.yaml --resume auto --optimize-for lowram >> logs/train_paired.log 2>&1 < /dev/null &` — confirm `step20` line appears (~4 min).
3. Then watch (`setsid nohup bash watch_runs.sh ...`, pid → `logs/watch.pid`) + keepalive (`setsid nohup bash logs/keepalive_week.sh ...`, pid → `logs/keepalive.pid`).
4. Keepalive restarts BOTH train and watch if dead (watch-guard added 2026-10-14 after watch died silently 1h pre-reboot). After editing it, kill + relaunch keepalive to reload.
5. Sync triple: `docs/progress.json:runs` + `docs/TRACKER.md` (Live Runs + Daily Log) + `MEMORY.md` banner, then commit + push (auth above).

## Wiki skill invocation
Each folder `wiki/0X-*/SKILL.md` is agent prompt. To re-apply: `cat wiki/0X-*/SKILL.md` + edit linked file.
