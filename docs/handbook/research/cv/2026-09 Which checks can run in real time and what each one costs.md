# Which checks can run in real time, and what does each one cost?

*September 2026 · Valentyn, with Yurii Luchko (making the heavy checks lighter) · Status: measurements done; the work to
make the heavy checks lighter is in progress*

## In short

We ran every module unchanged as if the camera were live. **20 of the 27 modules give the same verdict as
post-processing**, 3 of them only when the recording closes; 4 cannot, because they read the recording twice;
3 are not hosted yet. A module's own work is small (under 3.3 milliseconds per frame for 17 of the 20); the shared
General Model and tracker are the real cost, 19 to 47 milliseconds of the 125 milliseconds each frame allows. All 20
together kept up with the camera at 56 milliseconds per frame. Live accuracy on the monthly test drops from 86.7 % to
83.8 %, because on about one turnaround in six the live system picks up the arriving aircraft too late; that fix belongs
to the stage detector.

## The question

Today every check answers about 24 hours after the turnaround. Which checks can decide while it happens, what does each
cost, and in which order should they move "into minutes"?

A **frame** is one picture of the video (the cameras take 8 per second, so there are 125 milliseconds per frame); a
**track** is the same object followed from frame to frame; a **verdict** is Pass, Fail or Not observed; a **stage** is a
part of the turnaround; a **module** is the code of one check; **service vehicles** are the ground support equipment
(tugs, belt loaders, fuel trucks, tractors).

## What we did

1. Read every module's code: when does it decide, and does it need the whole recording?
2. Ran each module alone on a 36-minute turnaround of the monthly test (the client's validated turnarounds we measure on),
   fed like a live camera: each frame handed over once, in order, the end unknown. Then the 20 that work, together.
3. Compared verdicts over the whole monthly test (69 turnarounds, 90 videos), ran the 21 turnarounds still on disk fully
   live, and compared the cost with post-processing and production's machines.

## What we found

### Why some checks can decide live and others cannot

A check can run live when it decides during the turnaround (at a moment such as the arrival, at a deadline, or at the end
of a stage), reads each frame once and in order, and fits the time budget. Four things stop a module:

- **It reads the recording twice.** Live, the first frames are gone. The wheel chocks module and the pushback driver's
  pin check first look ahead to where the pushback tug finally parks; hand signals first averages the cargo door's
  position over the 60 seconds after arrival; safety zone first builds the zone from the nose wheel's path, then re-reads
  the 2 minutes before the stop. Fixable with a "pushback attached" moment from the stage detector, or a single pass.
- **The rule decides after the fact.** Safety zone, pushback path, pushback waiting for wing walkers and hand signals are
  the checks where seconds matter, and all four judge a moment already passed. Live they give a faster report, not a
  warning in time; a warning needs a new trigger agreed with the client.
- **The question only makes sense at the end.** The two walk-arounds judge the whole walk.
- **It cannot be hosted.** Hair policy is protected code that runs only on an old version of its programming language.

### Each check, measured

"Arrival" is when the tracker decides the aircraft has stopped (still for about 4 seconds); "departure" is when it decides
the aircraft moves away (about 10 seconds of motion). Here the arrival came 6 minutes in, the departure 24 minutes 25
seconds in, and the recording ran 11 and a half minutes more.

| Check | Runs live as written | Own work (milliseconds per frame) | Answer arrives |
|---|---|---|---|
| Chocks and cones available and staged for arrival | yes | 0.09 | at arrival |
| Crew present 10 minutes prior to aircraft arrival | yes | 0.54 | arrival + 64 seconds |
| FOD walk completed | yes, reads the video | 1.32 | at arrival |
| Safety huddle conducted at huddle cone | yes, reads the video | 0.87 | arrival + 60 seconds |
| Employees wearing safety vests secured to body | yes, reads the video, answers at the end | 18.75 | recording closed |
| Safety zone confirmed clear | no: reads twice | — | — |
| Hair policy | not hosted | — | — |
| The three wheel chock checks, one module: Nose gear chocks applied immediately; Main gear chocks removed only after aircraft is attached to pushback; Nose wheel chock removed from aircraft | no: reads twice | — | — |
| Cones placed in proper positions and timely | yes | 0.62 | departure + 10 seconds |
| Steering by-pass pin installed, or steering otherwise bypassed | yes, reads the video | 0.73 | arrival + 4 minutes 5 seconds |
| Lead marshaller and wing walkers in correct position | yes, reads the video | 2.50 | arrival + 10 seconds |
| Beltloader rear cone positioned after BL is in place | yes | 0.37 | at departure |
| All GSE guided into aircraft using approved hand signals | no: reads twice | — | — |
| Post-arrival aircraft walk around inspection completed accurately | not hosted | — | — |
| 3 stop brake check | yes | 0.64 | at departure (the count is final when the belt loader parks, so it could answer then) |
| All cargo bin doors opened and verified | yes | 0.87 | arrival + 2 minutes 44 seconds |
| Motorized GSE parked and properly chocked | yes, reads the video, answers at the end | 3.25 | recording closed |
| Handrails on GSE being used | yes, reads the video, answers at the end | 12.46 | recording closed |
| Safety handrails fully extended and used | yes, reads the video | 2.37 | at departure |
| Belt loader forward chock remained in place until unit is backed up clear of aircraft | yes | 0.34 | at departure |
| Conditioned air removed 10 mins prior to departure and properly stowed | yes, reads the video | 1.26 | departure + 10 seconds |
| Cones are removed only after all GSE is clear of A/C and chocked | yes | 1.54 | at departure |
| Pushback operator verifies steering bypass pin installation | no: reads twice | — | — |
| Pre-departure walk around completed | not hosted | — | — |
| Pushback does not start until wing walkers are in place and ready | yes | 0.33 | departure + 14 seconds |
| Pushback pathway confirmed clear of obstacles | yes | 0.48 | departure + 20 seconds |
| Wing walkers in proper position and using approved wands | yes, reads the video | 5.14 | departure + 44 seconds |

### The shared part is the bill

| Shared part, paid once per camera | Milliseconds per frame |
|---|---|
| General Model: main detector · with the chock detector · with the vehicle detector · all three | 8.5 · 11.5 · 14.3 · 19.2 |
| Tracker: aircraft · aircraft and people · aircraft and belt loaders · all four kinds of objects | 4.9 · 7.7 · 20.7 · 26.2 |

The first check that needs belt loaders followed pays about 15.7 milliseconds per frame for them; each later belt loader
check pays only its own work, under 2 milliseconds for most. So the order is built on the extra cost of the next check.

All 20 together: **56 milliseconds per frame** (95 for the slowest 5 %), the graphics card 24.5 % busy, 4.2 processor
cores, 18 gigabytes of memory, and 20 of 20 verdicts and reports identical to post-processing. Each module runs in its own
process beside the shared steps, so processor and memory, not the graphics card, limit a full set. On a second
turnaround single frames waited up to 15 seconds around the arrival, while memory reached 23 of 27 gigabytes.

### Accuracy

| Comparison | Verdicts the same | Accuracy against the labels |
|---|---|---|
| Rebuilt General Model and tracker against the production files, whole monthly test | 851 of 858 | 86.7 % against 86.6 % |
| Each module given only the objects it reads, against everything | 740 of 740 | 86.5 % both |
| Live, the arriving aircraft picked up as in post-processing | 70 of 70 | — |
| Live, the arriving aircraft picked up late (about one turnaround in six) | 112 of 148, mostly changed to Not observed | 83.8 % over the test, against 86.7 % |

Post-processing knows the whole video and takes the aircraft with the longest track; live, the system can only take the
longest track so far. An aircraft that taxied past or stood at the next stand earlier keeps the title, and if it stood
still for 4 seconds the arrival is set on it. Another box rule did not help (82.9 %); the stage detector has to decide
which aircraft is ours. *Later note (October 2026):* the monthly test's "production" files come from an older line of
the General Model; see the report *Which General Model version the monthly test compares against*.

### Against post-processing and today's machines

The work is about the same live and in post-processing, but a live stream holds its machine for the whole turnaround
and cannot wait for a free card. In September production spent 2.4 hours on the General Model and 1.3 on the tracker for
a median 87-minute video, so live needs less machine time but a stronger machine: in the production slot the General
Model alone spent 1.7 times the budget on each frame. A stream with 3 to 6 checks needs about 2 cores of the test machine (6 to 8 virtual
cores of a modern server) and 5 to 7 gigabytes; a card like production's is enough with a faster detector runtime (61 of
125 milliseconds, emulated) and only just without it.

### The order to move the checks

| Group | What it needs | Checks |
|---|---|---|
| Already running together live | — | three-stop brake check, pushback path, pushback waits for wing walkers |
| Answers during the turnaround (15) | the stage detector, a machine that keeps 8 frames per second | every "yes" above that answers before the recording closes, except the two pushback checks |
| Answers only at the end (2) | an interim verdict | motorized service vehicles chocked, handrails on service vehicles |
| Rule decides after the fact (2) | a new trigger with the client | pushback path, pushback waits for wing walkers |
| Reads the recording twice (5 verdicts) | one pass | safety zone, pushback driver's pin check, the three wheel chock verdicts |
| Stays in hours | — | hand signals, both walk-arounds, the derived belt loader approach task |
| On the camera itself | a small detector and classifier | hair policy, safety vests |

Four checks the roadmap still had in hours already run live with the same verdict: crew present, safety huddle, chocks
and cones ready, cargo doors. Safety vests took the camera slot first planned for "nose wheel chock placed right after
arrival": it needs nothing from the aircraft or the stage, though as written it is heavy (18.75 milliseconds per frame).

## What it means

- Most checks can answer in minutes without being rewritten. Verdicts do not get better: Not observed in hours is Not
  observed in minutes. What changes is when the answer arrives; it becomes an alert once the alert service exists.
- For the four seconds-matter checks a faster report is not a warning in time; that is a decision with the client.
- The cost is the shared General Model and tracker, so streams should share a card.

## What is next

1. The stage detector: open each check only in its stage, decide which aircraft belongs to the turnaround.
2. An interim verdict for the end-only checks; one pass for the four two-pass modules.
3. Lighter heavy modules: at most 10 milliseconds per module, 25 for all checks active in a stage. Each change is proved
   by byte-identical outputs, or by the same verdicts on all 69 turnarounds, or, when verdicts may change, by accuracy
   approved by Oksana (accuracy) and Ihor (technical review); a check with fewer than 5 Fail labels cannot carry that.
4. New triggers for the seconds-matter checks, and measurements inside a production machine slot.

## For developers

- Tasks: PF-Q2-11 (budget, EXACT / NEAR / SEMANTIC gates, single-pass hand-signals and safety-zone), PF-Q2-15 (cost per
  module), PF-Q2-12 (interim verdict), PF-Q3-04 (PUSHBACK_ATTACHED for aircraft-chocks, pin-verification), PF-Q3-06
  (`trigger-change`), PF-Q1-03 (stage detector).
- Reports: `docs/analysis/rt_module_selection.md` (v1 2026-09-15: A 11 / B 2 / C 9 / out 5), `rt_module_cost.md`,
  `rt_environment.md` (pod envelope, 40-gate sizing), `rt_priority_plan.md` (waves A–E, edge list),
  `roadmap_move_analysis.md`, `tasks/notes/PF-Q2-11.md`; NOW / NOW_PX / PATCH / RETHINK / POST in `docs/04_modules.md`;
  baseline caveat `docs/analysis/gm_baseline_lineage.md`.
- Event `zHxIAF2vUGxJ.mp4` (T_arr 2884, T_dep 11727 of 17 280 frames); RTX 5070 Ti 16 GB, 8 cores, 27 GB. Pod: T4,
  3.92 vCPU Haswell, 12.1 GB, emulated as heads 3× slower until `scripts/node_bench.py` runs. Faster runtime = TensorRT.
- Scripts: `scripts/rt_module_cost.py`, `rt_joint_run.py`, `rt_resource_fit.py`, `rt_priority_plan.py`,
  `rt_main_aircraft_delay.py`, `rt_live_accuracy.py`; main-aircraft rule `pf/pipeline/causal_rows.py` (`longest_so_far`).
- Check names, repositories and codes (M01–M27, HP): `docs/handbook/_data/modules.json`.
