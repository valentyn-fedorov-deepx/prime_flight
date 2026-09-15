"""Module adapters for the real-time branch.

    ProbeAdapter   negligible-cost control: measures the branch itself (chunk close + link + decode + queues); an optional
                   fixed per-frame cost emulates a module of that cost, to see where real time breaks.
"""

from __future__ import annotations

import time

from pf.rt.runtime import Adapter, Frame, Output


class ProbeAdapter(Adapter):
    """Mean brightness of a downscaled frame; an event when it jumps by more than `delta` from the running mean.

    `cost_ms` adds a busy wait per frame (0 = none), so a run can emulate a module that needs that long per frame.
    """

    name = "probe"

    def __init__(self, delta: float = 12.0, cost_ms: float = 0.0, note_every_s: float = 60.0):
        self.delta, self.cost_ms, self.note_every_s = delta, cost_ms, note_every_s

    def start(self, fps: float) -> None:
        super().start(fps)
        self.mean = None
        self.frames = self.missing = self.events = 0

    def on_frame(self, frame: Frame) -> list:
        self.frames += 1
        out = []
        if frame.missing:
            self.missing += 1
        else:
            small = frame.image[::16, ::16]
            b = float(small.mean())
            if self.mean is not None and abs(b - self.mean) > self.delta:
                self.events += 1
                out.append(Output("event", "brightness_step", frame.frame_id, {"from": round(self.mean, 1), "to": round(b, 1)}))
            self.mean = b if self.mean is None else 0.9 * self.mean + 0.1 * b
        if self.cost_ms:
            end = time.perf_counter() + self.cost_ms / 1000.0
            while time.perf_counter() < end:
                pass
        if self.note_every_s and frame.frame_id % max(1, int(self.note_every_s * self.fps)) == 0:
            out.append(Output("note", "progress", frame.frame_id, {"frames": self.frames}))
        return out

    def close(self) -> list:
        return [Output("verdict", "probe_summary", None, {"frames": self.frames, "missing": self.missing, "events": self.events})]


# name -> "module:Class"; imported only when used, so heavy module dependencies load only for their own runs
ADAPTERS = {"probe": "pf.rt.adapters:ProbeAdapter"}


def make_adapter(name: str, **kwargs) -> Adapter:
    import importlib

    module, cls = ADAPTERS[name].split(":")
    return getattr(importlib.import_module(module), cls)(**kwargs)
