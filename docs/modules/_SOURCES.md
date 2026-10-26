# Production versions of the modules (2026-10-26)

Which code each module page documents. "Branch exports" are copies of a branch checked out for the test set; the test
set chose them by matching the monthly report's production output ("New output"), so they are the deployed lines.
Paths are relative to `G:\prime_flight\external\`.

| ID | Module repository | Production line | Code to read | Evidence |
|---|---|---|---|---|
| M06 | chocks-and-cones-available-and-staged-for-arrival | not_observed_logic @ 2b4fca9 | `_branches/chocks-and-cones-available-and-staged-for-arrival@not_observed_logic` | test-set calibration |
| M10 | crew-present-10-minutes-prior-to-aircraft-arrival | main @ 5cfd25c | `crew-present-10-minutes-prior-to-aircraft-arrival` | default branch |
| M11 | fod-walk-completed | dev @ a30826f | `_branches/fod-walk-completed@dev` | test-set calibration |
| M18 | pre-arrival-safety-huddle | green_cone_median @ a1210c5 | `_branches/pre-arrival-safety-huddle@green_cone_median` | test-set calibration (4/5) |
| M23 | safety-vests-secured-to-body | tdv_cone @ 8f58d7e | `_branches/safety-vests-secured-to-body@tdv_cone` | test-set calibration (3/3) |
| M24 | safety-zone-confirmed-clear | master @ 91676a5 | `safety-zone-confirmed-clear` | default branch |
| HP | hair-policy | master @ 8a343bf (to confirm; a `python_3_10` branch exists) | `hair-policy` | default branch |
| M02A, M02B, M02C | aircraft-chocks | master @ fa00478 | `aircraft-chocks` | test-set calibration (newer branch is feature work) |
| M09 | cones-placed-in-proper-positions-and-timely | not_observed_logic @ d2a6898 | `_branches/cones-placed-in-proper-positions-and-timely@not_observed_logic` | test-set calibration (8/8) |
| M26 | steering-by-pass-pin-installed-or-steering-otherwise-bypassed | master @ 60dca73 | `steering-by-pass-pin-installed-or-steering-otherwise-bypassed` | test-set calibration (newer branch is feature work) |
| M15 | lead-marshaller-and-wing-walkers-in-position | pre_arrival_departure @ 9e1a9f0 | `_branches/lead-marshaller-and-wing-walkers-in-position@pre_arrival_departure` | test-set calibration (8/8) |
| M05 | bl_rear_cone | main @ 12429f5 | `bl_rear_cone` | default branch |
| M13 | hand-signals | master @ 60c0faf | `hand-signals` | default branch |
| M17 | post-arrival-aircraft-walk-around-inspection-completed-accurately | tdv_cone @ a0d9ee4 | `_branches/post-arrival-aircraft-walk-around-inspection-completed-accurately@tdv_cone` | test-set calibration |
| M01 | 3-stop-brake-check | master @ 14685f4 | `3-stop-brake-check` | default branch |
| M03 | all-cargo-bin-doors-opened-and-verified | bl_approach @ 3422bdc | `_branches/all-cargo-bin-doors-opened-and-verified@bl_approach` | test-set calibration (carries production fixes) |
| M12 | gse-chocks | per_component_improvement @ d3f92a5 | `_branches/gse-chocks@per_component_improvement` | test-set calibration |
| M14 | handrails-on-gse-being-used | per_component_improvement @ f2c4793 | `_branches/handrails-on-gse-being-used@per_component_improvement` | test-set calibration |
| M22 | safety-handrails-fully-extended | master @ 8b9a2a9 | `safety-handrails-fully-extended` | default branch |
| M04 | beltloader-chocks | master @ 7056099 | `beltloader-chocks` | default branch |
| M07 | conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed | new_logic @ 960bfe1 | `_branches/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed@new_logic` | test-set calibration (carries production fix) |
| M08 | cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked | main @ e2a25ba | `cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked` | default branch |
| M16 | pin-verification | master @ 8e1863c | `pin-verification` | default branch |
| M19 | pre-departure-walk-around-completed | tdv_cone @ e407de2 | `_branches/pre-departure-walk-around-completed@tdv_cone` | test-set calibration |
| M20 | pushback-does-not-start-until-wing-walkers-are-in-place-and-ready | obstruction_plane_track @ 6979d19 | `_branches/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready@obstruction_plane_track` | test-set calibration (8/8) |
| M21 | pushback-pathway-confirmed-clear-of-obstacles | master @ 104db85 | `pushback-pathway-confirmed-clear-of-obstacles` | default branch |
| M27 | wing-walkers-in-proper-position-and-using-approved-wands | obstruction_hand_signals @ 3460afc | `_branches/wing-walkers-in-proper-position-and-using-approved-wands@obstruction_hand_signals` | test-set calibration (5/5) |

Shared models:

| | Production version | Code to read |
|---|---|---|
| General Model | `pf/q4-02-gm-exact-speedups-a0157a4` built as b6e1a3e (a0157a4 + the exact speed-ups + image fixes), in production since October 2026 | `_pins/general_model` |
| Trackers | cv_trackers bd43c3c | `cv_trackers_prod` (+ `cv_common` at ac5098d; production pins may differ) |
