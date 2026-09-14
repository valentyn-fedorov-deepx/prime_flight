# ADR-000 · <decision title>

- **Date:** · **Status:** proposed / accepted / superseded by ADR-nnn
- **Author:** · **Reviewers:** Ihor, Serhii (+ Oksana, if the client logic changes)
- **Zone:** frame contract / stage events / client logic of a module / infra / GM-Tracker

## Context
What forces the decision (a measurement, a bug, a client requirement). Links to `docs/` and the `PF-…` task.

## Decision
In one paragraph. What exactly changes (contract fields, event, threshold, trigger).

## Alternatives rejected
- …

## Consequences
- For modules (who consumes): …
- For the client logic (`05_module_logic.md`): unchanged / changed (describe).
- For measurements: what has to be re-measured (parity, Time to Result).

## Actions
- [ ] update `docs/…`
- [ ] `python scripts/build_docs.py` (if the source changed)
- [ ] notify the consumer agents (`module-porter`, `alerting-engineer`)
