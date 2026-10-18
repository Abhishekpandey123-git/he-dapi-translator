## What does this PR do?

<!-- One or two sentences. Link issues: "Closes #12". -->

## Type

- [ ] Bug fix
- [ ] Feature / model change
- [ ] Data / pipeline
- [ ] Docs
- [ ] CI/CD / infra

## Low-RAM guardrails (this project runs on a 3.7GB CPU box)

- [ ] No new full-array loads — streaming/memmap/lazy H5 preserved
- [ ] `batch_size ≤ 2`, `num_workers 0`, DISTS off (or justified otherwise)
- [ ] `PYTHONPATH=. python -m src.utils.progress_tracker --enforce` passes
- [ ] `PYTHONPATH=. python -m pytest tests/test_resource_guards.py` passes (11 green)
- [ ] No secrets/tokens added to tracked files (CI secret-scan blocks them)

## How was it tested?

<!-- command(s) run + observed result. If it changed training, keep the run resumable. -->
