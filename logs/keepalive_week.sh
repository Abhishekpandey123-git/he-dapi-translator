#!/bin/bash
# keepalive_week.sh — 1-week supervisor: restarts train_paired if dead, every 300s
cd /home/bikash/he-dapi-translator || exit 1
while true; do
  if ! pgrep -f "train_paired.*hemit_dual_branch" > /dev/null 2>&1; then
    echo "[KEEPALIVE $(date -u +%Y-%m-%dT%H:%M:%SZ)] TRAIN DEAD -> relaunching epoch resume auto" >> logs/keepalive.log
    nohup nice -n 10 env PYTHONPATH=. .venv/bin/python -u -m src.models.train_paired --config configs/hemit_dual_branch.yaml --resume auto --optimize-for lowram >> logs/train_paired.log 2>&1 &
    echo "[KEEPALIVE] new PID $!" >> logs/keepalive.log
  fi
  sleep 300
done
