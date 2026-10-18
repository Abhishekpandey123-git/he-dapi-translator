# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project aims for
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.1.0] — 2026-10-18

First public milestone: streaming data pipeline, product-grade paired training
in progress, backend + Docker + CI/CD in place.

### Added
- **Data pipeline (streaming):** HEMIT 5,292 pairs (3717/630/945, 512px) via
  `hemit_extract.py` → `pack_hemit.py` (chunked copy, 10.6GB → 140MB peak);
  BCI HER2 and MHIST builders.
- **Models:** dual-branch Pix2Pix (CNN-ResNet + Swin + FMF fusion) for H&E→DAPI;
  CycleGAN fallback for DAPI→H&E; PatchGAN discriminator.
- **Training:** resumable `train_paired.py` / `train_unpaired.py`, per-epoch
  atomic checkpoints, `--resume auto`, OOM guard, grad-accum (eff. batch 8).
- **Inference:** patch + per-tile streaming WSI translation (`infer.py`,
  `infer_wsi_streaming`), ONNX export hook.
- **Backend:** FastAPI `/health`, `/models`, `/translate`, `/translate/wsi` with
  a 429 RAM guard; drag-and-drop frontend scaffold.
- **Low-RAM guardrails:** `ResourceMonitor`, streaming tiling/WSI, and
  `tests/test_resource_guards.py` (11 regression tests, mirrored in CI).
- **CI/CD:** `guards` on every push; `cd-staging` builds an immutable image to
  GHCR (paths-filtered); `cd-production` promote path (tag + env approval).
- **Operations:** crash-resume across reboots via cron `@reboot`+`*/5`
  `logs/boot_launch.sh`; progress tracker (`docs/progress.json`, `docs/TRACKER.md`).
- Docs: WORKPLAN, per-stage optimization wiki (9 tracks), Kaggle offload
  post-mortem, citation file, contributing guide, code of conduct.

### Status
- Paired training live at **181/200 epochs** (G-loss 2.2603 → 1.5302, best ep169).
- Full 630-image validation eval and Docker Hub mirror are on the roadmap.
