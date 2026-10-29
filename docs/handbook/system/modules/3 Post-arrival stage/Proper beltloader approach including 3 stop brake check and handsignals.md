# Proper beltloader approach including 3 stop brake check and handsignals

*In plain words: belt loader approach: three brake stops and hand signals.*

> A belt loader is the vehicle with a conveyor that carries bags to the cargo door. When it drives up to the aircraft,
> it must stop three times to test its brakes, and a guide must lead it in with approved hand signals. This check has
> no module of its own: its verdict is put together from the verdicts of two other checks, *3 stop brake check* and
> *All GSE guided into aircraft using approved hand signals*.

## Status

| | |
|---|---|
| How accurate it is | 57 of 68 turnarounds correct (84 %) on the monthly test |
| Fail turnarounds it caught | 47 of 50 |
| In production | no module of its own: the verdict is combined from the two checks' verdicts |
| Who looks after it | to assign |
| Biggest open problem | The client's sheet gives no rule for this check, and the rule that combines the two verdicts is not written down anywhere we know: we read it from the monthly reports. |

## What the client wants

A verdict is the answer of a check: Pass, Fail or Not observed. The client's sheet lists this check in the stage after
the aircraft stops, but leaves its Pass, Fail and Not observed rules empty. It marks the check as not yet ready for
production, for the post-processing group (checks judged after the turnaround), on both cameras for aircraft and on the
wing camera for jets.

The rules of the two parts are on their own pages: *3 stop brake check* (every stopped belt loader made three stops
before the final one) and *All GSE guided into aircraft using approved hand signals*.

## How it decides

The verdict follows from the two parts:

| 3 stop brake check | Hand signals | This check |
|---|---|---|
| Pass | Pass | Pass |
| Not observed | Not observed | Not observed |
| any other pair | | Fail |

So one Fail of either part gives Fail, and so does one part that could not be judged while the other passed. We read
this rule from the monthly test reports: it holds on all 69 turnarounds, with no exception. Where it is computed — in
the website's backend, not in the computer-vision code — is to confirm.

## When and where it looks

When the two parts look: after the aircraft stops, while the belt loaders drive up to the doors, and during unloading.
It needs no pictures or models of its own.

## How accurate it is

The monthly test is the set of the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this
check. The combined verdict was right on 57 (84 %). 50 turnarounds were labelled Fail and 47 of them were caught; 8 of
the 11 wrong verdicts were Fail on turnarounds labelled Pass. Because a single failing part fails the whole check, its
errors are mostly the errors of the two parts added up.

## Known problems

- **No rule from the client.** The sheet leaves the rules of this check empty; the combination is our reading of the
  reports, to confirm with the client's safety team.
- **Not observed turns into Fail.** One part Not observed and the other Pass gives Fail, although nothing wrong was seen.
  Whether the client means this is to confirm.
- **Errors add up:** every wrong verdict of either part can make this one wrong.

## In real time

It follows its two parts: as soon as both have a verdict, this one is known. The client puts the three-stop part in its
streaming group and the hand-signal part in the post-processing group, so in practice this check is known after the
turnaround.

## For developers

- **Task key in the monthly report:** `stopbrake-and-handsignals`; parts `stopbrake` (module `3-stop-brake-check`) and
  `handsignals` (module `hand-signals`).
- **Combination rule:** `scripts/testset/common.py` `derive_stopbrake_handsignals` (`DERIVED`), inferred from the
  reports' "New output" column on 69 events, no exception. The real-time worker lists it in
  `external/realtime-pipeline/module_rules.json` (`postArrival`, cameras wing and cone).
- **Sources:** `docs/05_module_logic.md` (row "composite: hand-signals + 3-stop-brake-check"), the two parts' pages.
