# M06 · Chocks and cones available and staged for arrival

> Checks that enough cones (7) and chocks (6) are laid out at the stand before the aircraft arrives. It counts the cones and chocks that the General Model detects on each cone-camera frame until the aircraft stops.

## At a glance

| | |
|---|---|
| Checks | M06 · Chocks and cones available and staged for arrival |
| Stage | Pre-arrival |
| Looks at | From the start of the video until the tracker reports that the aircraft has stopped |
| Cameras | Cone camera, for aircraft and jets (the code does not read the camera flag) |
| Uses | General Model: `cone`, `chock`; GSE (ground support equipment), BL (belt loader) and pushback boxes (chocks on vehicles); other vehicle, person, ladder and obstacle boxes (blocked view). Tracks: aircraft. Video frames: no (annotated video only) |
| Own models | None |
| Runs on | CPU |
| Real time | Ready as is — one pass over detections and tracks, verdict at the aircraft stop |
| Production version | `not_observed_logic` @ 2b4fca9 (2026-04-29) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | There are 7 cones and 6 chocks in the pre-arrival stage. |
| Fail | There are not 7 cones and 6 chocks in the pre-arrival stage. |
| Not observed | An obstacle, or there is no pre-arrival stage. |
| Not observed — view blocked | Obstacles during more than 50% of the pre-arrival stage, or a side obstacle. |

## How it decides

1. Reads the detections and the aircraft track frame by frame from the start of the video and follows the widest aircraft track.
2. Stops at the frame where the tracker marks the aircraft as stopped (the tracker's arrival frame: stopped for more than **4 s**). Nothing after the stop is counted.
3. On each frame counts cones (class `cone`, box taller than **30 px**) and chocks. A chock that touches a GSE, BL or pushback box enlarged by **20%** on each side is treated as carried on a vehicle and is not counted.
4. A frame with at least **7 cones** adds one to the cone counter; a frame with at least **6 chocks** adds one to the chock counter. When a counter passes **24 frames** (3 s), that object type is passed for good. The frames do not have to be consecutive, and cones and chocks do not have to be on the same frames.
5. Marks a frame as blocked when a large box sits in the lower part of the image (bottom edge in the lower **47.5%** of the frame, area at least **1–2.7%** of the frame) or a group of touching boxes there covers at least **2.2%** of the frame. A frame that already shows enough cones and chocks is not counted as blocked.
6. At the stop it checks the arrival with the shared arrival detector: the aircraft box (median over the first **3 s** of its track against the last **8 s** before the stop) must grow by more than **18%**. The pre-arrival counts as seen when, in addition, the aircraft first appears at frame **90** (11.25 s) or later.
7. Verdict: **Pass** if both cones and chocks passed. Otherwise **Not observed** if no aircraft was seen, the arrival or pre-arrival was not seen, or blocked frames are at least **50%** of the frames before the stop; else **Fail**.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `quantity_thr.cone` | 7 | Minimum cones on one frame |
| `quantity_thr.chock` | 6 | Minimum chocks on one frame |
| `presence_thr` | 3 s | Each count must be met on more than 24 frames (not necessarily in a row) |
| `obstacle.position` (`max_x1`, `min_x2`, `min_weaker_x2`, `min_y2`) | 0.928, 0.072, 0.058, 0.525 | Where a box must lie (share of frame width / height) to block the view; the weaker 0.058 applies to GSE, fuel trucks and people |
| `obstacle.combined` (`min_area`, `min_comb_area`, `w_margin`) | 0.0004, 0.022, 0.01 | Smaller boxes that touch (within 1% of the width) are grouped; a group of at least 2.2% of the frame blocks the view |
| `obstacle.not_observed_thr_ratio` | 0.5 | Share of blocked frames that gives Not observed |
| Cone height (code) | 30 px | Smaller cones are ignored |
| Vehicle margin (code) | 20% | Chocks touching an enlarged GSE / BL / pushback box are not counted |
| `area_change_thr` (arrival detector) | 0.18 | Aircraft box growth needed to call the arrival seen |
| `prearrival_min_frames` (arrival detector) | 90 frames (11.25 s) | Earliest first appearance of the aircraft for a pre-arrival stage |
| Detector time-outs | 10 s, 300 s | Reset after 10 s without an aircraft; check forced after 5 min of tracking without a stop |

## What it reports

- The verdict and one report line: Pass and Fail give the counts and the time span (Fail: the maximum counts seen, or "present for less than 3 seconds"); Not observed gives "Airplane wasn't detected", "No arrival stage", "No pre-arrival stage" or "There were obstacles during prearrival stage".
- Smart timeline: one Pass or Fail block from frame 0 to the stop; empty for Not observed.
- Overlay log (`JsonLogger` ndjson): cone, chock and obstacle boxes, counts, obstacle events, aircraft state. An annotated video only when video writing is on.

## Known issues and limits

- The arrival detector's comment says the aircraft must first appear **90 s** into the video, but the code compares the frame number with 90, i.e. **11.25 s**. Checked on the cv_common copy (2759daf); the production cv_common is to confirm.
- The client's "side obstacle" clause has no rule of its own: side-obstacle boxes only add to the 50% count when they pass the size and position filter.
- Pass is checked first and needs neither an aircraft nor a seen pre-arrival stage.
- If the tracker never reports a stop, counting runs to the end of the video, so cones and chocks placed after the arrival still count.
- Chocks staged right next to a GSE, BL or pushback are dropped like carried ones.
- The arrival check needs at least **88 frames** (11 s) of aircraft track before the stop; a track that starts at the stop gives "No arrival stage" (unless Pass).
- `README.md` still describes the replaced logic (60 s pre-arrival rule, camera-shake filter).
- The module imports `cv_common.modules`, which the pinned cv_common lacks locally; the production build must provide it (to confirm).

## For developers

- **Repository:** `dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival`; production line `not_observed_logic` @ `2b4fca9`; default branch `master` @ `1413225` (2025-06-19) — older logic: counts hard-coded as 7/6 while its YAML says 6/4 (the architecture review note applies to `master` only), pre-arrival = stop later than 60 s, blocked view = any `obstacle` / `side_obstacle` box.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, ..., json_logger, new_design)`. `obstacle_logic.py` — blocked-view rules; `visualization_overlay.py` — drawing only; `cv_common/modules/plane_arrival_detector.py` — arrival and pre-arrival check.
- **Dependencies:** branch pins cv_common `dd5b554`, db_worker `5a4aa83`; the exported copy holds cv_common `ac5098d` plus `cv_common/modules` from `2759daf`. torch, OpenCV, NumPy. No weights; CPU base image.
- **Run locally:** `python main.py --source <video>.mp4 --inferences-dir <dir> [--write-video] [--new-design] [--json-fn <name>]`; reads `general_model<video>.ndjson` and `trackers<video>.ndjson` from the inferences folder; `local_config.yaml` overrides `cv_common/global_config.yaml`. In production `db_worker/model_starter.py` calls `detect()`.
- **Logic diagram:** Confluence modules database, [sheet of 2023-07-10](https://docs.google.com/spreadsheets/d/1OMlFKRlEK1MeNw5v01Q04NoqEKZfUeCmt_Zr3Hu0Te4/edit?gid=0#gid=0) (older than the current logic).
- **Code references:** step 1 `main.py:153-187, 321`, `:47-97`; step 2 `main.py:329-333`; step 3 `main.py:168, 190-197, 335-338`; step 4 `main.py:200-211, 339`; step 5 `main.py:360`, `obstacle_logic.py:92-183`; step 6 `main.py:323-327`, `cv_common/modules/plane_arrival_detector.py:77, 85-149, 196-229`; step 7 `main.py:104-131, 402`.
