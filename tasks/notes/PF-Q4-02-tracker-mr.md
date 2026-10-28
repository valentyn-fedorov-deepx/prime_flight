# MR · cv_trackers: the same tracks and debug video in about half the time

**Branch:** `pf/q4-02-tracker-exact-speedups` on the production commit bd43c3c (cv_common in the production image
**58b1b1f**; local proofs on `tracker_optimization` 2759daf), two commits; built by Maksym as image `a6d6c53` (+ a font
fix):

1. `7e1b867` — **Optional `TRACKER_SEED` for reproducible runs.** Nothing changes without the variable.
2. `f1add44` — **Same tracks and debug video in about half the time.**

We have no access to `dxgat/utils/cv_trackers` (https "not found"), so the branch goes to Maksym as patches:
`tasks/patches/cv_trackers/` (`git am` on bd43c3c). Only `tracker.py` and the new `local_utils/speedups.py` change; no new
packages (`pywt` and `scipy` are already needed by scikit-image's `estimate_sigma`).

## Cluster result, 2026-10-28

Maksym's image `a6d6c53` (the branch + a font fix, cv_common **58b1b1f**, the production one), five videos of the GM test,
against the production files of 21.10 (`trackersbd43c3c.ndjson`). Compared unpacked with `scripts/tracker_ndjson_diff.py`
(`out/tracker_cluster/<video>_diff.json`). Neither run was seeded: production has no seed option, so the two files
were not expected to be equal.

| video | frames | identical frames (first difference) | arrival | departure | belt loader at the front door / leaving |
|---|---|---|---|---|---|
| fAkpu3dj2NIj | 25 470 | 6 597 (4 157) | 4 175 → 4 170 | — | — |
| ytQDROiCyhBh | 32 370 | 4 390 (3 127) | 3 380 → 3 371 | 30 993, same | at 19 158, same; leaves 29 880 → 29 863; one extra leave and return 21 932 → 21 984 |
| b8ijKDWsLlQi8W | 40 020 | 8 521 (1 105) | 5 105, same | 36 057 → 36 064 | at 5 896 → 5 862; leaves 33 442, same |
| n96M7fASlhGn | 47 790 | 3 985 (1 846) | 3 991, same | 44 406 → 44 401 | 3 200 → 3 202; leaves 12 347 → 12 338 and 42 713 → 42 692; the rest same |
| 7PytHarRNqmT | 52 800 | 6 202 (1 231) | 6 052, same | 52 111 → 52 110 | all the same |

- **The same on every frame of all five videos:** the tracks (the same ids for every class), every box (0 px), the
  number of frames, the re-identifications.
- **What differs** is what cv_common draws at random without a seed — the optical-flow points (`_p0`, 250 of an object's
  key points, `tracked_object.py:132`) and the segmenter's prompt points (`_segm_points`, 10 random points in the box,
  `transport.py:79`) — and what follows from the motion of those points: the stop/move counters and statuses (31–134
  frames per video), hence the event frames above (arrival and departure within 9 frames, 1.1 s; a belt loader at a door
  within 34 frames, 4.3 s), and `arrival_frame` / `departure_frame` on every later frame.
- This is the pattern of two production runs with different random numbers. **Local baseline** (fAkpu3dj2NIj frames
  0–8 000, no video, `out/tracker_cluster/fAkpu_8k_*.json`): production seed 0 against production seed 1 — identical
  4 156 frames, first difference at frame **4 157** (the airplane's first `_segm_points`), the same keys, the same
  tracks and boxes, T_ARR 4 157 / 4 159; the cluster pair on the same 8 000 frames — identical 4 156, first difference
  at **4 157**, T_ARR 4 175 / 4 170; production seed 0 against the branch seed 0 — **identical on all 8 000 frames**.
  (Local production against the cluster's production file parts at frame 1 904, where one GSE gets 71 key points
  instead of 72 — a different GPU, not randomness: exact comparisons need the same node type.) The exact test needs both
  sides seeded: image **A** = bd43c3c + 7e1b867 only (the same cv_common 58b1b1f and font fix) and image
  **B** = a6d6c53, both with `TRACKER_SEED=0`, on one or two videos (fAkpu3dj2NIj takes 30 min). Expected: every frame
  identical.

**Time.** Production runs the tracker **without the debug video**: `write_video=False` in the job arguments of every
production tracker job checked (6 of 6, 27–28.10, `prod_receiver`) and of both test runs. The drawing savings (masks,
encoder) therefore do not apply in production. Tracking time (log "start tracker" → "tracker processed"), production →
a6d6c53, five jobs started together both times:

| video | minutes | ms per frame |
|---|---|---|
| fAkpu3dj2NIj | 30.0 → 26.3 (−12.3 %) | 70.7 → 62.0 |
| ytQDROiCyhBh | 59.8 → 48.5 (−19.0 %) | 110.9 → 89.9 |
| b8ijKDWsLlQi8W | 100.7 → 91.6 (−9.1 %) | 150.9 → 137.3 |
| n96M7fASlhGn | 119.0 → 107.6 (−9.6 %) | 149.4 → 135.0 |
| 7PytHarRNqmT | 89.8 → 72.2 (−19.7 %) | 102.1 → 82.0 |
| **total** | **399.4 → 346.1 (−13.3 %)** | |

In production terms: the median tracker job about 1.3 → 1.13 h; the trackers are 19 % of a video's pod time, so about
−2.5 % of the processing bill (not −9 %: that estimate assumed the debug video is drawn).

**Local check without the video** (this machine, fAkpu3dj2NIj frames 0–8 000, both seeded 0, `tracker_exact_ab.py
--no-video`, `out/tracker_ab/fAkpu_nv8k.json`): tracks identical; 31.5 → 21.1 ms per frame (−33 %): noise estimate
6.0 → 1.5, per-object updates 11.6 → 9.9, DeepSORT off the main loop. The saving per frame is about the same on the
cluster (fAkpu3dj2NIj: −8.7 ms per frame there, −10.4 here); the cluster's frame costs more (70.7 ms), so the share is
smaller.

## What changes, and why the output cannot

| # | what the tracker does today | change | why the result is the same |
|---|---|---|---|
| 1 | debug video: every object's mask is drawn by allocating a full 1920×1080 colour frame and running three bitwise operations over the whole frame (cv_common `draw_obj_mask`); 38 % of the tracker's time | the same three operations on the bounding box of the mask (`draw_obj_mask_roi`) | outside that box the full-frame version leaves every pixel as it was |
| 2 | debug video encoded in the main loop | encoded in a background thread (`AsyncVideoWriter`) | the same frames in the same order; a frame is not touched after it is queued |
| 3 | three DeepSORT instances (belt loaders, workers, GSE) updated one after another | updated in three threads | they share no state; each has its own re-id model and grad mode |
| 4 | noise estimate on the full frame every 2 s: scikit-image computes four wavelet bands per channel and keeps one | only that band, one thread per channel (`estimate_sigma_rgb`) | the same PyWavelets routine in the same axis order; bit-identical, checked on real frames |
| 5 | two full-frame copies per frame (`img_to_track`, `prev_img_to_track`) and one into CuPy | no copies | the frames are only read; the reader returns a new array every frame |
| 6 | a frame header and a dump of the belt-loader state formatted on every frame, de-noising lines on every de-noised frame | behind `TRACKER_VERBOSE=1` | log only |
| 7 | the ignore-class id lists rebuilt for every detection; `confirmed_workers_ids` a growing list | built once; a set | only membership is checked |

The debug video stays (it is watched); only the way it is drawn changes.

## How it was proved

`scripts/tracker_exact_ab.py` (prime_flight repository) runs `tracker.detect()` of each checkout unmodified through
`scripts/tracker_v1_profile.py` (seeded `np.random`, a fixed palette for the optical-flow points, the production
`--write_video t` path), on the same GM rows, and compares the tracker ndjson, the debug video file and every decoded frame.

| run | tracks | debug video | ms per frame, production → branch |
|---|---|---|---|
| **full event zHxIAF2vUGxJ** (36 min, 17 280 frames) | identical (sha256 853e6c89…) | identical (685c1754…, 17 280 of 17 280 frames) | **70.7 → 33.2 (−53 %)**: 20.4 → 9.6 min |
| busy slice DjwtQRdZyt0sSk, frames 9 000–10 200, two rounds alternating | identical in all four runs (2ce18845…) | identical in all four runs (55c0306e…, 1 200 of 1 200 frames) | **83.0 → 42.5 (−49 %)**; rounds 83.0 / 83.0 and 42.7 / 42.4 |

A quiet machine (RTX 5070 Ti, 8 cores; nothing else computing), `out/tracker_ab/full_zHxI.json`, `busy_clean.json`.

Where the time went on the full event (ms per frame, production → branch): mask drawing 24.9 → 1.1, noise estimate
5.9 → 1.8, the encoder and the three DeepSORT updates moved off the main loop (their time now overlaps it), the rest the
same (optical flow, segmentation, per-object updates). About three quarters of the saving is less work, not more threads (masks and
noise estimate), so it carries over to the 3.3-vCPU pod; the threaded part needs the pod's spare cores.

**In production terms (estimate, to confirm on the cluster):** the tracker job about 1.3 → 0.65 h for the median
87-minute video; the computing part of time to result about 4.2 → 3.5 h; the trackers are 19 % of the pod time of a
video, so about −9 % of the processing bill.

## Versions to build with

| | Commit | Note |
|---|---|---|
| cv_trackers base | **bd43c3c** (branch `optimization`, 2026-02-28) | the production commit |
| patch 1 | 7e1b867 `Optional TRACKER_SEED for reproducible runs` | image A = bd43c3c + this |
| patch 2 | f1add44 `Same tracks and debug video in about half the time` | image B = both patches |
| cv_common | submodule pin **ac5098d2** (unchanged by the patches) | bd43c3c cannot run on ac5098d (its `update_params` calls need the `tracker_optimization` line); the production image carries **58b1b1f** (Maksym, 2026-10-28; not readable for us). The local proof ran on 2759daf, the line's tip of 2026-05-15 |
| db_worker | submodule pin **5a4aa83** (unchanged) | the local proof ran on 5a4aa83 |

Build A and B exactly the way the production tracker image is built (same Dockerfile and CI, same cv_common and
db_worker) — only `tracker.py` and the new `local_utils/speedups.py` differ. Record `git -C cv_common rev-parse HEAD` and
`git -C db_worker rev-parse HEAD` in both images. The patches use two cv_common internals — the tracked object's mask
(`_TrackedObject__segmenter.mask`) and `FeatureTracker._OF_color` — present in ac5098d and in 2759daf alike.

## For the test on the cluster (Maksym)

1. **Production itself is not reproducible:** cv_common samples optical-flow key points with the unseeded `np.random`
   (`tracked_object.py:132`, objects with more than 250 key points) and draws the colours of the points at import
   (`:103`), so two runs of today's image give different tracks and a different video. Build two images: **A** = bd43c3c +
   commit 1 (production + the seed option), **B** = the branch head. Run both with `TRACKER_SEED=0` on the same five
   videos as the GM test.
2. **Expected identical:** the tracker ndjson (after gunzip; the file name carries the commit) and the debug video.
3. Time: the tracker job should take about half (full event here: −53 %); the pod has 3.3 vCPU, enough for the
   parallel parts (three DeepSORT threads, the encoder thread).
4. `TRACKER_VERBOSE=1` brings the per-frame log lines back.

## Not in this MR

- Grey frame once per frame instead of two `cvtColor` per object, and the vectorised in-box test: exact (proved in the
  v2 stream port), but they live in cv_common (`tracked_object.py:421-422`, `:262`); a cv_common MR.
- Drawing the masks on the box in cv_common's own `draw_obj_mask` (here the tracker calls its own copy, reading the private
  mask attribute).
- Seeding by default: it would make every run reproducible, but changes which key points production samples.
