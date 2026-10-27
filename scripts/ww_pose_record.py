"""Wing walkers (M27) under several pose models in one run, to fit its hand-signal rule to a new pose model.

The module decides with its own HRNet-W48 (`run_module.py --pose-timing`). On every one of its pose calls inside the
departure window the same boxes and frame also go through the shared runner (`pf/pose/topdown_onnx.py`) in the variants
below, and the run's other decision inputs are kept: the window, the airplane type, the wing walkers of each side with
their frame counts and the blocked share of each side. Who is a wing walker comes from the paths of the tracks, never
from the pose, so every variant gets the same walkers, frames and boxes, and the hand-signal rule can be replayed for any
model and threshold (`scripts/ww_pose_replay.py`).

  hrnet     the module's own HRNet-W48 on the CLAHE frame (what it decided with)
  rtm       RTMPose-l on the CLAHE frame (= run_module.py --pose-override rtmpose-l)
  rtm_raw   RTMPose-l on the frame without CLAHE
  rtm_flip  RTMPose-l with flip test, CLAHE frame
  dw        DWPose-l, body keypoints, CLAHE frame

    python scripts/ww_pose_record.py --dump out/pose/ww/<video>.json -- <run_module.py arguments, with --pose-timing>
"""

from __future__ import annotations

import importlib
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VARIANTS = {  # name: (model, flip test, CLAHE frame)
    "rtm": ("rtmpose-l", False, True),
    "rtm_raw": ("rtmpose-l", False, False),
    "rtm_flip": ("rtmpose-l", True, True),
    "dw": ("dwpose-l", False, True),
}
ARM = (9, 7, 10, 8)  # wrist_l, elbow_l, wrist_r, elbow_r: the order of the module's handsign_stats rows


def main() -> int:
    if "--" not in sys.argv or sys.argv.index("--dump") > sys.argv.index("--"):
        raise SystemExit("usage: ww_pose_record.py --dump PATH -- <run_module.py arguments>")
    dump_path = os.path.abspath(sys.argv[sys.argv.index("--dump") + 1])
    rm_args = sys.argv[sys.argv.index("--") + 1:]
    entry = rm_args[rm_args.index("--entry") + 1] if "--entry" in rm_args else "main"
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    sys.path.append(ROOT)
    import numpy as np

    import run_module  # scripts/run_module.py
    from pf.pose.topdown_onnx import SimccTopdown

    runners: dict = {}
    extra_s = {name: 0.0 for name in VARIANTS}
    rows: dict = {name: {} for name in VARIANTS}  # variant -> track id -> [[frame, wl, el, wr, er, box], ...]
    captured: dict = {}
    state: dict = {}

    def arm_row(frame, kp, sc, box):
        return [int(frame)] + [[round(float(kp[j, 0]), 2), round(float(kp[j, 1]), 2), round(float(sc[j]), 4)]
                               for j in ARM] + [[int(v) for v in box]]

    def patch(prod) -> None:
        state["prod"] = prod
        check_orig = prod.WingWalker.check_hand_signals  # bound to the class

        def check_hand_signals(cls, main_plane, dataset, workers_tracks, pose_model, visualizer, frame_number, *a, **k):
            if workers_tracks and main_plane.start_moving_frame is not None:  # the frames the module keeps stats for
                boxes = np.asarray([prod.add_offset(t.xyxy, offset_x=0.1, offset_y=0.1) for t in workers_tracks],
                                   dtype=np.float64)
                ids = [int(t.tr_id) for t in workers_tracks]
                raw = dataset.get_im0s(frame_number).copy()
                clahe = prod.apply_clahe_to_color_image(raw.copy())
                for name, (model, flip, use_clahe) in VARIANTS.items():
                    if name not in runners:
                        runners[name] = SimccTopdown(model, device="cuda", flip_test=flip)
                    t0 = time.perf_counter()
                    kp, sc, _, _ = runners[name](clahe if use_clahe else raw, boxes)
                    extra_s[name] += time.perf_counter() - t0
                    for i, tid in enumerate(ids):
                        rows[name].setdefault(tid, []).append(arm_row(frame_number, kp[i], sc[i], boxes[i]))
            return check_orig(main_plane, dataset, workers_tracks, pose_model, visualizer, frame_number, *a, **k)

        prod.WingWalker.check_hand_signals = classmethod(check_hand_signals)

        trajectories_orig = prod.compute_trajectories

        def compute_trajectories(points_to_draw, start_moving, stop_frame, airplane_type, *a, **k):
            captured.update(start_moving=int(start_moving), stop_frame=int(stop_frame), airplane_type=airplane_type)
            return trajectories_orig(points_to_draw, start_moving, stop_frame, airplane_type, *a, **k)

        prod.compute_trajectories = compute_trajectories

        analyze_orig = prod.analyze_trajectories

        def analyze_trajectories(trajectories, *a, **k):
            side, walkers = analyze_orig(trajectories, *a, **k)
            captured["side_wing_walker"] = {s: bool(v) for s, v in side.items()}
            captured["wing_walkers"] = {s: [int(w) for w in ids] for s, ids in walkers.items()}
            captured["frames_observed"] = {key.split()[-1]: int(t.frames_observed) for key, t in trajectories.items()
                                           if key.startswith("worker ")}
            return side, walkers

        prod.analyze_trajectories = analyze_trajectories

        decide_orig = prod.check_wing_walkers

        def check_wing_walkers(points_to_draw, start_moving, stop_frame, main_plane, wand_counter, not_observed_frames,
                               airplane_type, *a, **k):
            captured["blocked_share"] = {}
            for side in ("left_side", "right_side"):
                arr = np.asarray(not_observed_frames[side])
                captured["blocked_share"][side] = float(np.sum((arr >= start_moving) & (arr < stop_frame))
                                                        / (stop_frame - start_moving))
            out = decide_orig(points_to_draw, start_moving, stop_frame, main_plane, wand_counter, not_observed_frames,
                              airplane_type, *a, **k)
            captured["decision"] = {"status": out[0], "report": out[1]}
            return out

        prod.check_wing_walkers = check_wing_walkers

    import_orig = importlib.import_module

    def import_module(name, package=None):
        mod = import_orig(name, package)
        if name == entry and hasattr(mod, "WingWalker") and "prod" not in state:
            patch(mod)
        return mod

    importlib.import_module = import_module
    sys.argv = ["run_module.py"] + rm_args
    rc = run_module.main()
    importlib.import_module = import_orig

    hrnet = {}
    prod = state.get("prod")
    if prod is not None:
        for tid, stats in prod.WingWalker.handsign_stats.items():  # already cut to the window by check_wing_walkers
            hrnet[int(tid)] = [[int(s[0])] + [[round(float(v), 2) for v in p[:2]] + [round(float(p[2]), 4)]
                                              for p in s[1:5]] + [[int(v) for v in s[5]]] for s in stats]
    out = {"args": rm_args, "rc": rc, "captured": captured, "rows": {"hrnet": hrnet, **rows},
           "runners": {name: {**r.describe(), "extra_s": round(extra_s[name], 2)} for name, r in runners.items()}}
    os.makedirs(os.path.dirname(dump_path), exist_ok=True)
    with io.open(dump_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print(f"wing walkers recorded: {sum(len(v) for v in rows['rtm'].values())} rows per variant -> {dump_path}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
