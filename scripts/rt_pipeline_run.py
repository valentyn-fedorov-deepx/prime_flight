"""Real-time GM + tracker + one production module in the real-time branch, compared with the batch files.

The module runs through `pf.rt.simulate --adapter pipeline` with the launch facts of the test set (checkout, overlays,
device, environment). GM v2 and Tracker v2 run per frame inside the branch (detector heads and tracked classes selectable)
and the module is fed the rows they produce. Afterwards, per run:
  * verdict and report against the batch runs on the GM v2 + Tracker v2 files (label v2) and on the production files (ctl);
  * the GM second-run rows handed to the module against the batch GM v2 second-run file (all classes; the module's classes);
  * the airplane tracker records against the batch Tracker v2 file (seed 0): boxes, status, arrival and departure frames;
  * frame latency, keeps-up, cost per frame per component, process memory.

    python scripts/rt_pipeline_run.py --video zHxIAF2vUGxJ.mp4 --module pushback-pathway-confirmed-clear-of-obstacles \
        --tag pp_full_rt [--speed 1] [--max-seconds 120] [--heads gm,chocks,vehicle] \
        [--tracker-classes airplane,beltloader,gse,person] [--provider cuda|tensorrt] [--no-write-rows]
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

from scripts.rt_modules import adapter_args  # noqa: E402
from scripts.testset import orchestrate as o  # noqa: E402
from scripts.testset import profiles  # noqa: E402

STR2ID = os.path.join(ROOT, "external", "cv_common", "global_config.yaml")


def module_classes(module: str) -> list:
    mods = json.load(io.open(os.path.join(ROOT, "docs", "analysis", "module_consumption.json"), encoding="utf-8"))["modules"]
    gm = mods.get(module, {}).get("gm", {})
    return sorted(set(gm.get("class_names", [])) | set(gm.get("class_names_cosmetic", [])))


def gm_parity(batch_path: str, live_path: str, keep_names=None) -> dict:
    from pf.eval.parity import compare_gm_ndjson_tolerant
    from pf.gm.rows import ClassMap
    from scripts.gm_v2_run import load_str2id

    kwargs = {}
    if keep_names:
        cm = ClassMap(load_str2id(STR2ID))
        keep = {cm.id(n) for n in keep_names if n in cm.str2id}
        kwargs["ignore_classes"] = tuple(sorted(set(range(64)) - keep))
    summary = compare_gm_ndjson_tolerant(batch_path, live_path, **kwargs).summary()
    summary.pop("first_diffs", None)
    return summary


def tracker_parity(batch_path: str, live_path: str, cls: str = "airplane") -> dict:
    """Frame by frame (files are in publication order = frame order): the records of one class."""
    frames = same_boxes = same_state = 0
    first_diff = None
    anchors = {"batch": {}, "live": {}}
    keys = ("_status", "arrival_frame", "departure_frame")
    with io.open(batch_path, encoding="utf-8") as fb, io.open(live_path, encoding="utf-8") as fl:
        for n, (lb, ll) in enumerate(zip(fb, fl), 1):
            rb = [r for r in next(iter(json.loads(lb).values()), []) if r.get("cls_str") == cls]
            rl = [r for r in next(iter(json.loads(ll).values()), []) if r.get("cls_str") == cls]
            for side, recs in (("batch", rb), ("live", rl)):
                for r in recs:
                    sd = r.get("state_dict") or {}
                    for k in ("arrival_frame", "departure_frame"):
                        if sd.get(k) not in (None, [], [None]) and k not in anchors[side]:
                            anchors[side][k] = {"value": sd.get(k), "first_published_line": n}
            if not rb and not rl:
                continue
            frames += 1
            boxes = len(rb) == len(rl) and all(x.get("xyxy") == y.get("xyxy") for x, y in zip(rb, rl))
            state = boxes and all(all((x.get("state_dict") or {}).get(k) == (y.get("state_dict") or {}).get(k) for k in keys)
                                  for x, y in zip(rb, rl))
            same_boxes += boxes
            same_state += state
            if not state and first_diff is None:
                first_diff = {"line": n,
                              "batch": [(r.get("xyxy"), (r.get("state_dict") or {}).get("_status")) for r in rb],
                              "live": [(r.get("xyxy"), (r.get("state_dict") or {}).get("_status")) for r in rl]}
    return {"class": cls, "frames_with_records": frames, "same_boxes": same_boxes, "same_boxes_and_state": same_state,
            "share_same": round(same_state / frames, 4) if frames else None, "anchors": anchors, "first_diff": first_diff}


def head_of_file(src: str, dst: str, n: int) -> str:
    with io.open(src, encoding="utf-8") as fin, io.open(dst, "w", encoding="utf-8", newline="\n") as fout:
        for i, line in enumerate(fin):
            if i >= n:
                break
            fout.write(line)
    return dst


def summarise(a, out: str, rc: int, wall_s: float) -> dict:
    run = os.path.join(ROOT, out)
    p = o.paths(a.video)
    rec = {"video": a.video, "module": a.module, "tag": a.tag, "speed": a.speed, "max_seconds": a.max_seconds,
           "heads": a.heads, "tracker_classes": a.tracker_classes, "provider": a.provider, "exit_code": rc,
           "wall_s": round(wall_s, 1)}
    report_path = os.path.join(run, "report.json")
    if not os.path.exists(report_path):
        rec["error"] = "no report (see the run log)"
        return rec
    r = json.load(io.open(report_path, encoding="utf-8"))
    outs = [json.loads(line) for line in io.open(os.path.join(run, "outputs.ndjson"), encoding="utf-8")]
    verdict = next((x for x in outs if x["kind"] == "verdict"), None)
    error = next((x for x in outs if x["name"] == "module_error"), None)
    audit = next((x for x in outs if x["name"] == "real_time_audit"), {}).get("payload", {})
    live = (verdict or {}).get("payload", {})
    comparable = not a.max_seconds  # batch verdicts cover the whole video
    for label in ("v2", "ctl"):
        bp = os.path.join(ROOT, "out", "testset", "modules", label, a.video, f"{a.module}.json")
        b = json.load(io.open(bp, encoding="utf-8")) if os.path.exists(bp) else {}
        rec[f"batch_{label}"] = {
            "status": b.get("status"),
            "status_identical": (live.get("status") == b.get("status")) if verdict and b and comparable else None,
            "report_identical": (live.get("report") == b.get("report")) if verdict and b and comparable else None}
    if not comparable:
        rec["verdict_note"] = "partial run: the batch verdicts cover the whole video, not compared"
    rec.update({
        "live_status": live.get("status"), "live_report": live.get("report"),
        "decided_after_frame": live.get("decided_after_frame"), "session_closed_at_decision": live.get("session_closed"),
        "verdict_latency_s": (verdict or {}).get("latency_s"), "module_error": (error or {}).get("payload", {}).get("error"),
        "frames": r.get("frames"), "keeps_up": r.get("keeps_up"), "pipeline_ms_per_frame": r.get("module_ms_per_frame"),
        "frame_latency_s": r.get("frame_latency_s"),
        "latency_drift_s_per_recording_minute": r.get("latency_drift_s_per_recording_minute"),
        "max_frame_queue": r.get("max_frame_queue"), "runtime_error": r.get("error"),
        "non_causal_reads": audit.get("non_causal_reads"),
    })
    pipeline_path = os.path.join(run, "pipeline_report.json")
    if os.path.exists(pipeline_path):
        pj = json.load(io.open(pipeline_path, encoding="utf-8"))
        rec.update({"components_ms_per_frame": pj.get("ms_per_frame"),
                    "tracker_ms_per_frame": (pj.get("tracker") or {}).get("timings_ms_per_frame"),
                    "gm_heads": pj.get("gm_heads"), "memory_gb": pj.get("process_memory_gb"), "init_s": pj.get("init_s"),
                    "max_unpublished_frames": pj.get("max_unpublished_frames"),
                    "row_files_ms_per_frame": pj.get("row_files_ms_per_frame")})
    live_gm = os.path.join(run, f"general_model{a.video}.ndjson")
    live_trk = os.path.join(run, f"trackers{a.video}.ndjson")
    if os.path.exists(live_gm) and os.path.getsize(live_gm):
        n = sum(1 for _ in io.open(live_gm, encoding="utf-8"))
        batch_gm = p["gm_compat"] if not a.max_seconds else head_of_file(p["gm_compat"], os.path.join(run, "batch_gm_head.ndjson"), n)
        classes = module_classes(a.module) + ["airplane"]
        rec["gm_rows_vs_batch_v2"] = {
            "all_classes": gm_parity(batch_gm, live_gm),
            "module_classes_and_airplane": gm_parity(batch_gm, live_gm, classes),
            # the batch file writes obstacle rows with the FINAL layout from frame 1; a causal branch cannot (streaming_v0.md)
            "module_classes_and_airplane_without_obstacles": gm_parity(
                batch_gm, live_gm, [c for c in classes if c not in ("obstacle", "side_obstacle")])}
    if os.path.exists(live_trk) and os.path.getsize(live_trk):
        rec["tracker_vs_batch_v2"] = tracker_parity(p["trk_compat"], live_trk)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--module", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--heads", default="gm,chocks,vehicle")
    ap.add_argument("--tracker-classes", default="airplane,beltloader,gse,person")
    ap.add_argument("--provider", default="cuda", choices=["cuda", "tensorrt"])
    ap.add_argument("--chunks", default=None, help="default out/rt/chunks/<video stem>_gop1")
    ap.add_argument("--no-write-rows", action="store_true", help="timing runs: do not write the rows handed to the module")
    a = ap.parse_args()

    stem = os.path.splitext(a.video)[0]
    chunks = a.chunks or os.path.join("out", "rt", "chunks", f"{stem}_gop1")
    out = os.path.join("out", "rt", "runs", a.tag)
    os.makedirs(os.path.join(ROOT, out), exist_ok=True)
    plan = o.Plan([a.video])
    prof = profiles.profile(a.module)
    margs = adapter_args(a.module, a.video, plan, os.path.join("out", "rt", "work", a.tag))
    pargs = {"module": a.module, "module_args": margs, "heads": [h for h in a.heads.split(",") if h],
             "gm_variant": "entity_clip", "gm_provider": a.provider,
             "tracker_classes": [c for c in a.tracker_classes.split(",") if c], "exact_fast": True, "seed": 0,
             "cone_camera": plan.cone(a.video), "pixels": not prof.get("pixel_free"), "out_dir": out,
             "write_rows": not a.no_write_rows}
    cmd = [sys.executable, "-m", "pf.rt.simulate", "--chunks", chunks, "--adapter", "pipeline", "--adapter-args",
           json.dumps(pargs), "--out", out, "--speed", str(a.speed)]
    if a.max_seconds:
        cmd += ["--max-seconds", str(a.max_seconds)]
    t0 = time.time()
    with io.open(os.path.join(ROOT, out + ".log"), "w", encoding="utf-8") as log:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
    summary = summarise(a, out, rc, time.time() - t0)
    with io.open(os.path.join(ROOT, out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, default=str)
    brief = {k: summary.get(k) for k in ("exit_code", "error", "module_error", "runtime_error", "live_status", "batch_v2",
                                         "batch_ctl", "decided_after_frame", "keeps_up", "pipeline_ms_per_frame",
                                         "frame_latency_s", "max_unpublished_frames", "memory_gb", "wall_s")}
    brief["components_mean_ms"] = {k: (v or {}).get("mean") for k, v in (summary.get("components_ms_per_frame") or {}).items()}
    brief["tracker_ms"] = summary.get("tracker_ms_per_frame")
    brief["gm_parity_module_classes"] = {k: ((summary.get("gm_rows_vs_batch_v2") or {}).get("module_classes_and_airplane") or {}).get(k)
                                         for k in ("pair_recall", "frame_parity_tolerant")}
    brief["tracker_parity"] = {k: (summary.get("tracker_vs_batch_v2") or {}).get(k)
                               for k in ("frames_with_records", "share_same", "anchors")}
    print(json.dumps(brief, indent=1, default=str))
    return 0 if rc == 0 else rc


if __name__ == "__main__":
    raise SystemExit(main())
