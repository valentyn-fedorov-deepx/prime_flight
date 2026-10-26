# M07 · Conditioned air removed 10 mins prior to departure and properly stowed

> The module checks that the conditioned-air (AC) hose was taken off the aircraft at least 10 minutes before the
> departure starts. It runs its own hose detector on the cone-camera video and follows, over the whole stay, whether the
> hose reaches the aircraft's connection point (the nose, or the left engine on a jet).

## At a glance

| | |
|---|---|
| Checks | M07 · Conditioned air removed 10 mins prior to departure and properly stowed |
| Stage | Pre-departure |
| Looks at | The hose from the moment the aircraft stops until its departure starts; the verdict is about the last 10 minutes before the departure and is given about 26 s after the aircraft starts moving |
| Cameras | Cone camera, aircraft and jet (the code ignores the camera flag) |
| Uses | General Model (GM) boxes: airplane_nose, airplane_wing, airplane_engine, and pushback, beltloader, gse, trailer, fuel_truck, air_conditioning, obstacle, side_obstacle, vehicle as obstacles. Tracks: airplane. Video frames: yes |
| Own models | Conditioned-air hose detector (YOLO11s segmentation model trained on our hose images; only its boxes are used) |
| Runs on | GPU (CPU if no GPU is present) |
| Real time | ready, needs video frames — one pass; the detector needs a frame every 2 s and the verdict only looks back at time already seen |
| Production version | new_logic @ 960bfe1 (2026-04-07) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | The AC hose was removed and properly stowed 10 minutes or more before the departure. |
| Fail | The AC hose was used but was not removed and/or properly stowed 10 minutes or more before the departure. |
| Not observed | The AC hose was not used, or the aircraft nose (jet: left engine) was not seen during the video, or the departure was not observed. |
| Not observed — view blocked | Obstacles were present at the "10 minutes before departure" mark and the hose had not been seen used, disconnected and stowed before that. |

## How it decides

1. **Aircraft and type.** The widest airplane track is the aircraft; it counts as arrived after **40 frames** (5 s) with tracker status "stopped". GM wing and engine boxes vote per frame: engine bottom above the wing bottom = "jet", below = "aircraft"; after more than **40** votes the majority wins.
2. **Connection point.** After arrival each frame needs the most confident nose box (aircraft) or the leftmost engine box (jet) inside the aircraft box; frames without it are skipped.
3. **Hose detection.** The own detector runs every **16 frames** (2 s); in between the last boxes are reused. It drops boxes far from the nose, small flat shadows under the nose (≤ 0.075 % of the frame), parts of a towbar, and the small stowed tip hanging from the gate (≤ 0.14 % of the frame).
4. **Obstacles.** A GM box overlapping the aircraft and spanning the right edge of the connection point: a pushback (aircraft only), or another listed class of at least **1.5 %** of the frame.
5. **Frame status.** "In use" when a hose box reaches the connection point; "possibly in use" when an obstacle touches the hose or hides the side the hose comes from; otherwise "not used".
6. **Smoothing.** The status changes only when **95 %** of the last **800 evaluated frames** (100 s) agree and they span at most 840 frames; the change is dated back by about 100 s.
7. **Departure.** After arrival, **64 frames** (8 s; jet 48 frames, 6 s) of "moving" start a departure, dated **32 frames** (4 s) before the first moving frame. **240 frames** (30 s) after that start the aircraft box must have shrunk by **≥ 17.5 %** (jet ≥ 11 %); otherwise the departure is cancelled and watching continues.
8. **Verdict**, going back from the departure start: "in use" at the 10-minute mark (**4 800 frames**) or later → Fail. "Possibly in use" at the mark → Not observed, unless the hose had been in use for 15 min and then went straight to "not used". "Not used" at the mark → an earlier "in use" period of at least **1 700 frames** (212.5 s) gives Pass, otherwise Not observed.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `plane.stop_thd` | 5 s | Stopped time (cumulative) before the aircraft counts as arrived |
| `plane.aircraft_departure_thd` / `jet_depart_thd` | 8 s / 6 s | Moving time that starts a departure |
| `plane.movement_det_delay` | 32 frames (4 s) | How far back the departure start is dated |
| `plane.departure_duration` | 30 s | When the departure is checked and the verdict given |
| `plane.departure_bbox_change` / `weaker_departure_bbox_change` | 0.175 / 0.11 | Minimum shrink of the aircraft box (weaker value for jets) |
| `ac_hose.status_frame_history` / `status_change_thd` | 800 frames (100 s) / 0.95 | Smoothing window and agreement needed |
| `ac_hose.min_usage_frames` | 1 700 frames (212.5 s) | Shortest hose use that can give Pass |
| `obstacle.min_area` | 0.015 | Minimum obstacle size, share of the frame |
| 10-minute mark, 15-minute rule, cadence | 4 800 / 7 200 / 16 frames | Hard-coded in `main.py`, not in the YAML |

`plane.jet_not_det_depart_thd`, `min_departure_len` and `min_plane_det_frames` are in the YAML but not used.

## What it reports

- The verdict and one report line with video times, e.g. Pass "Conditioned air hose was seen disconnected and stowed at …, which is … prior to departure at …"; Fail "Conditioned air hose was still in use on …, which is … before the departure at …".
- Not observed reasons: "Required airplane parts weren't observed", "Conditioned air was not used.", "There was an obstacle from … to … preventing reliable observation …" (view blocked), "Airplane departure wasn't observed".
- Smart timeline: one segment with the verdict from the arrival frame to the departure start (empty when no departure).
- Overlay file (.ndjson) with the aircraft, part, hose and obstacle boxes and status lines; an annotated video when video writing is on.

## Known issues and limits

- "In use" is a position proxy (hose box against the nose or engine box), not an observed coupling. "Properly stowed" is not checked on its own: a hose away from the aircraft, or not seen, counts as removed.
- Hose use shorter than 212.5 s never gives Pass; changes shorter than about 100 s are smoothed away; reused boxes count one detection up to 16 times.
- For jets, one "hose clearly away from the obstacle" test compares the hose's right edge (x) with the obstacles' top edge (y) (`main.py:520`): looks like a coordinate mix-up, to confirm.
- The detector has no confidence threshold, so the library default (0.25) applies — to confirm this is intended.
- The 10-minute mark assumes 8 fps; frame-width limits (86.5 % / 10 %) and obstacle margins are hard-coded.
- `weights/best28_full.onnx` and `util/yolov8_onnx.py` (the previous AC-unit detector) are never loaded.
- The architecture review and the consumption audit describe the default branch (old logic), not this line.

## For developers

- **Repository:** `dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed`; production line `new_logic` @ `960bfe1`; default branch `main` @ `940fdfc` (2025-06-19) (old logic with an ONNX AC-unit detector every 40 frames; `new_logic` is a 9-commit rewrite on top of it).
- **Entry point:** `main.py` → `detect(source, output_path, device, weights_dir, video_worker, cone_camera, json_fn, write_video, json_logger)`; `Plane` (arrival, departure, type), `AirConditioningHose` (status history), `get_ac_hose_detections`, `determine_obstacles`, `determine_ac_hose_status`, `get_decision`. `run_module.py` runs a test list. Block diagram `assets/block_diagram.png`; logic diagram (Confluence modules database, 2026-02-12): https://docs.google.com/spreadsheets/d/1HEcwdRgl3Pu8X6plJdPWup0uKyCe1otwTUXquB4ny_I/edit?gid=1532176923#gid=1532176923
- **Dependencies:** `cv_common` dd5b554, `db_worker` 5a4aa83 (exported copy; dd5b554 is not in the local archive, ac5098d was substituted). ultralytics 8.3.226, torch 2.4.1, norfair. Weights in DVC (2 files, 33 MB): `yolo11s_seg-det_ac_tr18_noalb.pt`, `best28_full.onnx` (unused). GPU Docker base image.
- **Run locally:** `python main.py --source <video>.mp4 --weights-dir weights --inferences-dir <GM and tracker .ndjson folder> [--write-video]`; fps and class ids come from `cv_common/global_config.yaml`.
- **Code references:** type `main.py:51-80, 161-183`; arrival `:126-131`; connection point `:82-102, 894-896`; detector `:574-684, 829`; obstacles `:316-361`; frame status `:480-571`; smoothing `:217-256`; departure `:147-155, 851-887`; verdict `:686-766, 909-917`.
