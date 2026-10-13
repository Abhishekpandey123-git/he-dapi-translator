#!/bin/bash
# waits for ckpt130, records exact time, no reboot (just notify)
cd /home/bikash/he-dapi-translator || exit 1
echo "[WAIT130 $(date -u +%Y-%m-%dT%H:%M:%SZ)] watching for checkpoint_epoch130.pt (129 now step1040/1858)" >> logs/ckpt130_watch.log
while true; do
  if grep -a -q "CHECKPOINT.*Epoch 130 " logs/train_paired.log 2>/dev/null && [ -f resources/models/checkpoints/he2dapi/checkpoint_epoch130.pt ]; then
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "[CKPT130 READY $TS] $(ls -lh resources/models/checkpoints/he2dapi/checkpoint_epoch130.pt) $(grep -a "\[Epoch 130" logs/train_paired.log | tail -1)" >> logs/ckpt130_watch.log
    echo "$TS" > logs/ckpt130_ready.flag
    echo "REBOOT NOW SAFE - run: sudo reboot, then relaunch train --resume auto" >> logs/ckpt130_watch.log
    break
  fi
  sleep 60
done
