# Main gear chocks removed only after aircraft is attached to pushback

*In plain words: main gear chocks removed only after the pushback is attached.*

> Chocks are the wedges the ground crew puts against an aircraft's wheels so that it cannot roll. The main gear is the
> main landing gear behind the nose wheel; the software calls these wheels the rear wheels. This check asks that their
> chocks come off only after the pushback tug (the vehicle that pushes the aircraft back from the gate) is attached. The
> software finds wheels, chocks and the tug in the boxes of the General Model (the shared detector), and also compares
> pictures of each rear wheel with a reference picture taken at arrival, using a model the team trained. The same module
> also gives two other checks of the client: *Nose gear chocks applied immediately* and *Nose wheel chock removed from
> aircraft*.

## Status

| | |
|---|---|
| How accurate it is | 61 of 68 turnarounds correct (90 %) on the monthly test |
| Fail turnarounds it caught | 15 of 19 |
| In production | the version of January 2026 |
| Who looks after it | to assign |
| Biggest open problem | The code waits for the tug to be attached and for the belt loaders to leave; the rule asks only for the attachment, so chocks removed after the attachment while a belt loader is still there can give Fail instead of Pass. |

## What the client wants

A verdict is the answer of a check: Pass, Fail or Not observed.

| Verdict | When |
|---|---|
| Pass | The main gear chocks were removed only after the aircraft was attached to the tug. |
| Fail | The main gear chocks were removed before the aircraft was attached to the tug. |
| Not observed | The aircraft or its rear wheels were not detected, or something stood in the way. |
| Not observed, view blocked | All frames were blocked. |

The client's sheet marks this check as not yet ready for production and puts it in its real-time group (checks wanted
while the turnaround happens).

## When and where it looks

The module works between two moments given by the tracker: the arrival, marked once the aircraft has stood still for
about 4 seconds, and the departure, marked after about 10 seconds of movement. For this check it uses the first 10
seconds after arrival to pick the rear wheels and take their reference pictures; then it watches until the tug is
attached and the belt loaders have left, and 10 seconds more. The stages are the arrival and the time before departure.
It runs on the cone camera (the camera that looks towards the aircraft nose) for aircraft and jets. The code does not
check which camera filmed the video.

## What it looks at

- **From the General Model:** rear wheels, chocks (from a separate chock detector), the aircraft nose, the tug and other
  vehicles; as things in the way, cones, trailers, fuel trucks, ladders and objects labelled "obstacle". A detection is
  a box the detector draws around an object.
- **From the tracker:** the aircraft track (the same object followed from frame to frame): arrival, departure and
  whether it moves. People and service vehicles (ground support equipment: tugs, belt loaders, fuel trucks, tractors)
  as things in front of a rear wheel. Belt loaders, and whether the tracker marks one as standing at a cargo door.
- **From the video itself:** yes, the pictures of the rear wheels on every frame from arrival to departure.
- **Own model:** an image classifier the team trained. It compares a picture of a rear wheel with the wheel's reference
  picture and says whether a chock is there.
- It runs on ordinary processors in production; the code can use a graphics card.

## How it decides, step by step

1. **Reading ahead for the tug.** Before the real work the module reads the General Model's boxes up to the departure
   (or the end of the video) and keeps the biggest pushback box of each frame. The middle position (median) of the boxes
   seen from 120 to 60 seconds before the departure is the tug's final position, where it stood while attached. This
   needs boxes on more than 1 second of frames in that minute; otherwise there is no final position.
2. **Tug attached.** On each frame, a pushback box that overlaps the final position by more than 80 % (shared area
   divided by the area both boxes cover) adds one to a counter; a frame without one takes one off. Past 5 seconds of
   frames, the tug is attached. Without a final position, a tug next to the nose and less than 0.3 aircraft heights
   below the aircraft counts instead; this backup counter never goes down.
3. **Safety zone.** The area around the aircraft is "busy" when, for more than 2 seconds, a belt loader stands at a cargo
   door or, while the aircraft is not moving, a vehicle stands right behind a rear wheel. It is "clear" again after more
   than 5 seconds without one.
4. **Picking the wheels.** For 10 seconds after arrival the module collects rear wheel boxes, then merges boxes of the
   same wheel, keeps the two biggest and names them right and left (a single wheel is named by its side of the nose
   wheel). For each, the 8 clearest and steadiest frames are averaged into a reference picture.
5. **Chocked before the event.** A rear wheel is "confirmed chocked" when a chock box sits in the zone under it for 4
   seconds in a row, or when the classifier finds a chock, comparing a steady view of the wheel (1 second of frames
   averaged, the picture unchanged for 2 seconds) with the reference. The classifier is asked at most once every 10
   seconds per wheel.
6. **The event** is the later of two moments: the tug attached and the safety zone clear. If a belt loader comes back,
   the event is cancelled and set again when the zone clears. Within 10 seconds after the event the module looks for
   the chock once more (4 seconds of chock boxes, or the classifier on the 8 best frames):
   - chock still there, so it can only come off after the event: **Pass** for this wheel;
   - chock gone, so it came off too early: **Fail**, but only for a wheel confirmed chocked before; otherwise **Not
     observed** ("never confirmed placed");
   - **Not observed** when the wheel is within 10 pixels of the picture's edge, when its box has an unusual shape
     (width under 0.9 or over 1.4 times its height), or when a person or a vehicle stands in front of it (a vehicle
     must cover more than 15 % of the zone under the wheel, a cone 35 %).
7. **Verdict:** any wheel Fail gives Fail; otherwise any wheel Pass gives Pass; otherwise Not observed.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Chock boxes in a row that confirm a rear wheel chock | 4 seconds | Fewer: not confirmed |
| Time after arrival to pick rear wheels and take reference pictures | 10 seconds | Wheels seen later are not checked |
| Time after the event in which the rear wheel chock must still be found | 10 seconds | Pass or Fail per rear wheel |
| Frames averaged into one wheel view | 1 second | Steadiness of the compared picture |
| Steadiness before a comparison | unchanged for 2 seconds, similarity at least 0.997 | No comparison while the view changes |
| Shortest time between two comparisons of a wheel | 10 seconds | How often the classifier is asked |
| Safety zone busy / clear | more than 2 seconds with a loader / more than 5 seconds without | Moves the event |
| Rear wheel box shape; distance from the edge | width 0.9 to 1.4 times the height; 10 pixels | Outside: Not observed |
| Share of the zone under a rear wheel that blocks it | vehicle 15 %, cone 35 % | Above: Not observed |
| Tug rules (in the code) | final position from 120 to 60 seconds before departure; overlap over 80 %; 5 seconds net | When the tug counts as attached |

Several values in the settings file are not used: the tow bar sizes, two obstacle overlap limits and a picture
difference limit whose check is switched off. Two others only show a message on the annotated video.

## What it reports

- One line per rear wheel, for example "Rear right wheel chocks removed after pushback attached and safety zone cleared
  (time)." or "Rear left wheel chocks were removed prematurely, before pushback attached and safety zone cleared
  (time)."; Not observed lines such as "… wheel chocks never confirmed placed." or "Aircraft wheels were not properly
  visible at arrival."
- A timeline entry (the stretch of video the website marks) per wheel from 5 seconds before to 10 seconds after the
  event; for Not observed, from 5 seconds before to 60 seconds after the wheel was first seen. Start and end are stored
  as numbers.
- Files: a drawing file with the boxes and texts; an annotated video and the classifier's input pictures only when a
  developer switches them on.

## How accurate it is

The monthly test is the set of the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this
check. The module was right on 61 (90 %). 19 turnarounds were labelled Fail and the module caught 15; 4 violations were
missed and 3 more wrong verdicts were on turnarounds labelled Pass or Not observed. Of the three wheel chock checks, only
this one has enough Fail labels to show how well it catches violations. Our sources do not say which turnarounds were
wrong, or why.

## Known problems

- **It waits for more than the rule.** The code waits for the tug to be attached and for the belt loaders to leave. The
  rule only asks for the attachment. Chocks removed after the attachment while a loader is still there can give Fail
  instead of Pass.
- **The tug can be confused.** Obstacles can spoil the attachment test, or another tug or vehicle can be taken for it
  (known from the team's notes on the module). The backup test next to the nose never counts down, so short false
  sightings add up.
- **Exact frames.** The module starts on the exact frame the tracker marks as the arrival and stops on the exact
  departure frame; if such a frame is missing from the data, it never starts or never stops.
- **Memory:** up to 194 full pictures are held per rear wheel.
- **Not ready for production:** the client's sheet marks this check as not ready.
- **Who confirms:** changes that would change a verdict the client sees are decided with the client's safety team.

## In real time

Not as it is. The module reads the whole turnaround first to find the tug's final position and needs the length of the
video; in real time the earlier frames are gone. The team rates it "needs a small patch": take the moments "pushback
attached", arrival and departure from the stage detector (the part that knows where in the turnaround we are), read
pictures only when needed, and keep small cut-outs of the wheels instead of full pictures. A test version fed with a
live "pushback attached" moment gave the same verdicts for this check as post-processing (after the turnaround) on 8
videos.

Cost on the team's test machine, one 36-minute turnaround: the reading-ahead pass alone, with its share of the General
Model and the tracker, needs 46.1 milliseconds of the 125 milliseconds each frame may take at 8 frames per second
(37 %). As a post-processing job the module takes 38 seconds, 84 seconds of processor work and at most 1.9 gigabytes of
memory.

## For developers

- **Module code in our workspace:** M02B. Task key in the monthly report: `aircraftchockback`.
- **Repository:** `dxgat/detectors/aircraft-chocks`; production line `master` @ `fa00478` (2026-01-30). The module
  returns three lists (verdicts, reports, timelines) in the order M02A, M02B, M02C.
- **Code:** first pass `main.py:1240-1286`; pushback attached `:1523-1549`; safety zone `:1561-1612`; rear wheel pick
  `:1659-1680`; observability `:281-389`; chock detection `:392-443`; image comparison `:446-865`; M02B verdict
  `:33-79`. `RearWheelChocksAnalyzer` (observability, chock detection, image comparison), `get_main_gear_report`;
  `complex_difference.py` builds the classifier input, `simple_difference.py` tests that the view is steady.
- **Settings keys:** `min_chock_frames` 32; `stop_capture_window` 80; `main_capture_window`, `main_check_timeframe` 80;
  `frame_average_window` 8, `static_env_window` 16, `static_env_threshold` 0.997; `differentiation_timeout` 80;
  `beltloader_in_thres` 16, `beltloader_out_thres` 40; `min_max_width_ratio` [0.9, 1.4], `edge_distance` 10;
  `diff_obstacle_min_iou` 0.15, `diff_cone_obs_min_iou` 0.35; rear wheel box median `bbox_window` 24. Pushback window
  `deque(maxlen=120*fps)`, first half, > 8 boxes, IoU 0.8, > 40 frames; nose fallback 0.3 aircraft heights.
- **Weights in DVC:** `effnetb0_ext_fix_993.pt` (EfficientNet-B0 chock classifier). Dependencies: `cv_common` ac5098d,
  `db_worker` 5a4aa83; timm, torch, torchvision, norfair; Docker base `cpu_base`.
- **Real time:** verdict PATCH in `docs/04_modules.md` (`main_stream.py`, 3 hunks: 0 M02B differences on 8 videos);
  group B in `docs/analysis/rt_module_selection.md` (5.7 ms per recorded frame); first pass only in
  `docs/analysis/rt_module_cost.md`.
- **Sources:** `docs/modules/aircraft-chocks.md`, `docs/analysis/module_review_2026-10.md`, `docs/05_module_logic.md`.
