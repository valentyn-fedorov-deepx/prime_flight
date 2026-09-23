"""What production gives a job and what a job takes today: the pod envelope and the measured time to result.

Two measurements that come from the cluster, not from this machine:

  * `docs/inbox/2026-09-23_cluster_pod_max_resources.xlsx` - the maximum one pod can reach (measured 23.09 on a test node of
    each pool), per module: pool, vCPU, RAM, GPU and its rates, scratch disk;
  * the time-to-result breakdown of the monthly sheet (median of 148 videos, 10-22 Sep, about 87 min long), typed in below.

Writes `docs/analysis/production_envelope.json`, which `scripts/rt_environment.py` reads to size the real-time branch in the
same envelope.

    python scripts/production_envelope.py
"""

from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

XLSX = os.path.join(ROOT, "docs", "inbox", "2026-09-23_cluster_pod_max_resources.xlsx")
# Median over 148 videos of 10-22 Sep, about 87 min long (the lead's sheet, 23.09). Hours per video, wall clock: a stage is
# the time from the previous artefact to this one, so the queue waits are in "waiting"/"until ... starts" rows.
TIME_TO_RESULT_H = {
    "last chunk filmed, until it is in the bucket": 9.5,
    "merge waiting to start": 1.7,
    "merge running": 0.8,
    "merged file arrived, until GM starts": 0.1,
    "GM running": 2.4,
    "GM finished, until the tracker starts": 0.1,
    "tracker running": 1.3,
    "modules, until the video is done": 0.9,
}
TOTALS_H = {"merged file to results": 5.0, "chunks uploaded to results": 8.6, "recorded to results": 20.3}
VIDEO_MINUTES = 87
VIDEOS = 148


def pods() -> dict:
    import openpyxl

    ws = openpyxl.load_workbook(XLSX, data_only=True)["max per pod"]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h).strip() if h else "" for h in rows[0]]
    per_module, pools, notes = {}, {}, []
    for row in rows[1:]:
        rec = {h: v for h, v in zip(header, row) if h}
        name, pool = rec.get("module"), rec.get("pool")
        if not name:
            continue
        if not pool:
            notes.append(str(name))
            continue
        per_module[name] = pool
        pools.setdefault(pool, {k: v for k, v in rec.items() if k != "module"})
    return {"per_module": per_module, "pools": pools, "notes": notes}


def main() -> int:
    p = pods()
    video_s = VIDEO_MINUTES * 60
    gpu_pod_h = TIME_TO_RESULT_H["GM running"] + TIME_TO_RESULT_H["tracker running"]
    result = {
        "source": {"pods": os.path.relpath(XLSX, ROOT), "time_to_result": f"monthly sheet, median of {VIDEOS} videos, 10-22 Sep"},
        "pools": p["pools"], "module_pool": p["per_module"], "notes": p["notes"],
        "modules_per_pool": {pool: sorted(m for m, x in p["per_module"].items() if x == pool) for pool in p["pools"]},
        "time_to_result_h": TIME_TO_RESULT_H, "totals_h": TOTALS_H, "video_minutes": VIDEO_MINUTES, "videos": VIDEOS,
        "per_video": {
            "gm_x_real_time": round(TIME_TO_RESULT_H["GM running"] * 60 / VIDEO_MINUTES, 2),
            "tracker_x_real_time": round(TIME_TO_RESULT_H["tracker running"] * 60 / VIDEO_MINUTES, 2),
            "modules_wall_x_real_time": round(TIME_TO_RESULT_H["modules, until the video is done"] * 60 / VIDEO_MINUTES, 2),
            "gm_ms_per_frame": round(TIME_TO_RESULT_H["GM running"] * 3600 * 1000 / (video_s * 8), 1),
            "tracker_ms_per_frame": round(TIME_TO_RESULT_H["tracker running"] * 3600 * 1000 / (video_s * 8), 1),
            "gpu_pod_hours_gm_and_tracker": round(gpu_pod_h, 2),
            "gpu_pod_hours_per_recorded_hour": round(gpu_pod_h / (VIDEO_MINUTES / 60), 2),
        },
    }
    out = os.path.join(ROOT, "docs", "analysis", "production_envelope.json")
    json.dump(result, io.open(out, "w", encoding="utf-8", newline="\n"), indent=1, default=str)
    print(json.dumps({"pools": list(result["pools"]), "per_video": result["per_video"],
                      "modules_per_pool": {k: len(v) for k, v in result["modules_per_pool"].items()}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
