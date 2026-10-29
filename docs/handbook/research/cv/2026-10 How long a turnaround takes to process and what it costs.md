# How long a turnaround takes to process and what it costs

*Timings of 10–22 September 2026, job times of 21–22 October 2026 · Computer-vision team; production job logs: Maksym
Chernyshev · Status: done; to be updated when the faster tracker reaches production*

## In short

For the median production video (148 videos of 10–22 September 2026, about 87 minutes long), the verdicts were ready
**16.8 hours after the end of recording**. 9.5 of those hours pass before the last piece of video even reaches cloud
storage, and 2.5 more go to merging the pieces. The processing itself, from the merged video to the results, took **4.8
hours**; the faster General Model, in production since October, brings it to about 4.2 hours (−13 %). Processing costs
**1.84 to 4.59 dollars per hour of video**, depending on the aircraft type and the number of cameras; the faster General
Model brings this to 1.60–4.05 dollars (10–13 % less). Of the machine time, the checks take 54 %, the General Model 27 %
and the tracker 19 %. The faster tracker (tested on the cluster, not yet in production) saves about 10 more minutes per
video and about 2.5 % of the bill; one shared pose model, about 1 %.

## The question

Words used on this page: a **turnaround** is the whole servicing of an aircraft at the gate; a **verdict** is Pass,
Fail or Not observed; a **check** is one item the client asked for, and a **module** is its code; **machine minutes**
are minutes of one cloud machine running one job.

How long does it take from the end of a turnaround's recording until its verdicts are ready? Where does the time go,
what does the processing cost per hour of video, and what does each speed-up change?

## What we did

1. **Took the median of every step** over 148 production videos of 10–22 September 2026, about 87 minutes long.
2. **Measured machine minutes per minute of video** on 20 production turnarounds, split into General Model, other work
   on machines with a graphics card, and work on machines with a processor only, for four kinds of turnaround. We turned
   them into dollars with the cloud prices.
3. **Read the job logs of five production videos** (21–22 October 2026): the General Model, the tracker and every
   check module.

## What we found

### Where the time goes

The camera box at the gate records the video in one-minute pieces and uploads them to cloud storage. A merge job joins
the pieces into one video per camera. Then three jobs run in a row: the General Model (the shared detector), the tracker
(which follows each object from picture to picture) and the check modules, which all run at the same time.

| Step (median video) | Before (hours) | Now, with the faster General Model (hours) |
|---|---|---|
| The last piece is filmed, until it is in cloud storage | 9.5 | 9.5 |
| The merge waits to start | 1.7 | 1.7 |
| The merge runs | 0.8 | 0.8 |
| The merged video arrives, until the General Model starts | 0.1 | 0.1 |
| The General Model runs | 2.4 | 1.76 |
| The General Model is done, until the tracker starts | 0.1 | 0.1 |
| The tracker runs | 1.3 | 1.3 |
| The checks run, until the video is done | 0.9 | 0.9 |
| **From the merged video to the results** | **4.8** | **4.16 (−13 %)** |
| From all pieces uploaded to the results | 7.3 | 6.66 (−9 %) |
| **From the end of recording to the results** | **16.8** | **16.16 (−4 %)** |

About 12 of the 16.8 hours pass before any processing starts: the upload of the last piece, the wait for the merge and
the merge itself.

### Where the machine time goes

On five production videos (21–22 October 2026, with the faster General Model):

| Job | Machine minutes | Share |
|---|---|---|
| General Model | 589 | 27 % |
| Tracker | 407 | 19 % |
| All check modules together | 1 186 | 54 % |
| **Total** | **2 181** (the parts are rounded) | 100 % |

Before the faster General Model, it took 799 minutes on the same videos, about a third of all the machine time.

The largest check modules on these five videos:

| Check | Machine minutes |
|---|---|
| Handrails on GSE being used | 194 |
| Safety zone confirmed clear | 167 |
| Employees wearing safety vests secured to body | 138 |
| Pre-departure walk around completed | 110 |
| Hair policy | 95 |
| Motorized GSE parked and properly chocked | 76 |
| 3 stop brake check | 57 |

These seven take 837 of the 1 186 check minutes, about 70 %. The five checks whose pose model (the model that finds a
person's joints) could be replaced by one shared model take 105 of the 2 181 minutes, about 5 %.

The checks of one video run at the same time on separate machines, so the time to result depends on the slowest one,
not on their sum. The slowest is the handrails check: 47–74 minutes on three of the five videos. The safety zone check
took up to 51 minutes and the safety vests check up to 35; the hand signals check, by comparison, 6–9 minutes.

### What it costs

The prices used: a machine with a graphics card costs 0.54 dollars an hour at the list price (0.483 after
the discount), a machine with a processor only 0.122 dollars an hour, and merging 0.305 dollars per hour of video per
camera (0.014 when the camera saw no aircraft). The General Model sorts each aircraft into "aircraft" or "jet" by where
its engines sit against the wing; fewer checks run for jets.

Machine minutes per minute of video, measured before the faster General Model on 20 production turnarounds:

| Turnaround | Check modules that run | General Model | Other graphics-card work | Processor-only work |
|---|---|---|---|---|
| Jet, cone camera only | 14 | 1.65 | 1.09 | 0.43 |
| Jet, both cameras | 14 + 10 | 3.22 | 2.59 | 0.96 |
| Aircraft, cone camera only | 27 | 1.85 | 2.35 | 0.75 |
| Aircraft, both cameras | 27 + 11 | 3.74 | 3.39 | 1.05 |

(The cone camera looks towards the aircraft nose, the wing camera along the wing.) An hour of video means an hour of a
recorded turnaround; with two cameras it covers both cameras' videos of that hour. For an aircraft with both cameras,
one hour of video needs 7.14 hours of graphics-card machines and 1.05 hours of processor-only machines: 3.98 dollars of
computing plus 0.61 dollars of merging, 4.59 dollars in all. With the faster General Model, which takes about three
quarters of its old time, the graphics-card hours fall to 6.14.

Cost per hour of video, in dollars:

| Turnaround | Before | Now | Cheaper by | At the discounted price: before → now |
|---|---|---|---|---|
| Jet, cone camera only | 1.84 | 1.60 | 12.9 % | 1.65 → 1.44 |
| Jet, both cameras | 3.86 | 3.40 | 12.0 % | 3.47 → 3.05 |
| Aircraft, cone camera only | 2.66 | 2.40 | 10.0 % | 2.39 → 2.16 |
| Aircraft, both cameras | 4.59 | 4.05 | 11.7 % | 4.12 → 3.64 |
| No aircraft seen (merging only) | 0.01 (one camera), 0.03 (two) | the same | — | the same |

The graphics-card work is most of the bill. That is why the faster General Model lowers the cost (10–13 %) more than
the total machine time (about 9 %).

### What each speed-up changes

| Speed-up | State | Time (median video) | Cost |
|---|---|---|---|
| Faster General Model (same results, byte for byte) | Done, in production since October 2026 | General Model 2.4 → 1.76 hours; merged video to results 4.8 → 4.16 hours (−13 %) | 10–13 % less per hour of video |
| Faster tracker (same tracks) | First cluster run on 28 October 2026; the exact comparison is next | Tracker 1.3 → about 1.13 hours (−13 % measured on five videos); merged video to results about 4.2 → 4.0 hours | About 2.5 % less |
| One shared pose model for the checks that read body poses | In progress (one check is being recalibrated) | No change: none of these checks is the slowest | About 1 % of the machine time (up to 2–3 %) |

## What it means

- **Most of the wait is outside the processing.** About 12 of the 16.8 hours pass before the General Model starts.
  The roadmap's first quarter attacks exactly this: uploading the pieces while the camera is still recording.
- **Inside the processing, the faster General Model saves about 40 minutes** for the median video (done), the faster
  tracker about 10 (tested on the cluster). The tracker's speed-up was twice as large on our machine, but most of it
  was in drawing a debug video that production does not draw. The checks' step ends when the slowest check ends:
  handrails, then safety zone and safety vests.
- **The checks are now the largest share of the machine time (54 %),** and seven of them take about 70 % of it. The
  next savings in cost are in those checks; the shared pose model saves only about 1 %.
- **A second measurement of the General Model's effect agrees.** On four of the five test videos, the time from the
  start of the General Model to the end of the slowest check fell by 15 % (the median video above: 13 %), and the
  machine time of all jobs by 9 %.

## What is next

1. The exact cluster comparison of the faster tracker, then production; then measure these timings and costs again.
2. Look at the slowest and largest checks: handrails on service vehicles, safety zone, safety vests.
3. The upload during recording (the roadmap's first quarter), for the 9.5 hours before processing can start.

## For developers

- Workbook `G:\fullturn_processing_cost.xlsx`: sheet `timings` (median of 148 videos, 10–22 Sep 2026; the "optimized"
  column changes only "GM running"); sheet `per hour` (parameters B2:B7: GPU 0.54 list / 0.483, CPU 0.122, optimized GM
  fraction 0.734, merge 0.305 / 0.014 per camera-hour; cohort inputs from 20 production events in sheet `events`;
  optimized GPU = gm × 0.734 + other GPU).
- Job logs `gs://cv-modules-logs` (21–22.10; GM `b6e1a3e`, trackers, module jobs). Videos `fAkpu3dj2NIj`,
  `ytQDROiCyhBh`, `b8ijKDWsLlQi8W`, `n96M7fASlhGn`, `7PytHarRNqmT`. Production GPU jobs: T4, 3.3 vCPU, 8 GiB. The job
  minutes per video: `docs/analysis/speed/production_job_minutes_2026-10-21_22.json`, made by
  `scripts/production_job_minutes.py` (GM: start in the log name to the upload; trackers and modules: first to last log
  timestamp).
- Largest modules: handrails-on-gse-being-used, safety-zone-confirmed-clear, safety-vests-secured-to-body,
  pre-departure-walk-around-completed, hair-policy, gse-chocks, 3-stop-brake-check. Pose modules (105 min): hand-signals,
  steering, lead-marshaller, wing-walkers, pin-verification (`docs/analysis/pose_unification.md` §8).
- Four-video whole-pipeline figures (processing −15 %, compute −9 %): `tasks/notes/PF-Q2-16.md`. Tracker cluster run
  (28.10, `trackersa6d6c53`, production jobs run with `write_video=False`): `tasks/notes/PF-Q4-02-tracker-mr.md`. Related tasks: PF-Q1-08 (Time to Result baseline), PF-Q1-01 (upload during
  recording), PF-Q2-16, PF-Q4-02.
