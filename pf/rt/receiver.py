"""Server-side chunk receiver: releases chunks in recording order, infers lost chunks, keeps frame ids explicit.

Chunks may arrive out of order (jitter) or never (loss); the network does not announce a loss. The receiver releases chunk
k only when every earlier chunk has been released or declared lost. A chunk is declared lost when a later chunk has been
waiting for `reorder_timeout_s`, or at once when the camera has closed the recording. The frames of a lost range become
placeholders whose count follows from the first frame id of the next chunk that did arrive — or, at the end, from the frame
count in the end-of-recording message — so frame ids are never shifted (X2).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class Release:
    """What the receiver hands to the decoder: one received chunk, or a gap of placeholder frames."""

    arrival: object | None  # pf.rt.cambox.ChunkArrival, None for a gap
    first_frame_id: int
    n_frames: int
    released_t: float
    lost_indices: tuple = ()


@dataclass
class ReceiverStats:
    chunks_in: int = 0
    chunks_lost: int = 0
    frames_filled: int = 0
    late_dropped: int = 0
    max_pending: int = 0
    gaps: list = field(default_factory=list)


class ChunkReceiver:
    def __init__(self, first_frame_id: int = 1, reorder_timeout_s: float = 2.0):
        self.timeout = reorder_timeout_s
        self.stats = ReceiverStats()
        self._cv = threading.Condition()
        self._pending: dict = {}  # chunk index -> (arrival, received monotonic time)
        self._next_index = 0
        self._next_frame_id = first_frame_id
        self._total_frames: int | None = None
        self._first_frame_id = first_frame_id

    def put(self, arrival) -> None:
        with self._cv:
            if arrival.index < self._next_index:
                self.stats.late_dropped += 1  # already declared lost; its frames were filled
                return
            self._pending[arrival.index] = (arrival, time.perf_counter())
            self.stats.chunks_in += 1
            self.stats.max_pending = max(self.stats.max_pending, len(self._pending))
            self._cv.notify_all()

    def close(self, total_frames: int) -> None:
        """End-of-recording message: the camera captured `total_frames` frames in this session."""
        with self._cv:
            self._total_frames = total_frames
            self._cv.notify_all()

    def pending(self) -> int:
        with self._cv:
            return len(self._pending)

    def _gap(self, first_frame_id: int, n_frames: int, lost: tuple) -> Release:
        self.stats.chunks_lost += len(lost)
        self.stats.frames_filled += n_frames
        self.stats.gaps.append({"first_frame_id": first_frame_id, "n_frames": n_frames, "chunks": list(lost)})
        return Release(None, first_frame_id, n_frames, time.perf_counter(), lost)

    def next(self, poll_s: float = 0.05):
        """Block until the next release; None once the recording is closed and everything has been released."""
        with self._cv:
            while True:
                item = self._pending.pop(self._next_index, None)
                if item is not None:
                    arrival = item[0]
                    self._next_index += 1
                    self._next_frame_id = arrival.first_frame_id + arrival.n_frames
                    return Release(arrival, arrival.first_frame_id, arrival.n_frames, time.perf_counter())
                closed = self._total_frames is not None
                if self._pending:
                    later = min(self._pending)
                    arrival, received = self._pending[later]
                    waited = time.perf_counter() - received
                    if closed or waited >= self.timeout:
                        rel = self._gap(self._next_frame_id, arrival.first_frame_id - self._next_frame_id,
                                        tuple(range(self._next_index, later)))
                        self._next_index, self._next_frame_id = later, arrival.first_frame_id
                        return rel
                    self._cv.wait(min(poll_s, self.timeout - waited))
                    continue
                if closed:
                    end = self._first_frame_id + self._total_frames
                    if self._next_frame_id < end:
                        rel = self._gap(self._next_frame_id, end - self._next_frame_id, (self._next_index,))
                        self._next_frame_id = end
                        return rel
                    return None
                self._cv.wait(poll_s)
