"""A real-time module as a component: what it declares, what it is given, when it is open, where its outputs go.

Today the branch hands every hosted module the same record and collects whatever it returns once per frame. That makes the
modules one block: they all see everything, they all run for the whole session, and an output waits for the next frame
before it leaves the process. This module is the contract that takes them apart (ADR-004, PF-Q2-13):

    spec = ComponentSpec.for_module("3-stop-brake-check")   # declared inputs, pixels, gate, look-back
    sub  = spec.subscription(class_id_of)                   # the rows and records this component reads
    meta = sub.filter(meta)                                 # what it is given, not everything
    bus  = OutputBus(sinks=[...])                           # outputs leave the moment they are produced

Three separate things, on purpose:
  * **declared inputs** — from the static analysis of the module code (`docs/analysis/module_consumption.json`), so the
    declaration is data, not a guess. Filtering is OFF by default: a wrong declaration would silently starve a module, so
    it is gated by verdict parity per module, exactly like the scoped GM heads and tracker classes.
  * **the gate** — `open_on` / `close_on` stage events with a look-back, from `pf/rt/gating.json`. Until the stage detector
    publishes events (PF-Q1-03) every gate is "always open", and a run records which gate it used.
  * **outputs** — an `OutputBus` with sinks. A component pushes into it from its own reader thread, so a verdict reaches
    the sinks as soon as the module has it, not on the next frame of the pipeline.
"""

from __future__ import annotations

import io
import json
import os
import threading
import time
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONSUMPTION = os.path.join(ROOT, "docs", "analysis", "module_consumption.json")
GATING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gating.json")
ALL_TRACKER_CLASSES = ("airplane", "beltloader", "gse", "person")


OPTICAL_FLOW_KEYS = ("_p0", "_st")  # the tracker's own point clouds: 76 % of a record, read by no module


def without_optical_flow(record: dict) -> dict:
    """Empty the tracker's point clouds, do NOT remove the keys.

    A module hands the whole `state_dict` back to `cv_common.tracked_object.from_state_dict`, which looks up every key
    the state declares in `to_numpy` — a removed `_p0` is a `KeyError` inside the module, which is exactly how the first
    run with subscriptions failed. Emptying keeps the shape of the record and drops the bytes.
    """
    state = record.get("state_dict")
    if not state or not any(key in state for key in OPTICAL_FLOW_KEYS):
        return record
    record = dict(record)
    record["state_dict"] = {**state, **{key: [] for key in OPTICAL_FLOW_KEYS if key in state}}
    return record


@dataclass(frozen=True)
class Subscription:
    """The part of a frame record a component reads. `None` means everything (nothing was declared)."""

    gm_class_ids: frozenset | None = None
    tracker_classes: frozenset | None = None
    pixels: bool = True
    keep_private: bool = True  # the tracker's own optical-flow state (`_p0`, `_st`): 76 % of the record, read by no module

    def filter(self, meta: dict) -> dict:
        if self.gm_class_ids is None and self.tracker_classes is None and self.keep_private:
            return meta
        out = dict(meta)
        if self.gm_class_ids is not None:
            out["general_model"] = [row for row in meta.get("general_model") or [] if int(row[5]) in self.gm_class_ids]
        records = meta.get("trackers") or []
        if self.tracker_classes is not None:
            records = [r for r in records if r.get("cls_str") in self.tracker_classes]
        if not self.keep_private:
            records = [without_optical_flow(r) for r in records]
        out["trackers"] = records
        return out

    def size(self, meta: dict) -> int:
        return len(meta.get("general_model") or []) + len(meta.get("trackers") or [])


@dataclass(frozen=True)
class ComponentSpec:
    """What a module component declares about itself. Built from data, not written by hand."""

    module: str
    pixels: bool = True
    gm_classes: tuple = ()
    tracker_classes: tuple = ()
    state_fields: tuple = ()
    private_fields: tuple = ()  # tracker internals the module reads by their raw key (`_status`, `_obj_id`, …)
    open_on: str | None = None  # stage event; None = open from the first frame of the session
    close_on: str | None = None  # stage event; None = until the end-of-session marker
    lookback_frames: int = 0
    decides_at: str | None = None  # prose from docs/analysis/rt_module_selection.md, for the report
    declared: bool = False  # False when the static analysis has no entry: the component gets everything

    @classmethod
    def for_module(cls, module: str, pixels: bool | None = None) -> "ComponentSpec":
        entry = {}
        if os.path.exists(CONSUMPTION):
            entry = (json.load(io.open(CONSUMPTION, encoding="utf-8"))["modules"] or {}).get(module) or {}
        gm = entry.get("gm") or {}
        tracker = entry.get("tracker") or {}
        gate = (json.load(io.open(GATING, encoding="utf-8")).get(module) or {}) if os.path.exists(GATING) else {}
        if pixels is None:
            pixels = bool((entry.get("pixels") or {}).get("reads_frames", True))
        return cls(
            module=module,
            pixels=bool(pixels),
            gm_classes=tuple(sorted(set(gm.get("class_names") or []) | set(gm.get("class_names_cosmetic") or []))),
            tracker_classes=tuple(tracker.get("classes") or ()),
            state_fields=tuple(tracker.get("state_fields") or ()),
            private_fields=tuple(tracker.get("private_fields") or ()),
            open_on=gate.get("open_on"), close_on=gate.get("close_on"),
            lookback_frames=int(gate.get("lookback_frames") or 0), decides_at=gate.get("decides_at"),
            declared=bool(gm or tracker),
        )

    def reads_optical_flow_state(self) -> bool:
        """Does the module read the tracker's own optical-flow state? (`_status` is not `_st`: compare whole names.)"""
        names = {field.split()[0] for field in self.private_fields if field}
        return bool(names & {"_p0", "_st"})

    def subscription(self, class_id_of=None) -> Subscription:
        """The rows this component reads. Without a class map (or without a declaration) it reads everything."""
        if not self.declared or class_id_of is None:
            return Subscription(pixels=self.pixels)
        ids = {class_id_of(name) for name in self.gm_classes if class_id_of(name) is not None}
        classes = set(self.tracker_classes) or set(ALL_TRACKER_CLASSES)
        return Subscription(gm_class_ids=frozenset(ids) if ids else None,
                            tracker_classes=frozenset(classes), pixels=self.pixels,
                            keep_private=self.reads_optical_flow_state())

    def as_dict(self) -> dict:
        return {"module": self.module, "pixels": self.pixels, "declared": self.declared,
                "gm_classes": list(self.gm_classes), "tracker_classes": list(self.tracker_classes),
                "reads_optical_flow_state": self.reads_optical_flow_state(),
                "gate": {"open_on": self.open_on or "session start", "close_on": self.close_on or "session end",
                         "lookback_frames": self.lookback_frames, "decides_at": self.decides_at}}


class Gate:
    """Open and close a component on stage events.

    `enabled=False` (the default) means nothing publishes stage events yet — the stage detector is PF-Q1-03 — so the gate
    stays open from the first frame and the table is only reported, never applied. A gate that is enabled without an event
    source would starve its module silently, which is exactly what the first gated run did.
    """

    def __init__(self, spec: ComponentSpec, enabled: bool = False):
        self.spec = spec
        self.enabled = bool(enabled)
        self.open = (spec.open_on is None) or not self.enabled
        self.closed = False
        self.opened_at: int | None = 1 if self.open else None
        self.closed_at: int | None = None

    def on_events(self, frame_id: int, events) -> str | None:
        """Returns "open" or "close" on the frame the gate changes state, else None."""
        if self.closed or not self.enabled:
            return None
        events = set(events or ())
        if not self.open and self.spec.open_on in events:
            self.open, self.opened_at = True, frame_id
            return "open"
        if self.open and self.spec.close_on and self.spec.close_on in events:
            self.open, self.closed, self.closed_at = False, True, frame_id
            return "close"
        return None

    def as_dict(self) -> dict:
        return {"open_on": self.spec.open_on or "session start", "close_on": self.spec.close_on or "session end",
                "opened_at": self.opened_at, "closed_at": self.closed_at, "open_now": self.open,
                "gating": "on" if self.enabled else "off — no stage events yet (PF-Q1-03), the table is only reported"}


class OutputBus:
    """Outputs leave the branch the moment they are produced, from whichever thread produced them.

    A sink is `f(output_record: dict)`. Sinks run on the bus thread, never on the frame path; a sink that raises is
    reported once and dropped, because a broken delivery must not stop the branch.
    """

    def __init__(self, sinks=(), t0: float | None = None, capture_time=None):
        self.sinks = list(sinks)
        self.t0 = t0 if t0 is not None else time.perf_counter()
        self.capture_time = capture_time  # frame_id -> capture moment, for the latency of an output
        self.records: list = []
        self.errors: list = []
        self._lock = threading.Lock()
        self._pending: list = []

    def publish(self, output, received_t: float | None = None) -> dict:
        """`output` is an Output produced by a component; it keeps the moment it was produced, not when it was collected."""
        now = time.perf_counter() if received_t is None else received_t
        if not isinstance(output, dict):
            output.emitted_t = output.emitted_t or now
        record = output if isinstance(output, dict) else {
            "kind": output.kind, "name": output.name, "frame_id": output.frame_id, "payload": output.payload}
        record = {**record, "t": round(now - self.t0, 4)}
        if self.capture_time and record.get("frame_id"):
            record["latency_s"] = round(now - self.capture_time(record["frame_id"]), 3)
        with self._lock:
            self.records.append(record)
            self._pending.append(output)  # the object, so the runtime keeps the production moment
        for sink in list(self.sinks):
            try:
                sink(record)
            except Exception as e:  # a sink must never break the branch
                self.errors.append({"sink": getattr(sink, "__name__", repr(sink)), "error": f"{type(e).__name__}: {e}"})
                self.sinks.remove(sink)
        return record

    def drain(self) -> list:
        """The outputs produced since the last call, as they were produced (the sinks already have them)."""
        with self._lock:
            pending, self._pending = self._pending, []
        return pending

    def wait(self, timeout_s: float = 0.0) -> list:
        """Drain, waiting up to `timeout_s` for the first output (for a consumer that is not driven by frames)."""
        deadline = time.perf_counter() + timeout_s
        while True:
            pending = self.drain()
            if pending or time.perf_counter() >= deadline:
                return pending
            time.sleep(0.002)

    def report(self) -> dict:
        kinds: dict = {}
        for r in self.records:
            kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        return {"outputs": len(self.records), "by_kind": kinds, "sink_errors": self.errors}


def ndjson_sink(path: str):
    """Every output written to a file the moment it is produced (the alert service reads this until it has an endpoint)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    handle = io.open(path, "w", encoding="utf-8", newline="\n")  # one file per run, not a growing mix of runs

    def sink(record: dict) -> None:
        handle.write(json.dumps(record, default=str) + "\n")
        handle.flush()

    sink.close = handle.close  # type: ignore[attr-defined]
    return sink


def http_sink(url: str, timeout_s: float = 2.0, queue_size: int = 1000):
    """Every output POSTed as JSON to an endpoint, from a background thread: the branch never waits for the network.

    This is the seam for the alert service (PF-Q3-01): until it exists, point it at any collector, or leave it unset and
    read `component_outputs.ndjson`. Delivery is best effort — failures are counted, never retried into the frame path.
    """
    import queue as queue_mod
    import urllib.request

    pending: "queue_mod.Queue" = queue_mod.Queue(maxsize=queue_size)
    state = {"sent": 0, "dropped": 0, "failed": 0, "last_error": None}

    def worker():
        while True:
            record = pending.get()
            if record is None:
                return
            try:
                body = json.dumps(record, default=str).encode("utf-8")
                request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=timeout_s):
                    state["sent"] += 1
            except Exception as e:
                state["failed"] += 1
                state["last_error"] = f"{type(e).__name__}: {str(e)[:200]}"

    thread = threading.Thread(target=worker, name="output-http-sink", daemon=True)
    thread.start()

    def sink(record: dict) -> None:
        try:
            pending.put_nowait(record)
        except Exception:
            state["dropped"] += 1  # a stalled endpoint must not slow the branch down

    sink.state = state  # type: ignore[attr-defined]
    sink.close = lambda: pending.put(None)  # type: ignore[attr-defined]
    return sink


def specs_for(modules, pixels_of=None) -> list:
    return [ComponentSpec.for_module(m, None if pixels_of is None else pixels_of(m)) for m in modules]
