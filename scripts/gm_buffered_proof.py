"""Proof that `scripts/gm_v2_run.py --buffered-decisions` only adds report fields and leaves the rows byte-identical.

Slice mode runs GM v2 twice on the same frames (flag off, then flag on; one GPU job at a time) and compares the first-run
and second-run ndjson files byte for byte (SHA-256, sizes) and the reports (the flag may only add `buffered_votes` and
`buffered_decisions_cost_ms_per_frame`; every non-timing value must be equal). Directory mode compares two existing output
directories, e.g. a full flagged run against the test-set run written without the flag.

    python scripts/gm_buffered_proof.py slice --video out/testset/videos/<video> --max-frames 4000 \
        --weights-dir external/general_model_prod/weights --variant entity_clip --parallel-heads \
        --out-dir out/gm_buffered/slice_<video>_4000
    python scripts/gm_buffered_proof.py dirs --video-name <video> --a out/testset/gm_v2/<video> --b out/gm_buffered/<video>
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDED_FIELDS = {"buffered_votes", "buffered_decisions_cost_ms_per_frame"}
TIMING_FIELDS = {"timings_ms_per_frame"}


def file_digest(path: str) -> dict:
    h = hashlib.sha256()
    lines = 0
    with io.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            lines += chunk.count(b"\n")
    return {"sha256": h.hexdigest(), "bytes": os.path.getsize(path), "lines": lines}


def first_difference(a: str, b: str):
    with io.open(a, "rb") as fa, io.open(b, "rb") as fb:
        for i, (la, lb) in enumerate(zip(fa, fb), 1):
            if la != lb:
                return {"line": i, "a": la[:200].decode("utf-8", "replace"), "b": lb[:200].decode("utf-8", "replace")}
    return None


def compare_dirs(a: str, b: str, video: str) -> dict:
    out = {"a": a, "b": b, "files": {}}
    for name in (f"general_model{video}.ndjson", f"general_model{video}-second_run.ndjson"):
        pa, pb = os.path.join(a, name), os.path.join(b, name)
        da, db = file_digest(pa), file_digest(pb)
        entry = {"a": da, "b": db, "identical": da["sha256"] == db["sha256"]}
        if not entry["identical"]:
            entry["first_difference"] = first_difference(pa, pb)
        out["files"][name] = entry
    ra, rb = os.path.join(a, f"gm_v2_report{video}.json"), os.path.join(b, f"gm_v2_report{video}.json")
    if os.path.isfile(ra) and os.path.isfile(rb):
        with io.open(ra, encoding="utf-8") as fh:
            rep_a = json.load(fh)
        with io.open(rb, encoding="utf-8") as fh:
            rep_b = json.load(fh)
        keys_a, keys_b = set(rep_a), set(rep_b)
        shared = sorted((keys_a & keys_b) - TIMING_FIELDS)
        out["report"] = {
            "only_in_a": sorted(keys_a - keys_b),
            "only_in_b": sorted(keys_b - keys_a),
            "added_fields_expected": sorted(ADDED_FIELDS),
            "differing_values": [k for k in shared if rep_a[k] != rep_b[k]],
            "end_to_end_ms_per_frame": {"a": (rep_a.get("timings_ms_per_frame") or {}).get("end_to_end"),
                                        "b": (rep_b.get("timings_ms_per_frame") or {}).get("end_to_end")},
            "buffered_cost_b": rep_b.get("buffered_decisions_cost_ms_per_frame"),
        }
    out["rows_identical"] = all(e["identical"] for e in out["files"].values())
    rep = out.get("report")
    out["report_ok"] = rep is None or (not rep["differing_values"] and set(rep["only_in_b"]) <= ADDED_FIELDS
                                       and set(rep["only_in_a"]) <= ADDED_FIELDS)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("slice")
    s.add_argument("--video", required=True)
    s.add_argument("--max-frames", type=int, required=True)
    s.add_argument("--weights-dir", required=True)
    s.add_argument("--variant", default="prod", choices=["prod", "entity_clip", "master"])
    s.add_argument("--parallel-heads", action="store_true")
    s.add_argument("--out-dir", required=True)
    d = sub.add_parser("dirs")
    d.add_argument("--video-name", required=True)
    d.add_argument("--a", required=True, help="run without the flag (reference)")
    d.add_argument("--b", required=True, help="run with the flag")
    d.add_argument("--out", default=None)
    a = ap.parse_args()

    if a.mode == "slice":
        video = os.path.basename(a.video)
        dirs = {}
        for label, flag in (("off", []), ("on", ["--buffered-decisions"])):
            dirs[label] = os.path.join(a.out_dir, label)
            cmd = [sys.executable, os.path.join(ROOT, "scripts", "gm_v2_run.py"), "--video", a.video, "--weights-dir",
                   a.weights_dir, "--variant", a.variant, "--max-frames", str(a.max_frames), "--out-dir", dirs[label],
                   *(["--parallel-heads"] if a.parallel_heads else []), *flag]
            print("running:", " ".join(cmd), flush=True)
            subprocess.run(cmd, cwd=ROOT, check=True)
        result = compare_dirs(dirs["off"], dirs["on"], video)
        result["slice"] = {"video": a.video, "max_frames": a.max_frames, "variant": a.variant,
                           "parallel_heads": a.parallel_heads}
        out_path = os.path.join(a.out_dir, f"gm_buffered_proof{video}.json")
    else:
        result = compare_dirs(a.a, a.b, a.video_name)
        out_path = a.out or os.path.join(a.b, f"gm_buffered_proof_vs_{os.path.basename(os.path.normpath(a.a))}.json")
    with io.open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    print(json.dumps({"rows_identical": result["rows_identical"], "report_ok": result["report_ok"],
                      "files": {k: v["identical"] for k, v in result["files"].items()},
                      "report": {k: v for k, v in (result.get("report") or {}).items() if k != "buffered_cost_b"}}))
    return 0 if result["rows_identical"] and result["report_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
