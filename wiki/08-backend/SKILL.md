# Skill: backend_throttler

Backend guard for FastAPI on 3.7GB.

- `src/backend/main.py:40` checks `/proc/meminfo` before processing; 429 if `used_pct>85` or `avail<400MB`.
- Rejects `len(data)>500MB` → 413, suggest `/translate/wsi`.
- PIL thumbnail before numpy for large w×h.
- Streaming tiled inference to temp tiff if `est_out>512MB`, returns 2048 preview to avoid loading full TIFF into response RAM.

Verify: `curl -X POST http://localhost:8000/translate -F file=@large.svs` returns 429 when under pressure, not crash.
