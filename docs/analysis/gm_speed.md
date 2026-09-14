# GM v2 speed — measured configurations, and what changed the numbers

Status: measured 2026-09-14 (PF-Q1-16 / PF-Q1-15). Raw reports: `docs/analysis/speed/`. Scripts: `scripts/gm_bench.py`,
`scripts/gm_ep_probe.py`.

Setup for every number below: RTX 5070 Ti (sm_120), onnxruntime-gpu 1.29 (CUDA EP), TensorRT 10.16 (pip), torch 2.11+cu128;
the three fp16 ONNX heads of production GM commit a0157a4 (GM yolov8m @1088, chocks @1280, vehicle yolov8m @1088),
production preprocessing (BGR→RGB), batch 1, 600 frames of `DjwtQRdZyt0sSk.mp4` from frame 3 600 (arrival phase: aircraft,
GSE, persons), frames pre-decoded (decode is NOT included; OpenCV decode costs 2.5–3.7 ms/frame in the full-video runs).

## 1. Correction of the earlier figures (73–79 ms/frame, "vehicle head 43 %")

The first port of the detector (`pf/gm/onnx_detector.py`, commit 91d6bfa) created the ORT session with
`cudnn_conv_algo_search=DEFAULT`. v1 (`general_model/scripts/new_model.py:232`) passes plain provider names, i.e. the
onnxruntime defaults (`EXHAUSTIVE`). On this GPU + cuDNN 9.19 the `DEFAULT` heuristic returns no usable algorithm and
onnxruntime runs **every one of the 64 convolutions of a head in "Fallback mode"** (warning in stderr) — 2.6× slower and
with different fp16 rounding. Probe on the GM head alone (`gm_ep_probe.py`, 150 frames, inference only):

| session options | inference ms/frame | rows identical to `DEFAULT` run |
|---|---|---|
| CUDA EP, `cudnn_conv_algo_search=DEFAULT` (first port) | 9.30 | — |
| CUDA EP, `HEURISTIC` | 3.56 | 1 / 150 frames |
| CUDA EP, `EXHAUSTIVE` (= v1 / onnxruntime default) | 3.56 | 1 / 150 |
| CUDA EP, no options (exactly v1) | 3.58 | 1 / 150 |
| TensorRT EP, fp16 engine (17 s build, cached) | 1.52 | 0 / 150 |

Consequences: (a) the detector now uses the v1 options (`cudnn_conv_algo_search` stays configurable for experiments);
(b) all ms/frame figures published earlier today in `gm_prod_delta.md` and `tasks/notes/PF-Q1-16.md` (73.3 / 77.6 / 79.3
ms/frame, "vehicle head 43 %") are void — they measured the fallback path; (c) the parity figures are unaffected in kind:
the fallback kernels were just another set of fp16 kernels, so the tolerant metric (pair recall, ±2 px / ±0.02) stays the
acceptance criterion and the "bit-exact" percentages will move with any kernel change (not a target, `measurement_plan.md` §3.1).

Lesson recorded for the port: **never add session/provider options v1 does not set**; every option is a versioned change.

## 2. Configurations (600 frames, all three heads, no decode)

| configuration | ms/frame | fps | inference GM / chocks / vehicle (ms) | rows vs baseline |
|---|---|---|---|---|
| **baseline** — v1 op sequence: per-head upload + letterbox, heads sequential, CUDA EP | **22.40** | 44.6 | 3.82 / 5.14 / 8.04 | — |
| **shared** — one uint8 upload, one letterbox per input size (GM and vehicle share 1088) | 21.41 | 46.7 | 3.88 / 5.21 / 8.11 | **byte-identical** 600/600 per head |
| **parallel** — shared + the three sessions run in threads | **16.75** | 59.7 | overlapped | **byte-identical** 600/600 per head |
| **tensorrt** — shared, sequential, fp16 TensorRT engines | 10.58 | 94.5 | 1.21 / 1.78 / 3.08 | tolerant only (table below) |
| **tensorrt_parallel** | **8.02** | 124.7 | overlapped | identical to `tensorrt` 600/600 |

Fixed per-frame costs (all configurations): upload 0.7–0.9 ms (uint8, 6 MB), letterbox 0.25–0.3 ms per input size,
postprocess ≈ 1.0 ms per head (max over classes, class-agnostic torchvision NMS, one device→host copy). In the parallel
configurations the per-head postprocess inflates to 1.5–3.4 ms (GIL / thread contention) — the next cut is a single
batched postprocess for all heads, or NMS inside the ONNX graph.

The vehicle head is the same architecture and resolution as the GM head but costs 2.1× more (8.0 vs 3.8 ms on CUDA EP,
3.1 vs 1.2 ms on TensorRT) — a single-class yolov8m exported differently (opset / fp16 casts) — worth a re-export check
before anything else; it is 46 % of the sequential budget.

TensorRT vs CUDA EP rows (tolerant metric, same class, IoU ≥ 0.5, ±2 px, ±0.02 conf):

| head | pairs | pair recall | pairs within tolerance | frames fully within tolerance | coord Δ p99 / max px | conf Δ max |
|---|---|---|---|---|---|---|
| GM (25 classes) | 7 117 | 99.9 % | 7 046 (99.0 %) | 526 / 600 = 87.7 % | 2.0 / 171 | 0.014 |
| chocks | 1 576 | 100 % | 1 564 (99.2 %) | 587 / 600 = 97.8 % | 2.0 / 3 | 0.006 |
| vehicle | 800 | 100 % | 792 (99.0 %) | 592 / 600 = 98.7 % | 2.5 / 37.5 | 0.028 |

This is the same order of difference as production-T4 vs this GPU on the CUDA EP (`gm_prod_delta.md`: pair recall 99.8 %,
frames within tolerance 97.1 % on the GM head); the lower GM frame-level figure comes from confidence deltas up to 0.014
flipping borderline small objects, plus a handful of large-object pairs where a different candidate wins NMS (the 171 px
maximum). Per ADR-001 §6 the TensorRT path is therefore a **versioned change**: adopted only after the L2 module gate
(`scripts/run_module.py`) on the 7 ATL-C5 videos shows 0 verdict changes, and re-validated on the production GPU because
TensorRT engines are hardware-specific (built at deploy time, cached).

## 3. What this means for the budgets

- Post-processing branch (batch): the three heads on one 5070 Ti go from the v1 sequence 22.4 ms to 16.8 ms with zero
  output change (parallel heads), and to 8.0 ms with TensorRT (tolerant parity). Decode (≈ 3 ms) and the tracker
  (`tracker_current.md`, profiling in progress) come on top.
- RT branch (125 ms/frame per camera at 8 fps): GM alone is 13–17 % of the budget on CUDA EP and 6–9 % on TensorRT on this
  GPU; a T4-class production GPU is roughly 3–4× slower (to be measured on the production runtime — `measurement_plan.md`
  §2 rule: numbers only count on the pinned hardware).
- **Full turnaround, measured 14.09** (`DjwtQRdZyt0sSk`, 37 530 frames, `scripts/gm_v2_run.py --parallel-heads`, fixed
  options, near-idle machine): **28.3 ms/frame end-to-end = 4.42× real time at 8 fps**, including OpenCV decode 2.5 ms,
  the three heads ≈ 16.4 ms (upload 0.7 + letterbox 0.4 + parallel run 15.4), and ≈ 9.4 ms of CPU work (GM rows, the
  incremental video context, the v1-compat second-run writer, the preprocessor's noise estimate every 48 frames). The
  regenerated second-run file against production on all rows: pair recall 99.90 %, 99.1 % of pairs within ±2 px /
  ±0.02 conf, 85.5 % of frames fully within tolerance — the same figures as the earlier replay (`gm_prod_delta.md`), so
  the fixed session options changed speed, not agreement. Report: `out/DjwtQRdZyt0sSk_full_v2/`. The void 1.58× figure
  is superseded.

## 4. Reproduce

```bash
python scripts/gm_ep_probe.py --video G:/gat_stages/atlc5_videos/DjwtQRdZyt0sSk.mp4 --weights external/general_model_prod/weights/GM_yolov8m_best_augmentation_march2024.onnx --frames 150
python scripts/gm_bench.py --video G:/gat_stages/atlc5_videos/DjwtQRdZyt0sSk.mp4 --weights-dir external/general_model_prod/weights --frames 600 --start 3600 --configs baseline,shared,parallel,tensorrt --out out/gm_bench_600.json
```

Requirements on Windows: `onnxruntime-gpu` only (the CPU `onnxruntime` wheel shadows it), pip `tensorrt` (the provider DLL
directory is registered by `pf.gm.onnx_detector.add_tensorrt_dll_dir`); the detector raises if TensorRT was requested but
the session silently fell back to CUDA.

## 5. Next

1. `GmStream`/`Detectors(parallel=True)` as the default (proven byte-identical); ~~re-run the full turnaround with decode~~
   done (28.3 ms/frame, 4.42× RT); the GM preprocessor's noise estimate can use the bit-identical `pf.tracker.fast_sigma`.
2. TensorRT adoption gate: full-video tolerant L1 + L2 on the 7 ATL-C5 videos; engine build/cache policy at deploy.
3. Vehicle head re-export check (2.1× the GM head cost at the same size); batched postprocess / NMS in graph.
4. Batching across cameras for the RT branch (one session, N frames) — after the tracker cost is known.
