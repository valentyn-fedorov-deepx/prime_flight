# ADR-003 · TensorRT fp16 engines for the GM detector heads as a versioned runtime

- **Status:** proposed (2026-09-14) · **Owner:** Valentyn with Yurii · **Tasks:** PF-Q1-16, PF-Q2-02, PF-Q4-02
- **Related:** ADR-001 §6 (changes that alter numbers are versioned), `docs/analysis/gm_speed.md`

## Context

- v1 runs the three GM heads (GM yolov8m @1088, chocks @1280, vehicle yolov8m @1088) as fp16 ONNX models on the ONNX Runtime CUDA
  provider with default session options.
- GM v2 exact path on the RTX 5070 Ti (600 frames, no decode): 22.4 ms/frame with v1's operation sequence, 16.8 ms with one letterbox
  per input size and the heads in parallel threads — rows byte-identical to the v1 sequence.
- TensorRT provider with fp16 engines: 10.6 ms/frame sequential, **8.0 ms/frame** in parallel (GM head 1.2 ms instead of 3.8 ms).
- Rows differ at fp16-noise level: pair recall 99.9–100 %, 99.0–99.2 % of pairs within ±2 px / ±0.02 confidence, confidence delta ≤ 0.028
  — the same order as production GPU vs workstation GPU on the CUDA provider (pair recall 99.8–99.9 % against production files).
- Engines are specific to the GPU architecture, driver and TensorRT version; the first build takes about 17 s per head and is cached.
- A TensorRT session that cannot load its libraries silently falls back to CUDA in ONNX Runtime; `pf/gm/onnx_detector.py` now refuses
  to run in that case.

## Decision (proposed)

1. TensorRT is a **versioned GM runtime**, never a silent swap: the runtime (`cuda-fp16` or `trt-fp16`) is recorded in the GM report and
   travels with the outputs.
2. **Adoption gates** (all required, owned by qa-parity):
   - tolerant L1 on the 7 ATL-C5 videos — pair recall ≥ 99.5 % and frames within tolerance not worse than the CUDA path against
     production;
   - L2 — no verdict change on the comparable pixel-free modules, then on the pixel modules as they become runnable;
   - the same two checks on the production GPU type with engines built there.
3. **Engine policy:** build at deploy time on the target GPU; cache keyed by model hash, GPU architecture, TensorRT version and
   precision; invalidate on TensorRT or driver upgrades; refuse to start on a silent CUDA fallback.
4. **Rollback:** `--provider cuda` stays the reference path. Both runtimes share preprocessing and postprocessing, so switching back
   is a configuration change.

## Consequences

- GM heads about 2× faster than the exact parallel path (16.8 → 8.0 ms/frame on the workstation) → more cameras per GPU in the RT branch.
- Byte-identical regression tests against the CUDA path do not apply to this runtime; its gate is tolerant L1 + L2.
- Operations must build engines per GPU type and manage the cache.

## Evidence log

- 2026-09-14 — 600-frame tolerant parity against the CUDA path: `docs/analysis/speed/gm_bench_600.json`.
- 2026-09-14 — full-video L1 against production and L2 on DjwtQRdZyt0sSk: queued (`out/l2/summary_prod_vs_trtgm.json`).
