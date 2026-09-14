# Реєстр ADR

| # | Назва | Статус | Дата | Зона |
|---|---|---|---|---|
| ADR-000 | Шаблон | — | — | — |
| ADR-001 | GM v2 / Tracker v2: стратегія сумісності з 27 модулями і по-чанкова обробка (v1-compat + v2 шина, gm_core/gm_context, state_dict заморожено, stage detector = власник якорів) | proposed | 2026-09-14 | GM / Tracker / контракт |

Кандидати на перші ADR (з `docs/02_target_architecture.md` і борду):
- Контракт кадру v1.0 (`schema_version`, `frame_id`, `stage/events/anchors`) — PF-Q1-02/03.
- Stage detector як єдиний власник якорів; де живе код (db_worker чи новий репо) — PF-Q1-03.
- Розмір чанка 7,5 с і stream-copy — PF-Q1-01.
- Політика пінів `cv_common` для модулів — PF-Q3-05.
- Перевизначення тригерів S1-перевірок — PF-Q3-06 (по одному ADR на перевірку).
