# Prime Flight — the lead's Claude Code workspace

GitHub: https://github.com/valentyn-fedorov-deepx/prime_flight (private). DeepX prod code stays in GitLab `dxgat/*`; here — the workspace, documentation, board and the new `pf/` package.

One workspace for all documentation, role agents and the backlog of the Prime Flight project (DXGAT → real-time).
Prod code — read-only clones of GitLab `dxgat/*` in `external/` (gitignored) and the gat-streaming stand (test bench) `G:\gat-streaming`; data for measurements — `G:\gat_stages`
(both external folders are attached via `.claude/settings.json → additionalDirectories`). New code — the `pf/` package.

## How to use

```bash
cd G:\prime_flight
claude
```

- The main context is loaded from `CLAUDE.md` (plus the `@docs/...` imports).
- **Role agents** (`.claude/agents/`): `pipeline-architect`, `gm-tracker-engineer`, `module-porter`, `alerting-engineer`, `qa-parity`, `pm-coordinator`.
  Invocation: "use the module-porter agent to port beltloader-chocks (PF-Q2-03)". Several agents can be run in parallel on different tasks —
  each reads the same docs and the same board, so the context is shared.
- **Skills** (`.claude/skills/`): `/pf-status`, `/pf-standup [days]`, `/pf-task <description>`, `/pf-port-module <repo>`, `/pf-parity <repo|PF-ID>`.
- **Board**: `tasks/BOARD.md` — the single source of truth; task notes in `tasks/notes/<ID>.md`; statuses/standups in `tasks/status/`.
- **Decisions**: `docs/decisions/ADR-nnn-*.md` (template `ADR-000-template.md`).

## Structure

```
CLAUDE.md                      project context for all agents (KPI, quarters, team, invariants, git rules)
.claude/settings.json          permissions, attached code folders, env
.claude/agents/*.md            6 role agents with zones, "read first", definition of done
.claude/skills/*/SKILL.md      5 skill commands
docs/00_index.md               map of documents
docs/01_architecture_current   prod as is (dataflow + cambox flow)
docs/02_target_architecture    two branches, frame contract, stage detector, X1–X4, frame budget, module queue
docs/03_components.md*         32 shared components E01–E33
docs/04_modules.md*            27 modules + 5 pipeline repos: stage, cameras, tier, verdict, inputs/outputs/attention
docs/05_module_logic.md*       client Pass/Fail logic, merge logic, cameras, tier
docs/06_roadmap.md             12 months by quarters, workstreams, KPI, risks
docs/07_team.md                people, zones, reviewers, rules of agent interaction
docs/08_repos.md               repos, local clones, infra, stand commands, conventions
docs/09_glossary.md            terms
docs/arch_review/              architecture review 2026-09-07 (ESSENTIALS.md, REVIEW_DETAILED.md, html, json)
docs/streaming_ref/            copies of the gat-streaming stand documents + module_map.json + png
docs/decisions/                ADRs
docs/inbox/                    new documents to be sorted
docs/DX_Modules_logic.xlsx     source of the client logic
tasks/BOARD.md                 task board Q1–Q4 + cross-cutting
tasks/TEMPLATE.md              task note template
scripts/build_docs.py          generates the files marked with * from their sources
scripts/bootstrap.ps1          environment check (clones, stand, python packages)
```

## Updating the sources

| What changed | What to do |
|---|---|
| `DX_Modules logic.xlsx` from the client | replace `docs/DX_Modules_logic.xlsx` → `python scripts/build_docs.py` |
| A new architecture review (zip) | unpack the JSON from `<script id="review-data">` into `docs/arch_review/essential_inventory.json` → build |
| `module_map.json` on the stand | copy into `docs/streaming_ref/` → build |
| A decision on the contract/events/logic | ADR + manual edits of 02/05 |
| A new document (Confluence, Slack) | into `docs/inbox/<date>-<name>.md`, then `/pf-task` or `pm-coordinator` sorts it out |

## What is not done yet (state as of 2026-09-14)

- The board is the lead's draft; align with Maksym Ch., Yurii, Aryan, then review by Ihor/Serhii.
- `G:\deepx_gat` disappeared on 14.09; clones in `external/` (https). `cv_trackers`/`cv_common`/`camera_software` are unavailable: the ssh key is not in GitLab (PF-X-05).
- No GPU runner for nightly parity (PF-Q1-07, external); gcloud requires `gcloud auth login`.
