# M13 · All GSE guided into aircraft using approved hand signals

> Checks that every belt loader (BL) driving up to a cargo door is guided by a worker giving hand signals. When a loader
> stops at the door, the module runs a pose model on the worker who stood in front of the door during the approach; a
> raised hand for at least 1 s counts as a signal.

## At a glance

| | |
|---|---|
| Checks | M13 · All GSE guided into aircraft using approved hand signals |
| Stage | Post-arrival |
| Looks at | from the aircraft's arrival until its departure; for each loader, from 30 s to 5 s before it stops at the door |
| Cameras | aircraft: both cameras; jet: wing camera. Front cargo door on the cone camera, rear door on the wing camera |
| Uses | General Model (GM) classes `front_door` / `back_door`, `back_wheel`, `airplane_engine`; tracks of the aircraft, belt loaders and persons; video frames: yes |
| Own models | none trained by the team; runs the stock HRNet-W48 pose model (mmpose, COCO keypoints) to find elbows and wrists |
| Runs on | GPU |
| Real time | needs a new first pass — a first pass reads ahead to average the door position; the door must be fixed from the past only |
| Production version | master @ 60c0faf (2025-11-13; last logic change 6bd027f, 2025-07-30) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | All belt loaders that come to the aircraft's open doors have a person guiding them with visible hand signals. |
| Fail | No workers in the area during the approach, or workers but no valid hand signals, or the signals are too short. |
| Not observed | No belt loaders are seen approaching open doors, or no aircraft appeared in the video. |
| Not observed — view blocked | Large obstacles in the centre of the frame, or side obstacles larger than 1.5 × a person's height. |

## How it decides

1. **First pass:** after the tracker's arrival flag, averages the first **480** detections (60 s) of the cargo door
   (front door on the cone camera, rear door on the wing camera) as a fallback door position.
2. **Second pass**, after arrival: builds a "workers area" in front of the door, where the guide should stand. The door is
   the average of its last **80** detections (10 s), or the first-pass average until it is first seen. The area is
   **1.5 ×** (cone) or **3.5 ×** (wing) the door width, centred on the door, reaching below the aircraft's lower edge.
3. Once no loader has stood at the door for **60 frames** (7.5 s), persons whose feet are in the area are candidates. If
   a loader taller than **50 px** is moving, the pose model runs on them at once; otherwise the frame is buffered
   (up to **240 frames**, 30 s).
4. A loader has arrived when the tracker reports it stopped and its box overlaps the area (cone camera: right half only)
   with its lower edge inside the area's height. Loaders behind a rear wheel are ignored on the cone camera; the wing
   camera also accepts a loader hidden by the engine or face-on below the door. The biggest is taken; a new track id
   within **120 frames** (15 s) of the last loader is the same loader.
5. For each new loader the check runs once, only if the loader was moving within the last **80 frames** (10 s) and the
   area existed for more than **80 frames** in the look-back window; otherwise the loader "could not be analyzed".
6. The check poses the buffered frames and keeps poses from **240 to 40 frames** (30 s to 5 s) before the stop. The
   helper is the worker with the most poses in that window.
7. A frame shows a signal when the helper's wrist is at or above the elbow (5 px tolerance) on either arm, both keypoints
   with confidence ≥ **0.2**. At least **8 frames** (1 s) → registered; fewer, or no worker → not registered.
8. At departure or the end of the video, loaders followed for less than **480 frames** (60 s) are ignored. None left, or
   none analyzable → Not observed; otherwise the unanalyzable ones are dropped, all registered → Pass, any not → Fail.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `door_bbox_window_length` | 80 frames (10 s) | averaging window for the door and aircraft boxes |
| `max_prev_frame_to_consider` | 240 frames (30 s) | start of the look-back window; frame buffer size |
| `min_prev_frame_to_consider` | 40 frames (5 s) | the last 5 s before the stop are ignored |
| `moving_bl_history_length`, `min_roi_presence_time` | 80 frames (10 s) each | otherwise the loader "could not be analyzed" |
| signal rule (code) | wrist ≤ elbow + 5 px, confidence ≥ 0.2, ≥ 8 frames (1 s) | what counts as a hand signal |
| `min_bl_stay_time_thresh` | 480 frames (60 s) | shorter loader visits are not judged |
| `min_bl_swap_time_thresh` | 120 frames (15 s) | merges a new track id into the last loader; half of it gates worker collection |
| `max_occlusion_ratio`, `max_obstacle_rate` | 0.35, 0.5 | mark the area as obstructed; **not used** for the verdict |
| `min_bl_stay_iou_thresh`, `min_plane_type_frames_eval`, `obstacle_width` | 0.8, 40, 0.6 | not used for the verdict |

## What it reports

- The verdict for the task `handsignals`.
- Report text: "All of the beltloaders' hand signals were registered." or "Not all …", then "Beltloader <id> hand signals
  [NOT ]registered (<start> - <end>)." per judged loader; for Not observed, the reason.
- Smart timeline: one entry per judged loader, `{Status: Pass/Fail, Start: first frame, End: last frame}`.
- A per-frame drawing log with the workers' keypoints; an annotated video when video writing is on.

## Known issues and limits

- A raised wrist is a coarse stand-in for a hand signal: no approved-signal vocabulary, no wand check.
- No "view blocked" verdict: the obstruction is measured, but the line that would give Not observed is commented out.
- The driver filter is called with person id 0 hard-coded, so it practically never runs; a loader driver in the area
  could be picked as the helper.
- When every loader "could not be analyzed", the verdict is Not observed but the timeline entries say Fail.
- The look-back comment says 5–15 s; the code uses 5–30 s. The aircraft type (jet / aircraft) is computed but never used.
- "Open doors" is not checked separately; the module trusts the GM door detection (to confirm).
- Up to 240 full frames (≈1.5 GB) are buffered; up to ≈200 pose calls can run on one stop frame.
- The team's error review (`scripts/specialized_issues.txt`) names the signal rule, the worker position and missed
  aircraft, door and loader-approach detections.

## For developers

- **Repository:** `dxgat/detectors/hand-signals`; production line `master` @ `60c0faf`; default branch the same. The last
  commit only adds an issue list; `main.py` last changed in `6bd027f`, the commit the architecture review pinned.
- **Entry point:** `main.py` → `detect(...)`; all logic is in `main.py`: `AirplaneWithWorkersROI` (door, area),
  `collect_workers_history`, `find_beltloader` / `manage_beltloader` (arrival, trigger), `Beltloader.check_hand_signals`
  (the rule), `generate_report`.
- **Dependencies:** `cv_common` 8e3a7bf (not in the local archive; the local copy is ac5098d, cv_common master, which the
  CI builds with), `db_worker` 5a4aa83. Packages: mmpose 1.x, mmengine, opencv-python, torch. Weights by DVC:
  `td-hm_hrnet-w48_8xb32-210e_coco-256x192-0e67c616_20220913.pth`; the `hrnet_w48_coco_384x288_dark` copy is never
  loaded. Image built on the mmpose base image.
- **Run locally:** `python main.py --source <video>.mp4 --inferences-dir <folder with GM and tracker ndjson>
  --local-inferences --weights-dir weights [--cone-camera] [--write-video] [--device cpu]`.
- **Code references:** step 1 `main.py:761-797`; step 2 `main.py:128-179`; obstruction `main.py:181-220`; step 3
  `main.py:522-589, 886-891`; step 4 `main.py:467-520, 632-638`; step 5 `main.py:640-650`; step 6 `main.py:276-305,
  338-370`; step 7 `main.py:307-336`; step 8 `main.py:73-113, 386-388`; unused aircraft type `main.py:675-717, 919-920`.
