# Real-time module selection v1

Date 2026-09-15. Question: which modules can run in the real-time branch at all, what each needs first, and what that
means for GM, the tracker, the stage detector and the event context.

Sources:
- `docs/04_modules.md` — stage window, decision type, streaming verdict;
- `docs/05_module_logic.md` — client rules and tiers;
- `docs/analysis/module_consumption.md` — passes, pixels, models, GM and tracker fields;
- `docs/analysis/module_compute/` — per-frame compute on the test-set checkouts, with file:line;
- batch cost from the test set: median ms per recorded frame on a loaded machine, a ranking only;
- real-time runs of a whole video (PF-Q1-19);
- fails from the monthly report (69 events).

## Criteria

A module runs in real time when:
1. it decides during the turnaround — at an event, a deadline or the end of a window — not from the whole recording;
2. it reads each metadata row once, in order (the real-time feed hands every row over once, so a second pass fails);
3. it needs the session length only at the end of the session (served by an end-of-session marker);
4. it fits the budget per active frame (≤ 10 ms, all modules of a stage ≤ 25 ms), now or after lightening through its gate
   (`tasks/notes/PF-Q2-11.md`).

## A — run as they are

Causal, one pass, pixel-free or light. They need stage gating and, where noted, the end-of-session marker or a small fix.

| module | decides at | client tier | ms per recorded frame | fails | before real time |
|---|---|---|---|---|---|
| beltloader-chocks | the aircraft departure (live run: the tracker's departure frame) | real-time | 2.7 (live 1.2) | 11 | — verified live, verdict and report identical; logs every detection from frame 1 (7.6 MB per run) |
| pushback-pathway-confirmed-clear-of-obstacles | around T_dep (live: 15 s after the departure frame) | real-time | 3.4 (live 1.6) | 3 | — verified live |
| conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed | departure confirmed (live: 11 s after) | streaming | 2.4 (live 2.4) | 4 | end-of-session marker for its fallback (reads `nframes` on every frame) — verified live |
| bl_rear_cone | BL in place and its window | real-time | 2.4 | 14 | logs every detection and track from frame 1 (14.1 MB per run) |
| cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked | BL leave → T_dep | real-time | 4.9 | 11 | rebuilds an ever-growing cone history into two unused arrays on every frame (`main.py:283-286`) |
| pushback-does-not-start-until-wing-walkers-are-in-place-and-ready | the pushback moving | streaming | 2.4 | 17 | uses the video's frame count in the decision → end-of-session marker; a module-level global persists across runs |
| 3-stop-brake-check | the BL stopped at the aircraft | streaming | 3.4 | 43 | — |
| cones-placed-in-proper-positions-and-timely | the end of the session | real-time | 2.3 | 2 | frame count in the decision → end-of-session marker; a deadline after T_ARR is a trigger change (PF-Q3-06) |
| chocks-and-cones-available-and-staged-for-arrival | T_arr | post | 1.4 | 24 | — |
| crew-present-10-minutes-prior-to-aircraft-arrival | T_arr | post | 1.2 | 25 | keeps processing 60 s after its verdict is fixed |
| all-cargo-bin-doors-opened-and-verified | a deadline after T_arr | post | 1.4 | 4 | — |

## B — run after a patch on stage events

Two passes today; the real-time feed cannot replay.

| module | why not now | patch | ms per recorded frame | fails |
|---|---|---|---|---|
| aircraft-chocks | pass 1 computes `median_pushback` over the whole event; `number_of_frames` as the end anchor; equality with the arrival / departure frames | PUSHBACK_ATTACHED, T_ARR, T_DEP from the stage detector; lazy frame reads; crops instead of per-wheel full-frame buffers (up to 81+81+16+16 frames) | 5.7 | main gear 19, nose gear 1, nose wheel 1 |
| pin-verification | pass 1 computes `median_pushback`; `number_of_frames`; serialises the whole plane state every frame | the same events; log four plane fields instead of the whole state | 3.9 | 12 |

## C — run after lightening

Causal, but they read pixels and run models. The heaviest items and the first steps that keep outputs identical (EXACT)
come from the compute inventory.

| module | heaviest per-frame work | first EXACT steps | ms per recorded frame | fails |
|---|---|---|---|---|
| safety-vests-secured-to-body | decodes every frame; 2 Swin-T classifiers and a ResNet-18 vest check per person; colour contours; a full-frame copy and an unused resize | drop the copy and the resize; batch the persons of a frame | 28.2 | 35 |
| gse-chocks | RTMPose-l and an effnet-b0 difference classifier per GSE track; full-frame buffers up to 24+8 per stationary GSE | read the frame once and only while a GSE is stationary; crops in buffers; the check image computed once | 6.1 | 22 |
| safety-handrails-fully-extended | reads and converts the full frame on every frame with a stopped BL but classifies every 8th | read only on classified frames; share the classifier call with handrails-on-gse (identical weights and crop) | 8.4 | 17 |
| steering-by-pass-pin-installed-or-steering-otherwise-bypassed | 200 raw frames buffered after arrival; up to 200 HRNet-W48 calls per stop | crops instead of frames; one HRNet-W48 loaded for four modules | 1.9 (much more per active frame) | 6 |
| fod-walk-completed | MoveNet per person per frame, unbatched (CPU onnxruntime in production) | MoveNet after the vehicle-occupant filter; no drawing on decoded frames | 3.0 | 49 |
| lead-marshaller-and-wing-walkers-in-position | HRNet-W48 with flip test on every approach frame, CLAHE on the full frame, a 96-frame buffer | shared HRNet; no full-frame copies; crops in the buffer | 5.7 | 49 |
| wing-walkers-in-proper-position-and-using-approved-wands | HRNet-W48 with flip test on every departure-window frame | shared HRNet; no full-frame copies | 3.2 | 15 |
| pre-arrival-safety-huddle | iterates the decoded video; pixel-based decision | no frame reads in the post-arrival tail | 1.9 | 52 |
| handrails-on-gse-being-used | full frame read from frame 1; handrail classifier, segmentation, a full-frame mask warp and one DWPose-l call per climber | read after the arrival / BL gates; shared classifier; single-channel mask warp; batching | 30.7 | 45 |

For every pixel module, the frame reader resizes each frame to 1280×768 and copies it, and the result is never used.
The real-time adapter still does this (`pf/rt/prod_module.py:168-171`). Removing it is EXACT.

## Not in real time (v1)

| module | why |
|---|---|
| hand-signals | RETHINK: pass 1 averages the door box over 60 s after arrival; 240-frame buffer; post tier |
| safety-zone-confirmed-clear | RETHINK: the zone is fitted in pass 1 up to T_arr and pass 2 re-reads 2 min with its own MobileSAM tracking; a causal zone is a trigger change (PF-Q3-06) |
| post-arrival-aircraft-walk-around-inspection-completed-accurately, pre-departure-walk-around-completed | POST by nature: whole-stage trajectories with SAM, depth and pose models; pre-departure costs 26 ms per recorded frame |
| hair-policy | obfuscated build (Pyarmor, Python 3.8), ≈0.9 CPU-s per frame, no source to port |
| seat-belts-used-on-all-gse-equipped-with-seat-belts | out of scope |

Result: 11 modules run as they are, 2 after a patch on stage events, 9 after lightening; 5 stay out of real time.

## What the selection means for the other components

**GM for real time (PF-Q2-02).**
- Groups A + B + C together use all 26 decision classes of the production GM. While the modules run unchanged, no class
  can be dropped.
- All three detector heads are needed:
  - the chock head: aircraft-chocks, beltloader-chocks, chocks-and-cones, gse-chocks, pushback-pathway, steering;
  - the vehicle head: aircraft-chocks, cones-are-removed, pin-verification, all-cargo;
  - `safety_vest` is read only by safety-vests.
- The "RT-GM ≈ 6 classes" idea in PF-Q2-02 would break these modules. The speed has to come from:
  - TensorRT: 8.0 ms for the three heads, L2 gate pending;
  - shared preprocessing;
  - batching across cameras.

**Tracker for real time.**
- Classes: airplane, beltloader, gse, person.
- The v1 `state_dict` fields have to stay on the bus for:
  - the optical-flow arrival block `_p0`, `_st`, `_of_dots_lifetime`, `_init_dots_lifetime` — aircraft-chocks,
    chocks-and-cones, crew-present, all-cargo, steering, fod-walk, lead-marshaller, huddle;
  - the GSE motion counters `_static_frames`, `_moving_frames`, `_stopping_time_thres`, `_display_proceeding_time_thres`
    — gse-chocks;
  - `_status`, `_obj_id`, `_color`, `_xyxy`.
- The 10.8× lighter v2 bus becomes possible once those modules take T_ARR from the stage detector instead of their local
  arrival block (PF-Q3-05).

**Stage detector (PF-Q1-03).**
- Gating for A + B + C needs these events:
  - session start;
  - T_ARR, with the deadlines derived from it: nose gear at 30 s, steering pin at 240 s;
  - BL_AT_DOOR, per belt loader;
  - BL_LEAVE, for the last belt loader;
  - PUSHBACK_ATTACHED;
  - the pushback moving and T_DEP;
  - T_DEP + 60 s;
  - the end of the session (marker).
- Look-back modules open at the previous stage with a margin:
  - conditioned-air from T_ARR, because it keeps whole-event hose history;
  - pushback-pathway from BL_LEAVE.
- Per-object events stay inside the modules in v1: a GSE stopped or gone, a worker off the belt loader.

**Event context (PF-Q2-14).**
- The camera type decides which checks run on which camera. In the client split:
  - aircraft: 12 checks on both cameras, 18 on the cone camera only;
  - jets: 3 checks on both, 13 on the cone camera only, 8 on the wing camera only.
- The aircraft type decides that split. beltloader-chocks and hand-signals recompute it locally.
- The test-set plan carries an aircraft type for only 23 of 69 events (14 jets, 9 aircraft).

## Order (proposal)

1. Group A on replayed production GM / tracker rows (already works for three modules), with stage gating and the
   end-of-session marker.
2. Group B once the stage detector serves PUSHBACK_ATTACHED.
3. Group C by value and cost:
   - first safety-vests: on for the whole session, 35 fails;
   - then gse-chocks, safety-handrails, steering, lead-marshaller, wing-walkers, fod-walk and huddle;
   - handrails-on-gse last.
