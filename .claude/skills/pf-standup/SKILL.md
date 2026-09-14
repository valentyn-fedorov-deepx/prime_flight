---
name: pf-standup
description: Short Prime Flight standup for Slack (5–8 lines, in English) from tasks/BOARD.md and fresh tasks/notes — done / doing / blockers / questions to Ihor. Optional argument — how many days of changes to take (default 7).
---

Period: the last `$ARGUMENTS` days (empty → 7). Executed by `pm-coordinator`.

1. Read `tasks/BOARD.md`, `tasks/notes/*.md` (journals with dates within the period), the latest `tasks/status/*.md`.
2. Compose the text for the channel — no markdown tables, no headings, in English, with task IDs:

```
PF · standup <date>
✅ Done: PF-…: …; PF-…: …
🔧 Doing: PF-…: … (who)
⛔ Blockers: PF-…: … → needed from <whom>
❓ To Ihor: …
📅 Next: …
```
3. Do not write on behalf of colleagues; only facts from the notes. If nothing changed over the period — say so.
4. Save a copy to `tasks/status/standup-<YYYY-MM-DD>.md`.
