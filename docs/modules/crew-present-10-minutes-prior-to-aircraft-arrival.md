# M10 · Crew present 10 minutes prior to aircraft arrival

> Checks that a crew of at least three people is at the stand well before the aircraft arrives. It counts the people the General Model detects on each cone-camera frame and, when the aircraft stops, looks at the period from 12 to 8 minutes before the stop.

## At a glance

| | |
|---|---|
| Checks | M10 · Crew present 10 minutes prior to aircraft arrival |
| Stage | Pre-arrival |
| Looks at | From the start of the video until the aircraft stops; the count is taken from 12 to 8 min before the stop (from the video start to 1 min before the stop if the video starts less than 12 min before it) |
| Cameras | Cone camera, for aircraft and jets (the code does not read the camera flag) |
| Uses | General Model: `person` (crew count); GSE (ground support equipment), pushback and trailer boxes (blocked view). Tracks: aircraft. Video frames: no (annotated video only) |
| Own models | None |
| Runs on | CPU |
| Real time | Ready as is — one pass over detections and tracks, verdict at the aircraft stop (a warning before the arrival would need the scheduled arrival time) |
| Production version | `main` @ 5cfd25c (2026-02-12) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | More than 80 frames with three workers in the period from 12 to 8 minutes before arrival. |
| Fail | The opposite of Pass. |
| Not observed | There is no pre-arrival stage on the video (less than 4 minutes). |
| Not observed — view blocked | Blocked frames are more than 70% of the pre-arrival stage. |

## How it decides

1. Reads the detections and the aircraft track frame by frame from the start of the video.
2. Treats a frame as blocked when a GSE, pushback or trailer box is wider than **30%** of the frame (576 px) and its centre lies in the right **70%** of the image. Blocked frames are counted and otherwise skipped (no people counted, no aircraft update).
3. On every other frame counts all `person` detections anywhere in the image and remembers the frames with **3 or more** people.
4. Follows the widest aircraft track. The arrival counts as seen once the tracker shows the aircraft moving for more than **24 frames** (3 s) in a row; a frame where its tracked points jump more than **50 px** sideways or **5 px** up or down (camera shake) restarts the count. The pre-arrival counts as seen when the stop comes later than **60 s** into the video.
5. Decides once, on the first frame where the tracker reports the stop, in this order: stop within the first 60 s → **Not observed**; no person detected at all → **Fail**; blocked frames above **70%** of the frames before the stop → **Not observed**; stop less than **4 min** (1,920 frames) into the video → **Not observed**; arrival movement not seen → **Not observed**.
6. Picks the count window: **12 to 8 min** before the stop. If the stop is less than 12 min into the video, the window runs from the video start to **1 min** before the stop.
7. **Pass** if more than **80 frames** (10 s) in the window had 3 or more people, otherwise **Fail**. The frames do not need to be consecutive or show the same people.
8. Runs **60 s** more only to draw the result, then stops. If the aircraft never stops: **Not observed**.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `obstacle.width` | 0.3 | A GSE / pushback / trailer box wider than 30% of the frame blocks the view… |
| `obstacle.center` | 0.3–1 | …when its centre is in this horizontal band (share of the width) |
| `crew_presence.four_minutes_seconds` | 240 s | Minimum pre-arrival length, and the window length |
| `crew_presence.twelve_minutes_seconds` | 720 s | Not used — the code hard-codes 12 × 60 s |
| `crew_presence.min_enough_workers_seconds` | 10 s | Pass needs more than 80 frames with 3+ people in the window |
| `crew_presence.min_pre_arrival_seconds` | 60 s | The stop must come later than this |
| `crew_presence.prearrival_exclude_last_seconds` | 60 s | Short videos: the last minute before the stop is left out |
| `crew_presence.obstacle_frame_ratio_threshold` | 0.7 | Share of blocked frames that gives Not observed |
| `crew_presence.motion_anomaly_x_threshold` / `_y_threshold` | 50 px / 5 px | Point jumps treated as camera shake |
| `crew_presence.max_value_count_threshold` | 10 | Report only: the largest crew size seen on more than 10 frames |
| Crew size (code) | 3 | People needed on a frame |
| `criteria_for_fail`, `criteria_for_n_o`, `matching_th` | 0.33, 10, three values | Not used by the code |

## What it reports

- The verdict and one report line: Pass "Three or more workers were present for enough time during prearrival stage" with the time span; Fail gives the largest crew seen and the number of frames with 3+ people, or "No workers where detected on pre-arrival stage"; Not observed gives "No arrival stage", "No pre-arrival stage", "There was an obstacle.", "The pre-arrival stage was very short (less than 4 minutes)" or "Plane did not arrive".
- Smart timeline: one Pass or Fail block from the window start (frame 1 when nobody was detected) to the stop; empty for Not observed.
- Overlay log (`JsonLogger` ndjson): person boxes, worker counts, "Camera is blocked!", aircraft state. An annotated video only when video writing is on.

## Known issues and limits

- It counts people anywhere in the image, frame by frame: any three visible people count, not the same crew present for ten minutes (architecture review).
- "No person detected at all" is checked first, so such a video returns Fail even when the arrival was not seen, the view was blocked over 70% of the time or the stop came within 4 minutes.
- The branch meant to count over the whole pre-arrival stage of short videos is dead code (its flag is always reset); only the windowed count is used.
- The window edges snap to the nearest frame with a person detection; when the window has none, frames just outside it can be counted.
- It still uses the older arrival logic (camera-shake filter, 60 s rule), not the shared arrival detector used by M06, M11 and M18.
- A General Model class id missing from `str2id` stops the module with an error (reverse lookup on every detection).
- The verdict is fixed at the stop, but the loop runs 60 s longer for drawing only.

## For developers

- **Repository:** `dxgat/detectors/crew-present-10-minutes-prior-to-aircraft-arrival`; production line `main` @ `5cfd25c`; default branch `main` @ `5cfd25c` (the same).
- **Entry point:** `main.py` → `detect(source, output_path, device, weights_dir, video_worker, write_video, cone_camera, json_fn, json_logger)`; `get_max_value()` builds the report number. All logic is inside `detect()`.
- **Dependencies:** `git ls-tree HEAD`: cv_common `dd5b554`, db_worker `6efc0b0`; the local `cv_common` folder holds `ac5098d` content (the pin is not in the local archive). opencv-python, torch 1.10. No weights; CPU base image.
- **Run locally:** `python main.py --source <video>.mp4 [--write-video] [--json-fn <name>]`; the video worker reads `general_model<video>.ndjson` and `trackers<video>.ndjson` from `../inferences_dir` (this `main.py` does not pass `--inferences-dir`); `local_config.yaml` overrides `cv_common/global_config.yaml`. In production `db_worker/model_starter.py` calls `detect()`.
- **Logic diagram:** `.doc/Crew present.svg`; Confluence modules database, [sheet of 2023-07-10](https://docs.google.com/spreadsheets/d/1nKaKB04x9nVaTH3_Ql0Qnz9bv5xOecaIaXRpTmESdy0/edit?gid=0#gid=0).
- **Code references:** step 1 `main.py:60-98`; step 2 `:100-110`; step 3 `:137-143`; step 4 `:147-202`; step 5 `:211-247, 259-260`; step 6 `:248-257, 280-289`; step 7 `:290-306`; step 8 `:123-133, 310-311`.
