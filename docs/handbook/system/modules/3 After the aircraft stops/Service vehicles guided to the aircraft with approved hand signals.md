# Service vehicles guided to the aircraft with approved hand signals

> When a belt loader (the vehicle with a conveyor belt that carries bags to a cargo door) drives up to the aircraft, a
> worker should stand in front of the cargo door and guide the driver with hand signals. The check makes sure every belt
> loader that comes to a door is guided this way. When a loader stops at the door, the software runs a pose model on the
> worker who stood in front of the door during the approach; a raised hand for at least 1 second counts as a signal.

## Status

| | |
|---|---|
| How accurate it is | 65 of 68 turnarounds correct (96 %) on the monthly test |
| Fail turnarounds it caught | 13 of 13 |
| In production | the version of November 2025 (the decision logic last changed in July 2025) |
| Who looks after it | to assign |
| Biggest open problem | A raised wrist is only a rough stand-in for an approved hand signal, and the client's blocked-view Not observed is switched off in the code. |

## What the client wants

The client calls this check *All [ground support equipment] guided into aircraft using approved hand signals*. Its rule
speaks only of belt loaders, and so does the module; other service vehicles are not checked.

| Verdict | When |
|---|---|
| Pass | Every belt loader that comes to the aircraft's open doors has a person guiding it with visible hand signals. |
| Fail | No worker is seen in the area in front of the door during the approach; or workers are seen but give no valid hand signals; or the signals are too short. |
| Not observed | No belt loader is seen approaching an open door, or no aircraft appears in the video. |
| Not observed, view blocked | Large obstacles in the centre of the picture, or obstacles at the side larger than 1.5 times a person's height. |

A verdict is the answer of a check: Pass, Fail or Not observed. The client puts the check in its post-processing group
(checks judged after the turnaround) and marks it as not ready for production. Its list also has a combined check,
*Proper beltloader approach including 3 stop brake check and handsignals*, built from this check and the *Three-stop
brake check*; how the two are combined is to confirm.

## When and where it looks

The stage (part of the turnaround) is the time after the aircraft stops. The module works from the aircraft's arrival to
its departure, as the tracker marks them (the arrival after about 4 seconds standing still, the departure after about
10 seconds of movement). For each loader it looks at the 30 seconds to 5 seconds before the loader stops at the door.

Cameras: for aircraft both cameras, for jets the wing camera (the client's two aircraft types). The cone camera (looks
towards the aircraft nose) watches the front cargo door, the wing camera (looks along the wing) the rear door. When both
run, the client merges the results: Fail on either camera gives Fail; Pass on one and Not observed on the other gives
Pass.

## What it looks at

- **From the General Model:** the front and rear cargo doors, rear wheels and the aircraft engine (a detection is a box
  the detector draws around an object).
- **From the tracker:** the aircraft, the belt loaders (moving or stopped) and people, with the point at their feet (a
  track is the same object followed from frame to frame).
- **From the video itself:** yes. The pose model needs the pictures; frames are kept in memory while no loader moves.
- **Own models:** none trained by the team. A standard pose model finds people's joints; the module uses the elbows and
  wrists. It runs on a graphics card.

## How it decides, step by step

A frame is one picture of the video; the cameras take 8 per second.

1. **Reading ahead for the door.** After the tracker's arrival flag, the module averages the first 60 seconds of
   detections of the cargo door (front door on the cone camera, rear door on the wing camera) as a fallback door
   position.
2. **The workers area.** In the main pass after the arrival it builds an area in front of the door, where the guide
   should stand. The door is the average of its last 10 seconds of detections, or the fallback until it is first seen.
   The area is 1.5 times (cone camera) or 3.5 times (wing camera) the door's width, centred on the door, and reaches
   below the aircraft's lower edge.
3. **Collecting workers.** Once no loader has stood at the door for 7.5 seconds, people whose feet are in the area are
   candidates. If a loader taller than 50 pixels is moving, the pose model runs on them at once; otherwise the frame is
   kept in memory (up to 30 seconds).
4. **A loader arrives** when the tracker reports it stopped and its box overlaps the area (cone camera: the right half
   only), with its lower edge inside the area's height. On the cone camera, loaders behind a rear wheel are ignored; the
   wing camera also accepts a loader hidden by the engine or standing face-on below the door. The biggest is taken. A new
   track number within 15 seconds of the last loader is the same loader (the tracker sometimes loses an object for a
   moment and gives it a new number).
5. **Can it be judged?** For each new loader the check runs once, and only if the loader was moving within the last 10
   seconds and the area existed for more than 10 seconds of the look-back time. Otherwise the loader "could not be
   analyzed".
6. **Finding the guide.** The pose model runs on the stored frames; the poses from 30 to 5 seconds before the stop are
   kept. The guide is the worker with the most poses in that window.
7. **Signals.** A frame shows a signal when the guide's wrist is at or above the elbow (5 pixels of tolerance) on either
   arm, with both points found at a confidence (the pose model's own certainty, from 0 to 1) of at least 0.2. At least
   8 frames (1 second) with a signal: registered. Fewer, or no worker: not registered.
8. **Verdict** at the departure or the end of the video. Loaders followed for less than 60 seconds are ignored. None
   left, or none that could be analyzed: **Not observed**. Otherwise the ones that could not be analyzed are dropped;
   all registered: **Pass**; any not registered: **Fail**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Averaging window for the door and aircraft boxes | 10 seconds | Where the workers area is |
| Start of the look-back window; frame memory | 30 seconds before the stop | Earlier signals are not seen |
| End of the look-back window | 5 seconds before the stop | The last 5 seconds are ignored |
| Loader moving recently; area present long enough | 10 seconds each | Otherwise "could not be analyzed" |
| Signal rule (in the code) | wrist at or above the elbow, 5 pixels of tolerance, confidence 0.2, at least 1 second | What counts as a hand signal |
| Shortest loader visit that is judged | 60 seconds | Shorter visits are ignored |
| New track number merged into the last loader | within 15 seconds; half of it (7.5 seconds without a loader at the door) starts worker collection | Fewer duplicate loaders; when workers are collected |
| Share of the area hidden; obstacle rate | 0.35; 0.5 | Mark the area as obstructed; not used for the verdict |
| Overlap limit for a loader staying in place; frames to decide the aircraft type; obstacle width | 0.8; 40 frames (5 seconds); 0.6 of the picture | Not used for the verdict |

## What it reports

- **Sentence:** "All of the beltloaders' hand signals were registered." or "Not all …", then one line per judged loader:
  "Beltloader <id> hand signals [NOT ]registered (<start> - <end>)."; for Not observed, the reason.
- **Timeline entry** (the stretch of video the website marks): one per judged loader, Pass or Fail, from its first to
  its last frame.
- **Files:** a drawing file with the workers' joints; an annotated video only when video writing is switched on.

## How accurate it is

The monthly test is the set of the client's validated turnarounds we measure on: 69 turnarounds, 68 of them labelled for
this check. The module gave the client's verdict on 65 (96 %). The client labelled 13 Fail and the module caught all 13.
The 3 wrong verdicts were on turnarounds labelled Pass or Not observed. With 13 Fail labels the test does show that the
check catches unguided approaches. Our sources do not say which turnarounds were wrong, or why.

## Known problems

- **A raised wrist is not an approved signal.** The client asks for approved hand signals; the code only checks that a
  wrist is at or above the elbow for 1 second. There is no list of approved signals and no wand check, so any raised
  hand can give Pass.
- **No blocked-view verdict.** The obstruction is measured, but the line that would give Not observed is switched off
  (commented out). A blocked view gives Pass or Fail instead of Not observed.
- **The driver filter practically never runs.** It is called with person number 0 written into the code, so the loader's
  driver standing in the area could be picked as the guide.
- **Timeline says Fail on a Not observed.** When every loader "could not be analyzed", the verdict is Not observed but
  the timeline entries say Fail.
- **Look-back time differs from its comment.** The comment says 5 to 15 seconds; the code uses 5 to 30 seconds. The
  aircraft type is computed but never used.
- **"Open doors" is not checked separately;** the module trusts the door detection (to confirm).
- **Heavy.** Up to 240 full pictures (about 1.5 gigabytes) are kept, and up to about 200 pose model calls can run on one
  stop.
- **The team's own error list** names the signal rule, the worker's position, and missed detections of the aircraft, the
  door and the loader's approach.
- **Who confirms:** the door question is for the module's owner (to assign) to check on a labelled turnaround; how the
  combined check is built, for Ihor, the technical lead. A stricter signal rule would change verdicts the client sees,
  so it is decided with the client's safety team.

## In real time

Not in the first real-time set. The module reads ahead (it averages the door position over the first 60 seconds after
the arrival) and keeps 30 seconds of pictures; in real time the earlier frames are gone. The team rates it "needs a new
first pass": a few seconds after the arrival the door no longer moves, so its position can be fixed from the past only.
The way it is computed must change, the meaning does not. It would decide when each loader stops at the door: feedback
after the approach, not a warning before it. The client puts the check in its post-processing group.

Cost on the team's test machine, one 36-minute turnaround: the reading-ahead pass alone, with its share of the General
Model and the tracker (which follows the aircraft, belt loaders and people), needs 36.6 of the 125 milliseconds each
frame may take at 8 frames per second (29 %). As a post-processing job it takes 91 seconds, 257 seconds of processor work
and at most 3.1 gigabytes of memory.

## For developers

- **Module code in our workspace:** M13. Client check name: *All GSE guided into aircraft using approved hand signals*.
- **Repository:** `dxgat/detectors/hand-signals`; production line `master` @ `60c0faf` (2025-11-13); default branch the
  same. The last commit only adds an issue list; `main.py` last changed in `6bd027f` (2025-07-30), the commit the
  architecture review pinned.
- **Entry point:** `main.py` → `detect(...)`; all logic in `main.py`: `AirplaneWithWorkersROI` (door, area),
  `collect_workers_history`, `find_beltloader` / `manage_beltloader` (arrival, trigger), `Beltloader.check_hand_signals`
  (the rule), `generate_report`. Task name `handsignals`. Error list `scripts/specialized_issues.txt`.
- **Run on one turnaround:** `python main.py --source <video>.mp4 --inferences-dir <folder with GM and tracker ndjson>
  --local-inferences --weights-dir weights [--cone-camera] [--write-video] [--device cpu]`.
- **Settings keys:** `door_bbox_window_length` 80; `max_prev_frame_to_consider` 240; `min_prev_frame_to_consider` 40;
  `moving_bl_history_length`, `min_roi_presence_time` 80; `min_bl_stay_time_thresh` 480; `min_bl_swap_time_thresh` 120;
  `min_bl_height` 50 px; `max_occlusion_ratio` 0.35, `max_obstacle_rate` 0.5 (unused for the verdict);
  `min_bl_stay_iou_thresh` 0.8, `min_plane_type_frames_eval` 40, `obstacle_width` 0.6 (unused). In code: signal rule
  wrist ≤ elbow + 5 px, keypoint confidence ≥ 0.2, ≥ 8 frames; area 1.5× / 3.5× door width; first-pass door average
  480 detections; pose on CLAHE frames; driver filter called with id 0.
- **Code places:** step 1 `main.py:761-797`; step 2 `:128-179`; obstruction `:181-220`; step 3 `:522-589, 886-891`;
  step 4 `:467-520, 632-638`; step 5 `:640-650`; step 6 `:276-305, 338-370`; step 7 `:307-336`; step 8 `:73-113,
  386-388`; unused aircraft type `:675-717, 919-920`.
- **Dependencies:** `cv_common` 8e3a7bf (not in the local archive; local copy ac5098d, cv_common master, which the CI
  builds with), `db_worker` 5a4aa83. mmpose 1.x, mmengine, opencv-python, torch. Weights by DVC:
  `td-hm_hrnet-w48_8xb32-210e_coco-256x192-0e67c616_20220913.pth` (HRNet-W48, COCO keypoints); the
  `hrnet_w48_coco_384x288_dark` copy is never loaded. Image built on the mmpose base image.
- **Real time and sources:** `docs/04_modules.md` (RETHINK), `docs/analysis/rt_module_selection.md` (not in real time
  v1), `docs/analysis/rt_module_cost.md` (two passes, first pass only); `docs/modules/hand-signals.md`,
  `docs/analysis/module_review_2026-10.md`.
