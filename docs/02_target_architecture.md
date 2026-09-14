# Prime Flight target architecture (to-be): two branches, one contract

A concise summary of the measured results of the gat-streaming stand (test bench) `G:\gat-streaming` (full texts — `streaming_ref/architecture.md`,
`contract.md`, `modules.md`, `testing.md`, `plan.md`; pictures `dataflow.png`, `stage_detector.png`, `stage_cards.png`,
`integration_order.png`). This is the **reference model** for Q1–Q4; Maksym Ch. as the architecture owner may change it via ADR.

## 1. One ingestion, two branches

```
cambox ──► chunks 7.5 s ──► receiver + session registry ──► GM + tracker (one per event) ──► stage detector
 1080p        stream-copy       gap-fill, frame_id                │                              │ stage/events/anchors
 8 fps        no transcode                                        ├──► HOT (real-time): gated modules ──► verdict/alert
 ≈4 Mbit/s                                                        └──► COLD (post): merge + post-analytics on the full recording
```

- The **hot branch** answers now (S1/S2 checks), the **cold** one — what can wait until the end of servicing
  (walk-arounds, lookbacks like conditioned air, reporting checks).
- The post branch **does not run the same models again**: GM/tracker are computed once, the results are shared.
- Q1 makes the first step without RT: chunks travel to the server during recording, GM+tracker run over the chunks, merge — only for
  the archive/post modules.

## 2. Frame contract (the bus)

```python
{
  "schema_version": "1.0",   # X3: without a version, incompatibility is visible only as a module crash
  "frame_id": 1234,          # X2: absolute number, NOT the position in the stream
  "stage": "DOWNLOAD",       # from the stage detector: where we are now
  "events": ["BL_AT_DOOR"],  # transitions that fired on this frame_id (almost always empty)
  "anchors": {"T_arr": 4812, "BL_at_door": 9600},   # absolute ids of past events for lookback windows
  "general_model": [...],    # detections
  "trackers": [...]          # tracks with state_dict
}
```
Reference implementation: `G:\gat-streaming\streaming\contract.py` (`schema_version` check, leakage of
`VEHICLE_ONLY_KEYS` fields between classes), `session.py` (session registry, gap-fill), tests in `tests/`.

## 3. Four correctness conditions (measured)

| # | Condition | Why |
|---|---|---|
| X1 | The tracker is created once per event and is never reset | the same input: end-to-end — 5 "aircraft"; a reset every 60 s — 42; every 7.5 s — 297 |
| X2 | Frame numbering is end-to-end and explicit (`frame_id`), gaps are filled with placeholder frames | modules take `enumerate(metadata, 1)`; the loss of one 7.5-s chunk → a 60-frame mismatch in `frame_number == aircraft.departure_frame` |
| X3 | `schema_version` in every record | 15–16 incompatible versions of inferences per video in `gs://cv-modules-topics` without a marker |
| X4 | The decoder is pinned on both sides of the comparison | ffmpeg drops frames on non-monotonic DTS, OpenCV reads them all: 22 791 vs 22 800 |

## 4. Chunking

A chunk is the unit of **transport**. GOP 3.75 s → chunk 7.5 s (2 GOPs); stream-copy without re-encoding; the actual chunk
length is up to 11.25 s (the last one takes the remainder) — therefore "frame number within the chunk" does not exist, only `frame_id`.
Latency: **10.5 s versus 84 s** for 60-second chunks. Parity of chunked feeding with end-to-end is bit-exact (D1 done).

## 5. Stage detector — a causal state machine after the tracker (the single owner of anchors)

```
PRE_ARRIVAL ──T_arr (tracker: 4 s stop)──► ARRIVAL/POST-ARRIVAL ──BL@door (iou(BL, aircraft)>0.2 ∧ stopped)──► DOWNLOAD/UPLOAD
   ──BL leave──► PRE_DEPARTURE ──T_dep (tracker: 10 s motion)──► DEPARTURE (until T_dep + 60 s)
   event inside a stage: pushback_attached = nose geometry ∧ pushback box stationary for N s
```
- Puts `stage`, `events`, `anchors` into every frame; tells the session registry which modules to open/close.
- Replaces the 9 copies of "arrival stage" in the modules and the 2 copies of `pushback_attached` (aircraft-chocks, pin-verification).
- Gating: instead of 27 always-on workers — 4–9 active per stage. Lookback modules run from the start of the stage and
  report at its end; they need no replay buffer.
- The lower bound of the alert latency = the event latency: 4 s after the stop, 10 s after the start of motion (the tracker's `_arrival_thresh`,
  `_departure_thresh`).
- BL@door and BL leave **are not tracker events today** — the detector has to produce them (lifted from 3-stop / beltloader-chocks).
- Deliberately outside the detector: ETA/ETD from the schedule.

## 6. Frame budget (RTX 5070 Ti, core profile, 8 fps → 125 ms)

| component | ms/frame |
|---|---|
| decode | 2.90 |
| GM detection | 28.29 |
| tracker | 0.11 (stand placeholder: a hard-coded replay constant, `simulate.py:305`; the real cv_trackers cost — optical flow on ≤ 250 points + segmentation — is not measured yet, PF-Q1-13 §8) |
| module logic (simplified) | 0.03 |

Real-time comes down to the detector and its plumbing (3.95× real-time on a full turnaround; short tests overestimate).
Caveat: the real `aircraft-chocks` runs effnetb0 inference every frame on each rear wheel — two orders of magnitude more expensive,
but it fits into the budget. 720p instead of 1080p: speed does not change, recall −≈3 %.

## 7. Module classification: two axes + integration queue

- **Axis 1 — causality**: how many passes over the metadata and whether the decision at frame N relies on the future.
- **Axis 2 — pixels**: whether decoded frames are needed (`dataset.get_im0s`) or the contract is enough (`--no-video`).
- The verdict per module is in `04_modules.md` (NOW / NOW_PX / PATCH / RETHINK / POST).

Queue (from `integration_order.png`): **E0·I1** first — `beltloader-chocks`, `pushback-does-not-start-until-wing-walkers…`,
`pushback-pathway…`; then the rest of E0 (12 modules as they are), E1 (frames without models, 4), E2 (frames + models, 5, after measuring
the per-frame cost), E3 (aircraft-chocks, pin-verification — waiting for the detector event), E4 (rewrite the first pass:
hand-signals, safety-zone) and POST (walk-arounds) — at the end or never.

**Two caveats without which the table lies**: technical readiness ≠ usefulness (beltloader-chocks completeness 83 % vs
pushback-pathway 0 of 4 at the same E0·I1); the labels are almost empty on 3 of 4 checks (Nose wheel — 1 fail in 90 videos) →
measure the paired batch↔stream difference, not the absolute accuracy.

**S1 checks (seconds matter)** — safety zone, pushback pathway, "pushback does not start without walkers", hand signals —
all make the decision after the fact. Delivery within seconds will not help without a **trigger change**: a separate track (Q3–Q4),
tagged `trigger-change`.

## 8. What does not exist today (components to build)

| component | state | owner in PF |
|---|---|---|
| chunk receiver (ordering, gap-fill) | reference in `gat-streaming/streaming/session.py` | pipeline-architect |
| session registry (one event = one tracker = one set of states) | modelled | pipeline-architect |
| schema contract | `contract.py` | gm-tracker-engineer |
| stage detector | design (`stage_detector.png`), no code | pipeline-architect |
| alert bus (deduplication, quiet windows, delivery) | not in the CV zone; 357 alerts on one video without deduplication | alerting-engineer |
| transport cambox → server (Wi-Fi/SIM, VPN, ≈4 Mbit/s per camera) | none | pipeline-architect + request to the outside |
| GPU runner for nightly parity | none (request to Ihor) | qa-parity |
