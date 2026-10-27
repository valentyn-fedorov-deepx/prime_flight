# Motorized service vehicles parked and chocked

> Service vehicles (ground support equipment: tugs, belt loaders, fuel trucks, tractors) park at the aircraft, and a
> motorized one must then have chocks at its wheels. For every stop of every service vehicle the check looks for proof:
> a chock seen at the wheels, a worker bending down at the vehicle, or a change at the wheels that our own image
> classifier recognises as a chock. One stop without chocks makes the turnaround Fail.

## Status

| | |
|---|---|
| How accurate it is | 55 of 68 turnarounds correct (81 %) on the monthly test |
| Fail turnarounds it caught | 18 of 22 |
| In production | the version of May 2026 |
| Who looks after it | to assign |
| Biggest open problem | It judges every service vehicle that parks anywhere in view, not only at the aircraft, and the client's rule has no written Fail case. |

## What the client wants

*Motorized GSE parked and properly chocked* (GSE: ground support equipment, the service vehicles)

| Verdict | When |
|---|---|
| Pass | The vehicle counts as parked and one of these holds: a chock is seen in the wheel zone; a worker is seen bending down, for a vehicle facing the camera; comparing pictures from different moments of the stop shows chocks. |
| Fail | Left empty in the client's sheet. The module gives Fail when any judged stop is found not chocked. |
| Not observed | The vehicle is too far (its box is lower than a minimum height), partly outside the picture, not parked long enough, or a person stays on it too long (a driver on board). |
| Not observed, view blocked | When the vehicle's direction is used: obstacles cover more than 75 % of the wheel zone. When pictures are compared: the scene is not still, or something stands in front. |

A verdict is the answer of a check: Pass, Fail or Not observed.

## When and where it looks

The client lists the check for unloading and loading (a stage is a part of the turnaround), but the module waits for no
stage and ignores the aircraft: it reads the whole video and judges each stop of each service vehicle, from the stop to
the drive-away or the end of the video. Cameras: for aircraft the cone camera (looks towards the aircraft nose) and the
wing camera (looks along the wing); for jets the wing camera only.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object): chocks, as evidence;
  pushback tugs, trailers, fuel trucks, cones and ladders, as things that may stand in front of the wheels.
- **From the tracker** (a track is the same object followed from frame to frame; a frame is one picture, 8 per second):
  service vehicles, with the tracker's standing and moving counters and the points it follows on each vehicle; people;
  belt loaders, as possible obstacles. Belt loaders, pushback tugs, trailers and fuel trucks have General Model classes
  of their own and are not judged here.
- **From the video itself:** yes, for the pose model and the picture comparison.
- **Its own models:** a **body pose model** (standard, not trained by us) finds 17 points of a person — nose, eyes,
  ears, shoulders, elbows, wrists, hips, knees, ankles — and shows a worker bending down, the movement of placing a
  chock. A **chock classifier** (trained by us) gets the wheel area at two moments of the same stop, and their
  difference, and answers "a chock appeared" or not.

## How it decides, step by step

1. **Stops.** The tracker says when a vehicle is stopping or stopped (still for 3 seconds); it has driven away after 6
   frames (0.75 seconds) of motion. Each stop is judged on its own.
2. **Direction.** From the last clear movement before the stop — sideways travel against growth in size as the vehicle
   comes closer — the direction is fixed at the stop: side-on (ratio above 40), face-on (below 8) or at an angle.
3. **Can the stop be judged?** Not while the box is lower than 120 pixels (too far), is cut by the picture edge or has
   unusual proportions, the vehicle has been parked less than 20 seconds, or a person has been on top for more than 60 %
   of the stop. Such a stop cannot give "not chocked". The box is smoothed over the last 3 seconds.
4. **Chock seen.** The wheel zone is the lowest 20 % of the box plus a margin of 5 % of its height. A General Model chock
   centred in it for 40 frames (5 seconds) in a row: chocked.
5. **Worker bending.** The pose model runs on each person at the bottom of the vehicle (people on board are left out).
   If the person's height, nose to lowest point, drops below 65 % of its maximum within 1 second, that is a bend:
   chocked. Uncertain poses (average score under 0.3) and walking people are ignored. At an angle, for a worker who
   leans, vanishes for 2–3 seconds behind the vehicle and reappears leaning, a drop to 91 % already counts, if both poses
   score 0.68 or more. Face-on only: zones beside the vehicle clear for 30 seconds with no bend mean "not chocked".
6. **Picture comparison.** Right after the stop, 4 to 8 frames are averaged into a "just stopped" picture, if the scene
   stays still with nothing in front. Every 10 seconds of full stop, after 3 still seconds, the classifier compares the
   wheel strip (bottom of the box) of that picture with an average of the current frames; a match score below 0.8 gives
   no answer; at most 6 checks per stop. "Chock" counts only if background objects stayed in place. If no check said
   "chocked", the picture just before the drive-away is compared with the saved ones, so chocks removed before leaving
   count too.
7. **Combining.** Any positive evidence means chocked, except: face-on — "no bend" gives not chocked unless step 4 or 6
   said chocked; side-on or unknown direction — once step 6 has an answer, step 4 is ignored; a box touching two picture
   edges cannot pass on step 6 alone. The result is recorded at the drive-away or the end of the video.
8. **Verdict.** A vehicle once found not chocked stays so. Any such vehicle gives Fail; otherwise any chocked vehicle
   gives Pass; otherwise Not observed.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Chock in the wheel zone | 40 frames (5 seconds) in a row | Chock proof |
| Shortest parking | 160 frames (20 seconds) | Shorter stops are not judged |
| Smallest vehicle | 120 pixels high | Smaller boxes are too far |
| Person on board | 60 % of the stop | Marks a driver on board |
| Bend | below 65 % within 8 frames (1 second) | Bend proof |
| Weaker bend | 91 % | "Lean, hide, reappear", vehicles at an angle |
| Clear view before "no bend" | 240 frames (30 seconds) | Face-on vehicles only |
| Picture checks | every 80 frames (10 seconds), at most 6 | Checks per stop |
| Comparable pictures | match score 0.8 | Below it: no answer |
| Direction | 40 and 8 | Side-on and face-on limits |

## What it reports

- **Sentence:** one line per judged stop, in time order: the vehicle's number, "was chocked" or "was not chocked", and
  the stop's time widened by 1 second on each side. Not observed: no service vehicle was seen, or none was parked or
  their chocks stayed unclear.
- **Timeline entry:** one Pass or Fail block per judged stop, from the stop to the drive-away or the end of the video.
- **Files:** a drawing file for every frame; an annotated video on request.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this check. The
module matched the client on 55 (81 %). Of the 22 labelled Fail it caught 18, so 4 of its 13 errors are missed
violations; the other 9 are turnarounds labelled Pass or Not observed. Which problem caused which error: not known
yet. The client's sheet marks this check as not production-ready.

## Known problems

- **The aircraft is not used.** Every stop in view counts, near the aircraft or not (the description says "near the
  aircraft"): an unchocked vehicle parked away from the aircraft can fail the turnaround.
- **No Fail rule from the client:** the Fail column is empty; the Fail rule is the module's own.
- **Bending counts for every direction**, not only face-on as in the client's rule (only "no bend" is face-on only), so
  a bend can pass a stop the rule would not.
- **Side-on vehicles:** a chock seen by the General Model can be overruled by the classifier's "no chock": Fail.
- **One bad stop decides the vehicle**, even if its later stops are chocked.
- **No blocked-view verdict.** The client's 75 % figure is not in the code; obstacles only stop one piece of evidence.
- **Heavy picture work:** pose per person and vehicle; up to 24 + 8 full frames kept per stopped vehicle, not released
  when it leaves.
- **Tracker internals:** it reads the tracker's internal motion counters, so a tracker change can shift stops.
- **To confirm:** the pose model gets its colour channels in reverse order (effect not known yet); whether production
  runs on a processor or a graphics card.

## In real time

It runs unchanged but needs the pictures. Each stop's result is known at the drive-away, but the verdict comes only
when the recording ends; an alert during the turnaround needs an interim verdict. In the real-time test setup, on a
36-minute turnaround, it matched post-processing (Not observed).

Own work: about 3.3 milliseconds per frame (4.5 with all checks together); with the shared General Model and tracker
parts, 43.6 of the 125 milliseconds each frame may take (35 %), on a faster graphics card than production's. As a
post-processing job: about 76 seconds. Lighter with the same results: read each picture once and only while a vehicle
stands still, keep cut-outs instead of whole pictures, compute each check picture once.

## For developers

- **Repository:** `dxgat/detectors/gse-chocks`; production `per_component_improvement` @ `d3f92a5` (2026-05-29; logic
  `426526b`, 2026-03-24); default `master` @ `3160b87` (2025-06-19, branch point: no tilt logic, no frame-edge veto,
  bend threshold 0.62, angled treated as side-on). Workspace module code: M12.
- **Entry point:** `main.py` → `detect(...)`; `GSEChocksAnalyzer` (orientation, observability, chock, human-action and
  difference parts), verdict and report in `get_gse_report`.
- **Models, dependencies:** EfficientNet-B0 chock classifier `effnetb0_small_clean_64_960.pt` (ours), RTMPose-l
  `rtmpose-l-4dba18fc.onnx`, DVC; `cv_common` @ `dd5b554`, `db_worker` @ `5a4aa83` (exported copy); image
  `cpu_base`, `--device cpu` by default.
- **Run:** `python main.py --source <video.mp4> --inferences-dir <dir> --weights-dir weights [--cone-camera]
  [--write-video] [--debug-all]`; settings in `local_config.yaml`.
- **Settings keys** (table order): `min_chock_frames`, `min_park_duration`, `min_observed_height`,
  `min_person_stay_ratio`, `bend_ratio_threshold` + `bend_window`, `weaker_bend_ratio_threshold`,
  `min_action_clear_frames`, `differentiation_timeout` + `max_checks_number`, `not_observed_diff_threshold`,
  `profile_threshold` + `frontal_threshold`.
- **Code places:** step 1 `main.py:1750-1781`; 2 `main.py:236-408`; 3 `main.py:444-583`; 4 `main.py:593-642`; 5
  `main.py:659-927`; 6 `main.py:1046-1489`, `complex_difference.py:140-147`, `simple_difference.py:40-51`; 7
  `main.py:1563-1594`; 8 `main.py:32-76, 1937-1947`.
