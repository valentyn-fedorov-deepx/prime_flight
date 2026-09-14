"""Event session: one turnaround — one continuous frame stream — one tracker — one set of module states.

The rule the whole architecture rests on lives here (X1): the tracker is created ONCE PER EVENT and is never reset
between chunks. Measured on real video, same input, only the tracker lifetime differs:

    continuous, no reset        5 unique "airplanes"    normal
    reset every 60 s           42                       timings fall apart
    reset every 7.5 s         297                       no check works at all

A chunk is a unit of transport, not of processing. A module never sees a chunk boundary.
Ported from G:/gat-streaming/streaming/session.py.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from pf.contract import SCHEMA_VERSION, ContractError, empty_frame, validate_frame


@dataclass
class SessionStats:
    frames_in: int = 0
    frames_filled: int = 0  # placeholders inserted for lost frames
    chunks_in: int = 0
    chunks_missing: int = 0
    started_at: float = field(default_factory=time.time)

    @property
    def loss_rate(self) -> float:
        total = self.frames_in + self.frames_filled
        return self.frames_filled / total if total else 0.0


class Session:
    """Accepts frames in arrival order and hands modules a continuous stream.

    Responsible for exactly two things that exist nowhere in production today:
      * keeps frame numbering continuous even when a chunk never arrives (X2);
      * hides chunk boundaries from modules.
    """

    CHUNK_FRAMES = 60  # 7.5 s × 8 fps

    def __init__(self, event_id: str, *, fps: int = 8, fill_gaps: bool = True, strict_version: bool = True):
        self.event_id = event_id
        self.fps = fps
        self.fill_gaps = fill_gaps
        self.strict_version = strict_version
        self.stats = SessionStats()
        self._next_id = 1
        self._closed = False

    # ---------------------------------------------------------------- intake
    def feed_chunk(self, frames):
        """Accept one chunk. Returns the frames ready to be handed to modules (gaps already filled)."""
        if self._closed:
            raise RuntimeError(f"session {self.event_id} is already closed")
        self.stats.chunks_in += 1
        out = []
        for frame in frames:
            validate_frame(frame, strict_version=self.strict_version)
            gap = frame["frame_id"] - self._next_id
            if gap > 0:
                out.extend(self._fill(gap))
            elif gap < 0:
                raise ContractError(
                    "frame %d arrived after %d — stream is not ordered"
                    % (frame["frame_id"], self._next_id - 1)
                )
            out.append(frame)
            self._next_id = frame["frame_id"] + 1
            self.stats.frames_in += 1
        return out

    def miss_chunk(self, n_frames: int | None = None):
        """A chunk never arrived. Fill the hole so the numbering stays intact."""
        n = self.CHUNK_FRAMES if n_frames is None else n_frames
        self.stats.chunks_missing += 1
        return self._fill(n)

    @property
    def next_frame_id(self) -> int:
        return self._next_id

    def close(self):
        self._closed = True
        return self.stats

    # ---------------------------------------------------------------- internals
    def _fill(self, n: int):
        if not self.fill_gaps:
            # "as-is" behaviour: frames simply vanish and the numbering drifts (kept for measuring the cost)
            self._next_id += n
            return []
        out = [empty_frame(self._next_id + i, SCHEMA_VERSION) for i in range(n)]
        self._next_id += n
        self.stats.frames_filled += n
        return out


def stream_from_chunks(event_id: str, chunks, *, drop=(), fill_gaps=True):
    """Assemble a continuous stream from a sequence of chunks.

    ``drop`` — indices of chunks that "never arrived"; for transport tests.
    """
    sess = Session(event_id, fill_gaps=fill_gaps)
    for i, chunk in enumerate(chunks):
        if i in drop:
            for frame in sess.miss_chunk(len(chunk)):
                yield frame
            continue
        for frame in sess.feed_chunk(chunk):
            yield frame
    sess.close()
