# General Model

The General Model is the shared detector of the system. It looks at every frame (one picture of the video; the cameras
take 8 per second) of each camera's recording of a turnaround and draws a box around every object it knows: the aircraft
and its parts, people, service vehicles, cones and chocks. Each box is a detection. It also picks out our aircraft, marks
vehicles that block the view, and decides which camera filmed the recording, the aircraft type and the airline. The
tracker and every check read its output, so a change here can change any verdict (Pass, Fail or Not observed).

## Status

| | |
|---|---|
| In production | The version of October 2026: the code of September 2025 with a speed-up that leaves every output file exactly the same |
| Last change | October 2026: work whose results nobody used was removed; the job is about 26 % shorter |
| Next step | Measure it on the monthly test, which still compares against an April 2024 model; then fold the vehicle detector into the main detector |
| Who looks after it | Yurii Luchko and Valentyn; Maksym Chernyshev builds the production image and runs the cluster tests |

## What it does

Two cameras film each turnaround: the cone camera looks towards the aircraft nose, the wing camera along the wing. Their
one-minute pieces are joined into one recording per camera. The General Model runs once on each recording, before the
tracker and the checks. It:

1. **detects objects** on every frame with three detectors on a graphics card (main, chock, vehicle);
2. **picks our aircraft** (the "main aircraft") among all aircraft in view, neighbours and passing ones included;
3. **marks obstacles**: vehicles in the way, which checks use to decide that the view is blocked;
4. **classifies the recording**: camera (cone or wing), aircraft type (aircraft or jet), airline;
5. **writes** the boxes of every frame, a report and an annotated video.

## What it finds

Every box has a position, a class (kind of object) and a confidence score from 0 to 1. Boxes are kept above a score of
0.35 (main detector), 0.10 (chock detector) and 0.40 (vehicle detector).

| Source | Classes, in plain words |
|---|---|
| Main detector (25 classes) | **People:** person (anyone, also workers in vehicles); safety vest. **Aircraft:** the whole aircraft; wing, engine, tail, nose; nose wheel (front landing gear), main wheel (rear landing gear); front and rear cargo door, where belt loaders stand (the cone camera almost never sees the rear one). **Vehicles:** belt loader (carries bags up a conveyor belt to a cargo door); pushback tractor; tow bar (joins a tractor to the nose wheel); fuel truck; trailer (carts pulled by a tractor, such as baggage carts); ladder; service vehicle (other ground support equipment, such as tugs); air conditioning unit (conditioned air for the parked aircraft). **Cones:** cone; wing, engine and tail cones; the cone behind a belt loader. **Other:** camera holder (not described in our sources, read by no check; to confirm with Yurii Luchko) |
| Chock detector | chock: the wedge placed against a wheel so it cannot roll |
| Vehicle detector | vehicle: any vehicle, one class |
| Added by the code | obstacle: a copy of a vehicle box reaching into the area left of or below our aircraft's nose wheel; side obstacle: the same, inside a side zone at a wing tip; main aircraft: our aircraft's box, carrying its usual height in pixels instead of a score |

**Outputs.** The *detection file* has one line per frame, numbered from 1 in reading order; a box is four corners in
pixels of the 1920 × 1080 picture, the score and the class. The *report* gives the camera type with the winning share of votes, the frame on which our aircraft stopped, the
aircraft type, the airline and, for each rough stage (a part of the turnaround) of at least 60 seconds, how often each
class was seen. An *annotated video* (on by default) and the job log complete it.

## How it works, step by step

It reads the video twice: the second pass needs the whole first pass to know which aircraft is ours.

**First pass**

1. Read a frame. Every 48 frames (6 seconds) estimate the picture noise; smooth the frames of noisy videos.
2. Run the three detectors. Where boxes overlap by more than 70 %, keep only the best one, whatever their classes.
3. Keep the boxes in a temporary file.
4. Follow every aircraft box at least 150 pixels high and covering at least 10 % of the frame. Of two overlapping by more than
   70 %, drop the larger. A new track (an object followed from frame to frame) overlapping a known aircraft by more than
   50 % continues its history.
5. Count how often each nose, nose-wheel and wing box appears.

**Second pass**

1. **Our aircraft** is the aircraft track seen on the most frames (none: the job reports an error). Its usual height is
   its most common box height, rounded to 10 pixels.
2. **Layout.** The main nose and nose wheel are the largest boxes seen on more than 240 frames (30 seconds), or on more
   frames than the tenth most frequent part if that is higher. The wings give two side zones at the wing tips.
3. Read the video again; take each frame's first-pass boxes, round them to whole pixels, keep them inside the picture,
   drop the raw aircraft boxes.
4. **Obstacles.** Belt loader, service vehicle, pushback tractor, tow bar, fuel truck, trailer and ladder boxes (and
   vehicle boxes matching none of them) larger than 7,000 square pixels that reach left of or below the main nose wheel
   are copied as obstacles; a copy more than 70 % inside a side zone becomes a side obstacle.
5. Add our aircraft's box on every frame of its track; write the line to the detection file and the frame to the
   annotated video.
6. Follow our aircraft's motion (points followed inside an outline drawn by a segmentation model) to find its arrival
   and departure.
7. **Aircraft type.** Take the best wing and engine boxes lying at least 50 % inside our aircraft. An engine whose bottom
   edge is higher than the wing's votes "jet"; lower votes "aircraft". Voting stops at the departure; if the aircraft
   vanishes for 10 seconds before arriving, it was passing by and voting restarts.
8. **Camera type.** After the arrival, a small image classifier labels each frame showing our aircraft as cone or wing
   camera, from the band between rows 150 and 930 of the picture.
9. **Airline.** Every 2 seconds during the first 60 seconds of our aircraft, read the text painted on it and match 12
   airline names; failing that, classify the tail paint (16 airlines). Keep the most common answer.

**Report.** The camera type is the majority vote. An open aircraft type becomes jet with more "jet" votes, otherwise
aircraft (empty with no votes and the aircraft never in view for 15 seconds in a row). Rough stages: before arrival (if
at least 30 seconds), arrival to departure, after departure (if at least 90 seconds), the full turnaround; belt loader
stages are always "no".

## How fast it is and what it costs

- One job per recording in Google's cloud: one NVIDIA T4 graphics card, 3.3 processor cores, 8 gigabytes
  of memory. The median recording (87 minutes) takes about 1 hour 46 minutes, against 2.4 hours before October 2026.
- **Cluster test, 22 October 2026**: five recordings, old and new image started together. Every detection file was
  identical byte for byte; 589 instead of 799 minutes in total, 26 % less (18–33 % per recording).
- For the median recording, all processing (General Model, tracker, checks) falls from 4.8 to 4.16 hours, and the cost
  per hour of video by 10–13 %, from 1.84–4.59 to 1.60–4.05 US dollars. Time to result (about 24 hours) shrinks by about
  48 minutes; the waits between jobs are unchanged.
- The speed-up removed unused work: motion analysis of every aircraft in the first pass, frame copies, loading an old
  airline detector, about ten log lines per frame, and a third reading of the video that fed only a file inside the job.
- **Where the time goes**: the vehicle detector is the largest network (25.8 million parameters) and about half of the
  detection time (8.0 of 16.9 milliseconds on our test machine). The main detector is the smallest (3.1 million).
- **Real time** allows 125 milliseconds per frame per camera. On our test machine the project's own version takes 28.3
  milliseconds per frame, video reading included; a faster graphics-card engine cuts the detectors from 16.8 to 8.0 milliseconds
  (results equal within a small tolerance). The production card is roughly 3–4 times slower; to be measured.

## How good it is

- How often it misses or invents objects is not known yet (to confirm with Yurii Luchko and Denys, who keeps the
  datasets).
- **The monthly test compares against the wrong model.** Its stored files come from an April 2024 version that fed the
  colours in the wrong order (blue-green-red). The production code has the fix from June 2024 (red-green-blue), but
  production files exist for only 1 of the 90 test recordings. There the two agree on no frame: 60 % of the boxes move by more than 2 pixels or 0.02 in
  score; 6–7 % have no counterpart.
- So the check accuracy with the production General Model has never been measured. A first comparison suggests it is
  lower than with the April 2024 model on 56 of 90 recordings, worst for the safety huddle, the walk-around before
  departure, the pushback driver's pin check, handrails on service vehicles, cones removed, steering bypass pin, hand
  signals and safety zone. Whether the
  detector or checks tuned on the old outputs cause it is the next question.

## Which checks depend on it

Every check reads it, directly or through the tracker (counts from the September 2026 review):

| What it gives | Who uses it |
|---|---|
| Our aircraft's box and usual height | the tracker (aircraft track, arrival rule), and through it 25 checks |
| People | 10 checks; the tracker follows them for 14 checks |
| Vehicle classes | trailer 23 checks, service vehicle 22, pushback tractor 22, belt loader 17, fuel truck 13, ladder 8 |
| Aircraft parts, cones, safety vest, tow bar | 1 to 9 checks each (cone 9; main wheel, engine, tail 8 each; safety vest, tow bar 1 each) |
| Chock | aircraft wheel chocks, belt loader forward chock, chocks and cones before arrival, service vehicles chocked, pushback path, steering bypass pin |
| Vehicle | aircraft wheel chocks, cargo doors, cones removed after service vehicles clear, pushback driver's pin check, pushback path, safety zone |
| Obstacles (blocked view) | cargo doors, chocks and cones before arrival, lead marshaller and wing walkers, pushback driver's pin check, pushback waits for wing walkers, wing walkers during pushback, aircraft wheel chocks, safety zone |
| Camera and aircraft type | every check job; they decide which checks run on which camera (aircraft: 12 checks on both cameras, 18 cone only; jets: 3 on both, 13 cone only, 8 wing only) |
| Read by no check | air conditioning unit (the conditioned-air check uses its own detector), airline (report only) |

## Known problems

1. **Report fields change between runs.** Our aircraft's motion analysis picks points at random, so the stop frame and
   camera confidence (in close cases the camera or aircraft type) can differ between runs. The detection file does not:
   compare files, not reports.
2. **Misleading values and gaps.** Obstacle boxes carry another box's score; our aircraft's box carries a height. The
   report's stage field is always empty, belt loader stages are always "no" (door boxes are never collected), and noise
   values are not sent.
3. **Airline spelling.** The two airline readers spell some names differently; with no airline after 60 seconds, a
   picture file is rewritten on every later frame.
4. **Whole recording only.** Our aircraft, layout and stages need the full recording, so it cannot run piece by piece.
   The file has no version mark; a frame's number is its line position.
5. **Failures.** A main nose or nose wheel without any wing detection would stop the job (found by reading code).
   "Processed" is reported before the upload; a failed upload adds an "error" report.
6. **Graphics library setting.** Production's choice of computing method works on its card, but on a newer card every
   computation fell back to a path 2.6 times slower. Check it before changing card or image (the planned move to Azure).
7. **Two software images.** Production's older image and the undeployed newer one agree on 99.95 % of boxes, not byte
   for byte: compare versions on one image.
8. **To confirm** (Maksym Chernyshev): the shared library in the production image is unreadable to us, so class names
   and thresholds here come from a newer copy; whether production writes the annotated video (about 12 milliseconds per
   frame plus upload) and whether anyone watches it.

## What changes next

1. **A production baseline for the monthly test** (first five recordings run on 21 October 2026): run the production
   image on all 90 recordings; Oksana scores them next to the April 2024 scores; the monthly test then follows production.
2. **Fold the vehicle detector into the main detector**, the largest saving left. 69 % of vehicle boxes coincide with a
   main detector box of a vehicle class (service vehicle 27 %, trailer 24 %, belt loader 19 %, pushback tractor 17 %, tow
   bar 10 %, fuel truck 3 %), but 27 % have none, so it cannot simply be dropped. It needs a training run (Denys's
   datasets, Yurii Luchko) and a check that no verdict changes on the six checks that read vehicles.
3. **After the same verdict check**: the faster graphics-card engine; classifying the camera on several frames at once.
   Two exact savings remain: reusing first-pass noise estimates (about 2 %) and skipping an unused resize (about 3.5 %).
4. **Real time.** In the real-time worker the main detector runs inside the stage detector (see that page).

## For developers

- `dxgat/detectors/general_model`; production `pf/q4-02-gm-exact-speedups-a0157a4`, image `b6e1a3e` (2026-10-22) =
  `a0157a4` + `2259608`, `8d8c9a4`; not deployed `d4ae8e5`, `afaebf1`, `master` `13a4ddc`. Python 3.8 image;
  `cv_common` `d74eb09` (unreadable).
- Entry `db_worker/model_starter.py --model=general_model` → `main.detect()`; first pass `main.py:541-698`, second
  pass `787-976`, report `978-1151`.
- Weights (ONNX fp16): `GM_yolov8m_best_augmentation_march2024.onnx` (YOLOv8n size), `chocks_v4.3_200ep_yolov8.onnx`
  (YOLOv8s), `VM_yolov8m_last_september2023.onnx` (YOLOv8m); EfficientNet-B0 camera classifier, MobileSAM, CRAFT +
  EasyOCR, tail classifier. Class ids 0–24, 25 chock, 29 obstacle, 30 side_obstacle, 31 vehicle; class 2 = height mode.
- Keys `conf_thres`, `chock_conf_thres`, `vehicle_conf_thres`, `airplane_min_height`, `GM_VERBOSE`, `--write_video`,
  `cudnn_conv_algo_search=DEFAULT` (`main.py:41`). Output `gs://cv-modules-topics/<video>.mp4/general_model<commit>.ndjson`;
  pin with `general_model_inferences_version_commit`.
- Sources: `docs/models/general_model.md`, `docs/analysis/gm_*.md`, `pose_unification.md` §6; PF-Q4-02, PF-Q2-16.
