"""Linux owned-process samples; never infer ownership from an executable name."""

from __future__ import annotations

import ctypes
import json
import os
import threading
import time
from pathlib import Path


class MemorySampler:
    def __init__(
        self,
        *,
        proc_root=Path("/proc"),
        output=None,
        interval=0.25,
        byte_limit=128 * 1024**2,
    ):
        self.proc_root = Path(proc_root)
        self.output = output
        self.interval = interval
        self.byte_limit = byte_limit
        self.identities = {}
        self.roots = {}
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.thread = None
        self.error = None
        self.bytes_written = 0
        self.samples = 0
        self.peaks = {"rss_bytes": 0, "pss_bytes": 0, "swap_pss_bytes": 0}
        self.missing_samples = 0

    def stat(self, pid):
        raw = (self.proc_root / str(pid) / "stat").read_text()
        left = raw.index("(")
        right = raw.rindex(")")
        fields = raw[right + 2 :].split()
        return {
            "pid": int(raw[:left]),
            "name": raw[left + 1 : right],
            "state": fields[0],
            "ppid": int(fields[1]),
            "pgrp": int(fields[2]),
            "session_id": int(fields[3]),
            "start_ticks": int(fields[19]),
        }

    def add_root(self, pid, role):
        with self.lock:
            row = self.stat(pid)
            self.identities[(pid, row["start_ticks"])] = role
            self.roots[(pid, row["start_ticks"])] = role
            return row

    def discover(self):
        current = {}
        for path in self.proc_root.iterdir():
            if not path.name.isdigit():
                continue
            try:
                current[int(path.name)] = self.stat(int(path.name))
            except (OSError, ValueError, IndexError):
                continue
        owned = {
            pid: role
            for (pid, start), role in self.roots.items()
            if pid in current and current[pid]["start_ticks"] == start
        }

        def descendants():
            changed = True
            while changed:
                changed = False
                for pid, row in current.items():
                    parent = row["ppid"]
                    if (
                        pid not in owned
                        and parent in owned
                        and row["start_ticks"] >= current[parent]["start_ticks"]
                    ):
                        owned[pid] = owned[parent]
                        self.identities[(pid, row["start_ticks"])] = owned[parent]
                        changed = True

        descendants()
        # Retain previously observed descendants after reparenting, but current
        # explicit roots take precedence over their former ancestor's label.
        for (pid, start), role in list(self.identities.items()):
            if pid not in owned and pid in current and current[pid]["start_ticks"] == start:
                owned[pid] = role
        descendants()
        return current, owned

    def live(self, role):
        with self.lock:
            current, owned = self.discover()
            return [
                current[pid]
                for pid, label in owned.items()
                if label == role and current[pid]["state"] != "Z"
            ]

    def sample(self):
        with self.lock:
            current, owned = self.discover()
            rows = []
            errors = []
            for pid, role in sorted(owned.items()):
                row = {**current[pid], "role": role}
                try:
                    fields = {}
                    for line in (
                        (self.proc_root / str(pid) / "smaps_rollup").read_text().splitlines()
                    ):
                        key, sep, value = line.partition(":")
                        if sep and key in {"Rss", "Pss", "SwapPss"}:
                            fields[key] = int(value.split()[0]) * 1024
                    if set(fields) != {"Rss", "Pss", "SwapPss"}:
                        raise ValueError("missing rollup field")
                    if self.stat(pid)["start_ticks"] != row["start_ticks"]:
                        raise ValueError("process identity changed")
                    row.update(
                        rss_bytes=fields["Rss"],
                        pss_bytes=fields["Pss"],
                        swap_pss_bytes=fields["SwapPss"],
                    )
                except (OSError, ValueError, IndexError) as exc:
                    row.update(rss_bytes=None, pss_bytes=None, swap_pss_bytes=None)
                    errors.append({"pid": pid, "type": type(exc).__name__})
                rows.append(row)
            result = {
                "monotonic": time.monotonic(),
                "processes": rows,
                "read_errors": errors,
                "complete_continuous_coverage": False,
                "scope": "Observed descendants of captured PID+starttime roots; short-lived or unobserved reparented processes may be missed",
            }
            for name in self.peaks:
                values = [r[name] for r in rows]
                total = sum(values) if all(v is not None for v in values) else None
                result["total_" + name] = total
                if total is not None:
                    self.peaks[name] = max(self.peaks[name], total)
            host = {}
            try:
                for line in (self.proc_root / "meminfo").read_text().splitlines():
                    name, _, value = line.partition(":")
                    if name in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                        host[name + "_bytes"] = int(value.split()[0]) * 1024
            except (OSError, ValueError):
                pass
            result["host"] = host
            self.samples += 1
            self.missing_samples += bool(errors)
            return result

    def start(self):
        if self.thread is not None:
            raise RuntimeError("Sampler already started")
        if self.output is None:
            raise ValueError("Sampler needs an owned evidence path")

        def collect():
            try:
                with Path(self.output).open("xb") as stream:
                    os.chmod(self.output, 0o600)
                    while True:
                        raw = (json.dumps(self.sample(), sort_keys=True) + "\n").encode()
                        if self.bytes_written + len(raw) > self.byte_limit:
                            raise ValueError("Memory sample byte bound reached")
                        stream.write(raw)
                        stream.flush()
                        self.bytes_written += len(raw)
                        self.ready.set()
                        if self.stop_event.wait(self.interval):
                            break
            except BaseException as exc:
                self.error = type(exc).__name__
            finally:
                self.ready.set()

        self.thread = threading.Thread(target=collect, name="owned-memory-sampler", daemon=False)
        self.thread.start()
        if not self.ready.wait(5):
            raise RuntimeError("Memory sampler did not start")
        self.check()

    def check(self):
        if self.error is not None:
            raise RuntimeError("Memory sampling failed: " + self.error)
        if self.thread is None or not self.thread.is_alive():
            raise RuntimeError("Memory sampler is not active")

    def close(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError("Memory sampler did not join")
        return {
            "samples": self.samples,
            "sampled_peak_totals": self.peaks,
            "missing_samples": self.missing_samples,
            "error": self.error,
            "interval_seconds": self.interval,
            "complete_continuous_coverage": False,
            "interpretation": "Same-sample sums. RSS double-counts shared pages; PSS apportions them. Not continuous/allocator peaks.",
        }


def pidfd_api():
    """Some standalone CPython builds omit wrappers; use exported libc functions."""
    library = ctypes.CDLL(None, use_errno=True)
    try:
        opened = library.pidfd_open
        sent = library.pidfd_send_signal
    except AttributeError as exc:
        raise RuntimeError("Atomic owned-process signaling unavailable") from exc
    opened.argtypes = [ctypes.c_int, ctypes.c_uint]
    opened.restype = ctypes.c_int
    sent.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
    sent.restype = ctypes.c_int
    return opened, sent


def pidfd_preflight():
    opened, sent = pidfd_api()
    fd = opened(os.getpid(), 0)
    if fd < 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))
    try:
        if sent(fd, 0, None, 0) < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
    finally:
        os.close(fd)


def signal_identity(row, sig, *, proc_root=Path("/proc")):
    """Pin the process with pidfd, then recheck start time; never signal reused PID."""
    opened, sent = pidfd_api()
    fd = opened(row["pid"], 0)
    if fd < 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))
    try:
        live = MemorySampler(proc_root=proc_root).stat(row["pid"])
        if live["start_ticks"] != row["start_ticks"]:
            raise RuntimeError("Process identity changed before signal")
        if sent(fd, sig, None, 0) < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
    finally:
        os.close(fd)
