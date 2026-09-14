"""Idle-machine tracker speed suite: production pin vs the v2 stream (pure port / exact fast paths / bus-only) on the same
slices, back to back, with byte-level identity against the seeded production output.

Run it only when nothing else uses the GPU/CPU (the numbers in tasks/notes/PF-Q1-17.md measured during the GM chain are
relative only). Every configuration is a separate process (cold CUDA context each time, warm file cache after the first).

    python scripts/tracker_speed_suite.py --video G:/gat_stages/atlc5_videos/DjwtQRdZyt0sSk.mp4 \
        --gm-ndjson G:/gat_stages/atlc5_inferences/general_modelDjwtQRdZyt0sSk.mp4.ndjson \
        --slices 3400:1200,9000:1200 --out docs/analysis/speed/tracker_speed_suite.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def run(cmd: list, log: str) -> int:
    with io.open(log, "w", encoding="utf-8") as fh:
        p = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    return p.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--gm-ndjson", required=True)
    ap.add_argument("--slices", default="3400:1200,9000:1200", help="start:frames,...")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--work", default="out/speed_suite")
    ap.add_argument("--out", default="docs/analysis/speed/tracker_speed_suite.json")
    a = ap.parse_args()

    from scripts.tracker_v2_run import compare_lines

    py = sys.executable
    name = os.path.basename(a.video)
    os.makedirs(a.work, exist_ok=True)
    results = {"video": name, "seed": a.seed, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "slices": []}
    for spec in a.slices.split(","):
        start, frames = (int(x) for x in spec.split(":"))
        tag = f"{start}_{frames}"
        entry = {"start": start, "frames": frames, "configs": {}}

        # 1. production pin (seeded), reference output
        v1_json = os.path.join(a.work, f"v1prod_{tag}.json")
        rc = run([py, "scripts/tracker_v1_profile.py", "--pin", "prod", "--seed", str(a.seed), "--video", a.video,
                  "--gm-ndjson", a.gm_ndjson, "--start", str(start), "--frames", str(frames), "--out", v1_json],
                 os.path.join(a.work, f"v1prod_{tag}.log"))
        ref = os.path.join(a.work, f"trackers_v1prod_{tag}.ndjson")
        src_ref = os.path.join(ROOT, "out", "tracker_profile_prod", f"trackers{name}.ndjson")
        if rc == 0 and os.path.exists(src_ref):
            shutil.copy(src_ref, ref)
        v1 = json.load(open(v1_json, encoding="utf-8")) if os.path.exists(v1_json) else {}
        entry["configs"]["v1_production_pin"] = {"rc": rc, "ms_per_frame": v1.get("ms_per_frame_total"),
                                                  "components": v1.get("components_ms_per_frame")}

        # 2-4. v2 stream configurations (timers off for clean totals)
        for cfg, extra in (("v2_port", []), ("v2_exact_fast", ["--exact-fast"]), ("v2_exact_fast_bus_only", ["--exact-fast", "--no-compat"])):
            out_dir = os.path.join(a.work, f"{cfg}_{tag}")
            cmd = [py, "scripts/tracker_v2_run.py", "--video", a.video, "--gm-ndjson", a.gm_ndjson, "--start", str(start),
                   "--frames", str(frames), "--seed", str(a.seed), "--no-profile", "--out-dir", out_dir, *extra]
            rc = run(cmd, out_dir + ".log")
            rep_path = os.path.join(out_dir, f"tracker_v2_report{name}.json")
            rep = json.load(open(rep_path, encoding="utf-8")) if os.path.exists(rep_path) else {}
            item = {"rc": rc, "ms_per_frame": rep.get("ms_per_frame_total"), "decode_ms": rep.get("decode_ms_per_frame"),
                    "serialise_ms": rep.get("serialise_ms_per_frame"), "stages": (rep.get("stream") or {}).get("timings_ms_per_frame"),
                    "compat_mb": rep.get("compat_mb"), "v2bus_mb": rep.get("v2bus_mb")}
            compat = os.path.join(out_dir, f"trackers{name}.ndjson")
            if "--no-compat" not in extra and os.path.exists(ref) and os.path.exists(compat):
                item["lines_vs_production_pin"] = compare_lines(ref, compat)
            entry["configs"][cfg] = item
        results["slices"].append(entry)

    results["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)

    print("| slice | configuration | ms/frame | byte-identical lines |")
    print("|---|---|---|---|")
    for e in results["slices"]:
        for cfg, item in e["configs"].items():
            lines = item.get("lines_vs_production_pin")
            ident = f"{lines['lines_identical']}/{lines['lines_compared']}" if lines else "—"
            print(f"| {e['start']}+{e['frames']} | {cfg} | {item.get('ms_per_frame')} | {ident} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
