#!/usr/bin/env bash
# download_codex.sh - CODEX Virtual H&E examples: DAPI+Eosin fluorescence -> virtual H&E
# Source: https://github.com/SimonsonLab/VirtualHE_examples  (PMC8721868)
set -e
ROOT="data/raw/codex_virtualhe"
mkdir -p "$ROOT"

echo "[CODEX] Cloning VirtualHE_examples..."
if [ ! -d "$ROOT/repo" ]; then
  git clone https://github.com/SimonsonLab/VirtualHE_examples.git "$ROOT/repo" || {
    echo "[CODEX] git clone failed, trying wget..."
    wget -P "$ROOT" https://github.com/SimonsonLab/VirtualHE_examples/archive/refs/heads/main.zip
    unzip -q "$ROOT/main.zip" -d "$ROOT"
  }
else
  echo "[CODEX] Already cloned"
fi

# Copy example data if present
if [ -d "$ROOT/repo/data" ]; then
  cp -r "$ROOT/repo/data" "$ROOT/examples" 2>/dev/null || true
fi

# Also fetch 1 GDC SVS for WSI testing (TCGA H&E)
echo "[TCGA] Fetching 1 example SVS via GDC portal (optional)..."
mkdir -p data/raw/wsi
# Small test SVS from OpenSlide demo (CM1_ShAHE_0_0_0.svs ~ 10MB)
wget -q -P data/raw/wsi https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CM1_ShAHE_0_0_0.svs || echo "[TCGA] openslide demo SVS download failed - manual download from https://portal.gdc.cancer.gov/"

echo "[CODEX] Done. Repo at $ROOT/repo"
ls -lh "$ROOT" 2>&1 | head -n 20
ls -lh data/raw/wsi 2>&1 | head -n 20
