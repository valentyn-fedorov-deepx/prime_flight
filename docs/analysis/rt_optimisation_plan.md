# Making the shared part fit: what to optimise in GM v2 and the tracker, and what each change buys

The modules are not the problem. Seventeen of the twenty that run live cost under 3.3 ms of their own work per frame; the
frame path a stream has to keep under 125 ms is **GM + tracker + hand-off**, and that is where every millisecond has to come
from. This is the plan for that part, written against measurements, not against intuition. It is the content of PF-Q4-02
pulled forward, because the pod envelope (`rt_environment.md`) makes it a blocker rather than a Q4 improvement.

Every number below was measured on this machine (RTX 5070 Ti, card kept busy) with `scripts/rt_resource_fit.py` and the
campaign runs; "on a T4" means the same run with the detector heads made 3× slower (the published rates give 65 against
about 176 FP16 tensor TFLOPS and 320 against 896 GB/s), which is an emulation until `scripts/node_bench.py` is run in a pod.

## Where the time goes

| part | this card, CUDA EP | this card, TensorRT heads | what it is |
|---|---|---|---|
| GM, three heads | **19.2 ms** | **11.1 ms** | upload, one letterbox per input size, three YOLO heads in threads, NMS |
| tracker, four classes | **26.2 ms** | 29.5 ms | see the breakdown below |
| causal second-run rows | 0.1 ms | 0.1 ms | |
| hand-off to the module processes | 5–7 ms | 5–7 ms | rows and pixels to every module, waiting for a slow reader |
| decode | 2.9 ms | 2.9 ms | CPU decode of the chunk |
| **frame path, ten pixel-free modules** | **52–56 ms** | **43.6 ms** | of the 125 ms budget |

The tracker's own breakdown on the same run (`tracker_ms_per_frame`, four classes):

| step | ms | what it is |
|---|---|---|
| belt loader path | **9.6** | the `bl_gse` segmentor (torch YOLO) per belt loader per frame, plus optical flow and the BL state machine |
| DeepSORT | **8.3** | three separate re-id updates per frame: belt loaders, workers, GSE |
| aircraft path | 4.0 | the plane segmentor, optical flow, the stage counters |
| noise estimate | 2.3 | `estimate_sigma` on the frame every 2 s |
| GSE path | 2.4 | the same segmentor again for the GSE boxes |

**With TensorRT the balance flips**: the tracker becomes 2.7 times the GM. Everything after step 1 below is about the tracker.

## What has to fit, measured

Ten pixel-free modules, the whole shared part, 240 s of the busy stretch, 8 cores:

| | heads through CUDA EP | heads through TensorRT |
|---|---|---|
| this card | 52.8 ms ✓ | **43.6 ms** ✓ |
| a T4-class card (heads 3× slower) | 89.3 ms ✓ | **60.2 ms** ✓ |
| a T4-class card, and the tracker 3× slower too (the pessimistic end) | **144 ms ✗ does not keep up** | **114.9 ms ✓** (p95 148) |

That is the headline: **TensorRT alone is the difference between a T4 pod that fails and one that works**, even if the T4 turns
out to be as hard on the tracker's own networks as on the heads. It is already implemented (`--provider tensorrt`), and what
it still needs is not code but a gate (below).

## The levers, in the order they are worth doing

| # | change | what it buys | risk | how it is proved | effort |
|---|---|---|---|---|---|
| 1 | **TensorRT fp16 for the three heads** | GM 19.2 → 11.1 ms here; the T4 case 89 → 60 ms, and 144 → 115 ms at the pessimistic end | NEAR: different kernels, so rows differ in the last digits | tolerant GM parity is already green; what is missing is the module gate — the test set with TensorRT rows against the same runs with CUDA rows (the `sub` machinery, one night) | implemented |
| 2 | **Heads and tracked classes per stream** | GM 19.2 → 8.5 (gm only) / 11.5 (+chocks) / 14.3 (+vehicle); tracker 26.2 → 4.9 (airplane) / 7.7 (+person) / 20.7 (+belt loader) | EXACT for the GM rows that are kept; NEAR for the tracker, whose association sees fewer objects (one single-module run moved T_dep by 42 frames) | the tracker side needs the anchors and the module verdicts compared per set, the harness exists | implemented |
| 3 | **The segmentors through ONNX/TensorRT** (`yolo11s-seg_plane`, `yolo26s_seg_bl_gse`) | the belt loader path is 9.6 ms and the aircraft path 4.0 ms, both dominated by a torch YOLO call per object per frame; the same conversion bought 42 % on the GM heads | NEAR | seeded byte-level tracker parity (`scripts/tracker_v2_run.py --seed` against the v1 profile) and then the module verdicts | days |
| 4 | **One DeepSORT forward instead of three** | the three re-id updates (belt loaders, workers, GSE) each run their own forward on their crops: 8.3 ms together; batching the crops is one forward | NEAR (batch composition changes nothing in the algorithm, but the order of the np.random draws can) | the same seeded parity | days |
| 5 | **Skip the re-id embedding when the association is unambiguous** | at 8 fps most frames have one obvious match per object; the embedding is only needed when IoU is ambiguous | NEAR | seeded parity will differ by design: fall back to the module verdicts on the test set | days |
| 6 | **The noise estimate** | 2.3 ms: raise the interval from 2 s, or switch on the half-resolution gate that already exists (`fast_noise_gate`) | NEAR: it decides when the preprocessing goes into HEAVY mode | the noise decision per video against the batch runs (90 videos, no GPU) | hours |
| 7 | **Heads at different rates** (chocks and vehicle every Nth frame, the rows reused in between) | from the head table: at stride 4 the GM is about `gm + (rest)/4` — 11.2 ms through CUDA EP, about 6 ms with TensorRT | SEMANTIC: a chock that appears is seen up to 0.5 s later | module verdicts on the test set; the chock checks decide on minutes, not frames, so the risk is small and measurable | ~25 lines + a night of runs |
| 8 | **INT8 for the heads on the T4** | the card does 130 TOPS INT8 against 65 FP16: up to 2× on the heads, i.e. the T4 case back to this card's numbers | SEMANTIC: quantisation changes detections | calibration set + recall per class against the current model, then the module gate | a project |
| 9 | **NVDEC instead of CPU decode** | 2.9 ms and a core per stream | EXACT (X4 says the decoder is pinned on both sides of a comparison, so the parity runs have to move with it) | frame-level comparison of the decoded frames | days |
| 10 | **One model instance per card for several streams** | does not shorten a frame, but removes the per-stream copy of the weights (3 GB) and lets a card carry more streams | — | the streams-per-card measurement that is still open | a project |

## What not to spend time on

- **The modules.** Seventeen of the twenty are under 3.3 ms; the three that are not (safety vests 18.8, handrails on GSE
  12.5, wing walkers 5.1) are pixel modules with their own networks and are a separate story (PF-Q2-11, PF-Q2-12).
- **The hand-off** (5–7 ms) until the tracker is dealt with: it is already smaller than one segmentor call.
- **Making GM faster than the tracker.** After step 1 the GM is 11 ms of a 44 ms frame path; the tracker is 30.

## The arithmetic to aim at

With TensorRT heads and per-stream scoping, a T4-class pod gets:

| set | heads | tracked | frame path on a T4 (estimated from the measured parts) |
|---|---|---|---|
| pushback trio | gm+chocks+vehicle | airplane+beltloader | ~24 + ~62 + 7 = **93 ms** |
| arrival set (six checks) | gm+chocks+vehicle | airplane+person | ~24 + ~23 + 7 = **54 ms** |
| ten pixel-free modules | all three | all four | **60 ms measured**, 115 ms at the pessimistic end |

Steps 3–6 are what turn the pessimistic end from "just fits" into "fits with room", which is what a production node needs if
two streams are ever to share a card.

## How every change gets proved

The harness is already there, and nothing goes in without it:

1. **GM rows**: `pf.eval.parity.compare_gm_ndjson_tolerant` against the batch second-run file (tolerant: boxes within a
   tolerance, same classes).
2. **Tracker**: seeded byte-level comparison against the production pin, plus the anchors (T_arr, T_dep) per video.
3. **Module verdicts**: the test set with the changed inputs against the same modules on the current inputs — the `sub`
   machinery, 740 task verdicts, one night (`scripts/testset/orchestrate.py`, `scripts/testset/compare.py`).
4. **End to end**: the ready modules live on the events on disk (`scripts/rt_joint_run.py`) and the accuracy against the
   labels (`scripts/rt_live_accuracy.py`).

A change that cannot keep the verdicts is not an optimisation, it is a different product.

## The first three things to do

1. **Close the TensorRT gate** (step 1): run the test set with TensorRT rows and compare the verdicts. If they hold, the
   branch switches its default and the T4 pod stops being a blocker. One night of runs on this machine.
2. **Run `scripts/node_bench.py` in a gpu-pool pod** (two minutes): it replaces the 3× emulation with the real factor for
   the heads and for a core, and tells us whether the pessimistic column above is the real one.
3. **Convert the two segmentors** (step 3): the tracker's biggest single cost, and the same trick that already worked on the
   heads.
