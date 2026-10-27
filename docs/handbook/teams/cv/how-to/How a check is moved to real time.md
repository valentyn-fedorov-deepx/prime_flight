# How a check is moved to real time

**For:** a CV engineer who moves a check from post-processing (after the turnaround) to the real-time branch (while it
happens).

## What changes for a check in real time

After the turnaround a check sees the whole video and can go through it as many times as it wants. In real time it sees
the video piece by piece as it arrives, has to keep up with 8 frames per second, and shares one graphics card with the
General Model, the tracker, the stage detector and the other checks. The whole chain has about 125 milliseconds per
frame.

In the real-time worker a check gives only its verdict — the check, Pass / Fail / Not observed, and the time. It does
not send alerts and does not write to the database; other parts do that. It runs as its own container on the same
graphics card. It starts only when the stage of the turnaround and the aircraft type are known (checks of the time before
arrival run from the start, but may decide only once a turnaround exists).

## Steps

1. **Find out how the check decides** (its page, *How it decides*):
   - it decides at one moment by looking back at what it has seen — it can run as it is;
   - it first goes through the whole video to find something it needs later (for example where the pushback finally
     stopped) — this part must be rewritten to work as the video arrives;
   - it can only decide after the fact (for example "the pushback path was clear during the whole pushback") — it still
     works in real time, but it cannot warn before the violation. To warn in time, the moment of the decision has to
     change: that is a change of the rule and needs the client's agreement.
2. **Find out what it costs:** does it read the pictures, does it run its own models, how many milliseconds per frame.
   The research report *Which checks can run in real time and what each one costs* has the numbers for every check.
3. **Use the stage detector's moments.** Many checks compute the arrival of the aircraft or the pushback themselves. In
   real time the stage detector owns these moments; the check takes them from there instead of computing its own copy.
4. **Build it as a container of the worker,** following the worker's architecture file.
5. **Prove that it gives the same verdicts** in real time as after the turnaround, on the monthly test turnarounds, and
   look at what happens when a piece of video is lost.
6. **Measure it on the Fail turnarounds.** "It runs" is not "it is useful": a check can run perfectly and still catch no
   violation — the pushback path check caught none of the four labelled violations.

## How to see that it worked

Same verdicts as after the turnaround on the test turnarounds, the cost inside the budget, and a measured number of
violations caught.

## For developers

- The checklist of the Prime Flight workspace: `.claude/skills/pf-port-module/SKILL.md` (audit of passes over the video,
  pixels, own models, private tracker fields; the stage events; parity between whole-video and piece-by-piece runs).
- The worker: `dxgat/detectors/realtime-pipeline`, its `ARCHITECTURE.md`; the per-check readiness in `docs/04_modules.md`
  and `docs/analysis/rt_module_selection.md`; the cost in `docs/analysis/rt_module_cost.md`.
