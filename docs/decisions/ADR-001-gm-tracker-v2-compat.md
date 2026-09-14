# ADR-001 · GM v2 / Tracker v2: compatibility strategy with the 27 modules and chunk-by-chunk processing

- **Date:** 2026-09-14 · **Status:** proposed
- **Author:** Valentyn · **Reviewers:** Ihor, Yurii, Maksym Ch. (+ Oksana — regarding the verdict semantics)
- **Zone:** GM / Tracker / frame contract / receiver
- **Basis:** `docs/analysis/gm_current.md` (PF-Q1-12), `docs/analysis/module_consumption.md` (PF-Q1-14),
  `docs/analysis/contract_observed.md` (PF-Q1-15), `docs/02_target_architecture.md` §2–5.

## Context

The modules (27) consume not "detections and tracks" but a very specific artifact: the GM **second-pass** file
(`[x1,y1,x2,y2,conf,cls]`, the synthesized `obstacle/side_obstacle`, the main-aircraft row with the height mode in the conf slot) and
the tracker JSON, whose `state_dict` is restored by `from_state_dict` on **10 different cv_common pins** that fail on any
unknown key. GM itself is two-pass and makes all per-video decisions after EOF; 9 modules duplicate the arrival-stage block from
private tracker fields; 4 compare `frame_number == arrival_frame`. Hence "optimize GM+Tracker and verify that
the module accuracy did not drop" is possible only if the interface to the modules is frozen bit-for-bit, and the new is versioned separately.

## Decision

1. **Two output layers, one inference.**
   - **v1-compat (post branch, for the 27 modules as is):** GM v2 + Tracker v2 at the end of the event reproduce the legacy artifacts
     bit-for-bit: the second-pass ndjson (raw rows without `airplane`, rows 29/30 with the same logic, the class-2 row with the height mode,
     1-based keys without gaps) and the tracker ndjson with the same set of `state_dict` keys per class (39 airplane / 34 vehicle,
     as observed). Parity with v1 is proven by `pf.eval.compare_gm_ndjson` + a comparison of `state_dict` on the consumed fields.
   - **v2 (the bus, for streaming and new modules):** `pf.contract` schema `"2.0"`: absolute `frame_id`, raw
     `airplane` rows with the real conf, no synthesized copies, `stage/events/anchors` from the stage detector; tracker objects
     with `schema_version` and without private optical-flow fields in the contract.
   A module that moves to streaming switches from v1 to v2 explicitly (an ADR per module), not "silently".

2. **GM v2 = `gm_core` + `gm_context` + sinks.** `gm_core`: a pure `frame → rows` with the same thresholds (0.35 / chock /
   vehicle), letterbox, fp16 IO-binding and class-agnostic NMS 0.7 — the condition of bit-for-bit parity of the raw rows. `gm_context`:
   incremental per-video decisions with a `decided_at` event (entity 40 hits; aircraft type 500 votes after T_arr; camera —
   the rule of fixing N frames after the stop, **a separate ADR**; parts layout — freeze after ≥240 stable frames;
   main aircraft — the running longest track, the final at the end of the event). The v1-compat sink reproduces the second pass from the raw rows +
   the final context; the v2 sink writes the bus frame by frame.

3. **Tracker v2 does not change `state_dict` for the old modules.** New fields/events (BL@door, BL leave, pushback stationarity,
   `have_arrival_stage` as an event) — only in the track's `data{}` (the modules read only `data.bl_type`) or in the frame fields
   `events/anchors`. One tracker per event (X1), causal; `schema_version` — in the frame wrapper, not in `state_dict`.

4. **The stage detector is the sole owner of the anchors.** T_arr/T_dep/BL@door/BL leave/pushback_attached are computed once after
   the tracker and put into `anchors`; the first step of porting any module is to replace the local arrival-stage block and
   the `frame_number ==` equalities with `anchors` (9 + 4 modules).

5. **Placeholder frames on chunk loss (X2):** an empty frame `general_model: []` leads to 15 modules not updating
   the aircraft track. Proposal: the placeholder frame carries `trackers` with the last known aircraft state and `general_model: []`; the choice
   is fixed after a measurement on the stand (`--drop-mode fill`).

6. **Optimizations that change the output** (rectangular ONNX export 1088×640, fp16→int8, a different NMS, 720p) are allowed only as a
   **versioned** change (`schema_version` or a separate model_version in the report) with a recall re-measurement on a balanced sample.
   Optimizations without an output change (batching across cameras, vectorization of the post-processing, removing the three decodings and SAM on every frame,
   `write_video` off, H2D caching) — without an ADR, with parity only.

## Alternatives rejected

- **Rewrite the modules for the new contract right away.** 27 repos on 10 cv_common pins, 15 with pixels, 13 with own models —
  months of work before the first measured result; risk of regressions without labels.
- **Leave GM single-pass "as is" and only speed it up.** Does not give chunk-by-chunk processing: all per-video decisions wait for EOF.
- **Add new keys to `state_dict`.** Proven by the `_bl_type_*` incident: module crashes on old pins.

## Consequences

- Modules: 0 code changes for the post branch (v1-compat); for streaming — an explicit switch to v2 with parity.
- Client logic (`05_module_logic.md`): unchanged.
- Measurements: L1 parity of the raw rows and `state_dict` (on the consumed fields) on the 7 ATL-C5 videos; L2 parity of verdicts on
  the v1-compat artifacts; GM v2 speed ≤ 28 ms/frame (`measurement_plan.md`).
- Debt that becomes visible: `str2id` as a versioned artifact in `pf/` (requires `cv_common/global_config.yaml`), dead
  GM branches (BL stages, `select_video`, `stages=None`), 8 modules with HEAD ≠ pinned.

## Actions
- [ ] Review by Ihor/Yurii/Maksym Ch.; separate ADRs: the camera fixing rule, the placeholder-frame policy, the `str2id` artifact.
- [ ] PF-Q1-16 (GM v2) and PF-Q1-17 (Tracker v2) are executed per this ADR; the `pf/gm`, `pf/tracker` interfaces already conform.
- [ ] After access to `cv_common` is restored — check `from_state_dict` on the 10 pins (whether it really fails on extra keys).
