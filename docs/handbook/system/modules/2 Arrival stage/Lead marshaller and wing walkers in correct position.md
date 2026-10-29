# Lead marshaller and wing walkers in correct position

*In plain words: lead marshaller and wing walkers in position.*

> Before the aircraft arrives, wing walkers must stand on both sides of the stand; while it rolls in, they must walk
> along both sides giving hand signals with their wands. The module uses trained models to decide who is a wing walker
> and on which side, and a pose model to spot raised hands. It does not check the lead marshaller.

## Status

| | |
|---|---|
| How accurate it is | 62 of 68 turnarounds correct (91 %) on the monthly test |
| Fail turnarounds it caught | 48 of 49 |
| In production | the version of May 2026 (its logic last changed in March 2026) |
| Who looks after it | to assign |
| Biggest open problem | The lead marshaller and the wands are never checked, and wing walkers need 90 seconds in position, not 10 minutes. |

## What the client wants

*Lead marshaller and wing walkers in correct position*

| Verdict | When |
|---|---|
| Pass | At least 2 wing walkers, one per side, stand in position for at least 10 minutes before the arrival, then walk along both sides of the aircraft with wands and hand signals as it arrives. |
| Fail | 0 or 1 wing walker is seen, and the side without one is not blocked; or a wing walker made no hand signals with wands. |
| Not observed | No aircraft in the video, a pre-arrival stage shorter than 10 minutes, or no arrival. |
| Not observed, view blocked | Fail does not apply, and either side is blocked in more than 65 % of the pre-arrival or arrival frames. |

A verdict is the answer of a check: Pass, Fail or Not observed. The pre-arrival stage is the part (stage) of the
turnaround before the aircraft arrives. The lead marshaller, named in the check, guides the aircraft in; the rule
itself only describes wing walkers.

## When and where it looks

From the first frame of the video (one picture; the cameras take 8 per second) to the frame on which the tracker (the
part that follows objects from frame to frame) reports the aircraft's stop, after about 4 seconds standing still:
first the pre-arrival stage, then the arrival, from the first movement to the stop. It runs on the cone
camera (which looks towards the aircraft nose), for aircraft and jets.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object), only to tell when a
  side is blocked: people, ladders and all vehicles: service vehicles (ground support equipment: tugs, belt loaders,
  fuel trucks, tractors), trailers, air conditioning units and vehicles marked as in the way.
- **From the tracker:** the aircraft and person tracks (a track is the same object followed from frame to frame).
- **From the video itself:** yes, for the pose model (after a contrast boost).
- **Own models:** a role model (left wing walker, right wing walker or neither, from a person's box and rough angle and
  distance); a walk-along model (the same three labels, from a person's path); two walking-start models (when a walker
  began to walk); and a ready-made pose model (it finds a person's joints), on a graphics card, though the production
  worker's settings name a processor: to confirm.

## How it decides, step by step

1. **Who stands where.** On every frame the role model labels each person. A person is "on position" after 5 seconds
   with the same side label, and leaves after 6 seconds labelled "neither" or 12 seconds unseen.
2. **Blocked sides.** A large object in the middle (at least 14 % of the picture) blocks both sides; an object other
   than a person at the left edge blocks the left side; boxes on one side adding up to 2.2 % of the picture (people
   included) block that side. Blocked frames are not held against a side whose walker, on position then, is still
   there at the verdict.
3. **The aircraft.** Its first moving frame starts the arrival. If it disappears for 10 seconds before stopping, it was
   a passing aircraft and the approach data is cleared.
4. **Approach.** Every frame it records rough angles and distances of workers and aircraft, and runs the pose model on
   all workers: a wrist above the elbow (confidence 0.2 or more) is a signal frame. Until the aircraft is seen,
   each worker's last 33 positions (about 4 seconds) and 12 seconds of pictures are kept, in case it is detected late.
5. **Pre-arrival check,** at the stop. An arrival that started within the first 7.5 minutes gives Not observed.
   Otherwise, from the state when the aircraft first appeared, a side passes if a walker was on position there for 90
   seconds; a side without one is Not observed if blocked in at least 65 % of the pre-arrival frames, else Fail.
6. **Walk-along check.** Each worker's path from the start of the arrival to the stop is smoothed and fitted with a
   line (more than 4 seconds of path needed). The walk-along model labels the worker from the angle and gap between
   their path and the aircraft's, the path's length and the distance. Sides are scored as in step 5.
7. **Hand-signal check.** For walkers with at least about 14.4 seconds (left) or 15 seconds (right) of path, a
   walking-start model finds when they began to walk and only later signals count; otherwise all count. One second of
   signals passes a side; walkers without them fail it; a side without a walker is Not observed.
8. **Verdict.** For each check: both sides Pass gives Pass, any Fail gives Fail, else Not observed. Overall: any Fail
   gives **Fail**, else any Not observed gives **Not observed**, else **Pass**. No stop: **Not observed**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Take / leave a position | 5 seconds on one side; 6 seconds as "neither" or 12 seconds unseen | Who is on position |
| Switch sides | more than 5 seconds labelled as the other side | Side changes, time restarts |
| Time on position | 90 seconds (the rule: 10 minutes) | A side passes |
| Shortest pre-arrival stage | 7.5 minutes (the rule: 10 minutes) | Shorter: Not observed |
| Blocked share | 65 % | Missing walker: Not observed, not Fail |
| Middle object | centre between 37 % and 60 % of the width; at least 14 % of the picture and 40 % of the width | Blocks both sides |
| Left-edge object | not a person; starts within 18 % of the width; at least 0.85 % of the picture and 6.5 % of the width | Blocks the left side |
| Side total | boxes of at least 1.2 % each, together 2.2 % | Blocks that side |
| Passing aircraft | gone for 10 seconds | Data cleared |
| Path for the walking-start model | about 14.4 seconds left, 15 seconds right | Only later signals count |
| Signals per side | 1 second | A side passes |
| Signal | wrist above the elbow, confidence 0.2 | What counts as a signal |

## What it reports

- **Sentence:** "Prearrival check is <verdict> - <reason> (<times>). Arrival walk along check is … . Arrival hand
  signals check is … ." or "Plane full stop was not detected (…)"; one verdict for the whole check.
- **Timeline entries:** pre-arrival (start of the video to the start of the arrival), walk-along and hand signals (start
  of the arrival to the stop).
- **Files:** a drawing log with the pose points, a plot of the paths on every run, an annotated video on request.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this check. The
module matched the client on 62 (91 %). The client labelled 49 Fail and the module caught 48, so 1 of its 6 errors is
a missed violation; the other 5 are turnarounds labelled Pass or Not observed where it said something else. Most
labelled turnarounds are Fails, so the test does show that it catches violations; which ones it got wrong is not in
our sources.

## Known problems

- **No lead marshaller, no wands.** Neither is checked; a hand signal is any wrist above the elbow. The rule asks for
  signals with wands, so a raised hand without a wand passes.
- **Shorter times than the rule.** 90 seconds on position instead of 10 minutes, and 7.5 minutes of pre-arrival instead
  of 10 (a code comment says production will use 10 minutes). This gives Pass where the rule gives Fail, and Pass or
  Fail where it gives Not observed.
- **Presence stops early.** It is counted until the aircraft first appears, not until it stops.
- **Late signals count.** Signals found in kept pictures are filed under the decision moment, so they always count as
  made after the walker began to walk.
- **Crowds block.** People's own boxes add to a side's blocked area, so a crowd can turn a missing walker into Not
  observed instead of Fail.
- **Build (to confirm).** Its build files lack the pose and model libraries it needs; how production builds it is to
  confirm. Two older role-model files and a pose-weights copy are never used.

## In real time

It can run as it is, with the video pictures, deciding at the stop from what it has already seen. On a 36-minute test
turnaround in the real-time test setup it matched post-processing (after the turnaround), with the verdict 10 seconds
after the stop. Own work: 2.5 milliseconds per frame; with the shared General Model (main detector plus vehicle part)
and tracker, 25.8 of the 125 milliseconds each frame may take (21 %). As a post-processing job: about 59 seconds. With
all modules together on another turnaround, its sentence (not its verdict) differed, and around the arrival, as the
pose-model modules fill their picture buffers, memory peaked and single frames waited up to 15 seconds. Planned savings,
same results: one shared pose model, no full-picture copies, cut-outs in the buffer. The client's split puts the check
in the real-time group and marks it not yet production-ready.

## For developers

- **Module code:** M15. **Repository:** `dxgat/detectors/lead-marshaller-and-wing-walkers-in-position`; production
  `pre_arrival_departure` @ `9e1a9f0` (2026-05-29; logic 9746ddf, 2026-03-20). `master` @ `9b37ccf` (2025-06-19) is
  the older rule-based version (no pose model or classifiers) that the architecture review and real-time audit describe.
- **Entry point:** `main.py` → `detect(...)`: `WingWalker`, `is_obstacle` / `check_combined_side_obstruction`,
  `handle_airplane`, three `perform_*_check`, `get_overall_result`; `helpers.py`; `walker_movement_start.py`. Task
  `wingwalker`.
- **Models:** `models/worker_classifier_svc.pkl` (SVC), `walk_along_classifier_rfc.pkl` (RandomForest),
  `*_walk_start_prediction_sgb.pkl` (gradient boosting); HRNet-W48 (mmpose, flip test, `cuda:0` unless `cpu`, DVC);
  full-frame CLAHE. Unused: `worker_type_classifier*.pkl`, `hrnet_w48_coco_384x288_dark`.
- **Run:** `python main.py --source <video>.mp4 --inferences-dir <dir> --weights-dir weights [--write-video]
  [--device cpu]`.
- **Keys** (seconds × 8 in code): `wing_walker.init_thr` 5, `removal_thr` 6, `side_change_thr` 5, `not_visible_thr` 12,
  `prearrival_presence_thr` 90; `min_prearrival_duration` 450; `obstacle.central`, `.left_side_single`, `.left_side`
  (centre < 0.37, top < 0.73), `.right_side` (centre 0.6–0.91, top < 0.75), `.not_observed_thr_ratio` 0.65;
  `msg_display_thr` 10; `movement_buffer_capacity` 33; `max_buffer_duration` 12; `left_min_frames` 115,
  `right_min_frames` 120; `hand_signals_thr` 8 frames; `CONF_THRES` 0.2.
- **Code places:** step 1 `main.py:68-153, 282-292, 1055-1083`; 2 `:209-229, 337-365, 796-851`; 3 `:854-887,
  1027-1048`; 4 `:156-199, 325-334, 1057-1089`; 5 `:368-416, 1106-1115`; 6 `:419-650`, `helpers.py:27-48`; 7
  `main.py:665-730`, `walker_movement_start.py:89-122`; 8 `main.py:890-897, 1136-1165, 1187-1198`.
- **Dependencies:** `cv_common` dd5b554 (local ac5098d), `db_worker` 5a4aa83; mmpose 1.3.1, mmcv 2.1.0, mmengine
  0.10.4, scikit-learn 1.6.1, imbalanced-learn, joblib, torch 2.2. Client sheet: 4,800 frames (10 min); ProdReady
  False.
