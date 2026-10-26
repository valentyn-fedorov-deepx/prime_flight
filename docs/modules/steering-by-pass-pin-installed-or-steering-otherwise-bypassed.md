# M26 · Steering by-pass pin installed, or steering otherwise bypassed

> The module checks that, within 4 minutes after the aircraft arrives, a worker installs the steering by-pass pin at
> the nose gear or uses the by-pass switch. It watches workers who stop next to the nose wheel, runs a body-pose model
> on a 25-s clip around each stop, and lets its own time-series classifier decide whether the movement was a pin
> installation.

## At a glance

| | |
|---|---|
| Checks | M26 · Steering by-pass pin installed, or steering otherwise bypassed |
| Stage | Arrival, Post-arrival |
| Looks at | From the tracker's arrival frame (aircraft stopped for about 4 s) until 4 min (1920 frames) later |
| Cameras | Cone camera, aircraft only (no camera for jets in the client split); the camera flag is ignored |
| Uses | General Model (GM) boxes: front_wheel (person and chock boxes are collected but not used). Tracks: airplane, person. Video frames: yes (buffered for the pose model) |
| Own models | Pin-installation classifier (InceptionTime via tsai, `model_newaug.pkl`, with its fitted scaler `scaler.gz`): labels a 200-frame pose sequence LEFT_PIN, AUTO_PIN or NOTHING. Also runs the stock HRNet-W48 COCO pose model (mmpose) |
| Runs on | GPU |
| Real time | ready, needs video frames — pose runs on buffered frames; a decision comes 12.5 s after the stop, a Fail only at arrival + 4 min |
| Production version | master @ 60dca73 (2025-06-19) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | The pin is installed during the 4 minutes after arrival (in the first minute after arrival, or until the installation, the chock installation is checked as well). |
| Fail | The pin is not installed during the 4 minutes after arrival. |
| Not observed | The front wheel was not seen for 1 minute after the aircraft stopped, or there was no pre-arrival stage. |
| Not observed — view blocked | There are obstacles for more than 1 minute after arrival. |

## How it decides

1. **Arrival stage.** The aircraft is restored from the tracker on each frame. An arrival stage exists if, before stopping, it moved smoothly for more than **24 frames** (3 s) in a row (mean optical-flow shift ≤ **50 px** across and ≤ **5 px** vertically per frame).
2. **Start.** The module waits for the tracker's arrival frame. Without an arrival stage it stops 5 s later with Not observed.
3. **Pin area.** For the next **1920 frames** (4 min) it counts frames without a front_wheel box, keeps the last **200 frames** (25 s) in memory, and averages the largest nose-wheel box. Around the wheel bottom it builds the pin area (1.5 wheel heights left to 2.85 right, 0.5 above to 0.65 below) and a second target about 1.35 wheel heights to the right, at the by-pass switch.
4. **Stops.** For each person track it follows the foot point and its speed, scaled to the wheel size, vertical motion weighted ×4, smoothed over **5 frames**. A person in the pin area slower than **5** for at least **5 frames** in a row is "stopped"; the distance to the wheel or switch is recorded.
5. **Clip.** **100 frames** (12.5 s) later, if the stop's closest point to the wheel or switch was exactly 100 frames back, it builds a **200-frame** (25 s) clip centred there: HRNet-W48 pose of the person per frame (crop enlarged, brightness equalised), the person box relative to the wheel, 17 keypoints relative to the ankles; gaps filled, smoothed and scaled.
6. **Classification.** LEFT_PIN (pin at the nose gear) or AUTO_PIN (by-pass switch) gives **Pass**; the module stops 5 s later. NOTHING keeps it watching.
7. **Verdict** at arrival + 4 min, or at the end of the video: Pass if a pin was found; otherwise **Not observed** if the nose wheel was missing on more than **480 frames** (60 s) in total; otherwise **Fail**. No arrival, or no arrival stage → Not observed.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `pin_installation_thresh` (code) | 1920 frames (4 min) | The window after arrival |
| missing-wheel limit (code) | 480 frames (60 s) | Frames without a nose wheel that turn Fail into Not observed |
| `velocity_threshold`, `min_stop_frames` (code) | 5.0, 5 frames (0.6 s) | When a person counts as stopped |
| `filter_kernel_size` (code) | 5 frames | Speed smoothing |
| `x_scale`, `y_scale`, `height_ref` (code) | 1, 4, 74 px | Speed scaling: vertical ×4, normalised to a 74-px wheel |
| `window_size` (code) | 200 frames (25 s) | Clip length; decisions come 100 frames (12.5 s) after the stop |
| pin area (code) | −1.5…+2.85 wheel heights across, −0.5…+0.65 vertically | Where a stop counts |
| installed labels (code) | LEFT_PIN, AUTO_PIN | Classifier labels that mean Pass |
| `pose_config`, `pose_checkpoint` | HRNet-W48 COCO 256×192 | The pose model |
| `classifier_weights`, `scaler_weights` | `model_newaug.pkl`, `scaler.gz` | The pin classifier and its scaler |

## What it reports

- Pass: "Pin was installed by worker N. (HH:MM:SS - HH:MM:SS)", ±20 s around the decision frame. Fail: "Pin was not installed during 4 mins after plane arrival." (arrival to arrival + 4 min). Not observed: "The front wheel was obscured for more than 1 minute!", "Airplane arrival was not detected" or "There was no arrival stage on video".
- Smart timeline: Pass — the decision frame ±160 frames (±20 s); Fail and the hidden-wheel Not observed — arrival to arrival + 1920 frames, both labelled "Fail"; other Not observed — empty. Start / End are text.
- Overlay file (.ndjson); an annotated video with `--write-video`; with `--write-clips`, a plain clip, a pose-annotated clip and the pose series of every classified stop.

## Known issues and limits

- The client's chock condition (chock installation checked in the first minute or until the pin) is not implemented; chock boxes are collected but not used.
- Obstacles are not checked, although the client rule and the README name them. Not observed comes only from frames without a nose wheel, counted over the whole 4 min (client: "1 minute after the stop"). The client says "no pre-arrival stage"; the code checks an arrival stage.
- The hidden-wheel Not observed carries a smart-timeline entry labelled "Fail".
- Decisions lag 12.5 s, so a stop in the last 12.5 s of the window is never classified. If the video ends before arrival + 4 min, the module still decides (Fail when no pin was found).
- Workers are followed only after a nose wheel has been seen once.
- When the 200-frame buffer is full, clip frames and person boxes are paired one frame apart (to confirm the effect).
- Memory and compute: 200 full frames (about 1.24 GB) are held, and one clip runs the pose model up to 200 times, one person at a time.
- The `hrnet_w48_coco_384x288_dark` weights and config in the repository are unused.
- M16 (pin-verification, pre-departure) checks a related action with a rule-based pose method; the overlap is to cross-check.

## For developers

- **Repository:** `dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed`; production line `master` @ `60dca73`; default branch `master` @ `60dca73` (the same). `steering_observability_fix` @ `45db11e` (2026-08-14, 4 commits ahead) is feature work, not in production: it stops defaulting to Fail when the pin area was not observable.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, cone_camera, weights_dir, json_logger, write_clips)`; `cone_camera` is unused (the README: the task always runs on the cone camera). `Plane` (arrival-stage rule), `PinInstallationAnalyzer` (pin area, stops, clips, classification), `get_report`. Diagram `.doc/new_pin_installation.svg`; logic diagram (Confluence modules database, 2025-04-04): https://docs.google.com/spreadsheets/d/1oNYniaG6EO67tgz5ZI9npZutjVbZgBKnq3Z-WWrjRbw/edit?gid=827748110#gid=827748110
- **Dependencies:** `cv_common` 8e3a7bf, `db_worker` 5a4aa83 (`git ls-tree HEAD`); the local folder holds `cv_common` ac5098d as a stand-in. mmpose 1.3.1, mmcv 2.1.0, mmdet 3.2.0, mmengine 0.10.4, tsai 0.3.9, fastai 2.7.18, joblib 1.4.2, norfair 0.3.1; Docker base `mmpose_base`. Weights in DVC: `td-hm_hrnet-w48_8xb32-210e_coco-256x192-0e67c616_20220913.pth`, `model_newaug.pkl`, `scaler.gz`.
- **Run locally:** `python main.py --source <video>.mp4 --weights-dir weights [--device cpu] [--write-video] [--write-clips] [--local-inferences --inferences-dir <folder>] [--save-csv]`.
- **Code references:** arrival-stage rule `main.py:198-228`; arrival wait, missing arrival stage `:773-787`; 4-min window `:790-801`; missing-wheel count `:804-807`; pin area `:308-343`; speed and stops `:345-436`; stop sequences `:452-493`; clip and pose `:495-612`; classification `:614-640`; Pass `:861-869`; verdicts `:34-53, 880-887`.
