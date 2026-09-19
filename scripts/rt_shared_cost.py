"""What the shared parts cost, on ONE stretch of video: GM by head set, tracker by tracked classes.

The per-module runs (`scripts/rt_module_cost.py`) each use the stretch where that module decides, so their GM and tracker
numbers come from different scenes and do not add up consistently (a tracker with more classes came out cheaper than one
with fewer). This measures every head set and every tracked-class set that a module needs on the same busy stretch, with the
lightest module as the carrier, so that `cost(set of modules) = GM[heads] + tracker[classes] + sum of module costs` is built
from comparable numbers.

    python scripts/rt_shared_cost.py [--slice zHxIAF2vUGxJ_6961_12007.mp4] [--seconds 360]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.rt_module_cost import MachineSampler  # noqa: E402

CARRIER = "crew-present-10-minutes-prior-to-aircraft-arrival"  # 0.35 ms per frame: the cheapest module that runs live
HEAD_SETS = ["gm", "gm,vehicle", "gm,chocks", "gm,chocks,vehicle"]
CLASS_SETS = ["airplane", "person", "airplane,person", "airplane,beltloader", "airplane,gse", "airplane,beltloader,person",
              "beltloader,gse,person", "airplane,beltloader,gse,person"]


def run(slice_video: str, event: str, heads: str, classes: str, seconds: float, tag: str) -> dict:
    stem = os.path.splitext(slice_video)[0]
    cmd = [sys.executable, "scripts/rt_pipeline_run.py", "--video", slice_video, "--plan-video", event, "--module", CARRIER,
           "--tag", tag, "--speed", "1", "--no-write-rows", "--heads", heads, "--tracker-classes", classes,
           "--ingest", "frames", "--bandwidth-mbps", "10", "--max-seconds", str(seconds),
           "--chunks", os.path.join("out", "rt", "chunks", f"{stem}_gop1")]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sampler = MachineSampler(proc.pid).start()
    rc = proc.wait()
    sampler.stop()
    path = os.path.join(ROOT, "out", "rt", "runs", tag, "summary.json")
    if rc != 0 or not os.path.exists(path):
        return {"heads": heads, "classes": classes, "error": f"exit {rc}"}
    s = json.load(io.open(path, encoding="utf-8"))
    comp = s.get("components_ms_per_frame") or {}
    return {"heads": heads, "classes": classes, "keeps_up": s.get("keeps_up"),
            "gm_ms": (comp.get("gm") or {}).get("mean"), "gm_p95": (comp.get("gm") or {}).get("p95"),
            "tracker_ms": (comp.get("tracker") or {}).get("mean"), "tracker_p95": (comp.get("tracker") or {}).get("p95"),
            "total_ms": (comp.get("total") or {}).get("mean"), "gm_heads_detail": s.get("gm_heads"),
            "tracker_detail_ms": s.get("tracker_ms_per_frame"), "machine": sampler.summary(steady_s=seconds)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slice", default="zHxIAF2vUGxJ_6961_12007.mp4", help="a slice under out/rt/slices with its chunk folder")
    ap.add_argument("--event", default="zHxIAF2vUGxJ.mp4")
    ap.add_argument("--seconds", type=float, default=360.0)
    a = ap.parse_args()

    out_path = os.path.join(ROOT, "out", "rt", "cost", os.path.splitext(a.event)[0], "shared.json")
    result = json.load(io.open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {"gm": {}, "tracker": {}}
    result.update(slice=a.slice, seconds=a.seconds, carrier=CARRIER)
    jobs = [("gm", h, h, "airplane") for h in HEAD_SETS] + [("tracker", c, "gm", c) for c in CLASS_SETS]
    for i, (kind, key, heads, classes) in enumerate(jobs, 1):
        if key in result[kind] and not result[kind][key].get("error"):
            continue
        print(f"[{i}/{len(jobs)}] {kind} {key}", flush=True)
        result[kind][key] = run(a.slice, a.event, heads, classes, a.seconds, f"shared_{kind}_{key.replace(',', '-')}")
        result["measured"] = time.strftime("%Y-%m-%d %H:%M")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        json.dump(result, io.open(out_path, "w", encoding="utf-8"), indent=1, default=str)
        r = result[kind][key]
        print("   ", {k: r.get(k) for k in ("gm_ms", "tracker_ms", "total_ms", "keeps_up", "error")}, flush=True)
    print("GM by head set:     ", {k: v.get("gm_ms") for k, v in result["gm"].items()})
    print("tracker by classes: ", {k: v.get("tracker_ms") for k, v in result["tracker"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
