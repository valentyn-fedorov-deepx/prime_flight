# HP · Hair policy

> The module checks that every worker's hair is above shoulder level, with two image classifiers applied to the tracked
> workers. The production code is obfuscated (a Pyarmor build), so the steps below come from the configuration, the
> README, the last readable version of the code and the module's per-frame output; the exact rules are to confirm.

## At a glance

| | |
|---|---|
| Checks | HP · Hair policy |
| Stage | Pre-arrival, Arrival, Post-arrival, Download, Upload, Pre-departure, Departure |
| Looks at | The whole video (client sheet: "executed throughout the entire video"); to confirm in the code |
| Cameras | Cone and wing cameras, aircraft and jets (client split) |
| Uses | Tracks: person (seen in the module's output). General Model (GM) classes: to confirm. Video frames: yes |
| Own models | Hair classifier (EfficientNet-B0, `night_efficientNetb0_223_epoch_06_01_2024.pth`, trained with night images); inside / outside classifier (EfficientNet-B0, `inside_outside_efficientnet_b0_best_model_17_epoch.pt`). MediaPipe is installed too; whether it is used: to confirm |
| Runs on | GPU in production (GPU pool); the test set runs it on CPU at about 0.9 CPU-s per frame |
| Real time | to confirm — not in the streaming audit because the code cannot be read; it needs video frames |
| Production version | master @ 8a343bf (2025-06-19) — to confirm; the module code last changed on 2024-02-22 |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | Every worker's hair is above shoulder level. |
| Fail | At least one worker has hair below shoulder length. |
| Not observed | Workers were not detected, or were too far away to identify their hair. |
| Not observed — view blocked | No rule given. |

Hair length is measured to the lowest point where there is hair, whatever the hairstyle (tied up or not). The client sheet marks the check as not production-ready.

## How it decides

1. **View.** On every frame the inside / outside classifier labels the view; the output shows "Cambox is outside" or "Cambox is inside". On "inside" frames no worker is evaluated (seen in the output; the exact meaning of the label is to confirm).
2. **Workers.** Each tracked person is cropped and classified by the hair classifier; the output shows one label per person and frame, e.g. "Person ID 1: hair above shoulder level".
3. **Worker result.** The per-frame labels of a worker are combined into a worker result, and one failing worker fails the video (to confirm). The README says a worker fails when more than **50%** of the worker's frames show hair below the shoulders.
4. **Not observed** when no worker is evaluated (client rule and README).
5. **Last readable version** (2023-09-08, commit `cca5eab`; one classifier, older weights): it skipped persons shorter than **120 px**, taller than **90%** of the frame or touching the side edges, and failed a worker after more than **8 frames** (1 s) in a row labelled "below" if the worker was seen for at least **40 frames** (5 s). Whether the production build keeps these values: to confirm.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `hair_classifier_model_name` | `night_efficientNetb0_223_epoch_06_01_2024.pth` | Weights of the hair classifier |
| `inside_outside_model_name` | `inside_outside_efficientnet_b0_best_model_17_epoch.pt` | Weights of the inside / outside classifier |
| `obstacle.width`, `obstacle.center` | 0.3, [0.3, 1] | An obstacle zone; whether the code uses it: to confirm (the last readable version did not) |

The other 7 weight files in `weights/` are not named by the configuration.

## What it reports

- The verdict: Pass, Fail or Not observed. Report and smart-timeline formats: to confirm. The last readable version reported "Every worker's hair is above shoulder level." or "Some workers have hair below shoulder level." with each failing worker's id and first-to-last time, and "Workers were not detected or were far away."; its smart timeline held one interval per worker.
- Overlay file (.ndjson): the inside / outside label on every frame, one hair label per person, person boxes with their track ids.

## Known issues and limits

- The production `main.py` is a Pyarmor 8.3.7 (trial) build made on 2024-02-22: the logic cannot be read, reviewed or ported. The readable history ends on 2023-09-08 (`cca5eab`).
- The build loads only on CPython 3.8 (bytecode magic 3413); its runtime fails on Python 3.9 and 3.10, while the Dockerfile installs packages for `python3.10`. How the production image runs it: to confirm. The `python_3_10` branch carries the same `main.py`, so it does not change this.
- No torch build for CPython 3.8 supports the newest GPUs, so the test set runs it on CPU.
- The README describes an older design (MediaPipe pose landmarks and hair segmentation with a vest mask), not the two EfficientNet-B0 classifiers named in the configuration.
- Production status is unclear: the module is not in the db_worker task list (`ml_global_config.json`) and the client sheet says "no repo yet", yet the cluster has a pod for it and the monthly report carries its verdicts. To confirm.
- The client rule has no "view blocked" case.

## For developers

- **Repository:** `dxgat/detectors/hair-policy`; production line `master` @ `8a343bf` (to confirm); default branch `master` @ `8a343bf` (the same). Branch `python_3_10` @ `070c998` (2025-12-22) has a byte-identical `main.py` and Pyarmor runtime; it only changes the Dockerfile (installs `requirements.txt`, patches the `cv_common` requirements to numpy ≥ 1.23 and < 2.0, scipy ≥ 1.8, norfair ≥ 2.0), pins mediapipe 0.10.5 instead of 0.10.1, and moves the submodules to `cv_common` e4c5e36, `db_worker` 495b6ff.
- **Entry point:** `main.py` (obfuscated) → `detect(...)`, signature to confirm; `pyarmor_runtime_000000/` holds the Linux x86-64 runtime. Logic diagram (Confluence modules database, 2023-07-10): https://docs.google.com/spreadsheets/d/1_QrMIXxrl1NeogmOJ5zvFnE-L0KC0jQUoKZ-EuIX-Bk/edit?gid=0#gid=0
- **Dependencies:** `cv_common` 2ae1b1a, `db_worker` 7883fa4 (`git ls-tree HEAD`); the local folder holds `cv_common` ac5098d as a stand-in. torch, torchvision, mediapipe 0.10.1 (installed without dependencies); Docker base `mmpose_base`. Weights in DVC (9 files, 2 named in the configuration).
- **Run locally:** CPython 3.8 on Linux only. The test set uses this workspace's `scripts/testset/wsl_run_module.sh` (WSL Ubuntu 24.04, CPython 3.8 venv, CPU torch, `--device cpu`). The arguments are expected to be the shared ones the README lists (`--source`, `--weights-dir`, `--write-video`, `--cone-camera`, …) — to confirm.
- **Code references:** none for the production build. Last readable logic, `git show cca5eab:main.py`: person filter `main.py:226-231`; classifier `:86-116`; worker rule `:142-153`; verdict and report `:155-173`.
