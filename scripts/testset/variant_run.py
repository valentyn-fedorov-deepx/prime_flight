"""Run a GM / tracker variant on the videos already on disk and gate it by module verdicts against the v2 run set.

A variant is a lighter or faster shared layer: another ONNX provider for the GM heads, a tracker with fewer classes, a
longer noise-estimate interval, no publication delay. The question is always the same — does the post-processing verdict
survive — so the gate is the one the test set already uses: the same modules, the same flags, on the variant's rows,
compared pairwise with `mod:v2` (`scripts/testset/compare.py --baseline-root`).

Per video: [gm_v2_run.py with --provider] → tracker_v2_run.py with the variant's flags on the GM rows (the v2 rows when the
GM is unchanged) → `<variant>_inf/<video>/` (hard links: general_model + trackers ndjson) → run_module.py for every module
that has a v2 result for that video → `modules/<variant>/<video>/<module>.json`. Then compare.

    python scripts/testset/variant_run.py --variant light --tracker-args "--classes person,beltloader,gse --sigma-interval 10"
    python scripts/testset/variant_run.py --variant trt --gm-provider tensorrt
    python scripts/testset/variant_run.py --variant light --compare-only
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import shlex
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts.testset import orchestrate as orch  # noqa: E402
from scripts.testset import profiles  # noqa: E402

TS, PY = orch.TS, sys.executable


def log(fh, text: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {text}"
    print(line, flush=True)
    fh.write(line + "\n")
    fh.flush()


def run(cmd: list, log_path: str, env=None) -> int:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with io.open(log_path, "w", encoding="utf-8") as fh:
        fh.write(" ".join(cmd) + "\n")
        fh.flush()
        return subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env=env).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", required=True, help="label: rows in out/testset/trk_<variant>, results in modules/<variant>")
    ap.add_argument("--gm-provider", default="", choices=["", "cuda", "tensorrt"], help="rerun GM v2 with this provider")
    ap.add_argument("--tracker-args", default="", help="extra flags for scripts/tracker_v2_run.py (quoted)")
    ap.add_argument("--videos", default="", help="comma list (default: every video on disk with v2 rows and module results)")
    ap.add_argument("--modules", default="", help="comma list (default: every module with a v2 result for the video)")
    ap.add_argument("--jobs", type=int, default=2, help="module runs in parallel")
    ap.add_argument("--compare-only", action="store_true")
    ap.add_argument("--redo", action="store_true", help="recompute rows and module results that already exist")
    a = ap.parse_args()

    plan = orch.Plan()
    label = a.variant
    log_path = os.path.join(TS, "logs", f"variant_{label}.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    lf = io.open(log_path, "a", encoding="utf-8")
    videos = [v for v in a.videos.split(",") if v] or sorted(
        os.path.basename(v) for v in glob.glob(os.path.join(TS, "videos", "*.mp4"))
        if os.path.exists(orch.paths(os.path.basename(v))["trk_compat"]) and glob.glob(orch.module_out("v2", os.path.basename(v), "*")))
    log(lf, f"variant {label}: {len(videos)} videos; gm_provider={a.gm_provider or 'v2 rows'}; tracker args: {a.tracker_args}")

    if not a.compare_only:
        for video in videos:
            p = orch.paths(video)
            gm_compat = p["gm_compat"]
            if a.gm_provider:
                gm_dir = os.path.join(TS, f"gm_{label}", video)
                gm_compat = os.path.join(gm_dir, f"general_model{video}-second_run.ndjson")
                if a.redo or not os.path.exists(gm_compat):
                    cmd = [PY, "scripts/gm_v2_run.py", "--video", p["video"], "--weights-dir", orch.GM_WEIGHTS, "--variant",
                           "entity_clip", "--parallel-heads", "--out-dir", gm_dir, "--compare", p["prod_gm"],
                           "--buffered-decisions", "--provider", a.gm_provider]
                    log(lf, f"{video}: gm ({a.gm_provider})")
                    rc = run(cmd, os.path.join(p["logs"], f"gm_{label}.log"))
                    if rc or not os.path.exists(gm_compat):
                        log(lf, f"{video}: gm FAILED rc={rc}")
                        continue
            trk_dir = os.path.join(TS, f"trk_{label}", video)
            trk_compat = os.path.join(trk_dir, f"trackers{video}.ndjson")
            if a.redo or not os.path.exists(trk_compat):
                cmd = [PY, "scripts/tracker_v2_run.py", "--video", p["video"], "--gm-ndjson", gm_compat, "--seed", "0",
                       "--exact-fast", "--no-profile", "--out-dir", trk_dir, "--compare", p["trk_compat"]]
                cmd += ["--cone-camera"] if plan.cone(video) else []
                cmd += shlex.split(a.tracker_args)
                log(lf, f"{video}: tracker")
                rc = run(cmd, os.path.join(p["logs"], f"tracker_{label}.log"))
                if rc or not os.path.exists(trk_compat):
                    log(lf, f"{video}: tracker FAILED rc={rc}")
                    continue
            inf = os.path.join(TS, f"{label}_inf", video)
            orch.link_into(gm_compat, os.path.join(inf, f"general_model{video}.ndjson"))
            orch.link_into(trk_compat, os.path.join(inf, f"trackers{video}.ndjson"))

            modules = [m for m in a.modules.split(",") if m] or sorted(
                os.path.basename(x)[:-5] for x in glob.glob(orch.module_out("v2", video, "*")))
            pending = []
            for module in modules:
                out = orch.module_out(label, video, module)
                if not a.redo and os.path.exists(out):
                    continue
                prof = profiles.profile(module)
                launcher = prof.get("launcher")
                rel = (lambda x: os.path.relpath(x, ROOT).replace("\\", "/")) if launcher else (lambda x: x)
                cmd = (list(launcher) if launcher else [PY, "scripts/run_module.py"]) + [
                    "--module", module, "--video", video, "--inferences-dir", rel(inf),
                    "--device", prof["device"], "--cone-camera", "true" if plan.cone(video) else "false",
                    "--out", rel(out), "--videos-dir", rel(os.path.join(TS, "videos"))]
                if prof["numpy1"]:
                    cmd.append("--numpy1-scalars")
                if plan.airplane_type(video):
                    cmd += ["--airplane-type", plan.airplane_type(video)]
                for x in prof["prepend_path"]:
                    cmd += ["--prepend-path", x]
                if prof["drop_state_keys"]:
                    cmd += ["--drop-state-keys", prof["drop_state_keys"]]
                if prof["module_dir"]:
                    cmd += ["--module-dir", prof["module_dir"]]
                pending.append((module, cmd))
            log(lf, f"{video}: {len(pending)} module runs")
            running: list = []
            env = dict(os.environ, **profiles.ENV)
            while pending or running:
                while pending and len(running) < a.jobs:
                    module, cmd = pending.pop(0)
                    lp = os.path.join(p["logs"], f"mod_{label}_{module}.log")
                    os.makedirs(os.path.dirname(lp), exist_ok=True)
                    fh = io.open(lp, "w", encoding="utf-8")
                    fh.write(" ".join(cmd) + "\n")
                    fh.flush()
                    running.append((module, subprocess.Popen(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env=env), fh))
                for item in list(running):
                    module, proc, fh = item
                    if proc.poll() is not None:
                        fh.close()
                        running.remove(item)
                        if proc.returncode:
                            log(lf, f"{video}: {module} rc={proc.returncode}")
                time.sleep(2)

    out = os.path.join(TS, f"compare_{label}_vs_v2.json")
    cmd = [PY, "scripts/testset/compare.py", "--runs-root", os.path.join(TS, "modules", label), "--label", label,
           "--baseline-root", os.path.join(TS, "modules", "v2"), "--baseline-label", "v2", "--out", out]
    rc = run(cmd, os.path.join(TS, "logs", f"compare_{label}.log"))
    log(lf, f"compare rc={rc}: {out}")
    if os.path.exists(out):
        rep = json.load(io.open(out, encoding="utf-8"))
        pair = rep.get("pairwise") or rep.get("paired") or {}
        log(lf, f"paired vs v2: {json.dumps(pair)[:600]}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
