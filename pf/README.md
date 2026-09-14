# `pf` — Prime Flight core package

Here we assemble, piece by piece, the streaming version of the DXGAT CV pipeline. The order is the one from the roadmap: contract and receiver
(done), then GM v2 and Tracker v2 (after the analysis in `docs/analysis/`), then the stage detector, then module adapters.

| Package | State | What it is |
|---|---|---|
| `pf.contract` | **done, tests** | Frame contract schema 1.0: `schema_version`, `frame_id`, `general_model`, `trackers` + optional `stage`/`events`/`anchors`; hygiene of field leakage between tracker classes. Ported from the `gat-streaming` stand (test bench). |
| `pf.receiver` | **done, tests** | `Session`: one event = one continuous stream = one tracker (X1); gap filling with placeholder frames (X2); `stream_from_chunks` for transport tests. |
| `pf.eval` | **done, tests** | Parity: stream digests, `diff_streams`, `compare_gm_ndjson` (old vs new GM per frame, with tolerance, matched by `frame_id`), `compare_tracker_ndjson` (consumed `state_dict` fields, identity by `(cls_str, _obj_id)`, `_p0/_st` by length). Streams a 600 MB production file in ~13 s. |
| `pf.gm` | **core + context + v1-compat sink, tests** | `geometry` (letterbox arithmetic, ported box helpers, cv_common assumptions flagged), `onnx_detector` (numerically faithful port of the v1 ONNX wrapper), `rows` (first-run rows, `ClassMap`), `context` (`VideoContextV2`: parts layout, main aircraft, entity, aircraft type, camera — each with `decided_at`), `compat_writer` (regenerates the legacy second-run ndjson). Not yet run on real weights (DVC/gcloud access, PF-Q1-16). |
| `pf.pipeline` | **done, tests** | `GmStream`: chunk-wise driver — rows → context → contract frames through `Session` (gaps filled), events with frame ids, `write_v1_compat()`, `report()`; CLI `scripts/gm_v2_run.py` (OpenCV decoder, timings, `--compare` vs production). |
| `pf.tracker` | interface | `Tracker.update(frame_id, detections)` causal, one per event; `state_dict` per class = the contract. Implementation — after the tracker analysis (requires access to `cv_trackers`/`cv_common`). |
| `pf.stage` | vocabulary | `STAGES`, `EVENTS` (in `pf.contract.frame`). The state machine — task PF-Q1-03. |

## Rules for code in `pf`

- The inference core knows nothing about video files, chunks, MongoDB or buckets — only frame → detections / detections → tracks.
- Everything the modules consume today (detection format, `class_id` map, `state_dict` keys, frame numbering from 1)
  stays bit-for-bit compatible, or changes via an ADR + `schema_version`.
- Every change is proven by parity on real ndjson (`pf.eval`) and by measurements on fail videos, not "by eye".
- Fast gates (`pytest`) do not need torch/onnx/opencv and must run in < 1 s.

```bash
pip install -e ".[ci]"   # or simply: pip install pytest
pytest
```
