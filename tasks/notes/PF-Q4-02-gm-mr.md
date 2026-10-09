# MR · general_model: skip work whose results are never used (outputs unchanged)

**Branch pushed:** `pf/q4-02-gm-exact-speedups` on `dxgat/detectors/general_model` (2026-10-09), on top of the production
branch `deployment_v_py3_10` @ d4ae8e5 (cv_common ac5098d, db_worker 5a4aa83 — the same pins the proof below ran with).
Create the MR: https://gitlab.com/dxgat/detectors/general_model/-/merge_requests/new?merge_request%5Bsource_branch%5D=pf%2Fq4-02-gm-exact-speedups

Two commits:

1. **fe243c1 — Skip work whose results are never used; outputs unchanged**
2. **3bd356e — Make the camera-motion pass of video selection opt-in** (separate, because it switches a computation off)

Dockerfile and requirements are untouched. The two commits change `main.py`, `scripts/new_model.py`,
`scripts/videos_selection_script.py` and `local_config.yaml` (+80 / −41 lines).

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
| 9 | every frame | about eleven `print` lines per frame to the job log (212 145 lines per 36-minute video) | log storage | behind `GM_VERBOSE=1`; per-video summaries kept (55 lines) |
| 10 | after the second run (commit 2) | `select_video`: a third decode of the whole video with frame differences, when the stage / detection filters pass | nobody — the result goes only to `report_video_selection_module.txt` in the pod's working directory: not returned by `detect()`, not uploaded, not sent | opt-in: `video_selection.check_camera_motion: true` restores it |

## How it was proved

`scripts/gm_prod_profile.py` (prime_flight repository) runs `detect()` of a checkout unmodified, the way
`model_starter.py` does (VideoWorker in testing mode, `torch.no_grad`, annotated video on), with `np.random` seeded before
the first run and re-seeded before the second, and compares the two checkouts file by file: the first-run ndjson, the
second-run ndjson, the returned report (`camera_type`, `confidence_camera`, `frame_stopped`, statistics, stages, entity,
aircraft type, noise fields), the annotated video frame by frame, the video-selection report.

- 6-minute slice (approach, arrival, stand) and the full 36-minute event zHxIAF2vUGxJ, three times (2026-10-08 and an
  interleaved production / branch / production / branch rerun on 2026-10-09): **every output byte-identical**, with the
  same hashes in every run.
- Speed of the GM job on the full event: **17–19 % faster** (first run about −30 %, second about −5 %); the job log goes
  from 212 145 lines per video to 55. Details: `tasks/notes/PF-Q4-02.md`.
- The camera-motion pass did not run on that event (its filters failed), so commit 2's saving is not in these numbers.

## For the test on the cluster (Maksym)

1. Build the image from the branch as usual (Dockerfile unchanged) and run the GM job on a few videos with the current
   image and with the new one.
2. **Expected identical:** `general_model<video>.ndjson` and `general_model<video>-second_run.ndjson` (the files the
   tracker and the modules read), the annotated video, `detection_statistics` and `stages`.
3. **May differ, and already differs between two runs of production itself:** `frame_stopped`, `confidence_camera` and
   anything else that comes from the second run's main-aircraft motion analysis. Production is unseeded and cv_common
   samples key points with `np.random`; removing the first-run motion analysis changes which random numbers the second run
   draws, nothing else. To compare those fields exactly, seed both runs the same way (`np.random.seed(0)` before
   `detect()`, `np.random.seed(1)` right before the second run — what the harness does), or run production twice to see
   its own spread.
4. Time: the GM job should take about 0.8 of today's on the same node.
5. `GM_VERBOSE=1` brings the per-frame log lines back for debugging; `video_selection.check_camera_motion: true` brings the
   camera-motion pass back.

## Not in this MR (they change numbers; they need the verdict gate)

- `cudnn_conv_algo_search=DEFAULT` in `main.py:41`: on a GPU where cuDNN's heuristic finds no kernel (seen on an RTX
  5070 Ti with cuDNN 9.19) every convolution runs in fallback mode, 2.6× slower. Worth checking with the new gpu_base
  image and before any GPU change (Azure migration).
- TensorRT engines for the three heads (`docs/decisions/ADR-003`).
- Batching the camera classifier across frames.
- Re-using the first run's noise estimates in the second run and skipping the unused letterbox in the reader (exact, about
  2 % and 3.5 %; the second one lives in cv_common).
