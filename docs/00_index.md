# Документація Prime Flight — карта

| Файл | Що всередині | Джерело / як оновлювати |
|---|---|---|
| `01_architecture_current.md` | Прод-архітектура як є: dataflow (Cambox → бакети → GM → трекери → модулі → MongoDB → RampVision) і cambox flow | Дві діаграми з Confluence («Dataflow diagram of DXGAT video processing», «Cambox flow diagram»); правити руками |
| `02_target_architecture.md` | Цільова архітектура: дві гілки, контракт кадру, stage detector, інваріанти X1–X4, бюджет кадру, чанкування | Стенд `G:\gat-streaming\docs` (копії в `streaming_ref/`); правити руками |
| `03_components.md` | 32 спільні компоненти E01–E33 (контракт, група, хто споживає) | **генерується** `scripts/build_docs.py` з `arch_review/essential_inventory.json` |
| `04_modules.md` | 27 модулів + 5 pipeline-репо: repo, стадія, камери, tier, ProdReady, streaming-verdict, inputs/outputs/attention | **генерується** з ревʼю + `streaming_ref/module_map.json` + xlsx |
| `05_module_logic.md` | Клієнтська логіка Pass/Fail/NO/NO-obstacles, merge logic двох камер, розподіл по камерах, tier | **генерується** з `DX_Modules_logic.xlsx` |
| `06_roadmap.md` | 12-місячний roadmap по кварталах, воркстріми, delivery, KPI | Roadmap-слайд + пост ліда в Slack; правити руками |
| `07_team.md` | Люди, ролі, зони, синхронізації, рецензенти | Slack + нотатки зустрічі 4.09.2026; правити руками |
| `08_repos.md` | GitLab-репо, локальні клони, гілки, інфраструктура (GCP, бакети, MongoDB), як запускати | правити руками |
| `09_glossary.md` | Терміни | правити руками |
| `arch_review/` | Архітектурне ревʼю 2026-09-07: `ESSENTIALS.md`, `REVIEW_DETAILED.md` (417 occurrences), інтерактивні `components.html`/`hierarchy.html`, JSON-інвентарі | з `cv-architecture-interactive.zip` |
| `streaming_ref/` | Копії документів стенду gat-streaming: architecture/contract/plan/modules/testing + `module_map.json` + png | з `G:\gat-streaming\docs` |
| `DX_Modules_logic.xlsx` | Оригінальний xlsx клієнтської логіки (аркуші: Updated logic 2025, Edge-Friendly, Post analytics, Streaming, Merge logic, Tasks by cameras) | джерело для 05 |

## Куди класти нове

- Рішення (ADR) → `decisions/ADR-nnn-<slug>.md` (шаблон у `decisions/ADR-000-template.md`).
- Нотатки по задачах → `../tasks/notes/<PF-ID>.md`.
- Нові зовнішні документи (Confluence, Slack-треди, презентації) → `inbox/` з датою в назві, потім перенести суть у відповідний файл.
