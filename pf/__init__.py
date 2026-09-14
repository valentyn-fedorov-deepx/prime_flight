"""Prime Flight core package.

Layout (see pf/README.md):
    pf.contract   frame contract on the bus (schema_version, frame_id, stage/events/anchors) + input hygiene
    pf.receiver   chunk receiver / session registry: one event = one continuous frame stream = one tracker
    pf.gm         General Model v2 interface (frame -> detections); implementation lands after docs/analysis/gm_current.md
    pf.tracker    Tracker v2 interface (detections -> tracks with state); implementation after tracker analysis
    pf.stage      stage detector (causal state machine after the tracker) — design in docs/02_target_architecture.md §5
    pf.eval       parity / regression tooling (old vs new GM+tracker, batch vs stream verdicts)
"""

__version__ = "0.1.0"
