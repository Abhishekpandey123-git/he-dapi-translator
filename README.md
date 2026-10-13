# H&E <-> DAPI Drag & Drop Translator

Bi-directional virtual staining tool: H&E <-> DAPI for both WSI and single patches.
- Drag & drop UI (web + napari plugin)
- PyTorch backend with Docker for Docker Hub deployment
- Supports paired (Pix2Pix) and unpaired (CycleGAN/CUT/Diffusion) training

## Structure
```
/he-dapi-translator
├── docs/                  # Workplan, novelty report, specs
├── resources/papers/      # Literature
├── resources/datasets/    # Dataset links & prep scripts
├── resources/models/      # Model cards
├── data/raw,processed,examples
├── src/frontend           # React drag-drop UI
├── src/backend            # FastAPI inference server
├── src/models             # Training & inference code
├── docker/                # Dockerfile + compose for Docker Hub
└── notebooks/             # Experiments
```

## Quick Start (after docker build)
```bash
docker build -t he-dapi-translator -f docker/Dockerfile .
docker run -p 8000:8000 -p 3000:3000 he-dapi-translator
# Frontend -> http://localhost:3000  Backend -> http://localhost:8000/docs
```

See `docs/WORKPLAN.md`, `docs/TRACKER.md` (38% Phase1 DONE), `docs/optimization/REPORT.md` and `wiki/README.md` for low-RAM guards.

## Tracker (low-RAM till end)
```bash
PYTHONPATH=. .venv/bin/python -m src.utils.progress_tracker --check      # 38% overall
PYTHONPATH=. .venv/bin/python -m src.utils.progress_tracker --enforce    # all guards ✅
cat docs/progress.json | python -m json.tool
```
