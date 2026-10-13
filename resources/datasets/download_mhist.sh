#!/usr/bin/env bash
# download_mhist.sh - MHIST: 3152 H&E images for unpaired training (target domain)
# Source: https://bmirds.github.io/MHIST/  (used in Light-sheet CycleGAN paper)
set -e
ROOT="data/raw/mhist"
mkdir -p "$ROOT"

echo "[MHIST] Downloading from BMIRDS..."

URL="https://bmirds.github.io/MHIST/MHIST.zip"
# Try official zip
if wget -O /tmp/MHIST.zip "$URL" 2>&1; then
  unzip -q /tmp/MHIST.zip -d "$ROOT"
  echo "[MHIST] Extracted to $ROOT"
else
  echo "[MHIST] wget failed, trying Kaggle mirror..."
  # Kaggle: https://www.kaggle.com/datasets/bmirds/mhist
  if command -v kaggle &>/dev/null; then
    kaggle datasets download -d bmirds/mhist -p /tmp && unzip -q /tmp/mhist.zip -d "$ROOT" || echo "Kaggle download failed - manual download needed"
  else
    cat << 'MANUAL'
[MANUAL] Download MHIST manually:
  Option 1: https://bmirds.github.io/MHIST/ -> Download ZIP -> unzip to data/raw/mhist
  Option 2: kaggle datasets download -d bmirds/mhist -p data/raw/mhist
  Expected: data/raw/mhist/images/*.png + annotations.csv
MANUAL
  fi
fi

echo "[MHIST] Done. Check: ls $ROOT | head"
ls -lh "$ROOT" 2>&1 | head -n 20
