# Hair policy

> No worker on the stand may have hair reaching below the shoulders. The module checks every worker's hair with image
> models. Its production code is scrambled (an obfuscated build), so nobody can read its exact rules; this page describes
> what we know from its settings, its description, its last readable version and its output, and marks the rest "to
> confirm".

## Status

| | |
|---|---|
| How accurate it is | 56 of 69 turnarounds correct (81 %) on the monthly test |
| Fail turnarounds it caught | 28 of 31 |
| In production | the version of June 2025, to confirm (its own code last changed in February 2024) |
| Who looks after it | to assign |
| Biggest open problem | The production code is an obfuscated build that runs only on an old Python version (3.8), so nobody can read, review or move its rules. |

## What the client wants

*Hair policy*

| Verdict | When |
|---|---|
| Pass | Every worker's hair is above shoulder level. |
| Fail | At least one worker has hair below shoulder length. |
| Not observed | No workers were seen, or they were too far away to judge their hair. |
| Not observed, view blocked | The client gives no rule. |

The hair is measured to its lowest point, whatever the hairstyle, tied up or not. The client's notes say the check runs
over the whole video, and the client's sheet marks it as not yet production-ready. A verdict is the answer of a check:
Pass, Fail or Not observed.

## When and where it looks

The whole video, in every stage (part) of the turnaround, according to the client's notes; that the code does the same
is to confirm. In the client's split it runs on both cameras, the cone camera (towards the aircraft nose) and the wing
camera (along the wing), for aircraft and jets.

## What it looks at

- **From the General Model** (the shared detector): which object types it reads is to confirm.
- **From the tracker** (the part that follows objects from frame to frame): the person tracks, as its output shows (a
  track is the same person followed from frame to frame).
- **From the video itself:** yes, every frame (one picture; the cameras take 8 per second).
- **Own models:** a hair model that says, from a worker's picture, whether the hair reaches below the shoulders (a
  version trained with night images); and an inside/outside model that labels each frame "Cambox is inside" or "Cambox
  is outside" (the camera box at the gate; what the label means exactly is to confirm). A body-landmark library is also
  installed; whether it is used is to confirm. In production it runs on a graphics card.

## How it decides, step by step

The steps below are not read from the production code, which cannot be read; each says where it comes from.

1. **View.** On every frame the inside/outside model labels the view. On "inside" frames no worker is judged (seen in
   the output).
2. **Workers.** Each tracked person is cut out of the picture and judged by the hair model; the output shows one label
   per person and frame, for example "Person ID 1: hair above shoulder level".
3. **Worker result.** A worker's labels are combined into one result, and one failing worker fails the video (to
   confirm). The description file says a worker fails when more than half of their frames show hair below the
   shoulders.
4. **Not observed** when no worker is judged (client rule and description file).
5. **The last readable version** (September 2023, with one model and older weights) skipped people under 120 pixels tall
   (the picture is 1,920 × 1,080), taller than 90 % of the picture or touching its side edges. It failed a worker after
   more than 1 second in a row of "below" labels, if the worker had been seen for at least 5 seconds. Whether the
   production build keeps these values is to confirm.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Hair model weights | the version named in the settings file (trained with night images) | How hair is judged |
| Inside/outside model weights | the version named in the settings file | Which frames are judged |
| Blocked-view values | 0.3 and 0.3 to 1, in other modules a box wider than 30 % of the picture with its centre in the right 70 % | Whether the code uses them is to confirm (the last readable version did not) |

Seven more weight files sit next to the two named ones and are not named by the settings.

## What it reports

- **Verdict:** Pass, Fail or Not observed. The exact sentence and timeline format are to confirm. The last readable
  version said "Every worker's hair is above shoulder level.", "Some workers have hair below shoulder level." with each
  failing worker's number and first-to-last time, or "Workers were not detected or were far away.", with one timeline
  entry per worker.
- **Files:** a drawing file with the inside/outside label on every frame, one hair label per person, and the person
  boxes with their track numbers.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, all labelled for this check. The
module matched the client on 56 (81 %). The client labelled 31 Fail and the module caught 28, so 3 of its 13 errors are
missed violations; the other 10 are turnarounds labelled Pass or Not observed where it said something else. So it
catches most long hair, but most of its errors are on turnarounds the client did not label Fail. Why, the code cannot
tell us; our sources do not say which turnarounds these are.

## Known problems

- **The code cannot be read.** The production program is an obfuscated build made on 22 February 2024 with a trial
  version of the obfuscation tool. Its logic cannot be read, reviewed or moved to real time; the readable history ends
  in September 2023. Every rule on this page is therefore to confirm.
- **Old Python only.** The build loads only on Python 3.8 and fails on 3.9 and 3.10, while its build file installs
  packages for 3.10. How the production image runs it is to confirm. A branch prepared for Python 3.10 carries the same
  obfuscated program, so it does not change this.
- **No support for new graphics cards.** No version of the machine-learning library for Python 3.8 supports the newest
  graphics cards, so our test set runs it on the processor instead.
- **Out-of-date description.** Its description file describes an older design (body landmarks and hair outlining with
  a vest mask), not the two image models named in its settings.
- **Unclear production status (to confirm).** It is missing from the list of checks production starts per camera, and
  the client's sheet says it has no repository yet; yet the production cluster runs a container for it and the monthly
  report carries its verdicts.
- **No blocked-view case.** The client's rule has none, and whether the module has one is to confirm.

## In real time

The client's split puts this check in the real-time group, but it is not in our real-time plan for now: its code cannot
be read or changed, it needs the video pictures, and the real-time test setup does not host it (on our test machine it
runs only in a separate Linux environment with the old Python). On a processor it uses about 0.9 seconds of processor
time per frame, while real time allows 0.125 seconds per frame (8 frames per second). Its cost on a graphics card in
production and when it could run in real time are to confirm.

## For developers

- **Module code:** HP. **Repository:** `dxgat/detectors/hair-policy`; production `master` @ `8a343bf` (2025-06-19, to
  confirm), the same as the default branch. Branch `python_3_10` @ `070c998` (2025-12-22): byte-identical `main.py` and
  Pyarmor runtime; only the Dockerfile changes (installs `requirements.txt`, patches `cv_common` requirements to numpy
  ≥ 1.23 and < 2.0, scipy ≥ 1.8, norfair ≥ 2.0), mediapipe 0.10.5 instead of 0.10.1, submodules `cv_common` e4c5e36,
  `db_worker` 495b6ff.
- **Entry point:** `main.py` (Pyarmor 8.3.7 trial, CPython 3.8, bytecode magic 3413) → `detect(...)`, signature to
  confirm; `pyarmor_runtime_000000/` holds the Linux x86-64 runtime.
- **Models (DVC, 9 files, 2 named):** hair EfficientNet-B0 `night_efficientNetb0_223_epoch_06_01_2024.pth`;
  inside/outside EfficientNet-B0 `inside_outside_efficientnet_b0_best_model_17_epoch.pt`; MediaPipe 0.10.1 installed
  without dependencies (use to confirm).
- **Keys:** `hair_classifier_model_name`, `inside_outside_model_name`, `obstacle.width` 0.3, `obstacle.center` [0.3, 1].
- **Run:** CPython 3.8 on Linux only. The test set uses `scripts/testset/wsl_run_module.sh` (WSL Ubuntu 24.04, CPython
  3.8 venv, CPU torch, `--device cpu`); arguments expected to be the shared ones the README lists (`--source`,
  `--weights-dir`, `--write-video`, `--cone-camera`, …), to confirm.
- **Code places:** none for the production build. Last readable logic, `git show cca5eab:main.py` (2023-09-08): person
  filter `:226-231` (120 px, 0.9 height, side edges); classifier `:86-116`; worker rule `:142-153` (> 8 frames in a
  row, ≥ 40 frames seen); verdict and report `:155-173`.
- **Dependencies:** `cv_common` 2ae1b1a, `db_worker` 7883fa4 (`git ls-tree HEAD`; local `cv_common` is ac5098d as a
  stand-in); torch, torchvision; Docker base `mmpose_base`. Not in `db_worker` `ml_global_config.json`; client sheet:
  "no repo yet". Logic diagram: Confluence modules database, 2023-07-10.
