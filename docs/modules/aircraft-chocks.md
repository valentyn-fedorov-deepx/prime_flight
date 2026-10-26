# M02A, M02B, M02C · Aircraft chocks

> One module, three checks on the aircraft's wheel chocks: the nose-wheel chock is placed within 30 s of arrival, and
> the main-gear and nose-wheel chocks come off only after the pushback is attached. It finds wheels, chocks and the
> pushback in the General Model (GM) detections; for the main gear it also compares wheel images with a reference taken
> at arrival, using its own classifier.

## At a glance

| | |
|---|---|
| Checks | M02A · Nose gear chocks applied immediately<br>M02B · Main gear chocks removed only after aircraft is attached to pushback<br>M02C · Nose wheel chock removed from aircraft |
| Stage | Arrival, Pre-departure, Departure |
| Looks at | From the aircraft's arrival to its departure: the nose wheel in the first 30 s after arrival, then the rear and nose wheels around the pushback attachment |
| Cameras | Cone camera, aircraft and jets (client split); the code does not check the camera |
| Uses | GM boxes: front_wheel, back_wheel, chock (separate chock detector), airplane_nose, pushback, vehicle; obstacles cone, trailer, fuel_truck, ladder, obstacle. Tracks: airplane, person, GSE (ground support equipment), BL (belt loader). Video frames: yes (rear wheels, every frame from arrival to departure) |
| Own models | Aircraft chock classifier (EfficientNet-B0, `effnetb0_ext_fix_993.pt`): compares a rear-wheel view with the wheel's reference image and says whether a chock is there |
| Runs on | CPU (production CPU pool); the code can use a GPU when given one |
| Real time | needs a small patch — a first pass reads ahead to the pushback's final position; a live "pushback attached" event can replace it |
| Production version | master @ fa00478 (2026-01-30) |

## The rule (agreed with the client)

### M02A · Nose gear chocks applied immediately

| Verdict | When |
|---|---|
| Pass | The front wheel was chocked in the first 240 frames (30 s). |
| Fail | The front wheel was detected but not chocked in the first 240 frames. |
| Not observed | The aircraft or the front wheel was not observed, there is no arrival stage, or there is an obstacle. |
| Not observed — view blocked | All arrival frames are blocked. |

### M02B · Main gear chocks removed only after aircraft is attached to pushback

| Verdict | When |
|---|---|
| Pass | Main gear chocks were removed only after the aircraft was attached to the pushback. |
| Fail | Main gear chocks were removed before the aircraft was attached to the pushback. |
| Not observed | The aircraft or the back wheels were not detected, or there is an obstacle. |
| Not observed — view blocked | All frames are blocked. |

### M02C · Nose wheel chock removed from aircraft

| Verdict | When |
|---|---|
| Pass | Nose gear chocks were removed only after the aircraft was attached to the pushback. |
| Fail | Nose gear chocks were removed before the attachment, or the video stops before the removal can be seen. |
| Not observed | The aircraft or the nose wheel was not detected, or there is an obstacle. |
| Not observed — view blocked | All frames are blocked. |

## How it decides

1. **First pass (look-ahead).** It reads the detections up to the departure (or the last frame) and keeps the largest pushback box per frame. The median box from **120 s to 60 s before departure** is the pushback's final position (needs more than **8 frames** with a pushback).
2. **Arrival and departure.** The main pass works from the tracker's arrival frame (aircraft stopped for about 4 s) to its departure frame (about 10 s of motion). An "arrival stage" exists if the aircraft moved smoothly for more than **24 frames** (3 s) in a row before stopping.
3. **Pushback attached:** a pushback box matching the final position (IoU > **0.8**) on more than **40 frames** (5 s) net; each frame without it takes one off. Without a final position, a pushback next to the nose and not far below the aircraft counts.
4. **Safety zone busy:** a BL the tracker marks as serving a door, or a vehicle just behind a rear wheel, for more than **16 frames** (2 s); clear again after more than **40 frames** (5 s) without one.
5. **M02A.** The nose wheel is the largest front_wheel box on the aircraft; it is chocked when a chock box overlaps its lower **40%**. Pass when chocked on more than **8 frames** (1 s, gaps under 2 s) within **240 frames** (30 s) after arrival. At 30 s: Fail, or Not observed if an obstacle covered the wheel on **80 frames** (10 s) or more. Also Not observed when the wheel was still undetected at some moment of the first 35 s and no chock was confirmed, or when there was no arrival stage.
6. **M02C.** After the attachment: Pass when the nose chock is still seen (more than **24 frames**, 3 s). Fail when it has been missing for more than **40 frames** (5 s), with no obstacle on the wheel, and is not seen again; Not observed instead when the pushback box covers more than half of the wheel's pre-attachment position, or when the pushback is never attached.
7. **M02B setup.** In the first **80 frames** (10 s) after arrival the two largest rear wheels are picked, and the 8 clearest, steadiest frames of each are averaged into a reference image.
8. **M02B before the event.** A wheel is "confirmed chocked" when a chock is detected under it for **32 frames** (4 s) in a row, or when the classifier, comparing a steady averaged view with the reference, finds a chock (at most once every 10 s).
9. **M02B event** = the later of "pushback attached" and "safety zone clear"; a returning BL cancels it. Within **80 frames** (10 s) after the event, a chock still found (4-s detection, or the classifier on the 8 best frames) gives Pass for the wheel. No chock gives Fail, but only for a wheel confirmed chocked before; a wheel near the frame edge, with an unusual box shape, or with a person or vehicle in front gives Not observed.
10. **M02B verdict:** any wheel Fail → Fail; else any wheel Pass → Pass; else Not observed.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `min_chock_frames` | 32 (4 s) | Chock detections in a row that confirm a rear-wheel chock |
| `stop_capture_window` | 80 (10 s) | Time after arrival to pick the rear wheels and build their reference images |
| `main_capture_window`, `main_check_timeframe` | 80 (10 s) | Window after the event in which the rear-wheel chock must still be found |
| `frame_average_window`, `static_env_window`, `static_env_threshold` | 8 (1 s), 16 (2 s), 0.997 | Frames averaged per view; the view must stay steady before a classifier check |
| `differentiation_timeout` | 80 (10 s) | Minimum time between two classifier checks of a wheel |
| `beltloader_in_thres`, `beltloader_out_thres` | 16 (2 s), 40 (5 s) | When the safety zone becomes busy or clear |
| `min_max_width_ratio`, `edge_distance` | 0.9–1.4, 10 px | Rear-wheel box shape and edge limits for Not observed |
| `diff_obstacle_min_iou`, `diff_cone_obs_min_iou` | 0.15, 0.35 | Share of the zone under a wheel a vehicle (or cone) must cover to be an obstacle |
| nose-wheel rules (code) | 30 s, 1 s, 3 s, 5 s, 10 s | Placement window, confirmation, presence after attachment, absence, obstacle limit |
| pushback rules (code) | 120 s window, IoU 0.8, 5 s | Final position and attachment |

Not used: `tow_width`, `tow_candidate_width`, `wh_rel`, `obstacles_match_iou`, `obstacles_check_iou`, and `not_observed_diff_threshold` (its check is commented out); `obstacle_width` and `obstacle_center_range` only drive an on-screen message.

## What it reports

- Three results in a fixed order — M02A, M02B, M02C — each with a verdict, a report and a smart timeline.
- M02A: "Nose wheel chocks are applied immediately." or "… are not applied immediately within 30 seconds …"; smart timeline from 10 s before to 30 s after arrival.
- M02B: one line per rear wheel, e.g. "Rear right wheel chocks removed after pushback attached and safety zone cleared (time)" or "… removed prematurely …"; smart timeline per wheel from 5 s before to 10 s after the event (Not observed: up to 60 s after the wheel was first seen).
- M02C: "Nose wheel chocks are removed after aircraft is attached to pushback." or "… removed before …"; smart timeline ±10 s around the decision frame.
- Not observed results name the reason ("Nose wheel is not detected or there is an obstacle", "No arrival stage", "No visible pushback attached", …). Nose timelines carry Start / End as text, the main-gear one as numbers.
- Overlay file (.ndjson); annotated video with `--write-video`; classifier inputs with `--save-diff`.

## Known issues and limits

- The first pass needs the whole turn up to departure (and the video length), so the module is not causal. A streaming version with a live "pushback attached" event gave no M02B differences on 8 videos; the M02C anchor moved by −7 to −444 s.
- M02B waits for more than the client rule: the pushback attached **and** the BLs gone from the safety zone.
- M02C Pass means "the chock was still seen after attachment", not an observed removal. The client's Fail "the video stops before the removal can be seen" is not implemented: a chock still visible at the end gives Pass.
- For an M02C Fail the reported time is the last processed frame without a chock (near departure), not the moment the chock disappeared.
- The M02A flag `installed_no` compares the arrival frame number with 240, so it only applies when the aircraft arrived in the first 30 s of the video; "within 30 s after arrival" was probably meant (to confirm).
- The last nose-wheel box is reused when the wheel is not detected, so a wheel hidden later is still checked at its old place. The 30-s window starts at the tracker's arrival frame, about 4 s after the stop.
- Pushback attachment can be spoiled by obstacles, or another pushback or vehicle can be taken for it (Confluence); the nose-based fallback never counts down.
- Arrival and departure are matched by exact frame number; up to 81 + 81 + 16 + 16 full frames are held per rear wheel.
- The client sheet marks M02B as not production-ready.

## For developers

- **Repository:** `dxgat/detectors/aircraft-chocks`; production line `master` @ `fa00478`; default branch `master` @ `fa00478` (the same). `towbar-attachment-fallback` (2026-09-04) and `visualization` (2026-03-02) are one commit ahead each: feature work.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera, json_logger, save_diff, debug_all)`; returns three lists (verdicts, reports, timelines) in the order M02A, M02B, M02C; `cone_camera` is unused. `FrontWheel` (nose rules), `RearWheelChocksAnalyzer` (observability, chock detection, image comparison), `get_aircraft_report`, `get_main_gear_report`; `complex_difference.py` builds the classifier input, `simple_difference.py` tests that the view is steady. Logic diagram (Confluence modules database, 2023-07-10): https://docs.google.com/spreadsheets/d/1nTmyOxG_teXgI5qAYUVU2xQsD5LTbYCAaxayuqtNmyE/edit?gid=0#gid=0
- **Dependencies:** `cv_common` ac5098d, `db_worker` 5a4aa83 (`git ls-tree HEAD`); timm, torch, torchvision, norfair, matplotlib; Docker base `cpu_base`. Weights in DVC: `effnetb0_ext_fix_993.pt`.
- **Run locally:** `python main.py --source <video>.mp4 --weights-dir weights --inferences-dir <folder> [--device cpu] [--write-video] [--save-csv] [--save-diff] [--debug-all]`; `run_module.py` loops over test videos.
- **Code references:** first pass `main.py:1240-1286`; arrival, departure, arrival stage `:1431-1485`; pushback attached `:1523-1549`; safety zone `:1561-1612`; nose wheel `:953-1060, 1615-1626, 1715-1749`; M02A / M02C verdicts `:1139-1211`, pushback-cover rule `:1760-1763`; rear-wheel pick `:1659-1680`; observability `:281-389`; chock detection `:392-443`; image comparison `:446-865`; M02B verdict `:33-79`.
