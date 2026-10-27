# Can the General Model and the tracker skip every second frame?

*October 2026 · Valentyn, with Yurii Luchko · Status: in progress. One measurement on three checks is done; a larger
sample and a version that keeps the tracker's waiting times in seconds are next*

## In short

The team's real-time worker falls behind when its tracker gets one processor core. We let the General Model and the
tracker work on every second frame only and handed their last result to the checks for the frame in between, so every
check still sees 8 frames a second. On the busiest 4 minutes of a turnaround, with the detector slowed down to stand in
for production's graphics card, one core went from **127 to 71 milliseconds per frame** (−44 %), and the delay of the
slowest frames from 12 seconds to 0.28 seconds. On 15 turnarounds per check, **42 of 45 verdicts** of the three checks
stayed the same and the correct verdicts went from 36 to 37 of 45. The sample is small and 7 % of the verdicts do change,
so before use it needs an accuracy check on the client's validated turnarounds and an approval. A second core or a
faster detector runtime, which skip nothing, already keep the three checks up with the camera on their own.

## The question

A **frame** is one picture of the video; the cameras take 8 per second, so a live system has 125 milliseconds per frame
on average. The General Model is the shared detector that draws a box around every object it finds (a **detection**);
the tracker follows each object from frame to frame (a **track**) and decides whether it is moving or standing still.
A **verdict** is Pass, Fail or Not observed. **Service vehicles** are the ground support equipment around the aircraft
(tugs, belt loaders, fuel trucks, tractors).

The team's real-time worker is built of containers, separately packaged programs that run side by side and share one
graphics card. The General Model container and the tracker container each get one processor core. The camera uploads
one-minute pieces of 450 to 460 frames, so each container has to finish a frame in about 130 milliseconds or the backlog
grows. On one fast core of the test machine the tracker alone needs about 60 milliseconds per frame; on a production
core (about 0.6 of one of ours) that is about 100 milliseconds, before it unpacks the pictures it receives (about 7
milliseconds per frame there) and before the slower production card. It does not keep up, which is what the worker
shows.

So the question: if the General Model and the tracker look at every second frame only, how much time does that save, and
do the verdicts change?

## What we did

1. **Sample and hold.** The General Model and the tracker process frames 1, 3, 5 and so on. For frames 2, 4, 6 the
   checks receive the boxes and tracks of the frame just before. The checks themselves are unchanged and still read 8
   frames a second.
2. **The tracker was not re-timed.** Its waiting times (how long a vehicle must stand still or move before its status
   changes) are counted in processed frames, so they now last twice as long in seconds: a status that needed 4 seconds of
   standing still needs about 8.
3. **Speed.** The three checks that already run live together (three-stop brake check, pushback path clear of obstacles,
   pushback waits until the wing walkers are in place and ready) on the busiest 4 minutes of a 36-minute turnaround, in
   our prototype: one program holding the General Model, the tracker and the three checks, pinned to the cores the
   worker gives (the worker splits the same work across containers). The detector parts were made 3 times slower to
   stand in for production's graphics card. Three set-ups: one core with the standard detector runtime (as in the worker
   today), two cores, and one core with a faster detector runtime.
4. **Accuracy.** The 21 videos of the monthly test (the client's validated turnarounds we measure on) still on disk, 15
   turnarounds per check. Each verdict was compared with the run on every frame and with the client's label.

## What we found

### Speed

| Set-up | Every frame: time per frame · delay of the slowest 5 % of frames | Every second frame: time per frame · delay |
|---|---|---|
| 1 core, standard runtime (the worker today) | 127.0 milliseconds · **12.0 seconds**, falls behind in the busy minutes | **71.3 milliseconds** · 0.28 seconds |
| 2 cores, standard runtime | 102.1 milliseconds · 0.29 seconds | 59.2 milliseconds · 0.23 seconds |
| 1 core, faster detector runtime | 80.0 milliseconds · 0.26 seconds | 48.6 milliseconds · 0.23 seconds |

The time fell by 39 to 44 %, not by half: decoding the video and the checks themselves still run on every frame. A
frame that is processed costs what it did (140 to 180 milliseconds for the slowest frames); the queue absorbs it because
the next frame is cheap.

### Accuracy

| Check | Turnarounds | Same verdict as every frame | Correct against the label: every frame → every second frame |
|---|---|---|---|
| Three-stop brake check | 15 | 13 | 10 → 12 |
| Pushback waits until the wing walkers are in place and ready | 15 | 14 | 13 → 12 |
| Pushback path clear of obstacles | 15 | 15 | 13 → 13 |
| **Total** | **45** | **42 (93 %)** | **36 → 37 (80.0 % → 82.2 %)** |

Three verdicts changed. Both three-stop changes moved to the client's label (one Fail became Pass, one Pass became Fail).
The wing walker change moved away from it: Pass became Fail where the label says Pass. The likely cause is the tracker's
doubled waiting times: the counts that decide when a vehicle or the aircraft counts as stopped or moving.

### The other ways to save time, measured in the same work

| Change | Does it change any output? | Effect |
|---|---|---|
| Run the tracker's three identity updates (one each for belt loaders, people and service vehicles) one after another instead of side by side; on one core they only got in each other's way | no | one core: 59.7 → 47.5 milliseconds per frame for the tracker |
| The above plus three settings: helper threads capped to the container's cores, the vehicle identity network in a fixed mode, the full-picture noise check every 10 seconds instead of 2 | two of the settings change numbers slightly; no verdict changed on 19 videos (2 more to rerun) | one core 45 to 48 milliseconds; two cores 37.7 |
| A faster runtime for the three detector parts | tiny numeric differences in the boxes; the verdict check is still to run | 19.2 → 11.1 milliseconds per frame |

About the "fixed mode": production runs the vehicle identity network in its training mode, where the result for one
vehicle depends on which other vehicles are in the same frame; the fixed mode removes that dependence, so it is a change
of numbers, not only of speed. Two settings did not help: half-precision numbers in the identity network (no gain,
because each call is too small to benefit) and automatic tuning of the graphics card's routines (164 instead of 60
milliseconds, because it tunes again whenever the number of picture crops changes, which is every frame). With the
faster runtime and the settings, the three checks keep up on one core: 78 milliseconds per frame, 122 for the slowest
5 %.

## What it means

- **Every second frame is the reserve, not the first fix.** In the emulation a second core or the faster runtime already
  keeps the three checks up with the camera (102 and 80 milliseconds per frame); the second core changes nothing the
  checks see, the faster runtime only the last digits of the boxes. Every second frame on top saves about 40 % more (59
  and 49 milliseconds), which is room for more checks or more cameras on one card.
- **It is the only one of these levers that changes verdicts.** The team sorts every speed-up into three kinds: changes
  that leave outputs identical, changes that move numbers slightly but keep the verdicts, and changes that can alter
  verdicts. Skipping frames is the third kind. It needs the accuracy on the client's validated turnarounds, per check,
  approved by Oksana (accuracy validation) and Ihor (technical review).
- **The sample is too small to judge yet.** 15 turnarounds per check found no loss of accuracy, but 7 % of the verdicts
  moved. Pushback path has only 3 turnarounds labelled Fail in the monthly test, fewer than the 5 the team asks for
  before judging a change of the third kind on a check.
- **Live answers can come a little later.** An object that first appears on a skipped frame is seen one frame (an eighth
  of a second) later, and every status that waits for standing still or moving waits twice as long in seconds until the
  tracker is re-timed.

## What is next

1. A version that scales the tracker's waiting times back to seconds, which would remove the likely cause of the changed
   verdicts. Not run yet.
2. Every check that runs live, on all labelled turnarounds of the monthly test, then the approval by Oksana and Ihor.
3. A narrower variant: run only the chock detector and the vehicle detector every fourth frame and reuse their boxes in
   between. Estimated General Model time 11.2 milliseconds per frame with the standard runtime and about 6 with the
   faster one; a chock that appears would be seen up to half a second later. The chock checks decide over minutes, so
   the risk is expected to be small, and it can be measured the same way.
4. First the exact options in the worker: two cores and the settings for the tracker container, and the faster runtime
   in the General Model container (a change of that container's image by Maksym Chernyshev), each with its verdict check.

## For developers

- Task PF-Q4-02, note section "GM and the tracker on every second frame, the three assembled checks (2026-10-12)".
  Flags: `pf/rt/pipeline.py --stride`, `scripts/tracker_v2_run.py --stride`, `scripts/testset/variant_run.py
  --hold-stride`; speed `scripts/rt_resource_fit.py --name trio_stride` (T4 emulated as heads 3× slower, 240 s of the
  busy stretch of `zHxIAF2vUGxJ`); accuracy `out/testset/compare_stride2_vs_v2.json` against the v2 run set.
- Flipped verdicts: 3-stop `63xitGPpUtLy` fail → pass and `8tve3pVzl5D8` pass → fail (both towards the label);
  pushback-does-not-start `OPsMEZUPjBtv` pass → fail (label pass). Tracker thresholds count updates; the time-scaled
  variant does not exist yet.
- Worker: `realtime-pipeline` `k8s/chunk-once.yaml` @ 7f10615 (general-model and trackers containers request 1 CPU;
  1-minute chunks, ≤ 130 ms per frame). Tracker switches in `pf/tracker/stream.py` `TrackerOptions`:
  `deepsort_parallel=False` and `cpu_threads` (EXACT), `reid_eval` and `estimate_sigma_interval_s` (not exact),
  `reid_half` and `cudnn_benchmark` (no gain / do not use). Light-variant gate: `out/testset/compare_light_vs_v2.json`
  (51 of 56 task verdicts, the 5 differences on `beqQ5Q0FoFWP` and `hmMUVO4MdtU8`, crashed out of memory).
- Faster runtime = TensorRT fp16 heads (19.2 → 11.1 ms busy); verdict gate `--variant trt --gm-provider tensorrt`.
- Gate classes EXACT / NEAR / SEMANTIC and the five-fail rule: `tasks/notes/PF-Q2-11.md`; heads at different rates:
  lever 7 of `docs/analysis/rt_optimisation_plan.md`.
