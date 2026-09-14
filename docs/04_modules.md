# Modules (M01–M27) and pipeline repositories (U01–U05)

A merge of three sources: the architecture review (inputs/outputs/attention/local policy), the code audit for streaming (`streaming_ref/module_map.json`: stage/opens/closes/decision/verdict) and the client xlsx (tier, cameras, ProdReady). Pass/Fail logic — in `05_module_logic.md`.

Verdict legend (streaming readiness): NOW = streams without code changes · NOW_PX = without changes, but needs frames · PATCH = 3-hunk fix as in aircraft-chocks · RETHINK = two-pass, the first pass determines the geometry · POST = in essence post-processing.

Tier (client split, xlsx Edge-Friendly/Post analytics/Streaming): real-time · streaming · post.


## Pre-arrival

### M06 · Chocks and cones available and staged for arrival
- **Repo**: [chocks-and-cones-available-and-staged-for-arrival](https://gitlab.com/dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival) · local `external\chocks-and-cones-available-and-staged-for-arrival` (read-only clone) · pinned `1413225f`
- **Tier / cameras / ProdReady**: post · Aircraft=Cone, Jet=Cone · ProdReady=True
- **Streaming audit**: stage=PRE_ARR · opens="start of the stream" → closes="T_arr" · decision=LOOKBACK · preventive=False · passes=1, pixels=0, models=0 · deps=tracker · **verdict=NOW**
  - why: Counts frames with cones/chocks in pre-arrival; verdict at T_arr. The module runs from the start of the stream and stops at T_arr — after that it has nothing to do.
- **Components**: E01, E04, E05, E07
- **Inputs**: GM cones/chocks and transport/obstacles; aircraft tracks/motion; metadata sufficient for central counting logic.
- **Outputs**: Staged-equipment compliance result/report/timeline.
- **Local policy**: Count ground chocks and cones before arrival; exclude transport-carried chocks and apply the count, duration and visibility rules locally.
- **Attention**: YAML 6/4 counts are not the active main-code 7/6 counts. Do not assume every configuration value controls behavior.

### M10 · Crew present 10 minutes prior to aircraft arrival
- **Repo**: [crew-present-10-minutes-prior-to-aircraft-arrival](https://gitlab.com/dxgat/detectors/crew-present-10-minutes-prior-to-aircraft-arrival) · local `external\crew-present-10-minutes-prior-to-aircraft-arrival` (read-only clone) · pinned `5cfd25c9`
- **Tier / cameras / ProdReady**: post · Aircraft=Cone, Jet=Cone · ProdReady=True
- **Streaming audit**: stage=PRE_ARR · opens="start of the stream" → closes="T_arr" · decision=LOOKBACK · preventive=False · passes=1, pixels=0, models=0 · deps=tracker · **verdict=NOW**
  - why: A 12-min window before T_arr, threshold 80 frames with ≥3 people. Verdict at T_arr. To shout BEFORE arrival an ETA from the schedule is needed, which the contract does not have.
- **Components**: E01, E06, E07
- **Inputs**: GM person counts and transport obstacles; aircraft arrival/motion; clip start time.
- **Outputs**: One result/report/timeline based on crew exposure in the eligible window.
- **Local policy**: Choose the arrival-relative crew window and test person-count exposure, including short-video handling.
- **Attention**: This measures counts over a window, not continuous presence of the same three named workers for ten minutes.

### M11 · FOD walk completed
- **Repo**: [fod-walk-completed](https://gitlab.com/dxgat/detectors/fod-walk-completed) · local `external\fod-walk-completed` (read-only clone) · pinned `b923b5c8`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Cone, Jet=Cone · ProdReady=True
- **Streaming audit**: stage=PRE_ARR · opens="start of the stream" → closes="T_arr" · decision=LOOKBACK · preventive=False · passes=1, pixels=3, models=1 · deps=tracker · **verdict=NOW_PX**
  - why: ROI coverage by the walk up to stop_frame. Causal at T_arr, but this is a question about a completed procedure — real time adds nothing except a faster report.
- **Components**: E01, E11, E19, E07 (+proposed: E12, E13)
- **Inputs**: Pixels; worker tracks, GM aircraft/front wheel/parts and vehicle detections; approach trajectory.
- **Outputs**: One result/report/timeline.
- **Local policy**: Decide whether a qualifying worker path crosses the inspection corridor before arrival.
- **Attention**: Not the simple horizontal-crossing rule in the basic description; bbox-derived scale is not calibrated physical distance.

### M18 · Safety huddle conducted at huddle cone
- **Repo**: [pre-arrival-safety-huddle](https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle) · local `external\pre-arrival-safety-huddle` (read-only clone) · pinned `5c8a7599`
- **Tier / cameras / ProdReady**: post · Aircraft=Cone, Jet=Cone · ProdReady=True
- **Streaming audit**: stage=PRE_ARR · opens="start of the stream" → closes="T_arr" · decision=LOOKBACK · preventive=False · passes=1, pixels=4, models=0 · deps=tracker · **verdict=NOW_PX**
  - why: Huddle before arrival; verdict at T_arr. Four accesses to the frame, no networks of its own.
- **Components**: E01, E21, E06, E07
- **Inputs**: Pixels; GM cones and big vehicles, worker/aircraft tracks, cone-relative perspective ROI and arrival observation.
- **Outputs**: One huddle result/report/timeline.
- **Local policy**: Count workers near the green cone and require a sustained gathering before arrival.
- **Attention**: Pinned cv_common ac5098d lacks imported PlaneArrivalDetector. A candidate implementation exists at cv_common 2759daf, not at the reviewed pin.

### M23 · Employees wearing safety vests secured to body
- **Repo**: [safety-vests-secured-to-body](https://gitlab.com/dxgat/detectors/safety-vests-secured-to-body) · local `external\safety-vests-secured-to-body` (read-only clone) · pinned `ae8ef164`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Both, Jet=Both · ProdReady=True
- **Streaming audit**: stage=ALL · opens="start of the stream" → closes="end of the stream" · decision=INSTANT · preventive=True · passes=1, pixels=6, models=4 · deps= · **verdict=NOW_PX**
  - why: frame_unzipped → Fail immediately. The reference example of the instant type. But the most expensive: iterates the video directly, vest classifier + pose. The only module without stage anchors — lives the whole event.
- **Components**: E11, E22
- **Inputs**: Pixels; GM vest/person boxes and worker tracks; no turnaround stage required by the core rule.
- **Outputs**: One result; person dictionary nonempty without final unzipped states returns Pass; no associated workers returns Not observed.
- **Local policy**: Apply per-worker vest rules and aggregate worker results. Keep the current unknown-state limitation visible.
- **Attention**: No keypoint pose despite the model name. Current unknown/undefined workers can coexist with Pass; do not silently strengthen semantics during extraction.

### M24 · Safety zone confirmed clear
- **Repo**: [safety-zone-confirmed-clear](https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear) · local `external\safety-zone-confirmed-clear` (read-only clone) · pinned `91676a55`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Cone, Jet=Cone · ProdReady=True
- **Streaming audit**: stage=PRE_ARR · opens="T_arr − 2 min" → closes="T_arr" · decision=LOOKBACK · preventive=False · passes=2, pixels=4, models=1 · deps=tracker · **verdict=RETHINK**
  - why: The first pass approximates the front-wheel trajectory over the 120 s before the stop and builds the zone. At T_arr this trajectory is already in the buffer — the zone can be built causally. The two-pass structure here is an implementation artefact. The real-time value is the highest of all; becomes preventive only with trajectory prediction.
- **Components**: E01, E19, E08, E04, E07
- **Inputs**: Pixels; aircraft/front-wheel/cone detections and approach tracks; transport/person detections and motion masks.
- **Outputs**: One result; unknown if uncertain exposure exceeds passing exposure, otherwise Pass absent enough violations.
- **Local policy**: Test moving transport and cone conditions inside the safety zone before arrival; apply violation and unknown-coverage rules locally.
- **Attention**: Upstream tracker does not cover every transport class currently tracked here. FOD and safety-zone ROIs are related but not identical.


## Arrival

### M02A · Nose gear chocks applied immediately
- **Repo**: [aircraft-chocks](https://gitlab.com/dxgat/detectors/aircraft-chocks) · local `external\aircraft-chocks` (read-only clone) · pinned `fa00478f`
- **Tier / cameras / ProdReady**: real-time · Aircraft=Cone, Jet=Cone · ProdReady=True
- **Streaming audit**: stage=PRE_DEP · opens="T_arr" → closes="pushback attached → chock removal" · decision=EVENT · preventive=True · passes=2, pixels=1, models=1 · deps=tracker, pushback_attached · **verdict=PATCH**
  - why: The second pass knows median_pushback in advance. main_stream.py — 3 hunks, 0 discrepancies on Main gear. The right place for pushback_attached is the stage detector, not the module.
  - measured: Main gear 0 batch↔stream discrepancies on 8 videos; Nose wheel anchor shift −7…−444 s
- **Components**: E01, E03, E14, E07
- **Inputs**: GM front-wheel/chock/obstacle observations; aircraft stop time and arrival-stage visibility.
- **Outputs**: Result[0]: front_placed, with its own report and timeline.
- **Local policy**: Check nose-gear chock evidence within the arrival deadline. No pushback or rear-wheel comparison prerequisite.
- **Attention**: Placement is assessed within 30 seconds of aircraft stop. Pushback attachment and rear-wheel image differences are not prerequisites for this task.

### M09 · Cones placed in proper positions and timely
- **Repo**: [cones-placed-in-proper-positions-and-timely](https://gitlab.com/dxgat/detectors/cones-placed-in-proper-positions-and-timely) · local `external\cones-placed-in-proper-positions-and-timely` (read-only clone) · pinned `b2c53f69`
- **Tier / cameras / ProdReady**: real-time · Aircraft=Both, Jet=Both · ProdReady=True
- **Streaming audit**: stage=ARR_POST · opens="T_arr" → closes="T_arr + time limit" · decision=DEADLINE · preventive=True · passes=1, pixels=0, models=0 · deps=tracker · **verdict=NOW**
  - why: "Timely" — a deadline after the aircraft stops. Fail exactly at the moment the limit has passed without cones.
- **Components**: E01, E03, E04, E07
- **Inputs**: GM typed wing/engine/tail cones, aircraft and transport obstacles; camera/aircraft type.
- **Outputs**: One policy; normal return also contains counters/stage data (five values versus three on early paths).
- **Local policy**: Choose required cone roles for this camera and aircraft, then apply their count and exposure requirements.
- **Attention**: Obstacle report text says 40% while code tests 65%; inconsistent return arity requires an explicit legacy adapter.

### M26 · Steering by-pass pin installed, or steering otherwise bypassed
- **Repo**: [steering-by-pass-pin-installed-or-steering-otherwise-bypassed](https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed) · local `external\steering-by-pass-pin-installed-or-steering-otherwise-bypassed` (read-only clone) · pinned `60dca736`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Cone, Jet=- · ProdReady=True
- **Streaming audit**: stage=ARR_POST · opens="T_arr" → closes="T_arr + 240 s" · decision=DEADLINE · preventive=True · passes=1, pixels=1, models=2 · deps=tracker · **verdict=NOW_PX**
  - why: The pin must appear within a 240 s window after the stop. Fail at the moment the window has passed. Pixels unconditional (the finger analyser takes the frame).
- **Components**: E01, E03, E24, E07 (+proposed: E12, E13)
- **Inputs**: Pixels; workers, aircraft/front wheel, obstacles and arrival state; camera-specific wheel ROI.
- **Outputs**: One installation result/report/timeline.
- **Local policy**: Accept installation-like actions within the arrival-relative window. Do not add an unimplemented chocking prerequisite.
- **Attention**: Distinct learned installation task from heuristic pin verification. Chock detections are collected but do not establish chocking prerequisite.

### M15 · Lead marshaller and wing walkers in correct position
- **Repo**: [lead-marshaller-and-wing-walkers-in-position](https://gitlab.com/dxgat/detectors/lead-marshaller-and-wing-walkers-in-position) · local `external\lead-marshaller-and-wing-walkers-in-position` (read-only clone) · pinned `9b37ccff`
- **Tier / cameras / ProdReady**: real-time · Aircraft=Cone, Jet=Cone · ProdReady=False
- **Streaming audit**: stage=PRE_ARR · opens="start of the stream" → closes="T_arr" · decision=LOOKBACK · preventive=False · passes=1, pixels=0, models=0 · deps=tracker · **verdict=NOW**
  - why: ≥2 walkers, left and right, in the pre-arrival window. Verdict at T_arr.
- **Components**: E01, E03, E11, E07
- **Inputs**: GM aircraft parts/people/obstacles and aircraft/worker tracks; arrival motion.
- **Outputs**: One role-position result/report/timeline.
- **Local policy**: Check arrival-period paths and opposite-side coverage. Lead-marshaller gestures are not verified by the active code.
- **Attention**: No separate pose/wand model or lead-marshaller signal proof on the active path.


## Post-arrival

### M05 · Beltloader rear cone positioned after BL is in place
- **Repo**: [bl_rear_cone](https://gitlab.com/dxgat/detectors/bl_rear_cone) · local `external\bl_rear_cone` (read-only clone) · pinned `d75f1f8b`
- **Tier / cameras / ProdReady**: real-time · Aircraft=Both, Jet=Wing · ProdReady=False
- **Streaming audit**: stage=DOWNLOAD · opens="BL next to the aircraft" → closes="BL confirmed in place" · decision=EVENT · preventive=True · passes=1, pixels=0, models=0 · deps=tracker, bl_track · **verdict=NOW**
  - why: cone_registered after the BL has stopped. The same skeleton as beltloader-chocks.
- **Components**: E09, E04
- **Inputs**: GM cones/doors/aircraft parts; BL tracks and role/view context.
- **Outputs**: One result; all confirmed eligible BL visits must be coned.
- **Local policy**: Choose the region behind each qualified parked loader and require enough cone presence during the visit.
- **Attention**: Checklist and code thresholds differ; preserve code behavior as the migration baseline, then approve requirement changes separately.

### M13 · All GSE guided into aircraft using approved hand signals
- **Repo**: [hand-signals](https://gitlab.com/dxgat/detectors/hand-signals) · local `external\hand-signals` (read-only clone) · pinned `6bd027f2`
- **Tier / cameras / ProdReady**: post · Aircraft=Both, Jet=Wing · ProdReady=False
- **Streaming audit**: stage=ARR_POST · opens="T_arr" → closes="GSE pulled up to the door" · decision=EVENT · preventive=False · passes=2, pixels=4, models=0 · deps=tracker, bl_track · **verdict=RETHINK**
  - why: The first pass averages the door position over the event. Semantically the door is stable a few seconds after T_arr — the geometry can be fixed causally. The implementation has to change, the semantics does not.
- **Components**: E09, E13, E15, E07 (+proposed: E12)
- **Inputs**: Pixels; workers/BL/aircraft tracks, doors and obstacle detections; stop episodes and view/layout.
- **Outputs**: One result over observable eligible BL visits; unobservable visits can be omitted when others qualify.
- **Local policy**: Select the helper and pre-stop signal window for each loader visit, then apply the raised-arm duration rule.
- **Attention**: Raised wrists are a coarse gesture proxy, not an approved signal vocabulary. Same HRNet checkpoint as steering does not imply same crop preprocessing.

### M17 · Post-arrival aircraft walk around inspection completed accurately
- **Repo**: [post-arrival-aircraft-walk-around-inspection-completed-accurately](https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately) · local `external\post-arrival-aircraft-walk-around-inspection-completed-accurately` (read-only clone) · pinned `a0d9ee4f`
- **Tier / cameras / ProdReady**: post · Aircraft=Cone, Jet=- · ProdReady=False
- **Streaming audit**: stage=ARR_POST · opens="T_arr" → closes="end of the walk-around" · decision=WHOLE · preventive=False · passes=1, pixels=2, models=2 · deps=tracker · **verdict=POST**
  - why: Coverage over the whole event. Partial coverage is not a partial answer — the question makes no sense before the end of the walk-around.
- **Components**: E01, E09, E18, E07 (+proposed: E12, E11, E03)
- **Inputs**: Pixels, workers/BL/aircraft tracks and aircraft-part detections; camera/layout and arrival/loading gates.
- **Outputs**: Result, report/timeline and technical evidence (canvases/CSV/JSON).
- **Local policy**: Choose the post-arrival inspection window and apply the arrival-specific walk score and coverage rules.
- **Attention**: Post-arrival rescue/outlier options are disabled by default. Score-derived confidence is not demonstrated calibrated probability; required cached geometry must exist.

### M01 · 3 stop brake check
- **Repo**: [3-stop-brake-check](https://gitlab.com/dxgat/detectors/3-stop-brake-check) · local `external\3-stop-brake-check` (read-only clone) · pinned `3a2337c1`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Both, Jet=Wing · ProdReady=False
- **Streaming audit**: stage=DOWNLOAD · opens="beltloader appeared" → closes="BL stopped next to the aircraft (intersection > 0.2)" · decision=EVENT · preventive=False · passes=1, pixels=0, models=0 · deps=tracker, bl_track · **verdict=NOW**
  - why: The stop counter is final at the moment the BL has parked next to the aircraft. Not "after the first stop" — one cannot shout earlier, because it may still stop again. Alert at the moment of parking: immediate feedback, not prevention.
- **Components**: E03, E08, E09, E07
- **Inputs**: GM aircraft/doors/BL/obstacles; BL tracks with optical-flow points, movement state and identity; view configuration.
- **Outputs**: One Pass/Fail/Not observed result plus report/timeline; any failed eligible loader causes failure.
- **Local policy**: Count confirmed stops during an eligible approach; handle reverse/reset behavior and aggregate loader visits locally.
- **Attention**: Do not replace its recomputed status with generic tracker status without replay comparison; seconds vary with configured FPS.


## Download

### M03 · All cargo bin doors opened and verified
- **Repo**: [all-cargo-bin-doors-opened-and-verified](https://gitlab.com/dxgat/detectors/all-cargo-bin-doors-opened-and-verified) · local `external\all-cargo-bin-doors-opened-and-verified` (read-only clone) · pinned `ac2707cb`
- **Tier / cameras / ProdReady**: post · Aircraft=Both, Jet=Wing · ProdReady=True
- **Streaming audit**: stage=DOWNLOAD · opens="T_arr" → closes="end of the stage or 480 frames of open doors" · decision=DEADLINE · preventive=False · passes=1, pixels=0, models=0 · deps=tracker · **verdict=NOW**
  - why: Pass as soon as the doors have been open for 60 s in a row; Fail if this has not happened by the end of the stage. Causal.
- **Components**: E01, E03, E07
- **Inputs**: GM front/back door, main aircraft and transport/obstacles; aircraft motion state and camera view.
- **Outputs**: One result/report/timeline.
- **Local policy**: Select the camera-relevant cargo door and test its visible exposure in the eligible arrival window.
- **Attention**: Does not verify a BL target-door relationship or independently distinguish mechanical open/closed state beyond detector-label semantics.


## Upload

### M12 · Motorized GSE parked and properly chocked
- **Repo**: [gse-chocks](https://gitlab.com/dxgat/detectors/gse-chocks) · local `external\gse-chocks` (read-only clone) · pinned `3160b871`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Both, Jet=Wing · ProdReady=False
- **Streaming audit**: stage=DOWNLOAD · opens="GSE stopped next to the aircraft" → closes="GSE drove away" · decision=EVENT · preventive=True · passes=1, pixels=2, models=1 · deps=tracker · **verdict=NOW_PX**
  - why: is_chocked after each GSE stops. video_last_frame only trims the timeline — it takes no part in the decision. 1568 lines.
- **Components**: E08, E13, E14, E07 (+proposed: E12, E15)
- **Inputs**: Pixels; GSE tracks/motion, GM chocks, persons, BL and occluding transport/objects.
- **Outputs**: Per-GSE stop evidence aggregated to module result; failed eligible cases cause failure.
- **Local policy**: Select parked GSE episodes and fuse direct chocks, worker-action clues and image changes according to the viewing profile.
- **Attention**: Different chock evidence channels have different semantics; current truthy fusion must be made explicit before sharing.

### M14 · Handrails on GSE being used
- **Repo**: [handrails-on-gse-being-used](https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used) · local `external\handrails-on-gse-being-used` (read-only clone) · pinned `59fbced4`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Both, Jet=- · ProdReady=True
- **Streaming audit**: stage=DOWNLOAD · opens="BL next to the aircraft" → closes="worker got off the BL" · decision=EVENT · preventive=False · passes=1, pixels=6, models=1 · deps=tracker, bl_track · **verdict=NOW_PX**
  - why: Touch counter > 20 per worker. Six image accesses per frame — the most expensive after vests.
- **Components**: E09, E16, E17, E07 (+proposed: E12, E13)
- **Inputs**: Pixels; workers and BL tracks, aircraft/door/engine/wheel context, transport/person occluders.
- **Outputs**: Pass when all evaluated climbers have contact plus positive coverage; Fail for a sufficiently covered non-contact case; none evaluated is Not observed.
- **Local policy**: Evaluate handrail use for observable climbers on active loader visits and aggregate results locally.
- **Attention**: Whole-body hands are required; do not substitute body-only pose. Unknown climbers are excluded rather than forcing global unknown in current aggregation.

### M22 · Safety handrails fully extended and used
- **Repo**: [safety-handrails-fully-extended](https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended) · local `external\safety-handrails-fully-extended` (read-only clone) · pinned `8b9a2a9b`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Both, Jet=- · ProdReady=True
- **Streaming audit**: stage=DOWNLOAD · opens="BL next to the aircraft" → closes="BL drove away" · decision=EVENT · preventive=False · passes=1, pixels=2, models=0 · deps=tracker, bl_track · **verdict=NOW_PX**
  - why: extended_ratio > threshold over the BL's stay (>60 s). Verdict when the BL drove away.
- **Components**: E09, E16
- **Inputs**: Pixels; BL/aircraft tracks, front/back role, camera context and stopped-state evidence.
- **Outputs**: One result/report/timeline; no qualified loader is Not observed.
- **Local policy**: Require the configured rail-extension exposure over each qualified stopped-loader visit.
- **Attention**: 480 frames is about 60 seconds at 8 FPS, not eight minutes. Shared classifier reuse needs artifact/preprocessing identity.


## Pre-departure

### M02B · Main gear chocks removed only after aircraft is attached to pushback
- **Repo**: [aircraft-chocks](https://gitlab.com/dxgat/detectors/aircraft-chocks) · local `external\aircraft-chocks` (read-only clone) · pinned `fa00478f`
- **Tier / cameras / ProdReady**: real-time · Aircraft=Cone, Jet=Cone · ProdReady=False
- **Streaming audit**: stage=PRE_DEP · opens="T_arr" → closes="pushback attached → chock removal" · decision=EVENT · preventive=True · passes=2, pixels=1, models=1 · deps=tracker, pushback_attached · **verdict=PATCH**
  - why: The second pass knows median_pushback in advance. main_stream.py — 3 hunks, 0 discrepancies on Main gear. The right place for pushback_attached is the stage detector, not the module.
  - measured: Main gear 0 batch↔stream discrepancies on 8 videos; Nose wheel anchor shift −7…−444 s
- **Components**: E03, E09, E10, E14, E07
- **Inputs**: Pixels; GM rear wheels/chocks, aircraft parts, pushback and transport; attachment and beltloader-clear evidence.
- **Outputs**: Result[1]: main_status (main-gear removal timing), with its own report and timeline.
- **Local policy**: Gate main-gear assessment on attachment and loader clearance, then judge rear-wheel chock evidence and timing.
- **Attention**: Current code uses pushback attachment and beltloader clearance to gate rear-wheel evidence. Direct chocks and wheel-image differences feed this task, not the nose-gear placement task.

### M07 · Conditioned air removed 10 mins prior to departure and properly stowed
- **Repo**: [conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed](https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed) · local `external\conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed` (read-only clone) · pinned `940fdfc5`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Cone, Jet=Cone · ProdReady=True
- **Streaming audit**: stage=PRE_DEP · opens="T_dep − 10 min (in practice: BL leave)" → closes="T_dep" · decision=LOOKBACK · preventive=False · passes=1, pixels=1, models=0 · deps=tracker · **verdict=NOW_PX**
  - why: Mean over the last minute against the maximum — a window before T_dep. One access to the frame. Becomes preventive only with ETD.
- **Components**: E02, E03, E20, E07
- **Inputs**: Pixels; GM nose/pushback and aircraft motion; full hose history and departure time.
- **Outputs**: Combined decision with separate removal/stowage evidence in the internal decision routine and report.
- **Local policy**: Compare deployed and final hose appearance relative to departure; keep deadline and short-turn rules local.
- **Attention**: Held boxes are counted repeatedly in current history. Evidence is a visual area/position proxy, not an observed disconnected coupling.

### M08 · Cones are removed only after all GSE is clear of A/C and chocked
- **Repo**: [cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked](https://gitlab.com/dxgat/detectors/cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked) · local `external\cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked` (read-only clone) · pinned `e2a25ba3`
- **Tier / cameras / ProdReady**: real-time · Aircraft=Cone, Jet=Wing · ProdReady=False
- **Streaming audit**: stage=PRE_DEP · opens="BL leave" → closes="T_dep" · decision=EVENT · preventive=True · passes=1, pixels=0, models=0 · deps=tracker · **verdict=NOW**
  - why: Fail at the moment a cone is removed while vehicles are still next to the aircraft. The second load_metadata in the code is commented out.
- **Components**: E02, E03, E04, E09, E07
- **Inputs**: GM wing/engine/tail cones, wheels/aircraft parts and obstacles; BL/aircraft tracks.
- **Outputs**: One result/report/timeline.
- **Local policy**: Compare last cone evidence with equipment clearance. The current rule does not verify that all GSE is chocked.
- **Attention**: Despite its name it does NOT test whether GSE is chocked, and its equipment coverage is narrower than all GSE. A chocked prerequisite is new functional work.

### M04 · Belt loader forward chock remained in place until unit is backed up clear of aircraft
- **Repo**: [beltloader-chocks](https://gitlab.com/dxgat/detectors/beltloader-chocks) · local `external\beltloader-chocks` (read-only clone) · pinned `7056099b`
- **Tier / cameras / ProdReady**: real-time · Aircraft=Both, Jet=Wing · ProdReady=True
- **Streaming audit**: stage=DOWNLOAD · opens="BL next to the aircraft" → closes="BL drove away" · decision=EVENT · preventive=True · passes=1, pixels=0, models=0 · deps=tracker, bl_track · **verdict=NOW**
  - why: chock_registered while the BL is stationary; verdict when the BL is confirmed. Goes as is.
  - measured: recall 83%, precision 91% on 29 videos with all 12 violations
- **Components**: E09, E14
- **Inputs**: GM chocks/aircraft parts; BL tracks, front/back role and camera/aircraft layout.
- **Outputs**: One result; all confirmed eligible visits must latch chocked; no visits is Not observed.
- **Local policy**: Judge chock evidence for each eligible parked-loader visit. Continuous chock retention until clearance is not currently proved.
- **Attention**: A one-time chock latch does not prove continuous chocking throughout the entire parked interval.

### M16 · Pushback operator verifies steering bypass pin installation
- **Repo**: [pin-verification](https://gitlab.com/dxgat/detectors/pin-verification) · local `external\pin-verification` (read-only clone) · pinned `8e1863c7`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Cone, Jet=- · ProdReady=False
- **Streaming audit**: stage=PRE_DEP · opens="BL leave" → closes="pushback attached" · decision=EVENT · preventive=True · passes=2, pixels=1, models=1 · deps=tracker, pushback_attached · **verdict=PATCH**
  - why: The first pass is a copy of aircraft-chocks: pushback_window, median_pushback, number_of_frames. The same 3-hunk fix. "TODO: review and rework" in the code. In substance duplicates steering-by-pass-pin — to be cross-checked.
- **Components**: E02, E03, E10, E13, E15, E07 (+proposed: E12)
- **Inputs**: Pixels; worker/aircraft tracks, nose wheel/pushback/aircraft and obstacles; departure and attachment evidence.
- **Outputs**: One verification result/report/timeline.
- **Local policy**: Accept verification-like wheel interactions before the departure cutoff, subject to attachment and visibility evidence.
- **Attention**: Measures a verification-like worker action, not direct pin visibility. Current 1.5/2.5-second criteria differ from the supplied description.

### M19 · Pre-departure walk around completed
- **Repo**: [pre-departure-walk-around-completed](https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed) · local `external\pre-departure-walk-around-completed` (read-only clone) · pinned `e407de23`
- **Tier / cameras / ProdReady**: post · Aircraft=Cone, Jet=- · ProdReady=False
- **Streaming audit**: stage=PRE_DEP · opens="BL leave" → closes="T_dep" · decision=WHOLE · preventive=False · passes=1, pixels=2, models=2 · deps=tracker · **verdict=POST**
  - why: The same as post-arrival: coverage over the stage.
- **Components**: E02, E09, E18, E07 (+proposed: E12, E11, E03)
- **Inputs**: Pixels; aircraft parts, worker/BL/aircraft tracks; latest loading end, departure evidence and pushback obstruction.
- **Outputs**: Result/report/timeline plus technical trajectory/geometry/classifier evidence.
- **Local policy**: Choose the final post-loading inspection window and apply departure-specific walk scores, coverage and fallback rules.
- **Attention**: Pinned cv_common e4c5e36 lacks imported departure/presence helpers. The reported five-minute wording does not match the 480-second code window. Torch and Keras paths must remain separate profiles.

### M20 · Pushback does not start until wing walkers are in place and ready
- **Repo**: [pushback-does-not-start-until-wing-walkers-are-in-place-and-ready](https://gitlab.com/dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready) · local `external\pushback-does-not-start-until-wing-walkers-are-in-place-and-ready` (read-only clone) · pinned `f3b041cb`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Cone, Jet=Cone · ProdReady=False
- **Streaming audit**: stage=DEP · opens="pushback attached" → closes="pushback started moving" · decision=EVENT · preventive=True · passes=1, pixels=0, models=0 · deps=tracker · **verdict=NOW**
  - why: At the moment of start_moving it is checked whether ≥2 walkers are in place. The most critical moment of the turnaround — here the alert carries the most weight.
- **Components**: E02, E03, E11, E13, E07
- **Inputs**: Worker/aircraft tracks, aircraft parts and person/pushback/obstacle detections.
- **Outputs**: One readiness result/report/timeline.
- **Local policy**: Test both-side worker positions and co-motion near departure. Current post-start evidence does not prove pre-start readiness.
- **Attention**: Current evidence is post-start co-motion, not a direct proof that everyone was ready before start. Global role flags require per-turn state isolation.

### M21 · Pushback pathway confirmed clear of obstacles
- **Repo**: [pushback-pathway-confirmed-clear-of-obstacles](https://gitlab.com/dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles) · local `external\pushback-pathway-confirmed-clear-of-obstacles` (read-only clone) · pinned `104db85a`
- **Tier / cameras / ProdReady**: real-time · Aircraft=Cone, Jet=Cone · ProdReady=True
- **Streaming audit**: stage=DEP · opens="T_dep − 45 s" → closes="T_dep" · decision=INSTANT · preventive=True · passes=1, pixels=0, models=0 · deps=tracker · **verdict=NOW**
  - why: Any frame with a corridor intersection → Fail. By type ideal for streaming — and yet measured 0 of 4 violations: it is not the logic that is broken but the intersection detection itself.
  - measured: recall 0% (0/4), 85% "accuracy" = just passes on the clean ones
- **Components**: E02, E19, E05, E04, E07
- **Inputs**: GM aircraft nose/tail, BL/GSE/fuel truck/trailer/cone/chock/ladder and pushback; aircraft motion.
- **Outputs**: One pathway result/report/timeline.
- **Local policy**: Test selected hazards in the pushback path over the departure window, distinguishing hazards from view blockers.
- **Attention**: Current hazard class list does not include people. Variable pushback_moving uses aircraft state, not an independent pushback motion state.

### M27 · Wing walkers in proper position and using approved wands
- **Repo**: [wing-walkers-in-proper-position-and-using-approved-wands](https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands) · local `external\wing-walkers-in-proper-position-and-using-approved-wands` (read-only clone) · pinned `4800b649`
- **Tier / cameras / ProdReady**: streaming · Aircraft=Cone, Jet=Cone · ProdReady=True
- **Streaming audit**: stage=DEP · opens="T_dep − predeparture_prepare" → closes="T_dep + 60 s" · decision=LOOKBACK · preventive=False · passes=1, pixels=0, models=1 · deps=tracker · **verdict=NOW**
  - why: Walker positions relative to depart_frame; wand_counter > 300. Loads wand_detector.pt, but the inference is commented out — the model is dead, remove before porting.
- **Components**: E02, E03, E11, E25
- **Inputs**: Worker/aircraft tracks, GM aircraft parts/pushback/persons/obstacles and movement history.
- **Outputs**: Position result plus wand sub-result and associated report/timeline structures.
- **Local policy**: Judge departure-side positions separately from wand evidence. Do not treat the current hard-coded wand Pass as detection.
- **Attention**: CRITICAL semantic gap: approved-wand Pass is hard-coded on the active path. Old wand-count code is not called; merely extracting it would not preserve active behavior or establish correctness.


## Departure (Tow-Bar disconnect)

### M02C · Nose wheel chock removed from aircraft
- **Repo**: [aircraft-chocks](https://gitlab.com/dxgat/detectors/aircraft-chocks) · local `external\aircraft-chocks` (read-only clone) · pinned `fa00478f`
- **Tier / cameras / ProdReady**: real-time · Aircraft=Cone, Jet=Cone · ProdReady=True
- **Streaming audit**: stage=PRE_DEP · opens="T_arr" → closes="pushback attached → chock removal" · decision=EVENT · preventive=True · passes=2, pixels=1, models=1 · deps=tracker, pushback_attached · **verdict=PATCH**
  - why: The second pass knows median_pushback in advance. main_stream.py — 3 hunks, 0 discrepancies on Main gear. The right place for pushback_attached is the stage detector, not the module.
  - measured: Main gear 0 batch↔stream discrepancies on 8 videos; Nose wheel anchor shift −7…−444 s
- **Components**: E03, E10, E14, E07
- **Inputs**: GM front-wheel/chock/obstacle observations; pushback reference box, attachment time and front-wheel presence history.
- **Outputs**: Result[2]: front_removed, with its own report and timeline.
- **Local policy**: Apply the nose-removal ordering rule. Current success uses post-attachment chock presence, not an observed removal edge.
- **Attention**: Current success includes sustained front-chock presence after attachment, not a directly detected removal edge. Keep the checklist name separate from this implementation limitation.


## Pipeline / utility (U)

### U01 · Camera ingestion and full-turn assembly
- **Repo**: [camera_software](https://gitlab.com/dxgat/utils/camera_software) · local `external\camera_software` (read-only clone) · pinned `13ef3fc3`
- **Components**: E28, E26, E03, E05, E27, E29, E32
- **Inputs**: Camera chunk manifests/storage/DB, 60-second video chunks nominally 8 FPS, persisted camera/turn candidate state.
- **Outputs**: Merged full-turn media plus DB/session metadata and processed-chunk state.
- **Local policy**: Select capture boundaries, assemble and publish full-turn videos. Capture arrival/departure rules are not downstream policy stage rules.
- **Attention**: Its coarse capture boundary is not identical to downstream arrival/departure semantics. Keep clip and analytic-stage versions distinct.

### U02 · General-model pipeline
- **Repo**: [general_model](https://gitlab.com/dxgat/detectors/general_model) · local `external\general_model` (read-only clone) · pinned `13a4ddc5`
- **Components**: E26, E03, E04, E05, E06, E07, E27, E01, E02, E09, E30
- **Inputs**: Merged video/pixels, inference configuration/class mappings, model artifacts and worker metadata writer.
- **Outputs**: general_model<video>.ndjson; camera/entity/aircraft type, stage/statistic dictionary, noise and broken-image information.
- **Local policy**: Run detection and scene enrichment, select the main aircraft and publish metadata. These are responsibilities to decompose, not leaf-policy inputs.
- **Attention**: Airplane height replaces normal detection confidence in the output array. Do not treat every fifth numeric field as probability.

### U03 · Tracking and semantic vehicle state
- **Repo**: [cv_trackers](https://gitlab.com/dxgat/utils/cv_trackers) · local `external\cv_trackers` (read-only clone) · pinned `b5d350c7`
- **Components**: E11, E08, E09, E27, E01, E30
- **Inputs**: Video pixels, GM NDJSON, class mappings, DeepSORT/tracked-object configuration and utility pins.
- **Outputs**: trackers<video>.ndjson: Track serialization, vehicle private state_dict, and BL role data.
- **Local policy**: Track identities and movement, assign loader service roles and publish tracking metadata.
- **Attention**: Only GSE/BL get general vehicle tracking here; downstream safety-zone still tracks other transport. Serialized private fields tightly couple consumers to implementation versions.

### U04 · Shared CV library
- **Repo**: [cv_common](https://gitlab.com/dxgat/utils/cv_common) · local `external\cv_common` (read-only clone) · pinned `ac5098d2`
- **Components**: E33, E08, E27, E01, E02, E28, E26, E30, E32
- **Inputs**: Model/runtime configs, pixels/detections, track state and geometric inputs supplied by callers.
- **Outputs**: Python APIs/classes rather than one pipeline stream.
- **Local policy**: Provide reusable library APIs. Availability at the standalone revision does not prove availability at each consumer pin.
- **Attention**: Standalone master is not every module dependency. Missing helper imports at selected pins must be resolved deliberately, not via blanket submodule update.

### U05 · Media, artifact, worker and reporting infrastructure
- **Repo**: [db_worker](https://gitlab.com/dxgat/utils/db_worker) · local `external\db_worker` (read-only clone) · pinned `5a4aa83d`
- **Components**: E28, E30, E31, E32
- **Inputs**: Media/storage/DB/Kafka configuration, model and task IDs, weights/inference artifacts and module return values.
- **Outputs**: NDJSON, task statuses/reports/timelines, technical artifacts and job execution status.
- **Local policy**: Supply media and metadata, execute jobs and deliver per-task reports and artifacts.
- **Attention**: Replace positional row joins and private filename conventions with explicit identity. Legacy tuple/task-array adapters must preserve multiple results and optional extras.


## Outside the active review scope, but present in the code audit

- `seat-belts-used-on-all-gse-equipped-with-seat-belts` — Seat belts used on all GSE equipped with seat belts · verdict=NOW_PX · seatbelt_used == False → Fail for the person. Instant type. Pixels needed, no networks of its own.
