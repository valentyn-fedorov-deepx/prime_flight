# ADR registry

| # | Title | Status | Date | Zone |
|---|---|---|---|---|
| ADR-000 | Template | — | — | — |
| ADR-001 | GM v2 / Tracker v2: compatibility strategy with the 27 modules and chunk-by-chunk processing (v1-compat + v2 bus, gm_core/gm_context, state_dict frozen, stage detector = owner of the anchors) | proposed | 2026-09-14 | GM / Tracker / contract |

Candidates for the first ADRs (from `docs/02_target_architecture.md` and the board):
- Frame contract v1.0 (`schema_version`, `frame_id`, `stage/events/anchors`) — PF-Q1-02/03.
- Stage detector as the sole owner of the anchors; where the code lives (db_worker or a new repo) — PF-Q1-03.
- Chunk size 7.5 s and stream-copy — PF-Q1-01.
- `cv_common` pin policy for modules — PF-Q3-05.
- Redefinition of the S1 check triggers — PF-Q3-06 (one ADR per check).
