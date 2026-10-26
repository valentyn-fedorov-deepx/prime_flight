# M03 · All cargo bin doors opened and verified

> The module checks that the cargo door served by the camera was seen open for at least a minute after the aircraft stopped, and that a belt loader (BL) parked at that door for at least 10 seconds. It works only from General Model (GM) door detections and the tracker's aircraft and belt loader tracks.

## At a glance

| | |
|---|---|
| Checks | M03 · All cargo bin doors opened and verified |
| Stage | Download |
| Looks at | from the moment the aircraft stops until it departs; ends early 10 s after both conditions are met |
| Cameras | cone camera (front cargo door) and wing camera (back cargo door) for aircraft; wing camera only for jets |
| Uses | GM classes `front_door` (cone) or `back_door` (wing), `back_wheel` (cone); aircraft and belt loader tracks (with the tracker's front / back door label and stopped status); video frames: no |
| Own models | none |
| Runs on | CPU |
| Real time | ready as is — one pass, no video frames; Pass is known as soon as both conditions hold, Fail at departure |
| Production version | bl_approach @ 3422bdc (2026-04-14) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | The open door is seen for at least **480 frames** (60 s) — the front door on the cone camera, the back door on the wing camera — and a belt loader approached that door (stayed near it for at least **10 s**). |
| Fail | The door is not detected as open long enough, or no belt loader approached it, and there were no obstacles. |
| Not observed | No arrival stage, or the Pass condition was not met and an obstacle stood in front of the camera for **480 frames** (60 s) between arrival and departure. |
| Not observed — view blocked | No separate obstacle verdict (obstacles fall under Not observed). |

The code differs from this rule: the obstacle case is switched off and a "no pre-arrival stage" case is added (see *Known issues and limits*).

## How it decides

1. **Main aircraft.** In every frame it follows the widest aircraft track and its tracker state (stopped, arrived, departed).
2. **Was the arrival visible?** At the stop (or after **5 min** of tracking) it compares the median aircraft box area of the first **3 s** of tracking with the last **8 s**. Growth of **18 %** or less, or less than **11 s** of tracking, gives Not observed "No arrival stage". If the aircraft was already in view before frame **90** (11.25 s), it gives Not observed "No pre-arrival stage".
3. **Window.** Frames are skipped until the tracker reports the aircraft as arrived (stopped for more than **4 s**); reading stops at departure (moving for **10 s**).
4. **Door.** It counts the frames in which the target door is detected. More than **480 frames** (60 s) in total, not necessarily in a row, confirms the doors.
5. **Which belt loader.** Belt loader tracks the tracker labelled for this door (front on cone, back on wing); on the cone camera those standing behind a rear wheel are dropped. If none is left, a belt loader that spans the door (within **30 %** of its width) and lies more than **20 %** inside the aircraft box is accepted. The biggest one wins. A new track within **10 s** of the last one inherits its counters.
6. **Approach.** While the belt loader is stopping or stopped and its box covers more than **5 %** of the door box, a counter goes up. More than **80 frames** (10 s) in total = approached.
7. **Early end.** **10 s** after both conditions are confirmed, the module stops reading.
8. **Verdict**, in this order: Pass if both conditions hold → "No arrival stage" → "No pre-arrival stage" → (obstacle case, switched off) → Fail if an aircraft was seen → Not observed "No plane was observed".

## Settings

| Setting | Value | What it does |
|---|---|---|
| `min_opened_doors_frames` | 480 (60 s) | Door frames needed after the stop; also the obstacle duration (inactive). |
| `min_frames_near_doors` | 80 (10 s) | Stopped frames the belt loader must overlap the door. |
| `min_bl_swap_time_thresh` | 80 (10 s) | A new belt loader track within this time inherits the previous one's counters. |
| `min_bl_init_frames_thresh`, `bl_init_check_delay` | 80 (10 s), 16 (2 s) | Belt loader records seen for under 10 s are dropped once gone for 2 s. |
| `obstacle_min_area_ratio` | 0.35 | Vehicle box size (share of the frame) that counts as an obstacle. **Not used** (obstacle check off). |
| `max_no_obstacle_frames`, `arrival_confirmation_offset` | 16 (2 s), 80 (10 s) | Obstacle bookkeeping only; no effect. |
| Door overlap (code) | 0.05 | Share of the door box the belt loader must cover (`main.py:94`). |
| Arrival check (shared library) | 18 %, 3 s / 8 s, 5 min, frame 90 | Arrival and pre-arrival visibility (`plane_arrival_detector.py:61-77`). |

## What it reports

- **Verdict:** Pass, Fail or Not observed.
- **Report text:** Pass — open doors "for 480 frames" and the id of the belt loader that approached, with times. Fail — which condition failed (doors, approach or both), the number of door frames and the time range. Not observed — "No arrival stage", "No pre-arrival stage" or "No plane was observed".
- **Smart timeline:** Pass — one interval from the first open-door frame to the end of the evidence; Fail — one interval from the stop to departure or the last frame; Not observed — empty.
- **Overlay log** (ndjson with boxes and texts per frame); an annotated video only with `--write-video`.

## Known issues and limits

- **The obstacle case never fires.** `collect_frame_detections` is called with `camera_config=None` (`main.py:420-421`), and the obstacle flag is set only when `camera_config` is given (`main.py:214`). A blocked view therefore ends as Fail, not Not observed. This came with the 2025-06-09 refactor; the default branch still has a working obstacle check.
- **Extra Not observed case.** "No pre-arrival stage" is not in the client rule. The shared library documents its threshold as 90 s but uses **90 frames** (11.25 s): the value is not multiplied by the frame rate (`plane_arrival_detector.py:77`). Intended value to confirm.
- **"Open" means "detected".** The module trusts the GM door class; it does not check the door's mechanical state.
- **Aircraft seen but never stopped:** no frame is checked and the verdict is Fail, unless the arrival check says "No arrival stage". To confirm whether intended.
- **One door per camera.** "All" doors are covered only by the two-camera merge (Fail on either = Fail).
- The Pass text always says "480 frames", whatever the real count.
- The architecture review note "does not verify a belt loader / door relationship" describes an older version.

## For developers

- **Repository:** `dxgat/detectors/all-cargo-bin-doors-opened-and-verified`; production line `bl_approach` @ `3422bdc`; default branch `master` @ `c60aed2` (2025-06-19) (no belt loader approach, no arrival / pre-arrival check, working obstacle check).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, cone_camera, weights_dir, json_logger)`. All logic is in `main.py`: `make_inference` (verdict), `Beltloader` (approach counter), `find_beltloader`, `manage_beltloader`, `handle_obstacles`, `handle_plane_anomaly`. Flowchart `.doc/cargo-doors.svg`; logic diagram (Confluence modules database): https://docs.google.com/spreadsheets/d/1iMrh9xOsKMPzMaYOjbd-ewhgZGI-xtHtubRlbP2a6yg/edit?gid=833646066#gid=833646066
- **Dependencies:** `cv_common` @ `dd5b554`, `db_worker` @ `6efc0b0` (exported copy). The pin lacks the `cv_common/modules` package that `main.py` imports (`PlaneArrivalDetector`); the export adds it from the cv_common `modules` branch, and the version built into production is to confirm. Packages: numpy, opencv-python, torch (only `no_grad`). No weights.
- **Run locally:** `python main.py --source <video.mp4> --inferences-dir <GM and tracker ndjson folder> [--cone-camera] [--write-video] [--json-fn <name>]`; settings from `local_config.yaml` over `cv_common/global_config.yaml`. In production `db_worker/model_starter.py` imports `detect` and passes the camera type.
- **Code references:** step 1 `main.py:286-338`; step 2 `main.py:375, 407-411`, `cv_common/modules/plane_arrival_detector.py:85-149, 196-229`; step 3 `main.py:436-447`; step 4 `main.py:452-464`; step 5 `main.py:116-140, 143-174`; step 6 `main.py:91-102, 503-517`; step 7 `main.py:426-434`; step 8 `main.py:21-64`; obstacle path `main.py:184-220, 241-283`.
