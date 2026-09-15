# ADR-004 · Real-time components and their interfaces (integration skeleton)

- **Date:** 2026-09-15 · **Status:** proposed
- **Author:** Valentyn · **Reviewers:** Ihor, Serhii; Maksym Ch. (owner of the event contract), Yurii, Aryan
- **Zone:** frame contract / stage events / infra

## Context

Real time is the client priority (PF-Q2-07). Its components are built in parallel by different owners:
- GM + Tracker for real time — Valentyn, PF-Q2-02;
- stage detector and event context — Maksym Ch., PF-Q1-03, PF-Q2-14;
- lightened modules — Yurii, PF-Q2-11 / PF-Q2-12;
- alert hooks — Vladyslav, PF-Q2-10;
- alert service — Aryan, PF-Q3-01.

They have to plug into one runtime without waiting for each other. The RT prototype (`pf/rt`, PF-Q1-19) already runs
chunks → receiver → decode → production modules on live frames, with GM / tracker rows replayed from files. What is
missing is a written contract between the components. Which modules run in real time, and therefore what GM, the tracker,
the stage detector and the context must provide, is fixed in `docs/analysis/rt_module_selection.md`.

## Decision

One runtime per camera session (`pf/rt`) passes one record per frame through the components in a fixed order. Each
component reads the fields of the components before it and adds its own. Every record carries `schema_version` and the
absolute 1-based `frame_id` (X2, X3).

```
ingest ─► decode ─► GM ─► tracker ─► context ─► stage ─► gating ─► modules ─► outputs ─► alert service
```

| component (owner) | adds to the record | contract |
|---|---|---|
| ingest: receiver, session (Maksym Ch., after the stage detector; prototype today) | `session_id`, `camera_id`, `frame_id`, `capture_t`, `placeholder` | chunks released in recording order; lost frames become placeholders (X2) |
| decode (runtime) | `image`: BGR, passed by reference, never copied into modules | pinned decoder, frame count checked per chunk (X4) |
| GM (Valentyn) | `general_model`: `[[x1, y1, x2, y2, conf, cls_id], …]` | the v1 row format and class ids of the modules' pins (ADR-001); all 26 decision classes, three heads |
| tracker (Valentyn) | `trackers`: `[{tr_id, cls_str, xyxy, conf, state_dict, data}]` | one tracker per event (X1); the v1 `state_dict` keys the RT modules read; a frame moves on only after the tracker has published its record |
| context (Maksym Ch.) | `context`: `{camera_type: cone / wing / null, aircraft_type: aircraft / jet / null, entity, decided_at: {field: frame_id}, source: {field: registry / classifier}}` | a field stays null until decided; a changed decision is an event, never a silent overwrite |
| stage (Maksym Ch.) | `stage`; `events` fired on this frame; `anchors`: `T_ARR`, `BL_AT_DOOR`, `BL_LEAVE`, `PUSHBACK_ATTACHED`, `T_DEP` as absolute frame ids | causal: an event fires with its declared latency (4 s after a stop, 10 s after motion starts), never from future frames |
| gating (runtime, table from the stage detector) | opens and closes module sessions | one row per module: cameras by aircraft type (client split), `open_on`, `close_on`, `lookback_frames`; a module opened late gets its look-back from the frame buffer; the end of the session is a marker, never a known length |
| modules (Yurii, Vladyslav) | — | adapter `start(context)`, `on_frame(record)`, `close(end_of_session)`; reads only the record; returns outputs |
| outputs (runtime) | `Output{kind: verdict / alert / resolved / event / note, name, frame_id, payload, emitted_t}` | written when emitted; an alert carries the object, the frame where the client rule is met and evidence frame ids |
| alert service (Aryan) | — | consumes `alert` and `resolved`; identity, deduplication, lifecycle, delivery (PF-Q3-01) |

Each component can be built and tested before the others exist:
- **Replayed inputs:**
  - production GM and tracker ndjson of the 90 test-set videos (bucket `cv-modules-topics`, `scripts/testset/fetch.py`);
  - the GM v2 and Tracker v2 outputs of the same videos.
- **Stubs in `pf/rt`** for every missing component: rows from files for GM and the tracker, a fixed context, an always-open
  gate.
- **One runtime and one report for everyone:** latency per component, drift, backlog.

## Alternatives rejected

- **A message broker between components from the start** (Kafka / Pub/Sub). It adds infrastructure before the components
  exist. The record format stays the same, so a broker can replace the in-process queues later.
- **Each owner integrates directly with the modules.** Every module would get its own notion of stage, camera and aircraft
  type — the drift we are removing (9 local copies of the arrival stage).
- **GM and tracker with fewer classes for real time.** The 22 RT modules read all 26 decision classes
  (`rt_module_selection.md`).

## Consequences

- **For modules:** unchanged in v1. They receive the record through the production adapter (`pf/rt/prod_module.py`).
  Modules that read the session length get it only at the end-of-session marker.
- **For the client logic** (`05_module_logic.md`): unchanged. Gating must not change verdicts, so gated and always-on runs
  are compared on the module sample.
- **For measurements:**
  - latency and cost per component in the runtime report;
  - gating parity;
  - alert quality through PF-Q2-08.

## Actions

- [ ] Review by Maksym Ch. (owner of the event contract) and Yurii; accept or amend.
- [ ] `pf/rt`: record type with `schema_version`, component stubs, gating table loader (PF-Q2-13).
- [ ] Notify module-porter and alerting-engineer.
