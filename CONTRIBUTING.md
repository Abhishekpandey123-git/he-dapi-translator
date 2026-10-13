# Contributing

Thanks for stopping by — this project is **actively building in public** and contributions are welcome, from docs fixes to training optimizations.

## Where help matters most

Pick an open [Issue](https://github.com/urbiologicalpa/he-dapi-translator/issues) — good starters:

- Docs / README figures and clarifications
- Frontend: Dropzone + OpenSeadragon WSI progress UI
- Eval: extending `src/models/eval_offline.py` (more metrics, more splits)
- Anything that lowers peak RAM without hurting quality

No need to ask permission — comment on the issue, fork, PR.

## Ground rules (this repo trains on a 3.7GB laptop)

1. **Streaming by default** — never load a full H5/WSI into RAM. If peak rises >500MB on an existing flow, the PR isn't ready.
2. **Guards must stay green** — `PYTHONPATH=. python -m pytest tests/test_resource_guards.py` (11 tests) + `progress_tracker --enforce`. CI runs both on every push.
3. **Never commit**: datasets/checkpoints (`*.h5`, `*.pt` — gitignored), logs, tokens/keys (use env vars: `HF_TOKEN`, `KAGGLE_API_TOKEN`). Push protection is on and *will* block secrets.
4. **Small, resumable steps** — long work must checkpoint so a crash doesn't lose it (see `watch_runs.sh` / keepalive pattern in `wiki/09-orchestration/`).

## Setup (CPU)

```bash
uv pip install --python .venv/bin/python torch torchvision --index-url https://download.pytorch.org/whl/cpu
uv pip install -r docker/requirements.txt
PYTHONPATH=. python -m pytest tests/test_resource_guards.py -v
```

Questions? Open a [Discussion](https://github.com/urbiologicalpa/he-dapi-translator/discussions) — maintainers answer there.
