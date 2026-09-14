# Prime Flight team — who is responsible for what

Sources: the lead's post in Slack (delivery by quarter) and the notes of the streaming-track meeting of Fri 4.09.2026.
Slack handles: Maksym Chernyshev `U0BLS9K3H8T`, Yurii Luchko `U0BL02TRFK6`, Aryan Singh `U09Q50VN2JH`.

## Core

| Person | Role in PF | Zone | Agent in the workspace | Quarters |
|---|---|---|---|---|
| **Valentyn** (lead) | track coordinator, tech lead of GM/Tracker together with Yurii | this workspace, summaries for Ihor/Serhii, tables/diagrams, roadmap; GM+Tracker | `pm-coordinator`, `gm-tracker-engineer`, `module-porter` | all |
| **Maksym Chernyshev** | architecture owner | data flow into two branches, receiver/orchestrator, stage detector, Wi-Fi/SIM upload, removal of early merge, RT branch, architecture tech debt | `pipeline-architect` | Q1 (upload, stage detector, per-chunk processing), Q2 (RT branch), Q3 (architecture fixes), Q4 (optimization) |
| **Yurii Luchko** | GM + Tracker | GM/Tracker fixes (Q1), adaptation to RT (Q2), optimization (Q4); analysis of module logic, grouping, chocks | `gm-tracker-engineer`, `module-porter` | Q1–Q4 |
| **Aryan Singh** | alerting | backend ↔ streaming: alert bus, deduplication, MongoDB, endpoint, rendering; list of open questions in the channel with Ihor tagged | `alerting-engineer` | Q3–Q4 |

## Adjacent

| Person | Contribution | Sync |
|---|---|---|
| **Vladyslav** | module hierarchy (tree), state of the GM and tracker, testing on fragments, Entity Classifier, Hair Policy on edge (≈20 % on the track) | with Yurii and Maksym Ch. |
| **Denys** | datasets in general and per module; balanced samples, fail labels | with Vladyslav (approach to testing), `qa-parity` |
| **Maksym Stankevych** | organizational: tasks for logging hours on planning/research | — |
| **Oksana** | validation of module accuracy; distribution of modules in the client presentation (≈11 streaming / 8–9 post) | with Vladyslav; `qa-parity` |

## Reviewers and sources of decisions

- **Ihor** — the single source of truth on the technical part; reviews the output; risk of a third iteration → **clarify the vision,
  do not guess**. All open technical questions — in the channel with his tag.
- **Serhii** — reviewer together with Ihor; needs a table of pain points for prioritization.

## Cadence

- Weekly: status by the board (`/pf-status`), risk update, "Decision needed" → Ihor.
- End of quarter: client delivery per the roadmap + Time to Result measurement.
- Any change of the frame contract / stage events / client logic → ADR in `docs/decisions/` + sign-off.

## Rules of agent interaction between zones

- `pipeline-architect` owns the event contract (stage/events/anchors); `gm-tracker-engineer` — the `general_model`/`trackers` schema
  in the contract. A change of any field = ADR + a message to `module-porter`.
- `module-porter` does not change the client semantics of the verdict; if needed — a task tagged `trigger-change` to the lead.
- `qa-parity` has the right to block the "done" status in any module-port task without a parity result.
- `alerting-engineer` consumes verdicts and events from the contract, does not read the internal state of modules.
