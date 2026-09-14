# Prime Flight (PF) — DXGAT real-time roadmap workspace

This is the **control workspace** of the Prime Flight project lead: all documentation, agent roles and the backlog in one place.
The code lives in the GitLab repositories `dxgat/*`; **fresh read-only clones are in `external/` of this workspace** (gitignored: 27 modules,
`general_model`, `db_worker`; `cv_trackers`/`cv_common`/`camera_software` are unavailable — PF-X-05). The streaming stand (test bench) — `G:\gat-streaming\`.
New code is assembled in the `pf/` package of this repo (`pf/README.md`): contract → receiver → GM v2 → Tracker v2 → stage detector → module adapters.
Here — context, decisions, tasks. Any agent working on PF reads this file first.

## What the project is, in one paragraph

DXGAT (DeepX Ground Aircraft Turnaround) is a CV system that, from two cameras at the gate (cone + wing), verifies 27 checklist tasks
of aircraft-servicing safety (chocks, cones, wing walkers, handrails, vests, pushback...). Today it is **post-processing**:
the CameraBox writes 1-minute chunks → after the event, merge into a full-turn video → General Model (GM) → trackers → modules → verdicts
Pass / Fail / Not observed → MongoDB → RampVision website. **Time to Result ≈ 24 h.**
Prime Flight is a 12-month roadmap that gradually moves the system to two branches (real-time + post) and brings
Time to Result down to **≈5–6 h for the post part** and **seconds for real-time checks**.

## Main KPI and quarters (details: @docs/06_roadmap.md)

| Quarter | Theme | What the client sees | Time to Result* |
|---|---|---|---|
| Q1 (months 1–3) | Continuous upload + faster post-processing (Wi-Fi/SIM chunks, stage detector, no early merge) | video travels to the server while the CameraBox is still recording | ~24h → ~15h |
| Q2 (months 4–6) | Real-time architecture foundation (separate RT branch, GM/Tracker for RT, first module in RT) | the first checks deliver a result before the merge completes | ↓ |
| Q3 (months 7–9) | Real-time expansion + alerting (more modules, backend alerts) | important safety events trigger alerts | ↓ |
| Q4 (months 10–12) | Maximum RT coverage + optimization (GM/Tracker/stage detector, gate streaming to RampVision) | the maximum of practical checks in RT | ~5–6h |

\* illustrative targets, subject to validation by measurements (baseline — task PF-Q1-08).

## Team and owners (details: @docs/07_team.md)

- **Valentyn (lead, coordinator)** — this workspace, summaries for Ihor/Serhii, roadmap; together with Yurii — GM + Tracker.
- **Maksym Chernyshev** — architecture owner: data flow into two branches, receiver/orchestrator, stage detector, Wi-Fi upload, RT branch.
- **Yurii Luchko** — GM + Tracker (fixes in Q1, adaptation for RT in Q2, optimization in Q4), analysis of module logic.
- **Aryan Singh** — alerting (Q3): backend ↔ streaming, MongoDB, endpoint, rendering.
- Vladyslav (module hierarchy, GM/tracker state, Entity Classifier, Hair Policy), Denys (datasets), Ihor (source of truth
  on the technical side, reviewer), Serhii (reviewer, pain points), Oksana (accuracy validation, module distribution for the client).

## Agents of this workspace (`.claude/agents/`)

Each agent = one role with a clear zone of repositories and a "definition of done". Invoke explicitly:
"use the **pipeline-architect** agent to …" or via `/pf-task`.

| Agent | Human owner | Zone |
|---|---|---|
| `pipeline-architect` | Maksym Ch. | camera_software / merge / db_worker, chunk receiver, session registry, stage detector, RT branch |
| `gm-tracker-engineer` | Yurii + Valentyn | general_model, cv_trackers, cv_common, frame contract, weights/DVC |
| `module-porter` | Valentyn / Yurii / Vladyslav | porting the 27 modules to streaming / real-time in the E0→E4 queue order |
| `alerting-engineer` | Aryan | alert bus, deduplication, MongoDB/endpoint, RampVision |
| `qa-parity` | Denys / Oksana | batch↔stream parity, balanced samples, fail labels, CI gates |
| `pm-coordinator` | Valentyn | task board, statuses, summaries for reviewers, risks |

Skills (`/pf-status`, `/pf-task`, `/pf-port-module`, `/pf-parity`, `/pf-standup`) — in `.claude/skills/`.

## Documentation (reading order for a new agent)

1. @docs/00_index.md — map of documents.
2. @docs/01_architecture_current.md — how prod works now (dataflow + cambox flow).
3. @docs/02_target_architecture.md — two branches, frame contract, stage detector, 4 correctness conditions, frame budget.
4. `docs/04_modules.md` — all 27 modules: repo, stage, cameras, tier, streaming-readiness verdict (generated).
5. `docs/05_module_logic.md` — **client Pass/Fail logic** (the contract with the client; generated from xlsx).
6. `docs/03_components.md` — 32 shared components E01–E33 (generated).
7. @docs/08_repos.md — repositories, local paths, branches, how to run.
8. `docs/09_glossary.md` — terms (T_arr, BL@door, cone/wing camera, Not observed...).
9. `tasks/BOARD.md` — **the single source of truth on tasks** (ID `PF-Qn-nn`, owner, agent, status, acceptance).

Generated files (03/04/05) are not edited by hand — update the source and run `python scripts/build_docs.py`.

## Invariant rules (for all agents)

**Architectural invariants of streaming** (measured, not opinions; see `docs/02_target_architecture.md`):
- X1. One tracker per event, never reset (a reset every 7.5 s → 297 "aircraft" instead of 5).
- X2. `frame_id` is absolute and explicit; the receiver fills gaps with placeholder frames rather than skipping frames.
- X3. `schema_version` in every contract record.
- X4. The decoder is pinned on both sides of any comparison (ffmpeg ≠ OpenCV on non-monotonic DTS).
- A chunk is a unit of transport, not of processing. A module knows nothing about chunks.
- Event anchors (T_arr, T_dep, BL@door, BL leave, pushback_attached) have **one owner — the stage detector**, not copies in modules.

**Verdict semantics**: Pass/Fail/Not observed/NO-with-obstacles are defined by the client in `docs/05_module_logic.md`.
Porting to RT does not change the semantics silently. If a trigger has to be redefined (S1 checks) — that is a separate task tagged
`trigger-change` and agreed with Ihor/Oksana.

**Measurement**: "technical readiness ≠ usefulness". A module is not considered delivered to streaming without a measurement on fail videos
(example: pushback-pathway — recall 0 of 4 at 85 % "accuracy"). A paired batch↔stream comparison is always valid,
absolute accuracy — only where fail labels exist (Main gear chocks).

**Git / repositories**:
- DeepX working repos: **no** `Co-Authored-By: Claude` trailers in commits. Commits — short, in English, in the repo's style.
- `git push` and creating an MR — done by a human. The agent prepares the branch, the commit and the MR description in `tasks/` or in the reply.
- Do not change the pinned `cv_common` versions in modules without a separate task (10 different pins — a known debt, PF-Q3-05).
- Prod inferences (500–800 MB per video) and weights do not go into git; weights — DVC, data — buckets (`docs/08_repos.md`).

**Language**: everything in this repository — docs, code, comments, commits, board, notes, ADRs — is written in English. Conversation with the lead may happen in Ukrainian; written artifacts stay English.

## Quick start for an agent

```
1. Read CLAUDE.md (this file) and tasks/BOARD.md.
2. Find your task by ID (PF-Qn-nn), check owner/agent/deps/acceptance.
3. Work in your zone (see the agent card). Read prod code in `external/<repo>` (read-only), the stand in G:\gat-streaming; new code — in `pf/`.
   Analysis reports — `docs/analysis/` (index in `docs/analysis/README.md`).
4. Result: code in a branch + a note in tasks/notes/<ID>.md (what was done, how it was verified, what remains) + updated status in BOARD.md.
5. Anything that changes the frame contract, stage events or client logic — as a separate "Decision needed" item in the note.
```
