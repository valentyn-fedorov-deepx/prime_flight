# Prime Flight — Claude Code workspace ліда

Один воркспейс для всієї документації, рольових агентів і беклогу проєкту Prime Flight (DXGAT → real-time).
Код не тут: він у `G:\deepx_gat\*` (клони GitLab `dxgat/*`) і на стенді `G:\gat-streaming`; обидві теки підключені
через `.claude/settings.json → additionalDirectories`, тож агенти читають їх без додаткових дозволів.

## Як користуватись

```bash
cd G:\prime_flight
claude
```

- Головний контекст завантажується з `CLAUDE.md` (плюс `@docs/...`-імпорти).
- **Агенти-ролі** (`.claude/agents/`): `pipeline-architect`, `gm-tracker-engineer`, `module-porter`, `alerting-engineer`, `qa-parity`, `pm-coordinator`.
  Виклик: «use the module-porter agent to port beltloader-chocks (PF-Q2-03)». Кілька агентів можна запускати паралельно на різних задачах —
  кожен читає ті самі docs і той самий борд, тож контекст спільний.
- **Скіли** (`.claude/skills/`): `/pf-status`, `/pf-standup [days]`, `/pf-task <опис>`, `/pf-port-module <repo>`, `/pf-parity <repo|PF-ID>`.
- **Борд**: `tasks/BOARD.md` — єдине джерело правди; нотатки по задачах у `tasks/notes/<ID>.md`; статуси/стендапи у `tasks/status/`.
- **Рішення**: `docs/decisions/ADR-nnn-*.md` (шаблон `ADR-000-template.md`).

## Структура

```
CLAUDE.md                      контекст проєкту для всіх агентів (KPI, квартали, команда, інваріанти, правила git)
.claude/settings.json          дозволи, підключені теки з кодом, env
.claude/agents/*.md            6 рольових агентів із зонами, «спочатку прочитай», definition of done
.claude/skills/*/SKILL.md      5 скілів-команд
docs/00_index.md               карта документів
docs/01_architecture_current   прод як є (dataflow + cambox flow)
docs/02_target_architecture    дві гілки, контракт кадру, stage detector, X1–X4, бюджет кадру, черга модулів
docs/03_components.md*         32 спільні компоненти E01–E33
docs/04_modules.md*            27 модулів + 5 pipeline-репо: стадія, камери, tier, verdict, inputs/outputs/attention
docs/05_module_logic.md*       клієнтська Pass/Fail-логіка, merge logic, камери, tier
docs/06_roadmap.md             12 місяців по кварталах, воркстріми, KPI, ризики
docs/07_team.md                люди, зони, рецензенти, правила взаємодії агентів
docs/08_repos.md               репо, локальні клони, інфра, команди стенду, конвенції
docs/09_glossary.md            терміни
docs/arch_review/              архітектурне ревʼю 2026-09-07 (ESSENTIALS.md, REVIEW_DETAILED.md, html, json)
docs/streaming_ref/            копії документів стенду gat-streaming + module_map.json + png
docs/decisions/                ADR
docs/inbox/                    нові документи до розкладання
docs/DX_Modules_logic.xlsx     джерело клієнтської логіки
tasks/BOARD.md                 борд задач Q1–Q4 + наскрізні
tasks/TEMPLATE.md              шаблон нотатки задачі
scripts/build_docs.py          генерує файли з * із джерел
scripts/bootstrap.ps1          перевірка оточення (клони, стенд, python-пакети)
```

## Оновлення джерел

| Змінилось | Що робити |
|---|---|
| `DX_Modules logic.xlsx` від клієнта | замінити `docs/DX_Modules_logic.xlsx` → `python scripts/build_docs.py` |
| Нове архітектурне ревʼю (zip) | розпакувати JSON з `<script id="review-data">` у `docs/arch_review/essential_inventory.json` → build |
| `module_map.json` на стенді | скопіювати в `docs/streaming_ref/` → build |
| Рішення по контракту/подіях/логіці | ADR + правки 02/05 руками |
| Новий документ (Confluence, Slack) | у `docs/inbox/<дата>-<назва>.md`, потім `/pf-task` або `pm-coordinator` розкладає |

## Що ще не зроблено (стан 2026-09-14)

- Борд — чернетка ліда; узгодити з Максимом Ч., Юрієм, Аріаном, потім рецензія Ігоря/Сергія.
- `camera_software` не клонований локально (PF-X-03); https-шлях у GitLab не знайдено — уточнити.
- SSH до GitLab на цій машині не налаштований (host key); https працює через Git Credential Manager для частини репо.
- GPU-раннер для nightly паритету відсутній (PF-Q1-07, external).
