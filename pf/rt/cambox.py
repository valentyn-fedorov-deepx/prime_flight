"""CameraBox + uplink simulator: replays a chunk manifest on the wall clock, the way chunks would reach the server.

A chunk leaves the box only once it is closed: chunk k, which records [t_start, t_end) of recording time, is ready at t_end.
The link adds the round-trip time, optional jitter and the serialisation time of the chunk (bytes * 8 / bandwidth), so the
server holds chunk k completely at

    due = t0 + (t_end + rtt + jitter + bytes * 8 / bandwidth) / speed

where t0 is the wall-clock moment the camera captured frame 1. Arrivals are delivered in time order; with jitter a chunk can
overtake an earlier one, and a lost chunk is delivered as `lost=True` without a file, so the receiver has to order and fill
gaps (X2). `speed` > 1 compresses every duration for smoke tests; measurements use speed 1.
"""

from __future__ import annotations

import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class LinkModel:
    bandwidth_mbps: float = 1000.0  # an ideal gigabit uplink by default
    rtt_ms: float = 10.0
    jitter_ms: float = 0.0  # uniform extra delay in [0, jitter_ms]
    loss: float = 0.0  # probability that a chunk never arrives
    seed: int = 0


@dataclass
class ChunkArrival:
    index: int
    path: str | None  # chunk file; None when the chunk was lost
    first_frame_id: int
    n_frames: int
    t_start: float  # recording time of the first frame (s)
    t_end: float  # recording time at which the chunk closes (s)
    bytes: int
    transfer_s: float  # unscaled network time: rtt + jitter + serialisation
    due: float  # scheduled arrival, monotonic clock
    arrived: float = 0.0  # actual delivery, monotonic clock
    lost: bool = False


def schedule(manifest: dict, link: LinkModel, t0: float, speed: float = 1.0, root: str = "") -> list:
    """Arrival of every chunk of the manifest, sorted by due time."""
    rng = random.Random(link.seed)
    out = []
    for c in manifest["chunks"]:
        jitter = rng.uniform(0.0, link.jitter_ms) / 1000.0 if link.jitter_ms else 0.0
        transfer = link.rtt_ms / 1000.0 + jitter + c["bytes"] * 8.0 / (link.bandwidth_mbps * 1e6)
        lost = bool(link.loss) and rng.random() < link.loss
        out.append(ChunkArrival(c["index"], None if lost else os.path.join(root, c["path"]), c["first_frame_id"],
                                c["n_frames"], c["t_start"], c["t_end"], c["bytes"], transfer,
                                t0 + (c["t_end"] + transfer) / speed, lost=lost))
    return sorted(out, key=lambda a: (a.due, a.index))


class CameraBoxSim:
    """Delivers the scheduled arrivals from a background thread at their due times."""

    def __init__(self, manifest: dict, link: LinkModel | None = None, speed: float = 1.0, root: str = ""):
        self.manifest, self.link, self.speed, self.root = manifest, link or LinkModel(), speed, root
        self.fps = float(manifest["fps"])
        self.t0 = 0.0
        self.arrivals: list = []
        self.done = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def capture_time(self, frame_id: int) -> float:
        """Wall-clock moment the camera captured `frame_id` (monotonic clock)."""
        return self.t0 + (frame_id - 1) / self.fps / self.speed

    def start(self, deliver: Callable[[ChunkArrival], None], t0: float | None = None) -> float:
        self.t0 = time.perf_counter() if t0 is None else t0
        self.arrivals = schedule(self.manifest, self.link, self.t0, self.speed, self.root)
        self._thread = threading.Thread(target=self._run, args=(deliver,), name="cambox", daemon=True)
        self._thread.start()
        return self.t0

    def _run(self, deliver: Callable[[ChunkArrival], None]) -> None:
        try:
            for a in self.arrivals:
                # Event.wait can return up to a timer tick early on Windows: re-check until the due time has passed
                while (remaining := a.due - time.perf_counter()) > 0:
                    if self._stop.wait(remaining):
                        break
                if self._stop.is_set():
                    break
                a.arrived = time.perf_counter()
                deliver(a)
        finally:
            self.done.set()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)
