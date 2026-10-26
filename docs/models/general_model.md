# General Model

> The General Model (GM) is the shared detector of the system. For every frame of a camera's full-turn video it writes
> where the aircraft, its parts, people, vehicles, cones and chocks are, and it reports the camera type, the arrival
> frame, the aircraft type and the airline.

## At a glance

| | |
|---|---|
| What it does | Detects objects on every frame; finds the main aircraft and gate obstacles; classifies camera (cone or wing), aircraft type, airline |
| When it runs | Once per camera video, after the merge job, before the trackers |
| Production version | `pf/q4-02-gm-exact-speedups-a0157a4`, built as **b6e1a3e** (2026-10-22): production code a0157a4 + speed-ups + image fixes; in production since October 2026 |
| Runs on | One job per video: one NVIDIA T4 GPU, 3.3 vCPU, 8 GiB, Google Kubernetes Engine node pool `gpu-pool` |
| Time per video | About **1.76 h** for a median 87-minute video (2.4 h before the speed-ups) |
| Outputs | Per-frame detection file (`gs://cv-modules-topics`), report message to the receiver, annotated video (on by default), job log |
| Used by | The trackers and the 27 check modules (the file); the receiver (the report); the module jobs also get the camera and aircraft type as arguments |

## What it detects

| Model / head | Input size | Classes or output | Weights file |
|---|---|---|---|
| GM head: YOLOv8n-size (3.1 M parameters) despite the "m" in its name; all heads ONNX, fp16 (half precision) | 1088×1088 (frame scaled to 1088×640, padded) | 25 classes (below), score > **0.35** | `GM_yolov8m_best_augmentation_march2024.onnx` |
| Chocks head: YOLOv8s-size (11.1 M) | 1280×1280 (1280×736, padded) | `chock` (25), > **0.10** | `chocks_v4.3_200ep_yolov8.onnx` |
| Vehicle head: YOLOv8m (25.8 M) | 1088×1088 | `vehicle` (31), > **0.40** | `VM_yolov8m_last_september2023.onnx` |
| Camera classifier: EfficientNet-B0 | frame rows 150–930 → 224×224 | ≥ 0.5 = cone camera, else wing | `camera_cls_effnet_b0_october_v1.8.1.pt` |
| MobileSAM (vit_t), in cv_common's motion analysis | frame + point prompts | main-aircraft outline → arrival, departure | `mobile_sam.pt` |
| Airline text: CRAFT text detector (CPU) + EasyOCR | full frame | text matched to 12 airline names | downloaded by the libraries |
| Tail livery classifier: small convolutional network | tail box → 224×224 | 16 airline classes | `general_tail_classifier.pth` |
| Aircraft type: a rule | wing and engine boxes | `AIRCRAFT` or `JET` | — |
| Aircraft tracker: Norfair 0.2.0, box overlap (IoU, intersection over union) | airplane boxes | tracks → main aircraft | — |

GM head classes: 0 person, 1 cone, 2 airplane, 3 beltloader, 4 gse, 5 pushback, 6 airplane_wing, 7 airplane_engine,
8 airplane_tail, 9 airplane_nose, 10 safety_vest, 11 camera_holder, 12 tow_bar, 13 fuel_truck, 14 trailer, 15 ladder,
16 wing_cone, 17 engine_cone, 18 tail_cone, 19 front_wheel, 20 back_wheel, 21 front_door, 22 back_door,
23 beltloader_cone, 24 air_conditioning. The code adds 25 chock, 29 obstacle, 30 side_obstacle, 31 vehicle and a
class-2 main-aircraft row. Names are from cv_common's master copy; the ids match production files.

## How it works

### First run

1. Decode each frame (OpenCV via cv_common). Every **48 frames** (6 s) estimate the noise; smooth frames of noisy videos.
2. Run the three heads on the GPU: scale and pad, BGR → RGB, fp16, threshold, then remove overlapping boxes across
   classes (non-maximum suppression, IoU **0.7**).
3. Write the boxes to the first-run file (it stays in the pod).
4. Track aircraft boxes at least **150 px** high and **10 %** of the frame. Of two boxes overlapping by more than
   **70 %** the larger is dropped; a new track overlapping a known aircraft by more than **50 %** continues its history.
5. Count how often each nose, front-wheel and wing box appears.

### Second run

1. **Main aircraft** = the track on the most frames (none → error report). **Height mode** = its most common box
   height, rounded to 10 px.
2. **Parts layout:** the largest nose and front-wheel boxes seen on more than max(10th-highest count, **240 frames**,
   30 s) frames; the wings give two side zones at the wing tips.
3. Decode again; read each frame's rows back, round down to whole pixels, clip, drop raw airplane boxes.
4. **Obstacles:** belt loader, GSE (ground support equipment), pushback, tow bar, fuel truck, trailer, ladder and
   non-overlapping vehicle boxes over **7 000 px²** that reach left of or below the main front wheel become
   `side_obstacle` (over **70 %** in a side zone) or `obstacle`.
5. Add the main-aircraft row on each frame of its track; write the frame to the second-run file — **the uploaded file**
   — and, if on, to the annotated video.
6. Follow the main aircraft's motion (cv_common: optical flow, MobileSAM) to find arrival and departure.
7. **Aircraft type:** per frame, the best wing and engine boxes at least 50 % inside the aircraft; an engine bottom
   above the wing's votes `JET`, below votes `AIRCRAFT`. Votes stop at departure; a **10 s** absence before arrival
   resets them.
8. **Camera type:** after arrival, each frame with the main aircraft is classified.
9. **Airline:** every **2 s** during the first **60 s** of the main aircraft, read text and match names, else classify
   the tail; keep the most common answer.

### Report

1. Camera type = majority vote; `confidence_camera` = the winning share. Aircraft type, if still open: more `JET`
   votes → `JET`, otherwise `AIRCRAFT`.
2. Stages from the main track: pre-arrival (before it, if at least **240 frames**), arrival to departure (the track),
   departure (after it, if at least **720 frames**, 90 s), full turn. Belt-loader stages are always `false`.
3. Statistics: the share of frames with each listed class per stage (none under **480 frames**, 60 s). Video
   selection: a text file in the pod.
4. Upload the annotated video, send the report, then upload the gzipped second-run file and the log.

## What it reports

### Per-frame rows

One JSON line per frame, `{"<n>": [row, ...]}`, numbered from 1 in decoding order. A row is
`[x1, y1, x2, y2, confidence, class_id]` in pixels of the 1920×1080 frame, grouped: GM head, chocks, vehicles,
obstacles, main aircraft. Frame 42 199 of a production file (a0157a4; the speed-ups do not change rows), wrapped:

```
{"42199": [[1691.0, 516.0, 1712.0, 565.0, 0.4111328125, 1], [1900.0, 563.0, 1918.0, 572.0, 0.1973876953125, 25],
  [1902.0, 562.0, 1920.0, 574.0, 0.171875, 25], [277.0, 331.0, 1818.0, 1052.0, 0.96728515625, 31],
  [1885.0, 493.0, 1920.0, 588.0, 0.76416015625, 31], [277.0, 331.0, 1818.0, 1052.0, 0.76416015625, 29],
  [22.0, 319.0, 1063.0, 538.0, 580, 2]]}
```

A cone, two chocks, two vehicles; the obstacle (29) copies the first vehicle's box with the second vehicle's
confidence; the aircraft row (2) holds the height mode, 580 px.

### Report message

Sent at the end to the Kafka topic in `receiver_topic`, with `process_status` (`processed` or `error`),
`processing_time` and:

| Field | Meaning |
|---|---|
| `camera_type` | `true` = cone, `false` = wing, `null` = no votes |
| `confidence_camera` | Winning share, 0–1 (1.0 with no votes) |
| `frame_stopped` | Arrival frame of the main aircraft, or `null` |
| `airplane_type` | `AIRCRAFT`, `JET`, or `null` (no votes and the aircraft never in view **120 frames**, 15 s, in a row) |
| `entity` | `[airline, share]` or `null` |
| `fps`, `number_of_frames` | From the video header |
| `detection_statistics` | Shares per stage, plus the stage frame ranges |
| `stages` | Always `null` |
| `video_name`, `log_filename` | The video and the log path |

### Files

- `gs://cv-modules-topics/<video>.mp4/general_model<commit>.ndjson` — the second-run file, **gzip** inside. `<commit>`
  is `git rev-parse --short HEAD` in the image: `b6e1a3e` now, `a0157a4` before. Old files stay; consumers read the
  newest unless `general_model_inferences_version_commit` names one.
- `gs://<output_bucket>/gm-output-<date>-<video>.mp4` (annotated video) and
  `gs://cv-modules-logs/<video>.mp4/general_model-<date>.logs` (job log).
- In the pod only: the first-run file, the selection text file, `entity.png`.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `conf_thres` | 0.35 | Minimum score of GM-head boxes |
| `airplane_min_height` | 150 px | Smaller airplane boxes are not tracked |
| `video_selection.check_camera_motion` | `false` (new) | `true` restores the third decode that looks for camera movement |
| other `video_selection` keys | 300 s per stage; shares such as airplane 0.9 | Change only the selection text file in the pod |
| `chock_conf_thres`, `vehicle_conf_thres` (cv_common) | 0.10, 0.40 | Minimum scores of chocks and vehicles |
| `fps` (cv_common) | 8 | Turns every "seconds" rule into frames |
| `tracking.airplane` (cv_common) | Norfair distance 0.8; 24 still frames (3 s) = stopped | Aircraft tracking and motion state |
| `GM_VERBOSE` (environment) | unset | `1` brings back the per-frame print lines |
| `--write_video` (job argument) | `true` | Writes and uploads the annotated video |

## The October 2026 speed-ups

Two code commits on a0157a4 (2259608 skips unused work; 8d8c9a4 makes the camera-motion pass opt-in) and three image
commits (727a474, bb9c0f2, b6e1a3e).

**What was removed**

- First-run motion analysis of every tracked aircraft (optical flow, MobileSAM, counters) and its frame copy: only the
  boxes were read.
- Tracker FAST/ORB features (never compared); an unused float32 GPU frame copy in the second run.
- Loading the retired airline detector; the camera classifier's ImageNet download (its checkpoint overwrites it).
- The CPU float32 conversion: the 8-bit frame is uploaded (6 MB, not 24 MB) and becomes fp16 on the GPU, same values.
- A frame copy per head; the two 1088 heads share one prepared frame.
- A GPU-to-CPU wait per detection value (now one copy per head).
- About ten print lines per frame (now behind `GM_VERBOSE=1`).
- The camera-motion pass: a third decode feeding only a text file in the pod (now opt-in).
- Image: onnxruntime-gpu 1.16.2 → 1.16.3, fastrlock 0.8.3 and pathspec 0.11.1 pinned, Ultralytics' font baked in.

**How it was proved**

- `scripts/gm_prod_profile.py` (prime_flight repository) runs `detect()` of both checkouts unchanged, with seeded random
  numbers, and compares every output (detection files, report, annotated video, selection file): byte-identical on a
  6-minute slice and, three times, on a 36-minute event.
- Cluster, 2026-10-22: production image vs b6e1a3e on five videos, started together: every GM file byte-identical
  (sha256 after gunzip).

**Measured result**

- GM job: 799 → 589 min over the five videos, **−26 %** (−18 to −33 % per video).
- Median 87-minute video: GM 2.4 → 1.76 h; GM + trackers + modules 4.8 → 4.16 h, **−13 %**; cost per hour of video
  **10–13 % lower** (1.84–4.59 $ → 1.60–4.05 $).

## Known issues and limits

- **Report fields vary between runs.** cv_common's motion analysis uses unseeded random numbers, so `frame_stopped` and
  `confidence_camera` (in close cases the camera or aircraft type) differ between runs; compare detection files.
- **cuDNN search.** `cudnn_conv_algo_search: DEFAULT` works on the T4 (cuDNN 8.2); on an RTX 5070 Ti with cuDNN 9.19
  every convolution fell back to a 2.6× slower path. Check before any GPU or base-image change (Azure).
- **Two image stacks.** Production is the a0157a4 image (Python 3.8, `gpu_base:legacy_base`, cuDNN 8.2.4, cv_common
  d74eb09). The branch head d4ae8e5 (Python 3.10, torch 1.13.1, onnxruntime-gpu 1.15.0, cv_common ac5098d) is not
  deployed. They pair 99.95 % of detections, not byte for byte: compare GM versions inside one image.
- **Misleading values.** Obstacle rows carry a leftover confidence (see the example above).
- **Whole video only.** Main aircraft, layout and stages need the full video: no chunk mode as it is. No schema
  version; the frame number is the line position.
- **Report gaps.** `stages` is always `null`; belt-loader stages are always `false` (door boxes are never collected);
  the noise fields are not sent; `entity` is a pair, not a string.
- **Airline quirks.** The two classifiers spell some airlines differently (`american_eagle` / `american eagle`,
  `southwest` / `Southwest`). With no airline after 60 s, `entity.png` is rewritten on every later frame.
- **Failures.** A main nose or wheel without any wing detection would crash at `main.py:728` (code reading). The
  `processed` report precedes the upload; a failed upload adds an `error` report.
- **To confirm.** cv_common d74eb09 is not readable to us: class names, weight names, thresholds, tracker settings and
  the arrival rule here are from master ac5098d. Also: whether production writes the annotated video (about 12 ms per
  frame); whether CRAFT and EasyOCR weights download at every start; the onnxruntime-gpu in the a0157a4 image (1.16.2 in
  its requirements).

## For developers

- **Repository:** `dxgat/detectors/general_model`. Production: `pf/q4-02-gm-exact-speedups-a0157a4` @ b6e1a3e, on
  a0157a4 (`deployment_v_py3_10`, 2025-09-04). Not deployed: that branch's head d4ae8e5; `pf/q4-02-gm-exact-speedups`
  @ afaebf1 (the speed-ups on d4ae8e5); `master` @ 13a4ddc. Read-only copies: `external\_pins\general_model`,
  `external\general_model_prod` (a0157a4 + weights) under `G:\prime_flight`.
- **Entry point:** the job (`test-gm.yaml`) runs db_worker's `model_starter.py --source=<video>.mp4
  --model=general_model --device=gpu --report_topic=$receiver_topic` (Python 3.8): `dvc pull`, video download,
  `main.detect()`, report, uploads.
- **Key files:** `main.py`; `scripts/` (`new_model.py` heads, camera, aircraft type, `entity/` airline);
  `local_config.yaml`; `weights.dvc`.
- **Dependencies:** `gpu_base:legacy_base` (Python 3.8; torch unpinned), cuDNN 8.2.4, onnxruntime-gpu 1.16.3, timm
  0.6.12, MobileSAM @ 01ea8d0f, dvc 3.4.0, easyocr 1.7.1, ultralytics 8.0.175, norfair 0.2.0. Submodules: cv_common
  **d74eb09** (not readable to us; `external\cv_common` is master ac5098d), db_worker 2fd7325 (readable). Weights:
  DVC, 9 files, 211 MB, `gs://cv_weights/DVC`.
- **Run locally:** `python main.py --source <video>.mp4 --weights <dir> [--save-video]` with the submodules and
  `dvc pull` (the README's `--weights-dir` is wrong); a CUDA GPU is required.
- **Test a change on the cluster:**
  1. Put the change on the production commit, not a branch head.
  2. Build it as the production image with the changed files and `.git` swapped; without the new `.git` its output is
     named a0157a4 and overwrites production's files.
  3. Run both images on the same 3–5 videos, same node type, started together.
  4. Compare after gunzip (`gsutil cat … | gunzip | sha256sum`): gzip stores the file time, so bucket md5 differs.
  5. Time = job start (log name, UTC) to the ndjson upload.
  6. For trackers and modules set `general_model_inferences_version_commit=<commit>.ndjson` (with the extension).
     Tracker files are named by the tracker's commit, so two tracker runs on one video overwrite each other.
- **Code references:** `main.py:37-42` (session options), `541-698` (first run), `705-740` (main aircraft, layout),
  `787-976` (second run), `978-1151` (report); `scripts/new_model.py:296-448` (heads); db_worker 2fd7325
  `model_starter.py:73-143`, `ML_worker.py:210-380`, `send_report.py:61-131`.
