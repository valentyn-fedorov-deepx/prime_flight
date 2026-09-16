"""Production modules in their own processes, fed frame by frame by one real-time pipeline.

A production module imports its own `main`, `cv_common` and `db_worker` packages by name, so two modules cannot share a
process. `ModuleHost` starts one child process per module (spawn), hands every published frame over a pipe without waiting
for the module, and collects the outputs the module emits. The pipeline stays one process per camera (decode, GM, tracker);
the modules run in parallel on their own CPU cores. A slow module fills its pipe and then slows the pipeline down:
backpressure, never dropped frames.

Modules that read pixels get the frames through one shared-memory ring (`SharedFrameRing`): the pipeline writes each
published frame into a slot and the host copies it out before the module sees it, so a module may keep frames as long as
its own logic needs. The host acknowledges every copy and the pipeline never overwrites a slot that has not been copied.

    ring = SharedFrameRing()                                   # only if some module reads pixels
    host = ModuleHost("safety-vests-secured-to-body", args, pixels=True)
    host.start(manifest, fps, ring.spec)
    slot = ring.write(frame_id, image, [host])                 # waits if the host has not copied that slot yet
    outs = host.push(frame_id, {"general_model": rows, "trackers": records}, slot)
    outs += host.close()
"""

from __future__ import annotations

import multiprocessing as mp
import os
import sys
import time
import traceback
from dataclasses import asdict

import numpy as np

from pf.rt.runtime import Output

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _stats(times: list) -> dict:
    if not times:
        return {"frames": 0}
    ordered = sorted(times)
    pick = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]
    return {"frames": len(times), "mean_ms": round(1000 * sum(times) / len(times), 3), "p95_ms": round(1000 * pick(0.95), 3),
            "max_ms": round(1000 * ordered[-1], 3)}


class SharedFrameRing:
    """One shared-memory ring of decoded frames: written once by the pipeline, copied by every host that reads pixels."""

    def __init__(self, shape=(1080, 1920, 3), slots: int = 16):
        from multiprocessing import shared_memory

        self.shape, self.slots = tuple(int(x) for x in shape), int(slots)
        self.frame_bytes = int(np.prod(self.shape))
        self.shm = shared_memory.SharedMemory(create=True, size=self.frame_bytes * self.slots)
        self.spec = {"name": self.shm.name, "shape": list(self.shape), "slots": self.slots}

    def write(self, frame_id: int, image, hosts=()) -> int | None:
        """Wait until every host has copied the frame that occupies this slot, then write and return the slot."""
        if image is None:
            return None
        for host in hosts:
            host.wait_for_slot(frame_id, self.slots)
        slot = frame_id % self.slots
        view = np.ndarray(self.shape, dtype=np.uint8, buffer=self.shm.buf, offset=slot * self.frame_bytes)
        view[:] = image
        return slot

    def close(self) -> None:
        try:
            self.shm.close()
            self.shm.unlink()
        except (FileNotFoundError, BufferError):
            pass


def _attach_ring(spec):
    from multiprocessing import shared_memory

    shm = shared_memory.SharedMemory(name=spec["name"])
    shape = tuple(int(x) for x in spec["shape"])
    return shm, shape, int(np.prod(shape))


def _host_main(conn, kwargs: dict, manifest: dict, fps: float, frame_spec: dict | None) -> None:
    """Child process: one ProductionModuleAdapter with live metadata (and pixels from the ring, if it reads them)."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    times: list = []
    shm = None
    try:
        from pf.rt.prod_module import ProductionModuleAdapter

        shape = frame_bytes = None
        if frame_spec:
            shm, shape, frame_bytes = _attach_ring(frame_spec)
        adapter = ProductionModuleAdapter(**kwargs)
        adapter.configure(manifest)
        adapter.start(fps)
        conn.send(("ready",))
        while True:
            msg = conn.recv()
            if msg[0] == "frame":
                _, frame_id, meta, slot = msg
                image = None
                if slot is not None and shm is not None:
                    image = np.ndarray(shape, dtype=np.uint8, buffer=shm.buf, offset=slot * frame_bytes).copy()
                    conn.send(("ack", frame_id))  # the slot is free again
                t0 = time.perf_counter()
                outs = adapter.push(frame_id, image, meta)
                times.append(time.perf_counter() - t0)
                if outs:
                    conn.send(("outs", [asdict(o) for o in outs]))
            elif msg[0] == "close":
                outs = adapter.close()
                conn.send(("closed", [asdict(o) for o in outs], _stats(times)))
                return
    except Exception as e:  # report instead of dying silently: the parent turns it into an output
        conn.send(("failed", f"{type(e).__name__}: {str(e)[:400]}", traceback.format_exc()[-3000:], _stats(times)))
    finally:
        if shm is not None:
            shm.close()


class ModuleHost:
    def __init__(self, module: str, module_args: dict | None = None, pixels: bool = False):
        args = dict(module_args or {})
        args.pop("inferences_dir", None)
        args.update(module=module, metadata="live")
        for key in ("module_dir", "work_dir"):  # the parent may change its working directory later
            if args.get(key):
                args[key] = os.path.abspath(args[key])
        args["prepend_path"] = [os.path.abspath(p) for p in args.get("prepend_path") or []]
        self.module, self.args, self.pixels = module, args, pixels
        self.stats: dict | None = None
        self.failed: str | None = None
        self.proc = self.conn = None
        self.waits = 0
        self.wait_s = 0.0
        self._last_ack = 0
        self._buffered: list = []
        self._closed = False

    def start(self, manifest: dict, fps: float, frame_spec: dict | None = None, timeout_s: float = 600.0) -> None:
        ctx = mp.get_context("spawn")
        self.conn, child = ctx.Pipe()
        self.proc = ctx.Process(target=_host_main, args=(child, self.args, manifest, fps, frame_spec if self.pixels else None),
                                name=f"host:{self.module}", daemon=True)
        self.proc.start()
        child.close()
        if not self.conn.poll(timeout_s):
            raise TimeoutError(f"module host {self.module} did not start within {timeout_s} s")
        msg = self.conn.recv()
        if msg[0] != "ready":
            raise RuntimeError(f"module host {self.module} failed to start: {msg[1:3]}")

    def wait_for_slot(self, frame_id: int, slots: int, timeout_s: float = 300.0) -> None:
        """Block while the module has not yet copied the frame that occupies the slot `frame_id` is about to take."""
        if not self.pixels or self._closed:
            return
        t0 = time.perf_counter()
        deadline = t0 + timeout_s
        waited = False
        while frame_id - self._last_ack > slots - 1 and not self._closed:
            waited = True
            if time.perf_counter() > deadline:
                raise TimeoutError(f"module host {self.module} has not copied frame {self._last_ack + 1}")
            try:
                if self.conn.poll(0.05):
                    self._buffered.extend(self._handle(self.conn.recv()))
            except (BrokenPipeError, EOFError, OSError):
                self._closed = True
        if waited:
            self.waits += 1
            self.wait_s += time.perf_counter() - t0

    def push(self, frame_id: int, meta: dict, slot: int | None = None) -> list:
        if not self._closed:
            try:
                self.conn.send(("frame", frame_id, meta, slot if self.pixels else None))
            except (BrokenPipeError, EOFError, OSError):
                self._closed = True
        return self.poll()

    def poll(self) -> list:
        out, self._buffered = self._buffered, []
        try:
            while not self._closed and self.conn.poll():
                out.extend(self._handle(self.conn.recv()))
        except (BrokenPipeError, EOFError, OSError):
            self._closed = True
        return out

    def _handle(self, msg) -> list:
        if msg[0] == "ack":
            self._last_ack = max(self._last_ack, int(msg[1]))
            return []
        if msg[0] == "outs":
            return [Output(**o) for o in msg[1]]
        if msg[0] == "closed":
            self._closed, self.stats = True, msg[2]
            return [Output(**o) for o in msg[1]]
        if msg[0] == "failed":
            self._closed, self.failed, self.stats = True, msg[1], msg[3]
            return [Output("note", "module_host_error", None, {"module": self.module, "error": msg[1], "traceback": msg[2]})]
        return []

    def close(self, timeout_s: float = 900.0) -> list:
        out = list(self._buffered)
        self._buffered = []
        if not self._closed:
            try:
                self.conn.send(("close",))
            except (BrokenPipeError, EOFError, OSError):
                self._closed = True
        deadline = time.perf_counter() + timeout_s
        try:
            while not self._closed and time.perf_counter() < deadline:
                if self.conn.poll(1.0):
                    out.extend(self._handle(self.conn.recv()))
        except (BrokenPipeError, EOFError, OSError):
            self._closed = True
        if self.proc is not None:
            self.proc.join(timeout=30)
        return out
