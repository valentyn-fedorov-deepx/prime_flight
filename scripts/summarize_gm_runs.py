"""Summarise GM v2 full-video runs (`scripts/gm_v2_run.py` reports) into a markdown table and a JSON file.

Reads `out/*_full_v2/gm_v2_report<video>.json` (runs made with `--compare` against the production second-run file) and
reports, per video: frames, end-to-end ms/frame and real-time factor (only comparable between runs made on an idle
machine), and the L1 parity of the regenerated second-run file against production — exact frame parity and the tolerant
metric (pair recall, pairs within ±2 px / ±0.02 conf, frames fully within tolerance, coordinate p99, confidence max).

    python scripts/summarize_gm_runs.py --glob "out/*_full_v2/gm_v2_report*.json" --out docs/analysis/parity/gm_v2_atlc5_summary.json
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--glob", default="out/*_full_v2/gm_v2_report*.json")
    ap.add_argument("--out", default="docs/analysis/parity/gm_v2_atlc5_summary.json")
    ap.add_argument("--contended", default="", help="comma-separated video ids whose timings overlapped other GPU jobs")
    a = ap.parse_args()
    contended = {v.strip() for v in a.contended.split(",") if v.strip()}

    rows = []
    for p in sorted(glob.glob(a.glob)):
        r = json.load(io.open(p, encoding="utf-8"))
        video = os.path.basename(p).replace("gm_v2_report", "").replace(".mp4.json", "")
        t = r.get("timings_ms_per_frame") or {}
        tol = r.get("parity_vs_production_tolerant") or {}
        ex = r.get("parity_vs_production") or {}
        pairs = tol.get("pairs") or 0
        rows.append({
            "video": video,
            "frames": r.get("number_of_frames"),
            "ms_per_frame": t.get("end_to_end"),
            "realtime_factor": t.get("realtime_factor_at_fps"),
            "decode_ms": t.get("decode"),
            "timing_contended": video in contended,
            "detections_production": tol.get("dets_a"),
            "detections_v2": tol.get("dets_b"),
            "pair_recall": tol.get("pair_recall"),
            "pairs_within_tolerance": round(tol["pairs_within_tolerance"] / pairs, 6) if pairs else None,
            "frames_within_tolerance": tol.get("frame_parity_tolerant"),
            "frames_bit_exact": ex.get("frame_parity"),
            "coord_delta_p99_px": (tol.get("coord_delta_px") or {}).get("p99"),
            "conf_delta_max": (tol.get("conf_delta") or {}).get("max"),
            "unmatched_production": tol.get("unmatched_a"),
            "unmatched_v2": tol.get("unmatched_b"),
        })

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"runs": rows}, fh, indent=1)

    def pct(x):
        return "—" if x is None else f"{100 * x:.2f} %"

    print("| video | frames | ms/frame (RT×) | pair recall | pairs within ±2 px/±0.02 | frames within tolerance | frames bit-exact | coord p99 px | conf Δ max |")
    print("|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        speed = f"{row['ms_per_frame']} ({row['realtime_factor']}×)" + (" *" if row["timing_contended"] else "")
        print(f"| {row['video']} | {row['frames']} | {speed} | {pct(row['pair_recall'])} | {pct(row['pairs_within_tolerance'])} | "
              f"{pct(row['frames_within_tolerance'])} | {pct(row['frames_bit_exact'])} | {row['coord_delta_p99_px']} | {row['conf_delta_max']} |")
    if contended:
        print("\n\\* timing overlapped other GPU jobs — not comparable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
