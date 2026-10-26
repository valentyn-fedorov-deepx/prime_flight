# M23 · Employees wearing safety vests secured to body

> The module checks that every worker's safety vest is closed. It pairs each tracked worker with a detected vest,
> classifies the vest as zipped or unzipped whenever its front is visible, and confirms an open vest with a colour test.
> Before a Pass is given, a second classifier re-checks the small (distant) vests.

## At a glance

| | |
|---|---|
| Checks | M23 · Employees wearing safety vests secured to body |
| Stage | Pre-arrival, Arrival, Post-arrival, Download, Upload, Pre-departure, Departure |
| Looks at | The whole video, first frame to last; no aircraft or stage is needed |
| Cameras | Cone and wing cameras, aircraft and jets (client split); the db_worker task list names only the cone camera — to confirm |
| Uses | General Model (GM) boxes: safety_vest. Tracks: person. Video frames: yes, every frame |
| Own models | Vest orientation classifier (Swin-T: back / head / side); vest closure classifier (Swin-T: zipped / unzipped); vest presence gate (ResNet-18); small-vest classifier (ResNet-18, "v4"). Also runs the stock YOLOv8m-pose model for a shoulder check |
| Runs on | GPU |
| Real time | ready, needs video frames — classifies vest crops on every frame; the small-vest re-check runs once, at the end |
| Production version | tdv_cone @ 8f58d7e (2026-08-13) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | A worker is detected wearing a zipped vest for more than 50% of the video frames, without any interval where the vest is unzipped. |
| Fail | A worker is detected with an unzipped vest in at least one interval during the video. |
| Not observed | No workers wearing vests are detected, or all detections are unclear (low quality, worker too far away). |
| Not observed — view blocked | Frames with a worker wearing a vest are mostly blocked by obstacles (more than 80%). |

An "interval" is a stretch of time in which the vest is clearly visible.

## How it decides

1. **Pairing.** On every frame it takes the person tracks and the GM safety_vest boxes; a person is paired with a vest box lying at least **85%** inside the person box.
2. **Orientation.** The orientation classifier looks at the person (crop widened by **15%**). Only "head" and "side" views, where the vest front is visible, go on.
3. **Gates.** The frame is skipped when the vest box is taller than half the person box (sitting or partly hidden). The vest box is trimmed (top **15%**, bottom **5%**); if the presence gate gives p(vest) < **0.5**, the frame does not vote and the oldest vote is dropped.
4. **Two tests.** The closure classifier says zipped or unzipped; a colour test segments the vest with four masks (red, green, blue, pink) and looks for two separate vertical halves (open) or one large shape (closed).
5. **Votes.** **1** when both say closed, **0** when both say open, **0.5** when they disagree. The worker keeps the last **21** votes; a frame without a classified front view drops the oldest one.
6. **Worker mark.** With 21 votes, the worker is marked **unzipped** if the average is **0.75** or less, the vest crop is bright (mean HSV value ≥ **200**), the vest box is at least **70 × 40 px**, and the worker has been tracked for at least **100 frames** (12.5 s); otherwise zipped. Each new window overwrites the mark.
7. **Verdict.** Fail if any worker's final mark is unzipped; Pass if at least one person was tracked and none ends unzipped; Not observed if no person was tracked.
8. **Small-vest re-check (Pass only).** Every **12th frame** (1.5 s) person and vest crops were saved (vest ≥ **28 px** tall). At the end, YOLOv8m-pose keeps crops showing both shoulders from the front (confidence ≥ **0.3**); vests **28–70 px** tall and taller than wide (width / height < **0.88**) are scored, and each worker gets the mean of the 3 highest scores.
9. A worker with at least **6** scored crops, a mean ≥ **0.65**, and at least **12** crops above 0.65 spread over **3 s** or more turns the verdict into **Fail**. Vests of 70 px and more are not re-checked.

## Settings

| Setting | Value | What it does |
|---|---|---|
| vote window (`_max_len_inference`, code) | 20 (21 votes) | Votes needed before a worker is marked |
| unzipped threshold (code) | average ≤ 0.75 | How much doubt marks a vest as open |
| brightness / size gates (code) | HSV value ≥ 200; vest ≥ 70 × 40 px | Only bright, large vests can be marked open |
| minimum tracking time (code) | 100 frames (12.5 s) | Shorter-tracked workers cannot be marked open |
| person–vest pairing (code) | 0.85 | Share of the vest box inside the person box |
| presence gate (code) | p(vest) ≥ 0.5 | Frames where the vest looks absent do not vote; env `VEST_PRESENCE_BBOX_W=0` turns it off |
| `enabled` (v4_config.yaml) | true | Turns the small-vest re-check on or off |
| `stride`, `min_vest_h`, `band_split` | 12 frames (1.5 s), 28 px, 70 px | Sampling and vest heights of the re-check |
| `t_small`, `max_aspect`, `min_crops` | 0.65, 0.88, 6 | Score, shape and crop-count limits of a re-check Fail |
| `main_autofail` | false | Vests of 70 px and more are not re-checked (CLIP not loaded) |

`pose_config` and `pose_checkpoint` in `local_config.yaml` (HRNet-W32 files) are not used.

## What it reports

- Fail: "Worker N wears an unzipped vest. (HH:MM:SS)" per such worker, at the time of the worker's last "unzipped" mark. Pass: "No workers with unzipped vests were detected." Not observed: "No workers wearing vests were detected."
- Smart timeline: Pass — intervals with at least one worker marked zipped; Fail — intervals with a worker marked unzipped, or, for a re-check Fail, the first to last sampled frame of the flagged worker. Frames count from 0; an interval still open at the end is dropped.
- Overlay file (.ndjson): person boxes with the vest mark, counts of zipped / unzipped / undefined workers. An annotated video with `--write-video`.

## Known issues and limits

- No obstacle logic: the client's "view blocked" rule is not implemented.
- Pass does not check "zipped for more than 50% of the frames". Every tracked person counts, even one never classified, so people without a readable vest give Pass; Not observed only means no person was tracked ("No workers wearing vests" really means "no persons").
- The client fails a worker after one unzipped interval, but only the last mark counts: a vest marked open, then closed, ends closed. The README says the opposite and describes an older 10-vote window.
- The main path cannot fail a dark (night, shade) or small vest; the re-check covers 28–70 px vests, and only when the verdict is Pass.
- Known re-check false alarm: crew in white shirts, where a tie looks like an opening (`README_V4.md`).
- Open requirement (Confluence): the new uniform is solid, so the logic needs an update; not agreed yet.
- The most expensive module per recorded frame: it decodes every frame and runs up to three classifiers per worker; the re-check adds about 2–5 min per Pass video.

## For developers

- **Repository:** `dxgat/detectors/safety-vests-secured-to-body`; production line `tdv_cone` @ `8f58d7e`; default branch `master` @ `ae8ef16` (2026-08-06), which has neither the small-vest re-check nor the presence gate and pins ultralytics 8.2.81 instead of 8.4.83.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, cone_camera, write_video, json_logger)`; `cone_camera` is unused. `Person` (votes, mark), `get_report`; `classifier_utils.py` (Swin-T wrapper), `vests_utils.py` (colour masks), `v4_override.py` + `v4_config.yaml` (re-check, documented in Ukrainian in `README_V4.md`). `fail_guard.py` and `export_v4_probe.py` are not used at run time. Logic diagram (Confluence modules database, 2023-07-10): https://docs.google.com/spreadsheets/d/1xSkSkCQcFqnYoB3y0fRUnfGSffF0HHy9Wgy-TgxYqKI/edit?gid=0#gid=0
- **Dependencies:** exported copy; branch pins `cv_common` 29def48, `db_worker` 5a4aa83 (master: 4291b0d, 0248146); the export holds `cv_common` ac5098d as a stand-in. torch / torchvision, ultralytics 8.4.83, OpenCV, SciPy; Docker base `gpu_base`. Weights in DVC (6 files): `pose_classifier.pt`, `vest_classifier.pt`, `presence_bbox_r18.pt`, `v4_cnn2.pt`, `yolov8m-pose.pt`, `v4_probe_head.npz` (unused).
- **Run locally:** `python main.py --source <video>.mp4 --weights-dir weights [--device cpu] [--write-video] [--json-fn <name>]`; `python single_run.py <video_id> [<path>]` runs one video with per-person debug output; `enabled: false` in `v4_config.yaml` turns the re-check off.
- **Code references:** pairing `main.py:401-409`; orientation `:418-422`; closure classifier `:423-427`; gates `:68-96`; colour test `:152-221`; votes `:116-122`; mark `:129-149`; verdict `:246-268`; re-check sampling `v4_override.py:90-141`; re-check decision `v4_override.py:192-344`, `main.py:492-501`; smart timeline `main.py:449-459, 503-506`.
