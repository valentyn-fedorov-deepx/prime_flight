# M20 · Pushback does not start until wing walkers are in place and ready

> Checks that a wing walker walks along each side of the aircraft when the pushback starts. It compares the paths of the people and of the aircraft in the cone camera view during the first 30 seconds of the pushback.

## At a glance

| | |
|---|---|
| Checks | M20 · Pushback does not start until wing walkers are in place and ready |
| Stage | Pre-departure, Departure |
| Looks at | the first 30 s after the aircraft starts moving back, once it has stood still for 60 s (at the end of the video, 20 s are enough) |
| Cameras | cone camera, for aircraft and jets (the code does not check the camera type) |
| Uses | General Model (GM) classes: pushback, airplane_wing; belt loader, GSE (ground support equipment), trailer, fuel truck, air conditioning, vehicle, obstacle, side_obstacle as view blockers. Tracks: aircraft, persons. Video frames: no |
| Own models | none |
| Runs on | CPU |
| Real time | ready as is — one pass, no video frames, decides about 30 s after the movement starts |
| Production version | obstruction_plane_track @ 6979d19 (2026-04-10) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | Two wing walkers, one on each side of the aircraft, during [departure frame, departure frame + 30 s]: their paths are within 50° of the aircraft's path, they move in the same direction, and their sides are confirmed by position. |
| Fail | 0 or 1 wing walker in total, with no obstacles on the side where a wing walker was not seen. |
| Not observed | There was no departure. |
| Not observed — view blocked | Fail is not triggered and a side was blocked by obstacles in more than 60 % of the frames of [departure frame, departure frame + 30 s]. |

## How it decides

1. Every frame it takes the widest aircraft track and the person tracks, without pushback drivers (more than 35 % of the person box inside a pushback box) and people standing between the left wing and the pushback.
2. **Parked:** the tracker reports the aircraft as stopped on **480 frames** (60 s) in a row. Another status, or an absence longer than **10 frames** (1.25 s), restarts the count.
3. **Departure start:** the first "moving" frame after parking, confirmed after **64 moving frames** (8 s); a "stopped" frame before that discards it.
4. From the departure start it records a rough top-view position of each person and of the aircraft: an angle from the place in the image (60° field of view) and a distance from the box height (1.75 m person, 7 m aircraft).
5. **Blocked sides:** from the tracker's arrival, a frame is blocked on one or both sides when vehicle boxes cover fixed parts of the image: a big box in the middle (both sides), a box at the left edge, enough box area on one side, or a pushback on the right.
6. **Decision moment:** **240 frames** (30 s) after the departure start, once the aircraft's estimated distance is growing; at the end of the video **160 frames** (20 s) are enough. The aircraft box must have shrunk by at least **18 %** between the first and the last 3 s of movement; otherwise the departure is discarded and the module waits for the next one.
7. **Paths:** each path needs at least **13 points** (about 1.6 s) in the window; it is smoothed over 11 frames and fitted with a straight line. A person is a wing walker when his line is within **50°** of the aircraft's and both move the same way.
8. **Side:** a line parallel to the aircraft's path is drawn through the end of each path; beyond the aircraft's line means right, otherwise left. A side also needs a person seen on that side of the aircraft box during the movement (left: centred left of a line **175 px** inside the box's left edge).
9. **Per side:** a wing walker → present. None → Not observed if the side was blocked in at least **60 %** of the window, otherwise Fail.
10. **Verdict:** both sides present → Pass; a side failed → Fail; otherwise Not observed. No aircraft, parking or confirmed departure → Not observed.

## Settings

| Setting | Value | What it does |
|---|---|---|
| parking time (hard-coded) | 480 frames (60 s) | stopped time needed before a departure can start |
| `plane.depart_thd` | 8 s (64 frames) | moving time that confirms the departure start |
| `plane.max_absence_frames` | 10 frames (1.25 s) | a longer absence restarts the counts |
| `plane.target_mov_time` | 30 s (240 frames) | length of the checked window |
| `plane.min_departure_len` | 20 s (160 frames) | shortest window accepted at the end of the video |
| `plane.departure_bbox_change` | 0.18 | minimum shrink of the aircraft box; less → reset |
| `degree_thresh` | 50° | maximum angle between a person's path and the aircraft's |
| `obstacle.not_observed_thr_ratio` | 0.6 | blocked share that makes a side Not observed |
| `obstacle.*` regions | fractions of the image (e.g. central box: centre at 37–60 % of the width, area ≥ 14 %) | where and how big a box must be to block a side |
| minimum path (hard-coded) | 13 points (about 1.6 s) | shorter paths are ignored |
| `plane.mov_reset_thr`, `plane.min_path_duration`, `message_display_duration` | 7, 8, 10 | in the YAML, not read by the code |

## What it reports

- **Verdict:** Pass, Fail or Not observed.
- **Report:** one line, e.g. `Check result is "Fail": there was a wing-walker on the left side of the plane and there were no wing-walkers on the right side. Time : 00:46:24 -- 00:46:54`. Without a departure: "Not enough moving frames of airplane were detected" or "No airplane was detected or no departure observed".
- **Smart timeline:** one entry with the status, the departure start frame and the decision frame; empty without a departure.
- **Files:** a per-frame JSON log, a trajectory plot `trajectories/trajectory_<video>.png` on every run, an annotated video with `--write-video`.

## Known issues and limits

- The evidence is walking along during the first 30 s after the start, not readiness before the start (architecture review).
- Probable bug: the right-side presence check compares people's horizontal positions with the top edge (y1) of the aircraft box instead of its right edge (`main.py:179`), so it is almost always true. To confirm.
- Own timing (60 s parked, 8 s moving) instead of the tracker's arrival and departure moments; a clip without 60 s of the parked aircraft gives Not observed.
- Blocking regions are fixed fractions of the image tuned for the cone camera view; people never count as obstacles.
- The side test uses the end point of each path; the README says the start point.
- "Pushback attached" (front wheel within 315 px of the pushback) is only an on-screen note.
- The end-of-video fallback reads the total frame count; real time needs an end-of-session signal.
- Cost: an on-screen obstacle counter is recomputed over the whole history on every frame.

## For developers

- **Repository:** `dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready`; production line `obstruction_plane_track` @ `6979d19`; default branch `master` @ `f3b041c` (2025-06-19; older logic with one whole-frame obstacle rule, 9 commits behind).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera, json_logger)`; `obstacle_logic.py` — side blocking rules; `helpers.py` — angle, distance, plots, overlay text.
- **Dependencies:** `cv_common` dd5b554, `db_worker` 5a4aa83 (exported copy; dd5b554 is not in the local archive, the export carries ac5098d); scikit-learn 1.6.1, norfair, matplotlib, OpenCV. No weights (`download_weights.sh` fetches an unused old GM file).
- **Run locally:** `python main.py --source <video>.mp4 --inferences-dir <GM and tracker files> [--write-video] [--json-fn <name>]`; `local_config.yaml` overrides `cv_common/global_config.yaml`. `run_module.py` runs a test list.
- **Code references:** step 1 `main.py:436-487`, `:635`; 2 `:96-107`, `:148-151`; 3 `:109-131`; 4 `:133-147`, `:417-433`; 5 `:389-393`, `obstacle_logic.py:65-131`; 6 `:658-684`; 7 `:33-53`, `:185-258`; 8 `:176-182`, `:652-653`; 9–10 `:296-330`, `:726-734`.
