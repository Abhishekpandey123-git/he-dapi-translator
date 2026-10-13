"""
resource_monitor.py - Global spike guard for 3.7GB RAM CPU box
Covers: /proc/meminfo fallback (no psutil), per-step budgets, throttling advice.
Usage:
  from src.utils.resource_monitor import ResourceMonitor, monitor_step
  mon = ResourceMonitor(budget_gb=1.5, spike_mb=500)
  mon.check("data_extraction:start")
  # ... do work ...
  mon.check("data_extraction:end", warn_if_spike=True)

CLI: python -m src.utils.resource_monitor --check
"""
import os
import time
import json
import functools
from pathlib import Path
from typing import Optional

def _read_meminfo():
    """Parse /proc/meminfo without psutil. Returns dict MB."""
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    k = parts[0].rstrip(":")
                    v = int(parts[1])  # kB
                    info[k] = v / 1024  # MB
    except Exception:
        info = {"MemTotal": 3898, "MemAvailable": 2600, "SwapTotal": 1024, "SwapFree": 1024}
    return info

def get_ram_state():
    info = _read_meminfo()
    total = info.get("MemTotal", 3898)
    avail = info.get("MemAvailable", info.get("MemFree", 1500))
    used = total - avail
    pct = (used / total * 100) if total else 0
    swap_total = info.get("SwapTotal", 1024)
    swap_free = info.get("SwapFree", 1024)
    return {
        "total_mb": round(total, 1),
        "avail_mb": round(avail, 1),
        "used_mb": round(used, 1),
        "used_pct": round(pct, 1),
        "swap_total_mb": round(swap_total, 1),
        "swap_free_mb": round(swap_free, 1),
    }

def get_disk_state(path="/"):
    try:
        import shutil
        du = shutil.disk_usage(path)
        return {"total_gb": round(du.total/1e9,1), "free_gb": round(du.free/1e9,1), "used_gb": round(du.used/1e9,1)}
    except Exception:
        return {"total_gb": 1007, "free_gb": 867, "used_gb": 90}

class ResourceMonitor:
    """
    Spike-aware monitor. Keep history, detect delta > spike_mb within window.
    On high pressure (>80%), suggests throttling: halve batch, stream to disk.
    """
    def __init__(self, budget_gb: float = 1.5, spike_mb: float = 500, log_path: str = "wiki/01-machine-profile/profile.json"):
        self.budget_mb = budget_gb * 1024
        self.spike_mb = spike_mb
        self.log_path = Path(log_path)
        self.history = []  # list of {ts, label, ram}
        self._load_log()

    def _load_log(self):
        if self.log_path.exists():
            try:
                with open(self.log_path) as f:
                    data = json.load(f)
                    self.history = data.get("history", [])
            except Exception:
                pass

    def _save_log(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w") as f:
            json.dump({"history": self.history[-200:], "budget_mb": self.budget_mb, "spike_mb": self.spike_mb}, f, indent=2)

    def check(self, label: str, warn_if_spike: bool = True, verbose: bool = True):
        ram = get_ram_state()
        disk = get_disk_state()
        entry = {"ts": time.time(), "label": label, "ram": ram, "disk": disk}
        self.history.append(entry)
        # spike detection: compare last two
        spike = False
        if len(self.history) >= 2:
            prev = self.history[-2]["ram"]["used_mb"]
            cur = ram["used_mb"]
            delta = cur - prev
            elapsed = entry["ts"] - self.history[-2]["ts"]
            if delta > self.spike_mb and elapsed < 10:
                spike = True
                if warn_if_spike and verbose:
                    print(f"[SPIKE] {label}: +{delta:.0f}MB in {elapsed:.1f}s (cur {cur:.0f}MB, {ram['used_pct']:.0f}%) -> THROTTLE: halve batch / stream to disk")
        # budget check
        over = ram["used_pct"] > 80 or ram["avail_mb"] < (self.budget_mb * 0.3)
        if over and verbose:
            print(f"[PRESSURE] {label}: RAM {ram['used_pct']:.0f}% used, {ram['avail_mb']:.0f}MB avail < budget {self.budget_mb:.0f}MB -> throttle")
        elif verbose:
            print(f"[MONITOR] {label}: RAM {ram['used_mb']:.0f}/{ram['total_mb']:.0f}MB ({ram['used_pct']:.0f}%), avail {ram['avail_mb']:.0f}MB, disk free {disk['free_gb']:.0f}GB")
        self._save_log()
        return {"ram": ram, "disk": disk, "spike": spike, "over": over}

    def advise_batch(self, requested_batch: int) -> int:
        """Return safe batch size given current RAM."""
        ram = get_ram_state()
        avail = ram["avail_mb"]
        # heuristic: 512px batch needs ~80MB per sample with grads on CPU (no VGG)
        # keep headroom 800MB
        if avail < 800:
            return 1
        if avail < 1200:
            return min(requested_batch, 2)
        return min(requested_batch, 4)

    def ensure_headroom(self, need_mb: float = 800) -> bool:
        ram = get_ram_state()
        return ram["avail_mb"] >= need_mb

def monitor_step(label: str):
    """Decorator: log before/after + detect spike."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            mon = ResourceMonitor()
            mon.check(f"{label}:start")
            try:
                result = fn(*args, **kwargs)
                return result
            finally:
                mon.check(f"{label}:end", warn_if_spike=True)
        return wrapper
    return decorator

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="one-shot check")
    ap.add_argument("--budget", type=float, default=1.5)
    ap.add_argument("--watch", type=int, default=0, help="watch for N seconds")
    args = ap.parse_args()
    mon = ResourceMonitor(budget_gb=args.budget)
    if args.check or args.watch == 0:
        state = mon.check("cli:check")
        print(json.dumps(state, indent=2))
        # also advise
        print(f"Advised batch for 512px: {mon.advise_batch(8)} (requested 8)")
        print(f"Headroom 800MB? {mon.ensure_headroom(800)}")
    if args.watch:
        for i in range(args.watch):
            mon.check(f"watch:{i}")
            time.sleep(1)
