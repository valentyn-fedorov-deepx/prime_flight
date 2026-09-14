---
name: pf-status
description: Статус проєкту Prime Flight по кварталах з tasks/BOARD.md і tasks/notes — що done/in-progress/blocked, що змінилось з минулого статусу, ризики, decision-needed, наступні кроки. Зберігає у tasks/status/<date>.md.
---

Використовуй агента `pm-coordinator` (або виконай сам, якщо вже в його ролі).

1. Прочитай `tasks/BOARD.md`, усі `tasks/notes/*.md`, останній файл у `tasks/status/` (якщо є), розділ «Ризики» у `docs/06_roadmap.md`.
2. Склади статус у такому форматі (українською, стисло):

```
# PF status · <YYYY-MM-DD>
## Q1 · <тема>
- done: …  · in-progress: … · blocked: … (чому, хто розблоковує)
## Q2 … Q4 (лише якщо є рух)
## Змінилось із <дата минулого статусу>
- …
## Decision needed (для Ігоря / ліда)
- <ID>: питання одним реченням, варіанти A/B, рекомендація
## Ризики (оновлено)
- …
## Наступні 3 кроки
1. …
```
3. Збережи у `tasks/status/<YYYY-MM-DD>.md`. Не змінюй статуси в BOARD.md без підстави в notes.
4. Якщо аргумент `$ARGUMENTS` містить `slack` — додай наприкінці 5–8-рядкову версію для каналу.
