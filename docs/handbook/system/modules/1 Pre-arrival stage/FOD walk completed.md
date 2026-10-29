# FOD walk completed

*In plain words: foreign object debris walk completed.*

> Before the aircraft arrives, a worker must walk the stand along its path and pick up loose objects (foreign object
> debris) that could damage it. The module follows people in the cone camera's pictures and, at the stop, tests their
> paths against a corridor along the aircraft's approach.

## Status

| | |
|---|---|
| How accurate it is | 64 of 68 turnarounds correct (94 %) on the monthly test |
| Fail turnarounds it caught | 47 of 49 |
| In production | the version of April 2026 |
| Who looks after it | to assign |
| Biggest open problem | People are followed only until the aircraft first appears, so a later walk, or a false early aircraft detection, hides the walk. |

## What the client wants

*FOD walk completed*

| Verdict | When |
|---|---|
| Pass | The diamond area is visible and someone walked it from beginning to end, "horizontally": from the start line of the safety clearance zone to the end of the lead-in line. |
| Fail | The diamond area is visible, nobody walked it from beginning to end, and the aircraft arrived. |
| Not observed | The diamond area is not visible, or the aircraft did not arrive. |
| Not observed, view blocked | The view is blocked in more than 80 % of the pre-arrival stage. |

A verdict is the answer of a check: Pass, Fail or Not observed. The diamond area is the safety zone the aircraft rolls
into (see *Safety zone confirmed clear*); the lead-in line is the painted line the aircraft follows to
its stop. The pre-arrival stage is the part (stage) of the turnaround before the aircraft arrives.

## When and where it looks

The module reads from the first frame of the video (one picture; the cameras take 8 per second) to the frame on which
the tracker (the part that follows objects from frame to frame) reports that the aircraft has stopped, once it has
stood still for more than 4 seconds. It records people's paths only until the aircraft first appears in the picture. It
runs on the cone camera (which looks towards the aircraft nose), for aircraft and jets, without checking which camera
filmed the video.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object): the aircraft's front
  wheel, nose and tail, for the corridor; belt loaders, pushback tugs and other service vehicles (ground support
  equipment: tugs, belt loaders, fuel trucks, tractors), for a blocked view and to spot drivers.
- **From the tracker:** the widest aircraft track (a track is the same object followed from frame to frame) and its
  stop; the person tracks.
- **From the video itself:** each person's picture, for the pose model; the stop frame, for drawing.
- **Own model:** a ready-made pose model (it finds a person's joints; not trained by us), of which only the shoulders are
  used: a left shoulder left of the right one means the person is seen from behind. It runs on an ordinary processor.

## How it decides, step by step

1. Reads the boxes, person tracks and aircraft track frame by frame; follows the widest aircraft.
2. A frame is blocked when a belt loader, pushback tug or other service vehicle box is wider than 30 % of the picture
   (576 of 1,920 pixels) with its centre in the right 70 %; the frame is still used.
3. Until the first aircraft track appears, it records each person's path (the middle of their box's bottom edge),
   skipping boxes under 20 pixels and people sitting in a vehicle (box more than 50 % inside a vehicle box). The pose
   model sorts each point into the person's "facing away" or "facing the camera" path.
4. While the aircraft approaches, it records the front wheel nearest the aircraft's centre (inside the aircraft box) and
   its rough distance from the box height (a wheel taken as 0.5 metres tall, an aircraft as 7 metres).
5. At the stop: **Not observed** if the shared arrival check sees no arrival (aircraft box grew 18 % or less) or no
   pre-arrival stage (aircraft first seen in the first 11.25 seconds), or if blocked frames exceed 80 % of the
   frames before the stop.
6. Builds the corridor from the front wheel at the stop back along its path to where it was about 30 metres further away
   (estimated), 373 pixels to each side (4 metres at 30 metres). If the wheel path is under about 15 metres or missing,
   it uses the aircraft box: tail to nose, or, without them, box centre to a point 200 pixels aside.
7. A walk counts when the person was inside the corridor for 5 seconds in total, the near and far ends of their path lie
   within 20 % of the corridor's height from its ends, and the walk's direction lies within the angle of the corridor's
   sides. People facing away must walk away from the camera, the others towards it.
8. **Pass** if at least one walk is found. Otherwise **Fail** ("not performed properly" if someone spent 5 seconds in
   the corridor, else "not performed at all"). No stop: **Not observed**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Blocking box | wider than 30 % of the picture, centre in the right 70 % | Which frames are blocked |
| Blocked share | 80 % of the frames before the stop | More: Not observed |
| Corridor | about 30 metres back from the stop (estimated); 373 pixels to each side (4 metres at 30 metres) | Where the walk must be |
| Time in the corridor | 5 seconds in total | Shorter visits do not count |
| End tolerance | 20 % of the corridor's height | Path ends near the corridor ends |
| Distance estimate | aircraft 7 metres, wheel 0.5 metres, lens 35 millimetres, sensor pixel 0.0125 millimetres | Distances from box heights |
| Fallback corridor | wheel path under about 15 metres: tail to nose, or 200 pixels from the centre | Corridor without a wheel path |
| People | at least 20 pixels; not more than 50 % inside a vehicle | Who is followed |
| Arrival check | box growth more than 18 %; first sighting 11.25 seconds or later | Arrival and pre-arrival filmed |

## What it reports

- **Sentence.** Pass lists each walk with the worker's number and the times ("Fod walk was performed by …", the client's
  short form). Fail: "Fod walk was not performed properly." or "Fod walk was not performed at all." with the time span.
  Not observed: "No arrival stage", "No pre-arrival stage", "There were obstacles" or "Plane arrival was not captured".
- **Timeline entry:** one Pass block per walk; one Fail block from the start of the video to the stop; none for Not
  observed.
- **Files:** a drawing file with person tracks, front wheels, "Camera is blocked!" and, for Pass, the walk's progress;
  an annotated video on request.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this check. The
module matched the client on 64 (94 %). The client labelled 49 of them Fail and the module caught 47, so 2 of its 4
errors are missed violations; the other 2 are turnarounds labelled Pass or Not observed where it said something else.
Most labelled turnarounds are Fails, so the test does show that it catches violations; our sources do not say which
turnarounds it got wrong.

## Known problems

- **Followed only until the aircraft appears.** A later walk, or a false early aircraft detection, hides the walk (a
  recorded case); the rule has no such limit, so a walk that was done can get Fail.
- **Zig-zag walks pass.** Only the path's ends and the time in the corridor are checked.
- **Facing direction without confidence.** It comes from the shoulder order alone; a wrong answer splits the path
  wrongly and can change the verdict.
- **Estimated distances; which direction?** Distances come from box heights with assumed sizes, not a calibrated camera.
  The rule says "horizontally"; the module checks a walk along the approach line (the architecture review reads the
  rule as a horizontal crossing). What the client means: to confirm.
- **No "diamond area visible" check.** Without a front wheel the corridor comes from the aircraft box, and blocked frames
  are judged by box size, not by whether the corridor is hidden: where the rule says Not observed, it can say Pass or
  Fail.
- **Arrival check.** Meant to need 90 seconds before the aircraft appears, it waits 11.25, so short pre-arrival stages
  count. A track starting just before the stop gives "No arrival stage"; with no answer on the stop frame, both arrival
  tests are skipped.
- **Wasted work.** The stop frame is drawn on even without video writing; the pose model runs per person picture, not
  in batches. No effect on the verdict.

## In real time

It can run as it is: one pass, in order, deciding at the stop (from the tracker today; from the stage detector, the
part that knows where in the turnaround we are, in real time), with the pictures for the pose model. As it judges a
finished procedure, real time only brings the report sooner.

On a 36-minute test turnaround in the real-time test setup it matched post-processing (after the turnaround) in verdict
and sentence, at the moment of the stop. Own work: 1.32 milliseconds per frame; with the shared General Model (main
detector plus vehicle part) and tracker, 22.8 of the 125 milliseconds each frame may take (18 %). As a post-processing
job: about 21 seconds. Planned savings with identical results: the pose model only for people not in a vehicle, and no
drawing on the pictures.

In live test runs its verdict changed on 1 turnaround (Pass to Fail), where another aircraft in view was taken for
the arriving one: a problem of the shared live feed, for the stage detector to solve. The client's split puts this
check in the streaming group.

## For developers

- **Module code:** M11; client name "FOD walk completed". **Repository:** `dxgat/detectors/fod-walk-completed`;
  production `dev` @ `a30826f` (2026-04-14). `master` @ `b923b5c` (2026-01-27) is one commit behind: old arrival block
  (camera-shake filter, 60 s rule) instead of the shared arrival detector.
- **Entry point:** `main.py` → `detect(source, output_path, device, write_video, weights_dir, video_worker, ...)`;
  `find_fod_walks()` (corridor, walk test), `get_desicion()` (verdict); `onnx_thunder_inference.py` →
  `PoseEstimation.is_backside()` (MoveNet SinglePose Thunder v4, ONNX, CPU onnxruntime 1.14.1).
- **Run:** `python main.py --source <video>.mp4 --weights-dir weights [--write-video] [--json-fn <name>]`; reads
  `general_model<video>.ndjson`, `trackers<video>.ndjson` from `../inferences_dir`. Production:
  `db_worker/model_starter.py` calls `detect()`.
- **Keys:** `obstacle.width`, `obstacle.center` (the only YAML values). In code: blocked share 0.8, `distance`,
  `stay_duration` (40 frames), end tolerance 0.2, `airplane_height`, wheel height, `focal_length`, `pixel_size`, person
  ≥ 20 px, driver overlap 0.5, fallback offset 200 px, wheel path > `distance`/2. Arrival detector: `area_change_thr`,
  `prearrival_min_frames` = 90 frames.
- **Code places:** step 1 `main.py:318-354, 371-387`; 2 `:356-367`; 3 `:434-466`, `onnx_thunder_inference.py:111-121`;
  4 `main.py:469-491`; 5 `:422-430, 500-517`; 6 `:113-158`; 7 `:180-236`; 8 `:45-64, 544-548, 577-580`.
- **Dependencies:** pins `cv_common` ac5098d, `db_worker` 5a4aa83 (export adds `cv_common/modules` 2759daf, imported);
  norfair, dvc 3.4.0. Weights `weights/movenet_singlepose_thunder_4.onnx` (25 MB) by DVC (`gs://cv_weights/DVC`).
  Known cases: `scripts/specialized_issues.txt`. Logic diagram: `assets/block_diagram.svg`; Confluence, 2023-07-10.
