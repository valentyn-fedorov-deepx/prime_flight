# M01 · 3 stop brake check

> Checks that every belt loader (BL) driving up to the aircraft makes at least three brake-check stops before its final
> stop at the cargo door. The tracker counts each loader's stops; the module judges each loader when it parks next to the
> aircraft.

## At a glance

| | |
|---|---|
| Checks | M01 · 3 stop brake check |
| Stage | Post-arrival, Download |
| Looks at | from the aircraft's arrival until its departure; each loader is judged when it parks next to the aircraft |
| Cameras | aircraft: both cameras; jet: wing camera (separate settings per camera) |
| Uses | General Model (GM) classes `gse`, `pushback`, `trailer` (only to spot a blocked view); tracks of the aircraft and belt loaders (status, stop count); video frames: no |
| Own models | none |
| Runs on | CPU |
| Real time | ready as is — a loader's stop count is final when it parks, so its verdict can be given at that moment |
| Production version | master @ 14685f4 (2026-05-07; last logic change 05cfc12, 2025-02-18) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | All stopped loaders made 3 stops before the final (4th) stop. |
| Fail | At least one of the stopped loaders made fewer than 3 stops. |
| Not observed | No loader stops were detected. |
| Not observed — view blocked | No obstacle logic in the rule. |

Client note: if a loader moves in reverse, its stop count is reset.

## How it decides

1. Picks the cone or wing settings from the camera type given by the pipeline.
2. Skips blocked frames: a GSE (ground support equipment), pushback or trailer box wider than **50 %** of the frame (cone)
   or **30 %** (wing), centred in the middle band, makes the module ignore the whole frame.
3. Waits for the tracker's arrival flag (the aircraft has stood still for about **4 s**); stops at the tracker's departure
   flag (about **10 s** of movement).
4. Follows every belt loader track. The tracker counts the stops: a stop counts when most tracked points on the loader stand
   still and the stop point is more than **5 %** of the loader's width from the previous one. If the loader stands still
   for **24 frames** (3 s) and then drives on for **16 frames** (2 s), the count goes back to zero.
5. A loader is parked when it has been "stopped" for **40 frames** (5 s) in a row, is at least **250 × 80 px** (cone) or
   **200 × 60 px** (wing), has left the place where tracking started (IoU with its first box below **0.5**) and its left
   edge lies between **10 %** and **85 %** of the frame width.
6. At that moment: more than **3** stops (three brake checks plus the final stop) → the loader passes; otherwise it fails.
7. The result counts only if the loader moved for at least **4 frames** (0.5 s) before parking and more than **20 %** of
   its box overlaps the aircraft box.
8. A parked loader that moves again for **16 frames** (2 s) loses its result and is judged again at its next park.
9. Verdict: any counted loader failed → Fail; all passed → Pass; none counted → Not observed.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `stop_thresh` | 40 frames (5 s) | time "stopped" before a loader counts as parked |
| `moving_thresh` | 16 frames (2 s) | movement after parking that clears the result |
| `moving_before_stop_thresh` | 4 frames (0.5 s) | movement needed before parking; the YAML comments say 1–1.5 s |
| `min_width` × `min_height` | cone 250 × 80 px; wing 200 × 60 px | smaller loaders are never judged |
| `bl_roi` | 0.1–0.85 of the width | allowed band for the loader's left edge |
| `obstacle_width` | cone 0.5; wing 0.3 | width of a blocking vehicle; the cone comment says 30 % |
| `obstacle_center_range` | cone 0.3–1.0; wing 0.1–0.9 | where the blocking box's centre must be |
| pass threshold (code) | stop count > 3 | three brake checks plus the final stop |
| overlap with the aircraft (code) | > 0.2 of the loader box | only loaders parked at the aircraft count |
| tracker `stopping_time_thres` | 24 frames (3 s) | a stop this long resets the count once the loader drives on |

## What it reports

- The verdict for the task `stopbrake`.
- Report text: "Beltloader <id> performed 3-stop-brake-checks on <hh:mm:ss>." per loader for Pass, "Beltloader <id> failed on
  <hh:mm:ss>." per failing loader for Fail, "No stopped beltloaders were detected" for Not observed.
- Smart timeline: one entry per loader of the final verdict's kind, `{Status, Start: first frame seen after arrival, End:
  decision frame}`; empty for Not observed.
- A per-frame drawing log (boxes, states, texts); an annotated video only when video writing is on.

## Known issues and limits

- Blocked frames are only skipped, so a loader hidden by a large vehicle ends as Not observed.
- No reverse detection: the tracker resets the count whenever a loader drives on after standing still for 3 s, in any
  direction. A brake-check stop longer than 3 s therefore wipes the earlier stops (to confirm on labelled videos).
- The stop count belongs to the shared tracker, so a tracker change can change this verdict; the architecture review asks
  for a replay comparison before swapping in a generic tracker status.
- The first timeline Start of a loader is written as a one-element list (`[frame]`), not a number — to confirm the website
  reads it.
- With several aircraft tracks in one frame, the last one listed wins. Report times assume 8 fps from the file start.
- Cameras: the worker settings file (`db_worker/ml_setting/ml_global_config.json`) lists the cone camera only; the client
  sheet says both — to confirm what runs in production.
- The README mentions "the biggest plane" and cone classes copied from another module; the code does neither.

## For developers

- **Repository:** `dxgat/detectors/3-stop-brake-check`; production line `master` @ `14685f4`; default branch the same.
  The architecture review pinned `3a2337c` on `not_observed_handling` (a reworked `main.py`), which is not in production.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera,
  json_logger)`; the `Loader` class (counters, parked test, pass/fail), the frame loop and `get_reports` are all in
  `main.py`; thresholds in `local_config.yaml`.
- **Dependencies:** `cv_common` 86731e4 (not in the local archive; the local copy is ac5098d, and the CI builds with
  cv_common master), `db_worker` 5a4aa83. Packages: norfair, opencv-python, numpy, torch (only `no_grad`). No weights;
  Docker image built on the CPU base image.
- **Run locally:** `python main.py --source <video>.mp4 --inferences-dir <folder with GM and tracker ndjson>
  [--cone-camera] [--write-video] [--json-fn <file>]`; `run_module.py` runs a batch of test videos.
- **Code references:** step 1 `main.py:226-227`; step 2 `main.py:278-304`; step 3 `main.py:311-355`; step 4
  `main.py:359-371`, `cv_common/tracked_object.py:51-53, 247-266, 274-277`; step 5 `main.py:76-94, 176-185`; step 6
  `main.py:106-120`; step 7 `main.py:187-190, 379-403`; step 8 `main.py:97-102, 388-391`; step 9 `main.py:193-221,
  444-459`.
