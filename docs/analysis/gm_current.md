# General Model (U02) — what it really does today

Read-only code analysis for rebuilding GM into a chunk-wise (streaming) component with a bitwise-compatible or explicitly versioned
per-frame output. Sources: `external/general_model` @ `13a4ddc` (master, 2024-06-07 "fix onnx corrupted outputs"),
`external/db_worker` @ `5a4aa83` (master; differs from the GM pin `2fd7325e` only in the README — `git diff --stat`),
`docs/04_modules.md` §U02, `docs/03_components.md`, `docs/arch_review/REVIEW_DETAILED.md:915-949`, real prod ndjson in
`G:\gat_stages\atlc5_inferences\`. Paths below are relative to `G:\prime_flight\external\` (`main.py` = `general_model/main.py`,
`ML_worker.py` = `db_worker/ML_worker.py`).

**Important limitation:** `cv_common` (GM pin `d74eb096`) is absent from disk — the submodule directories in all clones are empty,
`G:\deepx_gat` has been deleted. Everything that lives there (`global_config.yaml` with `str2id`, `LoadImages`, `ImagePreprocessor`, `Airplane`,
`BboxStabilizer`, `parse_config`) is described only from its usage in the GM code and from the actual data — see §11.

---

## 1. Entry points and launch modes

**What a job is.** One GM job = one full-turn video of one camera (`--source <video>.mp4`) → one per-frame ndjson into the bucket +
one report into the receiver's Kafka topic. There is no per-chunk or per-event mode whatsoever.

**Prod launch (K8s Job, `general_model/test-gm.yaml`).** Image `us-central1-docker.pkg.dev/rampvision-2/modules/general_model:latest`
(`test-gm.yaml:18`), a node with `nvidia-tesla-t4` (`:14`), 1 GPU / 3.3 CPU / 8 GiB (`:53-58`), env `videoname`, `model_name`, `device`,
`NODE_ID`, `POD_ID`, `service_dns` + ConfigMap `ml-config` + Secret `credentials` (`:26-51`). Command (`:60-65`): write
`$GCP_CRED` to `/config/bucket.json`, `mkdir ./weights`, **copy `db_worker/model_starter.py` into the root** and run
`python3.8 model_starter.py --source=<video>.mp4 --model=general_model --device=gpu --report_topic=$receiver_topic`.

**`model_starter.py` (db_worker) — the real entry point.** CLI (`model_starter.py:337-349`): `--kafka_ip`, `--report_topic`,
`--source`, `--output`, `--model`, `--weights_dir` (default `./weights`), `--device` (default `cpu`), `--camera_type`,
`--airplane_type`, `--restart`, `--write_video` (**default `t` = True**, `:348`). Sequence in `__main__` (`:350-405`):
1. `prepare_config_for_production()` — `sed` over `./cv_common/global_config.yaml`: `DIVX→avc1`, `mkv→mp4` (`:45-53`).
2. `pull_weights()` — `dvc pull` into `./weights` (`:58-69`).
3. Download of the video from GCS `source_bucket` (fallback `old_source_bucket`) into `storage/<video>` (`:372-388`).
4. `start_general_model()` (`:73-143`): `get_video_info()` opens the video once more for the sake of `nframes`/`fps` (`:36-40`);
   `VideoWorker(model_name='general_model', source, load_tracks=False, load_from_file=True, testing=True,
   auto_download_inference=False)` (`:86-87`); `from main import detect` (`:89`); `detect(...)` under `torch.no_grad()`
   (`:92-100`); assembly of `description` (`:102-110`); if `write_video` — upload of the annotated video (`:112-121`); Kafka report
   `ModuleReport.GENERAL_MODEL` with status `processed` (`:123-127`); `video_worker.close()`;
   `upload_infereces_to_cloud_storage("general_model")` (`:132`). Any exception → report with status `error` (`:133-140`).
5. Log `execution_logs.log` → `gs://cv-modules-logs/<video>/general_model-<date>.logs` (`:392, 405`).

**Local launch (`main.py:1077-1100`).** `--source`, `--output-path`, `--device`, `--weights` (the README describes `--weights-dir` —
a discrepancy, `README.md:66` vs `main.py:1083`), `--testing` (always True via `set_defaults`, `:1087`), `--inferences_dir` (not
used), `--save-video`. Creates `VideoWorker(source, model_name='general_model', testing=True)` (`:1096`) and calls
`detect()` (`:1098-1100`).

**Main loop — `detect()` (`main.py:444-1074`), three passes over the video:**

| Pass | Lines | What it does |
|---|---|---|
| Initialization | `444-514` | SAM, 3 ONNX detectors, **three independent readers** `load_source()` (`475-477`), Norfair aircraft tracker (`488-491`), `BboxStabilizer`, `ImagePreprocessor` |
| FIRST RUN | `517-662` | per-frame: preprocessing → GM + chocks + vehicle detectors → writing of raw rows (`595`) → aircraft merging/tracking (`598-646`) → BL heuristic (`649-660`) |
| Between passes | `664-712` | main aircraft selection (`669-675`), parts layout and side-obstacle ROI (`678-697`), closing the ndjson and **reopening the same file for reading** (`710-712`) |
| SECOND RUN | `714-902` | **re-decoding of the video**; reads the first-pass rows (`765`), enriches them (obstacle/side_obstacle, main aircraft), entity, aircraft type, camera classifier; writes the second ndjson (`871`) |
| Tail | `904-1074` | camera voting, stages, statistics, `select_video()` (**third decoding**, `1055`), `return_dict` (`1071-1073`) |

Per-frame loop — `for frame_id, (path, img, im0s, vid_cap) in enumerate(dataset, 1)` (`517`, `745`): 1-based numbering, from the
first decoded frame.

---

## 2. Models

| # | Model / purpose | Weights (config key) | Framework | Input | Batch | Device | Thresholds | Where loaded |
|---|---|---|---|---|---|---|---|---|
| 1 | **GM YOLOv8** — all apron classes (per docs: `GM_yolov8m_best_augmentation_march2024`) | `config['general_model_weights']` (cv_common) | onnxruntime-gpu 1.16.2, CUDA EP, fp16 IO-binding (`scripts/new_model.py:231-439`) | 1088×1088 static; 1920×1080 → letterbox 1088×640 + pad 224 px top/bottom (`:330-352`) | 1 | `cuda:0` | conf 0.35 (`local_config.yaml:3`), NMS IoU 0.7 **class-agnostic** (`new_model.py:426`) | `main.py:463-464` |
| 2 | **Chocks YOLOv8** (docstring: `chocks_v4.3_200ep_yolov8` export imgsz=1280 half, `new_model.py:244`) | `config['chocks_model_weights']` | same | 1280×1280; content 1280×736 + pad 272 | 1 | cuda | `config['chock_conf_thres']` (per data ≈0.10, §3) | `main.py:467-468` |
| 3 | **Vehicle YOLOv8** — broad vehicle detector | `config['vehicle_model_weights']` | same | 1088 (default `new_model.py:233`) | 1 | cuda | `config['vehicle_conf_thres']` (per data ≈0.40) | `main.py:471-472` |
| 4 | **MobileSAM vit_t** — aircraft mask for the motion state (inside `cv_common.transport.Airplane.update_params`) | `weights_dir/mobile_sam.pt` (hard-coded, `main.py:454`) | torch (`mobile_sam` from GitHub commit `01ea8d0f`) | image per call (inside cv_common) | – | device | – | `main.py:452-459` |
| 5 | **Entity detector** — airline (6 classes: JetBlue/Allegiant/UnitedExpress/Breeze/American/Spirit) | `./weights/{config['entity_detector_weights']}` — **path relative to cwd**, not `weights_dir` (`main.py:716`) | torch `torch.load(...)['model']` (YOLOv5-style, `UModel`, `new_model.py:152-209`), fp16 | resize 1280×1280 **without letterbox** (`:191`) | 1 | cuda if available | conf 0.7, IoU 0.7, YOLOv5 NMS (`:153, 197`) | `main.py:716` (start of SECOND RUN) |
| 6 | **Camera cone/wing** — binary classifier | `config['camera_classifier_weights']` | timm `efficientnet_b0(pretrained=True, num_classes=1)` — **`pretrained=True` pulls ImageNet weights from the network at startup** (`main.py:719`), then `load_state_dict` (`:720`) | crop of rows `150:930` → 224×224, ImageNet norm (`classifier_utils.py:9-13, 36-39`) | 1 | device | sigmoid ≥ 0.5 → cone (`classifier_utils.py:44`, TODO "threshold has to be finetuned") | `main.py:719-723` |

Weights: DVC (`weights.dvc`: directory `weights`, 8 files, 210 865 680 bytes, md5 `96fb8549…`), remote `gs://cv_weights/DVC`
(`.dvc/config:1-4`); last update 2024-03-29 (`git log -- weights.dvc`). The file names are defined by `cv_common/global_config.yaml`
(not on disk, §11). ONNX session: `ORT_ENABLE_ALL`, CUDA EP with `cudnn_conv_use_max_workspace=1`, `cudnn_conv_algo_search=DEFAULT`
(`main.py:34-39`). The `YOLO8` class (ultralytics) in `new_model.py:212-228` is not used in `main.py`.

---

## 3. Per-frame output schema

**File format.** ndjson, one line per frame: `{"<frame_id>": [row, row, ...]}` — the key is a string, the value is a list of rows
(`ML_worker.py:286` `writerow({str(frame_id): frame_metadata})`). `frame_id` is the **internal counter `frame_ii`** of VideoWorker,
which starts at 1 in `init_writer` (`ML_worker.py:223`) and is incremented on every `model_pub` call (`:321`); the
`frame_id` argument passed by GM is **ignored** (`:309`). GM calls `model_pub` exactly once per frame in each pass
(`main.py:595`, `871`), so the key = the 1-based index of `enumerate(dataset, 1)`. An empty frame is `{"1": []}`. There is no
`schema_version`, no `frame_id` field, no fps and no header in the file.

**Two files.** The first pass writes `<inferences_dir>/general_model<video>.mp4.ndjson` (`ML_worker.py:192-193`) — raw rows.
The second pass, after `init_writer(file_prefix="second_run")`, writes `general_model<video>.mp4-second_run.ndjson` **into cwd**
(`ML_worker.py:213`, without `inferences_dir`). What is uploaded to the bucket is `self.ndjson_path['general_model']` (`ML_worker.py:374-380`),
i.e. **the second-pass file** — that is exactly what the tracker and the 27 modules read.

**Detection row:** `[x1, y1, x2, y2, conf, cls_id]` (length always 6 — verified on 930 527 rows of a real file).
- `xyxy` are absolute pixels of the 1920×1080 frame, `int` → `float` (`main.py:543, 551`), clamped by `correct_coords` to
  `[0..1920]×[0..1080]` (`main.py:202-217`); in the real data all coordinates are integer-valued, min/max = 0/1920, 0/1080.
- `conf` — `float` from the fp16 ONNX output (all 905 247 values ≤1 in the file are exactly representable in float16).
- `cls_id` — `int` from `config['str2id']`.

**Sources of rows in the second-pass file (`main.py:767-871`):**
1. All first-pass rows **except the `airplane` class** (`:773-774`): GM classes with conf > 0.35; chocks as `str2id['chock']`
   (`:583-586`), the vehicle detector as `str2id['vehicle']` (`:589-592`).
2. Copies of transport/vehicle boxes that passed the "our gate" filter, with class `obstacle` or `side_obstacle` (`:810-832`).
   **Defect:** `conf` in these rows is a leftover loop variable (`:768`/`:798` → `:823`/`:829`), not the confidence of the
   object itself; in the real file conf matches the conf of the source box in only 5 687 of 72 512 class-29 rows.
3. Exactly one main-aircraft row per frame within the range of its track: `[x1,y1,x2,y2, int(mode_plane_height), str2id['airplane']]`
   (`:851-854`) — **the fifth field = the height mode of the bbox in pixels (e.g. 680), not a probability** (attention note U02).

**Real record** (`G:\gat_stages\atlc5_inferences\general_modelAIjEAz70OfWCYG.mp4.ndjson`, 39 360 lines, keys 1…39360
monotonic without gaps), line 5000, first elements:
```
{"5000": [[698.0, 505.0, 828.0, 617.0, 0.9150390625, 7], [1433.0, 362.0, 1920.0, 536.0, 0.888671875, 6],
          [577.0, 583.0, 642.0, 635.0, 0.85302734375, 20], [255.0, 476.0, 371.0, 781.0, 0.85205078125, 0], ...]}
```
line 11150 contains the main aircraft: `[508.0, 44.0, 1608.0, 752.0, 680, 2]` (class-2 rows only in frames 11150…38233).

**Class list.** The verbatim `str2id` lives in `cv_common/global_config.yaml` and is **unavailable** (§11). Names referenced by the
GM code (27): `person, cone, engine_cone, wing_cone, tail_cone, beltloader_cone, airplane_tail, airplane_wing,
airplane_engine, airplane_nose, front_door, back_door, front_wheel, back_wheel, air_conditioning, beltloader, pushback, gse,
airplane` (`main.py:480-483`), `trailer, fuel_truck` (`:575-576`), `tow_bar, ladder` (`:789-790`), `chock` (`:586`),
`vehicle` (`:592`), `side_obstacle` (`:823`), `obstacle` (`:829`). Identifiers confirmed by the data / the stand's (test bench) code:

| id | class | evidence |
|---|---|---|
| 0 | person | IoU match with the tracker's `cls_str` (1306/1306) |
| 2 | airplane | match with the tracker + rows with the height in the conf slot |
| 3 | beltloader | match with the tracker (959) |
| 4 | gse | match with the tracker (761) |
| 5 | pushback | `gat-streaming/streaming/simulate.py:33` ("str2id from global_config") |
| 9 | airplane_nose | same place |
| 25 | chock | min conf in the file 0.1002 (≠ 0.35 GM) → separate threshold `chock_conf_thres`; median box 21×22 px; present in 38 916/39 360 frames |
| 29 | obstacle | 100 % of rows are exact copies of boxes of classes 12/3/31/15 in the same frame; median center x=1410 |
| 30 | side_obstacle | 100 % copies of boxes 4/14/31/3; median center x=66 px (edge ROI) |
| 31 | vehicle | min conf 0.4004 → separate threshold `vehicle_conf_thres`; present in 39 329/39 360 frames |

The remaining GM classes have ids 0…24 (min conf 0.3503 = the GM threshold); ids 22, 26, 27, 28 do not occur in the three checked files.
Judging by the duplicate boxes, ids 12, 13, 14, 15 are transport classes (`tow_bar/fuel_truck/trailer/ladder` in unknown order).
So `str2id` has ≥ 32 entries, the GM detector has ≈25 classes (0…24), and `chock`, `obstacle`, `side_obstacle`, `vehicle` are
synthesized ids added by `main.py` itself.

**How consumers read it.** `VideoWorker.__metadata_generator` takes `list(record.values())[0]` and zips GM and trackers **by
position** (`ML_worker.py:244-254`); the frame key is ignored. The stand does the same (`simulate.py:47-53`). The tracker produces a file with
the same number of lines (39 360 = 39 360 for the same video).

---

## 4. Per-video decisions (critical for chunks)

| Decision | Where | When / on what basis | Where it is written | Verdict for streaming |
|---|---|---|---|---|
| **Main aircraft** | `main.py:669-675` | after EOF of the first pass: the Norfair track with the largest number of frames; candidates are `airplane` boxes with height ≥150 px (`:547-548`), merging of overlaps >0.7 (`:598-609`), re-association of a new id with the history at overlay >0.5 (`:633-645`); none at all → `NoPlaneException` (`:675`) | class-2 rows in the second file only for the track's frames (`:851-854`) | **needs whole video** (argmax over all tracks) |
| **Aircraft height mode** | `:701-702` | mode of the heights rounded to tens over the whole track | 5th field of the aircraft row | **needs whole video** |
| **Parts layout** (main front wheel, nose, left/right wing) | `:555-562, 367-375, 378-415, 678-689` | after EOF: buckets of boxes with IoU >0.8, a part is "main" if it appeared in > max(10th by frequency, 30·fps) frames | not written directly; determines the obstacle ROI | **recomputable incrementally** with a freeze rule (≥240 stable frames); the "10th by frequency" rule is whole-video |
| **Side-obstacle ROI** | `:691-697` | from the wings: `[x0_left + 0.8·w, 0, 1920, 1080]`, `[0, 0, x0_right + 0.2·w, 1080]` | affects class 29/30 in every frame of the second pass (`:810-832`) | after the layout freeze — per-frame |
| **Camera type cone/wing** | `:879-897, 904-908` | classifier on **every** frame where `plane_available and main_plane.arrived`; majority vote after EOF; `confidence_camera` = the share (`:1062-1063`). The variable `n_frames_for_classification = 20 min` is declared and **not used** (`:734`) | `gm_report({"camera_type", "frame_stopped"})` (`:911`, in testing only print) and the final report `camera_type: bool` (`model_starter.py:102`) | **recomputable incrementally** (running majority), but the final value is after EOF; for streaming a rule "fix after N frames past the stop" is needed (ADR) |
| **`frame_stopped`** | `:874-875` | `main_plane.arrival_frame` from the `cv_common.Airplane` state (`arrived`), overwritten every frame | report `frame_stopped` | causal after the stop, **but depends on the main aircraft selection** (second pass) |
| **Aircraft type JET/AIRCRAFT** | `:881-886`; `scripts/engine_script.py:7-108` | after `arrived`: a vote every frame by 4 geometric checks (engine∩tail, engine∩rear wheel, engine above/below the wing, engine position on the wing, `:66-91`), `answer` when the type counter > 500 frames (`:103-106`); `airplane_type` is assigned only on the next frame after `answer` (`main.py:883-886`) | report `airplane_type: str|None` | **decidable from first N frames** after the stop (~62 s of votes) |
| **Entity / airline** | `:835-848` | from frame 8, every 8th frame (1/s @8fps) up to 40 detections, independent of the aircraft; decision: the sum of class_id ∈ {0:JetBlue, 40:Allegiant, 80:UnitedExpress, 120:'Breze', 160:American, 200:Spirit} otherwise `Undefined` (`:844-848`) — all 40 must agree | report `entity: str|None` | **decidable from first N frames** |
| **Stages** | `:921-951` | `pre_arrival=(1, first_plane_frame)` if ≥241 frames; BL stages (`:930-943`) are **always False**: `front_door`/`back_door` are initialized to `[]` every frame (`:522`) and never populated → `check_if_bl_came` returns immediately (`:112-120`) [INPUT-GAP U02.19]; `from_arrival_till_departure=(first, last plane frame)`; `departure` only if ≥720 frames after the track (`:947-950`); `fullturn=(1, last_frame)` | report: inside `detection_statistics` (`model_starter.py:107`); the report's `stages` key = `None`, because `results.get('stages')` reads a missing key (`model_starter.py:109` vs `main.py:1071-1073`) | **needs whole video** (end of the track, last frame) |
| **Class visibility statistics** | `:171-199, 959-1051` | the share of frames with the class within a stage; `None` if the stage is < 480 frames (`:182`) | report `detection_statistics` | **needs whole video**; per `render_dependencies.py:177` no module reads it (only the site) |
| **Video selection** | `:1053-1055`; `videos_selection_script.py:24-113` | thresholds on stage durations and detection shares (`local_config.yaml:7-25`) + a third decoding with frame-diff (`:60-88`) | only `report_video_selection_module.txt` (append, `:90-111`); not part of `return_dict` (U02.22) | whole video; **nobody needs it** |
| **Noise / broken** | `:526-535, 753-755, 1073` | `ImagePreprocessor` (cv_common) every frame | `video_type_by_noise`, `noise_mean`, `noise_std`, `is_broken` in `return_dict`, **do not make it into the report** (`model_starter.py:102-110`; `send_report.py:92-104` has no such keys, `validation` would throw a `KeyError`) | per-frame; lost at the job boundary |
| Obstacle/side_obstacle per frame | `:810-832` | transport with `bbox_area > 7000` and outside the front-wheel box; vehicle boxes are deduplicated against transport at IoU >0.7 (`:797-805`) | rows 29/30 | per-frame, after the layout |

Dependency chain: **raw rows → main aircraft (EOF) → layout/ROI (EOF) → second pass (obstacles, `arrived`,
camera, aircraft type, `frame_stopped`) → stages/statistics (EOF)**. Only entity is independent of it.

---

## 5. Side effects and I/O

| Channel | What | Where |
|---|---|---|
| GCS read | video `gs://<source_bucket>/<video>` → `storage/<video>` (fallback `old_source_bucket`) | `model_starter.py:372-388`; `ML_worker.py:102-125` |
| Decoding | `cv_common.utils.datasets.LoadImages(source, img_size=cv_config["img_size"])` (cv2.VideoCapture; `.nframes`, `.cap`) — **4 instances** per job: `get_video_info` + three readers in `detect` | `ML_worker.py:225-238`; `model_starter.py:36-40`; `main.py:475-477`; rtsp/http → `Exception("Stream is not implemented yet")` (`ML_worker.py:229-233`) |
| Local files | `../inferences_dir/general_model<video>.mp4.ndjson` (first pass), `./general_model<video>.mp4-second_run.ndjson` (second), `.gz` after `gzip -f`, `report_video_selection_module.txt`, `execution_logs.log`, `gm-output-<date>-<video>` (mp4) | `ML_worker.py:192-193, 213, 378`; `videos_selection_script.py:91`; `custom_logging.py:8`; `model_starter.py:91` |
| GCS write | `gs://cv-modules-topics/<video>.mp4/general_model<short-commit>.ndjson` (**gzip content under a .ndjson name**); commit = `Repo('./.git').rev_parse HEAD` of the GM repo — the only schema "version" (X3), requires `.git` in the image (`.gcloudignore: !.git`) | `ML_worker.py:359-380` |
| GCS write | annotated video → `gs://<output_bucket>/gm-output-…` (if `--write_video`, default True) | `model_starter.py:112-121` |
| GCS write | log → `gs://cv-modules-logs/<video>/general_model-<date>.logs` | `model_starter.py:405` |
| Kafka | report `send_to_receiver(report_topic, 'general_model', report)` — a new `KafkaProducer` per call, `bootstrap=<kafka_ip>:9092`; `Report{sender_id, contents{pod_id, node_id, processing_time, process_status, description}}`; `description` for GM: `camera_type, frame_stopped, fps, entity, number_of_frames, video_name, detection_statistics, log_filename, airplane_type, stages, confidence_camera` | `send_report.py:10-23, 53-55, 74-131`; `model_starter.py:75-79, 102-110, 123-127` |
| Kafka per-video topics | `general_model<video>` are created **only when `testing=False`** — the prod path uses `testing=True`, so this branch is dead; `gm_report()` in testing only prints | `ML_worker.py:179-185, 439-453` |
| MongoDB | **no access whatsoever**, neither in `general_model` nor in `db_worker` (grep `mongo` is empty, `pymongo` is not in requirements). The video/event doc is updated by the `receiver_topic` receiver (the orchestrator, outside these repos, §11) | — |
| stdout | ≈8 lines per frame in the first pass (`main.py:533, 535, 652-654`; `new_model.py:435-438` ×3 models) with `PYTHONUNBUFFERED=1` | — |
| logging | `set_logging` is defined, never called (`main.py:87-90`); `logging.info` (`:1064`) goes to the root logger without a handler | — |
| Network at startup | `dvc pull` (`gs://cv_weights/DVC`), `timm.create_model(pretrained=True)` (`main.py:719`) | — |

Env variables read by db_worker: `kafka_ip`, `receiver_topic`, `source_bucket`, `old_source_bucket`, `output_bucket`,
`module_inferece_bucket` (modules), `event_id` (modules), `general_model_inferences_version_commit` (in the GM branch it is read and not
used, `model_starter.py:82-84`), `trackers_inferences_version_commit`, `POD_ID`, `NODE_ID`, `STAGE`,
`GOOGLE_APPLICATION_CREDENTIALS` (via `test-gm.yaml:61-62`).

How GM uses db_worker: `VideoWorker.load_source` (three times), `model_pub` (every frame, both passes + `end=True`
`main.py:710, 1066`), `load_metadata` (`:711`), `init_writer("second_run")` (`:712`), `gm_report` (`:911`); model_starter additionally uses
`upload_infereces_to_cloud_storage`, `close`, `upload_to_bucket`, `download_from_bucket`, `send_to_receiver`, `ModuleReport`.

---

## 6. Assumptions that break on a stream of chunks

1. **Three full-file readers are opened before processing starts** (`main.py:475-477`) + `load_source` throws an exception on any
   stream URL (`ML_worker.py:229-233`). Chunk input is impossible without replacing `LoadImages`.
2. **Two-pass by construction:** the second pass reads the video from frame 1 and the first-pass ndjson (`main.py:710-712, 745, 765`).
   All enriched rows (obstacles, main aircraft) and all per-video decisions of the second pass exist only after EOF of the first.
3. **Main aircraft = argmax after EOF** (`:669-675`), the height mode over the whole track (`:701-702`); class-2 rows in the output file
   appear only in the second pass. On a stream the "longest track" is unknown until the end of the event.
4. **Parts layout after EOF** with the "10th by frequency or 240 frames" rule (`:392-395`) → obstacle ROI (`:684-697`).
5. **Stages are keyed on EOF:** `last_frame` (`:664`), `frame_of_ending` (`:704`), `departure` requires ≥720 frames after the track
   (`:947-950`), `fullturn=(1, last_frame)` (`:951`); per-stage statistics (`:959-1000`) and `find_the_percent` (`:171-199`).
6. **Camera voting after EOF** (`:904-908`); aircraft type — a counter up to 500 (`engine_script.py:105`); entity — 40 hits
   (`main.py:841`) — these three are incremental, but without an explicit "decided" moment.
7. **`NoPlaneException` only after EOF** (`:675`) — on a stream the verdict "there was no aircraft" does not arise in time.
8. **Third decoding** in `select_video` (`videos_selection_script.py:66-88`) and `dataset.nframes` for the fps estimate (`main.py:1070`).
9. **Frame numbering = the writer's call counter** (`ML_worker.py:223, 309, 321`), without an absolute `frame_id` (X2);
   consumers zip GM/trackers positionally (`ML_worker.py:244-254`). A dropped chunk shifts everything.
10. **Preprocessor state and gates depend on the pass boundary:** `ImagePreprocessor.update` accumulates history (`:526, 753`);
    in the first pass preprocessing is enabled from frame 1 (`airplane_detected=True`, `:514`), in the second — only after the
    main aircraft appears (`:743, 754-755, 864`); `YOLOv8_onnx` caches the letterbox geometry from the first frame (`new_model.py:330-356`).
11. **One Norfair tracker per video** (`:488-491`) — compatible with X1 only if the GM process lives for the whole event and is not restarted per chunk.
12. **The schema version is only a file-name suffix** (`ML_worker.py:367-369`): in streaming a `schema_version` in the record is needed (X3).

---

## 7. Performance profile (from code, without execution)

Stand (test bench) reference (`docs/02_target_architecture.md:69-80`, RTX 5070 Ti, core profile): decode 2.90 ms/frame, **GM detection
28.29 ms/frame @1088**, tracker 0.11; budget 125 ms @ 8 fps; 3.95× real-time on a full turnaround. This is **only one detector**;
the prod GM does far more per frame, and on a T4 at that (`test-gm.yaml:14`).

**FIRST RUN, per frame (`main.py:517-662`):**
- cv2 decode (+ an unused letterbox `img` inside `LoadImages`, `img_size` from cv_common — not verified);
- `ImagePreprocessor.update` (cv_common; `cucim`/`cupy` in requirements hint at GPU noise estimation — not verified);
- H2D: `torch.from_numpy(im0s).float().cuda().half()` — 1920×1080×3 float32 (≈24 MB) to the GPU, then to fp16 (`:529-532`);
- **three ONNX detectors** (GM@1088, chocks@1280, vehicle@1088): GPU preprocessing permute/÷255/bilinear/pad (`new_model.py:305-314`),
  `run_with_iobinding` fp16 (`:393`), GPU postprocessing + `torchvision.nms` (`:409-426`), then a **Python loop over indices with
  GPU scalars** `detections.append([*boxes[i], scores[i], classes[i]])` → `torch.tensor(detections).cpu()` (`:427-432`) —
  ≈6·N_det implicit synchronizations per model per frame (≈24 rows/frame in the real file); 2 `print`s per model (`:435-438`);
- Python loops over detections (`main.py:541-580`), `count_bbox_frames` with IoU over a dictionary (`:367-375`) — O(N_buckets) per box;
- Norfair `update` (`:613`) + **MobileSAM via `Airplane.update_params` for every tracked aircraft every frame**
  (`:629-642`; the cost is in cv_common, unknown — potentially dominant);
- `ndjson.writerow` (JSON serialization every frame, `ML_worker.py:286`), `prev_im0s = im0s.copy()` (`:662`, 6 MB/frame).
- Static square inputs: of 1088×1088 only 1088×640 is useful → **≈41 % of GM/vehicle compute goes to padding**; of 1280×1280 only
  1280×736 is useful → ≈42.5 % for chocks.

**SECOND RUN, per frame (`:745-902`):** repeated decode; the H2D copy `image_tensor` is created and **not used**
(`:757`); JSON parsing of the line (`:765`); obstacle IoU loops (`:797-832`); entity YOLOv5 `.pt` @1280 every 8th frame up to 40 hits
(PIL resize + python NMS, `new_model.py:186-209`); SAM for the main aircraft every frame (`:861`); EfficientNet-B0 on CPU PIL
transforms every frame after the stop (`:889`); `aircraft_determining` every frame (`:884`); if `save_video` — `cv2.VideoWriter` 1080p +
drawing of all boxes (`:759-762, 793-832, 899-902`) — **in the prod path `write_video` defaults to True** (`model_starter.py:348`), unless
the manifest overrides it (§11).

**Third pass** (conditional, when the video passed the filters): decode + `absdiff/GaussianBlur/threshold/findContours` on CPU
(`videos_selection_script.py:66-88`).

**Startup:** `dvc pull`, video download, 3 ONNX sessions + SAM + `torch.load` entity + timm from the network; `get_video_info` opens the
video separately (`model_starter.py:36-40`).

**Batching:** absent everywhere (batch=1, one frame per `predict`). **Obvious inefficiencies:** three full decodings;
the unused tensor in the second pass; per-row GPU→CPU synchronizations; padding of square inputs; per-frame print/JSON;
SAM every frame; the annotated-video encoder in prod; `prev_im0s.copy()`; the entity detector without letterbox (aspect-ratio distortion).

---

## 8. Configuration surface

**`general_model/local_config.yaml` (merged by `parse_config()` from cv_common):** `task: general_model`; `conf_thres: 0.35`
(GM detector threshold); `airplane_min_height: 150` (min aircraft bbox height for tracking, `main.py:547`); `video_selection.stages`
(min stage durations: pre_arrival/from_arrival_till_departure/departure = 300 s) and `video_selection.detections` (min shares:
prearrival.cone 0.2; from_arrival_till_departure: airplane_tail 0.5, airplane_engine 0.7, airplane_wing 0.5, airplane_nose 0.7,
airplane 0.9, front_wheel 0.8, pushback 0.1; fullturn: airplane 0.4, pushback 0.01) — all of it only for `select_video`.

**Keys from `cv_common/global_config.yaml` (file unavailable; by usage):** `fps` (`main.py:446, 734; engine/select`),
`width`, `height`, `fourcc`, `save_format` (`:446-447, 694-697, 1092`), `img_size` (`ML_worker.py:235`), `str2id`, `colors`,
`general_model_weights`, `chocks_model_weights`, `vehicle_model_weights`, `entity_detector_weights`, `camera_classifier_weights`,
`chock_conf_thres`, `vehicle_conf_thres`, `tracking.airplane.norfair` (kwargs of the Norfair `Tracker`, `:490`),
`tracking.airplane.tracked_object` (`:230, 857`); `status2id` (modules). `prepare_config_for_production` edits it with `sed`.

**Hard-coded in the code (not in config):**

| Constant | Value | Location |
|---|---|---|
| GM/vehicle · chocks input | 1088 · 1280 | `new_model.py:233`; `main.py:467` |
| NMS IoU (ONNX, class-agnostic) | 0.7 | `new_model.py:233, 426` |
| Entity: size/conf/IoU; stride; number of hits; sum map | 1280 / 0.7 / 0.7; every 8th frame; 40; `{0,40,…,200}` | `new_model.py:153`; `main.py:835, 841, 844` |
| Camera: crop, threshold | rows 150:930, sigmoid ≥ 0.5 | `classifier_utils.py:36, 44` |
| Aircraft merging / re-association / parts buckets | overlay >0.7 (removes the **larger** box, `:606`) / >0.5 / IoU >0.8 | `main.py:605-606, 637, 371` |
| Min frames for a "main" part | max(10th by frequency, 30·fps) | `main.py:392-395` |
| Side-obstacle ROI | 0.8·w of the left wing, 0.2·w of the right | `main.py:694, 697` |
| Gate transport: area; side-ROI intersection; vehicle dedup | >7000 px²; >0.7; IoU >0.7 | `main.py:814, 821-822, 803` |
| Aircraft type: votes until the answer | >500 frames | `engine_script.py:105` |
| BL heuristic (dead) | 130 px to the door, 16 frames | `main.py:129, 135, 142-160` |
| Stages: pre-arrival / BL offset / departure / min stage | 240 / 480 / 720 / 480 frames | `main.py:922, 931, 947, 182` |
| Frame size for clamp | 1080×1920 | `main.py:202` |
| SAM type/file; timm model | `vit_t`, `mobile_sam.pt`; `efficientnet_b0` | `main.py:453-454, 719` |
| Entity weights path | `./weights/…` (cwd) | `main.py:716` |
| Device | `'cuda:0'` unless `cpu`; but `.cuda()` is unconditional (`:529, 757`) — CPU mode is effectively non-functional | `main.py:450` |
| Kafka | `<kafka_ip>:9092`, timeout 30 s, batch 32768 | `send_report.py:13-23` |
| Buckets | `cv-modules-topics`, `cv-modules-logs`, `gs://cv_weights/DVC` | `ML_worker.py:325, 362`; `model_starter.py:405`; `.dvc/config` |

Dead/unused: `xyxy2xywh`, `set_logging`, `stabilize_obj_bbox`/`stabilize_aiplane_bbox`, `n_frames_for_classification`,
`temp_camera_type_cone`, `--inferences_dir`, commented-out k-mean/EMA blocks (`main.py:237-270, 303-357`),
`scripts/videos_selection_script_from_json.py`, the `YOLO8` class, `frame_temp` (`ML_worker.py:43-48`).

---

## 9. Dependencies

**`general_model/requirements.txt`:** Cython, matplotlib≥3.2.2, numpy≥1.18.5, pillow≥8.0.1, PyYAML≥5.3, scipy≥1.4.1,
tqdm≥4.41.0, pandas≥1.2.2, seaborn==0.11.1, cucim, cupy-cuda110==12.3.0, easydict, dvc[gs]==3.4.0, timm==0.6.12,
mobile-sam @ git+…MobileSAM@01ea8d0f, onnxruntime-gpu==1.16.2, scikit-image==0.18.3, ndjson==0.3.1, kafka-python==2.0.2,
pydantic==1.8.2. **`no_deps_req.txt`** (`--no-deps`): ultralytics==8.0.175, norfair==0.3.1. **torch/torchvision are not pinned** —
they come from the base image `us-central1-docker.pkg.dev/rampvision-2/new-base/gpu_base:latest`, python3.8, `libcudnn8=8.2.4.15-1+cuda11.4`
(`Dockerfile:1-11`). **`db_worker/requirements.txt`:** google-cloud-storage, kafka-python, pydantic==1.9.1 (installed after
1.8.2 and wins), requests, ndjson, GitPython.

**Imports from cv_common** (pin `d74eb096`, `git ls-tree`): `image_preprocessing.ImagePreprocessor` (`main.py:14, 505`);
`utils.plots.plot_one_box` (`:17`); `common.{bbox_area, bboxes_iou, get_hw, get_relative_intersection, parse_config,
check_output_path, xyxy_to_det_arr, iou_distance, get_center}` (`:18-19`) + `is_overlap` (`engine_script.py:1`);
`transport.Airplane` (`:20`); `detections.BboxStabilizer` (`:21`); `utils.datasets.LoadImages` (`ML_worker.py:36`;
`model_starter.py:16`); `log_utils.JsonLogger` (modules). **From db_worker** (pin `2fd7325e`): `ML_worker.VideoWorker` (`main.py:31`);
`model_starter` pulls in `upload_to_bucket`, `download_from_bucket`, `send_to_receiver`, `ModuleReport`, `get_logger`.
db_worker itself has a submodule `ml_setting` (`dxgat/ml_backend/ml_setting`), where `ml_global_config.json` describes the modules
(`cameras`, `device`, `seq_number`) — this is exactly where the `camera_type` from GM is turned into the set of modules (`parser.py:96-108`).

---

## 10. Recommendations for the rebuild (prioritized)

1. **Inference core `gm_core` (P0).** A pure function `frame → rows` for the three detectors with the same thresholds, letterbox,
   fp16 IO-binding and class-agnostic NMS — this is the precondition for bitwise parity of the raw rows. Right away: vectorize the row
   extraction (a single `.cpu()` instead of the loop, `new_model.py:427-432`), remove the per-frame print, cache a pinned H2D buffer, batching
   across cameras (N streams × 1 frame). A rectangular ONNX export (1088×640 / 1280×736) saves ≈40 % FLOPs but changes the output —
   only as a versioned change with a re-measurement of recall on a balanced sample, not as an "optimization without an ADR".
2. **Context component `gm_context` (P0), incremental, with `decided_at` events:** entity (40 hits), aircraft type (500
   votes after T_arr), camera type (fix after N frames past the stop — the natural candidate is the unused 20-min
   window, `main.py:734`; an ADR, because it changes the "majority over the whole video" semantics), parts layout (freeze after ≥240 stable
   frames), main aircraft (running longest track + a final value at the end of the event). `frame_stopped`/T_arr — the owner is the stage detector,
   GM does not duplicate it. Each decision is a separate record `{"frame_id": N, "decision": "...", "value": ...}` in the session, so that modules
   open with the correct `cone_camera` before the end of the video (`render_dependencies.py:162`).
3. **Two output adapters (P0).** (a) Bus record v2: `{"schema_version": "2.0", "frame_id": N, "general_model": rows}` with
   **raw** `airplane` rows (true conf) and without obstacle copies; (b) a **post-branch v1-compat writer** which, at the end of the
   event, reproduces the legacy second-pass file from the same raw rows and the final context (class-2 rows with the height mode,
   rows 29/30, numbering 1..N) — then the 27 modules and the tracker do not change, and parity with batch is verified bitwise on 8
   reference videos. The stale `conf` in rows 29/30 (`main.py:823, 829`) is to be reproduced as is in v1 (parity), and not carried over into v2.
4. **I/O adapters (P1):** source (file / chunk session per `gat-streaming/streaming/session.py`, gap-fill with placeholder frames), sink
   (ndjson v1, bus v2), report (Kafka for now; add the noise/`is_broken` fields that are currently lost, and fix `stages=None`),
   weights registry (an explicit list of files with hashes instead of cv_common keys; remove the cwd path `./weights/` and `pretrained=True`).
5. **Move out / disable (P1):** the third pass `select_video` (its result is read by nobody), the BL stage heuristic (dead —
   the doors are never populated), stages/statistics (no module reads them; their place is the stage detector or a separate post-job),
   annotated video — off by default.
6. **What must stay identical for compatibility:** the row format `[x1,y1,x2,y2,conf,cls]` with float-integer coordinates and
   clamp 0..1920/1080; class ids (including the synthesized 25/29/30/31); 1-based sequential numbering without gaps; the report fields
   `camera_type: bool`, `frame_stopped: int`, `entity: str`, `airplane_type: str`, `fps`, `number_of_frames`; the object name
   `<video>.mp4/general_model<commit>.ndjson` (gzip) in `cv-modules-topics`.
7. **What to measure for parity:** (i) raw rows — exact equality of the sets of 6-tuples on every frame; (ii) a histogram of
   counts per class per video + min conf per class (catches threshold/model drift); (iii) the frame range and the height of class-2
   rows; (iv) rows 29/30 (count, boxes); (v) report fields; (vi) the context's `decided_at` vs the batch value. X4 conditions: the
   same decoder on both sides, full turnaround, warm cache, idle machine; T4 vs 5070 Ti — separate columns.

---

## 11. Open questions

1. **`cv_common@d74eb096` is not on disk:** the verbatim `str2id` (§3 covers 10 ids out of ≥32), the weights file names (8 in DVC),
   `fps`/`img_size`/`width`/`height`, Norfair parameters and `tracked_object`, `chock_conf_thres`/`vehicle_conf_thres` (per data
   ≈0.10/≈0.40), the `LoadImages` implementation (cv2? letterbox every frame?), `ImagePreprocessor` (what `is_heavy`/`is_broken` do,
   cost), `Airplane.update_params` (how often it calls SAM, the `arrived` threshold), `BboxStabilizer`.
2. Whether the orchestrator's prod manifest passes `--write_video false` (otherwise GM encodes a 1080p video every frame); whether `dvc pull`
   really pulls all 8 files; whether there is network access for `timm(pretrained=True)` in the cluster.
3. Who writes MongoDB from the GM report and exactly which fields of the video/event doc (the `receiver_topic` receiver is outside these repos); whether it is
   still Kafka, or Pub/Sub.
4. Whether any module reads the first (raw) file, `detection_statistics`/`stages` (the stand says no), `confidence_camera`.
5. The real wall-clock time of a GM job on a T4 on a full turn (for the PF-Q1-08 baseline) and whether the stand's 28.29 ms includes postprocessing/NMS.
6. Ids 22, 26, 27, 28 and the names for GM classes 1, 6, 7, 8, 10…24 (needs `global_config.yaml`); whether there is a `wand` class.
7. Whether the entity detector (6 airlines, `Breze` with a typo) is still relevant given the entity-classifier redesign.
8. Whether the main aircraft in the tracker (`cv_trackers`) is taken exactly from the class-2 rows of the second pass — this determines whether
   main-aircraft selection can be moved from GM into the tracker without changing the semantics.
