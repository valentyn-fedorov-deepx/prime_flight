---
name: pf-task
description: Break a new Prime Flight request/idea down into board tasks — ID PF-Qn-nn, human owner, agent, deps, measurable acceptance, tags — add to tasks/BOARD.md and create tasks/notes/<ID>.md from the template. Argument — the request description.
---

Request: `$ARGUMENTS`

1. Read `CLAUDE.md`, `tasks/BOARD.md`, `docs/07_team.md` (zones of people/agents), `docs/06_roadmap.md` (which quarter it belongs to).
2. Determine: the quarter (by theme), the next free number `PF-Qn-nn` (or `PF-X-nn` for cross-cutting ones), the human owner by zone, the agent from the table in `CLAUDE.md`.
3. Write the acceptance as **measurable**: a number/measurement/artifact (parity 0 discrepancies on N videos; latency ≤ X ms p95; a table in the notes). No "improve/investigate".
4. Deps — only existing IDs. Tags: `trigger-change` (changes the moment/condition of a check's decision), `decision-needed` (Ihor/the lead is required), `external` (outside the CV zone).
5. Add a row to the corresponding table in `tasks/BOARD.md` (do not break the markdown table), create `tasks/notes/<ID>.md` from `tasks/TEMPLATE.md`, fill in the Context with links to the docs sections.
6. If the request changes the frame contract/events/client logic — additionally create `docs/decisions/ADR-nnn-<slug>.md` with status proposed.
7. Reply: the ID, the task in one line, who it is assigned to, what needs clarification.
