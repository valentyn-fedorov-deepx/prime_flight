# M04 · Belt loader forward chock remained in place until unit is backed up clear of aircraft

> The module checks that every belt loader (BL) parked at the camera's cargo door was chocked. While the belt loader stands still, it watches a small zone at its wheels; a General Model (GM) chock detection that stays in that zone long enough marks the belt loader as chocked.

## At a glance

| | |
|---|---|
| Checks | M04 · Belt loader forward chock remained in place until unit is backed up clear of aircraft |
| Stage | Download, Upload, Pre-departure |
| Looks at | from the moment the aircraft stops until it departs, while the belt loader at the camera's door is stopping or stopped |
| Cameras | cone camera (front belt loader) and wing camera (back belt loader) for aircraft; wing camera only for jets |
| Uses | GM classes `chock` (evidence), `back_wheel`, `back_door`, `airplane_engine`, `airplane_wing` (belt loader choice, aircraft type); large vehicles, cones and persons only for an on-screen "camera blocked" note; tracks of the aircraft and belt loaders (front / back label, stopped status); video frames: no |
| Own models | none |
| Runs on | CPU |
| Real time | ready as is — one pass over detections and tracks, no video frames; each belt loader's result is final when it leaves |
| Production version | master @ 7056099 (2025-11-17) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | All belt loaders detected in the video parked and were chocked. Chocks remain in place while the belt loader is parked. |
| Fail | At least one detected belt loader stopped but was not chocked. |
| Not observed | No belt loader stop is detected, or there is an obstacle. |
| Not observed — view blocked | The field of view is blocked. |

## How it decides

1. **Window.** Processing starts when the tracker marks the aircraft as arrived (stopped for more than 4 s) and stops when it marks it departed (moving for 10 s). The first aircraft track of each frame is used.
2. **Aircraft type (wing camera).** After arrival, each frame with a wing detection votes: no engine, or an engine below the wing → aircraft; engine above the wing → jet. After more than **40** voting frames the majority is fixed (a tie means jet). The cone camera needs no type.
3. **Which belt loader.** It keeps belt loader tracks the tracker labelled for this camera's door (front on cone, back on wing). On the cone camera, a belt loader that overlaps a rear wheel and stands behind it is dropped. On the wing camera, if none is labelled, a belt loader under the engine or face-on below the back door is accepted. The biggest wins.
4. **Track changes.** A new belt loader track that appears within **80 frames** (10 s) of the last one takes over its record. Records seen in fewer than **80 frames** are dropped once they have been gone for **16 frames** (2 s). The box is smoothed as the median of the last **16** boxes; its height when that window first fills is kept as the reference height.
5. **Stopped frames only.** Frames where the belt loader is moving are skipped.
6. **Chock zone.** Cone camera: the lowest **20 %** of the reference height, between 50 % and 20 % of the width from the right edge (the belt loader's front wheel). Wing camera: the lower half of the box for an aircraft; for a jet the same, widened by 10 % of the height on each side and below.
7. **Chock counter.** Each frame with a GM chock overlapping the zone adds 1; each frame without one takes 1 away (never below 0). When the counter passes **80** (at least 10 s of net presence), the belt loader is marked chocked for good.
8. **Belt loader counted.** Only belt loaders whose first and last frames are more than **480 frames** (60 s) apart are judged.
9. **Verdict:** none judged → Not observed; all judged belt loaders chocked → Pass; otherwise Fail.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `min_chock_threshold` | 80 (10 s) | Counter value a chock must exceed to mark the belt loader chocked. |
| `min_bl_stay_time_thresh` | 480 (60 s) | Minimum span between a belt loader's first and last frame to be judged. |
| `min_bl_swap_time_thresh` | 80 (10 s) | A new belt loader track within this time takes over the previous record. |
| `min_bl_init_frames_thresh`, `bl_init_check_delay` | 80 (10 s), 16 (2 s) | Short-lived records are dropped after this absence. |
| `bl_bbox_window_length` | 16 frames (2 s) | Box smoothing window; sets the reference height. |
| `min_plane_type_frames_eval` | 40 frames | Wing-camera frames needed to fix the aircraft type. |
| `cone.*`, `wing.*` obstacle | width 0.6, centre 0.3–1.0 | Only for the "Camera is blocked!" overlay text; no effect on the verdict. |
| `min_bl_stay_iou_thresh` | 0.8 | **Not used**: the function that reads it is commented out. |

## What it reports

- **Verdict:** Pass, Fail or Not observed.
- **Report:** "All / Not all of the beltloaders were confirmed chocked.", then per judged belt loader "Beltloader N was [NOT] chocked (start – end)". The time range is 10 s around the chock confirmation, or the whole stay if not chocked. Not observed: "No beltloaders were detected in use."
- **Smart timeline:** one Pass or Fail entry per judged belt loader, from its first to its last frame.
- **Overlay log** (ndjson, a large one: every detection of six classes and every aircraft and belt loader track is logged); an annotated video only with `--write-video`.

## Known issues and limits

- **"Remained in place" is not checked.** The chocked mark is set once and kept; the module does not check that the chock stays until the belt loader backs away, as the check name and the client rule say.
- **Obstacles do not change the verdict.** The client rule and the README give Not observed for an obstacle; the code only prints "Camera is blocked!".
- **Wing camera, no aircraft type:** chocks are not counted until the type is fixed (more than 40 frames with a wing detected). If that never happens, a judged belt loader fails.
- The 60 s minimum is measured between first and last appearance, moving frames included, not as parked time.
- A review of 14 problem videos (2025-11-13, before the latest zone change) traced errors mostly to the tracker's belt loader approach (6), the wing-camera chock zone (4), chock detections (4: chock on the opposite side, wet ground, random objects) and missed doors (3) (`scripts/specialized_issues.txt`).
- Measured on 29 videos containing all 12 known violations: recall 83 %, precision 91 % (streaming audit).
- The README is partly out of date (it says a disappeared belt loader is dropped after 5 s; the code uses 2 s).

## For developers

- **Repository:** `dxgat/detectors/beltloader-chocks`; production line `master` @ `7056099`; default branch `master` @ `7056099` (the same).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, cone_camera, weights_dir, json_logger)`. All logic is in `main.py`: `Beltloader` (box smoothing, chock zone, counter), `find_beltloader`, `manage_beltloader`, `manage_old_beltloaders`, `save_plane_type_frame_data` / `evaluate_plane_type`, `make_inference` (verdict). Diagram `.doc/beltloader_chock_new.svg`; logic diagram (Confluence, 2025-05-21): https://docs.google.com/spreadsheets/d/1uBrtuDuXdhiwJrJjIvn-VIqUIbojhyhe6NxK1SD31L0/edit?gid=680015627#gid=680015627
- **Dependencies:** `cv_common` @ `ac5098d`, `db_worker` @ `5a4aa83` (`git ls-tree HEAD`). Packages: numpy, opencv-python, torch (only `no_grad`). No model weights; `download_weights.sh` fetches an old General Model file that `main.py` does not use.
- **Run locally:** `python main.py --source <video.mp4> --inferences-dir <dir> [--cone-camera] [--local-inferences] [--write-video] [--save-csv]`; settings in `local_config.yaml` over `cv_common/global_config.yaml`. `run_module.py` / `run_module_spec.py` run test lists.
- **Code references:** step 1 `main.py:221-230, 446-459`; step 2 `main.py:326-368, 461-462, 497-498`; step 3 `main.py:232-265`; step 4 `main.py:69-95, 293-316`; step 5 `main.py:489-495`; step 6 `main.py:98-132`; step 7 `main.py:134-151`; step 8 `main.py:164-166`; step 9 `main.py:23-50`; obstacle note `main.py:169-203, 441-444`.
