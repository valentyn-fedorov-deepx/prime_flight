"""Collect ADR-002 camera votes for a video from an existing second-run GM file — no GM rows, no detectors.

The main aircraft is read from the class-2 rows of the second-run file (v1's `max_time_plane_history`, the frames the exact
second pass classifies on), so every vote lies on the final main-aircraft track; the rest is `pf.gm.buffered.CameraVoteBuffer`
on the replay path (own noise preprocessor updated on every frame, the v1 classifier on every 8th frame with the main
aircraft). Use it where only a production GM output exists — e.g. the wing-camera videos of the test set — and decide with
`scripts/gm_decide_buffered.py --no-aircraft-type` and the tracker file of the same video.

    python scripts/gm_buffered_votes.py --video out/testset/videos/<video> \
        --second-run out/testset/prod/<video>/general_model<video>.ndjson \
        --out out/gm_buffered/prod/<video>/gm_buffered_votes<video>.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class SecondRunMainAircraft:
    """The aircraft-tracker interface `CameraVoteBuffer.observe` reads (`tracks`, `longest()`), fed from class-2 rows."""

    def __init__(self):
        self.frames: dict = {}
        self.first_track_at = None

    def add(self, frame_id: int, box) -> None:
        self.frames[frame_id] = box
        if self.first_track_at is None:
            self.first_track_at = frame_id

    @property
    def tracks(self) -> dict:
        return {1: self.frames}

    def longest(self):
        return 1 if self.frames else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--second-run", required=True, help="second-run GM ndjson whose class-2 rows mark the main aircraft")
    ap.add_argument("--weights-dir", default=os.path.join(ROOT, "external", "general_model_prod", "weights"))
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--airplane-id", type=int, default=2)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import cv2

    from pf.gm.buffered import CameraVoteBuffer
    from pf.gm.camera import CameraClassifier
    from pf.tracker.fast_sigma import estimate_sigma_rgb

    t_init = time.perf_counter()
    buffer = CameraVoteBuffer(CameraClassifier(a.weights_dir, device=a.device, transform="numpy"),
                              noise_fn=lambda img: float(estimate_sigma_rgb(img)))
    init_s = time.perf_counter() - t_init
    aircraft = SecondRunMainAircraft()
    cap = cv2.VideoCapture(a.video)
    frames, t_decode = 0, 0.0
    t0 = time.perf_counter()
    with io.open(a.second_run, "rb") as fh:
        for position, line in enumerate(fh, 1):
            ((key, rows),) = json.loads(line).items()
            frame_id = int(key)
            if frame_id != position:
                raise SystemExit(f"second-run keys must be contiguous from 1 (key {frame_id} at line {position})")
            td = time.perf_counter()
            ok, img = cap.read()
            t_decode += time.perf_counter() - td
            if not ok:
                raise SystemExit(f"video ended before frame {frame_id}")
            for *xyxy, _conf, cls_id in rows:
                if int(cls_id) == a.airplane_id:
                    aircraft.add(frame_id, [int(x) for x in xyxy])
            buffer.observe(frame_id, img, aircraft)
            frames += 1
    cap.release()
    total = time.perf_counter() - t0
    buffer.finalize(aircraft.frames)
    cost = buffer.cost_ms_per_frame(frames, init_s=init_s)
    cost["replay_decode"] = round(1000 * t_decode / max(frames, 1), 3)
    cost["replay_end_to_end"] = round(1000 * total / max(frames, 1), 3)
    video = os.path.basename(a.video)
    out = {
        "video": video,
        "second_run": a.second_run,
        "number_of_frames": frames,
        "main_aircraft_frames": len(aircraft.frames),
        "buffered_votes": buffer.as_report(aircraft=aircraft, variant="second_run_class2_rows"),
        "buffered_decisions_cost_ms_per_frame": cost,
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({"video": video, "frames": frames, "votes": len(buffer.votes), "cost": cost}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
