# How to measure a change on the monthly test

**For:** a CV engineer who changed the logic of a check, one of its models, or the General Model or the tracker in a way
that can change verdicts.

## What the monthly test is

Every month the client checks a set of turnarounds by hand and writes the correct verdict of every check. The latest
report we use has **69 turnarounds (90 videos)**. For every check and turnaround it holds the verdict production gave and
the correct one.

From it we compute, for every check:

- **accuracy** — in how many turnarounds the verdict was correct, out of all turnarounds the client labelled;
- **Fails caught** — how many of the turnarounds the client labelled Fail our check also called Fail.

The second number matters most for safety, and it is weak when the client labelled only one to three Fail turnarounds
for a check: then the accuracy number cannot show whether the check catches violations at all.

A turnaround filmed by both cameras gets one verdict per check: a Fail on either camera makes it Fail; otherwise a Pass
on either makes it Pass; Not observed only when both say so.

## Steps

1. **Run the current production version** of everything you changed on the monthly test turnarounds — this is the
   baseline. Run it on your machine, with the same inputs you will give the new version, so that the only difference is
   your change.
2. **Run the new version** on the same turnarounds with the same inputs and settings.
3. **Compare the two runs turnaround by turnaround.** List every turnaround where the verdict changed.
4. **Look at every changed verdict.** Open the video at the moment the check decided and write down why it changed and
   whether the new verdict matches the client's label.
5. **Compare both runs with the client's labels:** accuracy and Fails caught, before and after, per check.
6. **Write a research report** with the tables and every change explained. A change of what a verdict means goes to the
   client through the lead before production.

## How to see that it worked

You can say for every changed turnaround why it changed, and the accuracy and Fails caught are not lower — or, if they are
lower somewhere, the team has agreed that the gain is worth it.

## Common problems

| What you see | Why | What to do |
|---|---|---|
| the baseline does not equal the verdicts in the monthly report | the report was produced by an older version of the General Model, on another machine and environment | compare your two runs with each other first; compare with the report only for the labels |
| a turnaround is missing in one run | a run failed or its inputs were not there | a missing run is never "the same": rerun it |
| the accuracy changed although nothing should change | the tracker is random by itself | seed it, or run the baseline twice to see its own spread |

## For developers

The monthly test machinery in the Prime Flight workspace:

```bash
# the whole test set: inputs, the shared layers, every module on two input sets (control and new)
python scripts/testset/orchestrate.py
# a variant of the shared layers or of a module's own model, gated against the existing runs
python scripts/testset/variant_run.py --variant <name> --reuse-v2 --modules <module,...> --module-args "<flags>"
# verdicts per turnaround, against the report's labels and pairwise against a baseline run set
python scripts/testset/compare.py --runs-root out/testset/modules/<new> --label <new> \
    --baseline-root out/testset/modules/<base> --baseline-label <base> --out out/testset/compare_<new>_vs_<base>.json
```

The parsed monthly report is `out/testset/monthly_report_parsed.json`; the merge of the two cameras and the derived
"three-stop brake check and hand signals" task are in `scripts/testset/common.py`.
