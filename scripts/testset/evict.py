"""Free disk during event-by-event processing: delete the mp4 of videos whose events are far behind the processing window.

The breadth-first phase of the test-set run downloaded many more videos than event-by-event processing needs at a time. A
video can be evicted when its event is not among the first --keep-events unfinished events (in the orchestrator's event
order), and no running process mentions the video. Eviction deletes only the mp4 (and a stale .part) — the production
inference files stay — and removes the `fetch` record from the video's ledger, so the orchestrator downloads the video again
when its event enters the window. Nothing is touched for finished events (their cleanup is the orchestrator's `cleanup`).

    python scripts/testset/evict.py --keep-events 12            # dry run: what would be deleted
    python scripts/testset/evict.py --keep-events 12 --apply
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts.testset import orchestrate as o  # noqa: E402


def running_command_lines() -> str:
    ps = "Get-CimInstance Win32_Process | ForEach-Object { $_.CommandLine }"
    return subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep-events", type=int, default=12, help="unfinished events (window order) whose videos stay")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    ctl = o.read_control()
    plan = o.Plan()
    keep, n = set(), 0
    for event in plan.events:
        if o.event_finished(event, plan, ctl):
            continue
        if n < a.keep_events:
            keep.update(event["videos"])
        n += 1
    procs = running_command_lines()
    freed, evicted = 0, []
    for event in plan.events:
        if o.event_finished(event, plan, ctl):
            continue
        for video in event["videos"]:
            p = o.paths(video)
            if video in keep or not os.path.exists(p["video"]):
                continue
            if video in procs:
                print(f"skip {video}: used by a running process")
                continue
            size = os.path.getsize(p["video"])
            evicted.append(video)
            freed += size
            if a.apply:
                os.remove(p["video"])
                if os.path.exists(p["part"]):
                    os.remove(p["part"])
                led = o.load_ledger(video)
                led["steps"].pop("fetch", None)
                led["evicted"] = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "gb": round(size / 1e9, 2)}
                o.save_ledger(led)
    msg = f"{'evicted' if a.apply else 'would evict'} {len(evicted)} videos, {freed / 1e9:.1f} GB (keeping {len(keep)} videos of the first {a.keep_events} unfinished events)"
    print(msg)
    for v in evicted:
        print("  ", v)
    if a.apply:
        with io.open(os.path.join(o.TS, "orchestrator.log"), "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} evict: {msg}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
