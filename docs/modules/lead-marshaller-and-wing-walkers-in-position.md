# M15 · Lead marshaller and wing walkers in correct position

> Checks that wing walkers stand on both sides of the stand before the aircraft arrives, then walk along both sides of
> the aircraft giving hand signals while it rolls in. Small trained classifiers decide who is a wing walker and on which
> side; a pose model checks for raised hands.

## At a glance

| | |
|---|---|
| Checks | M15 · Lead marshaller and wing walkers in correct position |
| Stage | Pre-arrival, Arrival |
| Looks at | from the start of the video until the aircraft stops: pre-arrival, then the approach |
| Cameras | cone camera (aircraft and jet) |
| Uses | tracks of the aircraft and persons; General Model (GM) vehicle and equipment boxes and `obstacle` / `side_obstacle` rows (blocked sides only); video frames: yes |
| Own models | worker role classifier (SVC), walk-along classifier (RandomForest), two walking-start models (gradient boosting); plus the stock HRNet-W48 pose model (mmpose) |
| Runs on | GPU for the pose model (`cuda:0` unless the device is `cpu`); the worker settings file says CPU — to confirm |
| Real time | ready, needs video frames — decides at the aircraft's stop from past data (the real-time audit read the pose-free default branch) |
| Production version | pre_arrival_departure @ 9e1a9f0 (2026-05-29; last logic change 9746ddf, 2026-03-20) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | At least 2 wing walkers are on the stand (both sides) for at least 10 minutes during pre-arrival, and walk along both sides of the aircraft with wands and hand signals during arrival. |
| Fail | 0 or 1 wing walker, with no obstacles on the side where none was detected; or a wing walker made no hand signals with wands. |
| Not observed | No aircraft, pre-arrival shorter than 10 minutes (4800 frames), or no arrival. |
| Not observed — view blocked | Fail is not triggered and obstacles cover either side in more than 65 % of the pre-arrival or arrival frames. |

## How it decides

1. **Who stands where.** Every frame the role classifier labels each person left wing walker, right wing walker or
   neither, from his box and a rough angle and distance. He is "on position" after **40 frames** (5 s) with one side
   label; he leaves after **48 frames** (6 s) as "neither" or **96 frames** (12 s) unseen.
2. **Blocked sides.** A frame blocks a side if a large object stands in the centre (≥ **14 %** of the image; both
   sides), a non-person object at the left edge, or the boxes on one side add up to ≥ **2.2 %** of the image (people
   too). Frames are not charged to a side whose wing walker on position then is still there at the verdict.
3. **The aircraft.** Its first moving frame marks the arrival start. If it vanishes for **80 frames** (10 s) before
   stopping, it was a passing aircraft and the approach data is cleared.
4. **Approach.** Workers' and the aircraft's angles and distances are recorded every frame, and the pose model runs on
   all workers: a wrist above the elbow (confidence ≥ **0.2**) is a signal frame. Before the aircraft is seen, the last
   **33** positions per worker and **96 frames** (12 s) are buffered for a late detection.
5. **Pre-arrival check** at the tracker's arrival flag (aircraft still for about 4 s). Arrival start at or before **3600
   frames** (7.5 min) → Not observed. Otherwise, from the state when the aircraft first appeared, a side passes with a
   walker on position for **720 frames** (90 s); a side without one is Not observed if blocked in ≥ **65 %** of the
   pre-arrival frames, else Fail.
6. **Walk-along check.** Each worker's path from the arrival start to the stop is smoothed and fitted with a line (more
   than **32 points**, 4 s, needed). The walk-along classifier labels him left, right or neither from the angle and
   offset between his path and the aircraft's, his path length and his distance. Sides are scored as in step 5.
7. **Hand-signal check.** For walkers with at least **115** (left) / **120** (right) points, the walking-start model finds
   when they started walking and only later signal frames count. **8 frames** (1 s) → the side passes; walkers without
   signals → Fail; no walker → Not observed.
8. **Verdict.** Per check: both sides Pass → Pass, any Fail → Fail, else Not observed. Overall: any Fail → Fail; else any
   Not observed → Not observed; else Pass. No aircraft stop → Not observed.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `wing_walker.init_thr`, `removal_thr`, `not_visible_thr` | 5 s, 6 s, 12 s | time to take or lose a position |
| `wing_walker.prearrival_presence_thr` | 90 s (720 frames) | time on position for a side to pass; the rule says 10 minutes |
| `min_prearrival_duration` | 450 s (7.5 min) | shorter pre-arrival → Not observed; the rule says 10 minutes |
| `obstacle.not_observed_thr_ratio` | 0.65 | blocked share that turns a missing side into Not observed |
| `obstacle.*` | central area ≥ 0.14; side total ≥ 0.022 | when a side counts as blocked |
| `msg_display_thr` | 10 s (80 frames) | absence that marks a passing aircraft |
| `left_min_frames`, `right_min_frames` | 115, 120 frames | path length needed for the walking-start model |
| `hand_signals_thr` | 8 frames (1 s) | signal frames needed per walker |

Values in seconds are stored as seconds; the code multiplies them by 8.

## What it reports

- One verdict for the task `wingwalker`.
- Report text: "Prearrival check is <verdict> - <reason> (<times>). Arrival walk along check is … . Arrival hand signals
  check is … ." or "Plane full stop was not detected (…)".
- Smart timeline: three entries — pre-arrival (frame 0 to the arrival start), walk-along and hand signals (arrival start
  to the stop).
- A per-frame drawing log with keypoints, a trajectory plot (`trajectories/`) on every run and, when enabled, an
  annotated video.

## Known issues and limits

- The lead marshaller is not checked, and there is no wand check: a hand signal is a wrist above the elbow.
- Thresholds differ from the client rule: 90 s presence instead of 10 minutes, 7.5 minutes minimum pre-arrival instead of
  10 (the code comment says "in production 10 min. will be used").
- Presence is counted until the aircraft first appears, not until it stops.
- Signals found in buffered frames are stored under the decision frame number, so they always count as "after the walker
  started walking".
- People's own boxes add to a side's blocked area, so a crowd can turn a missing walker into Not observed.
- The branch keeps the default branch's CPU Dockerfile and Docker requirements (no mmpose, scikit-learn) — to confirm
  how the production image is built.
- Never loaded: `models/worker_type_classifier*.pkl`, the `hrnet_w48_coco_384x288_dark` weights copy.

## For developers

- **Repository:** `dxgat/detectors/lead-marshaller-and-wing-walkers-in-position`; production line
  `pre_arrival_departure` @ `9e1a9f0`; default branch `master` @ `9b37ccf` (2025-06-19), an older rule-based version
  (no pose model or classifiers) that the architecture review and the real-time audit describe.
- **Entry point:** `main.py` → `detect(...)`: `WingWalker` (position state, signals), `is_obstacle` /
  `check_combined_side_obstruction`, `handle_airplane`, three `perform_*_check` functions, `get_overall_result`;
  `helpers.py` (angle, distance, line fit); `walker_movement_start.py`.
- **Dependencies:** `cv_common` dd5b554 (not in the local archive; the local copy is ac5098d), `db_worker` 5a4aa83.
  Packages (README): mmpose 1.3.1, mmcv 2.1.0, mmengine 0.10.4, scikit-learn 1.6.1, imbalanced-learn, joblib, torch 2.2.
  Models in `models/` (`worker_classifier_svc.pkl`, `walk_along_classifier_rfc.pkl`, `*_walk_start_prediction_sgb.pkl`);
  HRNet weights by DVC; training scripts in `scripts/worker_related_models_training/`.
- **Run locally:** from the repository root: `python main.py --source <video>.mp4 --inferences-dir <folder with GM and
  tracker ndjson> --weights-dir weights [--write-video] [--device cpu]`.
- **Code references:** step 1 `main.py:68-153, 282-292, 1055-1083`; step 2 `main.py:209-229, 337-365, 796-851`; step 3
  `main.py:854-887, 1027-1048`; step 4 `main.py:156-199, 325-334, 1057-1089`; step 5 `main.py:368-416, 1106-1115`;
  step 6 `main.py:419-650`, `helpers.py:27-48`; step 7 `main.py:665-730`, `walker_movement_start.py:89-122`; step 8
  `main.py:890-897, 1136-1165, 1187-1198`.
