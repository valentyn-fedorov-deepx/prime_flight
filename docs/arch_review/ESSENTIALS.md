# Component Architecture

**32 shared components; 109 direct input references and 1 proposed reuse across 28 checklist tasks.** Pipeline and utility responsibilities are listed separately.

The component list is accepted for architecture work. [Components and notes](index.html) / [Interactive hierarchy](hierarchy.html). Seat-belt use (M25) and its dedicated evidence component (E23) are removed from the active scope; IDs are not renumbered. Historical source work remains in [the detailed workbook](REVIEW.md).

The two supplied review comments have been applied: E14 is Chock analysis; E24 is also listed for M16 as proposed reuse. [Applied comments](APPLIED_NOTES.md). Notes have been cleared; new notes can be added below.

## Boundaries

- Task lists contain evidence needed by the policy, not every internal function or model operation.
- Counts, deadlines, debouncing thresholds, eligibility rules and final Pass/Fail logic remain local.
- One component ID means one proposed contract. Shared names do not imply identical weights, preprocessing or regional rules.
- Internal building blocks are recorded separately; they are not additional direct prerequisites for every consumer of a broad concept.
- Pixel access, model wrappers, buffers, crops, serialization and reporting are not repeated in every policy list.
- Acceptance of a component boundary is not proof of detector accuracy or production readiness. The hierarchy is a proposed dependency structure, not a fixed deployment architecture.

## Shared Concepts

| ID | Component / supplied evidence | Evidence | Your notes |
| --- | --- | --- | --- |
| E01 | **Aircraft arrival context**<br>Arrival time, whether arrival was seen, and how much pre-arrival footage is available. | [Traceability](ESSENTIAL_MAPPING.md#e01) |  |
| E02 | **Aircraft departure context**<br>Departure time, whether departure was seen, and the available departure footage. | [Traceability](ESSENTIAL_MAPPING.md#e02) |  |
| E03 | **Aircraft layout**<br>Aircraft and part locations, aircraft type and camera view, including missing or off-screen parts. | [Traceability](ESSENTIAL_MAPPING.md#e03) |  |
| E04 | **Chocks and cones detections**<br>Chock and cone locations, types and counts over time. Placement requirements remain in the policy. | [Traceability](ESSENTIAL_MAPPING.md#e04) |  |
| E05 | **Transport detections**<br>Vehicle and ground-equipment locations and classes, including beltloaders, GSE, pushback and ladders. | [Traceability](ESSENTIAL_MAPPING.md#e05) |  |
| E06 | **People detections**<br>Person locations and counts per frame. Counts alone do not establish worker identity. | [Traceability](ESSENTIAL_MAPPING.md#e06) |  |
| E07 | **Camera obstacle status**<br>Which camera regions are blocked or not visible, and when. Keep region-specific visibility rather than one global flag. | [Traceability](ESSENTIAL_MAPPING.md#e07) |  |
| E08 | **Vehicle movement and stops**<br>Vehicle identity, position, direction and moving or stopped periods, with continuity across track changes. | [Traceability](ESSENTIAL_MAPPING.md#e08) |  |
| E09 | **Beltloader service status**<br>Which loader serves each door, its approach and parked periods, and when it leaves or returns. | [Traceability](ESSENTIAL_MAPPING.md#e09) |  |
| E10 | **Pushback attachment status**<br>When pushback appears attached to the aircraft. Current implementations use sustained proximity, not mechanical coupling detection. | [Traceability](ESSENTIAL_MAPPING.md#e10) |  |
| E11 | **Worker tracks and paths**<br>Worker identities and time-stamped positions, directions and paths relative to the aircraft or work area. | [Traceability](ESSENTIAL_MAPPING.md#e11) |  |
| E12 | **Worker pose**<br>Body landmarks and confidence; hand landmarks where needed. Body-only and whole-body models remain separate profiles. | [Traceability](ESSENTIAL_MAPPING.md#e12) |  |
| E13 | **Workers near equipment**<br>Which workers are drivers, helpers, climbers or interacting near a wheel, and during which equipment visit. | [Traceability](ESSENTIAL_MAPPING.md#e13) |  |
| E14 | **Chock analysis**<br>Chock evidence at the relevant wheel over time, with separate nose-wheel, main-gear, beltloader and GSE profiles. Keep direct sightings, worker-action clues and image-change clues distinct; final policy rules stay local. | [Traceability](ESSENTIAL_MAPPING.md#e14) |  |
| E15 | **Worker actions**<br>Time-stamped bending, sitting or raised-hand evidence. These are task-specific action profiles, not an approved signal vocabulary. | [Traceability](ESSENTIAL_MAPPING.md#e15) |  |
| E16 | **Handrail state**<br>Whether rails appear extended and where the rails are. Location masks are only needed by contact checks. | [Traceability](ESSENTIAL_MAPPING.md#e16) |  |
| E17 | **Handrail contact**<br>Whether and when a climber appears to hold the rail, with contact visibility and observation coverage. | [Traceability](ESSENTIAL_MAPPING.md#e17) |  |
| E18 | **Walk-around evidence**<br>Inspection paths, aircraft-relative coverage, model scores and usable observation coverage. Arrival and departure scorers remain distinct profiles. | [Traceability](ESSENTIAL_MAPPING.md#e18) |  |
| E19 | **Ground work areas**<br>The relevant ground region: FOD corridor, safety zone or pushback path. These are different region profiles, not the same polygon. | [Traceability](ESSENTIAL_MAPPING.md#e19) |  |
| E20 | **Hose state**<br>Hose location and deployed or stowed appearance over time. Visual changes do not prove physical disconnection. | [Traceability](ESSENTIAL_MAPPING.md#e20) |  |
| E21 | **Huddle cone detection**<br>The location and identity of the green meeting cone, including its color check. | [Traceability](ESSENTIAL_MAPPING.md#e21) |  |
| E22 | **Vest closure**<br>Each worker's zipped, unzipped or unknown vest appearance, with viewing direction and image quality. | [Traceability](ESSENTIAL_MAPPING.md#e22) |  |
| E24 | **Pin installation actions**<br>Worker action classes and times near the nose wheel from the learned installation model. This does not directly see the pin. | [Traceability](ESSENTIAL_MAPPING.md#e24) |  |
| E25 | **Wand evidence**<br>Visible wands associated with workers. Required by the checklist, but active visual verification is missing in the reviewed module. | [Traceability](ESSENTIAL_MAPPING.md#e25) |  |
| E26 | **Scene type and image quality**<br>Inside or outside scene, image noise and usable image quality, with suitable preprocessing. | [Traceability](ESSENTIAL_MAPPING.md#e26) |  |
| E27 | **Aircraft movement**<br>The main aircraft's identity and moving or stopped history. Capture boundaries and analytical stage rules remain separate profiles. | [Traceability](ESSENTIAL_MAPPING.md#e27) |  |
| E28 | **Video frames and timing**<br>Read video frames with their source identity and timing, including frame access and replay. | [Traceability](ESSENTIAL_MAPPING.md#e28) |  |
| E29 | **Turn video assembly**<br>Find, order and merge camera chunks into a turn video, retain context and resume incomplete processing. | [Traceability](ESSENTIAL_MAPPING.md#e29) |  |
| E30 | **Metadata exchange**<br>Read, align, store and deliver frame metadata through NDJSON or messaging. Current positional joins still need correction. | [Traceability](ESSENTIAL_MAPPING.md#e30) |  |
| E31 | **Job setup and execution**<br>Load configuration and weights, run pipeline stages and modules, and manage artifacts and retries. | [Traceability](ESSENTIAL_MAPPING.md#e31) |  |
| E32 | **Results and evidence**<br>Map task outputs, retain evidence and deliver reports, keeping processing errors separate from compliance failures. | [Traceability](ESSENTIAL_MAPPING.md#e32) |  |
| E33 | **CV runtime helpers**<br>Shared model wrappers and image, box, mask and coordinate operations. These are library internals, not policy inputs. | [Traceability](ESSENTIAL_MAPPING.md#e33) |  |

## Task Inputs

### M06 - Chocks and cones available and staged for arrival

Repository: `chocks-and-cones-available-and-staged-for-arrival`.

- [Aircraft arrival context](index.html#M06/E01) (E01).
- [Chocks and cones detections](index.html#M06/E04) (E04).
- [Transport detections](index.html#M06/E05) (E05).
- [Camera obstacle status](index.html#M06/E07) (E07).

**Kept local:** Count ground chocks and cones before arrival; exclude transport-carried chocks and apply the count, duration and visibility rules locally.

**Attention:** YAML 6/4 counts are not the active main-code 7/6 counts. Do not assume every configuration value controls behavior.

### M10 - Crew present 10 minutes prior to aircraft arrival

Repository: `crew-present-10-minutes-prior-to-aircraft-arrival`.

- [Aircraft arrival context](index.html#M10/E01) (E01).
- [People detections](index.html#M10/E06) (E06).
- [Camera obstacle status](index.html#M10/E07) (E07).

**Kept local:** Choose the arrival-relative crew window and test person-count exposure, including short-video handling.

**Attention:** This measures counts over a window, not continuous presence of the same three named workers for ten minutes.

### M11 - FOD walk completed

Repository: `fod-walk-completed`.

- [Aircraft arrival context](index.html#M11/E01) (E01).
- [Worker tracks and paths](index.html#M11/E11) (E11). FOD profile includes pose-based facing direction and approximate depth; vehicle occupants are excluded.
- [Ground work areas](index.html#M11/E19) (E19). FOD approach corridor.
- [Camera obstacle status](index.html#M11/E07) (E07).

**Kept local:** Decide whether a qualifying worker path crosses the inspection corridor before arrival.

**Attention:** Not the simple horizontal-crossing rule in the basic description; bbox-derived scale is not calibrated physical distance.

Internal building blocks: Worker pose (E12), Workers near equipment (E13).

### M18 - Safety huddle conducted at huddle cone

Repository: `pre-arrival-safety-huddle`.

- [Aircraft arrival context](index.html#M18/E01) (E01). Required arrival helper is absent at the reviewed utility pin.
- [Huddle cone detection](index.html#M18/E21) (E21).
- [People detections](index.html#M18/E06) (E06).
- [Camera obstacle status](index.html#M18/E07) (E07).

**Kept local:** Count workers near the green cone and require a sustained gathering before arrival.

**Attention:** Pinned cv_common ac5098d lacks imported PlaneArrivalDetector. A candidate implementation exists at cv_common 2759daf, not at the reviewed pin.

### M23 - Employees wearing safety vests secured to body

Repository: `safety-vests-secured-to-body`.

- [Worker tracks and paths](index.html#M23/E11) (E11). Identity and recent observations only; aircraft-relative paths are not required.
- [Vest closure](index.html#M23/E22) (E22). Appearance models and color geometry; no keypoint pose is used.

**Kept local:** Apply per-worker vest rules and aggregate worker results. Keep the current unknown-state limitation visible.

**Attention:** No keypoint pose despite the model name. Current unknown/undefined workers can coexist with Pass; do not silently strengthen semantics during extraction.

### M24 - Safety zone confirmed clear

Repository: `safety-zone-confirmed-clear`.

- [Aircraft arrival context](index.html#M24/E01) (E01).
- [Ground work areas](index.html#M24/E19) (E19). Safety diamond, distinct from the FOD corridor.
- [Vehicle movement and stops](index.html#M24/E08) (E08). Includes local tracking and segmentation-based motion for transport classes absent from cv_trackers.
- [Chocks and cones detections](index.html#M24/E04) (E04).
- [Camera obstacle status](index.html#M24/E07) (E07).

**Kept local:** Test moving transport and cone conditions inside the safety zone before arrival; apply violation and unknown-coverage rules locally.

**Attention:** Upstream tracker does not cover every transport class currently tracked here. FOD and safety-zone ROIs are related but not identical.

### M02A - Nose gear chocks applied immediately

Repository: `aircraft-chocks`.

- [Aircraft arrival context](index.html#M02A/E01) (E01).
- [Aircraft layout](index.html#M02A/E03) (E03).
- [Chock analysis](index.html#M02A/E14) (E14). Nose-wheel direct chock sightings only.
- [Camera obstacle status](index.html#M02A/E07) (E07). Front-placement visibility branch, not the rear-wheel timeout.

**Kept local:** Check nose-gear chock evidence within the arrival deadline. No pushback or rear-wheel comparison prerequisite.

**Attention:** Placement is assessed within 30 seconds of aircraft stop. Pushback attachment and rear-wheel image differences are not prerequisites for this task.

### M09 - Cones placed in proper positions and timely

Repository: `cones-placed-in-proper-positions-and-timely`.

- [Aircraft arrival context](index.html#M09/E01) (E01).
- [Aircraft layout](index.html#M09/E03) (E03).
- [Chocks and cones detections](index.html#M09/E04) (E04).
- [Camera obstacle status](index.html#M09/E07) (E07).

**Kept local:** Choose required cone roles for this camera and aircraft, then apply their count and exposure requirements.

**Attention:** Obstacle report text says 40% while code tests 65%; inconsistent return arity requires an explicit legacy adapter.

### M26 - Steering by-pass pin installed, or steering otherwise bypassed

Repository: `steering-by-pass-pin-installed-or-steering-otherwise-bypassed`.

- [Aircraft arrival context](index.html#M26/E01) (E01).
- [Aircraft layout](index.html#M26/E03) (E03).
- [Pin installation actions](index.html#M26/E24) (E24).
- [Camera obstacle status](index.html#M26/E07) (E07).

**Kept local:** Accept installation-like actions within the arrival-relative window. Do not add an unimplemented chocking prerequisite.

**Attention:** Distinct learned installation task from heuristic pin verification. Chock detections are collected but do not establish chocking prerequisite.

Internal building blocks: Worker pose (E12), Workers near equipment (E13).

### M15 - Lead marshaller and wing walkers in correct position

Repository: `lead-marshaller-and-wing-walkers-in-position`.

- [Aircraft arrival context](index.html#M15/E01) (E01).
- [Aircraft layout](index.html#M15/E03) (E03).
- [Worker tracks and paths](index.html#M15/E11) (E11). Arrival wing-walker positions and movement; no pose or wand model.
- [Camera obstacle status](index.html#M15/E07) (E07).

**Kept local:** Check arrival-period paths and opposite-side coverage. Lead-marshaller gestures are not verified by the active code.

**Attention:** No separate pose/wand model or lead-marshaller signal proof on the active path.

### M05 - Beltloader rear cone positioned after BL is in place

Repository: `bl_rear_cone`.

- [Beltloader service status](index.html#M05/E09) (E09). Includes loader identity, door role, viewing direction and parked visit geometry.
- [Chocks and cones detections](index.html#M05/E04) (E04). Rear-cone footpoints; chock detections are not needed by this profile.

**Kept local:** Choose the region behind each qualified parked loader and require enough cone presence during the visit.

**Attention:** Checklist and code thresholds differ; preserve code behavior as the migration baseline, then approve requirement changes separately.

### M13 - All GSE guided into aircraft using approved hand signals

Repository: `hand-signals`.

- [Beltloader service status](index.html#M13/E09) (E09).
- [Workers near equipment](index.html#M13/E13) (E13).
- [Worker actions](index.html#M13/E15) (E15). Raised-arm proxy only; no approved hand-signal vocabulary.
- [Camera obstacle status](index.html#M13/E07) (E07). Worker/crop eligibility and recorded ROI coverage; the saved coverage value is not itself a signal gate.

**Kept local:** Select the helper and pre-stop signal window for each loader visit, then apply the raised-arm duration rule.

**Attention:** Raised wrists are a coarse gesture proxy, not an approved signal vocabulary. Same HRNet checkpoint as steering does not imply same crop preprocessing.

Internal building blocks: Worker pose (E12).

### M17 - Post-arrival aircraft walk around inspection completed accurately

Repository: `post-arrival-aircraft-walk-around-inspection-completed-accurately`.

- [Aircraft arrival context](index.html#M17/E01) (E01).
- [Beltloader service status](index.html#M17/E09) (E09).
- [Walk-around evidence](index.html#M17/E18) (E18). Post-arrival PyTorch scorer. Depth, aircraft mask, top-down reconstruction and path cleanup stay inside this component; optional rescue paths are off by default.
- [Camera obstacle status](index.html#M17/E07) (E07).

**Kept local:** Choose the post-arrival inspection window and apply the arrival-specific walk score and coverage rules.

**Attention:** Post-arrival rescue/outlier options are disabled by default. Score-derived confidence is not demonstrated calibrated probability; required cached geometry must exist.

Internal building blocks: Worker pose (E12), Worker tracks and paths (E11), Aircraft layout (E03).

### M01 - 3 stop brake check

Repository: `3-stop-brake-check`.

- [Aircraft layout](index.html#M01/E03) (E03).
- [Vehicle movement and stops](index.html#M01/E08) (E08). Current module replays optical-flow motion locally. Reusing upstream stopped status requires equivalence testing.
- [Beltloader service status](index.html#M01/E09) (E09).
- [Camera obstacle status](index.html#M01/E07) (E07).

**Kept local:** Count confirmed stops during an eligible approach; handle reverse/reset behavior and aggregate loader visits locally.

**Attention:** Do not replace its recomputed status with generic tracker status without replay comparison; seconds vary with configured FPS.

### M03 - All cargo bin doors opened and verified

Repository: `all-cargo-bin-doors-opened-and-verified`.

- [Aircraft arrival context](index.html#M03/E01) (E01).
- [Aircraft layout](index.html#M03/E03) (E03). Includes visible cargo-door detections. Door-to-loader verification and independent mechanical open/closed sensing are not implemented.
- [Camera obstacle status](index.html#M03/E07) (E07).

**Kept local:** Select the camera-relevant cargo door and test its visible exposure in the eligible arrival window.

**Attention:** Does not verify a BL target-door relationship or independently distinguish mechanical open/closed state beyond detector-label semantics.

### M12 - Motorized GSE parked and properly chocked

Repository: `gse-chocks`.

- [Vehicle movement and stops](index.html#M12/E08) (E08).
- [Workers near equipment](index.html#M12/E13) (E13).
- [Chock analysis](index.html#M12/E14) (E14). GSE profile: direct sightings, bending clues and a GSE-specific image-change model. Fusion and pass thresholds stay local.
- [Camera obstacle status](index.html#M12/E07) (E07).

**Kept local:** Select parked GSE episodes and fuse direct chocks, worker-action clues and image changes according to the viewing profile.

**Attention:** Different chock evidence channels have different semantics; current truthy fusion must be made explicit before sharing.

Internal building blocks: Worker pose (E12), Worker actions (E15).

### M14 - Handrails on GSE being used

Repository: `handrails-on-gse-being-used`.

- [Beltloader service status](index.html#M14/E09) (E09).
- [Handrail state](index.html#M14/E16) (E16). Extension appearance plus rail segmentation.
- [Handrail contact](index.html#M14/E17) (E17). Uses hand landmarks, rail geometry and an appearance fallback; body-only pose is insufficient.
- [Camera obstacle status](index.html#M14/E07) (E07).

**Kept local:** Evaluate handrail use for observable climbers on active loader visits and aggregate results locally.

**Attention:** Whole-body hands are required; do not substitute body-only pose. Unknown climbers are excluded rather than forcing global unknown in current aggregation.

Internal building blocks: Worker pose (E12), Workers near equipment (E13).

### M22 - Safety handrails fully extended and used

Repository: `safety-handrails-fully-extended`.

- [Beltloader service status](index.html#M22/E09) (E09).
- [Handrail state](index.html#M22/E16) (E16). Extension classifier only; no rail-contact mask or hand-pose requirement.

**Kept local:** Require the configured rail-extension exposure over each qualified stopped-loader visit.

**Attention:** 480 frames is about 60 seconds at 8 FPS, not eight minutes. Shared classifier reuse needs artifact/preprocessing identity.

### M02B - Main gear chocks removed only after aircraft is attached to pushback

Repository: `aircraft-chocks`.

- [Aircraft layout](index.html#M02B/E03) (E03).
- [Beltloader service status](index.html#M02B/E09) (E09).
- [Pushback attachment status](index.html#M02B/E10) (E10).
- [Chock analysis](index.html#M02B/E14) (E14). Rear-wheel direct sightings and aircraft-specific image-change models; no worker-pose prerequisite.
- [Camera obstacle status](index.html#M02B/E07) (E07). Rear-wheel visibility and timeout branch.

**Kept local:** Gate main-gear assessment on attachment and loader clearance, then judge rear-wheel chock evidence and timing.

**Attention:** Current code uses pushback attachment and beltloader clearance to gate rear-wheel evidence. Direct chocks and wheel-image differences feed this task, not the nose-gear placement task.

### M07 - Conditioned air removed 10 mins prior to departure and properly stowed

Repository: `conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed`.

- [Aircraft departure context](index.html#M07/E02) (E02).
- [Aircraft layout](index.html#M07/E03) (E03).
- [Hose state](index.html#M07/E20) (E20). Sparse hose detector with held observations; repeated held boxes are not independent samples.
- [Camera obstacle status](index.html#M07/E07) (E07). Hose/pushback overlap at the final observation.

**Kept local:** Compare deployed and final hose appearance relative to departure; keep deadline and short-turn rules local.

**Attention:** Held boxes are counted repeatedly in current history. Evidence is a visual area/position proxy, not an observed disconnected coupling.

### M08 - Cones are removed only after all GSE is clear of A/C and chocked

Repository: `cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked`.

- [Aircraft departure context](index.html#M08/E02) (E02).
- [Aircraft layout](index.html#M08/E03) (E03).
- [Chocks and cones detections](index.html#M08/E04) (E04).
- [Beltloader service status](index.html#M08/E09) (E09). Current proximity checks cover narrower equipment than the all-GSE checklist wording.
- [Camera obstacle status](index.html#M08/E07) (E07).

**Kept local:** Compare last cone evidence with equipment clearance. The current rule does not verify that all GSE is chocked.

**Attention:** Despite its name it does NOT test whether GSE is chocked, and its equipment coverage is narrower than all GSE. A chocked prerequisite is new functional work.

### M04 - Belt loader forward chock remained in place until unit is backed up clear of aircraft

Repository: `beltloader-chocks`.

- [Beltloader service status](index.html#M04/E09) (E09).
- [Chock analysis](index.html#M04/E14) (E14). Beltloader profile: view-specific wheel region and direct chock sightings, not image-change or pose models.

**Kept local:** Judge chock evidence for each eligible parked-loader visit. Continuous chock retention until clearance is not currently proved.

**Attention:** A one-time chock latch does not prove continuous chocking throughout the entire parked interval.

### M16 - Pushback operator verifies steering bypass pin installation

Repository: `pin-verification`.

- [Aircraft departure context](index.html#M16/E02) (E02).
- [Aircraft layout](index.html#M16/E03) (E03).
- [Pushback attachment status](index.html#M16/E10) (E10).
- [Workers near equipment](index.html#M16/E13) (E13).
- [Worker actions](index.html#M16/E15) (E15). Bend/sit and raised-hands verification heuristics; not the learned pin-installation classifier and not direct pin visibility.
- [Camera obstacle status](index.html#M16/E07) (E07).
- [Pin installation actions](index.html#M16/E24) (E24). Proposed reuse: use pin-installation action evidence in pin verification as well. Adapt and validate a verification profile; the current M16 path uses E15 heuristics, not the learned E24 model.

**Kept local:** Accept verification-like wheel interactions before the departure cutoff, subject to attachment and visibility evidence.

**Attention:** Measures a verification-like worker action, not direct pin visibility. Current 1.5/2.5-second criteria differ from the supplied description.

Internal building blocks: Worker pose (E12).

### M19 - Pre-departure walk around completed

Repository: `pre-departure-walk-around-completed`.

- [Aircraft departure context](index.html#M19/E02) (E02). Imported departure helper is absent at the reviewed utility pin.
- [Beltloader service status](index.html#M19/E09) (E09). Imported loader-presence helper is absent at the reviewed utility pin.
- [Walk-around evidence](index.html#M19/E18) (E18). Pre-departure Keras scorer with enabled cleanup and wide-arc fallbacks; not interchangeable with the post-arrival scorer.
- [Camera obstacle status](index.html#M19/E07) (E07).

**Kept local:** Choose the final post-loading inspection window and apply departure-specific walk scores, coverage and fallback rules.

**Attention:** Pinned cv_common e4c5e36 lacks imported departure/presence helpers. The reported five-minute wording does not match the 480-second code window. Torch and Keras paths must remain separate profiles.

Internal building blocks: Worker pose (E12), Worker tracks and paths (E11), Aircraft layout (E03).

### M20 - Pushback does not start until wing walkers are in place and ready

Repository: `pushback-does-not-start-until-wing-walkers-are-in-place-and-ready`.

- [Aircraft departure context](index.html#M20/E02) (E02).
- [Aircraft layout](index.html#M20/E03) (E03).
- [Worker tracks and paths](index.html#M20/E11) (E11).
- [Workers near equipment](index.html#M20/E13) (E13).
- [Camera obstacle status](index.html#M20/E07) (E07).

**Kept local:** Test both-side worker positions and co-motion near departure. Current post-start evidence does not prove pre-start readiness.

**Attention:** Current evidence is post-start co-motion, not a direct proof that everyone was ready before start. Global role flags require per-turn state isolation.

### M21 - Pushback pathway confirmed clear of obstacles

Repository: `pushback-pathway-confirmed-clear-of-obstacles`.

- [Aircraft departure context](index.html#M21/E02) (E02).
- [Ground work areas](index.html#M21/E19) (E19). Pushback path profile.
- [Transport detections](index.html#M21/E05) (E05). Includes ladders and other selected ground equipment; the active hazard set omits people.
- [Chocks and cones detections](index.html#M21/E04) (E04).
- [Camera obstacle status](index.html#M21/E07) (E07).

**Kept local:** Test selected hazards in the pushback path over the departure window, distinguishing hazards from view blockers.

**Attention:** Current hazard class list does not include people. Variable pushback_moving uses aircraft state, not an independent pushback motion state.

### M27 - Wing walkers in proper position and using approved wands

Repository: `wing-walkers-in-proper-position-and-using-approved-wands`.

- [Aircraft departure context](index.html#M27/E02) (E02).
- [Aircraft layout](index.html#M27/E03) (E03).
- [Worker tracks and paths](index.html#M27/E11) (E11).
- [Wand evidence](index.html#M27/E25) (E25). MISSING: active path returns wand Pass without visual verification; legacy code and model initialization do not fill that gap.

**Kept local:** Judge departure-side positions separately from wand evidence. Do not treat the current hard-coded wand Pass as detection.

**Attention:** CRITICAL semantic gap: approved-wand Pass is hard-coded on the active path. Old wand-count code is not called; merely extracting it would not preserve active behavior or establish correctness.

### M02C - Nose wheel chock removed from aircraft

Repository: `aircraft-chocks`.

- [Aircraft layout](index.html#M02C/E03) (E03).
- [Pushback attachment status](index.html#M02C/E10) (E10).
- [Chock analysis](index.html#M02C/E14) (E14). Nose-wheel direct sightings only.
- [Camera obstacle status](index.html#M02C/E07) (E07). Front-removal branch, including pushback obstruction; not the rear-wheel timeout.

**Kept local:** Apply the nose-removal ordering rule. Current success uses post-attachment chock presence, not an observed removal edge.

**Attention:** Current success includes sustained front-chock presence after attachment, not a directly detected removal edge. Keep the checklist name separate from this implementation limitation.

## Pipeline And Utility Responsibilities

### U01 - Camera ingestion and full-turn assembly

Repository: `camera_software`.

- [Video frames and timing](index.html#U01/E28) (E28).
- [Scene type and image quality](index.html#U01/E26) (E26).
- [Aircraft layout](index.html#U01/E03) (E03).
- [Transport detections](index.html#U01/E05) (E05).
- [Aircraft movement](index.html#U01/E27) (E27).
- [Turn video assembly](index.html#U01/E29) (E29).
- [Results and evidence](index.html#U01/E32) (E32).

**Kept local:** Select capture boundaries, assemble and publish full-turn videos. Capture arrival/departure rules are not downstream policy stage rules.

**Attention:** Its coarse capture boundary is not identical to downstream arrival/departure semantics. Keep clip and analytic-stage versions distinct.

### U02 - General-model pipeline

Repository: `general_model`.

- [Scene type and image quality](index.html#U02/E26) (E26).
- [Aircraft layout](index.html#U02/E03) (E03).
- [Chocks and cones detections](index.html#U02/E04) (E04).
- [Transport detections](index.html#U02/E05) (E05).
- [People detections](index.html#U02/E06) (E06).
- [Camera obstacle status](index.html#U02/E07) (E07).
- [Aircraft movement](index.html#U02/E27) (E27).
- [Aircraft arrival context](index.html#U02/E01) (E01). GM stage intervals; do not assume identical timing to tracker-derived arrival.
- [Aircraft departure context](index.html#U02/E02) (E02). GM stage intervals; do not assume identical timing to downstream departure helpers.
- [Beltloader service status](index.html#U02/E09) (E09). INPUT GAP: door lists are not populated in the reviewed service-stage loop.
- [Metadata exchange](index.html#U02/E30) (E30).

**Kept local:** Run detection and scene enrichment, select the main aircraft and publish metadata. These are responsibilities to decompose, not leaf-policy inputs.

**Attention:** Airplane height replaces normal detection confidence in the output array. Do not treat every fifth numeric field as probability.

### U03 - Tracking and semantic vehicle state

Repository: `cv_trackers`.

- [Worker tracks and paths](index.html#U03/E11) (E11).
- [Vehicle movement and stops](index.html#U03/E08) (E08). General vehicle tracks cover GSE and beltloaders, not every transport class.
- [Beltloader service status](index.html#U03/E09) (E09).
- [Aircraft movement](index.html#U03/E27) (E27).
- [Aircraft arrival context](index.html#U03/E01) (E01).
- [Metadata exchange](index.html#U03/E30) (E30).

**Kept local:** Track identities and movement, assign loader service roles and publish tracking metadata.

**Attention:** Only GSE/BL get general vehicle tracking here; downstream safety-zone still tracks other transport. Serialized private fields tightly couple consumers to implementation versions.

### U04 - Shared CV library

Repository: `cv_common`.

- [CV runtime helpers](index.html#U04/E33) (E33).
- [Vehicle movement and stops](index.html#U04/E08) (E08).
- [Aircraft movement](index.html#U04/E27) (E27).
- [Aircraft arrival context](index.html#U04/E01) (E01).
- [Aircraft departure context](index.html#U04/E02) (E02).
- [Video frames and timing](index.html#U04/E28) (E28).
- [Scene type and image quality](index.html#U04/E26) (E26).
- [Metadata exchange](index.html#U04/E30) (E30).
- [Results and evidence](index.html#U04/E32) (E32).

**Kept local:** Provide reusable library APIs. Availability at the standalone revision does not prove availability at each consumer pin.

**Attention:** Standalone master is not every module dependency. Missing helper imports at selected pins must be resolved deliberately, not via blanket submodule update.

### U05 - Media, artifact, worker and reporting infrastructure

Repository: `db_worker`.

- [Video frames and timing](index.html#U05/E28) (E28). Current worker accepts files and rejects live RTSP/HTTP inputs.
- [Metadata exchange](index.html#U05/E30) (E30). Current joins are positional or arrival-ordered; publication also ignores the supplied frame_id.
- [Job setup and execution](index.html#U05/E31) (E31).
- [Results and evidence](index.html#U05/E32) (E32).

**Kept local:** Supply media and metadata, execute jobs and deliver per-task reports and artifacts.

**Attention:** Replace positional row joins and private filename conventions with explicit identity. Legacy tuple/task-array adapters must preserve multiple results and optional extras.

## Notes

Keep shared component notes separate from task-specific exceptions.

<a id="m01"></a>
### M01 - 3-stop-brake-check

**Module notes / missing components:**


<a id="m02"></a>
### M02 - aircraft-chocks

**M02A task notes:**
<!-- task-notes:M02A:start -->

<!-- task-notes:M02A:end -->

**M02B task notes:**
<!-- task-notes:M02B:start -->

<!-- task-notes:M02B:end -->

**M02C task notes:**
<!-- task-notes:M02C:start -->

<!-- task-notes:M02C:end -->

**Module notes / missing components:**


<a id="m03"></a>
### M03 - all-cargo-bin-doors-opened-and-verified

**Module notes / missing components:**


<a id="m04"></a>
### M04 - beltloader-chocks

**Module notes / missing components:**


<a id="m05"></a>
### M05 - bl_rear_cone

**Module notes / missing components:**


<a id="m06"></a>
### M06 - chocks-and-cones-available-and-staged-for-arrival

**Module notes / missing components:**


<a id="m07"></a>
### M07 - conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed

**Module notes / missing components:**


<a id="m08"></a>
### M08 - cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked

**Module notes / missing components:**


<a id="m09"></a>
### M09 - cones-placed-in-proper-positions-and-timely

**Module notes / missing components:**


<a id="m10"></a>
### M10 - crew-present-10-minutes-prior-to-aircraft-arrival

**Module notes / missing components:**


<a id="m11"></a>
### M11 - fod-walk-completed

**Module notes / missing components:**


<a id="m12"></a>
### M12 - gse-chocks

**Module notes / missing components:**


<a id="m13"></a>
### M13 - hand-signals

**Module notes / missing components:**


<a id="m14"></a>
### M14 - handrails-on-gse-being-used

**Module notes / missing components:**


<a id="m15"></a>
### M15 - lead-marshaller-and-wing-walkers-in-position

**Module notes / missing components:**


<a id="m16"></a>
### M16 - pin-verification

**Module notes / missing components:**


<a id="m17"></a>
### M17 - post-arrival-aircraft-walk-around-inspection-completed-accurately

**Module notes / missing components:**


<a id="m18"></a>
### M18 - pre-arrival-safety-huddle

**Module notes / missing components:**


<a id="m19"></a>
### M19 - pre-departure-walk-around-completed

**Module notes / missing components:**


<a id="m20"></a>
### M20 - pushback-does-not-start-until-wing-walkers-are-in-place-and-ready

**Module notes / missing components:**


<a id="m21"></a>
### M21 - pushback-pathway-confirmed-clear-of-obstacles

**Module notes / missing components:**


<a id="m22"></a>
### M22 - safety-handrails-fully-extended

**Module notes / missing components:**


<a id="m23"></a>
### M23 - safety-vests-secured-to-body

**Module notes / missing components:**


<a id="m24"></a>
### M24 - safety-zone-confirmed-clear

**Module notes / missing components:**


<a id="m26"></a>
### M26 - steering-by-pass-pin-installed-or-steering-otherwise-bypassed

**Module notes / missing components:**


<a id="m27"></a>
### M27 - wing-walkers-in-proper-position-and-using-approved-wands

**Module notes / missing components:**


<a id="u01"></a>
### U01 - camera_software

**Module notes / missing components:**


<a id="u02"></a>
### U02 - general_model

**Module notes / missing components:**


<a id="u03"></a>
### U03 - cv_trackers

**Module notes / missing components:**


<a id="u04"></a>
### U04 - cv_common

**Module notes / missing components:**


<a id="u05"></a>
### U05 - db_worker

**Module notes / missing components:**


## After Your Review

The hierarchy highlights the complete dependency path for each task, with module-specific profiles and infrastructure branches kept distinct.
