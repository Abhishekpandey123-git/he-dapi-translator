# Datasets

## Primary (Public, No Own Data)
- **HEMIT** — BEST for paired H&E <-> DAPI. 4278 patches 1024x1024, same-slide, 3717/630/945 split, DAPI/CD3/panCK. Source: ImmunoAIzer via https://arxiv.org/html/2403.18501v1 — contact authors or use derived. Use central 512x512 crop + Macenko norm.
- **MHIST** — 3152 H&E images, target domain for unpaired training (from Light-sheet paper) https://bmirds.github.io/MHIST/
- **CODEX VirtualHE_examples** — DAPI + Eosin -> H&E paired examples https://github.com/SimonsonLab/VirtualHE_examples
- **BCI** — H&E -> HER2 IHC (consecutive sections) structural-level, for testing unpaired generalization
- **TCGA / GDC** — WSI SVS for H&E WSI testing

## Scripts (to create)
- `download_hemit.sh` — wget huggingface or drive link after approval
- `download_mhist.sh` — wget https://bmirds.github.io/MHIST/
- `prepare_patches.py` — tiling, stain norm, HDF5 packing
- `verify_alignment.py` — check cellular alignment

Place raw in `data/raw/`, processed in `data/processed/`, examples in `data/examples/` (keep 1-2 samples for drag-drop demo).
