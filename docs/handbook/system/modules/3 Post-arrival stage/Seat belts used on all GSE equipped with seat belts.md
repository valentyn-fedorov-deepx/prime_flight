# Seat belts used on all GSE equipped with seat belts

*In plain words: seat belts worn on the service vehicles that have them.*

> Service vehicles (ground support equipment: tugs, belt loaders, fuel trucks, tractors) that have seat belts must be
> driven with the belt fastened. A module for this check exists, but it does not run in production and is outside the
> project's scope today, so the client gets no verdict for it.

## Status

| | |
|---|---|
| How accurate it is | no verdict on the monthly test |
| Fail turnarounds it caught | — |
| In production | no: the module is not among the production jobs |
| Who looks after it | to assign |
| Biggest open problem | Not running: no verdicts at all. The module's logic was last changed in August 2022 and needs an old software stack. |

## What the client wants

A verdict is the answer of a check: Pass, Fail or Not observed.

| Verdict | When |
|---|---|
| Pass | Every person on a service vehicle used the seat belt. |
| Fail | At least one person on a service vehicle did not use the seat belt. |
| Not observed | No service vehicles were seen, or something stood in the way. |
| Not observed, view blocked | The client gives no rule. |

The client's sheet lists the check in the stage after the aircraft stops, but leaves open whether it is ready for
production, which group it belongs to and which cameras it uses.

## What happens today

- **Production:** the module is not among the 27 module jobs that run for every turnaround (checked in the job list of a
  production turnaround, October 2026), so no verdict is made.
- **Monthly test:** 14 of the 69 turnarounds carry a label for this check, all Not observed, and none has a verdict from
  the system; the other 55 do not list the check at all.
- **The project:** it is outside the scope of the current work; whether to build it anew is a decision with the client.

## How the existing module would decide

Read from its code; it has not been run or measured by the team.

1. It follows the people near service vehicles and finds their body points (shoulders, elbows, wrists, hips, knees,
   ankles) with a body pose model.
2. A person counts as sitting on a vehicle when the angle at the knee (between hip, knee and ankle) is under 150
   degrees and the feet are not near the bottom of the vehicle's box.
3. When the vehicle changes between moving and stopped, it judges each sitting person a moment later, in one of two
   ways, chosen by the side the vehicle drove to: from the arm pose on the last 5 frames, or by looking for a belt-like
   stripe across the hip in the picture (a narrow shape tilted 45 to 75 degrees) on more than 2 frames around that
   moment.
4. **Fail** if any person was judged without a belt; **Pass** if at least one person was judged with a belt and none
   without; otherwise **Not observed** ("No visible GSE stopped close").

## Known problems

- **Not running,** so nothing about its accuracy is known.
- **Old and unmaintained:** the logic was written in 2021–2022; the last change, in June 2025, only adapted its
  installation. It needs an old version of Python (3.7) and old versions of its pose libraries.
- **The method depends on the driving direction,** and a person whose vehicle never changes between moving and stopped
  is never judged.
- **No rule for blocked views:** the client gives none, and the module has none.

## For developers

- **Repository:** `dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts`, `master` @ `43068fe`
  (2025-06-19, Docker requirements); logic last changed 2022-08-24 (`6354b27`). Local clone in `external/`.
- **Code:** `main.py` (762 lines): `GSE.update_inner_state` (direction from people inside the vehicle box),
  `PersonTrack._update_sitting_status` (knee angle < 150°, foot position), `inference_unfasten` (elbow angle < 90° on 5
  frames), `segmentation_belt` (Otsu threshold, contour main axis 45–75°, elongation), `_seatbelt_inference`, verdict at
  the end of `detect`. Pose: mmpose top-down (`init_pose_model`, `inference_top_down_pose_model`); people tracked with
  norfair; vehicles from the tracker file (`cls_str == 'gse'`).
- **Stack:** `mmcv_full-1.2.6-cp37` wheel, `mmdetection`, `mmpose` folders in the repository.
- **Monthly report:** task key `seat_belts` (no client name in `scripts/testset/common.py` `TASK_CHECK`).
- **Sources:** `docs/04_modules.md` (verdict NOW_PX), `docs/05_module_logic.md` (row "out of scope, M25"),
  `docs/08_repos.md`.
