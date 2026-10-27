# Pushback driver checks the steering bypass pin

> The steering bypass pin is put into the nose wheel after the aircraft arrives (see the page *Steering bypass pin
> installed*). Before the pushback, the pushback driver must check that it is there. The module looks for workers next
> to the nose wheel once the pushback tug is attached, and uses a pose model to see whether one of them bends or crouches
> there, or stands still there with a hand raised.

## Status

| | |
|---|---|
| How accurate it is | 42 of 55 turnarounds correct (76 %) on the monthly test |
| Fail turnarounds it caught | 9 of 12 |
| In production | the version of June 2025 |
| Who looks after it | to assign |
| Biggest open problem | It needs 1.5 seconds of bending or 2.5 seconds of standing with a raised hand, while the client asks for 0.5 seconds of bending or 3 seconds of standing. |

## What the client wants

*Pushback operator verifies steering bypass pin installation*

| Verdict | When |
|---|---|
| Pass | A worker bends near the front (nose) wheel for 0.5 seconds, or stands there for 3 seconds or more (either counts as checking the pin), while the pushback tug is in the video. |
| Fail | The aircraft was found, then the pushback tug, and the front wheel was detected, but no pin check was seen. |
| Not observed | The aircraft, the pushback tug or the front wheel was not seen. |
| Not observed, view blocked | Something blocked the view for 2 minutes in total after the pushback tug was first detected. |

A verdict is the answer of a check: Pass, Fail or Not observed.

## When and where it looks

The check belongs to the stage before departure (a stage is a part of the turnaround). The module looks from the moment
the pushback tug counts as attached until 10 seconds before the tracker's departure moment (set after about 10 seconds
of movement), and only while the aircraft stands still. It uses the cone camera (which looks towards the aircraft nose),
for aircraft only: the client does not run it for jets. The code does not check the camera.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object on a frame, one
  picture of the video, 8 per second): the pushback tug, the aircraft nose and the front wheel. As view blockers: large
  belt loaders, service vehicles (ground support equipment: tugs, belt loaders, fuel trucks, tractors), trailers,
  vehicles, and "obstacle" or "side obstacle" boxes.
- **From the tracker:** the aircraft track (the aircraft followed from frame to frame: stopped or moving, and the
  tracker's arrival and departure moments) and the people tracks.
- **From the video itself:** yes, the pose model reads the pictures of the workers near the wheel.
- **Own models:** none trained by us. A ready-made pose model finds each worker's joints (face points, shoulders,
  elbows, wrists, hips, knees, ankles). It needs a graphics card.

## How it decides, step by step

1. **First pass.** The module first reads the tracks up to the frame where the tracker reports the departure (or the
   end of the video). From the biggest pushback tug box of each frame it takes the typical (median)
   position between 120 and 60 seconds before that frame: the tug's parked position.
2. **Second pass.** It reads the video again, working only between the tracker's arrival and departure.
3. **Nose wheel.** It takes the largest front-wheel box taller than 40 pixels and more than 80 % inside the slightly
   enlarged aircraft box, then follows it and smooths its position over up to 60 seconds. The *wheel zone* runs from one
   wheel width left of the wheel's centre to 1.5 widths right of it, and from the centre down to one wheel height below.
4. **Tug attached.** A tug box that nearly coincides with the parked position (shared area above 80 % of the combined
   area) adds one to a counter; other frames take one off. Without a parked position, a tug touching the nose counts.
   Above 80 frames (10 seconds) the tug is attached and the provisional verdict becomes Fail.
5. **Blocked view.** Large boxes (wider than 500 and taller than 400 pixels) of the blocking classes, other than the tug,
   covering more than 75 % of the wheel zone make the frame blocked; blocked frames are counted and skipped.
6. **Workers.** After attachment, while the tracker says "stopped" and outside the last 10 seconds before the departure
   found in step 1 (when the chocks are taken away): a person is near the wheel when the lowest 10 % of the box lies
   more than half in the wheel zone and the person is at most 5 wheel heights tall (people right in front of the camera
   are skipped). The pose model runs on these workers.
7. **Action.** For each worker, one counter grows on frames showing bending (a wrist below its hip, the body bent to 150
   degrees or less at the hips) or crouching (a knee bent below 120 degrees); another grows on frames showing the worker
   upright (above 150 degrees) with a wrist at or above head height and the ankles moving 5 pixels or less. A frame
   without the posture takes 5 off that counter. Joints with a confidence below 0.2 are not trusted. 12 frames (1.5
   seconds) of bending or crouching, or 20 frames (2.5 seconds) of standing: **Pass**; processing stops 10 seconds
   later.
8. **Without a Pass**, in this order: blocked for 120 seconds or more: **Not observed**; wheel unseen for more than 60
   seconds after attachment: **Not observed**; tug covering more than 10 % of the wheel (average boxes): **Not
   observed**; tug never attached: **Not observed**; no departure: **Not observed**; otherwise **Fail**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Smallest blocking box | 500 × 400 pixels | Blocked frames |
| Parked-position window | 120 to 60 seconds before the departure | Reference for "attached" |
| Attachment | shared area above 80 %; counter above 10 seconds | When the check starts |
| Bend and stand time | 1.5 seconds and 2.5 seconds | Pass |
| Joint confidence | 0.2 | Which joints are trusted |
| Blocked limit | 120 seconds | Not observed |
| Hidden-wheel limit | 60 seconds after attachment | Not observed |
| No-check time | last 10 seconds before the departure | Chock removal ignored |

Only the blocking-box size is in the settings file (the rest is in the code); two values there are unused.

## What it reports

- **Sentence.** Pass: "Pin installation was verified by <worker number>. (<time> - <time>)". Fail: "Pin installation
  wasn`t verified (<time> - <time>)". Not observed: "There was an obstacle for more than 2 minutes", "Front wheel wasn`t
  detected for 1 minute after pushback appeared", "Front wheel was partially obscured by pushback", "Pushback attachment
  was not observed" (also when no aircraft was found) or "Plane departure was not observed, could not verify pin
  installation".
- **Timeline entry:** Pass, 6.25 seconds either side of the moment; Fail, from the attachment to the departure; none for
  Not observed.
- **Files:** per-frame drawings (aircraft state, nose, wheel and wheel zone, tug, workers with their flags, joints,
  status lines); an annotated video with pose skeletons if switched on.

## How accurate it is

The monthly test (the client's validated turnarounds we measure on) has 69 turnarounds; 55 were labelled for this check
and the module matched 42 (76 %). Of the 12 labelled Fail it caught 9: 3 of its 13 errors are missed violations, the
other 10 are turnarounds labelled Pass or Not observed where it said something else. Which ones, and why, is not in our
sources.

## Known problems

- **Stricter timing than the client.** The code needs 1.5 seconds of bending or 2.5 seconds of standing; the client
  (and the module's own description) say 0.5 and 3 seconds. Standing also needs a raised hand. Short bends that the
  client accepts give Fail; standing without a raised hand never counts.
- **An action, not the pin.** It measures a pin-check-like action at the wheel, not the pin itself. In substance it is
  close to *Steering bypass pin installed*; to cross-check.
- **Reads ahead.** The first pass uses the future (parked position, departure, video length).
- **Attachment rule.** Marked "to review and rework" in the code; it takes the first tug box of the frame, while the
  first pass takes the biggest.
- **Blocked time from the wrong moment.** The client counts from the first tug detection; the code counts from when the
  wheel zone exists (after arrival) and skips blocked frames (the code itself asks whether this is harmful).
- **Only while stopped.** Workers are checked only while the tracker says the aircraft is stopped.
- **Fixed machine settings.** The graphics card and the model file location are fixed in the code; their options are
  ignored. Several workers passing on one frame add several Pass entries.

## In real time

The client puts this check in the "streaming" group: wanted during the turnaround, but seconds do not matter. It needs
a small change first: it reads the recording twice, and in real time past frames are gone. The parked tug position, the
departure and the video length should come from the stage detector (the part that knows where in the turnaround we are)
as a shared "pushback attached" event and the departure moment, as planned for the aircraft chocks check too. It should
also log four aircraft values, not the whole aircraft state, on every frame. Its first pass costs 22.7 of the 125
milliseconds a frame may take (18 %) with the General Model and the tracker; as a post-processing job it takes 27
seconds per turnaround.

When all pose checks were tried with one shared, faster pose model, this check went from 35 to 36 correct of 46
turnarounds in our validation run: four verdicts changed (two towards the label, one away, one between two wrong
verdicts). Its own pose model is already light, so the gain is small: pose time fell from 284 to 167 seconds over the
run, but the whole module took 4 % longer.

## For developers

- **Module code:** M16. **Repository:** `dxgat/detectors/pin-verification`; production `master` @ `8e1863c`
  (2025-06-19), the default branch.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, weights_dir, cone_camera,
  json_logger)`; `Plane` (nose, wheel, wheel zone), `Wheel`, `Worker` (pose rules), `get_front_wheel_bbox`,
  `find_pushback`; `Pushback` and `pushback_ROI` unused. Logic diagram (Confluence):
  https://docs.google.com/spreadsheets/d/1SJpA9JmgyA2WEeERvQBNmtl4YPZc1VDCK2YGWV9OIRc/edit?gid=333438026
- **Run:** `python main.py --source <video>.mp4 [--local-inferences --inferences-dir <dir>] [--write-video]
  [--save-csv]`; needs CUDA (`cuda:0`, `weights/` hard-coded; `--device`, `--weights-dir` ignored).
- **Keys:** `obstacle_width` 500, `obstacle_height` 400. In code: window `120*fps` (older half), IoU 0.8, counter
  `10*fps`, `fps*1.5`, `fps*2.5`, `_conf_threshold` 0.2, `120*fps`, `60*fps`, `10*fps`. Unused: `obstacle_center_range`,
  `airplane_moving_thresh`.
- **Code places:** first pass `main.py:504-549`; arrival and departure `:633-645, 733-738`; wheel `:83-89, 435-457,
  647-650`; attachment `:466-477, 662-684`; wheel state `:693-706`; blocked view `:627-631, 708-729`; no-check time
  `:762-766`; workers and pose `:769-855`; action rules `:236-320`; Pass `:857-868, 604-612`; final verdict `:893-929`.
- **Dependencies:** `cv_common` dd5b554 (local folder: ac5098d), `db_worker` 6efc0b0; mmpose 1.3.1, mmcv 2.1.0, mmdet
  3.2.0, mmengine 0.10.4; DVC (178 MB) `simcc_res50_8xb32-140e_coco-384x288-45c3ba34_20220913.pth` (SimCC ResNet-50).
  First pass copied from aircraft-chocks; shared pose model RTMPose-l (`pose_unification.md` §8).
