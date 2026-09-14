"""Memory governor for the test-set orchestrator: pauses new module jobs when memory runs out and restores them later.

The machine shares its RAM with other applications, and the orchestrator's limits are static. Under pressure it would keep
starting module jobs while the commit charge sits at the commit limit, which means allocation failures and heavy paging.
Every --poll seconds the governor reads free RAM and the commit charge:
  * at or above --pause-commit-share of the limit, or below --pause-free-ram-gb free RAM: it sets the live control limits
    `mod` and `mod_gpu` to 0 (running jobs continue) and remembers the previous values in the control file;
  * at or below --resume-commit-share and at or above --resume-free-ram-gb: it restores the remembered limits.
GM and tracker limits are left alone (critical path). Changes are logged to out/testset/orchestrator.log.

    python scripts/testset/governor.py
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TS = os.path.join(ROOT, "out", "testset")
CONTROL = os.path.join(TS, "orchestrator_control.json")
KEYS = ("mod", "mod_gpu")


def memory() -> tuple:
    ps = ("$o=Get-CimInstance Win32_OperatingSystem; "
          "'{0} {1} {2}' -f $o.FreePhysicalMemory, ($o.TotalVirtualMemorySize-$o.FreeVirtualMemory), $o.TotalVirtualMemorySize")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.split()
    free, commit, limit = (int(x) / 2**20 for x in out[:3])
    return free, commit, limit


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} governor: {msg}"
    print(line, flush=True)
    with io.open(os.path.join(TS, "orchestrator.log"), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def update_control(fn) -> dict:
    ctl = json.load(io.open(CONTROL, encoding="utf-8"))
    fn(ctl)
    tmp = CONTROL + ".governor.tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        json.dump(ctl, fh, indent=1)
    os.replace(tmp, CONTROL)
    return ctl


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--pause-commit-share", type=float, default=0.93)
    ap.add_argument("--pause-free-ram-gb", type=float, default=1.0)
    ap.add_argument("--resume-commit-share", type=float, default=0.86)
    ap.add_argument("--resume-free-ram-gb", type=float, default=2.5)
    a = ap.parse_args()

    paused = "governor_saved_limits" in json.load(io.open(CONTROL, encoding="utf-8"))
    log(f"started ({'paused' if paused else 'running'}); pause at commit >= {a.pause_commit_share:.0%} or RAM < "
        f"{a.pause_free_ram_gb} GB, resume at commit <= {a.resume_commit_share:.0%} and RAM >= {a.resume_free_ram_gb} GB")
    while True:
        free, commit, limit = memory()
        share = commit / limit if limit else 0.0
        if not paused and (share >= a.pause_commit_share or free < a.pause_free_ram_gb):
            def pause(ctl):
                ctl["governor_saved_limits"] = {k: ctl["limits"].get(k, 0) for k in KEYS}
                ctl["limits"].update({k: 0 for k in KEYS})
            ctl = update_control(pause)
            log(f"paused new module jobs (RAM free {free:.1f} GB, commit {commit:.0f}/{limit:.0f} GB); "
                f"saved {ctl['governor_saved_limits']}")
            paused = True
        elif paused and share <= a.resume_commit_share and free >= a.resume_free_ram_gb:
            restored = {}

            def resume(ctl):
                saved = ctl.pop("governor_saved_limits", None) or {"mod": 1, "mod_gpu": 1}
                ctl["limits"].update(saved)
                restored.update(saved)
            update_control(resume)
            log(f"resumed module jobs {restored} (RAM free {free:.1f} GB, commit {commit:.0f}/{limit:.0f} GB)")
            paused = False
        time.sleep(a.poll)


if __name__ == "__main__":
    raise SystemExit(main())
