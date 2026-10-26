# M12 · Motorized GSE parked and properly chocked

> For every stop of a motorized GSE (ground support equipment) vehicle, the module looks for evidence that its wheels were chocked: a chock detected at the wheels, a worker bending down at the vehicle, or a change in the wheel area that a trained classifier recognises as a chock. One stop without chocks fails the video.

## At a glance

| | |
|---|---|
| Checks | M12 · Motorized GSE parked and properly chocked |
| Stage | Download, Upload |
| Looks at | the whole video: each stop of each GSE, from the moment it stops until it drives away (or the video ends) |
| Cameras | cone and wing camera for aircraft; wing camera only for jets (the code runs the same logic on both) |
| Uses | General Model (GM) classes `chock` (evidence), `pushback`, `trailer`, `fuel_truck`, `cone`, `ladder` (obstacles); tracks of `gse` (with the tracker's motion counters and optical-flow points), `person` and `beltloader`; video frames: yes |
| Own models | chock difference classifier (EfficientNet-B0, ours) — did a chock appear in the wheel area; RTMPose-l (stock pose model) — is a worker bending |
| Runs on | CPU in the current image (`cpu_base`, `--device cpu` by default); the code can use a GPU |
| Real time | ready, needs video frames — the verdict for each stop is known when the GSE drives away |
| Production version | per_component_improvement @ d3f92a5 (2026-05-29; last logic change 426526b, 2026-03-24) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | The GSE is considered parked and one of these holds: a chock is detected directly in the wheel zone; a worker's bending action is detected (frontal orientation); the frame-difference analysis shows chocks. |
| Fail | Not filled in the client sheet. The code fails the video when any evaluated stop is judged not chocked. |
| Not observed | The GSE is too far (box height below the minimum), partly outside the frame, not parked long enough, or a person stays on it too long. |
| Not observed — view blocked | Orientation-based check: obstacles cover more than 75 % of the wheel zone. Difference check: the scene is not static or something stands in front. |

## How it decides

1. **Vehicles.** Every track of the GM class `gse` is followed (belt loaders and pushbacks are not). The tracker says when it is stopping or stopped (still for 3 s); "drove away" means **6 frames** of motion after a stop.
2. **Orientation.** From the tracker's optical-flow points it compares sideways motion with the change in apparent size and fixes the orientation at the stop: side-on (ratio above **40**), face-on (below **8**) or angled.
3. **Observability.** A stop is "not observed" while the box is under **120 px** high, cut by the frame edge (or oddly proportioned), parked under **160 frames** (20 s), or a person sits on top for more than **60 %** of the stop. Such a stop cannot produce "not chocked".
4. **Direct chock.** A GM chock centred in the wheel zone (lowest 20 % of the box plus a 5 % margin) for **40 frames** (5 s) in a row: chocked.
5. **Worker bending.** RTMPose runs on each person standing at the lower part of the GSE. A drop of the person's height below **65 %** of its maximum within **1 s** is a bend: chocked. Low-confidence poses (under **0.3**) and moving feet are ignored; on angled GSE a worker who tilts, hides for **2–3 s** and reappears tilted counts with a weaker threshold (**0.91**). Face-on only: if the zones beside the GSE were clear for **30 s** without a bend, this channel says "not chocked".
6. **Frame difference.** Right after the stop, 4–8 static frames are averaged into a "just stopped" image. After every **10 s** of full stop, once the scene has been static for **3 s** with nothing in front, the current frames are averaged and the classifier compares the bottom strip of the GSE box (the wheels) in the two images (no answer if they match below **0.8**; at most **6** checks). If no check said "chocked", the scene just before the GSE leaves is compared with the saved check images, so chocks removed before leaving also count. A "chock" answer counts only if background objects stayed in place.
7. **Combining.** Any positive signal means chocked, except: face-on — "no bend" gives not chocked unless the chock or difference channel said chocked; side-on or unknown — once the difference check has an answer, the direct chock detection is ignored; a box touching two frame edges cannot pass on the difference check alone. The stop's result is recorded when the GSE drives away or the video ends.
8. **Verdict.** A GSE judged not chocked once stays not chocked. Any such GSE gives Fail; otherwise any chocked GSE gives Pass; otherwise Not observed.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `min_chock_frames` | 40 (5 s) | Consecutive frames a chock must sit in the wheel zone. |
| `min_park_duration` | 160 (20 s) | Shorter stops are not observed. |
| `min_observed_height` | 120 px | Smaller GSE boxes are too far. |
| `min_person_stay_ratio` | 0.6 | Share of the stop with a person on top that marks a driver on board. |
| `bend_window`, `bend_ratio_threshold` | 8 (1 s), 0.65 | Window and height drop that count as a bend. |
| `weaker_bend_ratio_threshold` | 0.91 | Bend threshold for the "tilt, hide, reappear" case (angled GSE). |
| `min_action_clear_frames` | 240 (30 s) | Clear view needed before "no bend" means not chocked (face-on). |
| `differentiation_timeout`, `max_checks_number` | 80 (10 s), 6 | Time between difference checks; checks per stop. |
| `not_observed_diff_threshold` | 0.8 | Below this match score a difference check has no answer. |
| `profile_threshold`, `frontal_threshold` | 40, 8 | Orientation boundaries. |

## What it reports

- **Verdict:** Pass, Fail or Not observed.
- **Report:** one line per evaluated stop, sorted by time: "GSE N was / was not chocked (start – end)", padded by 1 s. Not observed: "No GSE were observed." or "No GSE were parked, or chocking status remained unclear."
- **Smart timeline:** one Pass or Fail entry per evaluated stop, from the stop to the departure (or the end of the video).
- **Overlay log** (ndjson); an annotated video only with `--write-video`.

## Known issues and limits

- **The aircraft is not used.** Every stop of every GSE in view counts, near the aircraft or not (the README says "near the aircraft").
- **Bending counts for every orientation**, not only frontal as in the client rule; only "no bend" is frontal-only.
- **Side-on GSE:** a detected chock can be overruled by the difference classifier's "no chock".
- One not-chocked stop fixes the GSE as not chocked, even if later stops are chocked.
- The client's 75 % obstacle figure is not in the code; obstacles only stop a channel from answering, there is no separate "view blocked" verdict.
- Heavy pixel work: pose per person and GSE; up to 24 + 8 full frames buffered per stopped GSE, not released at departure.
- Uses private tracker counters (`_static_frames`, `_moving_frames`, `_stopping_time_thres`, `_display_proceeding_time_thres`): a tracker change can shift stop and departure moments.
- RTMPose gets BGR pixels with RGB-ordered normalisation (effect to confirm). CPU or GPU in production: to confirm.
- The client sheet marks the check as not production-ready.

## For developers

- **Repository:** `dxgat/detectors/gse-chocks`; production line `per_component_improvement` @ `d3f92a5`; default branch `master` @ `3160b87` (2025-06-19), the branch point (no tilt logic, no frame-edge veto, bend threshold 0.62, angled GSE treated as side-on).
- **Entry point:** `main.py` → `detect(...)`; `main.py` holds `GSEChocksAnalyzer` (orientation, observability, chock, human-action and difference parts) and `get_gse_report`. `complex_difference.py` — classifier input; `simple_difference.py` — static-scene test; `onnx_model_utils.py` — RTMPose; `visualization_overlay.py` — drawing. Flowcharts in `assets/`; logic diagram (Confluence, 2023): https://docs.google.com/spreadsheets/d/1-3OqjTuwGtddmwzO19QRV2YES-YB57ADFYQP5KdDI2Q/edit?gid=0#gid=0
- **Dependencies:** `cv_common` @ `dd5b554`, `db_worker` @ `5a4aa83` (exported copy; the local export substitutes cv_common `ac5098d`). Packages: torch 2.5.1, timm 0.6.12, onnxruntime-gpu, opencv-python, norfair. Weights (DVC, `gs://cv_weights/DVC`): `effnetb0_small_clean_64_960.pt`, `rtmpose-l-4dba18fc.onnx`.
- **Run locally:** `python main.py --source <video.mp4> --inferences-dir <dir> --weights-dir weights [--cone-camera] [--local-inferences] [--write-video] [--debug-all] [--timestamps …]`; settings in `local_config.yaml` over `cv_common/global_config.yaml`.
- **Code references:** step 1 `main.py:1750-1781`; step 2 `main.py:236-408`; step 3 `main.py:444-583`; step 4 `main.py:593-642`; step 5 `main.py:659-927`, `onnx_model_utils.py:9-22`; step 6 `main.py:1046-1489`, `complex_difference.py:140-147`, `simple_difference.py:40-51`; step 7 `main.py:1563-1594`; step 8 `main.py:32-76, 1937-1947`.
