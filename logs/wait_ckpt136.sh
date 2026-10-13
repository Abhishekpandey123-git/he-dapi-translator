#!/bin/bash
cd /home/bikash/he-dapi-translator || exit 1
echo "[WAIT136 $(date -u +%Y-%m-%dT%H:%M:%SZ)] watching for checkpoint_epoch136.pt" >> logs/ckpt136_watch.log
while true; do
  if grep -a -q "CHECKPOINT.*Epoch 136 " logs/train_paired.log 2>/dev/null && [ -f resources/models/checkpoints/he2dapi/checkpoint_epoch136.pt ]; then
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "[CKPT136 READY $TS] $(ls -lh resources/models/checkpoints/he2dapi/checkpoint_epoch136.pt) $(grep -a "\[Epoch 136" logs/train_paired.log | tail -1)" >> logs/ckpt136_watch.log
    echo "$TS" > logs/ckpt136_ready.flag
    echo "REBOOT NOW SAFE" >> logs/ckpt136_watch.log
    break
  fi
  sleep 60
done
