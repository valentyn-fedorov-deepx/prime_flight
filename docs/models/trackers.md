# Trackers

> The trackers job follows the aircraft, belt loaders, GSE (ground support equipment) and people that the General Model (GM)
> found in one camera video. It gives each object a stable id and a motion state, and marks when the aircraft arrives and
> departs; the check modules read this output.

## At a glance

| | |
|---|---|
| What it does | Identity and motion for the aircraft, belt loaders (BL), GSE and people; the aircraft arrival and departure frames; which BL serves a cargo door. |
| When it runs | After the GM job and before the modules; one job per camera video (cone or wing), on the merged full-turn recording. |
| Production version | `cv_trackers` `optimization` @ `bd43c3c` (2026-02-28), with a `cv_common` from the `tracker_optimization` line (exact commit to confirm). |
| Runs on | GPU job on GKE (Google Kubernetes Engine): one NVIDIA T4, 3.3 vCPU, 8 GiB RAM. |
| Time per video | About **1.3 h** for the median **87-min** video, ≈ 112 ms per frame (production, September 2026). |
| Outputs | One JSON line per frame (0.6–1.2 GB per video uncompressed), uploaded gzip-compressed to `gs://cv-modules-topics/<video>/trackers<commit>.ndjson`; a status report; optionally a debug video. |
| Used by | The check modules: 25 read the aircraft track, 14 people, 11 belt loaders, 3 GSE. |

## What it tracks

| Object | How it is tracked | What it adds |
|---|---|---|
| Aircraft | GM class `airplane` (one main-aircraft box per frame); one object, id 1, for the whole video. Motion: FAST corner points inside a YOLO segmentation mask, followed with Lucas–Kanade optical flow; points renewed every **16 frames** (2 s). | `_status`, stops, `arrival_frame`, `departure_frame`, `have_arrival_stage`, `have_pre_arrival_stage`, counters |
| Belt loader | GM class `beltloader`, minus near-square boxes. DeepSORT on Kalman prediction and box overlap (its ResNet-34 appearance check never rejects a match). A new track covering > 30 % of an old BL's largest box of the last **80 frames** (10 s) takes over that object. Motion as above; points renewed every **10 frames** (1.25 s). | `_status`, stops, door label `data.bl_type`, status `unobserved` |
| GSE | GM class `gse`. DeepSORT as for BL (Euclidean appearance distance); a new track with IoU (box overlap) > 0.25 against a known GSE takes over that object. Points renewed every **5 frames** (0.6 s). | `_status`, stops |
| Person | GM class `person`. DeepSORT with a person re-identification network. | id and box only |
| Pushback, trailers, cones, other vehicles | Not tracked (so no "pushback attached" event); their boxes are only cut out of the keypoint masks or act as BL obstacles. | — |

## Events

| Event | How it is decided | Threshold |
|---|---|---|
| Object stops or moves (aircraft, BL, GSE) | A frame is "still" when over half of the keypoints in the box moved less than 0.002 × box height ÷ real height (7 m aircraft, 3 m BL, 2 m GSE), at least 0.1 px. | `stopping` from the first still frame, `stopped` on its **24th frame** (3 s); `moving` again after **9** moving frames in a row (≈ 1.1 s). From `stopped`: `proceeding` after **6** (0.75 s), `moving` after **17** (≈ 2.1 s) |
| Arrival (`arrival_frame`) | The aircraft is `stopped` for more than 32 frames in a row with its box taller than 0.95 × its usual height (from the GM); the value is then moved back to the first frame of that stop. `have_pre_arrival_stage` is true when the arrival is confirmed at frame 480 (60 s) or later. | **> 32 frames** (4 s); known ≈ **57 frames** (≈ 7 s) after the stop begins |
| Approach seen (`have_arrival_stage`) | Before arrival, normal motion (no jump > 50 px sideways or > 5 px vertically per frame). | **> 24 frames** (3 s) in a row |
| Departure (`departure_frame`) | After arrival, +1 per `moving` frame (cap 80) and −10 per other frame; set when the count first reaches 80. | **80 frames** (10 s); at the earliest ≈ 12 s after the aircraft starts moving |
| BL at a door (`data.bl_type`) | A stopped, visible BL overlaps the largest front-door box and reaches over 60 % across it (`front`), or overlaps the back-door box (`back`); with no door detected, staying in place (IoU > 0.8) counts. Cleared when that BL is `moving`. | **8 frames** (1 s) in a row |
| BL hidden (`unobserved`) | A GSE or trailer box (+10 % margin) covers > 80 % of a stopped BL (centre within 10–90 % of the width, ≥ 30 px tall); the BL box freezes. | per frame |
| Stop counted (`_stops_count`) | A new stop more than 5 % of the box width from the previous one; reset when the object drives off. | 5 % of box width |

## How it works

1. **Load** the video and its GM file (the newest, or a pinned version).
2. **Pair** each decoded frame (OpenCV) with the next GM line, by position.
3. **Split** the detections: belt loaders, GSE and people go to three DeepSORT trackers.
4. **Denoise:** every **16 frames** (2 s) measure the image noise; above **0.5**, smooth the frames on the GPU.
5. **Aircraft:** created at its first box, then updated on every frame with a GM aircraft; it drives arrival and departure.
6. **Belt loaders:** a hidden BL becomes `unobserved`; otherwise its motion is updated and, while stopped, the door rule runs.
   A new track first tries to take over an old BL object.
7. **GSE and people:** GSE are re-matched or created, then updated like BL. People get an id and a box only.
8. **Motion state** per vehicle: renew the keypoints (mask, then at most **250** points), follow them with optical flow, drop
   outliers, update the state; skip frames where the box area jumps by more than 1.5×.
9. **Write** each frame **5 frames** late; during an aircraft stop that is not yet an arrival, hold frames, then rewrite
   `arrival_frame` in all of them.
10. **Finish:** write the rest, report `processed` (or `error`), then compress and upload the file.

Nothing is reset within a video, and objects are never deleted.

## What it reports

One line per frame, `{"<frame>": [object, …]}`, numbered by position from 1; `[]` when empty. Order: aircraft, belt
loaders, people, GSE.

| Field | Content |
|---|---|
| `tr_id` | Aircraft 1; otherwise the DeepSORT id, per class (repeats across classes; new after a re-match) |
| `xyxy` | Integer box in pixels (1920 × 1080): the GM box for the aircraft, the smoothed tracker estimate for the rest |
| `conf` | Always 0.0 |
| `state_dict` | 39 fields (aircraft), 34 (BL, GSE), `{}` (people) |
| `data` | `{"bl_type": …}` with `front`, `back` or `undefined` for belt loaders; otherwise `null` |

State fields the modules read:

| Fields | Meaning | Modules |
|---|---|---|
| `_status` (`status` after loading) | `moving`, `stopping`, `stopped`, `proceeding`, `unobserved` | 10 (18) |
| `arrival_frame`, `departure_frame`, `have_pre_arrival_stage` | Aircraft arrival and departure frames (`null` until known); footage before arrival | 11, 6, 1 |
| `_p0`, `_st`, `_of_dots_lifetime`, `_init_dots_lifetime` | Optical-flow points (≤ 250 `[x, y]`), their flags and lifetime | 10 (9 to recompute the arrival stage) |
| `_obj_id` | Stable object id that survives re-matching | 8 |
| `data.bl_type` | Door the BL serves | belt-loader checks |
| `_xyxy`, `_color`, `_stops_count`, `_static_frames`, `_moving_frames` | Box, status colour, stops, state counters | 1–6 each |

Modules load the whole `state_dict` back into `cv_common` objects, so every field must stay. Example (production file,
video `AIjEAz70OfWCYG`, frame 15 000, shortened with `…`):

```json
{"15000": [
 {"tr_id": 1, "xyxy": [2, 36, 1622, 737], "cls_str": "airplane", "conf": 0.0,
  "state_dict": {…, "_obj_id": 1, …, "_status": "stopped", …, "_p0": [[…]], "_st": null, …, "_stopped_counter": 33,
   "have_pre_arrival_stage": true, "have_arrival_stage": false,
   "arrival_frame": 11151, "departure_frame": null, "_height_mode": 680.0}, "data": null},
 {"tr_id": 99, "xyxy": [28, 451, 907, 718], "cls_str": "beltloader", "conf": 0.0,
  "state_dict": {…, "_obj_id": 81, …, "_status": "stopped", …, "_bl_type_frames": {"front": 3873, "back": 0}},
  "data": {"bl_type": "front"}},
 {"tr_id": 612, "xyxy": [174, 530, 222, 601], "cls_str": "person", "conf": 0.0, "state_dict": {}, "data": null}
]}
```

Lines average 15–22 KB, mostly point lists.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `fps` (`cv_common/global_config.yaml`) | 8 | Converts the seconds in the code into frames |
| `stopping_time_thres`, `moving_time_thres` | 24, 8 frames | Stop length before `stopped`; moving frames that end a stop |
| `display_proceeding_time_thres`, `proceeding_time_thres` | 5, 16 frames | `stopped` → `proceeding` → `moving`; the BL/GSE key is misspelled, so the code default (also 16) applies |
| `static_points_thres`; `real_height` | 0.5; 7 / 3 / 2 m | Share of points that must stay still; aircraft / BL / GSE tolerance |
| `init_dots_lifetime` | 16 / 10 / 5 frames | Keypoint renewal period |
| `movement_anomaly_thres_x`, `_y` | 50 / 5 px | Faster motion does not count for `have_arrival_stage` |
| DeepSORT `N_INIT`, `MAX_AGE` (`deep_sort_pytorch/configs/deep_sort.yaml`) | BL, GSE 8, 160; people 6, 100 frames | Confirm a track after 1 s (people 0.75 s), keep a lost one 20 s (12.5 s); people's `N_INIT` also sets the 5-frame delay |
| `gse_iou_reinit_thresh`; `bl_range`, `bl_min_height`; `estimate_sigma_interval` (`local_config.yaml`) | 0.25; 10–90 %, 30 px; 2 s | GSE re-match; hidden-BL rule; noise check period |
| `cone_camera` (argument of `detect`) | `True` (the job does not pass it) | `False` adds a wing-camera `back` rule |

`bl_rel_inter_thresh`, `door_offset` and `min_iou_bl_type` are in `local_config.yaml` but not read. The aircraft, door and
obstacle thresholds are hard-coded.

## Known issues and limits

- **No schema version.** Newer `cv_common` versions (including `ac5098d`) refuse unknown `state_dict` keys on loading, so
  adding a field breaks modules.
- **Private fields in use.** Nine modules recompute the arrival stage from the optical-flow points, which make the file 14–22
  times larger than the GM file.
- **Arrival written back in time.** Known ≈ 7 s after the stop begins; output is held meanwhile (≈ 6 min in one sample
  video), and about 60 frames get a stray `arrival_frame` key in the envelope. The GM's own stop frame differs by ≈ 57 frames.
- **Aircraft only where the GM drew it.** In 4 of 7 sample videos the track ends early and no departure is found.
- **Camera type ignored.** Production never passes it, so wing videos get the cone-camera door rules (`back` never appears
  in 7 sample videos); the command line defaults to wing.
- **Two "BL at the door" definitions.** Door boxes here; overlap with the aircraft box (> 0.2) in the 3-stop check.
- **Stale objects.** Never deleted, so a vehicle parking where an old one stood can inherit its id and counters.
- **Shared segmentation cache.** BL and GSE share one cache entry per frame, so a GSE renewing its points on the same frame
  as a BL gets the BL mask.
- **Not fully repeatable.** Unseeded keypoint sampling; the ResNet-34 runs in training mode. Two runs differed on 6 of 3 186
  object-frames.
- **Positional frame numbers.** A lost frame shifts all later ones.
- **Cost.** Reads pixels every frame, so it cannot run on detections alone; 112 ms per frame on the T4 is near the 125 ms
  real-time budget (36–49 ms on an RTX 5070 Ti; the default branch 137–149 ms).
- **Report before upload.** `processed` is reported before the upload (effect to confirm).

## For developers

- **Repository:** `dxgat/utils/cv_trackers`. Production `optimization` @ `bd43c3c` (2026-02-28); default `master` @
  `b5d350c` (2025-08-08). Production swaps MobileSAM for two YOLO segmentation models, checks noise every 16 frames instead
  of every frame, and adds `scripts/tracker_clips.py` and new weights. The rules and output fields are the same; the new
  masks changed 2.8 % of `_status` values in a test slice.
- **Entry point:** the job copies `db_worker/model_starter.py` to the repository root and runs it with `--model trackers` →
  `start_trackers()` → `tracker.detect()` (job manifest not checked; `--write_video` defaults to on). Key files: `tracker.py`
  (main loop), `local_utils/bl_utils.py` (door rule), `deep_sort_pytorch/`, `cv_common/tracked_object.py` (state machine,
  save/load), `cv_common/transport.py` (arrival, departure), `db_worker/ML_worker.py` (input/output).
- **Dependencies and pins:** submodules `cv_common` `ac5098d`, `db_worker` `5a4aa83`. But the code calls
  `update_params(…, frame_number, segmentor, …, yolo_idx=…)`, which only the `cv_common` branch `tracker_optimization`
  has; the copy in the checkout equals its tip `2759daf` (2026-05-15). The image's commit is to confirm. Python 3.10;
  torch 2.5.1, ultralytics 8.4.9, scikit-image 0.21.0, cupy, cucim; `norfair` unpinned (supplies `_color`). Weights via DVC
  (Data Version Control; `gs://cv_weights/DVC`, 4 files, 130.8 MB):
  `yolo11s-seg_plane.pt`, `yolo26s_seg_bl_gse_tr10_noalb.pt`, `scripted_ckpt.t7` (person re-id), `mobile_sam.pt` (unused).
- **Run locally:** in the repository root, `dvc pull`, then
  `python tracker.py --source <video>.mp4 --testing --weights-dir weights --inferences-dir <dir> --cone-camera`. It downloads
  the newest GM file from the bucket (needs GCP access); offline, place `<dir>/general_model<video>.ndjson` and pass
  `auto_download_inference=False` (`tracker.py:639`). Output: `<dir>/trackers<video>.ndjson`.
- **Code references** by step (`cv_common` lines from the `2759daf` copy): 1 `db_worker/model_starter.py:147-166`,
  `db_worker/ML_worker.py:323-356`; 2 `tracker.py:160`, `ML_worker.py:250-254`; 3 `tracker.py:115-118, 192-290`;
  4 `tracker.py:292-326`; 5 `tracker.py:329-349`, `cv_common/transport.py:81-116`; 6 `tracker.py:35-54, 364-459`,
  `local_utils/bl_utils.py:18-133`; 7 `tracker.py:468-526`; 8 `cv_common/tracked_object.py:200-237, 260-345, 417-449`;
  9 `tracker.py:533-564, 599-608`; 10 `model_starter.py:162-191`. Save/load `tracked_object.py:584-720`; camera default
  `tracker.py:66`, not passed at `model_starter.py:166`.
