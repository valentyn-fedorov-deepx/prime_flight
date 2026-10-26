# M09 · Cones placed in proper positions and timely

> The module checks that the safety cones around the parked aircraft are in place: on the cone camera one wing cone
> and, for aircraft that are not jets, two engine cones; on the wing camera one tail cone. It counts the frames on which
> the General Model (GM) sees enough cones of each type between arrival and departure, and gives Not observed when the
> cone zones were hidden.

## At a glance

| | |
|---|---|
| Checks | M09 · Cones placed in proper positions and timely |
| Stage | Arrival, Post-arrival, Download, Upload, Pre-departure |
| Looks at | From the moment the aircraft has been stopped for 5 s until its departure movement is confirmed |
| Cameras | Cone camera (wing and engine cones) and wing camera (tail cone), aircraft and jets (client split); the db_worker task list names only the cone camera — to confirm |
| Uses | GM boxes: wing_cone, engine_cone, tail_cone, airplane_nose, airplane_wing, airplane_engine, airplane_tail; obstacles pushback, beltloader, gse, trailer, fuel_truck, obstacle, side_obstacle, vehicle, person, ladder. Tracks: airplane. Video frames: no (only for the annotated video) |
| Own models | none (`weights/cones_v1.pt` and `cones_helpers.py` are shipped but never used) |
| Runs on | CPU |
| Real time | ready as is — reads only detections and the aircraft track; the verdict is final when the departure is confirmed |
| Production version | not_observed_logic @ d2a6898 (2026-03-25) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | 1 wing cone and 2 engine cones (only 1 wing cone for a jet) are seen for at least 100 frames on the cone camera, and 1 tail cone for at least 100 frames on the wing camera. |
| Fail | At least one cone is detected on fewer than 100 frames. |
| Not observed | The aircraft is not detected. |
| Not observed — view blocked | Blocked frames make up more than 65% of the full turn. |

## How it decides

1. **Main aircraft:** on each frame, the widest airplane track. It has arrived after **40 frames** (5 s) in the stopped state, counted in total, not in a row. An arrival in the first **96 frames** (12 s) of the video means "arrival not observed" (the aircraft was already parked).
2. **Departure.** After **64 frames** (8 s) in the moving state without stopping again, the departure start is set **32 frames** (4 s) before the first moving frame. **240 frames** (30 s) after that start the aircraft box over the first 3 s of the motion is compared with the last 3 s: a shrink of at least **17.5%** confirms the departure and the module decides at once; otherwise it was a false departure and counting goes on. At the last frame of the video it decides anyway.
3. **Cones on a frame:** cone camera — at least **1** wing_cone and, for aircraft that are not jets, at least **2** engine_cone; wing camera — at least **1** tail_cone (for jets, tail cones left of the engine are ignored). Between arrival and confirmed departure, each frame with the required number adds one to that cone type's count. Any box of the class counts; its position is not checked further.
4. **Aircraft parts** (nose, left wing, engines, tail) come from the part boxes on the aircraft; a part missing for up to **10 s** is replaced by its recent average.
5. **Hidden zones,** counted only on frames without the required cones: nose or left wing not found; an obstacle (a tow bar under the nose is ignored) in the zone under the left wing, in front of the engines or under the tail; the wing or tail zone at the frame edge; or, with no aircraft visible, a large obstacle (≥ **5.4%** of the frame) over the frame centre.
6. **Per cone type:** Pass with at least **100 frames** (12.5 s). Otherwise Not observed if the arrival was not observed or no departure was seen; otherwise Not observed if hidden frames make up at least **63%** of the time from arrival to departure start; otherwise Fail.
7. **Verdict:** any type Fail → Fail; else any Not observed → Not observed; else Pass. No aircraft at all, or one that never stopped → Not observed.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `min_presence_frames` | 100 (12.5 s) | Frames with the required cones needed for Pass |
| required cones (code) | wing 1, engine 2, tail 1 | Cones needed on one frame |
| `plane.stop_thd`, `plane.no_arrival_thr` | 5 s, 12 s | Stopped time that marks the arrival; an earlier arrival is "not observed" |
| `plane.aircraft_departure_thd` | 8 s | Moving time before a departure is checked (`jet_depart_thd` 6 s: see the known issues) |
| `plane.movement_det_delay`, `plane.departure_duration` | 32 frames (4 s), 30 s | Departure start offset; when the departure is confirmed |
| `plane.departure_bbox_change` | 0.175 | Box shrink that confirms a departure (`weaker_departure_bbox_change` 0.11 for jets: see the known issues) |
| `missing_part_thr` | 10 s | How long a missing aircraft part is replaced by its average |
| hidden-time limit (code) | 0.63 | Share of hidden frames that turns Fail into Not observed |
| `obstacle.*` | fractions of the part sizes; `min_area` 0.0025 of the frame | Shape of the wing, engine and tail zones; smallest obstacle |

`min_plane_type_frames_eval`, `jet_not_det_depart_thd`, `min_departure_len` and `min_plane_det_frames` are in the YAML but not used; the code reads `min_plane_direction_frames_eval`, which the YAML lacks, on a path that never runs.

## What it reports

- One report line built per cone type, e.g. "Wing cone(s) were successfully placed for N frames (Pass). Engine cone(s) were placed only for N frames (Fail)."; Not observed texts such as "Zone under wing was obstructed, was out of frame (not Observed).", "… not observed due to incomplete arrival and departure (Not observed).", "No plane detected", "Plane hasn't been detected."
- Smart timeline: Pass — per cone type, from 116 frames (14.5 s) before to 64 frames (8 s) after the frame where it reached 100 frames; Fail — arrival to departure start; Not observed — arrival to departure start (or the end of the video). Start / End are text.
- Overlay file (.ndjson): aircraft status, cone counts, hidden-zone events, obstacle boxes. An annotated video with `--write-video`.

## Known issues and limits

- **"Timely" is not checked:** there is no deadline after arrival. Cones are counted over the whole stay and Fail is decided only at departure or at the end of the video; a time limit would be a rule change to agree with the client.
- **"Proper positions" is the class label only:** any wing_cone, engine_cone or tail_cone box counts wherever it is (except the jet tail-cone filter); wing and engine cones are counted separately, not on the same frames.
- Not observed is wider than the client rule: it also covers an unseen arrival or departure, and zones hidden for at least 63% of the stay (client: 65% of the full turn).
- The jet departure rules compare the type with lower-case `jet`, but the GM reports `JET` / `AIRCRAFT`, so the 6-s threshold and the 11% shrink never apply (to confirm how the type is passed).
- The jet direction check never runs (it waits for the value `not evaluated`, but the field starts empty), so a jet's tail zone is always placed for one direction.
- The main aircraft is the widest track on each frame, with no identity check; a larger aircraft passing by can take its place.
- The last-frame check reads the video length (`dataset.nframes`), which a live stream does not know.
- The architecture review's notes (40% in the report text against 65% in the code, return values of different length) refer to the older default branch; here every path returns three values and the limit is 63%.

## For developers

- **Repository:** `dxgat/detectors/cones-placed-in-proper-positions-and-timely`; production line `not_observed_logic` @ `d2a6898`; default branch `master` @ `b2c53f6` (2025-09-22): the older version, 7 commits behind, before the refactor and the new Not observed logic (different YAML).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera, json_logger, airplane_type)`; in production db_worker's `model_starter.py` passes the camera flag and, for this module only, `airplane_type`. `Plane` (arrival, departure, part memory), `record_cones_presence`, `determine_obstruction`, `get_decision`; `README.md` and `assets/flowchart.png` describe this version. Logic diagram (Confluence modules database, 2026-03-12): https://docs.google.com/spreadsheets/d/1xXujLcsT1SQiaC8Bm9AWBjsLkBE3y__iIbO6sfao_As/edit?gid=0#gid=0
- **Dependencies:** exported copy; branch pins `cv_common` dd5b554, `db_worker` 5a4aa83; the export holds `cv_common` ac5098d as a stand-in. NumPy, OpenCV; no weights needed; Docker base `cpu_base`.
- **Run locally:** `python main.py --source <video>.mp4 --inferences-dir <folder> [--cone-camera] [--airplane_type JET|AIRCRAFT] [--write-video]`; without `--cone-camera` the wing-camera rules apply.
- **Code references:** arrival `main.py:76-81`; departure start `:83-105`; departure confirmation and early decision `:764-799`; box shrink `:231-242`; part memory `:111-182`; cones per camera `:723-735`; cone counting `:315-345`; hidden zones `:402-583`; decision `:254-312`; end-of-video decision `:824-828`; jet direction (never runs) `:208-229`.
