"""Run a GM / tracker variant on the videos already on disk and gate it by module verdicts against the v2 run set.

A variant is a lighter or faster shared layer: another ONNX provider for the GM heads, a tracker with fewer classes, a
longer noise-estimate interval, no publication delay. The question is always the same — does the post-processing verdict
survive — so the gate is the one the test set already uses: the same modules, the same flags, on the variant's rows,
compared pairwise with `mod:v2` (`scripts/testset/compare.py --baseline-root`).

Per video: [gm_v2_run.py with --provider] → tracker_v2_run.py with the variant's flags on the GM rows (the v2 rows when the
GM is unchanged) → `<variant>_inf/<video>/` (hard links: general_model + trackers ndjson) → run_module.py for every module
that has a v2 result for that video → `modules/<variant>/<video>/<module>.json`. Then compare.

A variant of a module's own model reuses the v2 inferences as they are (`--reuse-v2`: no GM or tracker run) and passes
flags to the module runner (`--module-args`), e.g. the shared pose model instead of the module's own.

    python scripts/testset/variant_run.py --variant light --tracker-args "--classes person,beltloader,gse --sigma-interval 10"
    python scripts/testset/variant_run.py --variant trt --gm-provider tensorrt
    python scripts/testset/variant_run.py --variant pose_rtm --reuse-v2 --modules hand-signals,pin-verification         --module-args "--pose-override rtmpose-l"
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


def hold_rows(src: str, dst: str, stride: int) -> None:
    """Every `stride`-th line of a GM rows file kept, the lines in between replaced by the last kept line's rows
    (frame keys unchanged): what the modules see when GM runs on every `stride`-th frame."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    held = None
    with io.open(src, encoding="utf-8") as fi, io.open(dst + ".part", "w", encoding="utf-8", newline="") as fo:
        for i, line in enumerate(fi):
            rec = json.loads(line)
            ((key, rows),) = rec.items()
            if i % stride == 0:
                held = rows
            fo.write(json.dumps({key: held}) + chr(10))
    os.replace(dst + ".part", dst)


def module_command(plan, label: str, video: str, module: str, inf: str, module_args: str = "") -> list:
    """The scripts/run_module.py command line of one module run, with the test set's profile and plan flags."""
    out = orch.module_out(label, video, module)
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
    return cmd + shlex.split(module_args)


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
    ap.add_argument("--hold-stride", type=int, default=1,
                    help="GM and the tracker on every N-th frame: the GM rows of the frames in between are the last processed frame's, the tracker runs with --stride N")
    ap.add_argument("--tracker-args", default="", help="extra flags for scripts/tracker_v2_run.py (quoted)")
    ap.add_argument("--reuse-v2", action="store_true",
                    help="no GM or tracker run: the modules read the v2 inferences (out/testset/v2_inf/<video>)")
    ap.add_argument("--module-args", default="", help="extra flags for scripts/run_module.py (quoted)")
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
    if a.modules:  # only the videos where a listed module has a v2 result to pair with
        videos = [v for v in videos if any(os.path.exists(orch.module_out("v2", v, m)) for m in a.modules.split(",") if m)]
    log(lf, f"variant {label}: {len(videos)} videos; gm_provider={a.gm_provider or 'v2 rows'}; tracker args: {a.tracker_args}; "
            f"reuse_v2={a.reuse_v2}; module args: {a.module_args}")

    if not a.compare_only:
        for video in videos:
            p = orch.paths(video)
            gm_compat = p["gm_compat"]
            if a.reuse_v2:
                inf = p["v2_inf"]
            elif a.gm_provider:
                gm_dir = os.path.join(TS, f"gm_{label}", video)
                gm_compat = os.path.join(gm_dir, f"general_model{video}-second_run.ndjson")
                gm_report = os.path.join(gm_dir, f"gm_v2_report{video}.json")  # written last: a run that died has none
                if a.redo or not os.path.exists(gm_report):
                    cmd = [PY, "scripts/gm_v2_run.py", "--video", p["video"], "--weights-dir", orch.GM_WEIGHTS, "--variant",
                           "entity_clip", "--parallel-heads", "--out-dir", gm_dir, "--compare", p["prod_gm"],
                           "--buffered-decisions", "--provider", a.gm_provider]
                    log(lf, f"{video}: gm ({a.gm_provider})")
                    rc = run(cmd, os.path.join(p["logs"], f"gm_{label}.log"))
                    if rc or not os.path.exists(gm_report):
                        log(lf, f"{video}: gm FAILED rc={rc}")
                        continue
            if not a.reuse_v2 and a.hold_stride > 1:  # the GM rows the modules get: every N-th frame, held in between
                held = os.path.join(TS, f"gm_{label}", video, f"general_model{video}-second_run.ndjson")
                if a.redo or not os.path.exists(held):
                    hold_rows(gm_compat, held, a.hold_stride)
                gm_compat = held
            if not a.reuse_v2:
                trk_dir = os.path.join(TS, f"trk_{label}", video)
                trk_compat = os.path.join(trk_dir, f"trackers{video}.ndjson")
                trk_report = os.path.join(trk_dir, f"tracker_v2_report{video}.json")  # written last: a run that died has none
                if a.redo or not os.path.exists(trk_report):
                    cmd = [PY, "scripts/tracker_v2_run.py", "--video", p["video"], "--gm-ndjson", gm_compat, "--seed", "0",
                           "--exact-fast", "--no-profile", "--out-dir", trk_dir, "--compare", p["trk_compat"]]
                    cmd += ["--cone-camera"] if plan.cone(video) else []
                    cmd += shlex.split(a.tracker_args)
                    if a.hold_stride > 1:
                        cmd += ["--stride", str(a.hold_stride)]
                    log(lf, f"{video}: tracker")
                    rc = run(cmd, os.path.join(p["logs"], f"tracker_{label}.log"))
                    if rc or not os.path.exists(trk_report):
                        log(lf, f"{video}: tracker FAILED rc={rc}")
                        continue
                inf = os.path.join(TS, f"{label}_inf", video)
                orch.link_into(gm_compat, os.path.join(inf, f"general_model{video}.ndjson"))
                orch.link_into(trk_compat, os.path.join(inf, f"trackers{video}.ndjson"))

            modules = sorted(os.path.basename(x)[:-5] for x in glob.glob(orch.module_out("v2", video, "*")))
            if a.modules:  # a listed module without a v2 result for this video has nothing to pair with
                modules = [m for m in a.modules.split(",") if m in modules]
            pending = []
            for module in modules:
                out = orch.module_out(label, video, module)
                if not a.redo and os.path.exists(out):
                    continue
                pending.append((module, module_command(plan, label, video, module, inf, a.module_args)))
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
        tot = json.load(io.open(out, encoding="utf-8")).get("totals", {})
        log(lf, "paired vs v2: " + json.dumps({k: tot.get(k, 0) for k in (
            "paired", "paired_equal", "paired_with_truth", "paired_ours_correct", "paired_baseline_correct", "missing")}))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
