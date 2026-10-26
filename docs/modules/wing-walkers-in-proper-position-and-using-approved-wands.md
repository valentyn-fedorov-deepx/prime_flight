# M27 · Wing walkers in proper position and using approved wands

> Checks that during the first 60 seconds of the pushback a wing walker walks along each side of the aircraft and signals with a raised arm. It compares the paths of people and aircraft in the cone camera view and reads arm positions with a pose model; wands are not detected.

## At a glance

| | |
|---|---|
| Checks | M27 · Wing walkers in proper position and using approved wands |
| Stage | Pre-departure, Departure |
| Looks at | the first 60 s after the aircraft starts moving back (at the end of the video, 20 s are enough) |
| Cameras | cone camera, for aircraft and jets (the camera type is not checked; aircraft or jet is detected by the module) |
| Uses | General Model (GM) classes: pushback, airplane_wing, airplane_engine; belt loader, GSE (ground support equipment), trailer, fuel truck, air conditioning, vehicle, obstacle, side_obstacle as view blockers. Tracks: aircraft, persons. Video frames: yes |
| Own models | none in use; runs the public HRNet-W48 COCO pose model (mmpose). The in-house wand detector `wand_detector.pt` is in the repository but not loaded |
| Runs on | GPU (CPU with `--device cpu`) |
| Real time | ready, needs video frames — one pass, decides 60 s after the movement starts (an earlier audit rated it "ready as is", but on the older default branch without pose) |
| Production version | obstruction_hand_signals @ 3460afc (2025-10-29) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | A wing walker with wands and hand signals is seen walking along the aircraft on both sides during [departure frame, departure frame + 60 s]. |
| Fail | At least one part of the check fails. |
| Not observed | There was no departure. |
| Not observed — view blocked | Fail is not triggered and a side was blocked by obstacles in more than 60 % of the frames of [departure frame, departure frame + 60 s]. |

## How it decides

1. Every frame it takes the widest aircraft track and the person tracks, without pushback drivers (more than **70 %** of the person box inside a pushback box, or crossing its top edge, and at least **13 %** as tall as it).
2. **Aircraft or jet:** until the tracker's departure, an engine above the wing votes jet, below it votes aircraft; the majority wins (default aircraft).
3. **Parked:** the tracker reports "stopped" on **40 frames** (5 s) in total. **Departure start:** the first "moving" frame after that, confirmed after **64 moving frames** (8 s); a "stopped" frame before that discards it.
4. From the departure start it records each person's rough top-view position (from the image position and the box height), runs the pose model on a contrast-enhanced (CLAHE) frame with the box enlarged by 10 %, and counts blocked sides as M20 does.
5. **Decision moment:** **480 frames** (60 s) after the departure start, or the video end if at least **160 frames** (20 s) were seen. The aircraft box must have shrunk by at least **17.5 %** between the first and the last 3 s; otherwise it was a false departure and the module waits for the next.
6. **Paths:** each path needs at least **13 points** in the window; it is smoothed over 11 frames and fitted with a straight line. For jets, paths of at least **270 points** (about 34 s) are cut at their first major turn.
7. **Wing walker:** the line is within **42°** of the aircraft's, the person does not move against the aircraft, and a path longer than **20 s** spans at least **12 m**. The side comes from lines parallel to the aircraft's path through the path starts; a left-side walker must also start above the aircraft's path on the top-view map (rejects people walking in the middle).
8. **Hand signals:** a frame counts when a wrist is above the elbow (tolerance: 8 % of the box height on the left; 4.8 % (aircraft) or 7 % (jet) on the right) and both points have confidence of at least **0.2**. A walker signals with **8** such frames (1 s), or 20 % of his frames if that is fewer.
9. **Per side:** no walker → Not observed if the side was blocked in at least **60 %** of the window, otherwise Fail.
10. **Verdict:** Pass only if both sides have a walker who signals. Fail if a side has no walker and is not blocked, or a walker does not signal. Otherwise Not observed; also without aircraft or departure.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `plane.stop_thd` | 5 s (40 frames) | stopped time that marks the aircraft as parked |
| `plane.depart_thd` | 8 s (64 frames) | moving time that confirms the departure start |
| `plane.departure_duration` | 60 s (480 frames) | length of the checked window |
| `plane.departure_bbox_change` | 0.175 | minimum shrink of the aircraft box; less → reset |
| `plane.degree_thresh` | 42° | maximum angle between a person's path and the aircraft's |
| `handsignals.<type>.<side>.margin_of_error_*` | left 0.08; right 0.048 (aircraft), 0.07 (jet) | allowed wrist drop below the elbow |
| `handsignals.min_frames`, `conf_thr` | 8 frames (1 s), 0.2 | signal frames needed; minimum keypoint confidence |
| `obstacle.not_observed_thr_ratio` | 0.6 | blocked share that makes a side Not observed |
| `obstacle.*` regions; `pushback.min_driver_intersect` | as in M20; 0.7 | where boxes block a side; driver detection |
| `turn_detection.*` | 270 points, 0.15, 0.02, 0.8 | jets only: cutting long paths at a turn |
| `task`, `weights`, `message_display_duration` | — | in the YAML, not read by the code |

## What it reports

- **Verdict:** Pass, Fail or Not observed.
- **Report:** one line, e.g. "Wing-walkers were present on both sides of the plane. Both wing-walkers were performing hand-signals with approved wands. Time : HH:MM:SS -- HH:MM:SS". Not observed: "Airplane was not detected.", "Departure wasn't observed." or "Airplane movement path was too short". The "approved wands" wording is fixed text.
- **Smart timeline:** one entry with the status, the departure start frame and the window end; empty without a departure.
- **Files:** a per-frame JSON log with pose keypoints, a trajectory plot, two pickle files; an annotated video with `--write-video`.

## Known issues and limits

- Wands are not checked: the wand detector line is commented out (`main.py:810`) and the report always says "approved wands". The architecture review calls this a critical gap against the client rule.
- "Hand signals" means a wrist at or above the elbow for about 1 s; any raised arm passes.
- Own timing (5 s stopped, 8 s moving), not the tracker's anchors; the stop count never resets, so earlier pauses may mark the aircraft parked too early. To confirm.
- The end-of-video fallback reads the total frame count; real time needs an end-of-session signal.
- Hand-signal and path data live in class-level dictionaries that are never cleared, so several videos in one process share them.
- `weights.dvc` lists the `weights` folder twice; the folder also holds an unused 255 MB HRNet copy.

## For developers

- **Repository:** `dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands`; production line `obstruction_hand_signals` @ `3460afc`; default branch `master` @ `5f7ca1a` (2025-06-19; older logic: walking along only, wand Pass hard-coded, no pose).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera, json_logger)`; classes `Plane` (timing, aircraft or jet) and `WingWalker` (paths, pose); `helpers.py` — geometry, turn detection, CLAHE; `obstacle_logic.py` — side blocking.
- **Dependencies:** `cv_common` dd5b554, `db_worker` 5a4aa83 (exported copy; dd5b554 is not in the local archive, the export carries ac5098d); mmpose 1.3.1, mmcv 2.1.0, torch 2.1.2, scikit-learn 1.6.1, scipy. Weights by DVC (`gs://cv_weights/DVC`): `weights/td-hm_hrnet-w48_8xb32-210e_coco-256x192-0e67c616_20220913.pth`.
- **Run locally:** `dvc pull`, then `python main.py --source <video>.mp4 --inferences-dir <GM and tracker files> --weights-dir weights [--device cpu] [--write-video]`; `run_module.py` runs a test list.
- **Code references:** step 1 `main.py:741-753`; 2 `:65-98`, `:161-189`; 3 `:129-157`; 4 `:219-291`, `:631-694`, `:949-952`; 5 `:981-1012`; 6 `:326-376`, `helpers.py:63-84`, `:132-187`; 7 `:397-453`; 8 `:314-323`, `:494-505`; 9–10 `:480-545`, `:1069-1076`.
