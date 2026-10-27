# Wing walkers in position with approved wands during pushback

> During the pushback, a wing walker should walk along each side of the aircraft and signal with approved wands. The
> module checks that, in the first 60 seconds of the pushback, a person walks along each side and raises an arm, using
> the paths of people and aircraft in the cone camera's pictures and a pose model for the arms. Wands are not detected.

## Status

| | |
|---|---|
| How accurate it is | 56 of 68 turnarounds correct (82 %) on the monthly test |
| Fail turnarounds it caught | 12 of 15 |
| In production | the version of October 2025 |
| Who looks after it | to assign |
| Biggest open problem | Wands are never detected, although the report always says "approved wands". |

## What the client wants

*Wing walkers in proper position and using approved wands*

| Verdict | When |
|---|---|
| Pass | A wing walker with wands and hand signals is seen walking along the aircraft on both sides in the first 60 seconds after the departure starts. |
| Fail | At least one part of the check fails: a walker missing on a side, no wands, or no hand signals. |
| Not observed | There was no departure stage. |
| Not observed, view blocked | Fail was not triggered, and a side was blocked in more than 60 % of the frames of those 60 seconds. |

A verdict is the answer of a check: Pass, Fail or Not observed; a stage is a part of the turnaround; a frame is one
picture of the video (8 per second).

## When and where it looks

The check covers the stages before departure and the departure with pushback: the first 60 seconds after the aircraft
starts moving back (at the end of a video, 20 seconds are enough). It uses the cone camera (which looks towards the
aircraft nose), for aircraft and jets; the code does not check the camera and works out itself whether it sees an
aircraft or a jet (the client's two types).

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object on a frame):
  pushback tugs, aircraft wings and engines; as view blockers, belt loaders, service vehicles (ground support
  equipment: tugs, belt loaders, fuel trucks, tractors), trailers, fuel trucks, air conditioning units, vehicles,
  "obstacle" and "side obstacle" boxes.
- **From the tracker:** the aircraft track (the aircraft followed from frame to frame: stopped or moving, its departure)
  and the people tracks.
- **From the video itself:** yes, for the pose model.
- **Own models:** none in use. A ready-made pose model finds each person's joints (shoulders, elbows, wrists and more),
  on a graphics card or, if asked, the processor. A wand detector trained in-house is stored but not loaded.

## How it decides, step by step

1. **People and aircraft.** Every frame: the widest aircraft track and the people tracks, without tug drivers (people at
   least 13 % as tall as the tug, with over 70 % of their box inside it, or inside its width and crossing its top edge).
2. **Aircraft or jet.** Until the tracker's departure, frames showing a wing and an engine on the aircraft vote: engine
   above the wing "jet", below "aircraft"; the majority wins (default "aircraft").
3. **Parked, then departure.** "Stopped" on 40 frames (5 seconds) in total: parked. The first moving frame after that
   starts the departure, confirmed after 64 moving frames (8 seconds); a stopped frame before that discards it.
4. **From the first moving frame:** each person's rough position seen from above (direction from the box's place across
   the picture, distance from its height); the pose model on a contrast-enhanced picture, boxes enlarged by 10 %;
   blocked sides counted with the picture areas of *Pushback waits until the wing walkers are in place and ready*.
5. **Decision moment.** 60 seconds after the departure start, or the video's end if at least 20 seconds were seen. The
   aircraft box must have shrunk 17.5 % between the first and last 3 seconds; otherwise the departure was false and
   the module waits for the next.
6. **Paths.** At least 13 points in the window, smoothed over 11 frames and fitted with a straight line. Jet paths of 270
   points or more (about 34 seconds) are cut at their first major turn.
7. **Wing walker.** The line is within 42 degrees of the aircraft's, the person does not move against the aircraft, and
   a path longer than 20 seconds spans at least 12 metres. The side comes from lines parallel to the aircraft's path
   through the path starts; a left-side walker must also start above the aircraft's path on the map seen from above,
   which rejects people walking in the middle (for a jet path cut at a turn, most points must be above).
8. **Hand signals.** A frame counts when a wrist is above its elbow or below it by less than a tolerance (8 % of the box
   height for left-side walkers; right side 4.8 % for aircraft, 7 % for jets), with both points' confidence at least
   0.2. A walker signals with 8 such frames (1 second), or 20 % of his frames if fewer.
9. **Per side.** No walker: Not observed if the side was blocked in at least 60 % of the window, otherwise Fail.
10. **Verdict.** **Pass** only if both sides have a signalling walker. **Fail** if a side has no walker and is not
    blocked, or a walker does not signal. Otherwise, or without aircraft or departure, **Not observed**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Stopped and moving time | 5 seconds in total; 8 seconds | Departure start |
| Window | 60 seconds (end of video: 20) | Stretch that is checked |
| Box shrink | 17.5 % | Less: false departure |
| Path angle | 42 degrees | Who is a wing walker |
| Arm tolerance | left 8 %; right 4.8 % (aircraft) or 7 % (jet) of the box height | Hand-signal frames |
| Signal frames, joint confidence | 8 frames (1 second); 0.2 | Hand signals |
| Blocked share | 60 % | Side Not observed |
| Blocking areas, tug drivers | as in the readiness check; 70 % inside a tug | Blocked sides, drivers |
| Jet turn cutting | 270 points and three shape values | Jet paths |

Three settings-file values are unused.

## What it reports

- **Sentence**, for example: "Wing-walkers were present on both sides of the plane. Both wing-walkers were performing
  hand-signals with approved wands. Time : <time> -- <time>". Fail sentences mention wands too ("Both wing-walkers were
  using approved wands, but weren't performing hand-signals."): fixed text. Not observed: "Airplane was not detected.",
  "Departure wasn't observed." or "Airplane movement path was too short".
- **Timeline entry:** the verdict from the departure start to the window end; none without a departure.
- **Files:** per-frame drawings with pose points, a picture of the paths, two data files (paths, hand signals); an
  annotated video if switched on.

## How accurate it is

The monthly test (the client's validated turnarounds we measure on) has 69 turnarounds; 68 were labelled for this check
and the module matched 56 (82 %). Of the 15 labelled Fail it caught 12; its other 9 errors are on turnarounds not
labelled Fail. As wands are not detected, the number cannot show whether walkers without approved wands are caught. In
our own re-run on 55 monthly-test turnarounds, only one of 11 Fail labels depended on the hand-signal rule; the rest
came from a missing walker or a blocked side.

## Known problems

- **Wands are never checked.** The wand detector is switched off in the code, yet the report always says "approved
  wands"; the architecture review calls this a critical gap. A walker without wands can pass.
- **Any raised arm counts.** "Hand signals" means a wrist at or above the elbow, within the tolerance, for about 1
  second.
- **Own timing (to confirm).** 5 seconds stopped and 8 moving, not the tracker's moments; the stop count never resets,
  so earlier pauses may mark the aircraft parked too early.
- **End of video.** The 20-second fallback reads the video length; real time needs an end-of-session signal.
- **Shared memory.** Hand-signal and path data are never cleared between videos run in one program.
- **Sensitive to the pose model.** With one shared, faster pose model for all pose checks, this check fell from 47 to 36
  correct on 55 turnarounds of the monthly test. Every loss comes from the hand-signal rule on very small people (about
  57 pixels tall, an arm about 10 pixels): arm confidence sits near the 0.2 limit for both models, the old model puts a
  wrist at elbow height about twice as often, and the tolerances were tuned on it. A recalibration is in progress.
- **Storage.** An unused 255-megabyte pose model copy is stored; the weights list names the folder twice.

## In real time

The client puts this check in the "streaming" group: wanted during the turnaround, but seconds do not matter. It runs
with the pictures its pose model needs: one pass, deciding 60 seconds after the movement starts (an older audit's
"ready as is" concerned the version without pose). In the real-time test setup it gave the post-processing (after the
turnaround) verdict and sentence 44 seconds after the tracker's departure moment; the reduced inputs changed nothing on
4 test turnarounds. Cost with the General Model and the tracker: 26.6 of the 125 milliseconds a frame may take (21 %);
own work 5.1 milliseconds alone, 8.3 on average with all checks; as a post-processing job, 111 seconds per turnaround.

To lighten it for real time: one pose model shared by the pose checks, no full-picture copies. The shared model is 6 to
7 times faster per call (about 58 against 9 milliseconds) and cut this module's total time by 24 % in the validation
run, but costs verdicts until recalibrated (see Known problems). The recalibration records both models' arm points on
the same walkers in the 40 turnarounds where pose matters and replays the rule offline, seeking a confidence limit,
tolerances and minimum frames that win back the 11 lost Passes and keep the one hand-signal Fail. The values go to the
accuracy reviewers with the verdict table before production; the fallback is the old model in this check.

## For developers

- **Module code:** M27. **Repository:** `dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands`;
  production `obstruction_hand_signals` @ `3460afc` (2025-10-29); `master` @ `5f7ca1a` (2025-06-19): walking along
  only, wand Pass hard-coded, no pose.
- **Entry point:** `main.py` → `detect()`; `Plane` (timing, type), `WingWalker` (paths, pose); `helpers.py` (geometry,
  turns, CLAHE); `obstacle_logic.py`.
- **Run:** `dvc pull`; `python main.py --source <video>.mp4 --inferences-dir <dir> --weights-dir weights [--device cpu]
  [--write-video]`.
- **Keys:** `plane.stop_thd`, `depart_thd`, `departure_duration`, `departure_bbox_change`, `degree_thresh`,
  `min_departure_len`; `handsignals.<type>.<side>.margin_of_error_l/_r`, `min_frames`, `conf_thr`;
  `obstacle.not_observed_thr_ratio`, `obstacle.*`, `obstacle.pushback.min_driver_intersect`; `turn_detection.*` (270,
  0.15, 0.02, 0.8). Not read: `task`, `weights`, `message_display_duration`.
- **Code places:** step 1 `main.py:741-753`; 2 `:65-98, 161-189`; 3 `:129-157`; 4 `:219-291, 631-694, 949-952`; 5
  `:981-1012`; 6 `:326-376`, `helpers.py:63-84, 132-187`; 7 `:397-453`; 8 `:314-323, 494-505`; 9–10 `:480-545,
  1069-1076`; wand line `:810`.
- **Dependencies:** `cv_common` dd5b554 (export: ac5098d), `db_worker` 5a4aa83; mmpose 1.3.1, mmcv 2.1.0, torch 2.1.2;
  DVC HRNet-W48 COCO with flip test; unused `wand_detector.pt`, 255 MB HRNet copy. Shared pose RTMPose-l:
  `pose_unification.md` §4, §5, §8; recalibration `scripts/ww_pose_*.py`.
