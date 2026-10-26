# M08 · Cones are removed only after all GSE is clear of A/C and chocked

> The module checks that the wing, engine and tail cones stay around the aircraft until the ground support equipment
> (GSE) has left it. In practice it compares the last time cones were seen with the last time a belt loader (BL) was at
> the aircraft, using only General Model detections and tracks.

## At a glance

| | |
|---|---|
| Checks | M08 · Cones are removed only after all GSE is clear of A/C and chocked |
| Stage | Pre-departure |
| Looks at | The whole video up to the tracker's departure moment (about 10 s after the aircraft starts moving); what counts is the last cone sighting against the last BL presence at the aircraft |
| Cameras | Cone camera for aircraft, wing camera for jets (client split); on the cone camera the code adds a tail-cone filter and a BL-behind-the-rear-wheel test |
| Uses | General Model (GM) boxes: engine_cone, wing_cone, tail_cone, front_door, back_wheel, vehicle; gse, pushback, trailer, beltloader, fuel_truck (obstacle test only). Tracks: airplane, beltloader. Video frames: no (only for the annotated video) |
| Own models | none (`weights/cones_v1.pt` is tracked in DVC but never loaded) |
| Runs on | CPU |
| Real time | ready as is — one pass over detections and tracks, no video frames; the verdict is given at the departure |
| Production version | main @ e2a25ba (2025-11-28) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | Cones were removed, and transport was far enough from the aircraft and did not approach it after that. |
| Fail | Cones were removed, but transport was too close to the aircraft or approached it after the removal. |
| Not observed | Cones were detected in fewer than 200 frames. |
| Not observed — view blocked | Blocked frames are more than 65 % of the full turn. |

## How it decides

1. **Aircraft.** On frames with a non-empty GM list it reads the airplane and BL tracks; the widest airplane track is the aircraft. "Arrived" and "departed" are set on the frames that exactly equal the tracker's arrival and departure frames.
2. **Cones.** GM engine_cone, wing_cone and tail_cone boxes count (on the cone camera a tail cone must overlap the aircraft box; the generic `cone` class is not used). A cone sighting needs at least **8 consecutive frames** (1 s) with cones; the module keeps the last frame of such a run as the **last cone frame**.
3. **Front door.** Between arrival and departure it keeps the widest front_door box and forgets it after **40 frames** (5 s) without a door detection.
4. **Transport at the aircraft.** The **last transport frame** is updated when:
   - a BL track lies more than **70 %** inside the aircraft box and its centre is less than **500 px** from the front-door centre; or
   - (cone camera only) a BL track overlaps a rear-wheel (back_wheel) box and stands right behind it; or
   - a GM vehicle box stands right behind a rear wheel for **8 consecutive frames** (1 s) — the rear BL.
   "Right behind" means the vehicle's bottom edge is above the wheel's bottom edge by less than **40 %** of the wheel height.
5. **Obstacles.** On frames with gse, pushback, trailer, beltloader or fuel_truck boxes, it compares those boxes with the cone boxes remembered from recent frames; an IoU (overlap over union) above **0.7** marks the frame as "cones overlapped".
6. **Stop.** The loop ends at the departure frame.
7. **Verdict.** No 1-s cone run at all → Not observed. No departure → Not observed. Last cone frame ≥ last transport frame → Pass. Otherwise: cones overlapped after the last cone frame → Not observed (obstacle); else Fail.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `rear_bl_position_margin` | 0.4 | How close behind a rear wheel a vehicle must stand, as a share of the wheel height |
| cone run (code) | 8 frames (1 s) | Consecutive cone frames needed for a sighting |
| door memory (code) | 40 frames (5 s) | How long a lost front door is kept |
| BL at the door (code) | > 70 % inside the aircraft, < 500 px from the door | When a BL counts as at the aircraft |
| rear vehicle (code) | 8 frames (1 s) | Consecutive frames for a vehicle behind a rear wheel |
| obstacle (code) | IoU > 0.7; duplicates IoU > 0.9; last 16 obstacle-free frames | When cones count as hidden by transport |
| timeline margin (code) | ±40 frames (±5 s) | Width of the reported time span |

In the YAML but not used: `obstacle_width`, `obstacle_center_range`, `beltloader_in_thres`, `beltloader_out_thres`,
`stop_capture_window`, `cone_register_delay`.

## What it reports

- Pass: "Cones were removed after all GSE are backed off airplane. Time: … -- …" (±5 s around the last cone frame), with a Pass smart-timeline segment of the same span.
- Fail: "Cones were removed before all GSE are backed off aircraft. Time: … -- …" (±5 s around the last transport frame), with a Fail segment.
- Not observed: "There are no detected cones", "There is no departure stage. The GSE can still drive up to the airplane" or "There was an obstacle"; empty smart timeline.
- Overlay file (.ndjson): aircraft, cone, BL and rear-vehicle boxes and status lines ("Cones are placed and visible", "Cones are removed or out of view", "Transport overlap placed cones"). An annotated video when video writing is on.

## Known issues and limits

- Despite its name it does not check that GSE is chocked, and "all GSE" is in practice BLs at the front door or behind a rear wheel; gse, pushback, trailer and fuel truck only feed the obstacle test.
- It does not check that cones were removed at all: cones visible until departure give Pass. Cones are counted over the whole video, including before arrival.
- The client's 200-frame and 65 % blocked-frame rules are not in the code.
- The obstacle test needs IoU > 0.7 between a vehicle box and a cone box, so boxes of almost the same size and place; a large vehicle in front of a small cone gives a low IoU, so this branch rarely fires (to confirm on data). The duplicate filter uses `break`, which ends the whole check at the first duplicate (`main.py:298`).
- Arrival and departure need the airplane track on exactly the tracker's frame; if it is missing there, departure is never seen and the result is Not observed.
- The remembered cone list grows while any transport box is in view and is turned into arrays that are never read (compute cost only).
- Local runs: `__main__` does not pass `--cone-camera`, so a local run always behaves as the wing camera; `run_module.py` passes the camera type.

## For developers

- **Repository:** `dxgat/detectors/cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked`; production line `main` @ `e2a25ba`; default branch `main` @ `e2a25ba` (the same).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera, json_logger)`. All logic is in `main.py`: `Plane` (front-door memory), `validate_cone_detection`, `is_overlap_and_right_behind`. `run_module.py` runs a test list with each video's camera type. Block diagram `shorted_block_diagram.svg`; logic diagram (Confluence modules database, 2023-07-10): https://docs.google.com/spreadsheets/d/10FxC1-9XI4tb_qIIo-W-_ebJaPUrKdeCeXbHobfj92I/edit?gid=0#gid=0
- **Dependencies:** `cv_common` 33c188d, `db_worker` 5a4aa83 (`git ls-tree HEAD`); 33c188d is not in the local archive, the local folder holds ac5098d. opencv, numpy; torch 1.10 is listed but no model is used. CPU Docker base image.
- **Run locally:** `python main.py --source <video>.mp4 [--write-video] [--json-fn <name>]`; the GM and tracker .ndjson are read from `../inferences_dir` or downloaded from the bucket.
- **Code references:** aircraft `main.py:127-155`; cones `:50-56, 158-208`; front door `:21-47, 210-212`; transport `:58-62, 214-246`; obstacles `:274-309`; stop `:335-336`; verdict `:338-378`.
