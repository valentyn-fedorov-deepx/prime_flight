# Real-time: the 7 critical checks — team assignments (2026-09-15)

## Why

The client's strongest interest is real time: a notification about a safety violation at the gate while it can still be
fixed on the spot.

The first scope is the seven checks rated **critical** in the importance table (`gat-streaming/docs/critical_table.html`).
The goal for this round is to build the real-time components separately and measure how fast the critical checks run and
answer. The components are then joined on one basic architecture (`docs/decisions/ADR-004-rt-component-interfaces.md`).

## The seven critical checks

| # | Check | Module | Stage | When it decides today | Real-time feasibility (table) | ms per recorded frame* | Fails in the monthly report |
|---|---|---|---|---|---|---|---|
| 1 | All GSE guided into aircraft using approved hand signals | hand-signals | arrival / post-arrival | after two passes over the whole video | yes, with a new trigger | 10.1 | 13 |
| 2 | Pushback does not start until wing walkers are in place and ready | pushback-does-not-start-until-wing-walkers-are-in-place-and-ready | departure | 30 s after the pushback starts moving | yes, with a new trigger | 2.4 | 17 |
| 3 | Pushback pathway confirmed clear of obstacles | pushback-pathway-confirmed-clear-of-obstacles | departure | 15 s after departure (verified live) | yes, with a new trigger | 3.4 | 3 |
| 4 | Safety zone confirmed clear | safety-zone-confirmed-clear | pre-arrival | after two passes (zone fitted up to arrival, then a 2-minute re-read with MobileSAM) | yes, with a new trigger | 10.3 | 13 |
| 5 | Wing walkers in proper position and using approved wands | wing-walkers-in-proper-position-and-using-approved-wands | departure | 60 s after departure | yes, with a new trigger | 3.2 | 15 |
| 6 | Employees wearing safety vests secured to body | safety-vests-secured-to-body | whole session | at the end of the session | blocked by a requirement (Pass needs > 50 % of the video) | 28.2 | 35 |
| 7 | 3 stop brake check | 3-stop-brake-check | download | at departure | yes, with a new trigger | 3.4 | 43 |

\* Batch runs of the monthly test set on a loaded machine: a ranking, not a budget.

## What already exists

- **Real-time prototype** `pf/rt` (PF-Q1-19):
  - CameraBox chunk simulation, uplink, receiver, a wall-clock runtime;
  - production modules run unchanged on live frames;
  - verdicts identical to batch on a whole video;
  - frame latency p50 2.1 s on 3.75 s chunks.
- **GM v2 and Tracker v2**, proven against production: GM pair recall ≥ 99.8 %, tracker byte-identical on whole videos.
  Causal tracker events: T_ARR, T_DEP, belt loader at door / leave, pushback attached.
- **Compute inventory** of every module, with sha256 and file:line: `docs/analysis/module_compute/`.

## Budget

One camera at 8 fps gives 125 ms per frame:
- decode ≈ 3 ms;
- GM v2 ≈ 17 ms (8 ms with TensorRT);
- tracker ≤ 15 ms (target);
- all modules active in a stage ≤ 25 ms together;
- any single module ≤ 10 ms per active frame.

## How we work

- **Parallel components on recorded data:**
  - each component is built against replayed recorded data (production GM / tracker ndjson from the bucket
    `cv-modules-topics`, the test-set videos);
  - components that do not exist yet are stubs;
  - everyone plugs in through the interfaces of ADR-004.
- **Quality gates for any change to a module:**
  - **EXACT:** outputs byte-identical to the batch run;
  - **NEAR:** verdict parity on the 69 monthly events;
  - **SEMANTIC:** accuracy on the labelled fails, approved by Oksana.
- **Reporting:** results go to a task note `tasks/notes/<ID>.md` and a status on `tasks/BOARD.md`.
- **Shared by Valentyn on request:** the August stage-boundary study and the test-set plan (90 videos, events, cameras).

---

## Maksym Chernyshev — stage detector and event context (PF-Q1-03, PF-Q2-14)

**Goal.** One causal component that says, on every frame, where the turnaround is. It fires the events the critical checks
need, so each check runs only in its window and can alert at the right moment. It also decides the camera type and the
aircraft type early.

**Scope of work**
1. **Stage machine** over the tracker records and GM rows:
   - stages PRE_ARRIVAL → ARRIVAL → POST_ARRIVAL → DOWNLOAD / UPLOAD → PRE_DEPARTURE → DEPARTURE → END;
   - `undetermined` when the view is blocked;
   - no look-ahead: a decision never uses future frames.
2. **Events and anchors with evidence** (frame ids and the signal that fired):

   | event | needed by |
   |---|---|
   | aircraft first seen, T_ARR | safety zone |
   | per belt loader: approach start, stopped at the door, leave | hand signals, 3-stop |
   | PUSHBACK_ATTACHED, pushback starts moving | pushback wing walkers, pushback pathway |
   | T_DEP, T_DEP + 60 s | wing walkers with wands |
   | end of session | all |

3. **Event context:** camera type (cone / wing) and aircraft type (aircraft / jet), each with the frame where it was decided.
   The camera registry is the primary source; the classifier is a check.
4. **Gating table** for the 7 checks: cameras per aircraft type (client split in `docs/05_module_logic.md`), open / close
   events, look-back.
5. **ADR-004 review** (you own the event contract); plug the component into the `pf/rt` runtime.

**Starting points**
- Code:
  - `pf/tracker/events.py`: causal events, identical to production on a full video;
  - `pf/stage/pushback.py`: pushback attached, the production frame on 5 of 7 ATL-C5 videos;
  - `pf/gm/context.py`, `pf/gm/camera.py` with ADR-002: the camera type is decided about 50 s after arrival.
- Docs: `docs/02_target_architecture.md` §5, `tasks/notes/PF-Q1-03.md`, `tasks/notes/PF-Q2-14.md`.
- The August stage study: 88 labelled events, with measured problems to solve:
  - the departure boundary: the bbox-shrink rule sees 3.2 % instead of 18 %, which gives 9 false absences; use the drop of
    part heights instead;
  - a broken camera view must become `undetermined`;
  - several events in one video;
  - belt loaders on the wing camera;
  - jets never checked.

**Done when**
- Every event is causal (identical when the stream is cut at any frame) and its latency is reported.
- T_ARR / T_DEP are within ±1 frame of the production tracker on the 90 test-set videos, or every difference is explained.
- Pushback attached is checked against the production frames of aircraft-chocks / pin-verification.
- Camera type and aircraft type equal the production GM report on the 90 videos; decision latency is reported.
- Stage boundaries on the 88 labelled events are at least as good as in the study.
- The critical modules give the same verdicts gated as always-on.

---

## Yurii Luchko — make the critical modules fast enough for real time (PF-Q2-11, PF-Q2-12)

**Goal.** All 7 critical modules run within the real-time budget: ≤ 10 ms per active frame each, ≤ 25 ms for all modules of
a stage, on the reference GPU. Verdicts stay unchanged, or the loss is measured and approved.

**Scope of work**
1. **Measure first.** Cost per active frame for each critical module: decode and crops, each model, logic, state restore,
   peak RAM / VRAM.
   - Use the `pf/rt` harness (`scripts/rt_modules.py`).
   - Time hand-signals and safety-zone per pass until they are single-pass.
2. **Shared fixes that keep outputs identical (EXACT):**
   - frame reader: drop the unused 1280×768 resize and copy on every frame read (`cv_common/utils/datasets.py:226-231`);
   - one HRNet-W48 instance and one mmpose pipeline for hand-signals and wing-walkers (same checkpoint `0e67c6167d6a10fe`,
     same CLAHE preprocessing);
   - no per-frame JSON logging, prints or plots in real time; tracks parsed once per frame.
3. **Per module, EXACT first** (file:line in `docs/analysis/module_compute/`):

   | module | fixes |
   |---|---|
   | safety-vests (28 ms, whole session) | no full-frame copy and text drawing without video (`main.py:367-368`); no letterbox copy; batch the persons of a frame for the two Swin-T classifiers and the ResNet-18 |
   | hand-signals | occlusion ratio on ROI-sized masks (`main.py:183-196`); no copy before CLAHE (`:554`, `:358`); buffer CLAHE'd regions instead of 240 raw frames (≈ 1.5 GB) |
   | wing-walkers | no copy before CLAHE (`main.py:248-249`); no plots or pickle dumps |
   | safety-zone | draw only the stop-frame PNG; read pixels only when needed; one MobileSAM `set_image` per frame; zone intersection on the box ROI instead of full-frame masks |
   | 3-stop, pushback-does-not-start, pushback-pathway (pixel-free) | one track parse per frame; no drawing on `None` images; in pushback-does-not-start, drop the O(history) text counter and the trajectory PNG written on every run |

4. **Then NEAR:** TensorRT / fp16 for Swin-T, ResNet-18, HRNet-W48 and MobileSAM. **Then SEMANTIC:** HRNet flip test off,
   per-track subsampling. Each goes only through its gate.
5. **Single-pass hand-signals and safety-zone** on Maksym's stage events. Without this they cannot run live.

**Starting points**
- `tasks/notes/PF-Q2-11.md`: budget, gates, cost by stage.
- `docs/analysis/module_compute/pose_person.md` and `scene_gse.md`.
- `docs/analysis/rt_module_selection.md`.
- `scripts/run_module.py`, `scripts/rt_modules.py`.

**Done when**
- A before / after cost table exists for the 7 modules.
- Each module is ≤ 10 ms per active frame with its gate passed.
- hand-signals and safety-zone run single-pass on stage events.

---

## Aryan Singh — alert service (PF-Q3-01, PF-X-02)

**Goal.** A violation found by a critical module reaches a person as one clear alert within seconds, with evidence, and is
closed when it is fixed.

**Scope of work**
1. **ADR for the alert record and its lifecycle.** Fields:
   - `schema_version`, alert id, session / event, gate, camera, check, object;
   - state: raised → updated → resolved | expired; a provisional flag;
   - the frame where the rule is broken, first and last frame, capture and emission time;
   - severity, evidence (frame ids or a clip), module version.
2. **Prototype service** on the outputs of the `pf/rt` runtime (`Output{kind, name, frame_id, payload, emitted_t}`, kinds
   `alert` / `resolved`):
   - deduplication (≤ 1 alert per violation);
   - quiet windows;
   - resolve on fix;
   - expiry at the end of the stage.
3. **Delivery** to a demo channel (webhook, Slack or a simple web page). Agree the production channel and recipients with
   Ihor: RampVision live page, mobile push or station manager.
4. **Measure on recorded runs:** alerts per event before and after deduplication; latency from module output to
   notification.

**Starting points**
- `docs/decisions/ADR-004-rt-component-interfaces.md`.
- `pf/rt/runtime.py` (`outputs.ndjson`).
- `pf/rt/hooks/vests.py`: provisional vest alerts, an example source.
- `tasks/notes/PF-Q2-07.md`: alert record, catalogue draft.
- `docs/02_target_architecture.md` §8: 357 alerts on one video without deduplication.

**Done when**
- The ADR is accepted.
- Recorded runs of the critical modules give ≤ 1 alert per violation, with lifecycle.
- Latency is measured.
- The open questions (channel, recipients, MongoDB schema) are listed for Ihor.

---

## Vladyslav — live alerts from the pixel-free critical modules (PF-Q2-10)

**Goal.** The three light critical modules raise an alert the moment their own state shows a violation, not only a verdict
at the end, and their verdicts do not change.

**Scope of work**
1. **Hooks** like `pf/rt/hooks/vests.py`: wrap module methods and emit `alert` / `resolved` with the object and the frame.

   | module | alert when |
   |---|---|
   | 3-stop-brake-check | a belt loader stops at the aircraft with fewer than 3 stops |
   | pushback-does-not-start | the pushback moves while a wing walker is missing on one side |
   | pushback-pathway | an obstacle is on the pushback pathway in the departure stage (provisional: the module drops entries older than the last 30 s) |

2. **End-of-session marker** for modules that use the session length in the decision (pushback-does-not-start,
   cones-placed): the value arrives only when the session closes.
3. **Verify** with `scripts/rt_modules.py` that verdicts and reports stay identical with the hooks installed. Write down what
   a new trigger would change for each of the three; this feeds Oksana's trigger definitions.

**Starting points**
- `pf/rt/prod_module.py`, `pf/rt/hooks/`, `scripts/rt_modules.py`.
- `docs/analysis/module_compute/scene_gse.md` §6.
- `docs/05_module_logic.md`.

**Done when**
- The three hooks run live on recorded videos and verdicts stay identical.
- Alert frames are compared with Denys's labels.

---

## Denys — violation-moment labels (PF-Q2-09)

**Goal.** Know when each critical violation happened, so live alerts can be scored for recall, false alerts and time to
alert. Today we only have one verdict per event.

**Scope of work**
1. **Label format** (JSON, versioned): event id, video, check, object / person, the frame where the client rule is broken,
   the frame where it ends or is fixed, notes.
2. **Label the 139 critical fails** listed in `docs/analysis/critical_label_queue.json`:

   | check | fails |
   |---|---|
   | 3-stop | 43 |
   | safety vests | 35 |
   | pushback wing walkers | 17 |
   | wing walkers with wands | 15 |
   | hand signals | 13 |
   | safety zone | 13 |
   | pushback pathway | 3 |

3. **Flag doubtful truth labels.** Add a sample of Pass events for the same checks to measure false alerts.
4. **Store** the labels in the bucket and the index in the repo.

**Starting points**
- `docs/analysis/critical_label_queue.json`.
- `docs/05_module_logic.md`: client rules.
- Videos from the buckets.

**Done when**
- All 139 fails are labelled.
- Oksana has reviewed a sample.
- A scorer reads the labels.

---

## Oksana — alert quality gate and new triggers with the client (PF-Q2-08, PF-Q3-06)

**Goal.** Agree with the client what a good real-time alert is for each critical check, and how six of them change their
trigger, so the team builds against signed rules.

**Scope of work**
1. **Quality gate per alert type.** Metrics: false alerts per event, recall on labelled violations, time from the violation
   to the notification. Proposed thresholds:
   - ≤ 1 false alert per 20 events;
   - recall not lower than today's module;
   - ≤ 10 s p95.
2. **A one-page definition for each check marked "yes, with a new trigger":** when the alert fires, what resolves it, and
   what happens to the Pass / Fail verdict.

   | check | proposed trigger |
   |---|---|
   | hand signals | — |
   | pushback wing walkers | alert when the pushback is attached and walkers are missing |
   | pushback pathway | check continuously from pushback attached until movement |
   | safety zone | a causal zone before arrival |
   | wing walkers with wands | during pushback |
   | 3-stop | per belt loader, at its stop |

3. **Safety vests** ("blocked by a requirement": Pass needs the whole session). Propose a live "vest unzipped" alert while the
   report verdict stays end-of-session, and get a decision.
4. **Review** with Ihor and Serhii, then with the client. Record every accepted rule as an ADR, one per check.
5. **Scorer spec** on Denys's labels.

**Starting points**
- `docs/05_module_logic.md`.
- The critical table (`gat-streaming/docs/critical_table.html`).
- `tasks/notes/PF-Q2-07.md`: catalogue draft, success measures.

**Done when**
- The gate thresholds are signed off.
- The seven alert / trigger definitions are signed off.

---

## Valentyn (+ agents) — for reference (PF-Q2-02, PF-Q2-13)

- **GM v2 + Tracker v2 per frame** inside `pf/rt` for the critical set:
  - GM: 21 decision classes and all three heads (the chock head for pushback-pathway, the vehicle head for safety-zone);
  - tracker: airplane, beltloader and person tracks — no GSE tracks are needed by the critical set — with the fields these
    modules read (the optical-flow arrival block for safety-zone; `_status`, `_obj_id`, `_color`, `_xyxy`);
  - target: GM + tracker + decode ≤ 35 ms per frame per camera.
- **ADR-004 skeleton** with stubs for every component.
- **First speed table** of the critical modules in the harness.
