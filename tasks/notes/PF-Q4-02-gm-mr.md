# MR draft · general_model: skip work whose results are never used (outputs unchanged)

Branch `pf/q4-02-gm-exact-speedups` in the local clone (`external/general_model_opt`, from production a0157a4,
`deployment_v_py3_10`). Push and MR by a human. Two commits:

1. **58cc275 — Skip work whose results are never used; outputs unchanged**
2. **793494b — Make the camera-motion pass of video selection opt-in** (separate, because it removes a computation)

## What the production GM does that nobody uses

| # | where | what runs today | who reads the result | change |
|---|---|---|---|---|
| 1 | first run, every frame, every tracked aircraft | `Plane.update_params`: optical flow on ≤ 250 points, MobileSAM key-point masks every ~8 frames, movement / arrival counters | nobody — after the first run only the box (`.xyxy`) of these objects is read, to re-associate a new track id; the second run builds the main aircraft from scratch | `update_box()`: the same box check and assignment, no motion analysis; no `prev_im0s` copy in the first run |
| 2 | first run, every frame, every track | `FeaturedTracker.update(..., image=im0s)` computes FAST / ORB features per track | nobody — `update_objects_in_place` is called without the image, so the feature check never runs | call `update()` without the image |
| 3 | second run, every frame | `torch.from_numpy(im0s).float().cuda()` — a float32 copy of the frame on the GPU | nobody — the second run reads the first run's detections | removed |
| 4 | between the runs | `UModel(...)` loads the YOLOv5 airline detector | nobody — its calls are commented out (replaced by `EntityClassifier`) | not loaded |
| 5 | between the runs | `timm.create_model(..., pretrained=True)` downloads ImageNet weights | nobody — `load_state_dict` (strict) replaces every weight | `pretrained=False` |
| 6 | first run, every frame | full frame converted to float32 on the CPU, 24 MB uploaded, then `.half()` | — | upload the uint8 frame (6 MB), `.half()` on the GPU: the same fp16 values |
| 7 | every head, every frame | `image.clone()` of the full frame before a channel gather that copies anyway; GM and vehicle (both 1088) preprocess the same frame twice | — | no clone; one preprocessed tensor per input size per frame |
| 8 | every head, every frame | a Python loop over detections with a GPU→CPU synchronisation per value | — | one gather, one host copy (identical float32 rows) |
| 9 | every frame | about ten `print` lines per frame to the job log | log storage | behind `GM_VERBOSE=1`; per-video summaries kept |
| 10 | after the second run (commit 2) | `select_video`: a third decode of the whole video with frame differences, when the stage / detection filters pass | nobody — the result goes only to `report_video_selection_module.txt` in the pod's working directory: not returned by `detect()`, not uploaded, not sent | opt-in: `video_selection.check_camera_motion: true` |

Item 1's only effect on the outputs was through `np.random`: the motion analysis samples key points and prompt points from
the global random stream, which the second run's motion analysis then continues. Production is unseeded, so that stream is
already different on every run of the same video; removing the first-run draws changes nothing beyond the seed.

## How it was proved

`scripts/gm_prod_profile.py` (prime_flight repository) runs `detect()` of a checkout unmodified, as `model_starter.py` does,
with `np.random` seeded before the first run and re-seeded before the second, and compares two runs file by file:
first-run ndjson, second-run ndjson, the returned report (`camera_type`, `confidence_camera`, `frame_stopped`, statistics,
stages, entity, aircraft type, noise fields), the annotated video frame by frame, the video-selection report.
Results: see `tasks/notes/PF-Q4-02.md` (slice and full event).

## Not in this MR (they change numbers; they need the verdict gate)

- `cudnn_conv_algo_search=DEFAULT` in `main.py:41`: on a GPU where cuDNN's heuristic finds no kernel (seen on an RTX
  5070 Ti with cuDNN 9.19) every convolution runs in fallback mode, 2.6× slower. Worth checking before any GPU change
  (Azure migration).
- TensorRT engines for the three heads (`docs/decisions/ADR-003`).
- Batching the camera classifier across frames.
