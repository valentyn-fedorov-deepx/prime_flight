---
name: pf-status
description: Prime Flight project status by quarters from tasks/BOARD.md and tasks/notes — what is done/in-progress/blocked, what changed since the previous status, risks, decision-needed, next steps. Saves to tasks/status/<date>.md.
---

Use the `pm-coordinator` agent (or do it yourself if you are already in its role).

1. Read `tasks/BOARD.md`, all `tasks/notes/*.md`, the latest file in `tasks/status/` (if any), the "Risks" section in `docs/06_roadmap.md`.
2. Compose the status in the following format (in English, concise):

```
# PF status · <YYYY-MM-DD>
## Q1 · <theme>
- done: …  · in-progress: … · blocked: … (why, who unblocks)
## Q2 … Q4 (only if there is movement)
## Changed since <date of the previous status>
- …
## Decision needed (for Ihor / the lead)
- <ID>: the question in one sentence, options A/B, recommendation
## Risks (updated)
- …
## Next 3 steps
1. …
```
3. Save to `tasks/status/<YYYY-MM-DD>.md`. Do not change statuses in BOARD.md without grounds in the notes.
4. If the `$ARGUMENTS` argument contains `slack` — add a 5–8-line version for the channel at the end.
