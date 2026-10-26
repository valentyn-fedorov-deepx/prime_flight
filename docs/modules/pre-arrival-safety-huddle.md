# M18 · Safety huddle conducted at huddle cone

> Checks that the crew held a safety huddle at the green huddle cone before the aircraft arrived. It finds green cones by their colour in the cone-camera image and counts tracked people standing next to each one until the aircraft stops.

## At a glance

| | |
|---|---|
| Checks | M18 · Safety huddle conducted at huddle cone |
| Stage | Pre-arrival |
| Looks at | From the start of the video until the aircraft stops (huddle), plus 60 s after the stop for the blocked-view count |
| Cameras | Cone camera, for aircraft and jets (the code does not read the camera flag) |
| Uses | General Model: `cone` (huddle cone); BL (belt loader), GSE (ground support equipment), pushback, trailer and fuel truck boxes (blocked view). Tracks: aircraft, person. Video frames: yes (colour inside every cone box) |
| Own models | None (a colour rule; cones are followed with the norfair tracker) |
| Runs on | CPU |
| Real time | Ready, needs video frames — reads cone pixels for the colour test; verdict 60 s after the stop |
| Production version | `green_cone_median` @ a1210c5 (2026-08-04) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | No plane is detected and at least 3 persons are detected near one green cone for 15 s. |
| Fail | No huddle is detected. |
| Not observed | There is no pre-arrival stage on the video, or the airplane has not arrived. |
| Not observed — view blocked | Obstacles during more than 50% of the pre-arrival stage. |

Client note: the cone is validated by colour (LAB colour space) and size.

## How it decides

1. Reads detections, person tracks and the aircraft track frame by frame; follows the largest aircraft track (by box area).
2. Counts a frame as blocked when a BL, GSE, pushback, trailer or fuel-truck box is larger than **600 × 400 px** with its centre in the left **75%** of the image. The frame is still used.
3. For every `cone` detection it reads the frame and keeps the cone only if the box is more than **1.2×** taller than wide and its lower middle part is greenish: the median of (G − R) / (R + G + B) there is above **0**.
4. Tracks the green cones. A cone becomes a candidate after more than **20** matched detections and is dropped when unseen for **15 s** (120 frames) while not hidden by a person.
5. Around each cone builds a huddle area: **±3 cone heights** sideways and about **5 m** in front of and behind the cone, estimated from the cone's pixel height (assuming a 1 m cone and a camera 1.5 m high). A person is in the area when the bottom edge of their box touches it.
6. A frame with at least **3** people in the area (or 2, when a third has just disappeared behind another) adds to the cone's huddle counter; **10 s** (80 frames) without that resets it. More than **120 frames** (15 s) → huddle detected at that cone.
7. Huddle counting stops when the tracker reports the stop; the module runs **60 s** (480 frames) more for the blocked-view count, then ends.
8. Verdict: **Pass** if a huddle was detected and the stop came later than **60 s** into the video. Otherwise **Not observed** if blocked frames are more than **50%** of all processed frames, if the shared arrival detector saw no pre-arrival stage (aircraft box growth of **18%** or less, or first appearance before frame **90**, 11.25 s), or if the aircraft did not stop; else **Fail**.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `Cone.huddle_threshold` | 15 s (120 frames) | Huddle length needed (3 people, or 2 + 1 hidden) |
| Gap reset (code) | 10 s (80 frames) | A longer gap restarts the huddle count |
| `Cone.missing_threshold` | 15 s | A cone unseen this long is dropped |
| Cone shape (code) | height / width > 1.2 | Square or lying boxes are not huddle cones |
| Green test (code) | median (G − R)/(R + G + B) > 0 | Measured on the box without its top 50%, bottom 5% and 30% on each side |
| Huddle area (code) | ±3 cone heights; 5 m; camera 1.5 m; cone 1 m | Size of the area around the cone |
| Blocker box (code) | 600 × 400 px, centre in the left 75% | What blocks the view |
| Blocked share (code) | 0.5 | Not observed above it |
| Pre-arrival for Pass (code) | 60 s | The stop must come later |
| Arrival detector (`area_change_thr`, `prearrival_min_frames`) | 0.18, 90 frames | Pre-arrival check for Not observed |

`local_config.yaml` holds only `task: huddle`; every value above is in the code.

## What it reports

- The verdict and one report line: Pass "Huddle detected at cone <id> by workers [<ids>]" with the time span; Fail names cones where workers left too early, or "Safety huddle is not detected near any cones during pre-arrival!"; Not observed gives "There is an obstacle!", "No pre-arrival stage is detected on video!" or "Airplane has not arrived on video!".
- Smart timeline: one Pass or Fail block from frame 1 to the stop; empty for Not observed.
- Overlay log (`JsonLogger` ndjson): person tracks, green cones, huddle areas, obstacles, status texts. An annotated video only when video writing is on.

## Known issues and limits

- The client note asks for a LAB colour check and size requirements; since 2026-08-04 the code uses the red-green median and a shape gate, with no minimum size.
- Pass uses the old pre-arrival rule (stop later than 60 s), Not observed uses the shared arrival detector; they can disagree, so a huddle with a stop in the first 60 s can end as Fail.
- The 60 s flag is set only on the exact stop frame (`frame_number == arrival_frame`), which breaks if frame numbers and stream positions differ.
- The rule says "no plane is detected"; the code counts huddles while the aircraft approaches, until the tracker reports the stop.
- The blocked share includes the 60 s after the stop, and blocked frames still count for the huddle.
- The huddle area relies on assumed sizes, not camera calibration. Arrival detector: its comment says 90 s, the code uses 90 frames (11.25 s).
- Branch housekeeping: old `python:3.7` Dockerfile with entrypoint `huddle_deepsort.py` (not in the repo), no `requirements_docker_developpment.txt`, unused `deep_sort_pytorch/`, outdated `README.md`; how production builds this branch is to confirm.
- It imports `cv_common.modules`, which the pinned cv_common lacks (architecture review).

## For developers

- **Repository:** `dxgat/detectors/pre-arrival-safety-huddle`; production line `green_cone_median` @ `a1210c5`; default branch `master` @ `9b61d2e` (2025-06-19) — split from the production line in 2023: older logic (HSV hue test for green, own arrival block, no arrival detector).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, weights_dir, cone_camera, json_logger)`; class `Cone` holds the per-cone huddle state; `is_valid()` / `rg_chromaticity_median()` — green test; `calculate_vertical_roi_size()` — depth of the huddle area.
- **Dependencies:** branch pins cv_common `ac5098d`, db_worker `5a4aa83` (default branch: `acfc080`, `6efc0b0`); the exported copy adds `cv_common/modules` from `2759daf`. norfair, OpenCV, NumPy. No weights.
- **Run locally:** `python main.py --source <video>.mp4 --inferences-dir <dir> [--write-video] [--json-fn <name>]`; reads `general_model<video>.ndjson` and `trackers<video>.ndjson` from the inferences folder. In production `db_worker/model_starter.py` calls `detect()`.
- **Logic diagram:** `.doc/Safety Huddle.svg`; Confluence modules database, [sheet of 2023-07-10](https://docs.google.com/spreadsheets/d/17NgkNWKQPCuxXBV7ZP7scqO6nOEN1akbPLZsH9g5fcY/edit?gid=0#gid=0).
- **Code references:** step 1 `main.py:345-355, 393-406`; step 2 `:365-382`; step 3 `:202-241, 384-390`; step 4 `:450-474, 77-91, 506`; step 5 `:251-272, 476-500`; step 6 `:93-140, 509-514`; step 7 `:436-448`; step 8 `:408-412, 545-585`.
