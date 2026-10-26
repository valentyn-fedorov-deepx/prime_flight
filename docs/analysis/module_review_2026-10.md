# Module review, October 2026: where the code differs from the client rule

Read from the production version of every module (pages in `docs/modules/`, versions in `docs/modules/_SOURCES.md`),
the General Model and the trackers, on 2026-10-26. These are findings from reading the code: each needs a run on a
labelled video or the module owner's word before it is fixed or reported to the client.

## Modules

| Module | What the code does differently from the client rule |
|---|---|
| M01 · 3 stop brake check | Reversing is never checked. The tracker resets the stop count after any stop of 3 s or more, so a long brake check wipes the earlier stops. |
| M02A–C · Aircraft chocks | M02B also waits for the belt loaders to leave, which the rule does not ask for. M02C passes if the chock is still seen after attachment; the rule's "video stops before the removal" Fail is missing. `installed_no` looks like a bug. |
| M03 · Cargo doors opened | The obstacle check is called with `camera_config=None` and never fires, so a blocked view gives Fail instead of Not observed. An extra "no pre-arrival stage" case uses 90 frames where the comment says 90 s. |
| M04 · Belt loader forward chock | Does not check that the chock stays until the belt loader backs away; obstacles do not change the verdict. |
| M05 · Belt loader rear cone | Needs more than 80 frames in a row (10 s), the rule says 100 frames in total; the blocked-view Not observed is not implemented. |
| M06 · Chocks and cones staged | The shared arrival detector (also in M11, M18) uses 90 frames (11.25 s) where its comment says 90 s. Pass skips the aircraft and pre-arrival checks. The rule's side-obstacle case is missing. |
| M07 · Conditioned air removed | The production branch is a full rewrite (the architecture review describes the old code). For jets one test compares a horizontal box edge with a vertical one (`main.py:520`), likely a bug. "Properly stowed" is never checked on its own. |
| M08 · Cones removed after GSE clear | Chocks are never checked; "all GSE" means belt loaders only; cones still visible at departure give Pass; the 200-frame and 65 % blocked rules are missing; the obstacle branch rarely fires (a `break` bug). |
| M09 · Cones placed | "Timely" is never checked. The jet rules never fire (`jet` vs `JET`). |
| M10 · Crew present | If no person is ever detected it returns Fail before the blocked-view and 4-minute checks (the rule says Not observed). The branch for videos shorter than 12 minutes never runs. |
| M11 · FOD walk | People are followed only until the aircraft first appears; there is no "diamond area visible" check. |
| M12 · GSE parked and chocked | The aircraft is never used, so any parked GSE counts. The client's Fail column is empty. Bending counts for every orientation, not only frontal. |
| M13 · Hand signals | The blocked-view Not observed is commented out; the driver filter is hard-coded to person id 0. |
| M14 · Handrails on GSE used | The blocked-view case is not implemented; the touch check without the pose model credits a touch to every worker seen on the belt loader in the last 2.5 s; the production branch lacks master's `pretrained=False` fix. |
| M15 · Lead marshaller and wing walkers | The lead marshaller and the wands are never checked; presence needs 90 s, not 10 minutes; the branch's Dockerfile lacks mmpose (how production builds it: to confirm). |
| M16 · Pin verification | Needs 1.5 s of bending or 2.5 s of standing (the rule: 0.5 s / 3 s); standing also needs a raised hand; the first pass reads ahead in the video. |
| M17 · Post-arrival walk-around | Crashes instead of Not observed when the aircraft never stops; whether the July 2026 commits are deployed: to confirm. |
| M18 · Safety huddle | Green is checked with a red–green value and a box-shape test, not LAB colour with a minimum size; Pass and Not observed use different pre-arrival rules. |
| M19 · Pre-departure walk-around | No workers seen gives Fail (the rule: Not observed); the blocked-view rule is commented out; the window is 8 minutes, not 5; its cv_common pin lacks a package it imports. |
| M20 · Pushback waits for wing walkers | The right-side test compares a horizontal position with the top edge of the aircraft box (`main.py:179`), likely a bug that makes it almost always true; it checks walking along after the pushback starts, not readiness before. |
| M21 · Pushback pathway clear | Only the first crossing is kept; if it is more than 15 s before departure the verdict flips to Pass. People are not checked; the chock size limit (25 × 5 px) means chocks practically never count. Measured: 0 of 4 violations caught. |
| M22 · Handrails fully extended | Only checks that the handrails are extended, not used; the "8 minutes" is really 60 s. |
| M23 · Safety vests | A worker's vest status is overwritten at each check, so "unzipped, then zipped" ends as Pass; no obstacle logic; any tracked person gives Pass; dark or small vests cannot fail. |
| M24 · Safety zone | The last 30 s before the stop are never checked; Not observed comes from blocked frames outnumbering clear ones, not from "obstacles over 30 s". |
| M26 · Steering pin | The chock and obstacle conditions are not implemented. |
| M27 · Wing walkers with wands | Wands are never detected (the detector line is commented out) although the report says "approved wands"; "hand signals" means a wrist at or above the elbow for about 1 s; the production branch runs a pose model on video frames. |
| HP · Hair policy | The production `main.py` is an obfuscated build that runs only on Python 3.8, so the logic cannot be read; which build runs in production: to confirm. |

## General Model

- The report's `stages` field is always null; `confidence_camera` is 1.0 when there are no votes; `entity` is an
  [airline, share] pair, not a string; `entity.png` is rewritten on every frame when no airline is found.
- The job could crash when a nose is found but no wing (`main.py:728`).
- The "processed" report is sent before the file upload.
- The October image also moves onnxruntime-gpu 1.16.2 → 1.16.3; outputs were still identical on five videos.
- The job log: the General Model's own per-frame prints are gone, but the cv_common video reader still prints one line
  per frame; the whole log is about 5× shorter, not 55 lines.

## Trackers

- Production cannot run on its pinned cv_common (ac5098d): it needs the `tracker_optimization` line (≈ 2759daf); which
  commit is in the image: to confirm.
- The camera type is never passed to the tracker: wing-camera videos get the cone-camera door rules, and the command
  line defaults to wing.
- The job reports "processed" before the upload finishes; whether the modules can start too early: to confirm.

## What follows

1. The module owners confirm or reject each finding on one labelled video (the monthly test set has fail labels for
   some checks).
2. Findings that change a verdict the client sees are decisions for the client's safety team (as for the rules on the
   October slides), not silent fixes.
3. The confirmed bugs go to Jira; the module pages are updated when they are fixed.
