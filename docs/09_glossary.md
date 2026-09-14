# Prime Flight / DXGAT glossary

| Term | Meaning |
|---|---|
| **DXGAT** | DeepX Ground Aircraft Turnaround — a CV system for checking the safety of aircraft servicing at the gate. |
| **Prime Flight (PF)** | The 12-month roadmap of the transition to continuous upload → real-time; the main KPI is Time to Result. |
| **Time to Result** | The time from the end of the event to the result on RampVision. Currently ≈24 h. |
| **Turnaround / turn / full turn / event** | One servicing of an aircraft from pre-arrival to departure; one full-turn video per camera. |
| **CameraBox / cambox** | The device at the gate with a camera; records 1-minute mp4 chunks and uploads them to the bucket. |
| **Cone camera / wing camera** | The two gate cameras: cone looks at the nose/front zone (cones, chocks), wing — at the wing/BL/doors. The distribution of tasks across cameras is in `05_module_logic.md`. |
| **Aircraft / Jet** | The two aircraft types (classified by the GM); some tasks run on different cameras depending on the type. |
| **Chunk** | The unit of video transport. Currently 1 min; target 7.5 s (2 GOPs of 3.75 s), stream-copy. |
| **Merge script** | The `camera_software` script that assembles the full-turn video from chunks. In PF it is moved off the critical path. |
| **GM (General Model)** | YOLO object detector + classification of the camera, the aircraft type, the entity (airline). Per-frame `.ndjson`. |
| **Tracker / cv_trackers** | Tracking of the aircraft, beltloaders, GSE, people; provides `state_dict` (arrival/departure, stops, BL near the door). |
| **Module / check** | A repo in `dxgat/detectors/*` that from GM+tracker ndjson (and pixels) gives a verdict on one checklist item. 27 modules, some with several checks (aircraft-chocks: M02A/B/C). |
| **Pass / Fail / Not observed / NO with obstacles** | The four verdicts; the semantics are defined by the client (`05_module_logic.md`). NO = did not see enough; NO with obstacles = blocked by an obstacle. |
| **Merge logic** | Combining the verdicts of the two cameras: Fail → Pass → Not observed. |
| **ProdReady** | A flag from the client xlsx: the task is in production (True/False). |
| **Tier (real-time / streaming / post)** | The client's division of where a check should be computed. Real-time = seconds, streaming = live stream to the server, post = after the event. |
| **Smart timeline** | Module output for visualization on RampVision (bucket `modules-inferences`). |
| **RampVision** | The client website with results by events and gates. |
| **T_arr / T_dep** | Arrival/departure anchors from the tracker: 4 s stop / 10 s motion (latency 4 s / 10 s). |
| **BL** | Beltloader (belt loader). **BL@door** — the BL stopped near the aircraft (iou > 0.2); **BL leave** — it drove away. |
| **GSE** | Ground Support Equipment — ground vehicles (BL, fuel truck, trailer, pushback…). |
| **pushback_attached** | The "pushback attached to the nose" event; today computed by two modules non-causally; in PF — a stage detector event. |
| **Stage detector** | A causal state machine after the tracker: PRE_ARRIVAL → ARRIVAL/POST-ARRIVAL → DOWNLOAD/UPLOAD → PRE_DEPARTURE → DEPARTURE; the single owner of anchors; gates the modules. |
| **Frame contract** | The schema of a record on the bus: `schema_version`, `frame_id`, `stage`, `events`, `anchors`, `general_model`, `trackers`. |
| **X1–X4** | The four streaming correctness conditions (`02_target_architecture.md`). |
| **Hot / cold branch** | The real-time branch (gated modules, alerts) / the post branch (merge + post-analytics). |
| **E0…E4, POST** | The effort of porting a module: E0 as is; E1 frames without models; E2 frames + models; E3 detector event; E4 rewrite the first pass; POST — post-processing by nature. |
| **I1/I2/I3** | Weight for alerts: critical / important / reporting. |
| **S1…S4** | Tier of immediate reaction: seconds matter / minutes, the state is reversible / reminder / impossible by nature. |
| **NOW / NOW_PX / PATCH / RETHINK / POST** | Verdict of a module's readiness for streaming (`module_map.json`). |
| **Lookback / live / instant / deadline / event / whole** | Type of module decision: evaluation of a window before T / accumulation from an event / one detection → Fail / Fail if X is not seen by T / verdict at the moment of the event / the whole event is needed. |
| **Parity** | Comparison of batch ↔ stream verdicts on the same video; valid at any class balance. |
| **Balanced sample** | All fails from the labels + the same number of passes (`tools/pick_balanced.py`). |
| **Class leakage** | `Vehicle` fields (`_bl_type_*`) in the aircraft state → `ValueError` in a module; caught by `check_class_leakage()`. |
| **cv-modules-topics** | The GCS bucket with per-frame GM/tracker ndjson (15–16 versions per video without `schema_version`). |
| **DVC** | Storage of model weights outside git. |
| **ADR** | Architecture Decision Record — `docs/decisions/`. |
| **trigger-change** | Tag of a task that changes the moment/condition of a check's decision (requires sign-off from Ihor/Oksana). |
