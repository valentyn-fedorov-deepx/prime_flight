# The real-time branch as it runs today

Everything below is what the code does now, with the cost measured on one run: `slice_comp2` — the decision slice of
event zHxIAF2vUGxJ (5 048 frames, 10.5 min), per-frame ingest at 10 Mbit/s, real-time speed, three GM heads, the full
tracker and three production modules on a quiet machine. Nothing here is a plan; the plan parts are marked *not wired*.

## 1. What runs

```mermaid
flowchart TB
  subgraph gate["at the gate"]
    cam["CameraBox · 1080p · 8 fps · H.264 ≈4 Mbit/s"]
    enc["per-frame transport (RTSP-like)<br/>or 3.75 s GOP chunks, stream copy"]
    cam --> enc
  end

  subgraph server["server · one process per camera session"]
    rcv["receiver / session<br/>order, gap-fill, absolute frame_id (X2)"]
    dec["decoder (OpenCV, pinned — X4)<br/>4.3 ms/frame"]
    gm["GM v2 · 3 ONNX heads in parallel (CUDA)<br/>gm@1088 · chocks@1280 · vehicle@1088<br/>28.4 ms/frame"]
    rows["causal second run → v1-compat rows<br/>0.15 ms/frame"]
    trk["Tracker v2 · one per event (X1)<br/>airplane · beltloader · gse · person<br/>42.0 ms/frame · publishes 6 frames late"]
    bus["output bus<br/>(component reader threads)"]
    rcv --> dec --> gm --> rows --> trk
  end

  subgraph comps["module components · one OS process each"]
    m1["3-stop-brake-check<br/>in the pipeline process"]
    m2["pushback-pathway<br/>own process · 0.61 ms/frame"]
    m3["pushback-does-not-start<br/>own process · 0.61 ms/frame"]
  end

  subgraph out["outputs"]
    nd["outputs.ndjson + component_outputs.ndjson<br/>written the moment an output is produced"]
    page["live page :8765<br/>diagram · frame · verdicts"]
    http["http_sink(url) — background POST<br/>(the seam for the alert service)"]
  end

  enc -->|"frames, 0.060 s on the link"| rcv
  trk -->|"rows + track records<br/>1.6–2.6 KB per component (declared subscription)"| m1 & m2 & m3
  trk -.->|"pixels, shared-memory ring, ack per frame"| m2
  m1 & m2 & m3 --> bus --> nd & page & http

  subgraph later["not wired yet"]
    stage["stage detector (PF-Q1-03)<br/>T_ARR · BL_AT_DOOR · BL_LEAVE · PUSHBACK_ATTACHED · T_DEP"]
    alert["alert service (PF-Q3-01, Aryan)<br/>identity · deduplication · lifecycle"]
    mongo[("MongoDB event / alert docs")]
    rv["RampVision website"]
  end

  stage -.->|"opens and closes components (gating.json)"| comps
  http -.-> alert -.-> mongo -.-> rv
```

## 2. What each stage adds, and what it costs

| stage | what it does | what it adds to the frame record | measured |
|---|---|---|---|
| transport | per frame as soon as it is encoded, or 3.75 s GOP chunks | — | link 0.060 s p50 at 10 Mbit/s; a chunk instead costs 1.94 s of waiting |
| receiver | orders arrivals, fills a lost chunk with placeholder frames, keeps the absolute `frame_id` | `frame_id`, `capture_t`, `placeholder` | 0.008 s queue |
| decoder | one pinned decoder, frame count checked against the manifest | `image` (BGR, by reference) | 4.3 ms |
| GM v2 | three heads in parallel: gm 15.0 ms inference + 7.2 post, chocks 14.9 + 5.0, vehicle; upload 1.1 ms | `general_model`: `[x1,y1,x2,y2,conf,cls_id]` | 28.4 ms |
| causal second run | the v1 second-run pass done causally (`pf/pipeline/causal_rows.py`) | obstacle / side-obstacle / aircraft rows | 0.15 ms |
| Tracker v2 | one tracker per event, DeepSORT ×3 + optical flow + segmentors | `trackers`: `{tr_id, cls_str, xyxy, conf, state_dict}` | 42.0 ms |
| components | each module in its own process, given only its declared subscription | — | 0.61 ms each; hand-off 0.174 ms per frame for both |
| **total** | | | **73.3 ms of the 125 ms budget** (64.6 ms in the run without subscriptions) |

## 3. How an output arrives

```mermaid
sequenceDiagram
  participant C as camera
  participant P as pipeline (GM → tracker)
  participant M as module component
  participant B as output bus
  participant S as sinks

  C->>P: frame N (0.060 s on the link)
  P->>P: decode + GM + rows + tracker (0.073 s)
  Note over P: the frame is processed 0.13 s after the camera saw it
  P-->>M: rows + records of frame N-6 (the tracker publishes 6 frames late = 0.75 s)
  M->>M: its own logic, 0.6 ms
  M->>B: verdict the moment it decides (its reader thread, not the frame loop)
  B->>S: ndjson file · live page · http POST — immediately
  Note over B,S: measured: 0.80–1.16 s after the frame that decided it
```

The 0.13 s is the frame; the rest is the tracker's publication delay (0.75 s — the worker DeepSORT `N_INIT: 6`, kept for
parity) plus the module's own time. Shortening it is `TrackerOptions.publish_delay`, gated by verdict parity (PF-Q1-17).

## 4. The outputs themselves

Every output is one record — `Output(kind, name, frame_id, payload, emitted_t)` — carrying the **absolute** frame id it
refers to, even for a component whose own session started later.

| kind | when | who produces it today |
|---|---|---|
| `verdict` | the module's own logic decided | all three modules (Pass / Fail / Not observed + report + smart timeline) |
| `alert` | a client rule is met while the session runs | hooks (`pf/rt/hooks/vests.py` for vest status); the other modules answer once |
| `event` | something the branch itself noticed (component opened / closed) | the component shell |
| `note` | audit: non-causal reads, look-back misses, module errors, the run's own report | the module shell and the pipeline |

Where they go **today**: `out/rt/runs/<tag>/outputs.ndjson` (the run's record), `component_outputs.ndjson` (written the
instant a component produces one) and the live page on `:8765`.

Where they go **next**: `http_sink(url)` POSTs each record as JSON from a background thread — that is the interface the
alert service (PF-Q3-01) consumes; from there identity, deduplication and lifecycle, then the MongoDB event/alert docs and
RampVision, exactly as ADR-004 describes. Nothing in the branch waits for that POST: a stalled endpoint drops records into
a counter, never into the frame path.

## 5. What is deliberately not there yet

- **Stage detector** (PF-Q1-03): the gates in `pf/rt/gating.json` are written and reported in every run, but nothing
  publishes `T_ARR` / `BL_LEAVE` / `PUSHBACK_ATTACHED` yet, so every component runs from the first frame.
- **The alert service** (PF-Q3-01): the sink exists, the endpoint does not.
- **The second camera**: one session = one camera. The wing camera is a second instance of exactly this, not a change.
- **The other modules**: 3 of the 11 real-time candidates run; the pixel ones (safety-vests, wing-walkers) need the
  shared-memory ring path exercised on a real run, which the component layer now supports.

## 6. How to run it

```bash
python scripts/rt_watch.py --video <event or slice>.mp4 \
    --module 3-stop-brake-check \
    --extra-modules pushback-pathway-confirmed-clear-of-obstacles,pushback-does-not-start-until-wing-walkers-are-in-place-and-ready \
    --ingest frames --bandwidth-mbps 10 --pause-testset
```

`scripts/rt_slices.py` cuts an event down to the minutes where the modules decide; `scripts/rt_components.py` prints the
component table; `docs/10_ci.md` says what is tested where.
