# Steering by-pass pin installed, or steering otherwise bypassed

*In plain words: steering bypass pin installed.*

> Within 4 minutes after the aircraft arrives, a worker must install the steering bypass pin at the nose gear, or bypass
> the steering with the bypass switch. The software watches workers who stop next to the nose wheel, follows their body
> movement with a pose model over a 25-second clip around each stop, and lets a model trained by the team decide whether
> the movement was a pin installation.

## Status

| | |
|---|---|
| How accurate it is | 50 of 55 turnarounds correct (91 %) on the monthly test |
| Fail turnarounds it caught | 4 of 6 |
| In production | the version of June 2025 |
| Who looks after it | to assign |
| Biggest open problem | The client's chock and blocked-view conditions are not implemented: chocks are never checked, and a blocked view gives Fail unless the nose wheel itself is missing for more than 60 seconds. |

## What the client wants

The client calls this check *Steering by-pass pin installed, or steering otherwise bypassed*.

| Verdict | When |
|---|---|
| Pass | The pin is installed within 4 minutes after the aircraft's arrival. In the first minute after arrival, or until the installation, the chock installation is checked as well. |
| Fail | The pin is not installed within 4 minutes after arrival. |
| Not observed | The nose wheel was not seen for 1 minute after the aircraft stopped, or there was no pre-arrival stage. |
| Not observed, view blocked | There are obstacles for more than 1 minute after the aircraft's arrival. |

A verdict is the answer of a check: Pass, Fail or Not observed. A stage is a part of the turnaround; "no pre-arrival
stage" means the video does not show the time before the arrival. The client does not say how the chock condition
changes the verdict. "Steering otherwise bypassed" is the bypass switch, which the module accepts instead of the pin.
The client puts the check in its streaming group, between the real-time group (checks wanted while the turnaround
happens) and the post-processing group (checks judged after it).

## When and where it looks

The stages are the arrival and the time after the aircraft stops. The window opens at the tracker's arrival moment (the
aircraft has stood still for about 4 seconds) and closes 4 minutes later.

It runs on the cone camera (the camera that looks towards the aircraft nose), for aircraft only: the client's split has
no camera for jets, so the check is not run for them. The code ignores the camera flag it is given.

## What it looks at

- **From the General Model:** nose wheel boxes (a detection is a box the detector draws around an object). Person and
  chock boxes are collected but not used.
- **From the tracker:** the aircraft (arrival moment and a smooth arrival) and people: where each one stands and how fast
  it moves (a track is the same object followed from frame to frame).
- **From the video itself:** yes. It keeps the last 25 seconds of pictures in memory, so that the pose model can look at
  a worker around a stop.
- **Own models:**
  - a pose model (a standard one, not trained by the team): it finds a person's 17 joints, such as shoulders, elbows,
    wrists, hips, knees and ankles;
  - the pin installation classifier, trained by the team: it looks at how a worker's joints moved over a 25-second clip
    and labels the movement "pin at the nose gear", "bypass switch" or "nothing". A fitted scaling file prepares the
    numbers for it.
- It runs on a graphics card.

## How it decides, step by step

A frame is one picture of the video; the cameras take 8 per second.

1. **Arrival stage.** The aircraft is rebuilt from the tracker on each frame. An arrival stage exists if, before
   stopping, it moved smoothly for more than 3 seconds in a row: the points the tracker follows on it moved on average by
   at most 50 pixels sideways and 5 pixels up or down from frame to frame.
2. **Start.** The module waits for the tracker's arrival moment. Without an arrival stage it stops 5 seconds later with
   Not observed.
3. **Pin area.** For the next 4 minutes it counts the frames without a nose wheel box, keeps the last 25 seconds of
   frames in memory and averages the largest nose wheel box. Around the bottom of the wheel it builds the pin area: from
   1.5 wheel heights left to 2.85 wheel heights right, and from 0.5 wheel heights above to 0.65 below. A second target
   lies about 1.35 wheel heights to the right, at the bypass switch.
4. **Stops.** For each person track it follows the point at the feet and its speed. The speed is scaled to the wheel's
   size (as if the wheel were 74 pixels tall), up-and-down movement counts 4 times as much as sideways, and it is
   smoothed over 5 frames (0.6 seconds). A person in the pin area slower than 5 (in these scaled units) for at least 5
   frames in a row (0.6 seconds) is "stopped"; the module records how close the person comes to the wheel or switch.
5. **Clip.** 12.5 seconds after the moment a stopped person came closest to the wheel or switch, the module builds a
   25-second clip centred on that moment. On each frame the pose model finds the person's joints, on a slightly enlarged
   cut-out with the brightness evened out. The person's box is measured relative to the wheel and the 17 joints relative
   to the ankles; gaps are filled, and the series is smoothed and scaled.
6. **Classification.** "Pin at the nose gear" or "bypass switch" gives **Pass**, and the module stops 5 seconds later.
   "Nothing" keeps it watching.
7. **Verdict** at arrival plus 4 minutes, or at the end of the video: **Pass** if a pin was found; otherwise **Not
   observed** if the nose wheel was missing on more than 60 seconds of frames in total; otherwise **Fail**. No arrival,
   or no arrival stage, gives Not observed.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Window after arrival | 4 minutes | Time allowed for the pin; Fail comes at its end |
| Missing nose wheel limit | 60 seconds in total | Above it, Fail becomes Not observed |
| When a person counts as stopped | speed under 5, for 5 frames (0.6 seconds) | Which stops are classified |
| Speed smoothing | 5 frames (0.6 seconds) | Steadier speed |
| Speed scaling | up-and-down 4 times; wheel scaled to 74 pixels | Same limit for near and far wheels |
| Clip length | 25 seconds; decided 12.5 seconds after the stop | What the classifier sees; the delay |
| Pin area | 1.5 wheel heights left to 2.85 right; 0.5 above to 0.65 below | Where a stop counts |
| Labels that mean Pass | pin at the nose gear; bypass switch | What counts as installed |
| Pose model | standard whole-body model, 256 × 192 pixel input | Joint positions |
| Classifier and its scaling file | team-trained files | The pin decision |

All values except the last two are written in the code, not in the settings file.

## What it reports

- **Sentence.** Pass: "Pin was installed by worker N. (HH:MM:SS - HH:MM:SS)", 20 seconds either side of the decision.
  Fail: "Pin was not installed during 4 mins after plane arrival." (arrival to arrival plus 4 minutes). Not observed:
  "The front wheel was obscured for more than 1 minute!", "Airplane arrival was not detected" or "There was no arrival
  stage on video".
- **Timeline entry** (the stretch of video the website marks): for Pass, 20 seconds either side of the decision; for Fail
  and for the hidden-wheel Not observed, from the arrival to 4 minutes later, both labelled "Fail"; empty for the other
  Not observed cases. Start and end are stored as text.
- **Files:** a drawing file; an annotated video when video writing is switched on; when clip writing is switched on, a
  plain clip, a clip with the joints drawn, and the joint series of every classified stop.

## How accurate it is

The monthly test is the set of the client's validated turnarounds we measure on: 69 turnarounds, 55 of them labelled for
this check. The module gave the client's verdict on 50 (91 %). 6 were labelled Fail and it said Fail on 4: 2 violations
were missed, and the other 3 wrong verdicts were on turnarounds labelled Pass or Not observed. Six Fail labels give only
a rough idea of how well it catches violations. Our sources do not say which turnarounds were wrong, or why.

## Known problems

- **No chock condition.** The client links the pin check to the chock installation in the first minute; chock boxes are
  collected but never used.
- **No blocked-view rule.** Obstacles are not checked, although the client's rule and the module's own description name
  them. Not observed comes only from frames without a nose wheel, counted over the whole 4 minutes (the client says "1
  minute after the stop"). A worker or vehicle hiding the pin area while the wheel stays visible leads to Fail instead of
  Not observed.
- **Arrival stage instead of pre-arrival stage.** The client asks for a pre-arrival stage; the code checks an arrival
  stage.
- **"Fail" on a Not observed timeline.** The hidden-wheel Not observed carries a timeline entry labelled "Fail".
- **Late stops are never judged.** Decisions come 12.5 seconds after a stop, so a stop in the last 12.5 seconds of the
  window is never classified. If the video ends before arrival plus 4 minutes, the module still decides (Fail when no pin
  was found).
- **Workers are followed only after the nose wheel has been seen once.**
- **Pictures and boxes one frame apart (to confirm).** When the 25-second memory is full, clip pictures and person boxes
  are paired one frame apart; the effect is to confirm.
- **Heavy.** 200 full pictures (about 1.24 gigabytes) are held in memory, and one clip runs the pose model up to 200
  times, one person at a time. A second, larger pose model's files are in the repository but unused.
- **Overlap with another check.** *Pushback operator verifies steering bypass pin installation* (before departure) looks at a related
  action with a hand-written pose rule; the two are to cross-check.
- **A fix waits on a side branch.** A newer version (August 2026, not in production) stops defaulting to Fail when the
  pin area could not be seen.
- **Who confirms:** the points marked "to confirm" are for the module's owner (to assign) to check on a labelled
  turnaround. Adding the chock and blocked-view conditions would change verdicts the client sees, so it is decided with
  the client's safety team.

## In real time

It can run in real time, but it needs the video pictures: the pose model works on the stored frames. A Pass comes 12.5
seconds after the worker's stop; a Fail only at the end of the 4-minute window. The stage detector (the part that knows
where in the turnaround we are) would give the arrival and the 4-minute deadline.

On one 36-minute test turnaround it gave the same verdict and sentence live as post-processing (after the turnaround),
245 seconds after the arrival. Giving it only the boxes and tracks it reads, as the real-time branch does, changed
nothing on the 2 monthly test videos checked. With its share of the General Model and the tracker it needs 19.6 of the
125 milliseconds each frame may take at 8 frames per second (16 %). Its own work is 0.73 milliseconds per frame on
average (1.32 with all other checks running), much more on frames with the pose model; as a post-processing job it takes
26 seconds. With one processor core it kept up with the graphics card slowed down 6 times, not 8 times, nor with the
tracker slowed down too. The card used in production is estimated, not measured, to be 3 to 4 times slower than the test
card.

The team plans to lighten it first, with the same results: small cut-outs instead of full pictures, and one pose model
shared by four checks. On one test turnaround where the live feed picked up the arriving aircraft late, its verdict
changed from Pass to Not observed: a problem of the shared live feed, not of the module.

## For developers

- **Module code in our workspace:** M26.
- **Repository:** `dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed`; production line
  `master` @ `60dca73` (2025-06-19); default branch the same. `steering_observability_fix` @ `45db11e` (2026-08-14, 4
  commits ahead) is feature work, not in production: it stops defaulting to Fail when the pin area was not observable.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, cone_camera, weights_dir,
  json_logger, write_clips)`; `cone_camera` is unused (the README: always the cone camera). `Plane` (arrival-stage
  rule), `PinInstallationAnalyzer` (pin area, stops, clips, classification), `get_report`. Diagram
  `.doc/new_pin_installation.svg`; logic diagram (Confluence, 2025-04-04):
  https://docs.google.com/spreadsheets/d/1oNYniaG6EO67tgz5ZI9npZutjVbZgBKnq3Z-WWrjRbw/edit?gid=827748110#gid=827748110
- **Run on one turnaround:** `python main.py --source <video>.mp4 --weights-dir weights [--device cpu] [--write-video]
  [--write-clips] [--local-inferences --inferences-dir <folder>] [--save-csv]`.
- **Settings keys:** in code `pin_installation_thresh` 1920 frames; missing-wheel limit 480 frames; `velocity_threshold`
  5.0, `min_stop_frames` 5; `filter_kernel_size` 5; `x_scale` 1, `y_scale` 4, `height_ref` 74 px; `window_size` 200;
  pin area −1.5…+2.85 × wheel height across, −0.5…+0.65 vertically; installed labels `LEFT_PIN`, `AUTO_PIN` (else
  `NOTHING`); arrival stage > 24 frames, flow ≤ 50 px / 5 px. Config: `pose_config`, `pose_checkpoint` (HRNet-W48 COCO
  256×192), `classifier_weights` `model_newaug.pkl` (InceptionTime via tsai), `scaler_weights` `scaler.gz`. Unused:
  `hrnet_w48_coco_384x288_dark` weights and config.
- **Code places:** arrival-stage rule `main.py:198-228`; arrival wait, missing arrival stage `:773-787`; 4-minute window
  `:790-801`; missing-wheel count `:804-807`; pin area `:308-343`; speed and stops `:345-436`; stop sequences
  `:452-493`; clip and pose `:495-612`; classification `:614-640`; Pass `:861-869`; verdicts `:34-53, 880-887`.
- **Dependencies:** `cv_common` 8e3a7bf, `db_worker` 5a4aa83 (`git ls-tree HEAD`; local stand-in `cv_common` ac5098d).
  mmpose 1.3.1, mmcv 2.1.0, mmdet 3.2.0, mmengine 0.10.4, tsai 0.3.9, fastai 2.7.18, joblib 1.4.2, norfair 0.3.1;
  Docker base `mmpose_base`. Weights in DVC: `td-hm_hrnet-w48_8xb32-210e_coco-256x192-0e67c616_20220913.pth`,
  `model_newaug.pkl`, `scaler.gz`.
- **Real time and sources:** `docs/04_modules.md` (NOW_PX), `docs/analysis/rt_module_selection.md` (group C: 200 raw
  frames buffered, up to 200 HRNet-W48 calls per stop; 1.9 ms per recorded frame), `docs/analysis/rt_module_cost.md`
  (resource fit, event `KB04bkqBI7ms`); related module M16 `pin-verification`;
  `docs/modules/steering-by-pass-pin-installed-or-steering-otherwise-bypassed.md`,
  `docs/analysis/module_review_2026-10.md`.
