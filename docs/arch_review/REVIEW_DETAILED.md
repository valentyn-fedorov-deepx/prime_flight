# Component Review Workbook

Initial inventory: **417 component occurrences across 32 repositories**: 27 downstream repositories implementing **29 checklist tasks**, three upstream repositories and two utilities. Hair Policy is excluded.

The [HTML review](index.html) and [checklist task index](TASKS.md) follow the names and order of the pasted task table. Aircraft-chocks is separated into M02A, M02B and M02C; shared component IDs retain one decision. This workbook keeps its original repository-based decision tables so existing reviews remain compatible.

This is a review worksheet, not a new architecture. Each row describes a meaningful operation, state, input adapter, model, policy or output found in a module. Repeated operations remain separate occurrences. The row count is **not** a proposed service/node count.

## Your Decisions

Edit **Decision** and **Your notes** directly in the tables. Keep IDs and rows intact; reject rather than delete. IDs are frozen for this review. Use one primary decision per row and describe additional changes in the notes. An empty notes cell is intentional.

| Decision | Meaning |
| --- | --- |
| TODO | Not reviewed yet. |
| OK | Accurate, meaningful component at a useful granularity. |
| REJECTED | Do not carry this candidate into the next architecture pass; explain why. |
| MODIFY | Change its responsibility, inputs, output or split/merge boundary; describe the change. |
| GENERALIZE | Broaden it into a reusable capability; say what should become common and what stays local. |
| REPHRASE | Keep the meaning/boundary, but replace the name or description; give the wording. |

**OK does not certify algorithm correctness, runtime readiness, or suitability as a shared service.** A local policy can be OK and still remain entirely inside its leaf module.

Useful notes: preferred name; missing input/output; split into X and Y; merge with an exact row ID; keep this threshold local; share the operation but retain separate model profiles. Put missing components or broader comments in the module notes below its table. Inside table cells, use `<br>` for line breaks and `\|` for a literal pipe.

## Evidence And Scope

Baseline: **2026-09-07**. Source links point to exact committed revisions, including the clean review checkouts selected in the previous audit, not arbitrary dirty working files. Input summaries distinguish consumed upstream facts from locally computed operations. A source range is an inspection anchor, not a runtime test or proof of accuracy.

Unmarked rows describe reviewed code behavior. Special flags are:

- **LIBRARY**: available utility API; actual consumers can pin other revisions.
- **OPTIONAL-OFF**: wired code, disabled in the reviewed default configuration.
- **MISSING-DEPENDENCY**: referenced operation whose required helper is absent at the consumer pin.
- **INPUT-GAP**: implemented operation with an identified gap in its incoming data.
- **STUB**: active placeholder, not a real capability.
- **INACTIVE / INITIALIZATION-ONLY**: retained code or model setup outside the active inference/result path.

Thresholds and assumptions describe current behavior, not endorsed requirements. Meaningful geometry, preprocessing, temporal buffers, identity continuity, observability and result mapping are included. Trivial getters, debug drawing, vendored neural-network internals, training frameworks and test harnesses are not individual components here. This is a static-analysis inventory for correction, not an exhaustiveness or execution guarantee.

## Repository Index

| ID | Repository / Module | Rows |
| --- | --- | ---: |
| M01 | [Beltloader brake checks](#m01) | 9 |
| M02 | [Aircraft wheel chocks](#m02) | 20 |
| M03 | [Cargo-door opening evidence](#m03) | 8 |
| M04 | [Beltloader chocks](#m04) | 9 |
| M05 | [Cone behind beltloader](#m05) | 8 |
| M06 | [Staged cones and chocks](#m06) | 8 |
| M07 | [Conditioned-air removal and stowage](#m07) | 10 |
| M08 | [Cone removal ordering](#m08) | 7 |
| M09 | [Aircraft cone placement](#m09) | 6 |
| M10 | [Pre-arrival crew presence](#m10) | 6 |
| M11 | [Pre-arrival FOD walk](#m11) | 9 |
| M12 | [GSE chocks](#m12) | 17 |
| M13 | [Beltloader hand signals](#m13) | 12 |
| M14 | [Beltloader handrail use](#m14) | 13 |
| M15 | [Arrival marshaller and wing walkers](#m15) | 6 |
| M16 | [Steering-pin verification action](#m16) | 13 |
| M17 | [Post-arrival walk-around](#m17) | 28 |
| M18 | [Pre-arrival safety huddle](#m18) | 10 |
| M19 | [Pre-departure walk-around](#m19) | 29 |
| M20 | [Wing walkers at pushback start](#m20) | 8 |
| M21 | [Pushback pathway clearance](#m21) | 8 |
| M22 | [Beltloader rail extension](#m22) | 8 |
| M23 | [Vest fastening](#m23) | 8 |
| M24 | [Pre-arrival safety-zone clearance](#m24) | 10 |
| M25 | [GSE seat-belt use](#m25) | 13 |
| M26 | [Steering bypass installation](#m26) | 14 |
| M27 | [Wing positions and approved wands](#m27) | 9 |
| U01 | [Camera ingestion and full-turn assembly](#u01) | 21 |
| U02 | [General-model pipeline](#u02) | 23 |
| U03 | [Tracking and semantic vehicle state](#u03) | 15 |
| U04 | [Shared CV library](#u04) | 30 |
| U05 | [Media, artifact, worker and reporting infrastructure](#u05) | 22 |

<a id="m01"></a>
## M01 - Beltloader brake checks

Repository: [3-stop-brake-check @ 3a2337c1](https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/tree/3a2337c18620b1678fb6ecc1aad9014a31a07861).

**Consumed inputs:** GM aircraft/doors/BL/obstacles; BL tracks with optical-flow points, movement state and identity; view configuration.

**Existing output:** One Pass/Fail/Not observed result plus report/timeline; any failed eligible loader causes failure.

**Review caution:** Do not replace its recomputed status with generic tracker status without replay comparison; seconds vary with configured FPS.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M01.01 | TODO | **Metadata and loader-state adapter**<br>GM boxes + serialized BL tracks -> local aircraft, obstacle and Loader state. | [main.py:127][M01.01-1]; [main.py:452][M01.01-2] |  |
| M01.02 | TODO | **Door target and approach vector**<br>Aircraft door history + loader position -> target location and direction toward the aircraft. | [main.py:35][M01.02-1] |  |
| M01.03 | TODO | **Loader eligibility**<br>Box size, track history and target/ROI visibility -> whether this approach can be evaluated. | [main.py:127][M01.03-1]; [main.py:372][M01.03-2] |  |
| M01.04 | TODO | **Local motion replay**<br>Stored optical-flow measurements -> locally recomputed moving/stopped status; does not simply accept upstream tracker status. | [main.py:267][M01.04-1] |  |
| M01.05 | TODO | **Orientation and reversing**<br>Loader motion + target vector + camera view -> approach/reverse evidence; sustained cone-view reverse motion resets progress. | [main.py:288][M01.05-1]; [main.py:210][M01.05-2] |  |
| M01.06 | TODO | **Stop confirmation and counting**<br>Ordered motion history -> debounced stop count; 40-frame stop confirmation and preceding movement requirement. | [main.py:156][M01.06-1]; [local_config.yaml:13][M01.06-2] |  |
| M01.07 | TODO | **Track replacement continuity**<br>Lost/new track state -> inherited approach history rather than a fresh visit. | [main.py:232][M01.07-1]; [main.py:431][M01.07-2] |  |
| M01.08 | TODO | **Brake-check visit policy**<br>Eligible loader stop count -> visit result; more than three stops represents three checks plus final docking. | [main.py:186][M01.08-1]; [main.py:372][M01.08-2] |  |
| M01.09 | TODO | **Multi-visit result and evidence**<br>Evaluated loader visits -> aggregate status, report and timeline; a failed eligible visit can fail the module. | [main.py:388][M01.09-1] |  |

**Module notes / missing components:**


<a id="m02"></a>
## M02 - Aircraft wheel chocks

Repository: [aircraft-chocks @ fa00478f](https://gitlab.com/dxgat/detectors/aircraft-chocks/-/tree/fa00478f4fd64e0eebb7fa0975cdc0f286c60878).

**Consumed inputs:** Pixels; GM chocks, wheels, nose/aircraft, pushback/towbar, cones and transport; worker/GSE/BL/aircraft tracks.

**Existing output:** THREE policy results in order: front_placed, main gear, front_removed, with parallel reports/timelines.

**Review caution:** Front-removed success includes sustained chock presence after attachment; this is ordering evidence, not an explicit removal-edge detector. Preserve multiple task IDs instead of flattening the repository to one result.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M02.01 | TODO | **Wheel detection cleanup**<br>GM wheel boxes -> deduplicated wheel observations. | [main.py:93][M02.01-1] |  |
| M02.02 | TODO | **Frame-sequence selection**<br>Buffered frame/time candidates -> observation sequences for wheel-region comparison. | [main.py:125][M02.02-1] |  |
| M02.03 | TODO | **Pushback reference prepass**<br>Late-turn pushback detections -> median reference box before departure; video is subsequently read again. | [main.py:1241][M02.03-1] |  |
| M02.04 | TODO | **Pushback attachment proxy**<br>Pushback/aircraft proximity history -> attached flag after sustained overlap/proximity, not mechanical coupling detection. | [main.py:1091][M02.04-1]; [main.py:1524][M02.04-2] |  |
| M02.05 | TODO | **Beltloader-clear evidence**<br>Door-associated loader and rear-wheel vehicle histories -> clear/not-clear debounce. | [main.py:1562][M02.05-1] |  |
| M02.06 | TODO | **Rear-wheel assessment phase**<br>Attachment + loader-clear events -> analysis start; returning loader resets the phase. | [main.py:201][M02.06-1] |  |
| M02.07 | TODO | **Wheel localization and clipping**<br>Wheel-box history + image bounds -> stable wheel crop and crop-validity evidence. | [main.py:296][M02.07-1] |  |
| M02.08 | TODO | **Wheel-region obstruction**<br>Obstacles + wheel region over time -> blocked windows and comparison eligibility. | [main.py:330][M02.08-1] |  |
| M02.09 | TODO | **Rear chock assignment**<br>GM chock boxes + rear-wheel ROI -> direct chock-presence evidence. | [main.py:405][M02.09-1] |  |
| M02.10 | TODO | **Before/after frame buffers**<br>Wheel-region images + phase events -> retained baseline and later samples. | [main.py:515][M02.10-1] |  |
| M02.11 | TODO | **Initial wheel-image comparison**<br>Initial buffered wheel crops -> initial difference evidence. | [main.py:571][M02.11-1] |  |
| M02.12 | TODO | **Main wheel-image comparison**<br>Later wheel crops and reference samples -> main temporal difference evidence. | [main.py:659][M02.12-1] |  |
| M02.13 | TODO | **Supporting comparison channel**<br>Additional wheel observations -> support evidence when primary comparison is insufficient. | [main.py:759][M02.13-1] |  |
| M02.14 | TODO | **Difference classifier**<br>Paired/difference wheel imagery -> learned change classification using the aircraft-specific EfficientNet profile. | [main.py:1227][M02.14-1]; [main.py:659][M02.14-2] |  |
| M02.15 | TODO | **Rear-wheel evidence fusion**<br>Direct chocks + image-change channels -> rear-wheel chocking judgment. | [main.py:853][M02.15-1] |  |
| M02.16 | TODO | **Front chock presence and obstruction**<br>Nose-wheel region + chock/obstacle detections -> front presence and visibility histories. | [main.py:953][M02.16-1] |  |
| M02.17 | TODO | **Front placement policy**<br>Arrival time + front presence duration -> placement judgment within the arrival-relative window. | [main.py:1025][M02.17-1] |  |
| M02.18 | TODO | **Front removal policy**<br>Pushback phase + front presence history -> removal-labeled result; current rule does not directly detect a removal edge. | [main.py:1025][M02.18-1]; [main.py:1139][M02.18-2] |  |
| M02.19 | TODO | **Timeout and missing-evidence handling**<br>Incomplete wheel observations + elapsed time -> bounded assessment and unknown evidence. | [main.py:225][M02.19-1]; [main.py:1139][M02.19-2] |  |
| M02.20 | TODO | **Three-result output adapter**<br>Front placement, main-gear and front removal judgments -> ordered module results, reports and timelines. | [main.py:33][M02.20-1]; [main.py:1766][M02.20-2] |  |

### Aircraft-Chocks Checklist Tasks

These are three tasks implemented in one repository, not three copies of all its dependencies. Review shared component IDs once; task-specific comments belong below. The existing M02 module note remains shared across the repository.

<span id="m02a"></span>
#### M02A - Nose gear chocks applied immediately

Arrival. Components: **M02.16, M02.17, M02.19, M02.20**. Uses front-wheel/chock/obstacle observations and aircraft stop time; no pushback or rear-wheel image-difference prerequisite. M02.19 uses the front-placement observability branch; M02.20 supplies output slot 0 (`front_placed`).

**Task notes / missing components:**
<!-- task-notes:M02A:start -->

<!-- task-notes:M02A:end -->

<span id="m02b"></span>
#### M02B - Main gear chocks removed only after aircraft is attached to pushback

Pre-departure. Components: **M02.01 through M02.15, M02.19, M02.20**. Uses rear-wheel pixels/detections, pushback attachment and beltloader clearance. M02.19 uses the rear-wheel timeout/missing-evidence branch; M02.20 supplies output slot 1 (`main_status`).

**Task notes / missing components:**
<!-- task-notes:M02B:start -->

<!-- task-notes:M02B:end -->

<span id="m02c"></span>
#### M02C - Nose wheel chock removed from aircraft

Departure (Tow-Bar disconnect). Components: **M02.03, M02.04, M02.16, M02.18, M02.19, M02.20**. Uses front-wheel/chock history, pushback reference and attachment. M02.19 uses the front-removal observability branch; M02.20 supplies output slot 2 (`front_removed`). Current success uses sustained chock presence after attachment, not a directly detected removal edge.

**Task notes / missing components:**
<!-- task-notes:M02C:start -->

<!-- task-notes:M02C:end -->

**Module notes / missing components:**


<a id="m03"></a>
## M03 - Cargo-door opening evidence

Repository: [all-cargo-bin-doors-opened-and-verified @ ac2707cb](https://gitlab.com/dxgat/detectors/all-cargo-bin-doors-opened-and-verified/-/tree/ac2707cb485e5bedd691fbf8c3d87303373349f5).

**Consumed inputs:** GM front/back door, main aircraft and transport/obstacles; aircraft motion state and camera view.

**Existing output:** One result/report/timeline.

**Review caution:** Does not verify a BL target-door relationship or independently distinguish mechanical open/closed state beyond detector-label semantics.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M03.01 | TODO | **Aircraft and door metadata adapter**<br>GM detections + aircraft tracking state + view -> aircraft, door and obstacle observations. | [main.py:22][M03.01-1] |  |
| M03.02 | TODO | **Arrival and pre-arrival evidence**<br>Aircraft motion/optical-flow history -> arrival proof and whether the approach was visible. | [main.py:155][M03.02-1] |  |
| M03.03 | TODO | **Scene blockage accumulation**<br>Obstacle area over time -> sustained blockage evidence with a clear-frame reset. | [main.py:155][M03.03-1] |  |
| M03.04 | TODO | **Camera-specific cargo-door selection**<br>Cone/wing camera profile + door detections -> relevant front/back door observations. | [main.py:217][M03.04-1] |  |
| M03.05 | TODO | **Door-presence accumulation**<br>Selected door detections -> cumulative visible-frame count; not independent verification of every cargo bin. | [main.py:217][M03.05-1] |  |
| M03.06 | TODO | **Observation completion window**<br>Door evidence and phase -> delayed end of collection after the qualifying period. | [main.py:217][M03.06-1] |  |
| M03.07 | TODO | **Door-opening result policy**<br>Door exposure + arrival/visibility evidence -> Pass, Fail or Not observed with Pass precedence. | [main.py:269][M03.07-1] |  |
| M03.08 | TODO | **Report and timeline adapter**<br>Final judgment + evidence interval -> existing module return format. | [main.py:269][M03.08-1] |  |

**Module notes / missing components:**


<a id="m04"></a>
## M04 - Beltloader chocks

Repository: [beltloader-chocks @ 7056099b](https://gitlab.com/dxgat/detectors/beltloader-chocks/-/tree/7056099b498dae42ae53e20d29fd9241f6a05939).

**Consumed inputs:** GM chocks/aircraft parts; BL tracks, front/back role and camera/aircraft layout.

**Existing output:** One result; all confirmed eligible visits must latch chocked; no visits is Not observed.

**Review caution:** A one-time chock latch does not prove continuous chocking throughout the entire parked interval.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M04.01 | TODO | **Detection and track adapter**<br>GM boxes + BL track payload + aircraft state -> typed local observations. | [main.py:169][M04.01-1] |  |
| M04.02 | TODO | **Active loader and door-role selection**<br>Loader/aircraft-part geometry -> front/back service-loader assignment with part-based fallback. | [main.py:232][M04.02-1] |  |
| M04.03 | TODO | **Loader track handover**<br>New track near a recent loader -> retained visit history within the configured frame gap. | [main.py:267][M04.03-1] |  |
| M04.04 | TODO | **Loader parking history**<br>Box overlap and movement history -> stabilized stopped loader and minimum-stay eligibility. | [main.py:69][M04.04-1] |  |
| M04.05 | TODO | **View-specific chock region**<br>Loader bounds + view + aircraft type -> expected chock ROI. | [main.py:98][M04.05-1] |  |
| M04.06 | TODO | **Chock presence accumulator**<br>Chocks intersecting the ROI -> decaying evidence counter and latched chocked state. | [main.py:134][M04.06-1] |  |
| M04.07 | TODO | **Scene layout sampling**<br>Aircraft/loader layout observations -> representative geometry used for chock assessment. | [main.py:326][M04.07-1] |  |
| M04.08 | TODO | **Lost-loader lifecycle**<br>Last-seen frame and track state -> stale loader finalization. | [main.py:309][M04.08-1] |  |
| M04.09 | TODO | **All-visit chocking result**<br>Eligible loader visits -> module report and timeline; each relevant visit contributes. | [main.py:23][M04.09-1] |  |

**Module notes / missing components:**


<a id="m05"></a>
## M05 - Cone behind beltloader

Repository: [bl_rear_cone @ d75f1f8b](https://gitlab.com/dxgat/detectors/bl_rear_cone/-/tree/d75f1f8b026c0a12645f8792bb35a139554df7de).

**Consumed inputs:** GM cones/doors/aircraft parts; BL tracks and role/view context.

**Existing output:** One result; all confirmed eligible BL visits must be coned.

**Review caution:** Checklist and code thresholds differ; preserve code behavior as the migration baseline, then approve requirement changes separately.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M05.01 | TODO | **Detection and track adapter**<br>GM boxes + loader track state + aircraft state -> local cone, loader and layout observations. | [main.py:199][M05.01-1] |  |
| M05.02 | TODO | **Service-loader selection**<br>Door/aircraft geometry + tracked BLs -> relevant front/back loader. | [main.py:262][M05.02-1] |  |
| M05.03 | TODO | **Loader lifecycle and continuity**<br>Current and previous loader tracks -> persistent visit state and expired visits. | [main.py:297][M05.03-1] |  |
| M05.04 | TODO | **Parking and stay qualification**<br>Loader box/motion history -> stable parked visit after the minimum stay. | [main.py:72][M05.04-1] |  |
| M05.05 | TODO | **Loader viewing-direction classifier**<br>Loader/aircraft geometry -> side/enface profile used by the ROI calculation. | [main.py:100][M05.05-1] |  |
| M05.06 | TODO | **Rear safety-cone ROI**<br>Loader bounds and view profile -> expected region behind the loader. | [main.py:129][M05.06-1] |  |
| M05.07 | TODO | **Cone-footpoint persistence**<br>Cone bottom point in rear ROI -> consecutive-frame confirmation and latched cone-present state. | [main.py:163][M05.07-1] |  |
| M05.08 | TODO | **All-visit cone result**<br>Qualified loader visits and confirmed cones -> aggregate report and timeline. | [main.py:23][M05.08-1] |  |

**Module notes / missing components:**


<a id="m06"></a>
## M06 - Staged cones and chocks

Repository: [chocks-and-cones-available-and-staged-for-arrival @ 1413225f](https://gitlab.com/dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival/-/tree/1413225fbbb9c4e7e04be82f9d5aa8f96ad2e379).

**Consumed inputs:** GM cones/chocks and transport/obstacles; aircraft tracks/motion; metadata sufficient for central counting logic.

**Existing output:** Staged-equipment compliance result/report/timeline.

**Review caution:** YAML 6/4 counts are not the active main-code 7/6 counts. Do not assume every configuration value controls behavior.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M06.01 | TODO | **Aircraft motion-state adapter**<br>Tracked aircraft state -> local motion/arrival context. | [main.py:21][M06.01-1] |  |
| M06.02 | TODO | **Relevant equipment observations**<br>GM cones, chocks and vehicles -> size-filtered staged-equipment candidates. | [main.py:40][M06.02-1] |  |
| M06.03 | TODO | **Arrival and approach visibility**<br>Aircraft history + optical flow -> arrival proof and pre-arrival collection eligibility. | [main.py:100][M06.03-1] |  |
| M06.04 | TODO | **Transport-carried chock exclusion**<br>Chock positions + vehicle boxes -> chocks considered on the ground rather than on transport. | [main.py:184][M06.04-1] |  |
| M06.05 | TODO | **Equipment-count exposure**<br>Ground chocks and cones per frame -> cumulative qualifying exposure; active code uses at least seven cones and six chocks. | [main.py:195][M06.05-1] |  |
| M06.06 | TODO | **Pre-arrival window closure**<br>First confirmed arrival -> stop collecting staging evidence. | [main.py:179][M06.06-1] |  |
| M06.07 | TODO | **Visibility and staging decision**<br>Count exposure + pre-arrival/blocked evidence -> staged-equipment result. | [main.py:265][M06.07-1] |  |
| M06.08 | TODO | **Evidence timeline**<br>Decision and selected frame bounds -> report interval in the downstream format. | [main.py:285][M06.08-1] |  |

**Module notes / missing components:**


<a id="m07"></a>
## M07 - Conditioned-air removal and stowage

Repository: [conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed @ 940fdfc5](https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/tree/940fdfc526f83839573434a6ee96d955a7f3d6cd).

**Consumed inputs:** Pixels; GM nose/pushback and aircraft motion; full hose history and departure time.

**Existing output:** Combined decision with separate removal/stowage evidence in the internal decision routine and report.

**Review caution:** Held boxes are counted repeatedly in current history. Evidence is a visual area/position proxy, not an observed disconnected coupling.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M07.01 | TODO | **Sparse hose object detection**<br>Video frames -> conditioned-air hose boxes from best28_full.onnx, sampled every 40 frames. | [main.py:280][M07.01-1] |  |
| M07.02 | TODO | **Held observations and history**<br>Last hose detection + nose/pushback boxes -> per-frame histories; held results are not independent model samples. | [main.py:308][M07.02-1] |  |
| M07.03 | TODO | **Coverage eligibility**<br>Hose and nose history lengths -> whether enough observations exist; threshold counts include held samples. | [main.py:24][M07.03-1]; [main.py:89][M07.03-2] |  |
| M07.04 | TODO | **Departure-relative assessment window**<br>Aircraft stop/departure times -> full window ending ten minutes before departure or short-turn fallback. | [main.py:43][M07.04-1] |  |
| M07.05 | TODO | **Hose-use evidence**<br>Hose box areas in first/interior periods + nose relation -> apparent deployment/use of the hose. | [main.py:104][M07.05-1]; [main.py:191][M07.05-2] |  |
| M07.06 | TODO | **Return-to-stowed appearance**<br>First-minute baseline and final-minute hose areas -> return within the configured 30 percent range. | [main.py:138][M07.06-1] |  |
| M07.07 | TODO | **Pushback occlusion exception**<br>Final hose location + nearest-time pushback box -> partial-overlap Not observed outcome. | [main.py:159][M07.07-1] |  |
| M07.08 | TODO | **Removal versus stow sub-decisions**<br>Deployment and final area change -> separate internal removal/stow judgments, including late-removal failure. | [main.py:169][M07.08-1] |  |
| M07.09 | TODO | **Short-turn policy**<br>Less than ten minutes of stopped time + hose/nose relation -> failure or unobserved fallback. | [main.py:43][M07.09-1] |  |
| M07.10 | TODO | **Combined result adapter**<br>Internal sub-decisions + departure availability -> combined returned judgment and timeline. | [main.py:227][M07.10-1]; [main.py:429][M07.10-2] |  |

**Module notes / missing components:**


<a id="m08"></a>
## M08 - Cone removal ordering

Repository: [cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked @ e2a25ba3](https://gitlab.com/dxgat/detectors/cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked/-/tree/e2a25ba3e97ceb403fcde512e78e8368e83d3aee).

**Consumed inputs:** GM wing/engine/tail cones, wheels/aircraft parts and obstacles; BL/aircraft tracks.

**Existing output:** One result/report/timeline.

**Review caution:** Despite its name it does NOT test whether GSE is chocked, and its equipment coverage is narrower than all GSE. A chocked prerequisite is new functional work.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M08.01 | TODO | **Aircraft layout history**<br>Door and aircraft-part detections -> layout used to associate cones and equipment. | [main.py:31][M08.01-1] |  |
| M08.02 | TODO | **Typed cone confirmation**<br>Cone type + consecutive detections -> confirmed cone and last-seen time. | [main.py:199][M08.02-1] |  |
| M08.03 | TODO | **Relevant equipment proximity**<br>Loader/equipment locations + aircraft layout -> nearby-equipment presence history; not a complete all-GSE inventory. | [main.py:215][M08.03-1] |  |
| M08.04 | TODO | **Cone occluder association**<br>Obstacle overlap + recent obstacle state -> retained obstruction evidence around a cone. | [main.py:275][M08.04-1] |  |
| M08.05 | TODO | **Last-seen event comparison**<br>Last relevant cone and transport observations -> whether cones persisted until equipment was clear. | [main.py:338][M08.05-1] |  |
| M08.06 | TODO | **Departure and observability gate**<br>Missing departure or obscured cone disappearance -> Not observed instead of an unsupported ordering judgment. | [main.py:338][M08.06-1] |  |
| M08.07 | TODO | **Removal-order output**<br>Ordering/visibility judgment -> report and timeline; GSE chocked state is not actually tested. | [main.py:338][M08.07-1] |  |

**Module notes / missing components:**


<a id="m09"></a>
## M09 - Aircraft cone placement

Repository: [cones-placed-in-proper-positions-and-timely @ b2c53f69](https://gitlab.com/dxgat/detectors/cones-placed-in-proper-positions-and-timely/-/tree/b2c53f69c29610fae5c83d748e64592fcbc43408).

**Consumed inputs:** GM typed wing/engine/tail cones, aircraft and transport obstacles; camera/aircraft type.

**Existing output:** One policy; normal return also contains counters/stage data (five values versus three on early paths).

**Review caution:** Obstacle report text says 40% while code tests 65%; inconsistent return arity requires an explicit legacy adapter.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M09.01 | TODO | **Cone-role requirement profile**<br>Camera view + aircraft type -> required engine/wing/tail cone roles and counts. | [main.py:140][M09.01-1] |  |
| M09.02 | TODO | **Scene and typed-cone observations**<br>GM cone labels + aircraft/obstacle metadata -> per-role observations; no extra cone model in the active decision path. | [main.py:148][M09.02-1] |  |
| M09.03 | TODO | **Role-presence exposure**<br>Per-role cone detections -> cumulative evidence exceeding the frame threshold. | [main.py:262][M09.03-1] |  |
| M09.04 | TODO | **Per-role placement result**<br>Required roles + accumulated cone evidence -> role-level placement assessment. | [main.py:77][M09.04-1] |  |
| M09.05 | TODO | **Arrival and scene visibility**<br>Arrival evidence, blocked fraction and off-frame tail -> whether missing cones can be judged. | [main.py:312][M09.05-1] |  |
| M09.06 | TODO | **Result and return-shape adapter**<br>Role judgments + observability -> report/timeline; normal and early-return shapes currently differ. | [main.py:312][M09.06-1] |  |

**Module notes / missing components:**


<a id="m10"></a>
## M10 - Pre-arrival crew presence

Repository: [crew-present-10-minutes-prior-to-aircraft-arrival @ 5cfd25c9](https://gitlab.com/dxgat/detectors/crew-present-10-minutes-prior-to-aircraft-arrival/-/tree/5cfd25c92c4a9765817505684ebcc3e4bb4755a2).

**Consumed inputs:** GM person counts and transport obstacles; aircraft arrival/motion; clip start time.

**Existing output:** One result/report/timeline based on crew exposure in the eligible window.

**Review caution:** This measures counts over a window, not continuous presence of the same three named workers for ten minutes.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M10.01 | TODO | **Crew-count observation**<br>GM person detections -> frame-level crew count; not proof of unique staff identities or roles. | [main.py:29][M10.01-1]; [main.py:211][M10.01-2] |  |
| M10.02 | TODO | **Arrival and usable pre-arrival evidence**<br>Aircraft motion + obstacle history -> arrival reference and usable crew observations. | [main.py:155][M10.02-1] |  |
| M10.03 | TODO | **Arrival-relative crew window**<br>Arrival time and video coverage -> nominal minus-12 to minus-8 minute window, with a shorter-clip fallback. | [main.py:224][M10.03-1] |  |
| M10.04 | TODO | **Crew exposure accumulator**<br>Frames with at least three people -> accumulated qualifying duration in the selected window. | [main.py:224][M10.04-1] |  |
| M10.05 | TODO | **Short/blocked observation policy**<br>Insufficient pre-arrival footage or excessive obstruction -> Not observed. | [main.py:224][M10.05-1] |  |
| M10.06 | TODO | **Crew-presence result and timeline**<br>Qualifying exposure above ten seconds + visibility -> final crew result and evidence interval. | [main.py:259][M10.06-1] |  |

**Module notes / missing components:**


<a id="m11"></a>
## M11 - Pre-arrival FOD walk

Repository: [fod-walk-completed @ b923b5c8](https://gitlab.com/dxgat/detectors/fod-walk-completed/-/tree/b923b5c830a6520626fc039609af33f988699bff).

**Consumed inputs:** Pixels; worker tracks, GM aircraft/front wheel/parts and vehicle detections; approach trajectory.

**Existing output:** One result/report/timeline.

**Review caution:** Not the simple horizontal-crossing rule in the basic description; bbox-derived scale is not calibrated physical distance.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M11.01 | TODO | **Worker and vehicle filtering**<br>Person tracks + vehicle boxes + phase -> pre-arrival workers excluding likely vehicle occupants. | [main.py:422][M11.01-1] |  |
| M11.02 | TODO | **Person pose estimation**<br>Worker image crops -> MoveNet Thunder body landmarks used by walking-direction analysis. | [main.py:286][M11.02-1]; [main.py:422][M11.02-2] |  |
| M11.03 | TODO | **Camera-specific pseudo-depth**<br>Person box height and camera profile -> approximate relative depth, not calibrated metric depth. | [main.py:30][M11.03-1] |  |
| M11.04 | TODO | **Worker facing direction**<br>Pose landmarks and trajectory observations -> facing/orientation evidence for a candidate walk. | [main.py:179][M11.04-1] |  |
| M11.05 | TODO | **Aircraft approach corridor**<br>Aircraft/front-wheel history -> retrospective inspection corridor and approach reference direction. | [main.py:112][M11.05-1] |  |
| M11.06 | TODO | **Worker trajectory collection**<br>Pre-arrival worker identities and positions -> time-ordered candidate paths. | [main.py:422][M11.06-1] |  |
| M11.07 | TODO | **Corridor traversal test**<br>Worker path + corridor endpoints -> duration, endpoint-coverage and directional checks. | [main.py:179][M11.07-1] |  |
| M11.08 | TODO | **Arrival/visibility eligibility**<br>Arrival proof + blocked fraction -> whether a missing FOD walk is assessable. | [main.py:488][M11.08-1] |  |
| M11.09 | TODO | **FOD-walk result and evidence**<br>Accepted traversals + observation quality -> module decision and selected walk evidence. | [main.py:44][M11.09-1]; [main.py:488][M11.09-2] |  |

**Module notes / missing components:**


<a id="m12"></a>
## M12 - GSE chocks

Repository: [gse-chocks @ 3160b871](https://gitlab.com/dxgat/detectors/gse-chocks/-/tree/3160b871f5130f206323b9398fb1233d6b07ed2c).

**Consumed inputs:** Pixels; GSE tracks/motion, GM chocks, persons, BL and occluding transport/objects.

**Existing output:** Per-GSE stop evidence aggregated to module result; failed eligible cases cause failure.

**Review caution:** Different chock evidence channels have different semantics; current truthy fusion must be made explicit before sharing.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M12.01 | TODO | **Vehicle motion measurement**<br>Vehicle crops, feature points and frame history -> optical-flow motion measurements. | [main.py:144][M12.01-1] |  |
| M12.02 | TODO | **Orientation-window estimation**<br>Recent motion windows -> vehicle orientation used to choose wheel and action profiles. | [main.py:233][M12.02-1] |  |
| M12.03 | TODO | **Vehicle eligibility and clipping**<br>Vehicle box dimensions + image bounds -> usable vehicle ROI and minimum-size eligibility. | [main.py:353][M12.03-1] |  |
| M12.04 | TODO | **Parking episode confirmation**<br>Vehicle motion history -> parked state after the required stationary duration. | [main.py:399][M12.04-1] |  |
| M12.05 | TODO | **Rider/worker association**<br>Person positions + vehicle geometry -> occupants versus external workers. | [main.py:415][M12.05-1] |  |
| M12.06 | TODO | **Wheel-region construction**<br>Vehicle orientation and box -> expected chock/wheel analysis region. | [main.py:473][M12.06-1] |  |
| M12.07 | TODO | **Direct chock persistence**<br>Chocks in the wheel region -> consecutive confirmation of placed chocks. | [main.py:497][M12.07-1] |  |
| M12.08 | TODO | **Worker action ROI**<br>Vehicle geometry + worker trajectory -> eligible wheel-interaction observations. | [main.py:536][M12.08-1] |  |
| M12.09 | TODO | **Worker pose estimation**<br>Person crops -> RTMPose landmarks for bending/action evidence. | [main.py:1354][M12.09-1]; [main.py:587][M12.09-2] |  |
| M12.10 | TODO | **Bending/placement heuristic**<br>Worker height change, feet stability and pose confidence -> candidate chock-placement action. | [main.py:587][M12.10-1] |  |
| M12.11 | TODO | **Negative action and visibility evidence**<br>Observable worker activity without qualifying action -> negative/unknown action channel. | [main.py:656][M12.11-1] |  |
| M12.12 | TODO | **Obstruction history**<br>Wheel ROI + obstacles -> retained visibility and comparable obstacle states. | [main.py:799][M12.12-1] |  |
| M12.13 | TODO | **Reference-image buffering**<br>Vehicle stop/departure and wheel crops -> before/after sample buffers. | [main.py:896][M12.13-1]; [main.py:1132][M12.13-2] |  |
| M12.14 | TODO | **Learned wheel-change comparison**<br>Reference and later wheel imagery -> difference-classifier evidence using the GSE-specific model profile. | [main.py:1028][M12.14-1]; [main.py:1354][M12.14-2] |  |
| M12.15 | TODO | **Assessment timeout**<br>Unfinished vehicle evidence + elapsed frames -> close the assessment window. | [main.py:1251][M12.15-1] |  |
| M12.16 | TODO | **View-dependent evidence fusion**<br>Direct chocks, action and image-change channels + orientation -> vehicle chocking judgment. | [main.py:1313][M12.16-1] |  |
| M12.17 | TODO | **Vehicle-result aggregation**<br>Eligible vehicle judgments -> report and timeline, preserving unobservable cases. | [main.py:27][M12.17-1] |  |

**Module notes / missing components:**


<a id="m13"></a>
## M13 - Beltloader hand signals

Repository: [hand-signals @ 6bd027f2](https://gitlab.com/dxgat/detectors/hand-signals/-/tree/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9).

**Consumed inputs:** Pixels; workers/BL/aircraft tracks, doors and obstacle detections; stop episodes and view/layout.

**Existing output:** One result over observable eligible BL visits; unobservable visits can be omitted when others qualify.

**Review caution:** Raised wrists are a coarse gesture proxy, not an approved signal vocabulary. Same HRNet checkpoint as steering does not imply same crop preprocessing.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M13.01 | TODO | **Pose-crop preprocessing**<br>Worker crop -> contrast-adjusted image using CLAHE. | [main.py:43][M13.01-1] |  |
| M13.02 | TODO | **Body pose estimation**<br>Prepared worker crops -> HRNet body landmarks and scores. | [main.py:29][M13.02-1]; [main.py:53][M13.02-2] |  |
| M13.03 | TODO | **Aircraft door reference prepass**<br>Door detections over the video -> representative docking geometry before main processing. | [main.py:762][M13.03-1] |  |
| M13.04 | TODO | **Service-loader state and selection**<br>GM loader boxes + tracks + aircraft layout -> active approach/docking loader state. | [main.py:248][M13.04-1]; [main.py:391][M13.04-2] |  |
| M13.05 | TODO | **Helper-person interaction region**<br>Loader geometry + worker boxes -> helper ROI and worker candidates. | [main.py:140][M13.05-1] |  |
| M13.06 | TODO | **Worker observation eligibility**<br>Person history and geometry -> eligible helper observations. | [main.py:202][M13.06-1] |  |
| M13.07 | TODO | **Pose/history buffering**<br>Eligible worker frames -> persisted landmarks and worker histories around a loader stop. | [main.py:338][M13.07-1]; [main.py:522][M13.07-2] |  |
| M13.08 | TODO | **Helper selection and signal window**<br>Persistent nearby workers + loader stop time -> candidate helper and minus-30 to minus-5 second window. | [main.py:276][M13.08-1] |  |
| M13.09 | TODO | **Raised-arm signal heuristic**<br>Wrist/elbow landmarks over the window -> sustained raised-arm evidence; not classification of a signal vocabulary. | [main.py:276][M13.09-1] |  |
| M13.10 | TODO | **Loader identity handover and expiry**<br>Current/new/lost loader tracks -> continuous visit state and finalized visits. | [main.py:606][M13.10-1] |  |
| M13.11 | TODO | **Layout and ROI-coverage sampling**<br>Aircraft/loader geometry -> saved layout and ROI coverage; coverage argument does not itself gate the signal check. | [main.py:675][M13.11-1]; [main.py:276][M13.11-2] |  |
| M13.12 | TODO | **Visit result aggregation**<br>Signal observations by loader visit -> report/timeline; unknown visits may be omitted when others are observable. | [main.py:73][M13.12-1] |  |

**Module notes / missing components:**


<a id="m14"></a>
## M14 - Beltloader handrail use

Repository: [handrails-on-gse-being-used @ 59fbced4](https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/tree/59fbced4161066945fdde6d45ee5a82132dde33b).

**Consumed inputs:** Pixels; workers and BL tracks, aircraft/door/engine/wheel context, transport/person occluders.

**Existing output:** Pass when all evaluated climbers have contact plus positive coverage; Fail for a sufficiently covered non-contact case; none evaluated is Not observed.

**Review caution:** Whole-body hands are required; do not substitute body-only pose. Unknown climbers are excluded rather than forcing global unknown in current aggregation.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M14.01 | TODO | **Loader view classification**<br>Loader and aircraft geometry -> viewing profile for rail-use analysis. | [main.py:110][M14.01-1] |  |
| M14.02 | TODO | **Rail-extension appearance classifier**<br>Loader image crop -> extended-rail evidence from an EfficientNet profile. | [main.py:589][M14.02-1] |  |
| M14.03 | TODO | **Rail segmentation**<br>Loader imagery -> SegFormer rail mask. | [main.py:137][M14.03-1]; [main.py:589][M14.03-2] |  |
| M14.04 | TODO | **Rail mask coordinate mapping**<br>Crop-local rail mask + loader bounds -> full-frame rail geometry. | [main.py:154][M14.04-1] |  |
| M14.05 | TODO | **Climber-to-loader association**<br>Worker boxes/feet + loader region -> people currently using this loader. | [main.py:230][M14.05-1] |  |
| M14.06 | TODO | **Whole-body/hand pose estimation**<br>Associated person crops -> DWPose landmarks, including hand keypoints. | [main.py:248][M14.06-1]; [main.py:589][M14.06-2] |  |
| M14.07 | TODO | **Feet and hand visibility**<br>Pose scores + crop geometry -> usable feet and selected hands. | [main.py:261][M14.07-1] |  |
| M14.08 | TODO | **Geometric hand-to-rail contact**<br>Hand trajectory + rail mask/line geometry -> temporally confirmed proximity/contact evidence. | [main.py:303][M14.08-1]; [main.py:530][M14.08-2] |  |
| M14.09 | TODO | **Climb observation coverage**<br>Person/rail visibility over a climb -> completeness of evaluable contact history. | [main.py:363][M14.09-1] |  |
| M14.10 | TODO | **Hand-contact appearance fallback**<br>Hand/rail patches -> contact classification when direct geometric evidence is insufficient. | [main.py:457][M14.10-1]; [main.py:589][M14.10-2] |  |
| M14.11 | TODO | **Deferred contact assessment**<br>Previously unobservable climb samples + later evidence -> delayed contact assessment. | [main.py:425][M14.11-1] |  |
| M14.12 | TODO | **Active-loader phase gate**<br>Aircraft phase and loader tracks -> visits on which to run rail-use analysis. | [main.py:663][M14.12-1] |  |
| M14.13 | TODO | **Climber and visit aggregation**<br>Observable climber contact results -> module report; unobserved climbers are not equivalent to proved compliance. | [main.py:28][M14.13-1] |  |

**Module notes / missing components:**


<a id="m15"></a>
## M15 - Arrival marshaller and wing walkers

Repository: [lead-marshaller-and-wing-walkers-in-position @ 9b37ccff](https://gitlab.com/dxgat/detectors/lead-marshaller-and-wing-walkers-in-position/-/tree/9b37ccffc380093f506bf0507919437b336aa172).

**Consumed inputs:** GM aircraft parts/people/obstacles and aircraft/worker tracks; arrival motion.

**Existing output:** One role-position result/report/timeline.

**Review caution:** No separate pose/wand model or lead-marshaller signal proof on the active path.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M15.01 | TODO | **Arrival-window observation collection**<br>GM persons/aircraft parts + tracked movement -> candidate arrival-period worker histories. | [main.py:286][M15.01-1] |  |
| M15.02 | TODO | **Worker movement representation**<br>Worker paths + camera-dependent geometry -> smoothed movement direction and relative travel estimates. | [main.py:43][M15.02-1] |  |
| M15.03 | TODO | **Wing-walker path qualification**<br>Worker movement vectors -> minimum-length and direction-compatible paths. | [main.py:43][M15.03-1] |  |
| M15.04 | TODO | **Opposite-side position test**<br>Qualified worker paths + aircraft reference geometry -> evidence of walkers on both sides. | [main.py:70][M15.04-1] |  |
| M15.05 | TODO | **Approach visibility and blockage**<br>Aircraft parts, arrival coverage and blocked fraction -> whether positions can be assessed. | [main.py:125][M15.05-1] |  |
| M15.06 | TODO | **Position result and evidence**<br>Qualified side coverage + observability -> result/report; no separate lead-marshaller gesture recognizer is implemented. | [main.py:125][M15.06-1] |  |

**Module notes / missing components:**


<a id="m16"></a>
## M16 - Steering-pin verification action

Repository: [pin-verification @ 8e1863c7](https://gitlab.com/dxgat/detectors/pin-verification/-/tree/8e1863c76bb97f9818e935e10d58f877637ed1c1).

**Consumed inputs:** Pixels; worker/aircraft tracks, nose wheel/pushback/aircraft and obstacles; departure and attachment evidence.

**Existing output:** One verification result/report/timeline.

**Review caution:** Measures a verification-like worker action, not direct pin visibility. Current 1.5/2.5-second criteria differ from the supplied description.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M16.01 | TODO | **Aircraft-part history**<br>GM aircraft parts -> reference layout for nose-wheel and pushback regions. | [main.py:50][M16.01-1] |  |
| M16.02 | TODO | **Pushback and wheel interaction regions**<br>Aircraft reference layout -> expected pushback and nose-wheel ROIs. | [main.py:64][M16.02-1] |  |
| M16.03 | TODO | **Late-turn pushback reference prepass**<br>Pushback boxes before departure -> median reference location; requires whole-video lookahead. | [main.py:505][M16.03-1] |  |
| M16.04 | TODO | **Wheel localization**<br>Wheel detections and recent geometry -> wheel region used for person interaction. | [main.py:435][M16.04-1] |  |
| M16.05 | TODO | **Worker-to-wheel association**<br>Worker position + wheel ROI -> candidates near the nose wheel. | [main.py:174][M16.05-1] |  |
| M16.06 | TODO | **Body pose estimation**<br>Candidate worker crop -> SimCC body landmarks and confidences. | [main.py:496][M16.06-1]; [main.py:236][M16.06-2] |  |
| M16.07 | TODO | **Bend/sit interaction evidence**<br>Worker landmarks over time -> sufficiently sustained bending or sitting near the wheel. | [main.py:236][M16.07-1] |  |
| M16.08 | TODO | **Raised-hands verification evidence**<br>Upright pose, raised hands and ankle stability -> sustained verification-like gesture. | [main.py:236][M16.08-1]; [main.py:349][M16.08-2] |  |
| M16.09 | TODO | **Action-state persistence**<br>Recent pose evidence and missing observations -> decayed persistent action state. | [main.py:299][M16.09-1] |  |
| M16.10 | TODO | **Pushback attachment proxy**<br>Pushback candidate/aircraft overlap over time -> attachment phase after sustained proximity. | [main.py:466][M16.10-1]; [main.py:663][M16.10-2] |  |
| M16.11 | TODO | **Departure-relative action cutoff**<br>Departure time -> stop accepting verification evidence ten seconds before departure. | [main.py:755][M16.11-1] |  |
| M16.12 | TODO | **Wheel/action observability**<br>Missing wheel duration, obstacles and pushback overlap -> Not observed reasons. | [main.py:894][M16.12-1] |  |
| M16.13 | TODO | **Pin-verification policy and output**<br>Wheel-interaction/gesture evidence + eligibility -> verification result; there is no visual pin-presence detector here. | [main.py:894][M16.13-1] |  |

**Module notes / missing components:**


<a id="m17"></a>
## M17 - Post-arrival walk-around

Repository: [post-arrival-aircraft-walk-around-inspection-completed-accurately @ a0d9ee4f](https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/tree/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2).

**Consumed inputs:** Pixels, workers/BL/aircraft tracks and aircraft-part detections; camera/layout and arrival/loading gates.

**Existing output:** Result, report/timeline and technical evidence (canvases/CSV/JSON).

**Review caution:** Post-arrival rescue/outlier options are disabled by default. Score-derived confidence is not demonstrated calibrated probability; required cached geometry must exist.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M17.01 | TODO | **Frame/metadata dispatch**<br>Video frames + GM/track metadata -> synchronized inputs to state managers and walk analysis. | [main.py:35][M17.01-1] |  |
| M17.02 | TODO | **Detection coordinate normalization**<br>Detection coordinates and image dimensions -> normalized local detection format. | [code/utils/detection_preprocessor.py:11][M17.02-1] |  |
| M17.03 | TODO | **Aircraft phase state**<br>Aircraft movement history -> arrival/stopped/departure state used by the walk gate. | [code/states.py:31][M17.03-1] |  |
| M17.04 | TODO | **Loader service state**<br>Tracked loaders + aircraft geometry -> loader approach, docking and loading state. | [code/states.py:112][M17.04-1] |  |
| M17.05 | TODO | **Post-arrival observation window**<br>Arrival + loader service state + duration limit -> inspection window ending at loading or timeout. | [code/states.py:312][M17.05-1] |  |
| M17.06 | TODO | **Body pose estimation**<br>Worker image crops -> YOLO pose landmarks for worker localization. | [code/walk_around/_pose_model.py:18][M17.06-1] |  |
| M17.07 | TODO | **Person-ground coordinate estimation**<br>Worker pose/bounds + camera assumptions -> estimated person ground coordinates. | [code/walk_around/distance_estimator.py:56][M17.07-1]; [code/walk_around/distance_estimator.py:243][M17.07-2] |  |
| M17.08 | TODO | **Worker trajectory observation adapter**<br>Worker detections/IDs -> time-stamped trajectory points. | [code/walk_around/detection_processor.py:34][M17.08-1] |  |
| M17.09 | TODO | **Aircraft-part reference storage**<br>Part detections over time -> retained aircraft reference geometry. | [code/walk_around/temp/airplane_parts_container.py:49][M17.09-1] |  |
| M17.10 | TODO | **Aircraft top-down reference sampling**<br>Aircraft imagery and part detections -> selected samples for top-down reconstruction. | [code/walk_around/temp/plane_tdv_extractor.py:109][M17.10-1] |  |
| M17.11 | TODO | **Scene depth inference**<br>Selected imagery -> depth map from the configured depth model. | [code/walk_around/temp/plane_tdv_extractor.py:65][M17.11-1]; [code/walk_around/temp/plane_tdv_extractor.py:159][M17.11-2] |  |
| M17.12 | TODO | **Aircraft-body segmentation**<br>Aircraft image and geometric prompts -> selected body mask using MobileSAM and mask processing. | [code/walk_around/temp/plane_tdv_extractor.py:163][M17.12-1] |  |
| M17.13 | TODO | **Top-down aircraft reconstruction**<br>Body mask, depth and camera parameters -> aircraft top-down template. | [code/walk_around/temp/plane_tdv_extractor.py:313][M17.13-1] |  |
| M17.14 | TODO | **Inspection-region blockage**<br>Obstacles in the inspection view -> blocked-frame coverage. | [code/walk_around/walk_around.py:201][M17.14-1] |  |
| M17.15 | TODO | **Trajectory window finalization**<br>Buffered person tracks + inspection bounds -> trimmed completed trajectories for batch analysis. | [code/walk_around/walk_around.py:276][M17.15-1] |  |
| M17.16 | TODO | **Spatial outlier removal**<br>Person trajectories + allowed spatial range -> paths with distant observations removed. | [code/walk_around/preprocessing/preprocessing.py:22][M17.16-1]; [code/walk_around/walk_around.py:531][M17.16-2] |  |
| M17.17 | TODO | **Trajectory coordinate/distance adjustment**<br>Raw path coordinates and distance profile -> adjusted path geometry. | [code/walk_around/preprocessing/preprocessing.py:121][M17.17-1]; [code/walk_around/walk_around.py:531][M17.17-2] |  |
| M17.18 | TODO | **Trajectory smoothing**<br>Noisy person coordinates -> smoothed trajectory samples. | [code/walk_around/preprocessing/preprocessing.py:66][M17.18-1]; [code/walk_around/walk_around.py:531][M17.18-2] |  |
| M17.19 | TODO | **Gap flattening**<br>Fragmented trajectory segments -> reduced discontinuities according to spatial/temporal limits. | [code/walk_around/preprocessing/preprocessing.py:140][M17.19-1] |  |
| M17.20 | TODO | **Trajectory splitting**<br>Path observations with discontinuities -> candidate coherent segments. | [code/walk_around/preprocessing/splitter.py:14][M17.20-1]; [code/walk_around/preprocessing/splitter.py:68][M17.20-2] |  |
| M17.21 | TODO | **Fragment compatibility and recombination**<br>Time/spatially compatible path segments -> candidate combined inspection trajectories. | [code/walk_around/preprocessing/recombination.py:48][M17.21-1]; [code/walk_around/preprocessing/recombination.py:177][M17.21-2] |  |
| M17.22 | TODO | **Trajectory-to-image encoding**<br>Recombined paths + aircraft template -> classifier canvases; these images are model inputs, not just debug plots. | [code/walk_around/temp/canvas_factory.py:22][M17.22-1]; [code/walk_around/walk_around.py:318][M17.22-2] |  |
| M17.23 | TODO | **Walk classifier**<br>Canvas images + aircraft-part CSV -> PyTorch inspection scores and selected evidence images. | [code/walk_around/model/predictor.py:59][M17.23-1]; [code/walk_around/walk_around.py:330][M17.23-2] |  |
| M17.24 | TODO | **Walk decision and observation-quality policy**<br>Scores, workers, sample count and blocked ratio -> result; includes strong multi-canvas Pass override of blockage. | [code/walk_around/decision_policy.py:41][M17.24-1] |  |
| M17.25 | TODO | **Outlier-cleaned second-pass fallback** **[OPTIONAL-OFF]**<br>Failed first result + cleaned trajectories -> optional re-render/re-score; disabled in the reviewed default config. | [code/walk_around/walk_around.py:360][M17.25-1]; [local_config.yaml:33][M17.25-2] |  |
| M17.26 | TODO | **Independent wide-arc re-tracking fallback** **[OPTIONAL-OFF]**<br>Failed result + source video -> optional YOLO-pose re-tracking and solo wide-arc rescue; disabled by default. | [code/walk_around/walk_around.py:393][M17.26-1]; [local_config.yaml:33][M17.26-2] |  |
| M17.27 | TODO | **Worker-contribution evidence export**<br>Combined paths and source worker IDs -> contribution CSV and inspection evidence artifacts. | [code/walk_around/walk_around.py:307][M17.27-1]; [code/walk_around/walk_around.py:470][M17.27-2] |  |
| M17.28 | TODO | **Walk result adapter**<br>Decision, probabilities, coverage and evidence image -> module output with technical/review information. | [code/walk_around/walk_around.py:415][M17.28-1]; [main.py:92][M17.28-2] |  |

**Module notes / missing components:**


<a id="m18"></a>
## M18 - Pre-arrival safety huddle

Repository: [pre-arrival-safety-huddle @ 5c8a7599](https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle/-/tree/5c8a75999651b9cad591d9ae2b65f1af6d309811).

**Consumed inputs:** Pixels; GM cones and big vehicles, worker/aircraft tracks, cone-relative perspective ROI and arrival observation.

**Existing output:** One huddle result/report/timeline.

**Review caution:** Pinned cv_common ac5098d lacks imported PlaneArrivalDetector. A candidate implementation exists at cv_common 2759daf, not at the reviewed pin.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M18.01 | TODO | **Arrival-phase dependency** **[MISSING-DEPENDENCY]**<br>Imported PlaneArrivalDetector -> expected arrival event; helper is absent at this repository's pinned cv_common revision. | [main.py:1][M18.01-1] |  |
| M18.02 | TODO | **Cone image-crop extraction**<br>Candidate cone box + source image -> profile-specific cone crop. | [main.py:159][M18.02-1] |  |
| M18.03 | TODO | **Cone color preprocessing**<br>Cone crop -> selected color channels, gamma adjustment and white-region mask. | [main.py:201][M18.03-1] |  |
| M18.04 | TODO | **Green-cone validation**<br>Preprocessed color statistics -> accepted meeting-cone candidate; color heuristic, not an additional neural detector. | [main.py:285][M18.04-1] |  |
| M18.05 | TODO | **Cone-centered gathering region**<br>Cone position/height -> nearby-worker ROI scaled to the cone. | [main.py:319][M18.05-1] |  |
| M18.06 | TODO | **Local cone identity tracking**<br>Valid cone observations over frames -> persistent Norfair cone identity. | [main.py:344][M18.06-1] |  |
| M18.07 | TODO | **Worker-to-huddle association**<br>Person boxes + cone gathering ROI -> workers belonging to each gathering candidate. | [main.py:544][M18.07-1] |  |
| M18.08 | TODO | **Group dwell and continuity**<br>At least three associated workers + cone ID history -> sustained huddle, with dwell/reset and ID-handover rules. | [main.py:77][M18.08-1] |  |
| M18.09 | TODO | **Arrival-bounded evidence collection**<br>Expected arrival event and short tail -> stop collecting huddle evidence. | [main.py:571][M18.09-1] |  |
| M18.10 | TODO | **Huddle observability and result**<br>Group dwell + obstruction fraction + arrival evidence -> huddle result and timeline. | [main.py:614][M18.10-1] |  |

**Module notes / missing components:**


<a id="m19"></a>
## M19 - Pre-departure walk-around

Repository: [pre-departure-walk-around-completed @ e407de23](https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/tree/e407de23c3226bf49d19f1755c40cfb53176159b).

**Consumed inputs:** Pixels; aircraft parts, worker/BL/aircraft tracks; latest loading end, departure evidence and pushback obstruction.

**Existing output:** Result/report/timeline plus technical trajectory/geometry/classifier evidence.

**Review caution:** Pinned cv_common e4c5e36 lacks imported departure/presence helpers. The reported five-minute wording does not match the 480-second code window. Torch and Keras paths must remain separate profiles.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M19.01 | TODO | **Frame/metadata dispatch**<br>Video frames + GM/tracker payloads -> state-manager and walk observations. | [main.py:42][M19.01-1] |  |
| M19.02 | TODO | **Detection coordinate normalization**<br>Detection coordinates and image dimensions -> local normalized observation format. | [code/utils/detection_preprocessor.py:11][M19.02-1] |  |
| M19.03 | TODO | **Aircraft phase state**<br>Aircraft movement history -> arrival/departure context for the walk window. | [code/states.py:37][M19.03-1] |  |
| M19.04 | TODO | **Loader service tracking**<br>Loader detections, identities and aircraft layout -> loader service states and retained histories. | [code/states.py:173][M19.04-1] |  |
| M19.05 | TODO | **Loading start/end and return**<br>Sustained loader presence/absence -> loading start, clear interval and resumed loading. | [code/states.py:945][M19.05-1] |  |
| M19.06 | TODO | **Imported phase helpers** **[MISSING-DEPENDENCY]**<br>Calls to departure/loader-presence helpers -> expected phase evidence; required helpers are missing at the pinned cv_common revision. | [code/states.py:17][M19.06-1]; [code/states.py:1010][M19.06-2] |  |
| M19.07 | TODO | **Final pre-departure worker window**<br>Loading end + departure -> retrospective trimmed window; current configured lookback and minimum coverage are eight minutes. | [code/states.py:750][M19.07-1]; [local_config.yaml:60][M19.07-2] |  |
| M19.08 | TODO | **Pushback obstruction prepass**<br>Pushback/aircraft observations -> early obstruction reference/history. | [code/walk_around/pushback_obstruction_detector.py:167][M19.08-1] |  |
| M19.09 | TODO | **Pushback obstruction postpass**<br>Late-turn observations and prepass reference -> final obstruction history. | [code/walk_around/pushback_obstruction_detector.py:228][M19.09-1] |  |
| M19.10 | TODO | **View-dependent pushback obstruction classification**<br>Wing geometry + pushback area stability -> obstruction class and usable assessment window. | [code/walk_around/pushback_obstruction_detector.py:349][M19.10-1]; [code/walk_around/pushback_obstruction_detector.py:519][M19.10-2] |  |
| M19.11 | TODO | **Body pose estimation**<br>Worker image crops -> YOLO pose landmarks for localization and trajectories. | [code/walk_around/_pose_model.py:18][M19.11-1] |  |
| M19.12 | TODO | **Person-ground coordinate estimation**<br>Person pose/bounds + camera assumptions -> ground-coordinate estimates. | [code/walk_around/distance_estimator.py:56][M19.12-1] |  |
| M19.13 | TODO | **Worker and aircraft-part history**<br>Time-stamped worker IDs/positions and part detections -> trajectory and aircraft-layout buffers. | [code/walk_around/walk_around.py:79][M19.13-1] |  |
| M19.14 | TODO | **Depth inference**<br>Selected aircraft imagery -> depth map for top-down reconstruction. | [code/walk_around/temp/plane_tdv_extractor.py:67][M19.14-1]; [code/walk_around/temp/plane_tdv_extractor.py:161][M19.14-2] |  |
| M19.15 | TODO | **Aircraft segmentation and mask selection**<br>Image prompts and aircraft layout -> selected MobileSAM body mask. | [code/walk_around/temp/plane_tdv_extractor.py:166][M19.15-1] |  |
| M19.16 | TODO | **Top-down aircraft template and fallback**<br>Body mask + depth/camera geometry -> top-down template or fallback geometry when reconstruction is incomplete. | [code/walk_around/temp/plane_tdv_extractor.py:323][M19.16-1] |  |
| M19.17 | TODO | **Inspection-view blockage**<br>Obstacles and inspection ROI -> blocked-frame coverage. | [code/walk_around/walk_around.py:296][M19.17-1] |  |
| M19.18 | TODO | **Trajectory finalization and trimming**<br>Buffered paths + selected departure window -> frozen, trimmed tracks. | [code/walk_around/walk_around.py:676][M19.18-1] |  |
| M19.19 | TODO | **Spatial outlier removal**<br>Worker paths + distance limits -> cleaned path samples. | [code/walk_around/preprocessing/preprocessing.py:22][M19.19-1]; [code/walk_around/walk_around.py:701][M19.19-2] |  |
| M19.20 | TODO | **Distance adjustment and smoothing**<br>Noisy trajectory coordinates + distance profile -> adjusted/smoothed paths. | [code/walk_around/preprocessing/preprocessing.py:66][M19.20-1]; [code/walk_around/walk_around.py:701][M19.20-2] |  |
| M19.21 | TODO | **Gap flattening**<br>Broken trajectory segments -> paths with eligible discontinuities flattened. | [code/walk_around/preprocessing/preprocessing.py:140][M19.21-1] |  |
| M19.22 | TODO | **Trajectory splitting**<br>Paths with time/spatial discontinuities -> coherent candidate segments. | [code/walk_around/preprocessing/splitter.py:68][M19.22-1] |  |
| M19.23 | TODO | **Fragment compatibility and recombination**<br>Compatible time/spatial segments -> candidate inspection paths, preserving worker contributions. | [code/walk_around/preprocessing/recombination.py:42][M19.23-1]; [code/walk_around/preprocessing/recombination.py:177][M19.23-2] |  |
| M19.24 | TODO | **Trajectory-to-image encoding**<br>Recombined worker paths + aircraft template -> canvas images used by the classifier. | [code/walk_around/walk_around.py:457][M19.24-1] |  |
| M19.25 | TODO | **Walk classifier**<br>Canvas images + aircraft-part features -> Keras inspection scores; distinct model/profile from post-arrival. | [code/walk_around/walk_around.py:215][M19.25-1]; [code/walk_around/walk_around.py:490][M19.25-2] |  |
| M19.26 | TODO | **Primary decision and observability**<br>Inspection score + observation coverage -> base result; reviewed config sets CNN threshold to 0.5. | [code/walk_around/walk_around.py:490][M19.26-1]; [local_config.yaml:66][M19.26-2] |  |
| M19.27 | TODO | **Outlier-cleaned second-pass fallback**<br>Failed base result + cleaned trajectories -> re-rendered CNN judgment at a stricter threshold; enabled in reviewed config. | [code/walk_around/walk_around.py:515][M19.27-1]; [local_config.yaml:66][M19.27-2] |  |
| M19.28 | TODO | **Independent wide-arc re-tracking fallback**<br>Failed result + source video -> YOLO-pose re-tracking and solo wide-arc rescue over a larger window; enabled in reviewed config. | [code/walk_around/walk_around.py:539][M19.28-1]; [local_config.yaml:72][M19.28-2] |  |
| M19.29 | TODO | **Contribution and result export**<br>Combined/source worker tracks, scores and coverage -> CSV evidence and technical result payload. | [code/walk_around/walk_around.py:450][M19.29-1]; [code/walk_around/walk_around.py:560][M19.29-2] |  |

**Module notes / missing components:**


<a id="m20"></a>
## M20 - Wing walkers at pushback start

Repository: [pushback-does-not-start-until-wing-walkers-are-in-place-and-ready @ f3b041cb](https://gitlab.com/dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready/-/tree/f3b041cbccdf96158d585def3798d3749bb32529).

**Consumed inputs:** Worker/aircraft tracks, aircraft parts and person/pushback/obstacle detections.

**Existing output:** One readiness result/report/timeline.

**Review caution:** Current evidence is post-start co-motion, not a direct proof that everyone was ready before start. Global role flags require per-turn state isolation.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M20.01 | TODO | **Camera-specific pseudo-depth**<br>Person box heights and view profile -> relative depth estimates for worker trajectories. | [main.py:31][M20.01-1] |  |
| M20.02 | TODO | **Trajectory smoothing and line fit**<br>Noisy worker observations -> representative motion direction. | [main.py:52][M20.02-1] |  |
| M20.03 | TODO | **Opposite-side assignment**<br>Worker positions relative to aircraft -> side labels and both-side coverage. | [main.py:147][M20.03-1] |  |
| M20.04 | TODO | **Worker path qualification**<br>Worker paths + aircraft direction -> length/direction-compatible wing-walker candidates. | [main.py:156][M20.04-1] |  |
| M20.05 | TODO | **Driver exclusion**<br>Worker/vehicle spatial relation -> removal of probable vehicle occupants. | [main.py:427][M20.05-1] |  |
| M20.06 | TODO | **Departure analysis phase**<br>Aircraft stopped/moving history + distance change -> departure collection window, including observations after motion starts. | [main.py:538][M20.06-1] |  |
| M20.07 | TODO | **Obstruction and part visibility**<br>Missing aircraft parts or high blocked fraction -> Not observed eligibility. | [main.py:272][M20.07-1] |  |
| M20.08 | TODO | **Readiness-labeled result**<br>Qualified paths and coverage -> wing-walker result; current evidence does not establish readiness strictly before pushback starts. | [main.py:156][M20.08-1]; [main.py:272][M20.08-2] |  |

**Module notes / missing components:**


<a id="m21"></a>
## M21 - Pushback pathway clearance

Repository: [pushback-pathway-confirmed-clear-of-obstacles @ 104db85a](https://gitlab.com/dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles/-/tree/104db85a4708e78a9abf779191a871b002a21d38).

**Consumed inputs:** GM aircraft nose/tail, BL/GSE/fuel truck/trailer/cone/chock/ladder and pushback; aircraft motion.

**Existing output:** One pathway result/report/timeline.

**Review caution:** Current hazard class list does not include people. Variable pushback_moving uses aircraft state, not an independent pushback motion state.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M21.01 | TODO | **Aircraft state and part history**<br>Aircraft tracks and part detections -> movement history and reference geometry. | [main.py:98][M21.01-1] |  |
| M21.02 | TODO | **Pushback pathway ROI**<br>Aircraft reference geometry -> area treated as the pushback pathway. | [main.py:134][M21.02-1] |  |
| M21.03 | TODO | **Hazard class/size selection**<br>GM object boxes -> selected relevant hazards using class-specific size rules; people are not included in the active hazard set. | [main.py:196][M21.03-1]; [main.py:201][M21.03-2] |  |
| M21.04 | TODO | **Obstacle-versus-blocker handling**<br>Object geometry and pathway ROI -> hazardous objects versus objects blocking the assessment view. | [main.py:303][M21.04-1] |  |
| M21.05 | TODO | **Pushback-seen and motion context**<br>Pushback observations + aircraft movement state -> active pathway assessment phase. | [main.py:430][M21.05-1] |  |
| M21.06 | TODO | **Hazard persistence and lookback**<br>Hazards over time -> sustained obstruction and recent-window evidence near departure. | [main.py:430][M21.06-1] |  |
| M21.07 | TODO | **Final observation-quality policy**<br>View blockage near departure + missing phase evidence -> unobservable pathway result. | [main.py:430][M21.07-1] |  |
| M21.08 | TODO | **Clear-path decision and timeline**<br>Hazard exposure + eligibility -> Fail/Pass/Not observed result with failure precedence. | [main.py:430][M21.08-1] |  |

**Module notes / missing components:**


<a id="m22"></a>
## M22 - Beltloader rail extension

Repository: [safety-handrails-fully-extended @ 8b9a2a9b](https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended/-/tree/8b9a2a9b0c16edbe91f50dea30b644bc79d420e4).

**Consumed inputs:** Pixels; BL/aircraft tracks, front/back role, camera context and stopped-state evidence.

**Existing output:** One result/report/timeline; no qualified loader is Not observed.

**Review caution:** 480 frames is about 60 seconds at 8 FPS, not eight minutes. Shared classifier reuse needs artifact/preprocessing identity.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M22.01 | TODO | **Loader identity and stopped state**<br>Tracked loader history -> persistent stopped-loader visits. | [main.py:63][M22.01-1] |  |
| M22.02 | TODO | **Relevant service-loader selection**<br>GM loader/aircraft geometry -> eligible loader crops for rail assessment. | [main.py:242][M22.02-1] |  |
| M22.03 | TODO | **Rail-extension classification**<br>Loader crop -> EfficientNet extended/not-extended prediction. | [local_config.yaml:3][M22.03-1]; [main.py:277][M22.03-2] |  |
| M22.04 | TODO | **Sparse inference and result hold**<br>Frame index + last classifier output -> every-eighth-frame inference with held intermediate result. | [main.py:277][M22.04-1] |  |
| M22.05 | TODO | **Rail-state exposure**<br>Held rail predictions over a stopped visit -> extended-frame ratio. | [main.py:79][M22.05-1] |  |
| M22.06 | TODO | **Loader identity handover**<br>New/lost loader tracks and allowed frame gap -> preserved visit evidence. | [main.py:63][M22.06-1]; [local_config.yaml:19][M22.06-2] |  |
| M22.07 | TODO | **Visit qualification and rail policy**<br>Visit duration + extension ratio -> loader result using minimum stay and greater-than-0.45 ratio. | [main.py:23][M22.07-1] |  |
| M22.08 | TODO | **All-visit output**<br>Qualified loader rail results -> aggregate report and timeline. | [main.py:23][M22.08-1] |  |

**Module notes / missing components:**


<a id="m23"></a>
## M23 - Vest fastening

Repository: [safety-vests-secured-to-body @ ae8ef164](https://gitlab.com/dxgat/detectors/safety-vests-secured-to-body/-/tree/ae8ef164a82c023fd99594913e4920306f2b40a3).

**Consumed inputs:** Pixels; GM vest/person boxes and worker tracks; no turnaround stage required by the core rule.

**Existing output:** One result; person dictionary nonempty without final unzipped states returns Pass; no associated workers returns Not observed.

**Review caution:** No keypoint pose despite the model name. Current unknown/undefined workers can coexist with Pass; do not silently strengthen semantics during extraction.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M23.01 | TODO | **Worker/vest association**<br>Person and vest boxes + overlap -> worker-specific vest observations. | [main.py:50][M23.01-1] |  |
| M23.02 | TODO | **Observation quality and state history**<br>Crop size/brightness, track age and recent observations -> usable appearance history. | [main.py:50][M23.02-1] |  |
| M23.03 | TODO | **Vest-closure image classification**<br>Worker/vest crop -> zipped/unzipped appearance score from a Swin-T model. | [main.py:268][M23.03-1] |  |
| M23.04 | TODO | **Appearance-orientation classification**<br>Worker crop -> front/back/side appearance score from a second Swin-T; not skeleton pose estimation. | [main.py:268][M23.04-1] |  |
| M23.05 | TODO | **Vest-color segmentation**<br>HSV crop and morphology -> vest-colored pixel mask. | [main.py:115][M23.05-1] |  |
| M23.06 | TODO | **Vest-panel geometry heuristic**<br>Mask contours and panel geometry -> supplementary closure/appearance evidence. | [main.py:144][M23.06-1] |  |
| M23.07 | TODO | **Worker/module result aggregation**<br>Worker appearance states -> failure if any unzipped state; current fallback can pass despite unknown worker states. | [main.py:209][M23.07-1] |  |
| M23.08 | TODO | **Result timeline**<br>Worker/result history -> annotated output intervals. | [main.py:428][M23.08-1] |  |

**Module notes / missing components:**


<a id="m24"></a>
## M24 - Pre-arrival safety-zone clearance

Repository: [safety-zone-confirmed-clear @ 91676a55](https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/tree/91676a554aca543723850f3f4641ebdaa7784b66).

**Consumed inputs:** Pixels; aircraft/front-wheel/cone detections and approach tracks; transport/person detections and motion masks.

**Existing output:** One result; unknown if uncertain exposure exceeds passing exposure, otherwise Pass absent enough violations.

**Review caution:** Upstream tracker does not cover every transport class currently tracked here. FOD and safety-zone ROIs are related but not identical.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M24.01 | TODO | **Aircraft approach/wheel trajectory**<br>Wheel and aircraft observations -> fitted approach line. | [main.py:546][M24.01-1] |  |
| M24.02 | TODO | **Safety-zone geometry**<br>Approach line and aircraft/wheel reference -> projected diamond-shaped safety region. | [main.py:632][M24.02-1] |  |
| M24.03 | TODO | **Transport-to-zone intersection**<br>Vehicle lower/foot strip + safety polygon -> relevant moving-transport overlap. | [main.py:716][M24.03-1] |  |
| M24.04 | TODO | **Cone validity in the zone**<br>Cone observations + zone geometry -> acceptable cone boundary evidence. | [main.py:747][M24.04-1] |  |
| M24.05 | TODO | **Local transport identity tracking**<br>GM transport observations -> Norfair vehicle identities used for zone motion analysis. | [main.py:831][M24.05-1]; [main.py:1150][M24.05-2] |  |
| M24.06 | TODO | **Transport segmentation and motion**<br>Vehicle imagery and tracks -> MobileSAM-assisted local motion evidence. | [main.py:831][M24.06-1]; [main.py:1234][M24.06-2] |  |
| M24.07 | TODO | **Arrival reference and two-pass replay**<br>Whole-video aircraft history -> retrospective replay interval before arrival. | [main.py:969][M24.07-1]; [main.py:1150][M24.07-2] |  |
| M24.08 | TODO | **Safety-zone occurrence history**<br>Vehicles/cones, motion and frame index -> retained safety-zone observations. | [main.py:1445][M24.08-1] |  |
| M24.09 | TODO | **Clear-zone policy**<br>Violation count and clear/unknown coverage -> result; more than fifteen failures can fail the module. | [main.py:800][M24.09-1] |  |
| M24.10 | TODO | **Spatial result evidence**<br>Safety-region geometry + occurrence/result history -> report/timeline and spatial evidence. | [main.py:800][M24.10-1]; [main.py:1445][M24.10-2] |  |

**Module notes / missing components:**


<a id="m25"></a>
## M25 - GSE seat-belt use

Repository: [seat-belts-used-on-all-gse-equipped-with-seat-belts @ 43068fec](https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/tree/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d).

**Consumed inputs:** Pixels; GSE movement state, GM people/vehicles/obstacles and aircraft stage; local Norfair worker tracking.

**Existing output:** One result/report/timeline plus CSV debug output.

**Review caution:** No authoritative equipment-is-seatbelt-equipped source is present. Visual heuristics do not prove hardware availability; sample videos are absent from videos_by_module.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M25.01 | TODO | **Vehicle direction relative to worker**<br>Vehicle motion + worker position -> direction/context for driver interaction. | [main.py:44][M25.01-1] |  |
| M25.02 | TODO | **Stop/start episode timing**<br>Vehicle state transitions -> stop/move event windows. | [main.py:98][M25.02-1] |  |
| M25.03 | TODO | **Local worker tracking**<br>Person detections and centroid association -> persistent Norfair worker identities. | [main.py:419][M25.03-1]; [main.py:428][M25.03-2] |  |
| M25.04 | TODO | **Driver association and obstruction**<br>Worker/GSE relation + obstacles -> eligible driver observations and visibility exclusions. | [main.py:514][M25.04-1] |  |
| M25.05 | TODO | **Driver body pose**<br>Driver image crop -> HRNet landmarks through the pinned shared pose wrapper. | [main.py:428][M25.05-1]; [main.py:514][M25.05-2] |  |
| M25.06 | TODO | **Seated-posture state**<br>Leg angles and relative body geometry -> seated/driver state. | [main.py:292][M25.06-1] |  |
| M25.07 | TODO | **Belt-unfastening action heuristic**<br>Arm motion over several frames -> candidate unfastening event. | [main.py:190][M25.07-1] |  |
| M25.08 | TODO | **Driver evidence persistence**<br>Pose, driver association and recent action history -> retained person state. | [main.py:239][M25.08-1] |  |
| M25.09 | TODO | **Event-relative belt inspection window**<br>Vehicle stop/start time -> image/pose windows before and around movement transitions. | [main.py:312][M25.09-1] |  |
| M25.10 | TODO | **Torso strap segmentation**<br>Torso crop -> thresholded candidate strap pixels using Otsu segmentation. | [main.py:365][M25.10-1] |  |
| M25.11 | TODO | **Diagonal strap geometry**<br>Candidate strap pixels -> PCA orientation/diagonal-belt evidence. | [main.py:365][M25.11-1] |  |
| M25.12 | TODO | **Driver and module result**<br>Eligible driver belt evidence -> result, with false evidence failing and unknowns skipped; no separate GSE belt-capability source. | [main.py:704][M25.12-1] |  |
| M25.13 | TODO | **Evidence export**<br>Driver assessments and event intervals -> CSV, report and timeline. | [main.py:704][M25.13-1] |  |

**Module notes / missing components:**


<a id="m26"></a>
## M26 - Steering bypass installation

Repository: [steering-by-pass-pin-installed-or-steering-otherwise-bypassed @ 60dca736](https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/tree/60dca7360132479064544ab321b055bc35b666b7).

**Consumed inputs:** Pixels; workers, aircraft/front wheel, obstacles and arrival state; camera-specific wheel ROI.

**Existing output:** One installation result/report/timeline.

**Review caution:** Distinct learned installation task from heuristic pin verification. Chock detections are collected but do not establish chocking prerequisite.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M26.01 | TODO | **Worker crop and body pose**<br>Person crop with color preprocessing -> HRNet body landmarks. | [main.py:62][M26.01-1] |  |
| M26.02 | TODO | **Relative pose coordinates**<br>Person box + keypoints -> normalized landmark features. | [main.py:76][M26.02-1] |  |
| M26.03 | TODO | **Ankle position relative to wheel**<br>Worker ankles + wheel reference -> wheel-relative foot trajectory. | [main.py:84][M26.03-1] |  |
| M26.04 | TODO | **Missing-sample interpolation and smoothing**<br>Noisy/incomplete pose sequence -> interpolated and Savitzky-Golay-smoothed features. | [main.py:124][M26.04-1] |  |
| M26.05 | TODO | **Aircraft state adapter**<br>Aircraft tracking state -> arrival and stationary-aircraft context. | [main.py:198][M26.05-1] |  |
| M26.06 | TODO | **Wheel reference stabilization**<br>Nose-wheel detections -> averaged stable wheel location. | [main.py:308][M26.06-1] |  |
| M26.07 | TODO | **Wheel-interaction worker selection**<br>Worker feet + wheel ROI -> eligible nearby workers. | [main.py:345][M26.07-1] |  |
| M26.08 | TODO | **Worker stop-episode detection**<br>Foot velocity and position history -> interaction stops near the wheel. | [main.py:345][M26.08-1]; [main.py:452][M26.08-2] |  |
| M26.09 | TODO | **Centered action-clip assembly**<br>Worker stop + buffered/future pose -> 200-frame sequence, including future context. | [main.py:495][M26.09-1] |  |
| M26.10 | TODO | **Action feature-vector encoding**<br>Person bounds + 17 body keypoints -> 55 features per frame for the sequence model. | [main.py:495][M26.10-1] |  |
| M26.11 | TODO | **Learned pin-installation action classification**<br>Scaled feature sequence -> FastAI/tsai action class, including pin-related classes. | [main.py:614][M26.11-1] |  |
| M26.12 | TODO | **Arrival-relative installation window**<br>Arrival time -> accept actions within the module's post-arrival window. | [main.py:682][M26.12-1] |  |
| M26.13 | TODO | **Wheel/worker observability**<br>Missing wheel duration and obstruction -> observation eligibility or unknown result. | [main.py:786][M26.13-1] |  |
| M26.14 | TODO | **Installation result and timeline**<br>Accepted action classes + eligibility -> module output; chock placement is not an actual prerequisite check here. | [main.py:34][M26.14-1]; [main.py:786][M26.14-2] |  |

**Module notes / missing components:**


<a id="m27"></a>
## M27 - Wing positions and approved wands

Repository: [wing-walkers-in-proper-position-and-using-approved-wands @ 4800b649](https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/tree/4800b649973038924905d74d616fbb5b77087053).

**Consumed inputs:** Worker/aircraft tracks, GM aircraft parts/pushback/persons/obstacles and movement history.

**Existing output:** Position result plus wand sub-result and associated report/timeline structures.

**Review caution:** CRITICAL semantic gap: approved-wand Pass is hard-coded on the active path. Old wand-count code is not called; merely extracting it would not preserve active behavior or establish correctness.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| M27.01 | TODO | **Aircraft departure-phase state**<br>Aircraft stopped/moving history -> departure window and sufficient prior stop evidence. | [main.py:40][M27.01-1] |  |
| M27.02 | TODO | **Worker identity association**<br>Person observations and existing IDs -> persistent candidate worker histories. | [main.py:93][M27.02-1] |  |
| M27.03 | TODO | **Camera-specific pseudo-depth**<br>Worker box heights + view profile -> approximate relative depth for movement analysis. | [main.py:315][M27.03-1] |  |
| M27.04 | TODO | **Trajectory smoothing and line fit**<br>Worker position history -> representative worker direction. | [main.py:371][M27.04-1] |  |
| M27.05 | TODO | **Wing-walker position/path checks**<br>Person paths + aircraft direction/geometry -> side-position and directional qualification. | [main.py:111][M27.05-1] |  |
| M27.06 | TODO | **Wand approval placeholder** **[STUB]**<br>Qualified-position path -> hard-coded wand Pass; no active visual wand verification is performed. | [main.py:226][M27.06-1]; [main.py:762][M27.06-2] |  |
| M27.07 | TODO | **Legacy wand-evidence decision** **[INACTIVE]**<br>Wand counters and legacy position state -> alternate decision function, not the currently called result path. | [main.py:243][M27.07-1]; [main.py:762][M27.07-2] |  |
| M27.08 | TODO | **Wand model initialization** **[INITIALIZATION-ONLY]**<br>Configured weights -> allocated model object; initialization is not proof of active wand inference. | [main.py:407][M27.08-1] |  |
| M27.09 | TODO | **Departure eligibility and two-result output**<br>Departure availability + position/stub-wand result -> two reported sub-results. | [main.py:762][M27.09-1] |  |

**Module notes / missing components:**


<a id="u01"></a>
## U01 - Camera ingestion and full-turn assembly

Repository: [camera_software @ 13ef3fc3](https://gitlab.com/dxgat/utils/camera_software/-/tree/13ef3fc3e3da8d757173c80651e7765f9bfaafe3).

**Consumed inputs:** Camera chunk manifests/storage/DB, 60-second video chunks nominally 8 FPS, persisted camera/turn candidate state.

**Existing output:** Merged full-turn media plus DB/session metadata and processed-chunk state.

**Review caution:** Its coarse capture boundary is not identical to downstream arrival/departure semantics. Keep clip and analytic-stage versions distinct.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| U01.01 | TODO | **Chunk identity and metadata adapter**<br>Storage objects and session identifiers -> chunk objects with names, sequence numbers and metadata. | [chunks_handling/storage_handling.py:34][U01.01-1] |  |
| U01.02 | TODO | **Chunk discovery and ordering**<br>Storage/session listing -> chronologically ordered candidate chunks. | [chunks_handling/storage_handling.py:116][U01.02-1] |  |
| U01.03 | TODO | **Processing eligibility and resume selection**<br>Chunk metadata and processed markers -> chunks still requiring merge analysis. | [chunks_handling/storage_handling.py:139][U01.03-1] |  |
| U01.04 | TODO | **Chunk download and frame iteration**<br>Selected chunks -> downloaded files and frame stream carrying chunk metadata. | [chunks_handling/chunks_generator.py:11][U01.04-1] |  |
| U01.05 | TODO | **Scene-classifier image preparation**<br>Sampled scene images -> grayscale resized model inputs. | [classifier/classifier.py:59][U01.05-1] |  |
| U01.06 | TODO | **Inside/outside scene classification**<br>Prepared images -> SimpleCNN scene labels and confidence. | [classifier/classifier.py:6][U01.06-1]; [classifier/classifier.py:110][U01.06-2] |  |
| U01.07 | TODO | **Coarse aircraft-presence gate**<br>Batched scene classification + aircraft detection -> whether a chunk merits detailed aircraft processing. | [merge.py:217][U01.07-1]; [merge.py:478][U01.07-2] |  |
| U01.08 | TODO | **General object/aircraft detection**<br>Video frames -> object and aircraft-part boxes using the merge model wrapper. | [new_model.py:19][U01.08-1]; [merge.py:534][U01.08-2] |  |
| U01.09 | TODO | **Tail tracking**<br>Tail detections across frames -> stable aircraft-tail candidates. | [merge.py:549][U01.09-1] |  |
| U01.10 | TODO | **Suitable-aircraft filtering**<br>Aircraft dimensions/location + tail alignment -> aircraft candidates relevant to this camera. | [merge.py:36][U01.10-1]; [merge.py:584][U01.10-2] |  |
| U01.11 | TODO | **Aircraft identity tracking**<br>Suitable aircraft boxes -> tracked primary aircraft candidate. | [merge.py:613][U01.11-1] |  |
| U01.12 | TODO | **Aircraft segmentation and motion**<br>Tracked aircraft imagery + ignored object boxes -> segmentation-assisted motion/stop evidence. | [merge.py:271][U01.12-1]; [merge.py:625][U01.12-2] |  |
| U01.13 | TODO | **Arrival event detection**<br>Stopped aircraft + minimum segmented area -> arrival event and start-chunk marker. | [merge.py:680][U01.13-1] |  |
| U01.14 | TODO | **Vehicle-occlusion detection**<br>Moving-aircraft phase + vehicle model boxes -> sustained occlusion evidence used to suppress departure counting. | [merge.py:701][U01.14-1] |  |
| U01.15 | TODO | **Departure event detection**<br>Aircraft motion/disappearance + occlusion counters -> end-chunk event after configured persistence. | [merge.py:649][U01.15-1]; [merge.py:701][U01.15-2] |  |
| U01.16 | TODO | **Pre/post-event context selection**<br>Arrival/departure chunk IDs + available history -> full-turn boundaries with retained context. | [merge.py:243][U01.16-1]; [merge.py:499][U01.16-2] |  |
| U01.17 | TODO | **Session-end finalization**<br>End/broken-chunk condition + open turnaround -> finalize an incomplete pending full-turn. | [merge.py:738][U01.17-1] |  |
| U01.18 | TODO | **Video concatenation**<br>Ordered chunk files -> merged full-turn video using ffmpeg stream-copy. | [merge.py:108][U01.18-1] |  |
| U01.19 | TODO | **Full-turn publication and retention**<br>Selected chunk interval + generated video -> published merge output and retained/processed chunk bookkeeping. | [merge.py:149][U01.19-1]; [chunks_handling/storage_handling.py:330][U01.19-2] |  |
| U01.20 | TODO | **Persistent processing markers**<br>Chunk events and completed intervals -> storage metadata updates enabling later resume. | [chunks_handling/storage_handling.py:241][U01.20-1]; [merge.py:658][U01.20-2]; [merge.py:695][U01.20-3] |  |
| U01.21 | TODO | **Merge report and notification**<br>Merge result metadata -> report/notification to the external workflow. | [chunks_handling/storage_handling.py:267][U01.21-1]; [notification.py:9][U01.21-2] |  |

**Module notes / missing components:**


<a id="u02"></a>
## U02 - General-model pipeline

Repository: [general_model @ 13a4ddc5](https://gitlab.com/dxgat/detectors/general_model/-/tree/13a4ddc57cca80f2432bc26eb76b5a300c3ac633).

**Consumed inputs:** Merged video/pixels, inference configuration/class mappings, model artifacts and worker metadata writer.

**Existing output:** general_model<video>.ndjson; camera/entity/aircraft type, stage/statistic dictionary, noise and broken-image information.

**Review caution:** Airplane height replaces normal detection confidence in the output array. Do not treat every fifth numeric field as probability.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| U02.01 | TODO | **Multi-pass video access**<br>Source video -> independent readers for detection, enrichment and quality selection. | [main.py:475][U02.01-1] |  |
| U02.02 | TODO | **Image-quality preprocessing**<br>Frame history -> adaptive image preprocessing and noise/mode measurements before inference. | [main.py:505][U02.02-1] |  |
| U02.03 | TODO | **General objects and aircraft-part detection**<br>Prepared frames -> multi-class GM detections using the configured YOLO ONNX model. | [main.py:463][U02.03-1]; [main.py:538][U02.03-2] |  |
| U02.04 | TODO | **Chock detection**<br>Prepared frames -> dedicated small-object chock detections. | [main.py:467][U02.04-1]; [main.py:583][U02.04-2] |  |
| U02.05 | TODO | **Broad vehicle detection**<br>Prepared frames -> vehicle candidates from a separate detector. | [main.py:471][U02.05-1]; [main.py:589][U02.05-2] |  |
| U02.06 | TODO | **Detection coordinate adapter**<br>Detector coordinates -> clamped integer image-space boxes. | [main.py:202][U02.06-1]; [main.py:542][U02.06-2] |  |
| U02.07 | TODO | **Aircraft duplicate suppression**<br>Overlapping aircraft candidates -> reduced candidate set. | [main.py:598][U02.07-1] |  |
| U02.08 | TODO | **Aircraft identity tracking**<br>Aircraft detections across frames -> Norfair aircraft histories and reassociation across changed IDs. | [main.py:488][U02.08-1]; [main.py:612][U02.08-2] |  |
| U02.09 | TODO | **Aircraft box stabilization**<br>Noisy aircraft observations + image-quality mode -> stabilized boxes. | [main.py:274][U02.09-1]; [main.py:615][U02.09-2] |  |
| U02.10 | TODO | **Aircraft segmentation and motion state**<br>Aircraft imagery + exclusion boxes + SAM -> aircraft movement/history state. | [main.py:288][U02.10-1]; [main.py:453][U02.10-2] |  |
| U02.11 | TODO | **Primary-aircraft selection**<br>Whole-video aircraft histories -> longest-observed aircraft and representative height. | [main.py:669][U02.11-1] |  |
| U02.12 | TODO | **Main aircraft-part selection**<br>Wheel/nose/wing observation histories -> representative primary-aircraft part layout. | [main.py:367][U02.12-1]; [main.py:678][U02.12-2] |  |
| U02.13 | TODO | **Transport detection fusion**<br>General-model transport classes + broad vehicle boxes -> overlap-deduplicated transport candidates. | [main.py:784][U02.13-1] |  |
| U02.14 | TODO | **Gate/side obstacle classification**<br>Transport boxes + selected aircraft layout -> obstacle and side-obstacle labels. | [main.py:811][U02.14-1] |  |
| U02.15 | TODO | **Entity/operator classification**<br>Sparse entity-model detections -> accumulated entity/operator label. | [main.py:716][U02.15-1]; [main.py:835][U02.15-2] |  |
| U02.16 | TODO | **Aircraft-type inference**<br>Aircraft-part detections and accumulated type state -> aircraft-category estimate. | [scripts/engine_script.py:7][U02.16-1]; [main.py:881][U02.16-2] |  |
| U02.17 | TODO | **Camera-view classification**<br>Stopped-aircraft imagery -> cone/wing classifier observations and whole-video majority vote. | [scripts/classifier_utils.py:33][U02.17-1]; [main.py:889][U02.17-2] |  |
| U02.18 | TODO | **Enriched aircraft detection serialization**<br>Selected aircraft box + representative height -> output detection; the confidence slot currently carries height, not a probability. | [main.py:851][U02.18-1] |  |
| U02.19 | TODO | **Loader-service stage heuristic** **[INPUT-GAP]**<br>Loader/door observations -> loader arrival/leave candidates; door lists are initialized empty and not populated in the reviewed loop. | [main.py:94][U02.19-1]; [main.py:519][U02.19-2]; [main.py:649][U02.19-3] |  |
| U02.20 | TODO | **Turnaround stage interval assembly**<br>Aircraft and loader event histories -> pre-arrival, service and departure intervals; loader-stage reliability depends on the input gap above. | [main.py:922][U02.20-1] |  |
| U02.21 | TODO | **Class/stage visibility statistics**<br>Detection histories + selected intervals -> per-class exposure fractions and statistics payload. | [main.py:171][U02.21-1]; [main.py:960][U02.21-2] |  |
| U02.22 | TODO | **Video suitability assessment**<br>Visibility statistics + additional video reader -> video-selection decision; computed but not included in the returned dictionary. | [scripts/videos_selection_script.py:24][U02.22-1]; [main.py:1055][U02.22-2] |  |
| U02.23 | TODO | **Metadata publication and final summary**<br>Raw/enriched detections + camera/type/noise data -> NDJSON through VideoWorker and returned GM summary. | [main.py:595][U02.23-1]; [main.py:710][U02.23-2]; [main.py:871][U02.23-3]; [main.py:1062][U02.23-4] |  |

**Module notes / missing components:**


<a id="u03"></a>
## U03 - Tracking and semantic vehicle state

Repository: [cv_trackers @ b5d350c7](https://gitlab.com/dxgat/utils/cv_trackers/-/tree/b5d350c71d0533439e9916077fc7b1215d3003ac).

**Consumed inputs:** Video pixels, GM NDJSON, class mappings, DeepSORT/tracked-object configuration and utility pins.

**Existing output:** trackers<video>.ndjson: Track serialization, vehicle private state_dict, and BL role data.

**Review caution:** Only GSE/BL get general vehicle tracking here; downstream safety-zone still tracks other transport. Serialized private fields tightly couple consumers to implementation versions.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| U03.01 | TODO | **Frame/GM metadata join**<br>Source frames + GM records -> paired tracking inputs; current loop joins by iterator position. | [tracker.py:82][U03.01-1]; [tracker.py:144][U03.01-2] |  |
| U03.02 | TODO | **Per-class detection routing**<br>GM class IDs and box filters -> worker, loader, GSE and aircraft inputs; not every vehicle class receives a track. | [tracker.py:168][U03.02-1] |  |
| U03.03 | TODO | **Worker identity tracking**<br>Person boxes + image appearance -> DeepSORT confirmed/tentative worker tracks. | [tracker.py:102][U03.03-1]; [tracker.py:243][U03.03-2] |  |
| U03.04 | TODO | **Loader identity tracking**<br>Beltloader boxes + image appearance -> separate DeepSORT loader tracks. | [tracker.py:93][U03.04-1]; [tracker.py:226][U03.04-2] |  |
| U03.05 | TODO | **GSE identity tracking**<br>GSE boxes + image appearance -> separate DeepSORT GSE tracks. | [tracker.py:97][U03.05-1]; [tracker.py:257][U03.05-2] |  |
| U03.06 | TODO | **Motion-image denoising**<br>Frame noise estimate -> raw or CuPy/CuCIM-denoised image for motion tracking. | [tracker.py:268][U03.06-1] |  |
| U03.07 | TODO | **Aircraft motion and phase state**<br>Primary aircraft box, previous/current frames and SAM -> serialized aircraft movement/arrival state. | [tracker.py:291][U03.07-1] |  |
| U03.08 | TODO | **Loader obstruction filtering**<br>Loader region + selected GSE/trailer detections -> observed/unobserved loader state. | [tracker.py:33][U03.08-1]; [tracker.py:330][U03.08-2] |  |
| U03.09 | TODO | **Segmentation-assisted vehicle motion**<br>Loader/GSE tracks + image pair + ignored-object boxes -> vehicle motion state and optical-flow evidence. | [tracker.py:348][U03.09-1]; [tracker.py:483][U03.09-2] |  |
| U03.10 | TODO | **Loader door-role assignment**<br>Parked loader + front/back doors, engine/wheel geometry and view -> front/back/undefined role. | [local_utils/bl_utils.py:4][U03.10-1]; [tracker.py:350][U03.10-2] |  |
| U03.11 | TODO | **Loader identity continuity**<br>New loader track + overlapping recent loader boxes -> transfer retained semantic state to replacement track. | [tracker.py:370][U03.11-1] |  |
| U03.12 | TODO | **GSE identity continuity**<br>New GSE track + previous box overlap -> retained vehicle state after ID change. | [tracker.py:454][U03.12-1] |  |
| U03.13 | TODO | **Tentative-worker backfill**<br>Newly confirmed worker ID + buffered tentative tracks -> corrected earlier worker records. | [tracker.py:430][U03.13-1] |  |
| U03.14 | TODO | **Arrival confirmation/backdating**<br>Provisional stopped frames + confirmed aircraft arrival -> retrospective arrival timestamp updates. | [tracker.py:55][U03.14-1]; [tracker.py:495][U03.14-2] |  |
| U03.15 | TODO | **Ordered tracking output buffers**<br>Buffered Track objects, confirmation delays and end-of-video -> published tracking NDJSON with nested private state. | [tracker.py:520][U03.15-1]; [tracker.py:562][U03.15-2] |  |

**Module notes / missing components:**


<a id="u04"></a>
## U04 - Shared CV library

Repository: [cv_common @ ac5098d2](https://gitlab.com/dxgat/utils/cv_common/-/tree/ac5098d2aae117b27a1e02a165a356ee016a755f).

**Consumed inputs:** Model/runtime configs, pixels/detections, track state and geometric inputs supplied by callers.

**Existing output:** Python APIs/classes rather than one pipeline stream.

**Review caution:** Standalone master is not every module dependency. Missing helper imports at selected pins must be resolved deliberately, not via blanket submodule update.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| U04.01 | TODO | **Model inference wrapper** **[LIBRARY]**<br>Model weights, image and prediction settings -> detections through a common wrapper. | [common.py:16][U04.01-1] |  |
| U04.02 | TODO | **Bounding-box measurement** **[LIBRARY]**<br>Boxes/points -> area, center, size and distance primitives. | [common.py:74][U04.02-1] |  |
| U04.03 | TODO | **Box overlap and intersection** **[LIBRARY]**<br>Box pairs -> overlap, IoU and relative-intersection measurements. | [common.py:113][U04.03-1]; [common.py:204][U04.03-2] |  |
| U04.04 | TODO | **ROI and coordinate conversion** **[LIBRARY]**<br>Boxes, offsets and point coordinates -> transformed boxes and containment tests. | [common.py:136][U04.04-1]; [common.py:287][U04.04-2] |  |
| U04.05 | TODO | **Configuration loading** **[LIBRARY]**<br>Shared and local YAML configuration -> merged detector settings. | [common.py:307][U04.05-1] |  |
| U04.06 | TODO | **Output-path lifecycle** **[LIBRARY]**<br>Requested output path and overwrite settings -> prepared output directory. | [common.py:328][U04.06-1] |  |
| U04.07 | TODO | **Ellipse/angle geometry** **[LIBRARY]**<br>Points/vectors and geometric parameters -> region contours and angle measurements. | [common.py:354][U04.07-1]; [common.py:439][U04.07-2] |  |
| U04.08 | TODO | **Image alignment** **[LIBRARY]**<br>Reference/current image pair -> feature-based aligned imagery for temporal comparison. | [common.py:372][U04.08-1] |  |
| U04.09 | TODO | **Obstacle filtering** **[LIBRARY]**<br>Box geometry and class/profile settings -> qualifying obstacles. | [common.py:470][U04.09-1] |  |
| U04.10 | TODO | **Mask component selection** **[LIBRARY]**<br>Binary mask -> largest connected component. | [common.py:522][U04.10-1] |  |
| U04.11 | TODO | **Motion-state representation** **[LIBRARY]**<br>Movement/stopping counters and history -> common ObjectState data. | [tracked_object.py:20][U04.11-1] |  |
| U04.12 | TODO | **Optical-flow feature initialization** **[LIBRARY]**<br>Image, object mask and excluded regions -> tracked feature-point seeds. | [tracked_object.py:111][U04.12-1] |  |
| U04.13 | TODO | **Optical-flow tracking** **[LIBRARY]**<br>Previous/current image + feature points -> LK point displacements and tracking quality. | [tracked_object.py:140][U04.13-1] |  |
| U04.14 | TODO | **Prompted object segmentation** **[LIBRARY]**<br>Image and object prompt -> segmentation mask via the supplied segmenter. | [tracked_object.py:175][U04.14-1] |  |
| U04.15 | TODO | **Motion analysis** **[LIBRARY]**<br>Feature displacements + motion profile -> moving/stopping/stopped evidence. | [tracked_object.py:203][U04.15-1] |  |
| U04.16 | TODO | **Recent-box history** **[LIBRARY]**<br>Recent object detections -> retained box window and representative bounds. | [tracked_object.py:326][U04.16-1] |  |
| U04.17 | TODO | **Tracked-object lifecycle** **[LIBRARY]**<br>Detection, images, segmentation and motion state -> updated persistent object state. | [tracked_object.py:341][U04.17-1] |  |
| U04.18 | TODO | **Private-state serialization/restoration** **[LIBRARY]**<br>Tracked object internals -> nested state dictionary and restored object, including algorithm-specific state. | [tracked_object.py:538][U04.18-1] |  |
| U04.19 | TODO | **Aircraft-specific feature region** **[LIBRARY]**<br>Aircraft geometry and part hints -> feature/segmentation seed region. | [transport.py:55][U04.19-1] |  |
| U04.20 | TODO | **Aircraft arrival/departure state machine** **[LIBRARY]**<br>Aircraft movement history + profile -> arrived/departed flags and event times. | [transport.py:78][U04.20-1] |  |
| U04.21 | TODO | **Vehicle-specific tracked state** **[LIBRARY]**<br>Generic tracked-object state + vehicle fields -> vehicle state and role-related data. | [transport.py:155][U04.21-1] |  |
| U04.22 | TODO | **Track metadata envelope** **[LIBRARY]**<br>Track ID, class, box and optional state/data -> serialized Track record. | [track.py:6][U04.22-1] |  |
| U04.23 | TODO | **Detection-box stabilization** **[LIBRARY]**<br>Detection history -> stabilized bounding box. | [detections.py:4][U04.23-1] |  |
| U04.24 | TODO | **File-video decoding and frame access** **[LIBRARY]**<br>File source + decode settings -> frame iterator and source frame access. | [utils/datasets.py:158][U04.24-1] |  |
| U04.25 | TODO | **Live-stream reader** **[LIBRARY]**<br>Stream source -> frame iterator utility; existence does not mean VideoWorker currently accepts live sources. | [utils/datasets.py:333][U04.25-1] |  |
| U04.26 | TODO | **Image noise/mode estimation** **[LIBRARY]**<br>Frame history -> preprocessing mode, noise summary and broken/heavy image flags. | [image_preprocessing.py:10][U04.26-1]; [image_preprocessing.py:99][U04.26-2] |  |
| U04.27 | TODO | **Adaptive image filtering** **[LIBRARY]**<br>Image + selected quality mode -> preprocessed image. | [image_preprocessing.py:58][U04.27-1] |  |
| U04.28 | TODO | **Structured evidence logging** **[LIBRARY]**<br>Frame-indexed local state -> JSON/NDJSON history with missing-frame filling. | [log_utils.py:26][U04.28-1] |  |
| U04.29 | TODO | **Report time and CSV conversion** **[LIBRARY]**<br>Frame/time values and result records -> formatted report times, timestamps and CSV. | [log_utils.py:139][U04.29-1] |  |
| U04.30 | TODO | **Code-version provenance** **[LIBRARY]**<br>Repository paths -> Git commit identifiers included in evidence. | [log_utils.py:186][U04.30-1] |  |

**Module notes / missing components:**


<a id="u05"></a>
## U05 - Media, artifact, worker and reporting infrastructure

Repository: [db_worker @ 5a4aa83d](https://gitlab.com/dxgat/utils/db_worker/-/tree/5a4aa83d828695e0f227038eaa2ff96af57f7cca).

**Consumed inputs:** Media/storage/DB/Kafka configuration, model and task IDs, weights/inference artifacts and module return values.

**Existing output:** NDJSON, task statuses/reports/timelines, technical artifacts and job execution status.

**Review caution:** Replace positional row joins and private filename conventions with explicit identity. Legacy tuple/task-array adapters must preserve multiple results and optional extras.

| ID | Decision | Component: inputs -> output / behavior | Evidence | Your notes |
| --- | --- | --- | --- | --- |
| U05.01 | TODO | **Worker/job identity configuration**<br>Video, module and environment parameters -> source, metadata artifact and messaging identities. | [ML_worker.py:129][U05.01-1] |  |
| U05.02 | TODO | **File-source loading**<br>Source string -> file video reader; current wrapper explicitly rejects live RTSP/HTTP sources. | [ML_worker.py:225][U05.02-1] |  |
| U05.03 | TODO | **Metadata artifact download**<br>Required upstream model names + video identity -> local inference files from cloud storage. | [ML_worker.py:323][U05.03-1] |  |
| U05.04 | TODO | **NDJSON decoding**<br>Inference files -> per-model record iterators. | [ML_worker.py:257][U05.04-1] |  |
| U05.05 | TODO | **Upstream metadata join**<br>Per-model iterators -> one metadata dictionary by positional zip/first value, without an event-time join. | [ML_worker.py:240][U05.05-1] |  |
| U05.06 | TODO | **Metadata writer initialization**<br>Model/video identity and output mode -> NDJSON output handle. | [ML_worker.py:210][U05.06-1] |  |
| U05.07 | TODO | **Per-frame result publication**<br>Model payload + publication call -> serialized record or messaging payload; internal counter does not honor supplied frame_id. | [ML_worker.py:290][U05.07-1] |  |
| U05.08 | TODO | **Kafka topic setup**<br>Video/model topic identities -> producer/consumer topic configuration. | [ML_worker.py:384][U05.08-1]; [ML_worker.py:410][U05.08-2] |  |
| U05.09 | TODO | **Kafka input collection**<br>Messages from upstream consumers -> combined metadata by arrival order, not keyed event-time alignment. | [ML_worker.py:395][U05.09-1] |  |
| U05.10 | TODO | **Kafka output delivery**<br>Serialized model payload -> producer send to the downstream topic. | [ML_worker.py:406][U05.10-1] |  |
| U05.11 | TODO | **Completion and archive lifecycle**<br>End marker and worker close -> topic/file archive and resource cleanup. | [ML_worker.py:468][U05.11-1] |  |
| U05.12 | TODO | **Inference artifact upload**<br>Completed local metadata files -> cloud inference artifacts. | [ML_worker.py:359][U05.12-1] |  |
| U05.13 | TODO | **Retry and cloud-transfer helpers**<br>Transfer operation and failure -> bounded retries for upload/download. | [ML_worker.py:52][U05.13-1]; [ML_worker.py:80][U05.13-2] |  |
| U05.14 | TODO | **GM-derived configuration handoff**<br>GM camera type and stop frame -> report/config updates consumed by later stages. | [ML_worker.py:439][U05.14-1] |  |
| U05.15 | TODO | **Runtime configuration preparation**<br>Job/video settings -> production detector configuration mutations. | [model_starter.py:45][U05.15-1] |  |
| U05.16 | TODO | **Model-weight provisioning**<br>Repository/DVC configuration -> downloaded weights before inference. | [model_starter.py:58][U05.16-1] |  |
| U05.17 | TODO | **General-model job runner**<br>Job source/config -> invoked GM and upstream job outcome. | [model_starter.py:73][U05.17-1] |  |
| U05.18 | TODO | **Tracker job runner**<br>GM metadata + source/config -> tracker execution and job outcome. | [model_starter.py:147][U05.18-1] |  |
| U05.19 | TODO | **Downstream module invocation**<br>Task identifier, source and metadata -> dynamically imported detector call. | [model_starter.py:195][U05.19-1] |  |
| U05.20 | TODO | **Multi-result/task output mapping**<br>Detector return arrays and task mapping -> individual compliance results, reports and timelines. | [model_starter.py:280][U05.20-1] |  |
| U05.21 | TODO | **Technical failure reporting**<br>Runtime exceptions or failed processing -> error report distinct from a compliance Fail. | [model_starter.py:304][U05.21-1]; [send_report.py:27][U05.21-2] |  |
| U05.22 | TODO | **Report validation and delivery**<br>Module result fields and evidence -> validated report object and HTTP delivery. | [send_report.py:53][U05.22-1]; [send_report.py:74][U05.22-2] |  |

**Module notes / missing components:**

## After Your Review

1. Resolve modifications, missing items and terminology while retaining the occurrence IDs.
2. Compare accepted occurrences by actual input/output contracts, state ownership, coordinate systems, model/preprocessing profiles, temporal windows and latency requirements.
3. Agree on shared components versus profiled variants versus module-local policies. Similarity alone is not evidence of interchangeability.
4. Group accepted components into practical pipeline nodes. Produce a module-by-component reuse matrix, then group modules from that matrix, not their business descriptions.
5. Draw the graph only after these boundaries are agreed. Map every node and module edge back to accepted IDs.

No sharing groups or new graph are approved by this worksheet. Existing [simplified hierarchy](../hierarchy.svg), [overview](../overview.svg) and [original detailed graph source](../detailed-dependencies.dot) remain unchanged, together with the [earlier analysis](../README.md).

## Review Progress

`REVIEW.md` is the editable source of your decisions. The companion script only reads it when checking progress. Creation refuses to overwrite either this file or its source manifest.

From the workspace root:

```powershell
python analysis/architecture/component_review/review.py check
```

Add `--json` for parsed row decisions and notes, or `--verify-sources` to recheck the pinned source hashes. Module-wide notes remain in this document and must also be read in the next analysis pass. The [source manifest](source_manifest.json) records immutable baselines, source hashes and initial row definitions. The utility sections describe their own baselines; each consumer's exact submodule pins are retained in that manifest.

<!-- Immutable source-link definitions. Keep these when editing decisions. -->

[M01.01-1]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L127-212
[M01.01-2]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L452-549
[M01.02-1]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L35-68
[M01.03-1]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L127-212
[M01.03-2]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L372-375
[M01.04-1]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L267-285
[M01.05-1]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L288-320
[M01.05-2]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L210-212
[M01.06-1]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L156-197
[M01.06-2]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/local_config.yaml#L13-15
[M01.07-1]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L232-264
[M01.07-2]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L431-449
[M01.08-1]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L186-199
[M01.08-2]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L372-385
[M01.09-1]: https://gitlab.com/dxgat/detectors/3-stop-brake-check/-/blob/3a2337c18620b1678fb6ecc1aad9014a31a07861/main.py#L388-428
[M02.01-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L93-123
[M02.02-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L125-179
[M02.03-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L1241-1286
[M02.04-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L1091-1102
[M02.04-2]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L1524-1548
[M02.05-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L1562-1612
[M02.06-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L201-223
[M02.07-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L296-328
[M02.08-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L330-385
[M02.09-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L405-443
[M02.10-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L515-569
[M02.11-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L571-657
[M02.12-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L659-757
[M02.13-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L759-850
[M02.14-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L1227-1231
[M02.14-2]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L659-757
[M02.15-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L853-923
[M02.16-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L953-1022
[M02.17-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L1025-1060
[M02.18-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L1025-1060
[M02.18-2]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L1139-1211
[M02.19-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L225-231
[M02.19-2]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L1139-1211
[M02.20-1]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L33-79
[M02.20-2]: https://gitlab.com/dxgat/detectors/aircraft-chocks/-/blob/fa00478f4fd64e0eebb7fa0975cdc0f286c60878/main.py#L1766-1783
[M03.01-1]: https://gitlab.com/dxgat/detectors/all-cargo-bin-doors-opened-and-verified/-/blob/ac2707cb485e5bedd691fbf8c3d87303373349f5/main.py#L22-154
[M03.02-1]: https://gitlab.com/dxgat/detectors/all-cargo-bin-doors-opened-and-verified/-/blob/ac2707cb485e5bedd691fbf8c3d87303373349f5/main.py#L155-205
[M03.03-1]: https://gitlab.com/dxgat/detectors/all-cargo-bin-doors-opened-and-verified/-/blob/ac2707cb485e5bedd691fbf8c3d87303373349f5/main.py#L155-205
[M03.04-1]: https://gitlab.com/dxgat/detectors/all-cargo-bin-doors-opened-and-verified/-/blob/ac2707cb485e5bedd691fbf8c3d87303373349f5/main.py#L217-244
[M03.05-1]: https://gitlab.com/dxgat/detectors/all-cargo-bin-doors-opened-and-verified/-/blob/ac2707cb485e5bedd691fbf8c3d87303373349f5/main.py#L217-244
[M03.06-1]: https://gitlab.com/dxgat/detectors/all-cargo-bin-doors-opened-and-verified/-/blob/ac2707cb485e5bedd691fbf8c3d87303373349f5/main.py#L217-267
[M03.07-1]: https://gitlab.com/dxgat/detectors/all-cargo-bin-doors-opened-and-verified/-/blob/ac2707cb485e5bedd691fbf8c3d87303373349f5/main.py#L269-296
[M03.08-1]: https://gitlab.com/dxgat/detectors/all-cargo-bin-doors-opened-and-verified/-/blob/ac2707cb485e5bedd691fbf8c3d87303373349f5/main.py#L269-302
[M04.01-1]: https://gitlab.com/dxgat/detectors/beltloader-chocks/-/blob/7056099b498dae42ae53e20d29fd9241f6a05939/main.py#L169-230
[M04.02-1]: https://gitlab.com/dxgat/detectors/beltloader-chocks/-/blob/7056099b498dae42ae53e20d29fd9241f6a05939/main.py#L232-265
[M04.03-1]: https://gitlab.com/dxgat/detectors/beltloader-chocks/-/blob/7056099b498dae42ae53e20d29fd9241f6a05939/main.py#L267-291
[M04.04-1]: https://gitlab.com/dxgat/detectors/beltloader-chocks/-/blob/7056099b498dae42ae53e20d29fd9241f6a05939/main.py#L69-95
[M04.05-1]: https://gitlab.com/dxgat/detectors/beltloader-chocks/-/blob/7056099b498dae42ae53e20d29fd9241f6a05939/main.py#L98-132
[M04.06-1]: https://gitlab.com/dxgat/detectors/beltloader-chocks/-/blob/7056099b498dae42ae53e20d29fd9241f6a05939/main.py#L134-151
[M04.07-1]: https://gitlab.com/dxgat/detectors/beltloader-chocks/-/blob/7056099b498dae42ae53e20d29fd9241f6a05939/main.py#L326-368
[M04.08-1]: https://gitlab.com/dxgat/detectors/beltloader-chocks/-/blob/7056099b498dae42ae53e20d29fd9241f6a05939/main.py#L309-316
[M04.09-1]: https://gitlab.com/dxgat/detectors/beltloader-chocks/-/blob/7056099b498dae42ae53e20d29fd9241f6a05939/main.py#L23-50
[M05.01-1]: https://gitlab.com/dxgat/detectors/bl_rear_cone/-/blob/d75f1f8b026c0a12645f8792bb35a139554df7de/main.py#L199-260
[M05.02-1]: https://gitlab.com/dxgat/detectors/bl_rear_cone/-/blob/d75f1f8b026c0a12645f8792bb35a139554df7de/main.py#L262-295
[M05.03-1]: https://gitlab.com/dxgat/detectors/bl_rear_cone/-/blob/d75f1f8b026c0a12645f8792bb35a139554df7de/main.py#L297-320
[M05.04-1]: https://gitlab.com/dxgat/detectors/bl_rear_cone/-/blob/d75f1f8b026c0a12645f8792bb35a139554df7de/main.py#L72-98
[M05.05-1]: https://gitlab.com/dxgat/detectors/bl_rear_cone/-/blob/d75f1f8b026c0a12645f8792bb35a139554df7de/main.py#L100-127
[M05.06-1]: https://gitlab.com/dxgat/detectors/bl_rear_cone/-/blob/d75f1f8b026c0a12645f8792bb35a139554df7de/main.py#L129-161
[M05.07-1]: https://gitlab.com/dxgat/detectors/bl_rear_cone/-/blob/d75f1f8b026c0a12645f8792bb35a139554df7de/main.py#L163-181
[M05.08-1]: https://gitlab.com/dxgat/detectors/bl_rear_cone/-/blob/d75f1f8b026c0a12645f8792bb35a139554df7de/main.py#L23-50
[M06.01-1]: https://gitlab.com/dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival/-/blob/1413225fbbb9c4e7e04be82f9d5aa8f96ad2e379/main.py#L21-37
[M06.02-1]: https://gitlab.com/dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival/-/blob/1413225fbbb9c4e7e04be82f9d5aa8f96ad2e379/main.py#L40-179
[M06.03-1]: https://gitlab.com/dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival/-/blob/1413225fbbb9c4e7e04be82f9d5aa8f96ad2e379/main.py#L100-182
[M06.04-1]: https://gitlab.com/dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival/-/blob/1413225fbbb9c4e7e04be82f9d5aa8f96ad2e379/main.py#L184-190
[M06.05-1]: https://gitlab.com/dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival/-/blob/1413225fbbb9c4e7e04be82f9d5aa8f96ad2e379/main.py#L195-213
[M06.06-1]: https://gitlab.com/dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival/-/blob/1413225fbbb9c4e7e04be82f9d5aa8f96ad2e379/main.py#L179-182
[M06.07-1]: https://gitlab.com/dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival/-/blob/1413225fbbb9c4e7e04be82f9d5aa8f96ad2e379/main.py#L265-283
[M06.08-1]: https://gitlab.com/dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival/-/blob/1413225fbbb9c4e7e04be82f9d5aa8f96ad2e379/main.py#L285-296
[M07.01-1]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L280-325
[M07.02-1]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L308-400
[M07.03-1]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L24-41
[M07.03-2]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L89-102
[M07.04-1]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L43-102
[M07.05-1]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L104-136
[M07.05-2]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L191-224
[M07.06-1]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L138-158
[M07.07-1]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L159-168
[M07.08-1]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L169-224
[M07.09-1]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L43-84
[M07.10-1]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L227-227
[M07.10-2]: https://gitlab.com/dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed/-/blob/940fdfc526f83839573434a6ee96d955a7f3d6cd/main.py#L429-457
[M08.01-1]: https://gitlab.com/dxgat/detectors/cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked/-/blob/e2a25ba3e97ceb403fcde512e78e8368e83d3aee/main.py#L31-56
[M08.02-1]: https://gitlab.com/dxgat/detectors/cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked/-/blob/e2a25ba3e97ceb403fcde512e78e8368e83d3aee/main.py#L199-208
[M08.03-1]: https://gitlab.com/dxgat/detectors/cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked/-/blob/e2a25ba3e97ceb403fcde512e78e8368e83d3aee/main.py#L215-246
[M08.04-1]: https://gitlab.com/dxgat/detectors/cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked/-/blob/e2a25ba3e97ceb403fcde512e78e8368e83d3aee/main.py#L275-308
[M08.05-1]: https://gitlab.com/dxgat/detectors/cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked/-/blob/e2a25ba3e97ceb403fcde512e78e8368e83d3aee/main.py#L338-389
[M08.06-1]: https://gitlab.com/dxgat/detectors/cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked/-/blob/e2a25ba3e97ceb403fcde512e78e8368e83d3aee/main.py#L338-389
[M08.07-1]: https://gitlab.com/dxgat/detectors/cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked/-/blob/e2a25ba3e97ceb403fcde512e78e8368e83d3aee/main.py#L338-389
[M09.01-1]: https://gitlab.com/dxgat/detectors/cones-placed-in-proper-positions-and-timely/-/blob/b2c53f69c29610fae5c83d748e64592fcbc43408/main.py#L140-146
[M09.02-1]: https://gitlab.com/dxgat/detectors/cones-placed-in-proper-positions-and-timely/-/blob/b2c53f69c29610fae5c83d748e64592fcbc43408/main.py#L148-285
[M09.03-1]: https://gitlab.com/dxgat/detectors/cones-placed-in-proper-positions-and-timely/-/blob/b2c53f69c29610fae5c83d748e64592fcbc43408/main.py#L262-285
[M09.04-1]: https://gitlab.com/dxgat/detectors/cones-placed-in-proper-positions-and-timely/-/blob/b2c53f69c29610fae5c83d748e64592fcbc43408/main.py#L77-107
[M09.05-1]: https://gitlab.com/dxgat/detectors/cones-placed-in-proper-positions-and-timely/-/blob/b2c53f69c29610fae5c83d748e64592fcbc43408/main.py#L312-348
[M09.06-1]: https://gitlab.com/dxgat/detectors/cones-placed-in-proper-positions-and-timely/-/blob/b2c53f69c29610fae5c83d748e64592fcbc43408/main.py#L312-372
[M10.01-1]: https://gitlab.com/dxgat/detectors/crew-present-10-minutes-prior-to-aircraft-arrival/-/blob/5cfd25c92c4a9765817505684ebcc3e4bb4755a2/main.py#L29-154
[M10.01-2]: https://gitlab.com/dxgat/detectors/crew-present-10-minutes-prior-to-aircraft-arrival/-/blob/5cfd25c92c4a9765817505684ebcc3e4bb4755a2/main.py#L211-222
[M10.02-1]: https://gitlab.com/dxgat/detectors/crew-present-10-minutes-prior-to-aircraft-arrival/-/blob/5cfd25c92c4a9765817505684ebcc3e4bb4755a2/main.py#L155-210
[M10.03-1]: https://gitlab.com/dxgat/detectors/crew-present-10-minutes-prior-to-aircraft-arrival/-/blob/5cfd25c92c4a9765817505684ebcc3e4bb4755a2/main.py#L224-257
[M10.04-1]: https://gitlab.com/dxgat/detectors/crew-present-10-minutes-prior-to-aircraft-arrival/-/blob/5cfd25c92c4a9765817505684ebcc3e4bb4755a2/main.py#L224-290
[M10.05-1]: https://gitlab.com/dxgat/detectors/crew-present-10-minutes-prior-to-aircraft-arrival/-/blob/5cfd25c92c4a9765817505684ebcc3e4bb4755a2/main.py#L224-314
[M10.06-1]: https://gitlab.com/dxgat/detectors/crew-present-10-minutes-prior-to-aircraft-arrival/-/blob/5cfd25c92c4a9765817505684ebcc3e4bb4755a2/main.py#L259-314
[M11.01-1]: https://gitlab.com/dxgat/detectors/fod-walk-completed/-/blob/b923b5c830a6520626fc039609af33f988699bff/main.py#L422-455
[M11.02-1]: https://gitlab.com/dxgat/detectors/fod-walk-completed/-/blob/b923b5c830a6520626fc039609af33f988699bff/main.py#L286-287
[M11.02-2]: https://gitlab.com/dxgat/detectors/fod-walk-completed/-/blob/b923b5c830a6520626fc039609af33f988699bff/main.py#L422-475
[M11.03-1]: https://gitlab.com/dxgat/detectors/fod-walk-completed/-/blob/b923b5c830a6520626fc039609af33f988699bff/main.py#L30-42
[M11.04-1]: https://gitlab.com/dxgat/detectors/fod-walk-completed/-/blob/b923b5c830a6520626fc039609af33f988699bff/main.py#L179-230
[M11.05-1]: https://gitlab.com/dxgat/detectors/fod-walk-completed/-/blob/b923b5c830a6520626fc039609af33f988699bff/main.py#L112-154
[M11.06-1]: https://gitlab.com/dxgat/detectors/fod-walk-completed/-/blob/b923b5c830a6520626fc039609af33f988699bff/main.py#L422-475
[M11.07-1]: https://gitlab.com/dxgat/detectors/fod-walk-completed/-/blob/b923b5c830a6520626fc039609af33f988699bff/main.py#L179-240
[M11.08-1]: https://gitlab.com/dxgat/detectors/fod-walk-completed/-/blob/b923b5c830a6520626fc039609af33f988699bff/main.py#L488-534
[M11.09-1]: https://gitlab.com/dxgat/detectors/fod-walk-completed/-/blob/b923b5c830a6520626fc039609af33f988699bff/main.py#L44-63
[M11.09-2]: https://gitlab.com/dxgat/detectors/fod-walk-completed/-/blob/b923b5c830a6520626fc039609af33f988699bff/main.py#L488-534
[M12.01-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L144-231
[M12.02-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L233-317
[M12.03-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L353-396
[M12.04-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L399-412
[M12.05-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L415-459
[M12.06-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L473-495
[M12.07-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L497-522
[M12.08-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L536-585
[M12.09-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L1354-1362
[M12.09-2]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L587-654
[M12.10-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L587-654
[M12.11-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L656-727
[M12.12-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L799-894
[M12.13-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L896-1026
[M12.13-2]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L1132-1240
[M12.14-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L1028-1130
[M12.14-2]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L1354-1362
[M12.15-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L1251-1254
[M12.16-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L1313-1338
[M12.17-1]: https://gitlab.com/dxgat/detectors/gse-chocks/-/blob/3160b871f5130f206323b9398fb1233d6b07ed2c/main.py#L27-71
[M13.01-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L43-51
[M13.02-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L29-41
[M13.02-2]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L53-71
[M13.03-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L762-797
[M13.04-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L248-274
[M13.04-2]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L391-520
[M13.05-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L140-200
[M13.06-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L202-220
[M13.07-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L338-370
[M13.07-2]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L522-589
[M13.08-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L276-332
[M13.09-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L276-332
[M13.10-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L606-665
[M13.11-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L675-717
[M13.11-2]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L276-332
[M13.12-1]: https://gitlab.com/dxgat/detectors/hand-signals/-/blob/6bd027f2ef9f946fd3d6331cf1d542bd098e83c9/main.py#L73-113
[M14.01-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L110-134
[M14.02-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L589-614
[M14.03-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L137-151
[M14.03-2]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L589-614
[M14.04-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L154-168
[M14.05-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L230-245
[M14.06-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L248-258
[M14.06-2]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L589-614
[M14.07-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L261-300
[M14.08-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L303-360
[M14.08-2]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L530-541
[M14.09-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L363-422
[M14.10-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L457-494
[M14.10-2]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L589-614
[M14.11-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L425-454
[M14.12-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L663-735
[M14.13-1]: https://gitlab.com/dxgat/detectors/handrails-on-gse-being-used/-/blob/59fbced4161066945fdde6d45ee5a82132dde33b/main.py#L28-76
[M15.01-1]: https://gitlab.com/dxgat/detectors/lead-marshaller-and-wing-walkers-in-position/-/blob/9b37ccffc380093f506bf0507919437b336aa172/main.py#L286-338
[M15.02-1]: https://gitlab.com/dxgat/detectors/lead-marshaller-and-wing-walkers-in-position/-/blob/9b37ccffc380093f506bf0507919437b336aa172/main.py#L43-123
[M15.03-1]: https://gitlab.com/dxgat/detectors/lead-marshaller-and-wing-walkers-in-position/-/blob/9b37ccffc380093f506bf0507919437b336aa172/main.py#L43-123
[M15.04-1]: https://gitlab.com/dxgat/detectors/lead-marshaller-and-wing-walkers-in-position/-/blob/9b37ccffc380093f506bf0507919437b336aa172/main.py#L70-123
[M15.05-1]: https://gitlab.com/dxgat/detectors/lead-marshaller-and-wing-walkers-in-position/-/blob/9b37ccffc380093f506bf0507919437b336aa172/main.py#L125-197
[M15.06-1]: https://gitlab.com/dxgat/detectors/lead-marshaller-and-wing-walkers-in-position/-/blob/9b37ccffc380093f506bf0507919437b336aa172/main.py#L125-197
[M16.01-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L50-62
[M16.02-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L64-88
[M16.03-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L505-554
[M16.04-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L435-457
[M16.05-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L174-183
[M16.06-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L496-499
[M16.06-2]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L236-296
[M16.07-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L236-296
[M16.08-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L236-296
[M16.08-2]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L349-356
[M16.09-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L299-328
[M16.10-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L466-477
[M16.10-2]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L663-678
[M16.11-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L755-770
[M16.12-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L894-941
[M16.13-1]: https://gitlab.com/dxgat/detectors/pin-verification/-/blob/8e1863c76bb97f9818e935e10d58f877637ed1c1/main.py#L894-941
[M17.01-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/main.py#L35-89
[M17.02-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/utils/detection_preprocessor.py#L11-26
[M17.03-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/states.py#L31-109
[M17.04-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/states.py#L112-195
[M17.05-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/states.py#L312-349
[M17.06-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/_pose_model.py#L18-23
[M17.07-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/distance_estimator.py#L56-87
[M17.07-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/distance_estimator.py#L243-275
[M17.08-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/detection_processor.py#L34-60
[M17.09-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/temp/airplane_parts_container.py#L49-58
[M17.10-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/temp/plane_tdv_extractor.py#L109-157
[M17.11-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/temp/plane_tdv_extractor.py#L65-98
[M17.11-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/temp/plane_tdv_extractor.py#L159-161
[M17.12-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/temp/plane_tdv_extractor.py#L163-311
[M17.13-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/temp/plane_tdv_extractor.py#L313-355
[M17.14-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L201-232
[M17.15-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L276-304
[M17.16-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/preprocessing/preprocessing.py#L22-35
[M17.16-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L531-585
[M17.17-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/preprocessing/preprocessing.py#L121-132
[M17.17-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L531-585
[M17.18-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/preprocessing/preprocessing.py#L66-95
[M17.18-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L531-585
[M17.19-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/preprocessing/preprocessing.py#L140-186
[M17.20-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/preprocessing/splitter.py#L14-23
[M17.20-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/preprocessing/splitter.py#L68-104
[M17.21-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/preprocessing/recombination.py#L48-115
[M17.21-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/preprocessing/recombination.py#L177-270
[M17.22-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/temp/canvas_factory.py#L22-141
[M17.22-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L318-339
[M17.23-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/model/predictor.py#L59-125
[M17.23-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L330-344
[M17.24-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/decision_policy.py#L41-94
[M17.25-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L360-389
[M17.25-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/local_config.yaml#L33-48
[M17.26-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L393-411
[M17.26-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/local_config.yaml#L33-48
[M17.27-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L307-315
[M17.27-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L470-506
[M17.28-1]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/code/walk_around/walk_around.py#L415-421
[M17.28-2]: https://gitlab.com/dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately/-/blob/a0d9ee4f338bfe3a8b177f8e4db28b31196e90e2/main.py#L92-146
[M18.01-1]: https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle/-/blob/5c8a75999651b9cad591d9ae2b65f1af6d309811/main.py#L1-35
[M18.02-1]: https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle/-/blob/5c8a75999651b9cad591d9ae2b65f1af6d309811/main.py#L159-198
[M18.03-1]: https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle/-/blob/5c8a75999651b9cad591d9ae2b65f1af6d309811/main.py#L201-282
[M18.04-1]: https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle/-/blob/5c8a75999651b9cad591d9ae2b65f1af6d309811/main.py#L285-309
[M18.05-1]: https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle/-/blob/5c8a75999651b9cad591d9ae2b65f1af6d309811/main.py#L319-340
[M18.06-1]: https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle/-/blob/5c8a75999651b9cad591d9ae2b65f1af6d309811/main.py#L344-543
[M18.07-1]: https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle/-/blob/5c8a75999651b9cad591d9ae2b65f1af6d309811/main.py#L544-570
[M18.08-1]: https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle/-/blob/5c8a75999651b9cad591d9ae2b65f1af6d309811/main.py#L77-140
[M18.09-1]: https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle/-/blob/5c8a75999651b9cad591d9ae2b65f1af6d309811/main.py#L571-613
[M18.10-1]: https://gitlab.com/dxgat/detectors/pre-arrival-safety-huddle/-/blob/5c8a75999651b9cad591d9ae2b65f1af6d309811/main.py#L614-661
[M19.01-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/main.py#L42-126
[M19.02-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/utils/detection_preprocessor.py#L11-26
[M19.03-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/states.py#L37-117
[M19.04-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/states.py#L173-374
[M19.05-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/states.py#L945-1006
[M19.06-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/states.py#L17-18
[M19.06-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/states.py#L1010-1033
[M19.07-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/states.py#L750-858
[M19.07-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/local_config.yaml#L60-61
[M19.08-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/pushback_obstruction_detector.py#L167-226
[M19.09-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/pushback_obstruction_detector.py#L228-312
[M19.10-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/pushback_obstruction_detector.py#L349-413
[M19.10-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/pushback_obstruction_detector.py#L519-573
[M19.11-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/_pose_model.py#L18-23
[M19.12-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/distance_estimator.py#L56-81
[M19.13-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L79-95
[M19.14-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/temp/plane_tdv_extractor.py#L67-100
[M19.14-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/temp/plane_tdv_extractor.py#L161-164
[M19.15-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/temp/plane_tdv_extractor.py#L166-321
[M19.16-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/temp/plane_tdv_extractor.py#L323-470
[M19.17-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L296-329
[M19.18-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L676-699
[M19.19-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/preprocessing/preprocessing.py#L22-35
[M19.19-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L701-780
[M19.20-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/preprocessing/preprocessing.py#L66-132
[M19.20-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L701-780
[M19.21-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/preprocessing/preprocessing.py#L140-186
[M19.22-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/preprocessing/splitter.py#L68-106
[M19.23-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/preprocessing/recombination.py#L42-114
[M19.23-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/preprocessing/recombination.py#L177-271
[M19.24-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L457-495
[M19.25-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L215-293
[M19.25-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L490-500
[M19.26-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L490-507
[M19.26-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/local_config.yaml#L66-69
[M19.27-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L515-533
[M19.27-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/local_config.yaml#L66-71
[M19.28-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L539-558
[M19.28-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/local_config.yaml#L72-81
[M19.29-1]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L450-454
[M19.29-2]: https://gitlab.com/dxgat/detectors/pre-departure-walk-around-completed/-/blob/e407de23c3226bf49d19f1755c40cfb53176159b/code/walk_around/walk_around.py#L560-573
[M20.01-1]: https://gitlab.com/dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready/-/blob/f3b041cbccdf96158d585def3798d3749bb32529/main.py#L31-49
[M20.02-1]: https://gitlab.com/dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready/-/blob/f3b041cbccdf96158d585def3798d3749bb32529/main.py#L52-72
[M20.03-1]: https://gitlab.com/dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready/-/blob/f3b041cbccdf96158d585def3798d3749bb32529/main.py#L147-153
[M20.04-1]: https://gitlab.com/dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready/-/blob/f3b041cbccdf96158d585def3798d3749bb32529/main.py#L156-269
[M20.05-1]: https://gitlab.com/dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready/-/blob/f3b041cbccdf96158d585def3798d3749bb32529/main.py#L427-440
[M20.06-1]: https://gitlab.com/dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready/-/blob/f3b041cbccdf96158d585def3798d3749bb32529/main.py#L538-566
[M20.07-1]: https://gitlab.com/dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready/-/blob/f3b041cbccdf96158d585def3798d3749bb32529/main.py#L272-289
[M20.08-1]: https://gitlab.com/dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready/-/blob/f3b041cbccdf96158d585def3798d3749bb32529/main.py#L156-205
[M20.08-2]: https://gitlab.com/dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready/-/blob/f3b041cbccdf96158d585def3798d3749bb32529/main.py#L272-289
[M21.01-1]: https://gitlab.com/dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles/-/blob/104db85a4708e78a9abf779191a871b002a21d38/main.py#L98-132
[M21.02-1]: https://gitlab.com/dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles/-/blob/104db85a4708e78a9abf779191a871b002a21d38/main.py#L134-150
[M21.03-1]: https://gitlab.com/dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles/-/blob/104db85a4708e78a9abf779191a871b002a21d38/main.py#L196-198
[M21.03-2]: https://gitlab.com/dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles/-/blob/104db85a4708e78a9abf779191a871b002a21d38/main.py#L201-362
[M21.04-1]: https://gitlab.com/dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles/-/blob/104db85a4708e78a9abf779191a871b002a21d38/main.py#L303-362
[M21.05-1]: https://gitlab.com/dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles/-/blob/104db85a4708e78a9abf779191a871b002a21d38/main.py#L430-557
[M21.06-1]: https://gitlab.com/dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles/-/blob/104db85a4708e78a9abf779191a871b002a21d38/main.py#L430-557
[M21.07-1]: https://gitlab.com/dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles/-/blob/104db85a4708e78a9abf779191a871b002a21d38/main.py#L430-557
[M21.08-1]: https://gitlab.com/dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles/-/blob/104db85a4708e78a9abf779191a871b002a21d38/main.py#L430-574
[M22.01-1]: https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended/-/blob/8b9a2a9b0c16edbe91f50dea30b644bc79d420e4/main.py#L63-77
[M22.02-1]: https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended/-/blob/8b9a2a9b0c16edbe91f50dea30b644bc79d420e4/main.py#L242-291
[M22.03-1]: https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended/-/blob/8b9a2a9b0c16edbe91f50dea30b644bc79d420e4/local_config.yaml#L3-3
[M22.03-2]: https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended/-/blob/8b9a2a9b0c16edbe91f50dea30b644bc79d420e4/main.py#L277-291
[M22.04-1]: https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended/-/blob/8b9a2a9b0c16edbe91f50dea30b644bc79d420e4/main.py#L277-291
[M22.05-1]: https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended/-/blob/8b9a2a9b0c16edbe91f50dea30b644bc79d420e4/main.py#L79-102
[M22.06-1]: https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended/-/blob/8b9a2a9b0c16edbe91f50dea30b644bc79d420e4/main.py#L63-77
[M22.06-2]: https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended/-/blob/8b9a2a9b0c16edbe91f50dea30b644bc79d420e4/local_config.yaml#L19-21
[M22.07-1]: https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended/-/blob/8b9a2a9b0c16edbe91f50dea30b644bc79d420e4/main.py#L23-46
[M22.08-1]: https://gitlab.com/dxgat/detectors/safety-handrails-fully-extended/-/blob/8b9a2a9b0c16edbe91f50dea30b644bc79d420e4/main.py#L23-46
[M23.01-1]: https://gitlab.com/dxgat/detectors/safety-vests-secured-to-body/-/blob/ae8ef164a82c023fd99594913e4920306f2b40a3/main.py#L50-112
[M23.02-1]: https://gitlab.com/dxgat/detectors/safety-vests-secured-to-body/-/blob/ae8ef164a82c023fd99594913e4920306f2b40a3/main.py#L50-112
[M23.03-1]: https://gitlab.com/dxgat/detectors/safety-vests-secured-to-body/-/blob/ae8ef164a82c023fd99594913e4920306f2b40a3/main.py#L268-298
[M23.04-1]: https://gitlab.com/dxgat/detectors/safety-vests-secured-to-body/-/blob/ae8ef164a82c023fd99594913e4920306f2b40a3/main.py#L268-298
[M23.05-1]: https://gitlab.com/dxgat/detectors/safety-vests-secured-to-body/-/blob/ae8ef164a82c023fd99594913e4920306f2b40a3/main.py#L115-140
[M23.06-1]: https://gitlab.com/dxgat/detectors/safety-vests-secured-to-body/-/blob/ae8ef164a82c023fd99594913e4920306f2b40a3/main.py#L144-184
[M23.07-1]: https://gitlab.com/dxgat/detectors/safety-vests-secured-to-body/-/blob/ae8ef164a82c023fd99594913e4920306f2b40a3/main.py#L209-231
[M23.08-1]: https://gitlab.com/dxgat/detectors/safety-vests-secured-to-body/-/blob/ae8ef164a82c023fd99594913e4920306f2b40a3/main.py#L428-441
[M24.01-1]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L546-619
[M24.02-1]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L632-677
[M24.03-1]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L716-745
[M24.04-1]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L747-764
[M24.05-1]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L831-975
[M24.05-2]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L1150-1233
[M24.06-1]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L831-975
[M24.06-2]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L1234-1444
[M24.07-1]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L969-975
[M24.07-2]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L1150-1233
[M24.08-1]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L1445-1485
[M24.09-1]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L800-828
[M24.10-1]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L800-828
[M24.10-2]: https://gitlab.com/dxgat/detectors/safety-zone-confirmed-clear/-/blob/91676a554aca543723850f3f4641ebdaa7784b66/main.py#L1445-1545
[M25.01-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L44-80
[M25.02-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L98-111
[M25.03-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L419-425
[M25.03-2]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L428-513
[M25.04-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L514-546
[M25.05-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L428-513
[M25.05-2]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L514-600
[M25.06-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L292-310
[M25.07-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L190-211
[M25.08-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L239-290
[M25.09-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L312-335
[M25.10-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L365-416
[M25.11-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L365-416
[M25.12-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L704-741
[M25.13-1]: https://gitlab.com/dxgat/detectors/seat-belts-used-on-all-gse-equipped-with-seat-belts/-/blob/43068fec5bdbb7c96d2b19570087a6dca9c2bc0d/main.py#L704-741
[M26.01-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L62-74
[M26.02-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L76-82
[M26.03-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L84-122
[M26.04-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L124-182
[M26.05-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L198-228
[M26.06-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L308-343
[M26.07-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L345-436
[M26.08-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L345-436
[M26.08-2]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L452-493
[M26.09-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L495-612
[M26.10-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L495-612
[M26.11-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L614-640
[M26.12-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L682-723
[M26.13-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L786-881
[M26.14-1]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L34-53
[M26.14-2]: https://gitlab.com/dxgat/detectors/steering-by-pass-pin-installed-or-steering-otherwise-bypassed/-/blob/60dca7360132479064544ab321b055bc35b666b7/main.py#L786-881
[M27.01-1]: https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/blob/4800b649973038924905d74d616fbb5b77087053/main.py#L40-50
[M27.02-1]: https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/blob/4800b649973038924905d74d616fbb5b77087053/main.py#L93-107
[M27.03-1]: https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/blob/4800b649973038924905d74d616fbb5b77087053/main.py#L315-333
[M27.04-1]: https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/blob/4800b649973038924905d74d616fbb5b77087053/main.py#L371-392
[M27.05-1]: https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/blob/4800b649973038924905d74d616fbb5b77087053/main.py#L111-225
[M27.06-1]: https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/blob/4800b649973038924905d74d616fbb5b77087053/main.py#L226-227
[M27.06-2]: https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/blob/4800b649973038924905d74d616fbb5b77087053/main.py#L762-795
[M27.07-1]: https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/blob/4800b649973038924905d74d616fbb5b77087053/main.py#L243-312
[M27.07-2]: https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/blob/4800b649973038924905d74d616fbb5b77087053/main.py#L762-795
[M27.08-1]: https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/blob/4800b649973038924905d74d616fbb5b77087053/main.py#L407-418
[M27.09-1]: https://gitlab.com/dxgat/detectors/wing-walkers-in-proper-position-and-using-approved-wands/-/blob/4800b649973038924905d74d616fbb5b77087053/main.py#L762-814
[U01.01-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/chunks_handling/storage_handling.py#L34-90
[U01.02-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/chunks_handling/storage_handling.py#L116-135
[U01.03-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/chunks_handling/storage_handling.py#L139-238
[U01.04-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/chunks_handling/chunks_generator.py#L11-66
[U01.05-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/classifier/classifier.py#L59-65
[U01.06-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/classifier/classifier.py#L6-57
[U01.06-2]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/classifier/classifier.py#L110-159
[U01.07-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L217-239
[U01.07-2]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L478-488
[U01.08-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/new_model.py#L19-76
[U01.08-2]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L534-581
[U01.09-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L549-564
[U01.10-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L36-54
[U01.10-2]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L584-595
[U01.11-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L613-637
[U01.12-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L271-280
[U01.12-2]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L625-645
[U01.13-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L680-698
[U01.14-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L701-720
[U01.15-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L649-673
[U01.15-2]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L701-723
[U01.16-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L243-268
[U01.16-2]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L499-520
[U01.17-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L738-760
[U01.18-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L108-146
[U01.19-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L149-213
[U01.19-2]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/chunks_handling/storage_handling.py#L330-344
[U01.20-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/chunks_handling/storage_handling.py#L241-265
[U01.20-2]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L658-660
[U01.20-3]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/merge.py#L695-698
[U01.21-1]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/chunks_handling/storage_handling.py#L267-296
[U01.21-2]: https://gitlab.com/dxgat/utils/camera_software/-/blob/13ef3fc3e3da8d757173c80651e7765f9bfaafe3/notification.py#L9-14
[U02.01-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L475-477
[U02.02-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L505-538
[U02.03-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L463-464
[U02.03-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L538-577
[U02.04-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L467-468
[U02.04-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L583-586
[U02.05-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L471-472
[U02.05-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L589-592
[U02.06-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L202-217
[U02.06-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L542-544
[U02.07-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L598-609
[U02.08-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L488-491
[U02.08-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L612-645
[U02.09-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L274-282
[U02.09-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L615-630
[U02.10-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L288-364
[U02.10-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L453-459
[U02.11-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L669-704
[U02.12-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L367-415
[U02.12-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L678-697
[U02.13-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L784-805
[U02.14-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L811-829
[U02.15-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L716-716
[U02.15-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L835-848
[U02.16-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/scripts/engine_script.py#L7-108
[U02.16-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L881-886
[U02.17-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/scripts/classifier_utils.py#L33-47
[U02.17-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L889-911
[U02.18-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L851-871
[U02.19-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L94-168
[U02.19-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L519-577
[U02.19-3]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L649-659
[U02.20-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L922-951
[U02.21-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L171-199
[U02.21-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L960-1050
[U02.22-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/scripts/videos_selection_script.py#L24-113
[U02.22-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L1055-1074
[U02.23-1]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L595-595
[U02.23-2]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L710-712
[U02.23-3]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L871-871
[U02.23-4]: https://gitlab.com/dxgat/detectors/general_model/-/blob/13a4ddc57cca80f2432bc26eb76b5a300c3ac633/main.py#L1062-1074
[U03.01-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L82-83
[U03.01-2]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L144-149
[U03.02-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L168-222
[U03.03-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L102-106
[U03.03-2]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L243-253
[U03.04-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L93-96
[U03.04-2]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L226-239
[U03.05-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L97-100
[U03.05-2]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L257-265
[U03.06-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L268-288
[U03.07-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L291-311
[U03.08-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L33-52
[U03.08-2]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L330-348
[U03.09-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L348-349
[U03.09-2]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L483-488
[U03.10-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/local_utils/bl_utils.py#L4-133
[U03.10-2]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L350-366
[U03.11-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L370-406
[U03.12-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L454-478
[U03.13-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L430-450
[U03.14-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L55-58
[U03.14-2]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L495-518
[U03.15-1]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L520-526
[U03.15-2]: https://gitlab.com/dxgat/utils/cv_trackers/-/blob/b5d350c71d0533439e9916077fc7b1215d3003ac/tracker.py#L562-570
[U04.01-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L16-70
[U04.02-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L74-110
[U04.03-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L113-133
[U04.03-2]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L204-250
[U04.04-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L136-201
[U04.04-2]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L287-304
[U04.05-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L307-325
[U04.06-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L328-351
[U04.07-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L354-369
[U04.07-2]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L439-468
[U04.08-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L372-436
[U04.09-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L470-520
[U04.10-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/common.py#L522-538
[U04.11-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/tracked_object.py#L20-95
[U04.12-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/tracked_object.py#L111-138
[U04.13-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/tracked_object.py#L140-172
[U04.14-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/tracked_object.py#L175-200
[U04.15-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/tracked_object.py#L203-301
[U04.16-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/tracked_object.py#L326-338
[U04.17-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/tracked_object.py#L341-403
[U04.18-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/tracked_object.py#L538-674
[U04.19-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/transport.py#L55-76
[U04.20-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/transport.py#L78-105
[U04.21-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/transport.py#L155-208
[U04.22-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/track.py#L6-21
[U04.23-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/detections.py#L4-51
[U04.24-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/utils/datasets.py#L158-288
[U04.25-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/utils/datasets.py#L333-418
[U04.26-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/image_preprocessing.py#L10-56
[U04.26-2]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/image_preprocessing.py#L99-123
[U04.27-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/image_preprocessing.py#L58-75
[U04.28-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/log_utils.py#L26-137
[U04.29-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/log_utils.py#L139-176
[U04.30-1]: https://gitlab.com/dxgat/utils/cv_common/-/blob/ac5098d2aae117b27a1e02a165a356ee016a755f/log_utils.py#L186-206
[U05.01-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L129-208
[U05.02-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L225-238
[U05.03-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L323-356
[U05.04-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L257-280
[U05.05-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L240-254
[U05.06-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L210-223
[U05.07-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L290-321
[U05.08-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L384-393
[U05.08-2]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L410-437
[U05.09-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L395-404
[U05.10-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L406-408
[U05.11-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L468-516
[U05.12-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L359-380
[U05.13-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L52-66
[U05.13-2]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L80-125
[U05.14-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/ML_worker.py#L439-453
[U05.15-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/model_starter.py#L45-54
[U05.16-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/model_starter.py#L58-69
[U05.17-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/model_starter.py#L73-143
[U05.18-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/model_starter.py#L147-191
[U05.19-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/model_starter.py#L195-279
[U05.20-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/model_starter.py#L280-303
[U05.21-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/model_starter.py#L304-331
[U05.21-2]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/send_report.py#L27-49
[U05.22-1]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/send_report.py#L53-55
[U05.22-2]: https://gitlab.com/dxgat/utils/db_worker/-/blob/5a4aa83d828695e0f227038eaa2ff96af57f7cca/send_report.py#L74-143
