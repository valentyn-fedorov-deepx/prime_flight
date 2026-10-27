# Aircraft wheel chocks: placed on arrival, removed only after the pushback is attached

> Chocks are the wedges the ground crew puts against an aircraft's wheels so that it cannot roll. One module serves
> three of the client's checks: the nose wheel is chocked within 30 seconds of the aircraft's arrival, and the chocks
> come off the main wheels and the nose wheel only after the pushback tug (the vehicle that pushes the aircraft back from
> the gate) is attached. The software finds wheels, chocks and the tug in the boxes of the General Model (the shared
> detector); for the main wheels it also compares pictures of each wheel with a reference picture taken at arrival,
> using a model the team trained.

## Status

| | |
|---|---|
| How accurate it is: nose wheel chock placed right after arrival | 62 of 68 turnarounds correct (91 %) on the monthly test |
| How accurate it is: main gear chocks removed only after the pushback is attached | 61 of 68 turnarounds correct (90 %) on the monthly test |
| How accurate it is: nose wheel chock removed only after the pushback is attached | 60 of 68 turnarounds correct (88 %) on the monthly test |
| Fail turnarounds it caught: nose wheel chock placed right after arrival | 1 of 1 |
| Fail turnarounds it caught: main gear chocks removed only after the pushback is attached | 15 of 19 |
| Fail turnarounds it caught: nose wheel chock removed only after the pushback is attached | 0 of 1 |
| In production | the version of January 2026 |
| Who looks after it | to assign |
| Biggest open problem | The nose wheel removal check never sees a removal: it passes when the chock is still there after the tug is attached, and the client's Fail for a video that ends before the removal is missing. |

## What the client wants

A verdict is the answer of a check: Pass, Fail or Not observed. "Arrival" is the moment the aircraft has stopped at the
gate. The main gear is the main landing gear behind the nose wheel; the software calls these wheels the rear wheels.

**Nose wheel chock placed right after arrival.** The client calls this check *Nose gear chocks applied immediately*.

| Verdict | When |
|---|---|
| Pass | The nose wheel was chocked within the first 30 seconds after arrival. |
| Fail | The nose wheel was seen, but not chocked within the first 30 seconds. |
| Not observed | The aircraft or the nose wheel was not seen, or there was no arrival stage, or something stood in the way. |
| Not observed, view blocked | All the frames of the arrival were blocked. |

A stage is a part of the turnaround; "no arrival stage" means the video does not show the aircraft driving in. A frame
is one picture of the video; the cameras take 8 per second.

**Main gear chocks removed only after the pushback is attached.** The client calls it *Main gear chocks removed only
after aircraft is attached to pushback*.

| Verdict | When |
|---|---|
| Pass | The main gear chocks were removed only after the aircraft was attached to the tug. |
| Fail | The main gear chocks were removed before the aircraft was attached to the tug. |
| Not observed | The aircraft or its rear wheels were not detected, or something stood in the way. |
| Not observed, view blocked | All frames were blocked. |

**Nose wheel chock removed only after the pushback is attached.** The client calls it *Nose wheel chock removed from
aircraft* and places it in the departure stage, when the tow bar is disconnected.

| Verdict | When |
|---|---|
| Pass | The nose wheel chocks were removed only after the aircraft was attached to the tug. |
| Fail | The nose wheel chocks were removed before the attachment, or the video stops before the removal can be seen. |
| Not observed | The aircraft or the nose wheel was not detected, or something stood in the way. |
| Not observed, view blocked | All frames were blocked. |

The client's sheet marks the two nose wheel checks as ready for production and the main gear check as not ready. All
three are in the client's real-time group (checks wanted while the turnaround happens).

## When and where it looks

The module works between two moments given by the tracker: the arrival, marked once the aircraft has stood still for
about 4 seconds, and the departure, marked after about 10 seconds of movement. Inside that time:

- **Nose wheel placed:** the first 30 seconds after the tracker's arrival moment, in practice from about 4 to about 34
  seconds after the aircraft stopped.
- **Main gear:** the first 10 seconds after arrival, to pick the rear wheels and take their reference pictures; then
  until the tug is attached and the belt loaders have left, and 10 seconds more.
- **Nose wheel removed:** from the tug's attachment until the departure.

The stages are the arrival, the time before departure, and the departure with the pushback. Before the main work the
module reads ahead to the departure (step 1). It runs on the cone camera (the camera that looks towards the aircraft
nose) for both aircraft types the client distinguishes, aircraft and jets. The code does not check which camera filmed
the video.

## What it looks at

- **From the General Model:** nose wheels, rear wheels, chocks (from a separate chock detector), the aircraft nose, the
  tug and other vehicles; as things in the way, cones, trailers, fuel trucks, ladders and objects labelled "obstacle".
  A detection is a box the detector draws around an object.
- **From the tracker:** the aircraft track (a track is the same object followed from frame to frame): arrival and
  departure, whether it moves, and the points the tracker follows on it. People and service vehicles (ground support
  equipment: tugs, belt loaders, fuel trucks, tractors) as things in front of a rear wheel. Belt loaders, and whether
  the tracker marks one as standing at a cargo door.
- **From the video itself:** yes, the pictures of the rear wheels on every frame from arrival to departure.
- **Own model:** an image classifier the team trained. It compares a picture of a rear wheel with the wheel's reference
  picture and says whether a chock is there.
- It runs on ordinary processors in production; the code can use a graphics card.

## How it decides, step by step

**Shared steps**

1. **Reading ahead for the tug.** Before the real work the module reads the General Model's boxes up to the departure
   (or the end of the video) and keeps the biggest pushback box of each frame. The middle position (median) of the boxes
   seen from 120 to 60 seconds before the departure is the tug's final position, where it stood while attached. This
   needs boxes on more than 1 second of frames in that minute; otherwise there is no final position.
2. **Arrival and departure.** The main pass runs from the tracker's arrival moment to its departure moment. There is an
   arrival stage if, before stopping, the aircraft moved smoothly for more than 3 seconds in a row: the points on it
   moved on average by at most 50 pixels sideways and 5 pixels up or down from frame to frame.
3. **Tug attached.** On each frame, a pushback box that overlaps the final position by more than 80 % (shared area
   divided by the area both boxes cover) adds one to a counter; a frame without one takes one off. Past 5 seconds of
   frames, the tug is attached. Without a final position, a tug next to the nose and less than 0.3 aircraft heights
   below the aircraft counts instead; this backup counter never goes down.
4. **Safety zone.** The area around the aircraft is "busy" when, for more than 2 seconds, a belt loader stands at a cargo
   door or, while the aircraft is not moving, a vehicle stands right behind a rear wheel. It is "clear" again after more
   than 5 seconds without one.

**Nose wheel chock placed right after arrival**

5. The nose wheel is the largest nose wheel box overlapping the aircraft. It is chocked on a frame when a chock box
   touches the lower 40 % of the wheel box (slightly enlarged). When the wheel is not found, its last box is used.
6. **Pass** as soon as the wheel is chocked on more than 1 second of frames, with gaps under 2 seconds, within 30
   seconds after arrival.
7. At 30 seconds without that: **Fail**, or **Not observed** if something covered the wheel on 10 seconds of frames or
   more. Also Not observed when the nose wheel was never found; when it was not yet found at some moment of the first 35
   seconds and no chock was confirmed; when there was no arrival stage (checked before Pass, so a chocked wheel then
   also gives Not observed); or when the video ended before the 30 seconds were over.

**Nose wheel chock removed only after the pushback is attached**

8. After the attachment: if the nose chock is still seen (for more than 3 seconds, gaps under 2 seconds), it counts as
   removed after the attachment: **Pass**. If it has been missing for more than 5 seconds while nothing covered the
   wheel, and is not seen again before the departure: **Fail**. **Not observed** when the tug's final position covers
   more than half of where the nose wheel stood before the attachment, when the tug is never attached, or when the nose
   wheel was never found.

**Main gear chocks removed only after the pushback is attached**

9. **Picking the wheels.** For 10 seconds after arrival the module collects rear wheel boxes, then merges boxes of the
   same wheel, keeps the two biggest and names them right and left (a single wheel is named by its side of the nose
   wheel). For each, the 8 clearest and steadiest frames are averaged into a reference picture.
10. **Chocked before the event.** A rear wheel is "confirmed chocked" when a chock box sits in the zone under it for 4
    seconds in a row, or when the classifier finds a chock, comparing a steady view of the wheel (1 second of frames
    averaged, the picture unchanged for 2 seconds) with the reference. The classifier is asked at most once every 10
    seconds per wheel.
11. **The event** is the later of two moments: the tug attached and the safety zone clear. If a belt loader comes back,
    the event is cancelled and set again when the zone clears. Within 10 seconds after the event the module looks for
    the chock once more (4 seconds of chock boxes, or the classifier on the 8 best frames):
    - chock still there, so it can only come off after the event: **Pass** for this wheel;
    - chock gone, so it came off too early: **Fail**, but only for a wheel confirmed chocked before; otherwise **Not
      observed** ("never confirmed placed");
    - **Not observed** when the wheel is within 10 pixels of the picture's edge, when its box has an unusual shape
      (width under 0.9 or over 1.4 times its height), or when a person or a vehicle stands in front of it (a vehicle
      must cover more than 15 % of the zone under the wheel, a cone 35 %).
12. **Main gear verdict:** any wheel Fail gives Fail; otherwise any wheel Pass gives Pass; otherwise Not observed.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Chock boxes in a row that confirm a rear wheel chock | 4 seconds | Fewer: not confirmed |
| Time after arrival to pick rear wheels and take reference pictures | 10 seconds | Wheels seen later are not checked |
| Time after the event in which the rear wheel chock must still be found | 10 seconds | Pass or Fail per rear wheel |
| Frames averaged into one wheel view | 1 second | Steadiness of the compared picture |
| Steadiness before a comparison | unchanged for 2 seconds, similarity at least 0.997 | No comparison while the view changes |
| Shortest time between two comparisons of a wheel | 10 seconds | How often the classifier is asked |
| Safety zone busy / clear | more than 2 seconds with a loader / more than 5 seconds without | Moves the main gear event |
| Rear wheel box shape; distance from the edge | width 0.9 to 1.4 times the height; 10 pixels | Outside: Not observed |
| Share of the zone under a rear wheel that blocks it | vehicle 15 %, cone 35 % | Above: Not observed |
| Nose wheel rules (in the code) | 30-second window; 1 second to confirm; 3 seconds present after attachment; 5 seconds absent; 10 seconds of obstacle | Nose wheel verdicts |
| Tug rules (in the code) | final position from 120 to 60 seconds before departure; overlap over 80 %; 5 seconds net | When the tug counts as attached |

Several values in the settings file are not used: the tow bar sizes, two obstacle overlap limits and a picture
difference limit whose check is switched off. Two others only show a message on the annotated video.

## What it reports

- Three results in a fixed order (nose wheel placed, main gear, nose wheel removed), each with a verdict, a sentence and
  a timeline entry (the stretch of video the website marks).
- **Nose wheel placed:** "Nose wheel chocks are applied immediately." or "Nose wheel chocks are not applied immediately
  within 30 seconds after stopping the aircraft.", with times; timeline from 10 seconds before to 30 seconds after the
  arrival.
- **Main gear:** one line per rear wheel, for example "Rear right wheel chocks removed after pushback attached and safety
  zone cleared (time)." or "Rear left wheel chocks were removed prematurely, before pushback attached and safety zone
  cleared (time)."; Not observed lines such as "… wheel chocks never confirmed placed." or "Aircraft wheels were not
  properly visible at arrival." Timeline per wheel from 5 seconds before to 10 seconds after the event; for Not
  observed, from 5 seconds before to 60 seconds after the wheel was first seen.
- **Nose wheel removed:** "Nose wheel chocks are removed after aircraft is attached to pushback." or "… removed before
  aircraft is attached to pushback."; timeline 10 seconds either side of the decision moment.
- Not observed names the reason, for example "Nose wheel is not detected or there is an obstacle", "No arrival stage",
  "No visible pushback attached" or "Chock removal could not be visually confirmed because pushback obstructed the
  wheel." The nose wheel timelines store start and end as text, the main gear one as numbers.
- Files: a drawing file with the boxes and texts; an annotated video and the classifier's input pictures only when a
  developer switches them on.

## How accurate it is

The monthly test is the set of the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for each
check.

- **Nose wheel placed:** 62 of 68 correct (91 %). Only 1 turnaround was labelled Fail, and the module caught it; with a
  single Fail label the number cannot show whether the check catches violations. All 6 wrong verdicts were on
  turnarounds labelled Pass or Not observed.
- **Main gear:** 61 of 68 (90 %). 19 turnarounds were labelled Fail and the module caught 15; 4 violations were missed
  and 3 more wrong verdicts were on turnarounds labelled Pass or Not observed. Only this check has enough Fail labels
  to show how well it catches violations.
- **Nose wheel removed:** 60 of 68 (88 %). The single Fail turnaround was missed; 7 more wrong verdicts were on
  turnarounds labelled Pass or Not observed. One Fail label cannot show whether it catches violations.

Our sources do not say which turnarounds were wrong, or why.

## Known problems

- **Main gear waits for more than the rule.** The code waits for the tug to be attached and for the belt loaders to
  leave. The rule only asks for the attachment. Chocks removed after the attachment while a loader is still there can
  give Fail instead of Pass.
- **Nose wheel removal is never seen.** Pass means "the chock was still seen after the attachment". The rule also gives
  Fail when the video stops before the removal can be seen; that case is missing, so a chock still visible at the end
  gives Pass.
- **Wrong time on a nose wheel removal Fail.** The reported time is the last frame without a chock (near the departure),
  not the moment the chock disappeared.
- **A rule that almost never fires (looks like a bug).** A rule meant to give Not observed when the nose wheel stays
  unseen for more than 5 seconds checks whether the arrival came within the first 30 seconds of the video, so it can
  only fire for such videos. "Within 30 seconds after the arrival" was probably meant (to confirm).
- **A hidden nose wheel is checked at its old place,** because its last box is reused. The 30-second window starts at the
  tracker's arrival moment, about 4 seconds after the stop, not at the stop itself.
- **The tug can be confused.** Obstacles can spoil the attachment test, or another tug or vehicle can be taken for it
  (known from the team's notes on the module). The backup test next to the nose never counts down, so short false
  sightings add up.
- **Exact frames.** The module starts on the exact frame the tracker marks as the arrival and stops on the exact
  departure frame; if such a frame is missing from the data, it never starts or never stops.
- **Memory:** up to 194 full pictures are held per rear wheel.
- **Not ready for production:** the client's sheet marks the main gear check as not ready.
- **Who confirms:** the points marked "to confirm" are for the module's owner (to assign) to check on a labelled
  turnaround. Changes that would change a verdict the client sees are decided with the client's safety team.

## In real time

Not as it is. The module reads the whole turnaround first to find the tug's final position and needs the length of the
video; in real time the earlier frames are gone. The team rates it "needs a small patch": take the moments "pushback
attached", arrival and departure from the stage detector (the part that knows where in the turnaround we are), read
pictures only when needed, and keep small cut-outs of the wheels instead of full pictures. A test version fed with a
live "pushback attached" moment gave the same main gear verdicts as post-processing (after the turnaround) on 8 videos;
the moment used for the nose wheel removal moved earlier by 7 to 444 seconds.

Cost on the team's test machine, one 36-minute turnaround: the reading-ahead pass alone, with its share of the General
Model and the tracker, needs 46.1 milliseconds of the 125 milliseconds each frame may take at 8 frames per second
(37 %). As a post-processing job it takes 38 seconds, 84 seconds of processor work and at most 1.9 gigabytes of memory.

## For developers

- **Module codes in our workspace:** M02A (nose wheel placed), M02B (main gear), M02C (nose wheel removed).
- **Repository:** `dxgat/detectors/aircraft-chocks`; production line `master` @ `fa00478` (2026-01-30); default branch
  the same. `towbar-attachment-fallback` (2026-09-04) and `visualization` (2026-03-02) are one commit ahead each: feature
  work, not in production.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera,
  json_logger, save_diff, debug_all)`; returns three lists (verdicts, reports, timelines) in the order M02A, M02B,
  M02C; `cone_camera` is unused. `FrontWheel` (nose rules), `RearWheelChocksAnalyzer` (observability, chock detection,
  image comparison), `get_aircraft_report`, `get_main_gear_report`; `complex_difference.py` builds the classifier input,
  `simple_difference.py` tests that the view is steady. Logic diagram (Confluence modules database, 2023-07-10):
  https://docs.google.com/spreadsheets/d/1nTmyOxG_teXgI5qAYUVU2xQsD5LTbYCAaxayuqtNmyE/edit?gid=0#gid=0
- **Run on one turnaround:** `python main.py --source <video>.mp4 --weights-dir weights --inferences-dir <folder>
  [--device cpu] [--write-video] [--save-csv] [--save-diff] [--debug-all]`; `run_module.py` loops over test videos.
- **Settings keys:** `min_chock_frames` 32; `stop_capture_window` 80; `main_capture_window`, `main_check_timeframe` 80;
  `frame_average_window` 8, `static_env_window` 16, `static_env_threshold` 0.997; `differentiation_timeout` 80;
  `beltloader_in_thres` 16, `beltloader_out_thres` 40; `min_max_width_ratio` [0.9, 1.4], `edge_distance` 10;
  `diff_obstacle_min_iou` 0.15, `diff_cone_obs_min_iou` 0.35; rear wheel box median `bbox_window` 24. Not used:
  `tow_width`, `tow_candidate_width`, `wh_rel`, `obstacles_match_iou`, `obstacles_check_iou`,
  `not_observed_diff_threshold` (its check is commented out); `obstacle_width`, `obstacle_center_range` only drive an
  on-screen message. In code: nose rules 30 s / 1 s / 3 s / 5 s / 10 s / 35 s; arrival stage > 24 frames with mean
  optical-flow shift ≤ 50 px across, ≤ 5 px vertically; pushback window `deque(maxlen=120*fps)`, first half, > 8 boxes,
  IoU 0.8, > 40 frames; nose fallback 0.3 aircraft heights; nose chock zone `y1 + 0.6·h` with `add_offset` 0.2.
- **Code places:** first pass `main.py:1240-1286`; arrival, departure, arrival stage `:1431-1485`; pushback attached
  `:1523-1549`; safety zone `:1561-1612`; nose wheel `:953-1060, 1615-1626, 1715-1749`; `installed_no` `:970`; M02A /
  M02C verdicts `:1139-1211`; pushback-cover rule `:1760-1763`; rear wheel pick `:1659-1680`; observability
  `:281-389`; chock detection `:392-443`; image comparison `:446-865`; M02B verdict `:33-79`.
- **Dependencies:** `cv_common` ac5098d, `db_worker` 5a4aa83 (`git ls-tree HEAD`); timm, torch, torchvision, norfair,
  matplotlib; Docker base `cpu_base`. Weights in DVC: `effnetb0_ext_fix_993.pt` (EfficientNet-B0 chock classifier).
- **Real time:** verdict PATCH in `docs/04_modules.md` (`main_stream.py`, 3 hunks: 0 M02B differences on 8 videos, M02C
  anchor −7 to −444 s); group B in `docs/analysis/rt_module_selection.md` (5.7 ms per recorded frame); first pass only
  in `docs/analysis/rt_module_cost.md`.
- **Sources:** `docs/modules/aircraft-chocks.md`, `docs/analysis/module_review_2026-10.md`, `docs/05_module_logic.md`.
