# Where the module code differs from the client rules

*26 October 2026 · Computer-vision team (code review); confirmation: the module owners · Status: in progress; findings
from reading the code, each still to be confirmed*

## In short

We read the production code of all 27 checks, the General Model and the tracker, and compared every step with the rules
the client wrote. In 26 checks the code differs from the rule somewhere; the 27th, hair policy, cannot be read. Many
differences can change the verdict the client sees. In several checks a blocked view gives Fail instead of Not observed;
two checks never look for something the rule names (the lead marshaller, the wing walkers' wands); the pushback path
check caught none of 4 known violations. Each finding will be confirmed on a labelled turnaround; anything that
changes a verdict the client sees is the client's decision.

## The question

For every check the client wrote a rule: when the verdict is Pass, Fail, Not observed, and Not observed because the view
is blocked (by a vehicle or an object in front of the camera). The module is the code of one check. Does the code that
runs in production do what the rule says?

Words used on this page: a **turnaround** is the whole servicing of an aircraft at the gate; a **frame** is one picture
of the video (8 per second); a **verdict** is Pass, Fail or Not observed; the **monthly test** is the set of the
client's validated turnarounds we measure on.

## What we did

On 26 October 2026 we read the production version of every module, the General Model (the shared detector) and the
tracker (which follows each object from frame to frame), and compared each step with the client's rule.

## What we found

### Before the aircraft arrives

| Check | What the code does differently | What it can mean for the verdict |
|---|---|---|
| Chocks and cones available and staged for arrival | Its arrival detector (shared with two other checks) counts a part before arrival when the aircraft first appears after 11.25 seconds of video; its comment says 90 seconds. Pass is decided before the aircraft is checked. A view blocked from the side has no rule | Pass or Fail where Not observed may be meant |
| Crew present 10 minutes prior to aircraft arrival | If no person is ever detected, it gives Fail before checking for a blocked view or the 4-minute minimum. The handling for short videos never runs | Fail where the rule says Not observed |
| FOD walk completed | Follows people only until the aircraft first appears; never checks that the marked area the aircraft drives into is visible | A later walk is missed: Fail although it was done |
| Safety huddle conducted at huddle cone | Judges the cone's green by a red-against-green value and the box shape, not by the client's colour measure and minimum size. Pass and Not observed use different arrival rules | A cone may be judged wrongly; a real huddle can end as Fail (to confirm) |
| Employees wearing safety vests secured to body | A vest's status is overwritten at every look, so "open, then closed" ends as closed. Any followed person counts towards Pass, even with an unread vest. Dark or small vests cannot fail. No blocked-view rule | Pass where the rule gives Fail |
| Safety zone confirmed clear | The last 30 seconds or so before the aircraft stops are not checked (the rule: the last 2 minutes). Not observed follows a different rule than the client's | A vehicle in the zone in those seconds is missed: Pass instead of Fail |
| Hair policy | A scrambled build that cannot be read | Unknown |
| Lead marshaller and wing walkers in correct position | The lead marshaller (who guides the aircraft in) and the wands (lighted batons) are never checked. Walkers must be present for 90 seconds, not 10 minutes | Pass without a lead marshaller or wands |

### Arrival

| Check | What the code does differently | What it can mean for the verdict |
|---|---|---|
| Nose gear chocks applied immediately | One condition counts 30 seconds from the start of the video instead of from the arrival; probably a slip | To confirm |
| Main gear chocks removed only after aircraft is attached to pushback (the pushback is the tractor that pushes the aircraft back) | Also waits for the belt loaders (conveyor vehicles for the bags) to leave, which the rule does not ask | Chocks removed after the attachment but before the belt loaders left: Fail instead of Pass |
| Nose wheel chock removed from aircraft | Pass means "still seen after the attachment"; the rule's Fail "the video stops before the removal" is missing | A chock visible until the end: Pass instead of Fail |
| Cones placed in proper positions and timely | Neither the time nor the position is checked, only the kind of cone. The jet rules never apply (the code expects "jet" in small letters; to confirm) | Late or misplaced cones still Pass |
| Steering by-pass pin installed, or steering otherwise bypassed | The client's conditions on the chocks and on obstacles are not implemented | A blocked view can give Fail instead of Not observed |

### After the aircraft stops

| Check | What the code does differently | What it can mean for the verdict |
|---|---|---|
| Beltloader rear cone positioned after BL is in place | Needs the cone for 10 seconds in a row (the rule: 100 frames, 12.5 seconds, in total); one frame without it restarts the count. No blocked-view rule | A cone seen in pieces gives Fail |
| All GSE guided into aircraft using approved hand signals | The blocked-view rule is switched off. The filter that should leave out the vehicle's driver practically never runs | A blocked view gives Pass or Fail; the driver can count as the guide |
| Post-arrival aircraft walk around inspection completed accurately | Stops with an error when the aircraft never stops | No verdict instead of Not observed |
| 3 stop brake check | Reversing is never checked. Any stop of 3 seconds or more restarts a loader's stop count, so a long brake-check stop wipes the earlier ones | A correct loader with one long stop can get Fail (to confirm) |

### Unloading and loading

| Check | What the code does differently | What it can mean for the verdict |
|---|---|---|
| All cargo bin doors opened and verified | The blocked-view check never fires: it is called without the camera settings it needs. An extra "no part before arrival" case uses 11.25 seconds where its comment says 90 | A blocked view gives Fail instead of Not observed |
| Motorized GSE parked and properly chocked | The aircraft is never used, so every parked vehicle in view counts. A worker bending counts as chocking from every side, not only from the front. The client's rule has no Fail condition | A bend beside a side-on vehicle can give Pass; Fail needs a definition |
| Handrails on GSE being used | No blocked-view rule. Without the pose model, a hand on the rail is credited to every worker seen on the belt loader in the last 2.5 seconds | A worker who does not hold the rail can pass with a colleague who does |
| Safety handrails fully extended and used | Checks only that the handrails are extended, not used. The rule's "8 minutes" is written as 480 frames, which is 60 seconds, as in the code | Belt loaders seen for 1–8 minutes are judged; the client should say which was meant |
| Belt loader forward chock remained in place until unit is backed up clear of aircraft | Once seen chocked, a loader stays chocked; obstacles do not change the verdict | A chock removed early still gives Pass |

### Before departure

| Check | What the code does differently | What it can mean for the verdict |
|---|---|---|
| Conditioned air removed 10 mins prior to departure and properly stowed | "Properly stowed" is never checked: a hose away from the aircraft, or not seen, counts as removed. For jets one test compares a horizontal box edge with a vertical one, probably a slip | Pass for a hose that was not stowed; some jet verdicts may be wrong (to confirm) |
| Cones are removed only after all GSE is clear of A/C and chocked | Chocks are never checked, and "all service vehicles" means belt loaders only. Cones still visible at departure give Pass. The rule's Not observed cases (cones seen under 200 frames, view blocked over 65 %) are missing | Pass when the cones were never removed |
| Pushback operator verifies steering bypass pin installation | Needs 1.5 seconds of bending or 2.5 seconds of standing with a raised hand (the rule: 0.5 and 3 seconds) | Short bends do not count: Fail instead of Pass |
| Pre-departure walk around completed | No workers seen gives Fail; the blocked-view rule is switched off; it looks 8 minutes back, not 5 | Fail instead of Not observed |
| Pushback does not start until wing walkers are in place and ready | The right-side test compares a horizontal position with the aircraft box's top edge, probably a slip that makes it almost always true. It checks walking along after the start, not readiness before | A missing right-side walker may still give Pass (to confirm) |
| Pushback pathway confirmed clear of obstacles | Keeps only the first crossing; if that was more than 15 seconds before departure, the verdict becomes Pass. People are not checked; a chock must be under 25 × 5 pixels to count. **Measured: 0 of 4 known violations caught** | Pass with obstacles on the path |
| Wing walkers in proper position and using approved wands | Wands are never detected, although the report says "approved wands". A hand signal is a wrist at or above the elbow for about 1 second | Pass without wands; any raised arm counts |

### The shared parts

- **General Model.** The stage field of its report is always empty, and the job could crash when it finds an aircraft
  nose but no wing.
- **Tracker.** The camera type is never passed in, so wing camera videos get the cone camera's rules for which cargo
  door a belt loader serves.
- Both report "processed" before their upload ends; whether the next job can start too early is to confirm.

## What it means

- **Both directions.** Some differences make the system more lenient than the rule (safety vests, wands, cones, the
  pushback path): violations can pass unseen. Others make it stricter (crew present, the pin
  check, the three-stop brake check): the client can see a Fail that was not one.
- **A blocked view often becomes Fail**, so a camera's bad view is reported as the crew's violation.
- **A high accuracy does not mean violations are caught.** The pushback path check is right on 61 of 68 turnarounds of
  the monthly test, but caught none of the 3 labelled Fails.
- **Some rules are themselves unclear** (the handrails "8 minutes", vehicle chocks without a Fail); only the client
  can settle them.

## What is next

1. **Confirm or reject.** The module owners check each finding on one labelled turnaround (the monthly test has Fail
   labels for some checks).
2. **The client decides** on any finding that changes a verdict the client sees, through the client's safety team, as
   for the rules on the October slides. Nothing is fixed silently.
3. **Track and fix.** Confirmed bugs go to the team's issue tracker; the module pages follow the fixes.

## For developers

- Source `docs/analysis/module_review_2026-10.md`; pages `docs/modules/`.
- Table order → codes: M06, M10, M11, M18, M23, M24, HP, M15; M02A, M02B, M02C, M09, M26; M05, M13, M17, M01; M03, M12,
  M14, M22, M04; M07, M08, M16, M19, M20, M21, M27.
- Code places: arrival detector `plane_arrival_detector.py:77` (90 frames; M06, M11, M18); M03 `camera_config=None`
  (`main.py:420-421`); M02A `installed_no`; M09 `jet` vs `JET`; M07 `main.py:520` (full rewrite); M08 `break`
  (`main.py:298`), hidden-cone IoU > 0.7; M13 person id 0; M14 `pretrained=True`; M15 no mmpose in the Dockerfile; M16
  non-causal first pass; M17 July 2026 commits: to confirm; M19 pin lacks `cv_common.modules`; M20 `main.py:179`; M21
  `main.py:479-482`; M27 `main.py:810`; HP Pyarmor, CPython 3.8 only, production build to confirm.
- GM: crash `main.py:728`, `stages` null. Trackers: pinned cv_common `ac5098d`
  vs `tracker_optimization` (≈ `2759daf`, image to confirm); `cone_camera` not passed (`model_starter.py:166`).
