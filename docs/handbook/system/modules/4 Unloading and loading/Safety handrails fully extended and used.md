# Safety handrails fully extended and used

> A belt loader (the conveyor vehicle that carries bags up to a cargo door) has safety handrails for the workers who
> walk on it, and they must be fully extended while it stands at the aircraft. This check makes sure that the belt
> loader at the camera's cargo door had its handrails extended for most of the time it stood there. Once per second our
> own image classifier looks at the stopped belt loader and says "extended" or "not extended".

## Status

| | |
|---|---|
| How accurate it is | 55 of 56 turnarounds correct (98 %) on the monthly test |
| Fail turnarounds it caught | 16 of 17 |
| In production | the version of June 2025 (logic last changed in February 2025) |
| Who looks after it | to assign |
| Biggest open problem | It checks only that the handrails are extended, not that they are used, and the client's "8 minutes" is really 60 seconds. |

## What the client wants

*Safety handrails fully extended and used*

| Verdict | When |
|---|---|
| Pass | Every belt loader seen for more than 8 × 60 = 480 frames had its handrails extended in more than 45 % of them (an "extended ratio" above 0.45). |
| Fail | Any belt loader seen for more than 480 frames had its handrails extended in 45 % of them or less. |
| Not observed | No belt loader is seen near the aircraft. |
| Not observed, view blocked | No rule for obstacles. |

A verdict is the answer of a check: Pass, Fail or Not observed. A frame is one picture of the video; the cameras take 8
per second. The client's sheet calls 8 × 60 frames "8 minutes", but at 8 frames per second it is 60 seconds; the code
uses 60 seconds of standing still.

## When and where it looks

Unloading and loading (a stage is a part of the turnaround): from the moment the tracker reports the aircraft as arrived
(standing still for more than 4 seconds) until the departure (moving for 10 seconds), only on frames in which the belt
loader at this camera's door is stopped. For aircraft, the cone camera (looks towards the aircraft nose) watches the
front belt loader and the wing camera (looks along the wing) the back one; when both run, Fail on either gives Fail and
Pass on one with Not observed on the other gives Pass. Not used for jets.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object): the aircraft's rear
  wheels, on the cone camera, to drop the belt loader of the back door; people, trailers and service vehicles (ground
  support equipment: tugs, belt loaders, fuel trucks, tractors) only for an on-screen "Camera is blocked!" note.
- **From the tracker** (a track is the same object followed from frame to frame): the aircraft (arrived, departed) and
  the belt loaders, with the tracker's label of the door each serves (front or back) and whether it is stopped.
- **From the video itself:** yes: the picture of the belt loader goes to the classifier.
- **Its own model:** a **handrail classifier** (trained by us) that looks at the picture of a belt loader and answers
  "handrails extended" or "not extended". *Handrails on service vehicles being used* uses the same model. It runs on a
  graphics card if there is one, otherwise on the processor.

## How it decides, step by step

1. **Window.** Processing starts when the tracker marks the aircraft as arrived and stops when it marks it departed.
2. **Which belt loader.** It keeps the belt loaders the tracker labelled for this camera's door: front on the cone
   camera, back on the wing camera. On the cone camera a belt loader that overlaps a rear wheel and stands behind it is
   dropped. The biggest one left is used. There are no other ways to find it.
3. **Track changes.** If a belt loader track appears less than 120 frames (15 seconds) after the last one was seen, it
   is treated as the same belt loader and continues its record.
4. **Stopped frames only.** Frames in which the belt loader is not stopped are skipped.
5. **Classification.** Every 8th frame (once per second) the classifier looks at the belt loader picture, with the box
   raised by 30 % of its height to take in the rails, and says extended or not extended. The answer is kept for the
   frames in between.
6. **Counting.** Each stopped frame adds the current answer to that belt loader's record.
7. **Each belt loader**, at the departure or the end of the video: only belt loaders with more than 480 stopped frames
   (60 seconds) are judged. If the share of "extended" frames is above 45 %, it passes.
8. **Verdict:** no belt loader judged → Not observed; all judged belt loaders pass → Pass; any fails → Fail.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Extended share needed | 0.45 (45 %) of stopped frames | Pass or Fail of a belt loader |
| Same belt loader after a new track | within 120 frames (15 seconds) | Records are merged |
| Shortest stay judged | 480 stopped frames (60 seconds) | Fixed in the code as 60 × 8, not taken from the frame-rate setting |
| Classification | every 8th frame (once per second) | Fixed in the code |
| Box raise | 30 % of the belt loader's height | Fixed in the code |
| Frames in a row before a belt loader's start is noted | 4 frames (0.5 seconds) | Only the start time shown |
| Obstacle width and position | 30 % of the picture width; centre at 30–100 % | Only the "Camera is blocked!" note |
| "Camera type does not matter" | on | Not used by the code |

## What it reports

- **Sentence:** "All of the beltloaders had safety handrails extended for enough time." or "Not all of the beltloaders had
  safety handrails extended for enough time.", then for each judged belt loader "Beltloader N extended long enough: X%
  (start - end)" or "Beltloader N extended NOT long enough: X% (start - end)". Not observed: "Beltloaders were not
  detected".
- **Timeline entry:** one Pass or Fail block per judged belt loader, from its first to its last frame.
- **Files:** a drawing file for every frame; an annotated video only when video writing is on.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, 56 labelled for this check. The
module matched the client on 55 (98 %). Of the 17 labelled Fail it caught 16; its only error is that missed violation.
With 17 Fail labels the test does show that it catches most of the turnarounds the client labelled Fail.

## Known problems

- **Extension only.** The check is called "fully extended and used", but the module checks only that the handrails are
  extended; their use is the check *Handrails on service vehicles being used*. The client's rule also speaks only of
  the extended ratio, so a Pass here says nothing about use.
- **"8 minutes" is 60 seconds.** The client's sheet calls 480 frames "8 minutes"; the code, like the frame count, uses
  60 seconds. Belt loaders that stood between 1 and 8 minutes are judged. Which one the client means: to confirm with the
  client's safety team.
- **Merging is broad.** Any belt loader track that appears within 15 seconds of the last one is merged into it, so two
  belt loaders served back to back can count as one.
- **Held answers.** One classification decides 8 frames, and a new belt loader record starts as "not extended" until
  its first classification (up to 7 frames).
- **No top limit.** After the box is raised by 30 %, its top is not held at the picture edge, so a belt loader near the
  top of the picture gives the classifier a wrong picture.
- **Obstacles only print "Camera is blocked!"** on the annotated video; a hidden belt loader simply stops adding frames.
- **Wasted work.** Every stopped frame is read and converted, although only one in eight is classified.
- **Outdated descriptions.** The module's description file describes an older version (another classifier and a rule of
  70 % overlap with the aircraft). The real-time audit lists no models, but the module has the classifier.
- **Wing-camera door label (to confirm).** The tracker review found that production may not tell the tracker the
  camera; in 7 sample videos no belt loader got the back-door label. This module has no other way to find the belt
  loader, so on the wing camera it may seldom or never judge one. The tracker's owner can confirm.

## In real time

It runs unchanged but needs the video pictures: one belt loader picture per second. Each belt loader's result could be
final when it leaves; today all are computed at the end. On a 36-minute test turnaround in the real-time test setup it
gave the same verdict as post-processing (Pass), at the departure.

Own work: about 2.4 milliseconds per frame (3.6 with all checks together); with the shared General Model and tracker
parts, 34.6 of the 125 milliseconds each frame may take (28 %), on a faster graphics card than production's. As a
post-processing job: about 46 seconds. Lighter with the same results: read pictures only on the frames it classifies,
and share the classifier call with *Handrails on service vehicles being used* (same model, same picture). From the
stage detector (the part that knows where in the turnaround we are) it needs the moments a belt loader reaches and
leaves the door. The client puts this check in the streaming group.

## For developers

- **Repository:** `dxgat/detectors/safety-handrails-fully-extended`; production and default branch `master` @
  `8b9a2a9` (2025-06-19; last logic change `c7c5b6d`, 2025-02-18). Workspace module code: M22.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, cone_camera, weights_dir,
  json_logger)`; `Loader` (record per belt loader, answer history, extended ratio), `make_inference` (verdict);
  `efficientnet.py` wraps the classifier (torchvision EfficientNet-B0, 224 × 224 input, softmax). Block diagram
  `assets/block_diagram.svg`.
- **Dependencies:** `cv_common` @ `33c188d`, `db_worker` @ `5a4aa83` (the local clone substitutes cv_common `ac5098d`);
  torch and torchvision from the `mmpose_base` image. Weights (DVC):
  `efficientNetb0_300_epoch_general_classifier_dataset_safety_handrails_v3_26_09_2023.pth`.
- **Run on one turnaround:** `python main.py --source <video.mp4> --inferences-dir <dir> --weights-dir weights
  [--cone-camera] [--local-inferences] [--write-video] [--save-csv]`; settings `local_config.yaml` over
  `cv_common/global_config.yaml`.
- **Settings keys** (table order): `min_extended_time_thresh`, `min_bl_swap_time_thresh`, stay `60 * 8` at
  `main.py:24`, cadence `main.py:283`, box raise `main.py:77`, `bl_min_detection_streak`, `cone.obstacle` /
  `wing.obstacle`, `camera_type_irrelevant`.
- **Code places:** step 1 `main.py:176-198`; 2 `main.py:225-248`; 3 `main.py:249-263`; 4 `main.py:268-274`; 5
  `main.py:63-77, 276-288`; 6 `main.py:89-102, 291`; 7-8 `main.py:23-46`; obstacle note `main.py:200-223`.
