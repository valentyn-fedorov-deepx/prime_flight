# M05 · Beltloader rear cone positioned after BL is in place

> Checks that a cone is placed behind every belt loader (BL) once it stands at the aircraft's cargo door. While the tracker
> reports the loader stopped at the door, the module looks for a General Model cone at the loader's rear corner and needs
> to see it there for more than 10 s in a row.

## At a glance

| | |
|---|---|
| Checks | M05 · Beltloader rear cone positioned after BL is in place |
| Stage | Post-arrival, Download |
| Looks at | from the aircraft's arrival until its departure; cones are counted only while a loader stands (stopping or stopped) at the door |
| Cameras | aircraft: both cameras; jet: wing camera. The cone camera checks the front-door loader, the wing camera the rear-door loader |
| Uses | General Model (GM) classes `cone`, `beltloader_cone`, `engine_cone`, `wing_cone` (the cone), `back_door`, `back_wheel`, `airplane_engine` (choosing the loader); tracks of the aircraft and belt loaders (status, door label); video frames: no |
| Own models | none |
| Runs on | CPU |
| Real time | ready as is — works on frames already seen; a Pass is known once the cone has stood 10 s behind a loader that has been at the door for 60 s |
| Production version | main @ 12429f5 (2025-06-19; last logic change d75f1f8, 2025-05-14) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | The belt loader rear cone is seen for at least 100 frames. |
| Fail | The belt loader rear cone is detected fewer than 100 times. |
| Not observed | No stopped belt loader near the aircraft is detected. |
| Not observed — view blocked | There were obstacles for 1 minute in total. |

## How it decides

1. Waits for the tracker's arrival flag on the first aircraft track of the frame; stops at its departure flag.
2. Chooses the door: the cone camera looks only at loaders the tracker labels "front", the wing camera only at "back".
   The tracker gives the label once a loader has stood at that cargo door for **8 frames** (1 s) and removes it when the
   loader drives off. On the cone camera, loaders standing behind a rear wheel are dropped. On the wing camera, if no
   "back" loader is present, a loader hidden by the engine or face-on below the rear door is taken instead.
3. Takes the biggest of these loaders; one loader is checked per frame.
4. A new track id that appears within **80 frames** (10 s) of the last loader is treated as the same loader. Loaders seen
   for fewer than **80 frames** are forgotten once they have been gone for **16 frames** (2 s).
5. Smooths the loader box with the median of its last **16 boxes**; the height of the first full median box is the
   reference height H.
6. Skips frames in which the tracker reports the loader moving. Otherwise builds a search area at the loader's bottom-left
   corner: cone camera — from 1 H left to 1 H right of its left edge, from 0.1 H above to 0.2 H below its bottom edge;
   wing camera — a similar area up to 1.5 H wide, or at the bottom-right corner when the loader stands right of the door.
7. Counts frames in a row with any GM cone whose bottom centre lies in the area; a checked frame without one resets the
   count. More than **80 frames** (10 s) → the loader is "coned".
8. At the departure or the end of the video, only loaders followed for more than **480 frames** (60 s), first to last
   frame, are judged. None → Not observed; all coned → Pass; otherwise Fail.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `min_cone_threshold` | 80 frames (10 s) | frames in a row with a cone needed for "coned"; the client rule says 100 frames |
| `min_bl_stay_time_thresh` | 480 frames (60 s) | shorter loader visits are not judged |
| `min_bl_swap_time_thresh` | 80 frames (10 s) | a new track id within this time is merged into the last loader |
| `min_bl_init_frames_thresh`, `bl_init_check_delay` | 80 frames (10 s), 16 frames (2 s) | short-lived loaders are dropped |
| `bl_bbox_window_length` | 16 frames (2 s) | median window for the loader box; fixes the height H that sizes the area |
| `obstacle_width`, `obstacle_center_range` | 0.6 of the width; centre in 0.3–1.0 | only shows "Camera is blocked!" on screen; not used for the verdict |
| `min_bl_stay_iou_thresh` | 0.8 | not used by the code |
| search area (code) | cone camera: ±1 H around the left edge, 0.1 H above to 0.2 H below the bottom | where a cone counts; wing areas in `update_cone_roi` |
| tracker door label | 8 frames (1 s) at the door | which loaders count as "at the door" |

## What it reports

- The verdict for the task `beltloader_rear_cone`.
- Report text: "All of the beltloaders were confirmed coned." or "Not all of …", then "Beltloader <id> was [NOT ]coned
  (<start> - <end>)." per judged loader (±10 s around the cone registration, or first to last frame). Not observed: "No
  beltloaders were detected in use."
- Smart timeline: one entry per judged loader, `{Status: Pass/Fail, Start: first frame, End: last frame}`.
- A per-frame drawing log (boxes, texts); an annotated video only when video writing is on.

## Known issues and limits

- The code needs more than 80 frames in a row; the client rule says 100 frames. The architecture review: keep the code
  behaviour as the baseline and approve requirement changes separately.
- No "view blocked" verdict: obstacles are found but only shown on screen; "obstacles for 1 minute → Not observed" is not
  implemented.
- One checked frame without a detected cone resets the count, so detection flicker can turn a coned loader into a Fail.
- Any GM cone class counts, so an engine or wing cone standing in the area passes the check.
- Only the biggest qualifying loader per frame is checked; a loader that never gets the tracker's door label is never judged.
- "Near the aircraft" comes only from the door label; there is no size or aircraft-overlap test. The README still
  describes an older version (cone tracker, 100 frames, 5 s stop, obstacle skipping).
- Cameras: the worker settings file (`db_worker/ml_setting/ml_global_config.json`) lists the cone camera only; the client
  sheet says both — to confirm what runs in production.

## For developers

- **Repository:** `dxgat/detectors/bl_rear_cone`; production line `main` @ `12429f5`; default branch the same. The side
  branch `plane_type_cone_roi` (1ce83b5, 2025-06-12: jet/aircraft split on the wing camera, new cone area) is not in
  production.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, cone_camera, weights_dir,
  json_logger)`; all logic is in `main.py`: `find_beltloader`, `manage_beltloader` / `manage_old_beltloaders`, the
  `Beltloader` class (smoothing, view side, search area, cone count) and `make_inference`.
- **Dependencies:** `cv_common` 86731e4 (not in the local archive; the local copy is ac5098d), `db_worker` 5a4aa83.
  Packages: numpy, opencv-python, norfair (through `cv_common`), torch (only `no_grad`). No weights.
- **Run locally:** `python main.py --source <video>.mp4 --inferences-dir <folder with GM and tracker ndjson>
  --local-inferences [--cone-camera] [--write-video] [--save-csv]`. The local `__main__` names the worker
  `safety-handrails-fully-extended` (copied from another module).
- **Code references:** step 1 `main.py:251-260, 410-422`; step 2 `main.py:262-292, 345-347`; step 3 `main.py:295`;
  step 4 `main.py:297-320, 373`; step 5 `main.py:72-89`; step 6 `main.py:100-161, 446-455`; step 7 `main.py:163-181,
  397-402`; step 8 `main.py:23-50, 194-196, 468`; obstacle message `main.py:199-233, 405-407`; tracker door label
  `cv_trackers/local_utils/bl_utils.py:4-133`.
