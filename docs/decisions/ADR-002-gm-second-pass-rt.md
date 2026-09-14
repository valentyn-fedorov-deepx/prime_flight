# ADR-002 · GM v2: `camera_type` and `frame_stopped` in the chunk-wise pipeline

- **Status:** proposed (2026-09-14) · **Owner:** Valentyn (lead) with Yurii · **Tasks:** PF-Q1-16, PF-Q1-03 (stage detector), PF-Q2-02
- **Related:** ADR-001 (v1-compat sink + v2 bus), CLAUDE.md invariant "the stage detector is the single owner of anchors"

## Context

GM v1 (production commit a0157a4) decides two report fields after the end of the video, in a second decode of the whole file:

| field | v1 mechanism (`general_model/main.py`) | consumers |
|---|---|---|
| `camera_type`, `confidence_camera` | EfficientNet-B0 cone/wing classifier on **every** frame that has the main aircraft after arrival (rows 150:930 of the noise-preprocessed frame, BGR order, PIL resize to 224); majority at the end, confidence = share of the majority (`:924-963, 1117-1126`) | `model_starter.py` passes it to every module as `cone_camera` and uses it to choose the module set |
| `frame_stopped` | `arrival_frame` of a `cv_common.Airplane` updated on every main-aircraft frame with MobileSAM masks and optical flow on noise-preprocessed frames (`:884-909`) | `cones-placed-in-proper-positions-and-timely`, `steering-by-pass-pin-installed-or-steering-otherwise-bypassed`, `wing-walkers-in-proper-position-and-using-approved-wands` (via the starter's description) |

Measured on `DjwtQRdZyt0sSk` with the exact port (`pf/gm/second_pass.py`, `pf/gm/camera.py`; `tasks/notes/PF-Q1-16.md`):

- `frame_stopped = 3 725`; camera **cone**, confidence 0.9964 over 17 456 votes, 31 votes with a probability between 0.4 and 0.6.
- The tracker already computes its own airplane `arrival_frame` (3 669 on the same video): the same state-machine family,
  YOLO-seg masks on non-preprocessed frames, rewritten back to the first stopping frame. Two notions of "arrival" exist today.
- Cost of the v1 second pass: **24.5 ms/frame** over the whole video — classifier 7.2 ms (19.8 ms per call), preprocessing
  8.4 ms (about half removed exactly by on-demand preprocessing), Plane update 4.2 ms, decode 3.6 ms.

In the real-time branch there is no "end of the video", the budget is 125 ms/frame per camera, and anchors must have one owner.

## Decision (proposed)

1. **Batch / v1-compat branch — exact.** Run `pf.gm.second_pass.SecondPass` exactly as v1 (MobileSAM plane on every main-aircraft
   frame, classifier on every arrived frame, majority at the end), with the output-identical on-demand preprocessing. The
   v1-compat report keeps `camera_type`, `confidence_camera` and `frame_stopped` with v1 semantics. Cost is acceptable in batch.
2. **RT branch — camera type as an early, sampled decision.** Vote on every 8th frame that has the main aircraft after arrival;
   emit `camera_type` (with `decided_at`) once at least 50 votes are in and the running share is ≥ 0.9 or ≤ 0.1, otherwise keep
   voting until the end of the event. `confidence_camera` becomes the share of the sampled votes and is versioned through
   `schema_version` (its decimals differ from v1; the decision must not).
3. **RT branch — no second aircraft state machine.** `frame_stopped` / T_arr is owned by the stage detector (PF-Q1-03), fed by the
   Tracker v2 airplane state that the RT branch already computes. GM v2 in RT does not run MobileSAM on the aircraft.
4. **Switch conditions** (qa-parity blocks the switch until all are met):
   - camera decision identical to the production GM report on the 7 ATL-C5 videos and on a balanced sample with wing cameras;
   - a table of T_arr (stage detector) vs v1 `frame_stopped` per video; the L2 gate on the three modules that read `frame_stopped`
     shows no verdict change; any change is explained and signed off by Ihor;
   - production GM reports (`camera_type`, `frame_stopped`) retrieved from MongoDB for the comparison — until then the exact
     batch port is the reference.

## Consequences

- The RT GM avoids roughly 20 ms/frame of second-pass work per camera, and "arrival" gets a single owner.
- The v1-compat branch stays behaviour-identical; the two branches may report different `frame_stopped` values (for example
  56 frames on `DjwtQRdZyt0sSk`), which is exactly what the switch conditions measure.
- Needs MongoDB access (or another source of production GM reports) before the RT switch.

## Open questions

- Which production collection holds the GM report (`camera_type`, `confidence_camera`, `frame_stopped`) per event?
- Do the three consuming modules expect "stop counter completed" (v1 GM) or "first stopping frame" (tracker) semantics?
- Wing-camera share of the fleet — the sampled vote rule needs wing-camera videos in the validation sample.
