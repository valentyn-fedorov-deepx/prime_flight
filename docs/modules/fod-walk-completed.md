# M11 · FOD walk completed

> Checks that a worker walked the lead-in line to look for FOD (foreign object debris) before the aircraft arrived. It follows tracked people until the aircraft appears and, at the stop, tests their paths against a corridor along the aircraft's approach.

## At a glance

| | |
|---|---|
| Checks | M11 · FOD walk completed |
| Stage | Pre-arrival |
| Looks at | From the start of the video until the aircraft stops; people's paths only until the aircraft first appears on camera |
| Cameras | Cone camera, for aircraft and jets (the code does not read the camera flag) |
| Uses | General Model: `front_wheel`, `airplane_nose`, `airplane_tail` (corridor); GSE (ground support equipment), BL (belt loader) and pushback boxes (blocked view, drivers). Tracks: aircraft, person. Video frames: yes (person crops for the pose model; the stop frame for drawing) |
| Own models | MoveNet SinglePose Thunder v4 (stock pose model, ONNX, not trained by us) — tells from the shoulder order whether a person faces away from the camera |
| Runs on | CPU (ONNX Runtime 1.14.1, CPU build) |
| Real time | Ready, needs video frames — pose model on person crops; verdict at the stop |
| Production version | `dev` @ a30826f (2026-04-14) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | The diamond area is visible and a person walked from the beginning to the end of the area horizontally (from the safety clearance zone start line to the end of the lead-in line). |
| Fail | The diamond area is visible, no one walked from the beginning to the end, and the plane arrived. |
| Not observed | The diamond area is not visible, or the plane did not arrive. |
| Not observed — view blocked | Blocked frames are more than 80% of the pre-arrival stage. |

## How it decides

1. Reads detections, person tracks and the aircraft track frame by frame from the start of the video; follows the widest aircraft track.
2. Counts a frame as blocked when a GSE, BL or pushback box is wider than **30%** of the frame (576 px) with its centre in the right **70%** of the image.
3. Until the first aircraft track appears, records each person's path (bottom-centre of the box per frame). It skips boxes under **20 px** and people sitting in a vehicle (box more than **50%** inside a GSE, BL or pushback box). On each person crop it runs MoveNet and notes whether the person faces away from the camera (left shoulder left of the right shoulder).
4. While the aircraft approaches, records the front wheel nearest the aircraft centre (inside the aircraft box) and a rough distance from the box height (assumed **0.5 m** wheel, **7 m** aircraft).
5. At the tracker's stop it asks the shared arrival detector: arrival not seen (aircraft box grew by **18%** or less) → **Not observed**; pre-arrival not seen (aircraft first appeared before frame **90**, 11.25 s) → **Not observed**; blocked frames above **80%** of the frames before the stop → **Not observed**.
6. Builds the corridor: from the front wheel at the stop back along its path to where it was about **30 m** (estimated) further away, **±373 px** wide (4 m at 30 m). If the wheel path is shorter than about 15 m or missing, the corridor comes from the aircraft box: tail to nose, or a fixed **200 px** offset from its centre.
7. A person has done the walk when they are inside the corridor on at least **40 frames** (5 s), their path's near and far ends lie within **20%** of the corridor's height from its two ends, and the direction from start to end lies within the angle of the corridor sides. People facing away must walk away from the camera, the others towards it.
8. **Pass** if at least one walk is found; otherwise **Fail** ("not performed properly" if someone spent 5 s in the corridor, "not performed at all" otherwise). If the aircraft never stops: **Not observed**.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `obstacle.width` | 0.3 | A GSE / BL / pushback box wider than 30% of the frame blocks the view… |
| `obstacle.center` | 0.3–1 | …when its centre is in this horizontal band (share of the width) |
| Blocked share (code) | 0.8 | Not observed when blocked frames exceed 80% of the frames before the stop |
| `distance` (code) | 30 (estimated metres) | Corridor length along the approach; its half-width is 4 m at 30 m (373 px) |
| `stay_duration` (code) | 5 s (40 frames) | Minimum time inside the corridor |
| End tolerance (code) | 20% | How close the path must come to each corridor end |
| Sizes (`airplane_height`, wheel, `focal_length`, `pixel_size`) | 7 m, 0.5 m, 35 mm, 0.0125 mm | Rough distance from box height |
| Arrival detector (`area_change_thr`, `prearrival_min_frames`) | 0.18, 90 frames | Arrival and pre-arrival checks |

Only the two `obstacle` values are in the YAML.

## What it reports

- The verdict and one report line: Pass lists each walk (worker id and times); Fail says "not performed properly" or "not performed at all"; Not observed gives "No arrival stage", "No pre-arrival stage", "There were obstacles" or "Plane arrival was not captured".
- Smart timeline: one Pass block per walk; one Fail block from frame 1 to the stop; empty for Not observed.
- Overlay log (`JsonLogger` ndjson): person tracks, front wheels, "Camera is blocked!", walk progress for Pass. An annotated video only when video writing is on.

## Known issues and limits

- People are followed only until the first aircraft track appears: a later walk, or a false early aircraft detection, hides the walk (a case in `scripts/specialized_issues.txt`).
- Only the path ends and the time in the corridor are checked, so a zig-zag walk can pass (same file).
- The facing direction comes from the shoulder order without a confidence check.
- Distances come from box heights with assumed sizes, not a calibrated camera; the walk is along the approach line, not the horizontal crossing of the basic description (architecture review).
- No "diamond area visible" check (without a front wheel the corridor comes from the aircraft box); blocked frames are judged by box size, not by whether the corridor is hidden.
- Arrival detector: its comment says 90 s, the code uses 90 frames (11.25 s); an aircraft track that starts just before the stop gives "No arrival stage"; with no detector answer on the stop frame both checks are skipped.
- The stop frame is read and drawn on in place even without video writing; MoveNet runs once per crop, not batched.

## For developers

- **Repository:** `dxgat/detectors/fod-walk-completed`; production line `dev` @ `a30826f`; default branch `master` @ `b923b5c` (2026-01-27) — one commit behind: the old arrival block (camera-shake filter, 60 s pre-arrival rule) instead of the shared arrival detector.
- **Entry point:** `main.py` → `detect(source, output_path, device, write_video, weights_dir, video_worker, ...)`; `find_fod_walks()` builds the corridor and tests the paths; `get_desicion()` writes the verdict; `onnx_thunder_inference.py` → `PoseEstimation.is_backside()`.
- **Dependencies:** branch pins cv_common `ac5098d`, db_worker `5a4aa83`; the exported copy adds `cv_common/modules` from `2759daf`, which the module imports. onnxruntime 1.14.1, norfair, dvc 3.4.0. Weights: `weights/movenet_singlepose_thunder_4.onnx` (25 MB) through DVC (`gs://cv_weights/DVC`).
- **Run locally:** `python main.py --source <video>.mp4 --weights-dir weights [--write-video] [--json-fn <name>]`; reads `general_model<video>.ndjson` and `trackers<video>.ndjson` from `../inferences_dir`. In production `db_worker/model_starter.py` calls `detect()`.
- **Logic diagram:** `assets/block_diagram.svg`; Confluence modules database, [sheet of 2023-07-10](https://docs.google.com/spreadsheets/d/1LSbJWo2vbK48O_0sVbjOG2vvvijSSnWc0extFPr0qyk/edit?gid=0#gid=0).
- **Code references:** step 1 `main.py:318-354, 371-387`; step 2 `:356-367`; step 3 `:434-466`, `onnx_thunder_inference.py:111-121`; step 4 `main.py:469-491`; step 5 `:422-430, 500-517`; step 6 `:113-158`; step 7 `:180-236`; step 8 `:45-64, 544-548, 577-580`.
