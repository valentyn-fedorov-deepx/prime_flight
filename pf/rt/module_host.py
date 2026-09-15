"""Production modules in their own processes, fed frame by frame by one real-time pipeline (pixel-free modules).

A production module imports its own `main`, `cv_common` and `db_worker` packages by name, so two modules cannot share a
process. `ModuleHost` starts one child process per module (spawn), hands every published frame's rows over a pipe without
waiting for the module, and collects the outputs the module emits. The pipeline stays one process per camera (decode, GM,
tracker); the modules run in parallel on their own CPU cores. A slow module fills its pipe and then slows the pipeline down:
backpressure, never dropped frames. Pixel modules need shared frame memory and are not hosted yet.

    host = ModuleHost("3-stop-brake-check", module_args)   # the kwargs of ProductionModuleAdapter (profile facts)
    host.start(manifest, fps)
    outs = host.push(frame_id, {"general_model": rows, "trackers": records})   # returns outputs that arrived meanwhile
    outs += host.close()                                                          # verdict, audit, per-frame cost
"""

from __future__ import annotations

import multiprocessing as mp
import os
import sys
import time
import traceback
from dataclasses import asdict

from pf.rt.runtime import Output

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _stats(times: list) -> dict:
    if not times:
        return {"frames": 0}
    ordered = sorted(times)
    pick = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]
    return {"frames": len(times), "mean_ms": round(1000 * sum(times) / len(times), 3), "p95_ms": round(1000 * pick(0.95), 3),
            "max_ms": round(1000 * ordered[-1], 3)}


def _host_main(conn, kwargs: dict, manifest: dict, fps: float) -> None:
    """Child process: one ProductionModuleAdapter with live metadata."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    times: list = []
    try:
        from pf.rt.prod_module import ProductionModuleAdapter

        adapter = ProductionModuleAdapter(**kwargs)
        adapter.configure(manifest)
        adapter.start(fps)
        conn.send(("ready",))
        while True:
            msg = conn.recv()
            if msg[0] == "frame":
                t0 = time.perf_counter()
                outs = adapter.push(msg[1], None, msg[2])
                times.append(time.perf_counter() - t0)
                if outs:
                    conn.send(("outs", [asdict(o) for o in outs]))
            elif msg[0] == "close":
                outs = adapter.close()
                conn.send(("closed", [asdict(o) for o in outs], _stats(times)))
                return
    except Exception as e:  # report instead of dying silently: the parent turns it into an output
        conn.send(("failed", f"{type(e).__name__}: {str(e)[:400]}", traceback.format_exc()[-3000:], _stats(times)))


class ModuleHost:
    def __init__(self, module: str, module_args: dict | None = None):
        args = dict(module_args or {})
        args.pop("inferences_dir", None)
        args.update(module=module, metadata="live")
        for key in ("module_dir", "work_dir"):  # the parent may change its working directory later
            if args.get(key):
                args[key] = os.path.abspath(args[key])
        args["prepend_path"] = [os.path.abspath(p) for p in args.get("prepend_path") or []]
        self.module, self.args = module, args
        self.stats: dict | None = None
        self.failed: str | None = None
        self.proc = self.conn = None
        self._closed = False

    def start(self, manifest: dict, fps: float, timeout_s: float = 600.0) -> None:
        ctx = mp.get_context("spawn")
        self.conn, child = ctx.Pipe()
        self.proc = ctx.Process(target=_host_main, args=(child, self.args, manifest, fps), name=f"host:{self.module}",
                                daemon=True)
        self.proc.start()
        child.close()
        if not self.conn.poll(timeout_s):
            raise TimeoutError(f"module host {self.module} did not start within {timeout_s} s")
        msg = self.conn.recv()
        if msg[0] != "ready":
            raise RuntimeError(f"module host {self.module} failed to start: {msg[1:3]}")

    def push(self, frame_id: int, meta: dict) -> list:
        if not self._closed:
            try:
                self.conn.send(("frame", frame_id, meta))
            except (BrokenPipeError, EOFError, OSError):
                self._closed = True
        return self.poll()

    def poll(self) -> list:
        out = []
        try:
            while not self._closed and self.conn.poll():
                out.extend(self._handle(self.conn.recv()))
        except (BrokenPipeError, EOFError, OSError):
            self._closed = True
        return out

    def _handle(self, msg) -> list:
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
        out = []
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
