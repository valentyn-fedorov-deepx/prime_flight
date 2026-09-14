# DXGAT production architecture today (as-is, September 2026)

Sources: the diagrams "Dataflow diagram of DXGAT video processing" and "Cambox flow diagram" (Confluence), the code of `db_worker`,
`general_model`, `cv_trackers`, `camera_software`. Everything below is post-processing: no result appears until
the event (turnaround) is finished and the chunks are merged into a full-turn video.

## 1. Cambox flow (at the gate)

```
camera (cone / wing) ──1-min mp4──► CamboxChunks bucket (GCS)
   │                                     │
   ├─ logs ──► logs bucket ◄── logs handling (Cloud Run)
   ◄─ ping ── ping service (Cloud Run) ──DB record──► MongoDB
                                         │
                       pub-sub-camboxes-subscriber (Cloud Run):
                       collects chunks into a list for the merge script
                                         │  pub-sub cam. sub. logic
                                         ▼
                                    Merge script ──full turns──► ML processing pipeline
```

- CameraBox records **1-minute videos** (1080p, 8 fps, H.264, ≈4 Mbit/s per camera) and uploads the chunks to the bucket
  after/during the event — this is exactly where Q1 adds upload over Wi-Fi/SIM **during recording**.
- `ping service` watches the camera's liveness and writes a record to MongoDB; `logs handling` stores the logs.
- `pub-sub-camboxes-subscriber` builds the list of the event's chunks for merge.

## 2. Processing dataflow (server, GKE)

```
Cambox ──chunks──► CamboxChunks (GCS) ──Cambox bucket checker──► Merge Script (GKE Job) ──video merged──► Videos-to-process (GCS)
                                                                                                             │ subscriber
        ┌────────────────────────────────────────────────────────────────────────────────────────────────────┘
        ▼                              Receiver                            Receiver
  General Model (GKE Job) ─────────────────────► Trackers (GKE Job) ─────────────────────► Modules (GKE Jobs)
  · object detection                             · tracking of aircraft, BL, GSE, people   · CV module inference
  · camera classification (cone / wing)                                                    · smart timeline
  · aircraft type (aircraft / jet)                                                          │
  · entity (airline)                                                                        │
        │ per-frame inferences .ndjson             │ per-frame tracks .ndjson               │ smart-timeline data
        ▼                                          ▼                                        ▼
  cv-modules-topics (GCS bucket: GM / tracker inference storage) ◄── modules read GM+tracker ndjson
                                                                                     modules-inferences (GCS) ──► RampVision Website
  GM / Trackers / Modules ──update video doc, create/update event doc, video/event tasks──► MongoDB ──video & event data──► RampVision
```

The raw full-turn video goes to the GM, to the trackers and to the modules (some modules read pixels — see axis 2 in `04_modules.md`).

## 3. What exactly each node does

| Node | Repo | Role | Output |
|---|---|---|---|
| Merge Script | `camera_software` (`merge.py`, `chunks_handling/`) | find, order and merge the chunks into a full-turn video; event-boundary classifier | mp4 in Videos-to-process, notifications |
| General Model | `detectors/general_model` (`main.py`, `scripts/engine_script.py`) | YOLO detections (GM_yolov8m @1088 + chocks_v4.3 @1280 etc.), cone/wing camera, aircraft type, entity | per-frame `.ndjson` in cv-modules-topics |
| Trackers | `utils/cv_trackers` (`tracker.py`, `local_utils/bl_utils.py`) | identity and motion: aircraft (arrival/departure by 4 s / 10 s of stop/motion), BL, GSE, people; semantics of the BL near the door | per-frame `.ndjson` tracks with `state_dict` |
| Modules | `detectors/<27 repos>` (`main.py` each) | check logic; reads GM+tracker ndjson (and pixels, if needed) | Pass/Fail/NO + report + smart timeline |
| db_worker | `utils/db_worker` (`ML_worker.py`, `model_starter.py`, `send_report.py`) | loading media/metadata, launching the models, reports to MongoDB | video/event docs, tasks |
| cv_common | `utils/cv_common` | shared library: `tracked_object.py`, `transport.py`, `detections.py`, `image_preprocessing.py` | — |

## 4. Known bottlenecks (why Time to Result ≈ 24 h)

1. **Waiting for the event to finish and for merge**: nothing starts until all chunks are uploaded and merged. Q1 removes this
   (upload during recording + per-chunk processing without early merge).
2. **Sequential GKE jobs** GM → trackers → modules on the full video; 27 modules = 27 always-on workers per video.
3. **9 modules recompute the arrival stage themselves** from the tracker's private fields, 2 — `pushback_attached` in a second pass
   (aircraft-chocks, pin-verification). Every copy drifts → stage detector as the single owner (Q1).
4. `db_worker.ML_worker.load_source` for rtsp/http throws `Exception("Stream is not implemented yet")` — stream ingestion
   is absent in production, the RT branch is built from scratch (Q2).
5. The tracker's `state_dict` schemas have no version: 15–16 versions of inferences per video in the bucket, incompatibility is visible only as a crash.
6. Modules are pinned to **different** versions of `cv_common` (ac5098d, dd5b554, 86731e4 …) — shared components need unification.

## 5. What is computed where (for tiering)

- **Edge (CameraBox)**: recording and upload only. The budget and the hardware on the camera do not provide for inference.
- **Streaming (server, live)**: the RT branch — the stream goes to the server, GM+tracker+stage detector+RT modules, budget 125 ms/frame @ 8 fps.
- **Post (server, after the event)**: as now, on the full-turn — walk-arounds, conditioned air lookback and everything that is "POST by nature".
