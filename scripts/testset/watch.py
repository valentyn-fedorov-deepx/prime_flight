"""Wait until the test-set run needs attention, then print a compact status and exit (a background wake-up for the operator).

Exit reasons, checked every --poll seconds:
  calibration   a calibrate.py process running at start has finished
  failed        new failed steps in the ledgers since start
  orchestrator  no orchestrator process is running
  disk          free disk below --min-free-gb
  memory        free RAM below --min-free-ram-gb while commit is above --max-commit-share of the limit
  complete      every video has fetch, gm and tracker done and no module step is pending for an enabled module
  timeout       --max-minutes elapsed

    python scripts/testset/watch.py --max-minutes 60
"""

from __future__ import annotations

import argparse
import collections
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TS = os.path.join(ROOT, "out", "testset")
sys.path.insert(0, ROOT)


def processes() -> list:
    """Command lines of running python processes (Windows)."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object { $_.CommandLine }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def memory() -> tuple:
    ps = "$o=Get-CimInstance Win32_OperatingSystem; '{0} {1} {2}' -f $o.FreePhysicalMemory, ($o.TotalVirtualMemorySize-$o.FreeVirtualMemory), $o.TotalVirtualMemorySize"
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.split()
    free, commit, limit = (int(x) / 2**20 for x in out[:3])
    return free, commit, limit


def ledgers() -> dict:
    out = {}
    for f in glob.glob(os.path.join(TS, "ledger", "*.json")):
        try:
            led = json.load(io.open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out[led["video"]] = led
    return out


def failed_steps(leds: dict) -> set:
    return {(v, s) for v, led in leds.items() for s, r in led.get("steps", {}).items() if r.get("status") == "failed"}


def summary(leds: dict) -> dict:
    counts = collections.defaultdict(collections.Counter)
    for led in leds.values():
        for step, rec in led.get("steps", {}).items():
            counts[":".join(step.split(":")[:2])][rec.get("status")] += 1
    return {k: dict(v) for k, v in sorted(counts.items())}


def complete(leds: dict) -> bool:
    from scripts.testset import orchestrate as o

    ctl = o.read_control()
    plan = o.Plan()
    for video in plan.order:
        led = leds.get(video, {"steps": {}})
        steps = [s for s in ("fetch", "gm", "tracker") if o.step_enabled(s, ctl)]
        steps += [f"mod:{lb}:{m}" for lb in ("ctl", "v2") for m in plan.modules(video) if o.step_enabled(f"mod:{lb}:{m}", ctl)]
        if any(led["steps"].get(s, {}).get("status") not in ("done", "failed") for s in steps):
            return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-minutes", type=float, default=60)
    ap.add_argument("--poll", type=float, default=60)
    ap.add_argument("--min-free-gb", type=float, default=65)
    ap.add_argument("--min-free-ram-gb", type=float, default=1.0)
    ap.add_argument("--max-commit-share", type=float, default=0.92)
    a = ap.parse_args()

    t0 = time.time()
    start_calibrations = {c for c in processes() if "calibrate.py run" in c}
    start_failed = failed_steps(ledgers())
    reason = "timeout"
    while time.time() - t0 < a.max_minutes * 60:
        procs = processes()
        leds = ledgers()
        if start_calibrations and not any(c in procs for c in start_calibrations):
            reason = "calibration"
            break
        new_failed = failed_steps(leds) - start_failed
        if new_failed:
            reason = "failed"
            break
        if not any("orchestrate.py run" in c for c in procs):
            reason = "orchestrator"
            break
        if shutil.disk_usage(TS).free / 1e9 < a.min_free_gb:
            reason = "disk"
            break
        free, commit, limit = memory()
        if free < a.min_free_ram_gb and commit > a.max_commit_share * limit:
            reason = "memory"
            break
        if complete(leds):
            reason = "complete"
            break
        time.sleep(a.poll)

    leds = ledgers()
    free, commit, limit = memory()
    gm = [led["steps"]["gm"] for led in leds.values() if led.get("steps", {}).get("gm", {}).get("status") == "done"]
    trk = [led["steps"]["tracker"] for led in leds.values() if led.get("steps", {}).get("tracker", {}).get("status") == "done"]
    new_failed = sorted(failed_steps(leds) - start_failed)
    report = {
        "reason": reason,
        "minutes": round((time.time() - t0) / 60, 1),
        "steps": summary(leds),
        "gm_done_videos": len(gm),
        "tracker_done_videos": len(trk),
        "new_failed": [{"video": v, "step": s, "error": (leds[v]["steps"][s].get("error") or f"rc {leds[v]['steps'][s].get('rc')}")[:160]}
                       for v, s in new_failed[:15]],
        "calibration_running": [c[-120:] for c in processes() if "calibrate.py run" in c],
        "orchestrator_running": any("orchestrate.py run" in c for c in processes()),
        "disk_free_gb": round(shutil.disk_usage(TS).free / 1e9),
        "ram_free_gb": round(free, 1),
        "commit_gb": f"{commit:.0f}/{limit:.0f}",
    }
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
