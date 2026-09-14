# Streaming pipeline v0 — GM v2 + Tracker v2 on chunks as they arrive

Status: code 2026-09-14 (PF-Q1-04 foundation). Code: `scripts/stream_pipeline.py`, `pf/pipeline/causal_rows.py`,
`pf/tracker/events.py`, `pf/stage/pushback.py`. Validation: smoke run on 4 200 frames and a full-video run with L2 — results
are added below when they land.

## Data flow

```
chunk (60 frames = 7.5 s)
  └─► GM heads (3 × YOLOv8, parallel, byte-identical rows) ─► first-run rows ─► VideoContextV2 (decisions with decided_at)
        └─► causal second-run rows: frame t's box of the CURRENT longest aircraft track; mode height and layout
            (front wheel, side regions) refreshed per chunk and when the main track appears or changes
              └─► Tracker v2 (exact fast paths; one instance per event; records final after the N_INIT delay of 8 frames)
                    ├─► events from the published records: T_ARR, T_DEP, BL_AT_DOOR, BL_LEAVE
                    ├─► PUSHBACK_ATTACHED (aircraft-chocks' causal nose rule)
                    └─► v2 bus frame per published frame: schema 1.0 + GM rows + tracker records without `_p0/_st`
                        + events fired on that frame + anchors so far
```

The run also writes what the 27 modules read today (a streaming second-run GM file and a v1-compat tracker file), so the
L2 gate can compare module verdicts on streaming outputs with production.

## What is causal and what differs from the batch path

| output | batch (v1 and the v1-compat branch) | streaming v0 | expected difference |
|---|---|---|---|
| GM first-run rows | per frame | per frame, same heads and order | none |
| main aircraft row (class 2) | longest track of the WHOLE video, mode height of the whole track | longest track at frame t, mode refreshed per chunk | frames before the main track settles; the height in the conf slot while the mode moves |
| obstacle rows (29 / 30) | final front wheel and side regions | layout refreshed per chunk | frames before the layout decision (≈ 30 s of wheel or nose sightings) |
| tracker records | v1 tracker on the final second-run file | Tracker v2 on the causal rows | as far as the rows differ; publication lags by 8 frames (1 s), longer while the airplane buffer holds arrival frames |
| T_ARR, T_DEP, BL_AT_DOOR, BL_LEAVE | modules recompute them from files after the video | derived when the records are published | none on the batch inputs (production DjwtQRdZyt0sSk vs GM v2 → Tracker v2: identical frames) |
| PUSHBACK_ATTACHED | aircraft-chocks and pin-verification, two passes | nose rule, causal | identical where production uses the nose rule (5 of 7 ATL-C5 videos); earlier where production uses its look-ahead median rule (−183 and −18 frames) |
| camera type, frame_stopped | GM second pass after the video | not in v0 | ADR-002 |

## Measured so far

- Tracker events on the batch path, full DjwtQRdZyt0sSk video: T_ARR 3 669, front door occupied 9 888–22 776, the same
  re-identification frame — identical between production and GM v2 → Tracker v2
  (`stage/events_DjwtQRdZyt0sSk_production_vs_gmv2_trackerv2.json`).
- PUSHBACK_ATTACHED on the 7 ATL-C5 videos: `stage/pushback_attached_atlc5.json`.
- **Smoke run, the first 4 200 frames of DjwtQRdZyt0sSk** (GPU shared with the GM chain): 70 chunks, 65.2 ms/frame = 1.9× real
  time (GM heads + context 41.6, causal rows 0.16, Tracker v2 16.8, events and bus 0.3). Tracker records are published 5 frames
  after their frame at the median, 22 at p99 and 60 at most (the airplane buffer around arrival). T_ARR fires with frame 3 669 —
  the production value — and is published at frame 3 729, 7.5 s later.
- Streaming vs batch second-run rows from the same first-run rows: every main-aircraft row is there (695 of 695); on 6 % of those
  frames only the height written into the conf slot differs (running mode 680, final 670). Obstacle rows are identical from the
  frame the front wheel is first known (3 945: the same rows on 243 of 243 frames). The 2 563 batch obstacle rows before that
  frame exist only because v1 applies the final front wheel to the whole video — the first one at frame 4, long before the
  aircraft appears. No causal pipeline can produce them; the L2 run on the full streaming outputs shows whether a module
  depends on them.
- Full streaming run and L2 on its outputs: queued after the idle speed suite.

## Known limitations of v0

- Chunks group the frames of the local video; there is no transport yet, and no lost chunk is simulated in the run (the
  receiver's gap filling is tested separately in `tests/test_session.py`).
- Modules still consume files after the video; module streaming entry points are PF-Q2-03.
- Camera type and `frame_stopped` are not produced in streaming (ADR-002 decides how).
- `schema_version` exists at the frame level only; the tracker `state_dict` stays frozen (ADR-001).
- The aircraft-chocks median rule for PUSHBACK_ATTACHED has no causal equivalent; the v0 event can fire earlier than
  production on videos where production uses it.
