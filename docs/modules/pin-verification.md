# M16 · Pushback operator verifies steering bypass pin installation

> The module checks that, after the pushback tug is attached and before the aircraft leaves, a worker goes to the nose
> wheel and checks the steering bypass pin. It finds workers next to the nose wheel and uses a body-pose model to see
> whether one of them bends or crouches there, or stands still there with a hand raised.

## At a glance

| | |
|---|---|
| Checks | M16 · Pushback operator verifies steering bypass pin installation |
| Stage | Pre-departure |
| Looks at | From the moment the pushback counts as attached until 10 s before the tracker's departure moment, only while the aircraft is stopped |
| Cameras | Cone camera, aircraft only (not run for jets); the camera flag is ignored |
| Uses | General Model (GM) boxes: pushback, airplane_nose, front_wheel; obstacles beltloader, gse, trailer, obstacle, side_obstacle, vehicle. Tracks: airplane, person. Video frames: yes (pose on workers near the wheel) |
| Own models | none trained by us; a stock body-pose model (SimCC ResNet-50, COCO, via mmpose) gives each worker's keypoints |
| Runs on | GPU (`cuda:0` is hard-coded) |
| Real time | needs a small patch — a first pass reads the whole video to find the departure frame and where the pushback finally parks; this should come from a shared "pushback attached" event instead |
| Production version | master @ 8e1863c (2025-06-19) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | A worker bends near the front wheel for 0.5 s or stands there for ≥ 3 s (counted as the pin verification) while the pushback is on video. |
| Fail | Aircraft found, pushback found, front wheel detected, but no pin verification detected. |
| Not observed | The aircraft, the pushback or the front wheel was not observed. |
| Not observed — view blocked | There were obstacles for 2 minutes in total after the first pushback detection. |

## How it decides

1. **First pass.** It reads the tracks up to the frame where the tracker reports departure (or the last frame). From the biggest pushback box of each frame it takes the median over the window from **120 s to 60 s** before that frame: the pushback's parked position.
2. **Second pass.** It follows the airplane track and works only between the tracker's arrival and departure.
3. **Nose wheel.** It takes the largest GM front_wheel box (taller than 40 px) lying more than 80 % inside the aircraft box, then follows and smooths it (median over 60 s). The **wheel zone** runs from one wheel width left of the wheel centre to 1.5 widths right of it, and from the centre to one wheel height below it.
4. **Pushback attached.** A pushback box matching the parked position (IoU, overlap over union, above **0.8**) adds one to a counter; other frames take one away. Without a parked position, a pushback touching the nose counts. Above **80 frames** (10 s) the pushback is attached and the provisional verdict becomes Fail.
5. **Obstacles.** Large GM boxes (wider than **500 px**, taller than **400 px**) of the obstacle classes, not the pushback itself, that overlap the wheel zone by more than 75 % make the frame "blocked". Blocked frames are counted and skipped.
6. **Workers.** After attachment, while the tracker says "stopped" and not in the last **80 frames** (10 s) before the first-pass departure frame: a person track is near the wheel when the bottom 10 % of its box lies more than 50 % in the wheel zone and it is at most 5 wheel heights tall. The pose model runs on these workers.
7. **Action.** Per worker, one counter grows on frames showing bending (a wrist below the hip, body angle ≤ 150°) or crouching (a knee angle < 120°); another grows when the worker stands upright (> 150°) with a wrist at or above head level and the ankles move ≤ 5 px. Other pose frames subtract 5. **12 frames** (1.5 s) of bending/crouching or **20 frames** (2.5 s) of standing → Pass; processing stops 10 s later.
8. **Without a Pass:** blocked frames ≥ **960** (120 s) → Not observed; nose wheel missing > **480 frames** (60 s) after attachment → Not observed; mean pushback box covering > 10 % of the mean wheel box → Not observed; pushback never attached → Not observed; no departure → Not observed; otherwise Fail.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `obstacle_width` / `obstacle_height` | 500 px / 400 px | Minimum size of an obstacle box |
| parked-position window (code) | 120 s, median of the older half | Reference for "attached" |
| attachment (code) | IoU > 0.8, counter > 80 frames (10 s) | When the pushback counts as attached |
| bend / stand time (code) | 12 frames (1.5 s) / 20 frames (2.5 s) | Action length that gives Pass |
| keypoint confidence (code) | 0.2 | Keypoints below it are not trusted |
| obstacle limit (code) | 960 frames (120 s) | Blocked time that gives Not observed |
| wheel-missing limit (code) | 480 frames (60 s) | Hidden wheel after attachment → Not observed |
| no-check time (code) | 80 frames (10 s) before departure | Ignores the chock-removal moment |

`obstacle_center_range` and `airplane_moving_thresh` are in the YAML but not used.

## What it reports

- Pass: "Pin installation was verified by <worker track id>. (… - …)" with a Pass smart-timeline segment of ±50 frames (±6.25 s) around the frame.
- Fail: "Pin installation wasn't verified (… - …)" with a Fail segment from the attachment to the departure.
- Not observed: "There was an obstacle for more than 2 minutes", "Front wheel wasn't detected for 1 minute after pushback appeared", "Front wheel was partially obscured by pushback", "Pushback attachment was not observed" or "Plane departure was not observed, could not verify pin installation"; empty smart timeline.
- Overlay file (.ndjson): aircraft state, nose, wheel and wheel zone, pushback, worker boxes with their flags, keypoints and status lines. An annotated video with pose skeletons when video writing is on.

## Known issues and limits

- The 1.5-s bend and 2.5-s stand rules differ from the client's 0.5 s / 3 s (and from the README); "standing" also needs a raised hand.
- It measures a check-like action at the wheel, not the pin itself. In substance it is close to M26 (steering bypass pin installed) — to cross-check.
- The first pass uses the future (parked position, departure frame, video length), so the module is not causal.
- The attachment rule is marked "TODO: review and rework"; it takes the first pushback box in the GM list, while the first pass uses the biggest one.
- Obstacles are counted from when the wheel zone exists (after arrival), not from the first pushback detection as the client rule says; blocked frames are skipped ("TODO: make sure this old logic is not harmful").
- Workers are checked only while the tracker status is "stopped".
- `cuda:0` and the `weights/...` path are hard-coded; `--device` and `--weights-dir` are ignored. Several workers qualifying on one frame add several Pass segments.

## For developers

- **Repository:** `dxgat/detectors/pin-verification`; production line `master` @ `8e1863c`; default branch `master` @ `8e1863c` (the same).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, weights_dir, cone_camera, json_logger)`. `Plane` (nose, wheel, wheel zone), `Wheel`, `Worker` (pose rules), `get_front_wheel_bbox`, `find_pushback`. The `Pushback` class and `pushback_ROI` are unused. Diagram `.doc/new_pin_verification.svg`; logic diagram (Confluence modules database, 2025-04-25): https://docs.google.com/spreadsheets/d/1SJpA9JmgyA2WEeERvQBNmtl4YPZc1VDCK2YGWV9OIRc/edit?gid=333438026#gid=333438026
- **Dependencies:** `cv_common` dd5b554, `db_worker` 6efc0b0 (`git ls-tree HEAD`); dd5b554 is not in the local archive, the local folder holds ac5098d. mmpose 1.3.1, mmcv 2.1.0, mmdet 3.2.0, mmengine 0.10.4 (README); mmpose Docker base image. Weights in DVC (178 MB): `weights/simcc_res50_8xb32-140e_coco-384x288-45c3ba34_20220913.pth`; the model config comes from the mmpose package.
- **Run locally:** `python main.py --source <video>.mp4 [--local-inferences --inferences-dir <folder>] [--write-video] [--save-csv]`; needs a CUDA GPU.
- **Code references:** first pass `main.py:504-549`; arrival/departure gate `:633-645, 733-738`; wheel `:83-89, 435-457, 647-650`; attachment `:466-477, 662-684`; wheel state `:693-706`; obstacles `:627-631, 708-729`; no-check time `:762-766`; workers and pose `:769-855`; action rules `:236-320`; Pass `:857-868, 604-612`; final verdict `:893-929`.
