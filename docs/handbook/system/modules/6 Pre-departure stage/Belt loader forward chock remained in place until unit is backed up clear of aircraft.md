# Belt loader forward chock remained in place until unit is backed up clear of aircraft

*In plain words: belt loader forward chock stays in place until the belt loader backs away.*

> When a belt loader (the conveyor vehicle that carries bags up to a cargo door) parks at the aircraft, a chock goes at
> its front wheel and must stay there until the belt loader backs away. Today the software checks that every belt
> loader parked at the camera's cargo door was chocked: while it stands still, the module watches a small zone at its
> wheels, and a chock found by the General Model that stays in that zone long enough marks the belt loader as chocked.

## Status

| | |
|---|---|
| How accurate it is | 60 of 68 turnarounds correct (88 %) on the monthly test |
| Fail turnarounds it caught | 10 of 11 |
| In production | the version of November 2025 |
| Who looks after it | to assign |
| Biggest open problem | It does not check that the chock stays until the belt loader backs away: one confirmed chock is enough. |

## What the client wants

*Belt loader forward chock remained in place until unit is backed up clear of aircraft*

| Verdict | When |
|---|---|
| Pass | Every belt loader seen in the video parked and was chocked, and the chocks stayed in place while it was parked. |
| Fail | At least one belt loader stopped but was not chocked. |
| Not observed | No belt loader stop is seen, or there is an obstacle. |
| Not observed, view blocked | The camera's view is blocked. |

A verdict is the answer of a check: Pass, Fail or Not observed. With both cameras, Fail on either gives Fail.

## When and where it looks

Unloading, loading and before departure (a stage is a part of the turnaround): from the moment the tracker reports the
aircraft as arrived (standing still for more than 4 seconds) until its departure (moving for 10 seconds), while the
belt loader at this camera's door is stopping or stopped. For aircraft, the cone camera (looks towards the aircraft
nose) watches the front belt loader and the wing camera (looks along the wing) the back one. For jets, only the wing
camera.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object): chocks, as the
  evidence; the aircraft's rear wheels, back cargo doors, engines and wings, to choose the belt loader and tell the
  aircraft type; large vehicles, belt loaders, ladders, cones and people only for an on-screen "Camera is blocked!"
  note.
- **From the tracker** (a track is the same object followed from frame to frame; a frame is one picture of the video,
  8 per second): the aircraft (arrived, departed) and the belt loaders, with the tracker's label of the door each serves
  (front or back) and whether it is moving, stopping or stopped.
- **From the video itself:** nothing; it works only from boxes and tracks.
- **Its own models:** none. It runs on an ordinary processor.

## How it decides, step by step

1. **Window.** Processing starts when the tracker marks the aircraft as arrived and stops when it marks it departed.
   It follows the first aircraft track of each frame.
2. **Aircraft type (wing camera only).** After the arrival, each frame in which a wing is seen votes: no engine, or the
   engine below the wing, means aircraft; the engine above the wing means jet. After more than 40 voting frames the
   majority is fixed; a tie means jet. The cone camera needs no type.
3. **Which belt loader.** The belt loaders the tracker labelled for this door: front on the cone camera, back on the wing
   camera. On the cone camera one that overlaps a rear wheel and stands behind it is dropped. On the wing camera, if
   none is labelled, a belt loader under the engine or one face-on below the back door is accepted. The biggest wins.
4. **Track changes.** A new belt loader track within 80 frames (10 seconds) of the last one takes over its record.
   Records seen in fewer than 80 frames are dropped after 16 frames (2 seconds) gone. The box is smoothed as the middle
   value of the last 16 boxes (2 seconds); its height when that window first fills is kept as the reference height.
5. **Stopped frames only.** Frames in which the belt loader is moving are skipped.
6. **Chock zone.** Cone camera: the lowest 20 % of the reference height, between 50 % and 20 % of the box width from its
   right edge (the belt loader's front wheel). Wing camera: the lower half of the reference height across the box for
   an aircraft; for a jet the same, widened by 10 % of the height on each side and below.
7. **Chock counter.** Each frame with a General Model chock overlapping the zone adds 1; each frame without one takes 1
   away (never below 0). When the counter passes 80 (at least 10 seconds more with a chock than without), the belt
   loader is marked chocked for good.
8. **Belt loader counted.** Only belt loaders whose first and last frames are more than 480 frames (60 seconds) apart
   are judged.
9. **Verdict:** none judged → Not observed; all judged belt loaders chocked → Pass; otherwise Fail.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Chock counter | above 80 (10 seconds net) | Marks the belt loader chocked |
| Shortest stay judged | 480 frames (60 seconds) between first and last frame | Shorter visits are not judged |
| New track, same belt loader | within 80 frames (10 seconds) | The record carries over |
| Short-lived record | seen fewer than 80 frames, gone 16 frames (2 seconds) | The record is dropped |
| Box smoothing | 16 frames (2 seconds) | Sets the reference height |
| Aircraft type votes | more than 40 frames with a wing | Wing camera: when chocks start to count |
| Obstacle width and position | 60 % of the picture width; centre at 30–100 % | Only the "Camera is blocked!" note |
| Stay-in-place overlap | 0.8 | Not used: the part that reads it is switched off |

## What it reports

- **Sentence:** "All of the beltloaders were confirmed chocked." or "Not all of the beltloaders were confirmed
  chocked.", then for each judged belt loader "Beltloader N was chocked (start - end)" or "Beltloader N was NOT chocked
  (start - end)".
  The time span runs from 10 seconds before to 10 seconds after the chock was confirmed, or covers the whole stay if
  it was not. Not observed: "No beltloaders were detected in use."
- **Timeline entry:** one Pass or Fail block per judged belt loader, from its first to its last frame.
- **Files:** a large drawing file (every box of six object types and every aircraft and belt loader track); an
  annotated video on request.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this check. The
module matched the client on 60 (88 %). Of the 11 labelled Fail it caught 10, so 1 of its 8 errors is a missed
violation; the other 7 are turnarounds labelled Pass or Not observed. An earlier measurement on 29 videos holding all
12 known violations found 83 % of the violations, and 91 % of its Fail verdicts were right. A review of 14 problem
videos in November 2025, before the latest change of the chock zone, traced the errors mostly to the tracker's belt
loader approach (6), the wing-camera chock zone (4), chock boxes (4: a chock on the opposite side, wet ground, random
objects taken for chocks) and missed doors (3).

## Known problems

- **"Remained in place" is not checked.** The chocked mark is set once and kept; the module does not check that the
  chock stays until the belt loader backs away, as the check's name and the client's rule say. A chock removed while
  the belt loader is still at the aircraft gives Pass.
- **Obstacles do not change the verdict.** The client's rule and the module's description give Not observed for an
  obstacle; the code only prints "Camera is blocked!". A blocked view gives Pass or Fail.
- **Wing camera without an aircraft type.** Chocks are not counted until the type is fixed (more than 40 frames with a
  wing). If that never happens, a judged belt loader fails.
- **The 60-second minimum** is measured between first and last appearance, moving frames included, not as parked time.
- **Outdated description.** The module's description says a lost belt loader is dropped after 5 seconds; the code uses
  2 seconds.
- **Wing-camera door label (to confirm):** production may not tell the tracker the camera (no back-door label in 7
  sample videos); the wing camera would then rely on step 3's fallbacks. The tracker's owner can confirm.

## In real time

It can run as it is: one pass over the boxes and tracks, no pictures; checked live, it gave the same verdict and
sentence as post-processing, at the departure. Each belt loader's result is final when it leaves, so a missing chock
could be reported then. It works out the aircraft type itself, although the real-time worker needs the type anyway to
choose the checks of each camera. It logs every detection from the first frame (7.6 megabytes per run).

Own work: about 0.3 milliseconds per frame (1.4 with all checks together); with the shared General Model and tracker
parts, 39.9 of the 125 milliseconds each frame may take (32 %), on a faster graphics card than production's. As a
post-processing job: about 12 seconds. From the stage detector (the part that knows where in the turnaround we are) it
needs the moments a belt loader reaches and leaves the door.

In live runs where another aircraft in view was taken for the arriving one, its verdict changed on 4 turnarounds, mostly
to Not observed: a problem of the shared live feed, for the stage detector to solve. The client puts this check in the
real-time group.

## For developers

- **Repository:** `dxgat/detectors/beltloader-chocks`; production and default branch `master` @ `7056099`
  (2025-11-17). Workspace module code: M04.
- **Entry point:** `main.py` → `detect(...)`; all logic in `main.py`: `Beltloader` (box smoothing, chock zone,
  counter), `find_beltloader`, `manage_beltloader`, `manage_old_beltloaders`, `save_plane_type_frame_data` /
  `evaluate_plane_type`, `make_inference`. Diagram `.doc/beltloader_chock_new.svg`; problem-video review
  `scripts/specialized_issues.txt`.
- **Dependencies:** `cv_common` @ `ac5098d`, `db_worker` @ `5a4aa83`; numpy, opencv-python, torch (only `no_grad`). No
  weights; `download_weights.sh` fetches an old General Model file that `main.py` does not use. CPU.
- **Run on one turnaround:** `python main.py --source <video.mp4> --inferences-dir <dir> [--cone-camera]
  [--local-inferences] [--write-video] [--save-csv]`; settings `local_config.yaml` over `cv_common/global_config.yaml`;
  `run_module.py` / `run_module_spec.py` run test lists.
- **Settings keys** (table order): `min_chock_threshold`, `min_bl_stay_time_thresh`, `min_bl_swap_time_thresh`,
  `min_bl_init_frames_thresh` + `bl_init_check_delay`, `bl_bbox_window_length`, `min_plane_type_frames_eval`,
  `cone.*` / `wing.*` obstacle keys, `min_bl_stay_iou_thresh` (read only by the commented-out `find_old_beltloader`).
- **Code places:** step 1 `main.py:221-230, 446-459`; 2 `main.py:326-368, 461-462, 497-498`; 3 `main.py:232-265`; 4
  `main.py:69-95, 293-316`; 5 `main.py:489-495`; 6 `main.py:98-132`; 7 `main.py:134-151`; 8 `main.py:164-166`; 9
  `main.py:23-50`; obstacle note `main.py:169-203, 441-444`.
