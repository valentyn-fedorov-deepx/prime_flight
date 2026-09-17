# Prime Flight documentation — map

| File | What is inside | Source / how to update |
|---|---|---|
| `01_architecture_current.md` | Production architecture as-is: dataflow (Cambox → buckets → GM → trackers → modules → MongoDB → RampVision) and cambox flow | Two diagrams from Confluence ("Dataflow diagram of DXGAT video processing", "Cambox flow diagram"); edit by hand |
| `02_target_architecture.md` | Target architecture: two branches, frame contract, stage detector, invariants X1–X4, frame budget, chunking | The gat-streaming stand (test bench) `G:\gat-streaming\docs` (copies in `streaming_ref/`); edit by hand |
| `03_components.md` | 32 shared components E01–E33 (contract, group, who consumes) | **generated** by `scripts/build_docs.py` from `arch_review/essential_inventory.json` |
| `04_modules.md` | 27 modules + 5 pipeline repos: repo, stage, cameras, tier, ProdReady, streaming verdict, inputs/outputs/attention | **generated** from the architecture review + `streaming_ref/module_map.json` + xlsx |
| `05_module_logic.md` | Client logic Pass/Fail/NO/NO-obstacles, merge logic of the two cameras, distribution across cameras, tier | **generated** from `DX_Modules_logic.xlsx` |
| `06_roadmap.md` | 12-month roadmap by quarter, workstreams, delivery, KPI | Roadmap slide + the lead's post in Slack; edit by hand |
| `07_team.md` | People, roles, zones, syncs, reviewers | Slack + notes of the meeting of 4.09.2026; edit by hand |
| `08_repos.md` | GitLab repos, local clones, branches, infrastructure (GCP, buckets, MongoDB), how to run | edit by hand |
| `09_glossary.md` | Terms | edit by hand |
| `11_rt_dataflow.md` | The real-time branch as it runs today: what runs, what each stage costs, how an output arrives and where it goes next (diagrams) | edit by hand |
| `10_ci.md` | What is tested where: fast gates on GitHub Actions, GPU gates on the machine with the card, the monthly set; why there is no deployment step | edit by hand |
| `arch_review/` | Architecture review of 2026-09-07: `ESSENTIALS.md`, `REVIEW_DETAILED.md` (417 occurrences), interactive `components.html`/`hierarchy.html`, JSON inventories | from `cv-architecture-interactive.zip` |
| `streaming_ref/` | Copies of the gat-streaming stand (test bench) documents: architecture/contract/plan/modules/testing + `module_map.json` + png | from `G:\gat-streaming\docs` |
| `DX_Modules_logic.xlsx` | The original xlsx of the client logic (sheets: Updated logic 2025, Edge-Friendly, Post analytics, Streaming, Merge logic, Tasks by cameras) | source for 05 |

## Where to put new things

- Decisions (ADR) → `decisions/ADR-nnn-<slug>.md` (template in `decisions/ADR-000-template.md`).
- Task notes → `../tasks/notes/<PF-ID>.md`.
- New external documents (Confluence, Slack threads, presentations) → `inbox/` with the date in the name, then move the essence into the corresponding file.
