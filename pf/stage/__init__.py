"""Stage detector — causal state machine after the tracker (design: docs/02_target_architecture.md §5).

Owner of every anchor event (T_ARR, BL_AT_DOOR, BL_LEAVE, PUSHBACK_ATTACHED, T_DEP). Stamps ``stage``, ``events``
and ``anchors`` into each frame (see pf.contract.frame) and tells the session which modules to open/close.
Implementation is task PF-Q1-03; nothing here yet by design — the vocabulary lives in pf.contract.frame
(STAGES, EVENTS) so that modules and the receiver can already depend on it.
"""

from pf.contract.frame import EVENTS, STAGES

__all__ = ["EVENTS", "STAGES"]
