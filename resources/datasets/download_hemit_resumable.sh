#!/usr/bin/env bash
# download_hemit_resumable.sh - nohup + resumable HEMIT download (Mendeley 8.21G)
# Usage: nohup bash resources/datasets/download_hemit_resumable.sh > /tmp/hemit_nohup.log 2>&1 &
set -e
ROOT="data/raw/hemit"
mkdir -p "$ROOT" data/processed
URL="https://data.mendeley.com/public-api/zip/3gx53zm49d/download/1"
OUT="$ROOT/hemit.zip"
LOG="/tmp/hemit_download.log"

echo "[HEMIT] Resumable nohup download to $OUT (log $LOG)"
echo "[HEMIT] To monitor: tail -f $LOG  ; du -sh $OUT ; ps aux | grep curl"
echo "[HEMIT] To resume after kill/interrupt: just re-run this script (curl -C -)"
echo "[HEMIT] URL: $URL"

# Use curl with resume + retry + speed limit detection (resumable)
nohup bash -c "curl -L -C - --retry 20 --retry-delay 10 --retry-all-errors --speed-limit 1000 --speed-time 120 --connect-timeout 30 \"$URL\" -o \"$OUT\" 2>&1 | tee -a \"$LOG\"" > /tmp/hemit_nohup_outer.log 2>&1 &
PID=$!
echo "[HEMIT] Launched PID $PID (curl child). Outer log: /tmp/hemit_nohup_outer.log"
sleep 1
ps -o pid,ppid,cmd -p $PID 2>&1 | head
echo "[HEMIT] Next after done: 7z x or unzip $OUT  && python resources/datasets/prepare_patches.py --input $ROOT --patch 512 --out data/processed/hemit_512.h5"
echo "[HEMIT] Checkpoint: file size persists, re-run resumes from byte \$(stat -c%s $OUT 2>/dev/null || echo 0)"
