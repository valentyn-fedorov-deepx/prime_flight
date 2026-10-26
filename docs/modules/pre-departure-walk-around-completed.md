# M19 · Pre-departure walk around completed

> The module checks that a worker walked around the aircraft before departure. It turns each worker's track from the
> last minutes before departure into a path on a top-down picture of the aircraft, and a small image classifier (CNN)
> decides whether that path is a walk-around.

## At a glance

| | |
|---|---|
| Checks | M19 · Pre-departure walk around completed |
| Stage | Pre-departure |
| Looks at | Worker paths in a window that ends when the departure starts and begins 480 s (8 min) earlier, but not earlier than about 30 s before the last belt loader (BL) left; the verdict comes 30 s after the aircraft starts moving |
| Cameras | Cone camera, aircraft only (not run for jets) |
| Uses | Tracks: airplane, person, beltloader. General Model (GM) boxes: aircraft parts (nose, wing, engine, tail, wheels, doors), pushback and other vehicles. Video frames: yes, every frame |
| Own models | Walk-around classifier: small Keras CNN (`best_acc.keras`, 224×224) that scores one path image. Stock models: YOLOv8m-pose (worker keypoints, for distance), Depth Anything V2 and MobileSAM (top-down picture of the aircraft) |
| Runs on | GPU for pose, depth and segmentation; the CNN runs through TensorFlow on CPU |
| Real time | post-processing only — the verdict judges the whole window at departure, and on Fail it re-reads up to 12.5 minutes of video |
| Production version | tdv_cone @ e407de2 (2026-07-27) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | The trajectory model outputs True for a worker's path around the aircraft (path preprocessed and turned into an image). |
| Fail | The model outputs False for every observed path. |
| Not observed | No workers are visible. |
| Not observed — view blocked | The view is blocked (blocked frames / all frames > 0.6). |

Client note: the check covers the 5 minutes before departure, but not before the last BL leaves.

## How it decides

1. **Phases.** A state machine follows the turn: pre-arrival → arrival (airplane track ≥ 250 px tall, stopped or stopping) → post-arrival (60 s of continuous "stopped", or the tracker's arrival) → download (an active BL for **5 s**) ⇄ download without BL (no active BL for **10 s**) → departure.
2. **Departure.** After a 60-s continuous stop, **64 frames** (8 s) of movement start a departure; **240 frames** (30 s) after the start the aircraft box must have shrunk by **≥ 18 %**, otherwise the departure is cancelled.
3. **Top-down picture.** After arrival it builds once a top-down image of the aircraft (depth plus segmentation); if that fails it draws a simple silhouette.
4. **Worker positions.** From post-arrival to departure, every person track gets a pose run on its crop on every frame. Distance comes from the person's height in pixels (1.75 m person, scaled by the visible body parts); direction comes from the horizontal position (65° field of view).
5. **Checks at departure.** Not observed if the departure was never confirmed, the aircraft never reached post-arrival, or post-arrival → departure is shorter than **480 s**. Otherwise the paths are cut to the window above.
6. **Paths.** Points nearer than 5 m (10 m when the nose looks small) or farther than 55 m are dropped; paths are smoothed, paths under 8 points removed, and pieces of one worker are joined across track-id changes.
7. **Classifier.** Each joined path is drawn on the top-down picture and scored by the CNN; any score above **0.5** → Pass, else Fail.
8. **Second chances on Fail.** (a) Remove jumps over 5 m and score again; above **0.8** → Pass. (b) Re-read the video from **720 s** before to 30 s after the departure at 2 frames/s, track people with YOLOv8m-pose at 1 280 px, and give Pass when exactly one track sweeps at least **0.8 rad** (about 46°) over at least 30 samples (about 15 s).
9. **Pushback check on Pass.** If the pushback hides the left wing in ≥ **75 %** of the window frames, or stands at the frame edge in ≥ **45 %**, the Pass becomes Not observed.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `pre_departure.worker_window_sec` | 480 s | Window length and minimum stop-to-departure time |
| `gs1737.cnn_threshold` | 0.5 | Pass threshold (code fallback 0.7) |
| `gs1737.outlier_second_pass` / `outlier_threshold` | true / 0.8 | Second scoring on Fail |
| `gs1737.rescue_solo_track.*` | on; 0.8 rad, 30 samples, 720 s, 2 fps, 1 280 px | Re-tracking rescue on Fail |
| `post_arrival.trajectory_spatial_threshold` / `trajectory_temporal_threshold` | 6.5 m / 1.5 s | Splits a track where it jumps |
| `camera.hfov` | 65° | Turns image position into direction |
| `artifacts.*` | all true | Debug images, CSVs and annotations |
| hard-coded | 40 s; 5 s / 10 s; 60 s, 8 s, 30 s, 18 %; 75 % / 45 % | Window bound before BL absence; BL presence/absence; departure; pushback rule |

Not used by the code: `post_arrival.max_*`, `min_walk_around_duration`, `max_blocked_frame`, `obstacle_*`,
`seconds_between_parts`, `distance_estimation.*` (distance uses constants in `sources/config.py`).

## What it reports

- The verdict; the report is only "Returned status: <verdict>".
- Smart timeline: one segment with the verdict from the pre-departure start to the departure start ("0"–"0" when no departure or a short stay).
- `report.json` in the work folder: passing paths, best path image and probability, blocked frames, frame count, which add-on changed the verdict; plus debug files (trajectory CSVs, path images, top-down picture).
- Annotated video only for download frames, every 6th frame. The overlay file stays empty: the state machine never writes to it (to confirm on a production output).

## Known issues and limits

- The window differs from the client note: 480 s (8 min) instead of 5 min (code default 420 s); the rescue looks 720 s back and ignores the BL bound.
- No workers → Fail (nothing to score), while the client rule says Not observed.
- The blocked-view rule (> 0.6) is not applied: blocked frames are counted, but the check is commented out (`walk_around.py:121-131`).
- A stop-to-departure time under 8 min → Not observed (not in the client rule). If the departure is confirmed while a BL is still active, the window shrinks to the last 40 s and the timeline start falls after its end.
- Positions come from box height: wrong when only the feet show; paths and aircraft can be misaligned; joining fails when a worker is hidden by the aircraft rear or the pushback (Confluence: 4 videos); the CNN accepted a path that never reached the right side (2 videos).
- The distance uses `math.cos(25)` (radians, ≈ 0.99) in a block marked "TEST". Pose runs on every person crop of every frame from the stop, since the window is applied only at the end.
- Results of an earlier run in the work folder (`report.json`, `airparts.csv`, `trajectories.csv`) are reused instead of recomputed. Two airplane tracks taller than 250 px make `get_main_plane` raise an error.
- `sam_vit_b_01ec64.pth` (375 MB), `code/walk_around_copy/` and `main_test_metric3d_surface.py` are unused.
- The default branch of the post-arrival walk-around module (7112c99) also returns a pre-departure walk-around verdict from the same run (`main.py:650-652` there); which job feeds this check in production is to confirm.
- The branch pins cv_common e4c5e36, which lacks the `cv_common.modules` package that `code/states.py` imports; CI builds with cv_common master. Which cv_common production runs is to confirm. The branch has no Dockerfile, and the architecture review notes that the Torch and Keras parts must stay in separate environment profiles.

## For developers

- **Repository:** `dxgat/detectors/pre-departure-walk-around-completed`; production line `tdv_cone` @ `e407de2`; default branch `main` @ `f2b6c36` (2025-06-19) (older walk-around code; `tdv_cone` is 35 commits ahead with the state machine, the CNN decision and the add-ons).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera, json_logger, cache_folder, only_workers, debug_cv_common_modules)` → `VideoProcessor` → `code/states.py` `Gate` (phases, window, final checks) → `code/walk_around/walk_around.py` `PostArrivalWalkAround` (paths, CNN, add-ons); the top-down picture is built in `code/walk_around/temp/plane_tdv_extractor.py`, BL presence in `cv_common/modules/beltloader_presence_detector.py`. Flowchart `assets/Pre-departure walk around completed flowchart.png`; logic diagram (Confluence modules database, 2026-04-17): https://docs.google.com/spreadsheets/d/1mR-JCYcb5OCmSFqYyNG2NoiFXvgZROsrBPGk9CyrB9I/edit?usp=sharing
- **Dependencies:** branch pins `cv_common` e4c5e36, `db_worker` 6efc0b0, `UniDepth` e39594f (only used by the unused copy); the export carries cv_common ac5098d plus `modules/` from cv_common branch `modules` @ 2759daf. torch 2.2.0+cu121, ultralytics 8.2.48, tensorflow-cpu 2.15.1, keras 2.15.0, mobile_sam (`prod_requirements.txt`). Weights in DVC (5 files, 903 MB).
- **Run locally:** `python main.py --source <video>.mp4 --inferences-dir <folder> --cache_folder ./data [--write-video]`, or `python single_run.py <video_id> <video_path>`, which loads the CNN through the torch twin `keras_torch_shim.py` (local validation only).
- **Code references:** phases `code/states.py:597-620, 916-1006`; departure `cv_common/modules/plane_departure_detector.py:186-230`; positions `code/walk_around/detection_processor.py:34-49`, `distance_estimator.py:56-79`; final checks and window `states.py:778-819`; paths `walk_around.py:685-780`; CNN `:490-507`; add-ons `:515-558`; pushback `states.py:833-856`, `pushback_obstruction_detector.py:289-312, 519-573`.
