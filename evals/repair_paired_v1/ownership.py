"""Pinned Linux worker ownership copied from reviewed v6; no server launcher."""

import os
import select
import signal
import subprocess
import threading
import time
from pathlib import Path
from memory_sampler import pidfd_preflight, signal_identity


class OwnedProcess:
    def __init__(self, command, *, cwd, env, artifacts, sampler, role):
        self.command = command
        self.cwd = cwd
        self.env = env
        self.artifacts = Path(artifacts)
        self.sampler = sampler
        self.role = role
        self.process = None
        self.drainers = []
        self.output = {}
        self.identity = None
        self._stop_capture = threading.Event()

    def start(self):
        pidfd_preflight()  # Refuse before starting anything if cleanup cannot pin identities.
        self.artifacts.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
        )
        try:
            self.identity = self.sampler.add_root(self.process.pid, self.role)
        except BaseException:
            self.process.kill()
            self.process.wait(timeout=3)
            self.process.stdout.close()
            self.process.stderr.close()
            raise
        for name, source in [
            ("stdout", self.process.stdout),
            ("stderr", self.process.stderr),
        ]:
            self.output[name] = {"bytes": 0, "omitted_bytes": 0, "eof_observed": False}
            os.set_blocking(source.fileno(), False)

            def drain(name=name, source=source):
                try:
                    with (self.artifacts / (name + ".log")).open("xb") as target:
                        os.chmod(target.name, 0o600)
                        while not self._stop_capture.is_set():
                            # An unobserved, reparented descendant can retain a
                            # writer indefinitely. Our reader must remain owned
                            # and stoppable without waiting for that child's EOF.
                            ready, _, _ = select.select([source.fileno()], [], [], 0.05)
                            if not ready:
                                continue
                            try:
                                chunk = os.read(source.fileno(), 65536)
                            except BlockingIOError:
                                continue
                            if not chunk:
                                self.output[name]["eof_observed"] = True
                                break
                            row = self.output[name]
                            room = max(0, 2 * 1024**2 - row["bytes"])
                            target.write(chunk[:room])
                            row["bytes"] += len(chunk)
                            row["omitted_bytes"] += max(0, len(chunk) - room)
                except BaseException as exc:
                    self.output[name]["error"] = type(exc).__name__
                finally:
                    source.close()

            thread = threading.Thread(target=drain, name="owned-" + name, daemon=False)
            thread.start()
            self.drainers.append(thread)
        return self

    def stop(self):
        if self.process is None:
            return {"started": False}
        errors = []
        for sig, allowance in [(signal.SIGTERM, 3), (signal.SIGKILL, 3)]:
            for row in self.sampler.live(self.role):
                try:
                    signal_identity(row, sig)
                except ProcessLookupError:
                    pass
                except BaseException as exc:
                    errors.append(type(exc).__name__)
            deadline = time.monotonic() + allowance
            while self.sampler.live(self.role) and time.monotonic() < deadline:
                time.sleep(0.02)
            if not self.sampler.live(self.role):
                break
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            errors.append("parent_wait_timeout")
        drain_deadline = time.monotonic() + 1
        for thread in self.drainers:
            thread.join(timeout=max(0, drain_deadline - time.monotonic()))
        self._stop_capture.set()
        for thread in self.drainers:
            thread.join(timeout=1)
            if thread.is_alive():
                errors.append("output_drain_unjoined")
        readers_joined = all(not thread.is_alive() for thread in self.drainers)
        output_eof_observed = all(row["eof_observed"] for row in self.output.values())
        if not output_eof_observed:
            errors.append("output_eof_unobserved")
        if any(row.get("error") for row in self.output.values()):
            errors.append("output_capture_failed")
        remaining = self.sampler.live(self.role)
        if remaining:
            errors.append("owned_processes_remain")
        return {
            "started": True,
            "joined": not errors,
            "readers_joined": readers_joined,
            "output_eof_observed": output_eof_observed,
            "errors": errors,
            "output": self.output,
            "returncode": self.process.returncode,
        }
