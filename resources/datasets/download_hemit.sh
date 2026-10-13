#!/usr/bin/env bash
# download_hemit.sh - HEMIT paired H&E <-> mIHC (DAPI/CD3/panCK)
# Paper: Bian et al. MICCAI 2024 https://arxiv.org/html/2403.18501v1
# Dataset: 4278 pairs, 1024x1024, same-slide cellular alignment, ImmunoAIzer
# NOTE: HEMIT requires author approval / HuggingFace gated access. This script tries public mirrors.
set -e
ROOT="data/raw/hemit"
mkdir -p "$ROOT" data/processed data/examples

echo "[HEMIT] Target: $ROOT"

# Try HuggingFace (if public) - replace with actual repo when available
# Option A: Direct from authors (request via email immunoaizer)
HF_URL="https://huggingface.co/datasets/ImmunoAIzer/HEMIT/resolve/main"
# Option B: GitHub clone of training code often contains download script
GITHUB_REPO="https://github.com/BianLab/HEMIT"

if command -v huggingface-cli &>/dev/null; then
  echo "[HEMIT] Trying huggingface-cli download..."
  huggingface-cli download ImmunoAIzer/HEMIT --repo-type dataset --local-dir "$ROOT" || echo "[HEMIT] HF gated - request access at https://huggingface.co/datasets/ImmunoAIzer/HEMIT"
else
  echo "[HEMIT] huggingface-cli not found, trying wget..."
  # Placeholder wget - will 404 until public link confirmed
  wget -P "$ROOT" "${HF_URL}/hemit_1024.zip" || echo "[HEMIT] Direct wget failed - dataset is gated. Follow manual steps:"
fi

cat << 'MANUAL'
[MANUAL STEPS if gated]
1. Visit https://arxiv.org/html/2403.18501v1 -> contact authors or HF dataset page
2. Request HEMIT access (academic email)
3. Once approved: huggingface-cli download ImmunoAIzer/HEMIT --repo-type dataset --local-dir data/raw/hemit
4. Expected structure:
   data/raw/hemit/
     train/he/*.png  train/mihc/*.png  (or combined)
     val/ ...
     test/ ...
     metadata.csv
5. Then run: python resources/datasets/prepare_patches.py --input data/raw/hemit --patch 512 --out data/processed/hemit_512.h5
MANUAL

# Fallback: create synthetic paired example for pipeline testing (2x2 patches)
if [ ! -f "$ROOT/metadata.csv" ]; then
  echo "[HEMIT] Creating synthetic mini-example for pipeline testing..."
  mkdir -p data/examples
  python3 - << 'PY' || echo "synthetic gen needs numpy/PIL - skipping"
import numpy as np
from PIL import Image
import os
os.makedirs("data/examples", exist_ok=True)
rng = np.random.default_rng(0)
# Fake H&E RGB
he = rng.integers(0,255,(512,512,3),dtype=np.uint8)
Image.fromarray(he).save("data/examples/he_example.png")
# Fake DAPI grayscale (nuclei-like dots)
dapi = rng.integers(0,40,(512,512),dtype=np.uint8)
for _ in range(200):
    x,y = rng.integers(0,512,2)
    dapi[max(0,y-3):y+3, max(0,x-3):x+3] = rng.integers(180,255)
Image.fromarray(dapi).save("data/examples/dapi_example.png")
print("Created data/examples/he_example.png + dapi_example.png")
PY
fi

echo "[HEMIT] Done. Next: python resources/datasets/prepare_patches.py"
