# Safety vests worn and fastened

> Every worker on the stand must wear a safety vest that is closed. The module pairs each worker with a vest found by
> the General Model (the shared detector), judges the vest open or closed whenever its front is visible, and before a
> Pass re-checks the small, distant vests with a second model.

## Status

| | |
|---|---|
| How accurate it is | 51 of 69 turnarounds correct (74 %) on the monthly test |
| Fail turnarounds it caught | 24 of 35 |
| In production | the version of August 2026 |
| Who looks after it | to assign |
| Biggest open problem | Only a worker's last vest mark counts, so a vest seen open and later closed ends as Pass. |

## What the client wants

*Employees wearing safety vests secured to body*

| Verdict | When |
|---|---|
| Pass | A worker is seen wearing a closed vest in more than half of the video's frames, with no stretch where the vest is open. |
| Fail | A worker is seen with an open vest in at least one stretch of the video. |
| Not observed | No workers wearing vests are seen, or every sighting is unclear (poor picture, worker too far away). |
| Not observed, view blocked | The frames with a worker in a vest are mostly blocked (more than 80 %). |

A verdict is the answer of a check: Pass, Fail or Not observed. A frame is one picture of the video (the cameras take 8
per second). A "stretch" (the client says interval) is a time in which the vest is clearly visible.

## When and where it looks

The whole video, from the first frame to the last, in every stage (part) of the turnaround; it needs neither the
aircraft nor the stages. In the client's split it runs on both cameras, the cone camera (towards the aircraft nose) and
the wing camera (along the wing), for aircraft and jets. The list of checks that production runs per camera names only
the cone camera: to confirm.

## What it looks at

- **From the General Model** (a detection is a box it draws around an object): safety vests.
- **From the tracker** (the part that follows objects from frame to frame): the person tracks (a track is the same
  person followed from frame to frame).
- **From the video itself:** every frame, for the pictures of workers and vests.
- **Own models** (on a graphics card): a view model (back, front or side); a closure model (zipped or unzipped); a
  presence model (is there a vest at all); a small-vest model for the re-check; and a ready-made pose model (it finds a
  person's joints), used only for the shoulders.

## How it decides, step by step

1. **Pairing.** On every frame, a person is paired with a vest box lying at least 85 % inside the person's box.
2. **View.** The view model looks at the person (picture widened by 15 %). Only the views showing the vest's front
   ("head" and "side") go on.
3. **Gates.** The frame is skipped when the vest box is taller than half the person box (sitting or partly hidden). The
   vest box is trimmed (top 15 %, bottom 5 %); if the presence model gives a vest probability under 0.5, the frame does
   not vote and the worker's oldest vote is dropped.
4. **Two tests.** The closure model says zipped or unzipped. A colour test outlines the vest in red, green, blue or pink
   and looks for two separate upright halves (open) or one large shape (closed); on a vest box under 40 × 25 pixels or
   without a clear shape it gives no answer.
5. **Votes.** 1 when both say closed, 0 when both say open, 0.5 when they disagree (a "zipped" with no colour answer
   counts 1, an "unzipped" 0.5). The worker keeps the last 21 votes; a frame without a front view drops the oldest one.
6. **Worker mark.** With 21 votes, the worker is marked open if the average is 0.75 or less, the vest picture is bright
   (average brightness at least 200 on a 0–255 scale), the vest box is at least 70 pixels tall and 40 wide, and the
   worker has been followed for at least 12.5 seconds; otherwise closed. Each new vote overwrites the mark.
7. **Verdict.** **Fail** if any worker's last mark is open; **Pass** if at least one person was tracked and none ends
   open; **Not observed** if no person was tracked.
8. **Small-vest re-check (only before a Pass).** Every 1.5 seconds, pictures of each worker and vest are saved (vest at
   least 28 pixels tall). At the end, the pose model keeps those showing both shoulders from the front (confidence at
   least 0.3). Vests 28 to 70 pixels tall and taller than wide (width under 0.88 of the height) are scored by the
   small-vest model; each worker gets the average of their 3 highest scores.
9. A worker with at least 6 scored pictures, that average at 0.65 or more, and at least 12 pictures above 0.65 spread
   over 3 seconds or more turns the verdict into **Fail**. Vests of 70 pixels and taller are not re-checked.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Votes per worker | 21 | Votes needed before a worker is marked |
| Open threshold | average 0.75 or less | How much doubt marks a vest open |
| Brightness and size gates | brightness 200 of 255; vest 70 × 40 pixels (tall × wide) | Only bright, large vests can be marked open |
| Time followed | 12.5 seconds | Shorter-followed workers cannot be marked open |
| Pairing | 85 % of the vest box inside the person box | Which vest belongs to whom |
| Presence gate | vest probability 0.5 (can be switched off at start-up) | Vest looks absent: no vote |
| Re-check | on | Turns the small-vest re-check on or off |
| Re-check sampling | every 1.5 seconds; vests from 28 pixels; small band up to 70 pixels | Which pictures are scored |
| Re-check limits | score 0.65; width under 0.88 of height; 6 pictures; 12 high scores over 3 seconds | When the re-check gives Fail |
| Large-vest re-check | off | Vests of 70 pixels and more are not re-checked |

Two pose-model entries in the module's settings file are not used.

## What it reports

- **Sentence.** Fail: "Worker 4 wears an unzipped vest. (00:12:31)" for each such worker, at the time of their last
  "open" mark (example numbers). Pass: "No workers with unzipped vests were detected." Not observed: "No
  workers wearing vests were detected."
- **Timeline entry:** Pass, the stretches with at least one worker marked closed; Fail, the stretches with a worker
  marked open, or, for a re-check Fail, the first to the last sampled picture of that worker. A stretch still open at
  the end of the video is dropped.
- **Files:** a drawing file with person boxes and their vest marks and the counts of closed, open and undecided
  workers; an annotated video on request.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, all labelled for this check. The
module matched the client on 51 (74 %). The client labelled 35 Fail and the module caught 24, so 11 of its 18 errors
are missed open vests; the other 7 are turnarounds labelled Pass or Not observed where it said something else. With 35
Fail labels, the test shows that it misses about a third of the violations.

## Known problems

- **Last mark wins.** The client fails a worker after one open stretch, but only the last mark counts: a vest marked
  open, then closed, ends closed, and the verdict is Pass. The module's description file says the opposite and
  describes an older 10-vote window.
- **No blocked-view rule.** The client's "view blocked" case is not built, so such turnarounds get Pass or Fail.
- **Pass is too easy.** Pass does not check "closed in more than half of the frames". Every tracked person counts, even
  one never judged, so people without a readable vest give Pass; Not observed only means that no person was tracked.
- **Dark and small vests.** The main path marks a vest open only if it is bright and at least 70 pixels tall; the
  re-check covers vests of 28 to 70 pixels, and only before a Pass. An open vest at night, in shade or on a distant
  worker can be missed.
- **Known re-check false alarm.** Crew in white shirts, where a tie looks like an opening.
- **New uniform (open requirement).** The new uniform is solid, so the logic needs an update; not agreed yet.
- **The heaviest module.** It reads every frame and runs up to three models per worker; the re-check adds about 2 to 5
  minutes per Pass video.

## In real time

It can run as it is, with the video pictures, and gives the same verdict as post-processing (after the turnaround),
but only when the turnaround ends. To warn while it happens it needs an earlier, interim verdict, for example at the
first "open" mark: a change of when it decides. It needs no stage detector (the part that knows where in the
turnaround we are).

Cost on a 36-minute test turnaround: own work 18.75 milliseconds per frame alone and 26.75 with all the other modules
(54.6 for the slowest 5 % of frames), the most of any module; with the shared General Model and tracker, 35.0 of the 125
milliseconds each frame may take (28 %). As a post-processing job: about 370 seconds. Planned savings with identical
results: drop a full-picture copy and an unused resize, and judge all people of a frame together. It is first in line
among the heavier modules: it covers the whole turnaround and has many Fails. The client's split puts it in the
streaming group.

## For developers

- **Module code:** M23. **Repository:** `dxgat/detectors/safety-vests-secured-to-body`; production `tdv_cone` @
  `8f58d7e` (2026-08-13). `master` @ `ae8ef16` (2026-08-06) has neither the re-check nor the presence gate and pins
  ultralytics 8.2.81 (production 8.4.83).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, cone_camera, write_video,
  json_logger)` (`cone_camera` unused); `Person` (votes, mark), `get_report`; `classifier_utils.py` (Swin-T),
  `vests_utils.py` (colour masks), `v4_override.py` + `v4_config.yaml` (re-check; `README_V4.md`, in Ukrainian).
  `fail_guard.py`, `export_v4_probe.py` unused at run time.
- **Models (DVC):** view Swin-T `pose_classifier.pt`, closure Swin-T `vest_classifier.pt`, presence ResNet-18
  `presence_bbox_r18.pt`, small-vest ResNet-18 `v4_cnn2.pt`, `yolov8m-pose.pt`; `v4_probe_head.npz` unused (CLIP probe).
- **Run:** `python main.py --source <video>.mp4 --weights-dir weights [--device cpu] [--write-video]`; `python
  single_run.py <video_id> [<path>]` for per-person debug output.
- **Keys:** code `_max_len_inference` 20, 0.75, HSV V ≥ 200, h ≥ 70, w ≥ 40, `_age` ≥ 100 frames, pairing 0.85, presence
  0.5 (env `VEST_PRESENCE_BBOX_W=0` off), colour test needs ≥ 40 × 25 px. `v4_config.yaml`: `enabled`, `stride` 12,
  `min_vest_h` 28, `min_person_h` 42, `rel_inter` 0.7, `band_split` 70, `t_small` 0.65, `max_aspect` 0.88, `min_crops`
  6, `main_autofail` false; env `V4_SMALL_MIN_HOT` 12, `V4_SMALL_MIN_SPAN` 3. Unused: `pose_config`,
  `pose_checkpoint` (HRNet-W32).
- **Code places:** pairing `main.py:401-409`; view `:418-422`; closure `:423-427`; gates `:68-96`; colour `:152-221`;
  votes `:116-122`; mark `:129-149`; verdict `:246-268`; re-check `v4_override.py:90-141, 192-344`, `main.py:492-501`;
  timeline `:449-459, 503-506` (frames counted from 0).
- **Dependencies:** pins `cv_common` 29def48, `db_worker` 5a4aa83 (`master`: 4291b0d, 0248146); the export holds
  `cv_common` ac5098d. Docker `gpu_base`. Logic diagram: Confluence modules database, 2023-07-10.
